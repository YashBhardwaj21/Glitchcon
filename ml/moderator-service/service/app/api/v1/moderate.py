import hashlib
from typing import List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.api.deps import get_db, get_redis, verify_api_key
from app.schemas.moderate import ModerationRequest, ModerationResponse
from app.cache.profile_cache import ProfileCacheService
from app.pipeline.engine import ModerationEngine
from app.db.models import APIKey, ModerationLog

router = APIRouter()

def hash_message(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()

@router.post("/", response_model=ModerationResponse)
async def moderate_message(
    request: ModerationRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    api_key: APIKey = Depends(verify_api_key)
):
    # 1. Load Profile
    profile = await ProfileCacheService.get_profile(request.profile_id, db, redis)
    if not profile:
        raise HTTPException(status_code=404, detail="Rules profile not found")
        
    # 2. Run Engine
    response = await ModerationEngine.moderate(request, profile, db, redis)
    
    # 3. Log Moderation
    log = ModerationLog(
        api_key_id=api_key.id,
        profile_id=request.profile_id,
        message_hash=hash_message(request.message),
        decision=response.decision,
        detected_language=response.detected_language,
        stage_triggered=response.stage_triggered,
        violated_rule=response.violated_rule,
        confidence=response.confidence,
        latency_stage0_ms=response.latency_ms.stage0_lang,
        latency_stage1_ms=response.latency_ms.stage1,
        latency_stage2_ms=response.latency_ms.stage2_llm,
        latency_stage3_ms=response.latency_ms.stage3_faiss,
        total_latency_ms=response.latency_ms.total,
        llm_provider=response.latency_ms.llm_provider
    )
    db.add(log)
    await db.commit()
    
    return response

@router.post("/batch", response_model=List[ModerationResponse])
async def batch_moderate(
    requests: List[ModerationRequest],
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    api_key: APIKey = Depends(verify_api_key)
):
    """
    Process multiple moderation requests in parallel using asyncio.gather.
    Logs each result individually.
    """
    # 1. Resolve profiles for all requests
    # Using a cache to avoid redundant lookups for the same profile_id in a batch
    profile_map = {}
    
    async def process_single(req: ModerationRequest) -> ModerationResponse:
        if req.profile_id not in profile_map:
            p = await ProfileCacheService.get_profile(req.profile_id, db, redis)
            if not p:
                # Return a dummy response with error for this specific item
                return ModerationResponse(
                    decision="ALLOW",
                    detected_language="unknown",
                    stage_triggered="error",
                    reason=f"Profile '{req.profile_id}' not found",
                    latency_ms={"total": 0}
                )
            profile_map[req.profile_id] = p
            
        profile = profile_map[req.profile_id]
        response = await ModerationEngine.moderate(req, profile, db, redis)
        
        # Log this specific request
        log = ModerationLog(
            api_key_id=api_key.id,
            profile_id=req.profile_id,
            message_hash=hash_message(req.message),
            decision=response.decision,
            detected_language=response.detected_language,
            stage_triggered=response.stage_triggered,
            violated_rule=response.violated_rule,
            confidence=response.confidence,
            latency_stage0_ms=response.latency_ms.stage0_lang,
            latency_stage1_ms=response.latency_ms.stage1,
            latency_stage2_ms=response.latency_ms.stage2_llm,
            latency_stage3_ms=response.latency_ms.stage3_faiss,
            total_latency_ms=response.latency_ms.total,
            llm_provider=response.latency_ms.llm_provider
        )
        db.add(log)
        return response

    # 2. Run all in parallel
    results = await asyncio.gather(*(process_single(r) for r in requests))
    
    # 3. Save all logs at once
    await db.commit()
    
    return results
