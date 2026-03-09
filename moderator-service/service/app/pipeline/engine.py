import time
import asyncio
from typing import Dict, Any
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.moderate import ModerationRequest, ModerationResponse, LatencyResult
from app.schemas.profile import RulesProfileResponse
from app.pipeline.stage0_language import Stage0Language
from app.pipeline.stage1_prefilter import Stage1Prefilter
from app.pipeline.stage2_llm import Stage2LLM
from app.pipeline.stage3_faiss import FaissService
from app.cache.feedback_cache import FeedbackTemplateService
from app.llm.factory import get_provider

_llm_provider = None

# ── Academic / Reporting Context Guard ───────────────────────────────────────
# These phrases indicate the message is discussing a topic analytically,
# not perpetuating it. Used to override FAISS false positives.
# Not a content blocklist — a CONTEXT detector.
_REPORTING_CONTEXT_PHRASES = [
    "is a serious issue",
    "we must discuss",
    "we should discuss",
    "research shows",
    "study found",
    "statistics show",
    "awareness about",
    "must talk about",
    "should address",
    "is a problem",
    "should I report",
    "how to report",
    "reporting this",
    "i want to report",
    "what is",
    "why does",
    "how does",
    "can someone explain",
]

def _is_reporting_context(text: str) -> bool:
    """
    Returns True if the message appears to be discussing/reporting a topic
    rather than perpetuating it. Prevents FAISS false positives on academic
    and news-style messages.
    """
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

        # Stage 0: Language Detection
        lang_ctx, latency_stage0 = Stage0Language.process(request.message)

        # Stage 1: Fast Pre-filter
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
                db=db,
                redis=redis
            )

            # stage1_prefilter.py now sets category explicitly on every blocked return.
            # The category_map here is a safety fallback only.
            category_map = {
                "pii":        "PII",
                "spam":       "SPAM",
                "profanity":  "PROFANITY",
                "hate_speech": "HATE_SPEECH",
                "threat":     "THREAT",
                "keyword":    "HATE_SPEECH",
            }
            stage1_category = (
                prefilter_result.category
                or category_map.get(prefilter_result.template_key, "NONE")
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

        # ── Stage 3 (FAISS) ───────────────────────────────────────────────────
        s3_start = time.perf_counter()

        faiss_result = await FaissService.search(
            lang_ctx.normalised_text,
            profile.profile_id,
            profile.faiss_threshold,
            db
        )
        latency_stage3 = int((time.perf_counter() - s3_start) * 1000)

        # Academic/reporting context guard:
        # If FAISS wants to hard block but the message is clearly discussing
        # a topic analytically (e.g. "Sexual harassment is a serious issue"),
        # downgrade the BLOCK to a HINT so LLM gets final say.
        # This prevents false positives without raising the global threshold.
        if faiss_result.decision == "BLOCK" and _is_reporting_context(request.message):
            faiss_result.decision = "HINT"
            faiss_result.score = faiss_result.score * 0.85  # dampen score for hint

        # Extract FAISS hint if in the soft threshold range
        faiss_hint = None
        if faiss_result.decision == "HINT":
            faiss_hint = (faiss_result.topic, faiss_result.score)

        # ── Stage 2 (LLM) — only if FAISS didn't hard block ──────────────────
        s2_start = time.perf_counter()

        llm_response = None
        if faiss_result.decision != "BLOCK":
            llm_response = await Stage2LLM.process(
                request.message,
                profile,
                lang_ctx,
                _llm_provider,
                db,
                redis,
                faiss_hint=faiss_hint,
                keyword_hint=prefilter_result.keyword_hint
            )

        latency_stage2 = int((time.perf_counter() - s2_start) * 1000)
        total_latency = int((time.perf_counter() - total_start) * 1000)

        # ── Decision Logic ────────────────────────────────────────────────────
        # FAISS BLOCK (hard)  → deterministic block, skip LLM
        # FAISS HINT (soft)   → LLM received the hint, its decision is final
        # FAISS ALLOW         → LLM decision used as-is
        # LLM unavailable     → fail open to ALLOW with category=NONE (safe default)

        stage_triggered = None
        decision = "ALLOW"
        category = "NONE"
        confidence = None
        violated_rule = None
        reason = None
        feedback = None

        if faiss_result.decision == "BLOCK":
            decision = "BLOCK"
            stage_triggered = "stage3_faiss"
            confidence = faiss_result.score
            violated_rule = "topic"
            category = getattr(faiss_result, "category", "NONE") or "NONE"
            reason = f"Blocked by FAISS semantic override: {faiss_result.topic}"
            feedback = await FeedbackTemplateService.render(
                "topic", lang_ctx.code, {"topic": faiss_result.topic}, db, redis
            )
        else:
            if llm_response:
                decision = llm_response.decision
                category = getattr(llm_response, "category", "NONE") or "NONE"
                confidence = llm_response.confidence
                violated_rule = llm_response.violated_rule
                reason = llm_response.reason
                feedback = llm_response.feedback_message
                if decision == "BLOCK":
                    stage_triggered = "llm"
                    if faiss_result.decision == "HINT":
                        stage_triggered += "+faiss_hint"
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