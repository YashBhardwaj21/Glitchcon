"""
gba1/app/tasks/moderation_task.py
----------------------------------
Celery task — moderate a single message via the SDK.
Full implementation landing in P5.2. This stub ensures the import chain
works at startup (messages.py references this task).
"""
from __future__ import annotations

import logging
from app.tasks.celery_app import celery_app

logger = logging.getLogger("gba1.tasks.moderation")


@celery_app.task(
    name="gba1.tasks.moderate_message",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
)
def moderate_message_task(
    self,
    *,
    message_id: str,
    message: str,
    profile_id: str,
    user_id: str,
    group_id: str,
    metadata: dict,
) -> dict:
    """
    Stub — full SDK integration implemented in P5.2.
    Logs the received payload and returns a placeholder result.
    """
    logger.info(
        "moderate_message_task | id=%s profile=%s user=%s group=%s",
        message_id, profile_id, user_id, group_id,
    )
    # P5.2 will replace this stub with the actual SDK call:
    #   from moderator_sdk import SyncModerationClient
    #   client = SyncModerationClient(base_url=..., api_key=...)
    #   return client.moderate(...).model_dump()
    return {
        "message_id": message_id,
        "status": "stub",
        "detail": "SDK integration pending P5.2",
    }
