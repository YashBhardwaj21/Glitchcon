import json
import asyncio
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from app.core.config import settings
from app.llm.base import BaseLLMProvider
from app.schemas.llm import ModerationLLMResponse
from app.llm.exceptions import LLMUnavailableError
from app.core.logging import logger

class GeminiProvider(BaseLLMProvider):
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.generation_config = GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1
        )
        
    async def moderate(self, prompt: str) -> ModerationLLMResponse:
        retries = 2
        backoff = 0.5
        
        for attempt in range(retries + 1):
            try:
                # generate_content_async is the async SDK method for gemini
                response = await self.model.generate_content_async(
                    prompt,
                    generation_config=self.generation_config
                )
                
                content = response.text
                if not content:
                    raise ValueError("Empty response from Gemini")
                    
                parsed_json = json.loads(content)
                return ModerationLLMResponse(**parsed_json)
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from Gemini (attempt {attempt+1}/{retries+1}): {e}")
                if attempt == retries:
                    raise LLMUnavailableError(f"Gemini returned invalid JSON after {retries} retries")
            except Exception as e:
                logger.error(f"Gemini API error (attempt {attempt+1}/{retries+1}): {str(e)}")
                if attempt == retries:
                    raise LLMUnavailableError(f"Gemini API failed: {str(e)}")
                    
            await asyncio.sleep(backoff * (2 ** attempt))

    async def health_check(self) -> bool:
        try:
            # We can request the model info to check connectivity
            model_info = genai.get_model("models/gemini-1.5-flash")
            return model_info is not None
        except Exception as e:
            logger.error(f"Gemini health check failed: {e}")
            return False
