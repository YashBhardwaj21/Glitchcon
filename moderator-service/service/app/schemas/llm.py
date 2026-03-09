from typing import Optional
from pydantic import BaseModel, Field

class ModerationLLMResponse(BaseModel):
    decision: str = Field(..., description="'ALLOW' or 'BLOCK'")
    confidence: float = Field(..., description="0.0 to 1.0 confidence score")
    violated_rule: Optional[str] = Field(None, description="brief rule name or null if allowed")
    reason: Optional[str] = Field(None, description="one sentence in English explaining the decision")
    feedback_message: Optional[str] = Field(None, description="polite educational message in the detected language")
