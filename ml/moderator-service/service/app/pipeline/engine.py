import time
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.moderate import ModerationRequest, ModerationResponse, LatencyResult
from app.schemas.profile import RulesProfileResponse
from app.pipeline.stage0_language import Stage0Language
from app.pipeline.stage1_prefilter import Stage1Prefilter
from app.pipeline.stage2_classifier import Stage2Classifier
from app.pipeline.stage2_llm import Stage2LLM
from app.pipeline.stage3_faiss import FaissService
from app.cache.feedback_cache import FeedbackTemplateService
from app.llm.factory import get_provider

_llm_provider = None

# ── Academic / Reporting Context Guard ───────────────────────────────────────
# Detects messages that DISCUSS a topic vs PERPETUATE it.
# Prevents FAISS + LLM false positives on neutral/analytical messages.
_REPORTING_CONTEXT_PHRASES = [
    "is a serious issue", "we must discuss", "we should discuss",
    "research shows", "study found", "statistics show",
    "awareness about", "must talk about", "should address",
    "is a problem", "should I report", "how to report",
    "reporting this", "i want to report",
    "what is", "why does", "how does",
    "can someone explain",
    # Threat-reporting context (victim describing threat they received)
    "i received a threat", "someone threatened me", "i was threatened",
    "got a threat", "being threatened", "threatening messages",
    # Scam-awareness context
    "explaining a scam", "warning about", "be careful of",
    "this is a scam", "watch out for", "don't fall for",
    # News / journalism context
    "news report", "according to reports", "breaking news",
    "in the news", "reported that", "journalists say",
    "according to police", "according to authorities",
    # Gaming / competitive banter context
    "in the game", "in this match", "competitive gaming",
    "trash talk", "friendly banter", "just joking",
    "just kidding", "lol i will", "haha i will",
]

def _is_reporting_context(text: str) -> bool:
    text_lower = text.lower()
    return any(phrase in text_lower for phrase in _REPORTING_CONTEXT_PHRASES)


