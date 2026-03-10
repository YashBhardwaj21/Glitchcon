import time
import asyncio
from typing import Optional
from difflib import SequenceMatcher

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.profile import RulesProfileResponse
from app.schemas.i18n import LanguageContext
from app.schemas.llm import ModerationLLMResponse
from app.llm.base import BaseLLMProvider
from app.llm.prompt_builder import PromptBuilder
from app.llm.exceptions import LLMUnavailableError
from app.cache.feedback_cache import FeedbackTemplateService
from app.core.logging import logger

class Stage2LLM:
    """
    Stage 2 — LLM Semantic Analysis (Multilingual)
    Only reached if Stage 1 passes. Uses LLM to evaluate complex context.
    Takes 200-800 ms depending on the provider.
    """
    
    @staticmethod
    async def process(
        message: str, 
        profile: RulesProfileResponse, 
        lang_ctx: LanguageContext,
        provider: BaseLLMProvider,
        db: AsyncSession,
        redis: Redis,
        faiss_hint: tuple[str, float] | None = None,
        keyword_hint: str | None = None,
    ) -> ModerationLLMResponse | None:
        start_time = time.perf_counter()
        
        try:
            # 1. Build multilingual prompt (with optional FAISS and keyword semantic hints)
            prompt = await PromptBuilder.build(message, profile, lang_ctx, db, redis, faiss_hint=faiss_hint, keyword_hint=keyword_hint)
            
            # 2. Call LLM with timeout (increased to handle retries)
            response: ModerationLLMResponse = await asyncio.wait_for(
                provider.moderate(prompt),
                timeout=15.0
            )
            
            # 3. Confidence Gating based on language
            threshold = profile.llm_confidence_threshold_en
            if lang_ctx.code in ["hi", "ta", "te", "kn", "ml", "hi-en"]:
                threshold = profile.llm_confidence_threshold_indic
                
            if response.confidence < threshold:
                logger.info(f"LLM confidence {response.confidence} below threshold {threshold} for lang {lang_ctx.code}")
                # If unsure, we ALLOW by default to avoid false positives
                response.decision = "ALLOW"
                
            # 4. Rule Validation — prevents hallucinated rules from blocking
            if response.decision == "BLOCK" and response.violated_rule:
                violated_lower = response.violated_rule.lower()
                all_rules = profile.global_rules + profile.group_rules
                
                valid = False
                for rule in all_rules:
                    rule_lower = rule.lower()
                    # Fuzzy match — ratio > 0.4 means meaningful overlap
                    if SequenceMatcher(None, violated_lower, rule_lower).ratio() > 0.4:
                        valid = True
                        break
                    
                    # Also check if any 4+ letter word from violated_rule appears in any actual rule
                    violated_words = [w for w in violated_lower.replace("/", " ").replace("-", " ").split() if len(w) >= 4]
                    if any(w in rule_lower for w in violated_words):
                        valid = True
                        break
                
                if not valid:
                    logger.warning(f"LLM hallucinated rule '{response.violated_rule}'. Overriding to ALLOW.")
                    response.decision = "ALLOW"
                    response.violated_rule = None

            return response
            
        except asyncio.TimeoutError:
            logger.error(f"LLM Provider timed out for message in {lang_ctx.code}")
            return await Stage2LLM._handle_fallback(lang_ctx, db, redis)
            
        except LLMUnavailableError as e:
            logger.error(f"LLM Provider unavailable: {e}")
            return await Stage2LLM._handle_fallback(lang_ctx, db, redis)
            
        except Exception as e:
            logger.error(f"Unexpected error in Stage 2 LLM: {e}")
            return await Stage2LLM._handle_fallback(lang_ctx, db, redis)

    @staticmethod
    async def _handle_fallback(lang_ctx: LanguageContext, db: AsyncSession, redis: Redis) -> ModerationLLMResponse:
        """
        Creates a fallback ALLOW response but renders an educational template if 
        the application wants to show a 'temporary issue' message, or just fail open.
        Here we fail open (ALLOW) but log the fallback.
        """
        feedback = await FeedbackTemplateService.render(
            rule_type="llm_fallback",
            lang_code=lang_ctx.code,
            context={},
            db=db,
            redis=redis
        )
        return ModerationLLMResponse(
            decision="ALLOW",
            confidence=0.0,
            violated_rule=None,
            reason="LLM Provider timeout/error. Felled back to ALLOW.",
            feedback_message=feedback
        )
