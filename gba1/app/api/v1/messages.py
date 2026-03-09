"""
gba1/app/api/v1/messages.py
----------------------------
Messages API — accepts incoming messages and queues moderation via Celery.
The moderation task (P5.2) is a Celery worker that calls the SDK.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class IncomingMessage(BaseModel):
    """Payload from the frontend / bot."""
    group_id: str = Field(..., description="Channel/group identifier")
    user_id: str = Field(..., description="Sender user identifier")
    message: str = Field(..., min_length=1, max_length=4000, description="Message text")
    profile_id: str = Field(..., description="Moderation profile for this group")
    metadata: Optional[dict] = None


class MessageResponse(BaseModel):
    message_id: str
    status: str
    info: str


@router.post("/", response_model=MessageResponse, status_code=202)
async def submit_message(payload: IncomingMessage, background: BackgroundTasks):
    """
    Accept a message, queue it for moderation, return immediately (202 Accepted).

    The moderation decision is handled asynchronously by the Celery worker
    defined in app/tasks/moderation_task.py (implemented in P5.2).
    """
    import uuid
    message_id = str(uuid.uuid4())

    # Import here to avoid circular import at startup
    from app.tasks.moderation_task import moderate_message_task

    # Fire and forget — Celery task handles the moderation pipeline
    moderate_message_task.delay(
        message_id=message_id,
        message=payload.message,
        profile_id=payload.profile_id,
        user_id=payload.user_id,
        group_id=payload.group_id,
        metadata=payload.metadata or {},
    )

    return MessageResponse(
        message_id=message_id,
        status="queued",
        info="Message queued for moderation",
    )


@router.post("/sync", response_model=dict, summary="Synchronous moderation (testing only)")
async def moderate_sync(payload: IncomingMessage):
    """
    Direct synchronous moderation — bypasses Celery for testing/debugging.
    Not intended for production use (blocks the request thread).
    """
    from moderator_sdk import SyncModerationClient
    from moderator_sdk.models import ModerationRequest
    from moderator_sdk.exceptions import ModerationClientError
    from app.core.config import settings

    client = SyncModerationClient(
        base_url=settings.MODERATOR_BASE_URL,
        api_key=settings.MODERATOR_API_KEY,
        timeout=settings.MODERATOR_TIMEOUT,
    )
    try:
        response = client.moderate(
            ModerationRequest(
                message=payload.message,
                profile_id=payload.profile_id,
                user_id=payload.user_id,
                metadata=payload.metadata,
            )
        )
        return response.model_dump()
    except ModerationClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
