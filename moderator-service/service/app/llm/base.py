from abc import ABC, abstractmethod
from app.schemas.llm import ModerationLLMResponse

class BaseLLMProvider(ABC):
    @abstractmethod
    async def moderate(self, prompt: str) -> ModerationLLMResponse:
        """Send moderation prompt, return structured decision."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify the provider is reachable and active."""
        pass
