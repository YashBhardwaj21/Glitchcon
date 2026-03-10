import os
from app.core.config import settings
from app.llm.base import BaseLLMProvider
from app.core.logging import logger

def get_provider() -> BaseLLMProvider:
    provider_name = settings.LLM_PROVIDER.lower()
    
    if provider_name == "groq":
        from app.llm.providers.groq_provider import GroqProvider
        return GroqProvider()
    else:
        logger.warning(f"Provider '{provider_name}' is no longer supported or unknown. Defaulting to Groq.")
        from app.llm.providers.groq_provider import GroqProvider
        return GroqProvider()
