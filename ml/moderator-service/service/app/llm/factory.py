import os
from app.core.config import settings
from app.llm.base import BaseLLMProvider
from app.core.logging import logger

def get_provider() -> BaseLLMProvider:
    provider_name = settings.LLM_PROVIDER.lower()
    
    if provider_name == "groq":
        from app.llm.providers.groq_provider import GroqProvider
        return GroqProvider()
    elif provider_name == "gemini":
        from app.llm.providers.gemini_provider import GeminiProvider
        return GeminiProvider()
    elif provider_name == "openrouter":
        from app.llm.providers.openrouter_provider import OpenRouterProvider
        return OpenRouterProvider()
    else:
        logger.warning(f"Unknown LLM Provider '{provider_name}', falling back to Groq")
        from app.llm.providers.groq_provider import GroqProvider
        return GroqProvider()
