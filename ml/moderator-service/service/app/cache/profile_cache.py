import json
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import RulesProfile
from app.schemas.profile import RulesProfileResponse

class ProfileCacheService:
    PROFILE_TTL = 60  # Cache profile logic for 60 seconds

    @staticmethod
    def _generate_key(profile_id: str) -> str:
        return f"profile:{profile_id}"

    @staticmethod
    async def get_profile(
        profile_id: str, db: AsyncSession, redis: Redis
    ) -> RulesProfileResponse | None:
        cache_key = ProfileCacheService._generate_key(profile_id)
        
        # 1. Try Redis cache
        cached_data = await redis.get(cache_key)
        if cached_data:
            return RulesProfileResponse.model_validate_json(cached_data)

        # 2. Cache miss -> query DB
        stmt = select(RulesProfile).where(RulesProfile.profile_id == profile_id)
        result = await db.execute(stmt)
        profile_obj = result.scalar_one_or_none()
        
        if not profile_obj:
            return None

        profile_resp = RulesProfileResponse.model_validate(profile_obj)
        
        # 3. Store in cache
        await redis.set(
            cache_key,
            profile_resp.model_dump_json(),
            ex=ProfileCacheService.PROFILE_TTL
        )
        return profile_resp

    @staticmethod
    async def invalidate(profile_id: str, redis: Redis):
        """Invalidates a profile cache when updated."""
        cache_key = ProfileCacheService._generate_key(profile_id)
        await redis.delete(cache_key)
        
    @staticmethod
    async def sync_keywords_to_redis(profile: RulesProfile, redis: Redis):
        """
        Synchronizes the keywords_by_language dict into fast Redis SETs.
        Creates SETs like: banned:wele_java_group:en
        """
        if not profile.keywords_by_language:
            return
            
        pipe = redis.pipeline()
        for lang, words in profile.keywords_by_language.items():
            set_key = f"banned:{profile.profile_id}:{lang}"
            # Clear existing set
            pipe.delete(set_key)
            # Add all new words
            if words:
                pipe.sadd(set_key, *[w.lower() for w in words])
                
        await pipe.execute()
