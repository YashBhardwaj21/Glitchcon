from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import FeedbackTemplate
from app.schemas.feedback import FeedbackTemplateResponse

class FeedbackCacheService:
    TEMPLATE_TTL = 3600  # Cache templates for 1 hour

    @staticmethod
    def _generate_key(template_key: str, language: str) -> str:
        return f"template:{template_key}:{language}"

    @staticmethod
    async def get_template(
        template_key: str, language: str, db: AsyncSession, redis: Redis
    ) -> FeedbackTemplateResponse | None:
        cache_key = FeedbackCacheService._generate_key(template_key, language)
        
        # 1. Try Redis cache
        cached_data = await redis.get(cache_key)
        if cached_data:
            return FeedbackTemplateResponse.model_validate_json(cached_data)

        # 2. Cache miss -> query DB
        stmt = select(FeedbackTemplate).where(
            FeedbackTemplate.template_key == template_key,
            FeedbackTemplate.language == language
        )
        result = await db.execute(stmt)
        template_obj = result.scalar_one_or_none()
        
        if not template_obj:
            return None

        template_resp = FeedbackTemplateResponse.model_validate(template_obj)
        
        # 3. Store in cache
        await redis.set(
            cache_key,
            template_resp.model_dump_json(),
            ex=FeedbackCacheService.TEMPLATE_TTL
        )
        return template_resp

    @staticmethod
    async def invalidate(template_key: str, language: str, redis: Redis):
        """Invalidates a template cache when updated."""
        cache_key = FeedbackCacheService._generate_key(template_key, language)
        await redis.delete(cache_key)
