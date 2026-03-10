from typing import Optional
from pydantic import BaseModel, Field, validator
from app.schemas.moderate import ViolationCategory

class ModerationLLMResponse(BaseModel):
    decision: str = Field(..., description="'ALLOW' or 'BLOCK'")
    category: str = Field("NONE", description="The violation category")
    confidence: float = Field(..., description="0.0 to 1.0 confidence score")
    violated_rule: Optional[str] = Field(None, description="brief rule name or null if allowed")
    reason: Optional[str] = Field(None, description="one sentence in English explaining the decision")
    feedback_message: Optional[str] = Field(None, description="polite educational message in the detected language")

    @validator("category")
    def validate_category(cls, v):
        valid = {c.value for c in ViolationCategory}
        if v and v.upper() in valid:
            return v.upper()
        return "NONE"
