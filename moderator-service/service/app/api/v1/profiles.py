from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from redis.asyncio import Redis

from app.db.session import get_db
from app.db.models import RulesProfile, APIKey
from app.api.deps import verify_api_key
from app.api.v1.health import get_redis
from app.cache.profile_cache import ProfileCacheService
from app.schemas.profile import RulesProfileCreate, RulesProfileUpdate, RulesProfileResponse, KeywordAddRequest

router = APIRouter()

@router.post("/", response_model=RulesProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    profile_in: RulesProfileCreate,
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key),
    redis: Redis = Depends(get_redis)
):
    """
    Creates a new moderation rules profile.
    """
    stmt = select(RulesProfile).where(RulesProfile.profile_id == profile_in.profile_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Profile ID already exists",
        )
        
    db_profile = RulesProfile(**profile_in.model_dump())
    db.add(db_profile)
    await db.commit()
    await db.refresh(db_profile)
    
    # Sync keyword SETs to Redis
    await ProfileCacheService.sync_keywords_to_redis(db_profile, redis)
    
    return RulesProfileResponse.model_validate(db_profile)

@router.get("/{profile_id}", response_model=RulesProfileResponse)
async def get_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key),
    redis: Redis = Depends(get_redis)
):
    """
    Returns the full rules profile (from cache if possible).
    """
    profile = await ProfileCacheService.get_profile(profile_id, db, redis)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
        
    return profile

@router.patch("/{profile_id}", response_model=RulesProfileResponse)
async def update_profile(
    profile_id: str,
    profile_in: RulesProfileUpdate,
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key),
    redis: Redis = Depends(get_redis)
):
    """
    Updates an existing profile and invalidates its cache.
    """
    stmt = select(RulesProfile).where(RulesProfile.profile_id == profile_id)
    result = await db.execute(stmt)
    db_profile = result.scalar_one_or_none()
    
    if not db_profile:
        raise HTTPException(status_code=404, detail="Profile not found")
        
    update_data = profile_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_profile, field, value)
        
    await db.commit()
    await db.refresh(db_profile)
    
    # Invalidate cache & sync keywords
    await ProfileCacheService.invalidate(profile_id, redis)
    await ProfileCacheService.sync_keywords_to_redis(db_profile, redis)
    
    return RulesProfileResponse.model_validate(db_profile)

@router.post("/{profile_id}/keywords", response_model=RulesProfileResponse)
async def add_keyword(
    profile_id: str,
    keyword_in: KeywordAddRequest,
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key),
    redis: Redis = Depends(get_redis)
):
    """
    Adds a single keyword to a specific language list for a profile.
    """
    stmt = select(RulesProfile).where(RulesProfile.profile_id == profile_id)
    result = await db.execute(stmt)
    db_profile = result.scalar_one_or_none()
    
    if not db_profile:
        raise HTTPException(status_code=404, detail="Profile not found")
        
    # Python dictionaries returned by SQLAlchemy JSONB need a deep copy for modification updates
    keywords = dict(db_profile.keywords_by_language)
    if keyword_in.lang not in keywords:
        keywords[keyword_in.lang] = []
        
    if keyword_in.word not in keywords[keyword_in.lang]:
        keywords[keyword_in.lang].append(keyword_in.word)
        
    db_profile.keywords_by_language = keywords
    await db.commit()
    await db.refresh(db_profile)
    
    # Invalidate cache & sync keywords
    await ProfileCacheService.invalidate(profile_id, redis)
    await ProfileCacheService.sync_keywords_to_redis(db_profile, redis)
    
    return RulesProfileResponse.model_validate(db_profile)