class ModerationEngine:
    @staticmethod
    async def moderate(
        request: ModerationRequest,
        profile: RulesProfileResponse,
        db: AsyncSession,
        redis: Redis
    ) -> ModerationResponse:
        global _llm_provider
        if _llm_provider is None:
            _llm_provider = get_provider()

        total_start = time.perf_counter()

        # ── Stage 0: Language Detection ───────────────────────────────────────
        lang_ctx, latency_stage0 = Stage0Language.process(request.message)

        # ── Stage 1: Deterministic Pre-filter ─────────────────────────────────
        s1_start = time.perf_counter()
        prefilter_result = await Stage1Prefilter.process(
            request.message, profile, lang_ctx, request.user_id, redis
        )
        latency_stage1 = int((time.perf_counter() - s1_start) * 1000)

        if prefilter_result.blocked:
            total_latency = int((time.perf_counter() - total_start) * 1000)
            feedback = await FeedbackTemplateService.render(
                rule_type=prefilter_result.template_key or "keyword",
                lang_code=lang_ctx.code,
                context={"violation": prefilter_result.matched},
                db=db, redis=redis
            )
            _category_fallback = {
                "pii": "PII", "spam": "SPAM", "profanity": "PROFANITY",
                "hate_speech": "HATE_SPEECH", "threat": "THREAT",
                "keyword": "HATE_SPEECH",
            }
            stage1_category = (
                prefilter_result.category
                or _category_fallback.get(prefilter_result.template_key, "NONE")
            )
            return ModerationResponse(
                decision="BLOCK",
                category=stage1_category,
                detected_language=lang_ctx.code,
                stage_triggered=prefilter_result.stage,
                confidence=1.0,
                violated_rule=prefilter_result.template_key or "keyword",
                reason=f"Blocked by Stage 1: {prefilter_result.matched}",
                feedback_message=feedback,
                latency_ms=LatencyResult(
                    stage0_lang=latency_stage0,
                    stage1=latency_stage1,
                    total=total_latency,
                    llm_provider=None
                ),
                metadata=request.metadata
            )

        # ── Compute embedding once — shared by Stage 2A and Stage 3 ──────────
        # FaissService.encode() normalises the vector (required for cosine sim).
        # Passing it downstream avoids a second encode() call (~10ms saving).
        embedding = FaissService.encode(lang_ctx.normalised_text)

        # ── Stage 2A: Local Classifier ────────────────────────────────────────
        # Receives pre-computed 768-dim embedding — NOT raw text.
        # Returns: decision (BLOCK/HINT/ALLOW), category, confidence, hint.
        # BLOCK  (conf >= 0.80, category != NONE) → skip FAISS + LLM entirely
        # HINT   (conf 0.40–0.80)                 → pass to LLM with hint
        # ALLOW  (conf < 0.40)                    → continue to FAISS
        s2a_start = time.perf_counter()
        classifier_result = Stage2Classifier.predict(embedding)
        latency_stage2a = int((time.perf_counter() - s2a_start) * 1000)

        if classifier_result and classifier_result["decision"] == "BLOCK":
            total_latency = int((time.perf_counter() - total_start) * 1000)
            feedback = await FeedbackTemplateService.render(
                rule_type=classifier_result["category"].lower(),
                lang_code=lang_ctx.code,
                context={},
                db=db, redis=redis
            )
            return ModerationResponse(
                decision="BLOCK",
                category=classifier_result["category"],
                detected_language=lang_ctx.code,
                stage_triggered="stage2_classifier",
                confidence=classifier_result["confidence"],
                violated_rule=classifier_result["category"].lower(),
                reason=(
                    f"Blocked by local classifier: {classifier_result['category']} "
                    f"(conf: {classifier_result['confidence']:.2f})"
                ),
                feedback_message=feedback,
                latency_ms=LatencyResult(
                    stage0_lang=latency_stage0,
                    stage1=latency_stage1,
                    stage2_llm=latency_stage2a,
                    total=total_latency,
                    llm_provider="classifier"
                ),
                metadata=request.metadata
            )

        # ── Stage 3: FAISS Semantic Search ────────────────────────────────────
        # Passes pre-computed embedding to avoid a second encode() call.
        s3_start = time.perf_counter()
        faiss_result = await FaissService.search(
            lang_ctx.normalised_text,
            profile.profile_id,
            profile.faiss_threshold,
            db,
            precomputed_embedding=embedding
        )
        latency_stage3 = int((time.perf_counter() - s3_start) * 1000)

        # Reporting context guard — downgrade FAISS hard block to hint
        faiss_decision = faiss_result.decision
        faiss_score    = faiss_result.score
        if faiss_decision == "BLOCK" and _is_reporting_context(request.message):
            faiss_decision = "HINT"
            faiss_score    = faiss_score * 0.85

        faiss_hint = None
        if faiss_decision == "HINT":
            faiss_hint = (faiss_result.topic, faiss_score)

        # ── Stage 2B: LLM ─────────────────────────────────────────────────────
        # Only reached when classifier or FAISS is uncertain.
        # Target: ~10-20% of traffic.
        s2_start = time.perf_counter()
        llm_response = None

        classifier_uncertain = (
            classifier_result is not None
            and classifier_result["decision"] == "HINT"
        )
        faiss_hinting   = faiss_decision == "HINT"
        keyword_hinting = bool(prefilter_result.keyword_hint)

        needs_llm = (
            faiss_decision != "BLOCK"
            and (classifier_uncertain or faiss_hinting or keyword_hinting)
        )

        if needs_llm:
            combined_hint = prefilter_result.keyword_hint
            if (
                classifier_result
                and classifier_result.get("hint")
                and "classifier_unavailable" not in classifier_result["hint"]
            ):
                combined_hint = (
                    f"{classifier_result['hint']}. {combined_hint}"
                    if combined_hint
                    else classifier_result["hint"]
                )

            llm_response = await Stage2LLM.process(
                request.message,
                profile,
                lang_ctx,
                _llm_provider,
                db,
                redis,
                faiss_hint=faiss_hint,
                keyword_hint=combined_hint
            )

        latency_stage2 = int((time.perf_counter() - s2_start) * 1000)
        total_latency  = int((time.perf_counter() - total_start) * 1000)

        # ── Final Decision ────────────────────────────────────────────────────
        stage_triggered = None
        decision        = "ALLOW"
        category        = "NONE"
        confidence      = None
        violated_rule   = None
        reason          = None
        feedback        = None

        if faiss_decision == "BLOCK":
            decision        = "BLOCK"
            stage_triggered = "stage3_faiss"
            confidence      = faiss_score
            violated_rule   = "topic"
            category        = getattr(faiss_result, "category", "NONE") or "NONE"
            reason          = f"Blocked by FAISS: {faiss_result.topic}"
            feedback        = await FeedbackTemplateService.render(
                "topic", lang_ctx.code, {"topic": faiss_result.topic}, db, redis
            )

        elif llm_response:
            decision      = llm_response.decision
            category      = getattr(llm_response, "category", "NONE") or "NONE"
            confidence    = llm_response.confidence
            violated_rule = llm_response.violated_rule
            reason        = llm_response.reason
            feedback      = llm_response.feedback_message
            if decision == "BLOCK":
                stage_triggered = "llm"
                if faiss_decision == "HINT":
                    stage_triggered += "+faiss_hint"
                if classifier_uncertain:
                    stage_triggered += "+classifier_hint"
                if prefilter_result.keyword_hint:
                    stage_triggered += "+keyword_hint"

        # ── Classifier-only HINT fallback ─────────────────────────────────────
        # Handles the case where the classifier returned HINT with a real
        # violation category but needs_llm was False because there was no
        # FAISS hint and no keyword hint. Without this block those messages
        # silently become ALLOW — fixing Group 3 failures from the test suite.
        if (
            decision == "ALLOW"
            and classifier_result is not None
            and classifier_result["decision"] == "HINT"
            and classifier_result["category"] != "NONE"
            and not needs_llm
        ):
            combined_hint = classifier_result.get("hint")
            fallback_llm = await Stage2LLM.process(
                request.message,
                profile,
                lang_ctx,
                _llm_provider,
                db,
                redis,
                faiss_hint=None,
                keyword_hint=combined_hint
            )
            if fallback_llm:
                decision      = fallback_llm.decision
                category      = getattr(fallback_llm, "category", "NONE") or "NONE"
                confidence    = fallback_llm.confidence
                violated_rule = fallback_llm.violated_rule
                reason        = fallback_llm.reason
                feedback      = fallback_llm.feedback_message
                if decision == "BLOCK":
                    stage_triggered = "llm+classifier_hint"

        return ModerationResponse(
            decision=decision,
            category=category,
            detected_language=lang_ctx.code,
            stage_triggered=stage_triggered,
            confidence=confidence,
            violated_rule=violated_rule,
            reason=reason,
            feedback_message=feedback,
            latency_ms=LatencyResult(
                stage0_lang=latency_stage0,
                stage1=latency_stage1,
                stage2_llm=latency_stage2,
                stage3_faiss=latency_stage3,
                total=total_latency,
                llm_provider=(
                    getattr(_llm_provider, "name", "unknown")
                    if llm_response else None
                )
            ),
            metadata=request.metadata
        )