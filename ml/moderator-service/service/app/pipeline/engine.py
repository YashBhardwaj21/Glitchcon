import time
import asyncio
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
# Prevents FAISS false positives on neutral/academic messages.
_REPORTING_CONTEXT_PHRASES = [
    "is a serious issue", "we must discuss", "we should discuss",
    "research shows", "study found", "statistics show",
    "awareness about", "must talk about", "should address",
    "is a problem", "should I report", "how to report",
    "reporting this", "i want to report",
    "what is", "why does", "how does",
    "can someone explain",
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
            # Fallback map — stage1_prefilter sets category explicitly,
            # this is a safety net only
            _category_fallback = {
                "pii": "PII", "spam": "SPAM", "profanity": "PROFANITY",
                "hate_speech": "HATE_SPEECH", "threat": "THREAT", "keyword": "HATE_SPEECH",
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

        # ── Stage 2A: Local Classifier ────────────────────────────────────────
        # Fast local model (~2ms). Handles ~70% of semantic violations.
        # LLM only called for messages where classifier is uncertain (0.50–0.80 conf).
        s2a_start = time.perf_counter()
        classifier_result = Stage2Classifier.predict(request.message)
        latency_stage2a = int((time.perf_counter() - s2a_start) * 1000)

        if classifier_result.decision == "BLOCK":
            # Classifier is confident — block immediately, skip FAISS and LLM
            total_latency = int((time.perf_counter() - total_start) * 1000)
            feedback = await FeedbackTemplateService.render(
                rule_type=classifier_result.category.lower(),
                lang_code=lang_ctx.code,
                context={},
                db=db, redis=redis
            )
            return ModerationResponse(
                decision="BLOCK",
                category=classifier_result.category,
                detected_language=lang_ctx.code,
                stage_triggered="stage2_classifier",
                confidence=classifier_result.confidence,
                violated_rule=classifier_result.category.lower(),
                reason=f"Blocked by local classifier: {classifier_result.category}",
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
        s3_start = time.perf_counter()
        faiss_result = await FaissService.search(
            lang_ctx.normalised_text,
            profile.profile_id,
            profile.faiss_threshold,
            db
        )
        latency_stage3 = int((time.perf_counter() - s3_start) * 1000)

        # Academic/reporting context guard — downgrade FAISS hard block to hint
        # to prevent false positives on neutral analytical messages
        faiss_decision = faiss_result.decision
        faiss_score = faiss_result.score
        if faiss_decision == "BLOCK" and _is_reporting_context(request.message):
            faiss_decision = "HINT"
            faiss_score = faiss_score * 0.85

        # Build FAISS hint for LLM if in soft threshold range
        faiss_hint = None
        if faiss_decision == "HINT":
            faiss_hint = (faiss_result.topic, faiss_score)

        # ── Stage 2B: LLM — only for ambiguous cases ──────────────────────────
        # Reaches here only if:
        #   - Classifier was uncertain (HINT or low-confidence ALLOW)
        #   - FAISS didn't hard block
        # This means LLM sees ~10-20% of total traffic, not 100%
        s2_start = time.perf_counter()
        llm_response = None

        # Determine if LLM is needed
        classifier_uncertain = classifier_result.decision == "HINT"
        faiss_hinting = faiss_decision == "HINT"
        keyword_hinting = bool(prefilter_result.keyword_hint)

        needs_llm = (
            faiss_decision != "BLOCK"
            and (classifier_uncertain or faiss_hinting or keyword_hinting)
        )

        if needs_llm:
            # Build combined hint from classifier + keyword
            combined_hint = prefilter_result.keyword_hint
            if classifier_result.hint and "classifier_unavailable" not in classifier_result.hint:
                combined_hint = (
                    f"{classifier_result.hint}. {combined_hint}"
                    if combined_hint
                    else classifier_result.hint
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
        total_latency = int((time.perf_counter() - total_start) * 1000)

        # ── Final Decision ────────────────────────────────────────────────────
        stage_triggered = None
        decision = "ALLOW"
        category = "NONE"
        confidence = None
        violated_rule = None
        reason = None
        feedback = None

        if faiss_decision == "BLOCK":
            decision = "BLOCK"
            stage_triggered = "stage3_faiss"
            confidence = faiss_score
            violated_rule = "topic"
            category = getattr(faiss_result, "category", "NONE") or "NONE"
            reason = f"Blocked by FAISS semantic override: {faiss_result.topic}"
            feedback = await FeedbackTemplateService.render(
                "topic", lang_ctx.code, {"topic": faiss_result.topic}, db, redis
            )
        elif llm_response:
            decision = llm_response.decision
            category = getattr(llm_response, "category", "NONE") or "NONE"
            confidence = llm_response.confidence
            violated_rule = llm_response.violated_rule
            reason = llm_response.reason
            feedback = llm_response.feedback_message
            if decision == "BLOCK":
                stage_triggered = "llm"
                if faiss_decision == "HINT":
                    stage_triggered += "+faiss_hint"
                if classifier_uncertain:
                    stage_triggered += "+classifier_hint"
                if prefilter_result.keyword_hint:
                    stage_triggered += "+keyword_hint"

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
                llm_provider=getattr(_llm_provider, "name", "unknown") if llm_response else None
            ),
            metadata=request.metadata
        )