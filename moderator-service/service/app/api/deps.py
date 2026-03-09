import time
import bcrypt
from fastapi import Security, HTTPException, status, Depends
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.db.session import get_db
from app.db.models import APIKey
from app.api.v1.health import get_redis

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_api_key(
    api_key: str = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
) -> APIKey:
    """
    Validates the API key, ensures it exists and is active, and applies rate limiting.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )
        
    try:
        # Key format is <id>.<secret>
        key_id_str, secret = api_key.split(".", 1)
        key_id = int(key_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key format",
        )
        
    # Lookup key by ID
    db_api_key = await db.get(APIKey, key_id)
    if not db_api_key or not db_api_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API Key",
        )
        
    # Verify the hash
    if not bcrypt.checkpw(api_key.encode('utf-8'), db_api_key.key_hash.encode('utf-8')):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
        
    # Check rate limit via Redis
    current_min = int(time.time() // 60)
    rate_limit_key = f"rate_limit:{db_api_key.id}:{current_min}"
    
    # Atomic increment and TTL set inside pipeline
    pipe = redis.pipeline()
    pipe.incr(rate_limit_key)
    pipe.expire(rate_limit_key, 60)
    results = await pipe.execute()
    
    current_count = results[0]
    
    if current_count > db_api_key.rate_limit_per_min:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for this API Key",
        )
        
    return db_api_key
