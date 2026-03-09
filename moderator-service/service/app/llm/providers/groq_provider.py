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
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.model = "llama-3-8b-instant"
        
    async def moderate(self, prompt: str) -> ModerationLLMResponse:
        retries = 2
        backoff = 0.5
        
        for attempt in range(retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=350,
                    timeout=4.0
                )
                
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Empty response from Groq")
                    
                parsed_json = json.loads(content)
                return ModerationLLMResponse(**parsed_json)
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from Groq (attempt {attempt+1}/{retries+1}): {e}")
                if attempt == retries:
                    raise LLMUnavailableError(f"Groq returned invalid JSON after {retries} retries")
            except Exception as e:
                logger.error(f"Groq API error (attempt {attempt+1}/{retries+1}): {str(e)}")
                if attempt == retries:
                    raise LLMUnavailableError(f"Groq API failed: {str(e)}")
                    
            await asyncio.sleep(backoff * (2 ** attempt))

    async def health_check(self) -> bool:
        try:
            # Simple models list to verify connectivity and auth
            await self.client.models.list(timeout=2.0)
            return True
        except Exception as e:
            logger.error(f"Groq health check failed: {e}")
            return False
