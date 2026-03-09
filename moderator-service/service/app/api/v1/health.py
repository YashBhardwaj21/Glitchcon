from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from redis.asyncio import Redis

from app.db.session import get_db
from app.core.config import settings

router = APIRouter()

async def get_redis():
    # Placeholder for actual Redis pool integration
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield redis
    finally:
        await redis.aclose()


@router.get("/health", summary="Health Check")
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    status_data = {
        "status": "ok",
        "llm_provider": settings.LLM_PROVIDER,
        "db_reachable": False,
        "redis_reachable": False,
        "llm_reachable": False,  # To be implemented in P3.7
    }
    
    # Check DB
    try:
        await db.execute(text("SELECT 1"))
        status_data["db_reachable"] = True
    except Exception:
        pass
        
    # Check Redis
    try:
        await redis.ping()
        status_data["redis_reachable"] = True
    except Exception:
        pass
        
    full_status_ok = status_data["db_reachable"] and status_data["redis_reachable"]
    
    if not full_status_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=status_data
        )
        
    return status_data
