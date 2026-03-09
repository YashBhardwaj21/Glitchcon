"""
moderator_sdk.models
--------------------
Pydantic models matching the AI Moderation Service API schemas.
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# ─── Request ──────────────────────────────────────────────────────────────────

class ModerationRequest(BaseModel):
    """Payload sent to POST /v1/moderate/"""
    message: str = Field(..., description="The text content to moderate", min_length=1)
    profile_id: str = Field(..., description="Rules profile identifier")
    user_id: str = Field(..., description="Originating user identifier for spam tracking")
    metadata: Optional[Dict[str, str]] = Field(
        default=None,
        description="Arbitrary key/value metadata passed through in the response"
    )


# ─── Response ─────────────────────────────────────────────────────────────────

class LatencyResult(BaseModel):
    """Per-stage latency breakdown in milliseconds."""
    stage0_lang: int = 0
    stage1: int = 0
    stage2_llm: int = 0
    stage3_faiss: int = 0
    total: int = 0


class ModerationResponse(BaseModel):
    """Full moderation result returned by the service."""
    decision: Literal["ALLOW", "BLOCK"]
    detected_language: str
    stage_triggered: Optional[str] = None
    confidence: Optional[float] = None
    violated_rule: Optional[str] = None
    reason: Optional[str] = None
    feedback_message: Optional[str] = None
    latency_ms: LatencyResult = Field(default_factory=LatencyResult)
    metadata: Optional[Dict[str, str]] = None


# ─── Batch ────────────────────────────────────────────────────────────────────

class ModerationError(BaseModel):
    """
    Represents a failed item in a batch request.
    Carries the original request alongside the error message so callers can
    re-queue individual failures without losing context.
    """
    request: ModerationRequest
    error: str
    status_code: Optional[int] = None


class BatchModerationResult(BaseModel):
    """Result container for batch_moderate(). Both lists may be non-empty."""
    results: List[ModerationResponse] = Field(default_factory=list)
    errors: List[ModerationError] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results) + len(self.errors)

    @property
    def success_count(self) -> int:
        return len(self.results)

    @property
    def error_count(self) -> int:
        return len(self.errors)


# ─── Health ───────────────────────────────────────────────────────────────────

class HealthStatus(BaseModel):
    """Response model for GET /v1/health"""
    status: str
    llm_provider: Optional[str] = None
    db_reachable: bool = False
    redis_reachable: bool = False
    llm_reachable: bool = False
