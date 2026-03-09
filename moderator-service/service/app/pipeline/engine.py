import time
import asyncio
from typing import Dict, Any
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.moderate import ModerationRequest, ModerationResponse, LatencyResult
from app.schemas.profile import RulesProfileResponse
from app.pipeline.stage0_language import Stage0Language
from app.pipeline.stage1_prefilter import Stage1Prefilter
from app.pipeline.stage3_faiss import FaissService
from app.cache.feedback_cache import FeedbackTemplateService

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
            
        # Stage 2 (LLM Stub) & Stage 3 (FAISS) concurrently
        # Since Phase 2, Stage 2 is just a stub returning ALLOW, we'll only run Stage 3 really.
        
        s3_start = time.perf_counter()
        is_blocked, topic_label, faiss_score = await FaissService.search(
            text=lang_ctx.normalised_text,
            profile_id=profile.profile_id,
            threshold=profile.faiss_threshold,
            db=db
        )
        latency_stage3 = int((time.perf_counter() - s3_start) * 1000)
        
        if is_blocked:
            total_latency = int((time.perf_counter() - total_start) * 1000)
            
            feedback = await FeedbackTemplateService.render(
                rule_type="topic",
                lang_code=lang_ctx.code,
                context={"topic": topic_label},
                db=db,
                redis=redis
            )
            
            return ModerationResponse(
                decision="BLOCK",
                detected_language=lang_ctx.code,
                stage_triggered="stage3_faiss",
                confidence=faiss_score,
                violated_rule="topic",
                reason=f"Blocked by FAISS topic match: {topic_label}",
                feedback_message=feedback,
                latency_ms=LatencyResult(
                    stage0_lang=latency_stage0,
                    stage1=latency_stage1,
                    stage3_faiss=latency_stage3,
                    total=total_latency
                ),
                metadata=request.metadata
            )
            
        # If all pass, ALLOW
        total_latency = int((time.perf_counter() - total_start) * 1000)
        
        return ModerationResponse(
            decision="ALLOW",
            detected_language=lang_ctx.code,
            stage_triggered=None,
            confidence=None,
            violated_rule=None,
            reason=None,
            feedback_message=None,
            latency_ms=LatencyResult(
                stage0_lang=latency_stage0,
                stage1=latency_stage1,
                stage3_faiss=latency_stage3,
                total=total_latency
            ),
            metadata=request.metadata
        )
