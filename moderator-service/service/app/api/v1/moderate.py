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
        llm_provider=None # Set in Phase 3
    )
    db.add(log)
    await db.commit()
    
    return response

@router.post("/batch")
async def batch_moderate(
    requests: List[ModerationRequest],
    api_key: APIKey = Depends(verify_api_key)
):
    # Stub for batch moderate
    # The actual processing would either use Celery or process in loop
    # For now, just returning a stub response indicating background task
    return {"message": "Batch moderation queued", "count": len(requests)}
