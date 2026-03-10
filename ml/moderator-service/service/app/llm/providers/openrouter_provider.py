import json
import asyncio
import httpx
from typing import Any
from app.core.config import settings
from app.llm.base import BaseLLMProvider
from app.schemas.llm import ModerationLLMResponse
from app.llm.exceptions import LLMUnavailableError
from app.core.logging import logger

class OpenRouterProvider(BaseLLMProvider):
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = "https://openrouter.ai/api/v1"
        self.model = getattr(settings, "OPENROUTER_MODEL", "mistralai/mistral-7b-instruct:free")
        # Reuse a single httpx client if possible, but initializing here is fine for the stub
        
    async def moderate(self, prompt: str) -> ModerationLLMResponse:
        retries = 2
        backoff = 0.5
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/YashBhardwaj21/Glitchcon", # Your repo link
            "X-Title": "AI Moderation Microservice",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            # We don't enforce json object strictly via openrouter because model support varies
            # But we can prompt it to output valid JSON
            "response_format": {"type": "json_object"}, 
            "temperature": 0.1,
            "max_tokens": 350
        }
        
        for attempt in range(retries + 1):
            try:
                # Using httpx directly
                async with httpx.AsyncClient(timeout=4.0) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload
                    )
                    response.raise_for_status()
                    
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    
                    if not content:
                        raise ValueError("Empty response from OpenRouter")
                        
                    parsed_json = json.loads(content)
                    return ModerationLLMResponse(**parsed_json)
                    
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from OpenRouter (attempt {attempt+1}/{retries+1}): {e}")
                if attempt == retries:
                    raise LLMUnavailableError(f"OpenRouter returned invalid JSON after {retries} retries")
            except httpx.HTTPError as e:
                logger.error(f"OpenRouter HTTP error (attempt {attempt+1}/{retries+1}): {str(e)}")
                if attempt == retries:
                    raise LLMUnavailableError(f"OpenRouter API failed: {str(e)}")
            except Exception as e:
                logger.error(f"OpenRouter unexpected error (attempt {attempt+1}/{retries+1}): {str(e)}")
                if attempt == retries:
                    raise LLMUnavailableError(f"OpenRouter failed: {str(e)}")
                    
            await asyncio.sleep(backoff * (2 ** attempt))

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(
                    f"{self.base_url}/auth/key",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"OpenRouter health check failed: {e}")
            return False
