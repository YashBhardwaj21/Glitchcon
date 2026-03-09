from pydantic import BaseModel, Field
from typing import Optional, Dict
from enum import Enum

class ViolationCategory(str, Enum):
    HATE_SPEECH      = "HATE_SPEECH"
    PROFANITY        = "PROFANITY"
    THREAT           = "THREAT"
    SELF_HARM        = "SELF_HARM"
    PII              = "PII"
    SPAM             = "SPAM"
    SCAM             = "SCAM"
    SEXUAL           = "SEXUAL"
    CSAM             = "CSAM"
    OFF_TOPIC        = "OFF_TOPIC"
    MISINFORMATION   = "MISINFORMATION"
    NONE             = "NONE"

class ModerationRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="The text content to moderate")
    profile_id: str = Field(..., description="The rules profile to apply")
    user_id: str
    metadata: Optional[Dict[str, str]] = None

class LatencyResult(BaseModel):
    stage0_lang: int = 0
    stage1: int = 0
    stage2_llm: int = 0
    stage3_faiss: int = 0
    total: int = 0
    llm_provider: Optional[str] = None

class ModerationResponse(BaseModel):
    decision: str
    category: ViolationCategory = ViolationCategory.NONE  # default prevents crash when LLM unavailable
    detected_language: str
    stage_triggered: Optional[str] = None
    confidence: Optional[float] = None
    violated_rule: Optional[str] = None
    reason: Optional[str] = None
    feedback_message: Optional[str] = None
    latency_ms: LatencyResult
    metadata: Optional[Dict[str, str]] = None