import json
from functools import lru_cache
from jinja2 import Template
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.schemas.profile import RulesProfileResponse
from app.schemas.i18n import LanguageContext
from app.db.models import PromptTemplate
from app.core.logging import logger

class PromptBuilder:
    # Small local cache for the fallback template
    _default_template_str: str | None = None
    
    @staticmethod
    def _get_lang_name(code: str) -> str:
        names = {
            "en": "English",
            "hi": "Hindi",
            "ta": "Tamil",
            "te": "Telugu",
            "kn": "Kannada",
            "ml": "Malayalam",
            "hi-en": "Hindi-English code-mix (Hinglish)"
        }
        return names.get(code, "English")

    @classmethod
    async def get_template_str(cls, profile_id: str, db: AsyncSession, redis: Redis) -> str:
        cache_key = f"prompt:{profile_id}"
        
        # 1. Try Redis
        cached = await redis.get(cache_key)
        if cached is not None:
            return cached
            
        # 2. Try DB for profile-specific
        stmt = select(PromptTemplate).where(
            PromptTemplate.profile_id == profile_id,
            PromptTemplate.is_active == True
        ).order_by(PromptTemplate.version.desc()).limit(1)
        result = await db.execute(stmt)
        template_obj = result.scalar_one_or_none()
        
        # 3. Try global default if profile doesn't have one
        if not template_obj:
            stmt = select(PromptTemplate).where(
                PromptTemplate.profile_id == None,
                PromptTemplate.is_active == True
            ).order_by(PromptTemplate.version.desc()).limit(1)
            result = await db.execute(stmt)
            template_obj = result.scalar_one_or_none()
            
        if not template_obj:
            # Fallback
            from app.core.logging import logger
            logger.warning("No prompt template found in DB, using hardcoded fallback")
            return cls._get_hardcoded_fallback()
            
        template_str = template_obj.template_text
        
        # Cache for 120s
        await redis.set(cache_key, template_str, ex=120)
        return template_str

    @classmethod
    async def build(
        cls,
        message: str,
        profile: RulesProfileResponse,
        lang_ctx: LanguageContext,
        db: AsyncSession,
        redis: Redis,
        faiss_hint: tuple[str, float] | None = None,
        keyword_hint: str | None = None,
    ) -> str:
        
        template_str = await cls.get_template_str(profile.profile_id, db, redis)
        template = Template(template_str)
        
        # Format rules
        global_rules = "\n".join(f"- {r}" for r in profile.global_rules)
        group_rules = "\n".join(f"- {r}" for r in profile.group_rules)
        
        # Handle long rule lists for prompt truncation
        # Rough token estimate: 1 word ~ 1.3 tokens
        estimated_words = len(global_rules.split()) + len(group_rules.split())
        if estimated_words > 1200:
            logger.warning(f"Rules list very long for {profile.profile_id}, LLM might struggle")
            # In a real system, you might truncate or summarize here
            
        # Optional context
        extra_instruction = ""
        if lang_ctx.code == "hi-en":
            extra_instruction = "\nThis is a code-mixed Hindi-English message. Evaluate the combined meaning."
        elif lang_ctx.is_transliterated:
            extra_instruction = f"\nNote: The user typed this message in Roman script, but it was detected as {cls._get_lang_name(lang_ctx.code)}."

        # Inject FAISS soft-block semantic hint when Stage 3 is uncertain
        # This prompts the LLM to pay attention to the flagged topic area
        if faiss_hint is not None:
            topic, score = faiss_hint
            extra_instruction += (
                f"\n\nNOTE: Semantic analysis suggests this message may relate to "
                f'"{topic}" (similarity score: {score:.2f}). '
                f"Pay extra attention to whether this topic is being discussed, "
                f"even if framed indirectly or in a cultural context."
            )

        # Inject Keyword soft-block hint
        if keyword_hint is not None:
            extra_instruction += (
                f"\n\nNOTE: {keyword_hint} "
                f"It may be context-dependent or a false positive. Evaluate its actual usage carefully."
            )

        prompt = template.render(
            detected_language=cls._get_lang_name(lang_ctx.code),
            group_topic=profile.group_topic,
            global_rules_formatted=global_rules,
            group_rules_formatted=group_rules,
            message=message,
            extra_instruction=extra_instruction
        )
        
        return prompt
        
    @classmethod
    def _get_hardcoded_fallback(cls) -> str:
        return """
You are a multilingual content moderation engine for a structured learning community.
You support English, Hindi, Tamil, Telugu, Kannada, Malayalam, and Hindi-English code-mix.

DETECTED LANGUAGE: {{ detected_language }}
GROUP CONTEXT: {{ group_topic }}

GLOBAL RULES (apply to all communities, all languages):
{{ global_rules_formatted }}

GROUP-SPECIFIC RULES:
{{ group_rules_formatted }}

MESSAGE TO EVALUATE: "{{ message }}"{{ extra_instruction }}

INSTRUCTIONS:
1. Evaluate the message considering its language and cultural context.
2. For code-mixed messages (Hinglish), evaluate the combined meaning.
3. The "feedback_message" field MUST be written in {{ detected_language }}.
   If detected_language is "Hindi", respond in Hindi.
   If detected_language is "Tamil", respond in Tamil. And so on.
   If detected_language is "English" or unknown, respond in English.
4. Be culturally sensitive — the same phrase may carry different weight in different languages.

Return ONLY a valid JSON object:
{
  "decision": "ALLOW" or "BLOCK",
  "confidence": 0.0 to 1.0,
  "violated_rule": "brief rule name or null",
  "reason": "one sentence in English explaining the decision",
  "feedback_message": "polite educational message in {{ detected_language }}"
}
"""
