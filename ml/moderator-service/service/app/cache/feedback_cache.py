from jinja2 import Template
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import FeedbackTemplate
from app.schemas.feedback import FeedbackTemplateResponse
from app.core.logging import logger

class FeedbackTemplateService:
    TEMPLATE_TTL = 3600  # Cache templates for 1 hour

    @staticmethod
    def _generate_key(rule_type: str, language_code: str) -> str:
        return f"template:{rule_type}:{language_code}"

    @staticmethod
    async def get_template(
        rule_type: str, language_code: str, db: AsyncSession, redis: Redis
    ) -> FeedbackTemplateResponse | None:
        cache_key = FeedbackTemplateService._generate_key(rule_type, language_code)
        
        # 1. Try Redis cache
        try:
            cached_data = await redis.get(cache_key)
            if cached_data:
                return FeedbackTemplateResponse.model_validate_json(cached_data)
        except Exception as e:
            logger.warning(f"Redis error in get_template: {e}")

        # 2. Cache miss -> query DB
        stmt = select(FeedbackTemplate).where(
            FeedbackTemplate.rule_type == rule_type,
            FeedbackTemplate.language_code == language_code
        )
        result = await db.execute(stmt)
        template_obj = result.scalar_one_or_none()
        
        if not template_obj:
            # Fallback to default if available
            stmt_default = select(FeedbackTemplate).where(
                FeedbackTemplate.rule_type == rule_type,
                FeedbackTemplate.is_default == True
            )
            result_default = await db.execute(stmt_default)
            template_obj = result_default.scalar_one_or_none()

        if not template_obj:
            return None

        template_resp = FeedbackTemplateResponse.model_validate(template_obj)
        
        # 3. Store in cache
        try:
            await redis.set(
                cache_key,
                template_resp.model_dump_json(),
                ex=FeedbackTemplateService.TEMPLATE_TTL
            )
        except Exception as e:
            logger.warning(f"Failed to cache template in Redis: {e}")
            
        return template_resp

    @staticmethod
    async def render(
        rule_type: str, 
        lang_code: str, 
        context: dict, 
        db: AsyncSession, 
        redis: Redis
    ) -> str | None:
        """
        Fetches and renders a feedback template using Jinja2 strings.
        Example template: "Blocked due to {{ violation }}."
        """
        template_obj = await FeedbackTemplateService.get_template(rule_type, lang_code, db, redis)
        if not template_obj:
            return None
        
        try:
            t = Template(template_obj.template_text)
            return t.render(**context)
        except Exception as e:
            logger.error(f"Error rendering template {rule_type} for {lang_code}: {e}")
            return template_obj.template_text # Fallback to raw text

    @staticmethod
    async def invalidate(rule_type: str, language_code: str, redis: Redis):
        """Invalidates a template cache when updated."""
        cache_key = FeedbackTemplateService._generate_key(rule_type, language_code)
        await redis.delete(cache_key)
