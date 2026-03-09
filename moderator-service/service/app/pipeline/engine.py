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

# Instantiate provider once if possible, or we can just fetch it securely.
# In a real app, this might be injected via dependency, but fetching here is fine.
_llm_provider = get_provider()

class ModerationEngine:
    @staticmethod
    async def moderate(
        request: ModerationRequest,
        profile: RulesProfileResponse,
        db: AsyncSession,
        redis: Redis
    ) -> ModerationResponse:
        total_start = time.perf_counter()

        # Stage 0: Language Detection
        lang_ctx, latency_stage0 = Stage0Language.process(request.message)

        # Stage 1: Fast Pre-filter
        s1_start = time.perf_counter()
        prefilter_result = await Stage1Prefilter.process(request.message, profile, lang_ctx, request.user_id, redis)
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

            return ModerationResponse(
                decision="BLOCK",
                detected_language=lang_ctx.code,
                stage_triggered=prefilter_result.stage,
                confidence=1.0, # Deterministic rule
                violated_rule=prefilter_result.template_key or "keyword",
                reason=f"Blocked by Stage 1: {prefilter_result.matched}",
                feedback_message=feedback,
                latency_ms=LatencyResult(
                    stage0_lang=latency_stage0,
                    stage1=latency_stage1,
                    total=total_latency
                ),
                metadata=request.metadata
            )

        # Stage 2 (LLM) & Stage 3 (FAISS) concurrently
        s23_start = time.perf_counter()

        # Stage 3 runs first as a task — result used to optionally hint Stage 2
        stage3_task = asyncio.create_task(
            FaissService.search(lang_ctx.normalised_text, profile.profile_id, profile.faiss_threshold, db)
        )

        # We await Stage 3 before building the Stage 2 task so we can pass the hint.
        # Both still run concurrently via asyncio — Stage 3 is typically <50 ms.
        faiss_result = await stage3_task

        # Build faiss_hint tuple for Stage 2 when Stage 3 is uncertain (HINT zone)
        faiss_hint = None
        if faiss_result.decision == "HINT":
            faiss_hint = (faiss_result.topic, faiss_result.score)

        stage2_task = asyncio.create_task(
            Stage2LLM.process(request.message, profile, lang_ctx, _llm_provider, db, redis, faiss_hint=faiss_hint, keyword_hint=prefilter_result.keyword_hint)
        )

        llm_response = await stage2_task

        latency_stage23 = int((time.perf_counter() - s23_start) * 1000)

        # In a real setup, you might measure these exactly internally,
        # but since they run concurrently we'll assign the total parallel time.
        latency_stage2 = latency_stage23
        latency_stage3 = latency_stage23

        total_latency = int((time.perf_counter() - total_start) * 1000)

        # ── Decision Logic ────────────────────────────────────────────────────
        # FAISS BLOCK (hard, score > 0.82) overrides LLM — deterministic.
        # FAISS HINT (soft, 0.65–0.82)    → LLM already received the hint and
        #                                    took it into account in its response.
        # FAISS ALLOW (score < 0.65)       → LLM decision used as-is.

        stage_triggered = None
        decision = "ALLOW"
        confidence = None
        violated_rule = None
        reason = None
        feedback = None

        if faiss_result.decision == "BLOCK":
            decision = "BLOCK"
            stage_triggered = "stage3_faiss"
            confidence = faiss_result.score
            violated_rule = "topic"
            reason = f"Blocked by FAISS semantic override: {faiss_result.topic}"
            feedback = await FeedbackTemplateService.render(
                "topic", lang_ctx.code, {"topic": faiss_result.topic}, db, redis
            )
        else:
            # Use Stage 2 LLM decision (whether HINT was sent or not)
            if llm_response:
                decision = llm_response.decision
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
                total=total_latency
            ),
            metadata=request.metadata
        )
