import json
import asyncio
from typing import Any
from groq import AsyncGroq
from app.core.config import settings
from app.llm.base import BaseLLMProvider
from app.schemas.llm import ModerationLLMResponse
from app.llm.exceptions import LLMUnavailableError
from app.core.logging import logger

class GroqProvider(BaseLLMProvider):
    def __init__(self):
        self.client = AsyncGroq(
            api_key=settings.GROQ_API_KEY,
            timeout=12.0  # HTTP-level timeout
        )
        self.model = "llama-3.1-8b-instant"

    async def moderate(self, prompt: str) -> ModerationLLMResponse:
        for attempt in range(1, 4):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=300,
                )
                raw = response.choices[0].message.content
                if not raw:
                    raise ValueError("Empty response from Groq")
                return ModerationLLMResponse(**json.loads(raw))
            except Exception as e:
                logger.warning(f"Groq API error (attempt {attempt}/3): {e}")
                if attempt < 3:
                    await asyncio.sleep(attempt * 0.5)
        raise LLMUnavailableError(f"Groq API failed after 3 attempts")

    async def health_check(self) -> bool:
        try:
            # Simple models list to verify connectivity and auth
            await self.client.models.list(timeout=2.0)
            return True
        except Exception as e:
            logger.error(f"Groq health check failed: {e}")
            return False
