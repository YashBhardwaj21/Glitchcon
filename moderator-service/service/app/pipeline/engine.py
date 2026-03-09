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

# We will instantiate the provider lazily inside the engine to prevent
# startup crashes if environment variables are missing.
_llm_provider = None

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
                category=prefilter_result.category,
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

        # ── Stage 3 (FAISS) and Stage 2 (LLM) ─────────────────────────────────
        # These stages run sequentially because Stage 2 (LLM) REQUIRES the output
        # of Stage 3 (faiss_hint) to inform its prompt. 
        
        s3_start = time.perf_counter()
        
        # 1. Run FAISS (Semantic Search) first
        faiss_result = await FaissService.search(
            lang_ctx.normalised_text, 
            profile.profile_id, 
            profile.faiss_threshold, 
            db
        )
        latency_stage3 = int((time.perf_counter() - s3_start) * 1000)

        # 2. Extract FAISS hint if in the "SOFT" match threshold
        faiss_hint = None
        if faiss_result.decision == "HINT":
            faiss_hint = (faiss_result.topic, faiss_result.score)

        # 3. Run LLM Analysis (only if FAISS didn't HARD BLOCK)
        # If FAISS HARD BLOCKS, we can technically skip the LLM, but to keep the 
        # pipeline simple and match existing tests, we'll run it or short-circuit here.
        # For now, we run it sequentially as before but measure latency properly.
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
            category = faiss_result.category
            reason = f"Blocked by FAISS semantic override: {faiss_result.topic}"
            feedback = await FeedbackTemplateService.render(
                "topic", lang_ctx.code, {"topic": faiss_result.topic}, db, redis
            )
        else:
            # Use Stage 2 LLM decision (whether HINT was sent or not)
            if llm_response:
                decision = llm_response.decision
                category = llm_response.category
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
