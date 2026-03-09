from pydantic import BaseModel
from typing import Optional, Dict

class ModerationRequest(BaseModel):
    message: str
    profile_id: str
    user_id: str
    metadata: Optional[Dict[str, str]] = None

class LatencyResult(BaseModel):
    stage0_lang: int = 0
    stage1: int = 0
    stage2_llm: int = 0
    stage3_faiss: int = 0
    total: int = 0

class ModerationResponse(BaseModel):
    decision: str
    detected_language: str
    stage_triggered: Optional[str] = None
    confidence: Optional[float] = None
    violated_rule: Optional[str] = None
    reason: Optional[str] = None
    feedback_message: Optional[str] = None
    latency_ms: LatencyResult
    metadata: Optional[Dict[str, str]] = None
