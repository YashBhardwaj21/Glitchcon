"""
gba1/app/tasks/moderation_task.py
----------------------------------
Celery task — moderate a single message via the AI Moderation SDK.

This task is invoked by POST /v1/messages/ and runs asynchronously in the
Celery worker. It calls the moderation service, logs the decision, and
(in a real deployment) would persist the decision to a DB or push a
webhook/event back to the frontend.

Decision handling:
    ALLOW  → message passes, downstream system can deliver it.
    BLOCK  → message rejected; feedback_message can be shown to the sender.
"""
from __future__ import annotations

import logging
from typing import Optional

from celery import Task

from app.tasks.celery_app import celery_app
from app.core.config import settings

from moderator_sdk import SyncModerationClient
from moderator_sdk.models import ModerationRequest, ModerationResponse
from moderator_sdk.exceptions import (
    AuthenticationError,
    ModerationClientError,
    ProfileNotFoundError,
    RateLimitError,
    CircuitOpenError,
)
from moderator_sdk.retry import RetryConfig, CircuitBreaker

logger = logging.getLogger("gba1.tasks.moderation")

# ─── Shared circuit breaker (module-level singleton) ──────────────────────────
# Shared across all task invocations in the same worker process.
# Trips after 5 consecutive failures; recovers after 60s.
_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60.0,
    name="moderator-service",
)


def _build_client() -> SyncModerationClient:
    """Create a SyncModerationClient with settings from env vars."""
    return SyncModerationClient(
        base_url=settings.MODERATOR_BASE_URL,
        api_key=settings.MODERATOR_API_KEY,
        timeout=settings.MODERATOR_TIMEOUT,
        retry=RetryConfig(
            max_retries=settings.MODERATOR_MAX_RETRIES,
            base_delay=1.0,
            max_delay=15.0,
            jitter=True,
        ),
        circuit_breaker=_circuit_breaker,
    )


@celery_app.task(
    name="gba1.tasks.moderate_message",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
)
def moderate_message_task(
    self: Task,
    *,
    message_id: str,
    message: str,
    profile_id: str,
    user_id: str,
    group_id: str,
    metadata: Optional[dict] = None,
) -> dict:
    """
    Moderate a single message using the AI Moderation Microservice SDK.

    Returns a dict with the moderation decision, persisting / forwarding it
    to downstream systems (webhook, DB write, etc.) is left for the
    application layer.

    Celery retry policy:
        - Network errors, 5xx → retried up to max_retries with exponential backoff.
        - Auth errors, 404    → not retried (configuration problem, alert needed).
        - Circuit open        → retried after recovery_timeout.
    """
    logger.info(
        "moderate_message_task START | id=%s profile=%s user=%s group=%s len=%d",
        message_id, profile_id, user_id, group_id, len(message),
    )

    client = _build_client()

    try:
        response: ModerationResponse = client.moderate(
            ModerationRequest(
                message=message,
                profile_id=profile_id,
                user_id=user_id,
                metadata=metadata,
            )
        )

    # ── Non-retryable auth/config errors ──────────────────────────────────────
    except AuthenticationError as exc:
        logger.error(
            "moderate_message_task AUTH_ERROR | id=%s — %s. "
            "Check MODERATOR_API_KEY env var. NOT retrying.",
            message_id, exc,
        )
        return _error_result(message_id, "AUTH_ERROR", str(exc), retried=False)

    except ProfileNotFoundError as exc:
        logger.error(
            "moderate_message_task PROFILE_NOT_FOUND | id=%s profile=%s — %s. "
            "Run the seed script. NOT retrying.",
            message_id, profile_id, exc,
        )
        return _error_result(message_id, "PROFILE_NOT_FOUND", str(exc), retried=False)

    # ── Rate limit — back off and Celery-retry ─────────────────────────────────
    except RateLimitError as exc:
        logger.warning(
            "moderate_message_task RATE_LIMITED | id=%s — retrying in 60s",
            message_id,
        )
        raise self.retry(exc=exc, countdown=60)

    # ── Circuit open — retry after recovery_timeout ────────────────────────────
    except CircuitOpenError as exc:
        logger.warning(
            "moderate_message_task CIRCUIT_OPEN | id=%s — retrying in %ds",
            message_id, int(_circuit_breaker.recovery_timeout),
        )
        raise self.retry(exc=exc, countdown=int(_circuit_breaker.recovery_timeout))

    # ── Network / 5xx — let Celery retry with default_retry_delay ─────────────
    except ModerationClientError as exc:
        logger.warning(
            "moderate_message_task NETWORK_ERROR | id=%s attempt=%d — %s",
            message_id, self.request.retries + 1, exc,
        )
        raise self.retry(exc=exc)

    # ── Success ───────────────────────────────────────────────────────────────
    decision = response.decision
    logger.info(
        "moderate_message_task DONE | id=%s decision=%s stage=%s confidence=%s lang=%s latency=%dms",
        message_id,
        decision,
        response.stage_triggered,
        f"{response.confidence:.2f}" if response.confidence is not None else "n/a",
        response.detected_language,
        response.latency_ms.total,
    )

    result = {
        "message_id":         message_id,
        "status":             "moderated",
        "decision":           decision,
        "detected_language":  response.detected_language,
        "stage_triggered":    response.stage_triggered,
        "confidence":         response.confidence,
        "violated_rule":      response.violated_rule,
        "reason":             response.reason,
        "feedback_message":   response.feedback_message,
        "latency_ms":         response.latency_ms.model_dump(),
    }

    # ── Post-decision hooks (extend here per product requirements) ────────────
    if decision == "BLOCK":
        _on_block(message_id, group_id, user_id, response)
    else:
        _on_allow(message_id, group_id, user_id)

    return result


# ─── Decision hooks ───────────────────────────────────────────────────────────

def _on_allow(message_id: str, group_id: str, user_id: str) -> None:
    """
    Called when message passes moderation.
    Extend to: push to frontend via WebSocket, mark DB record as delivered, etc.
    """
    logger.debug("ALLOW hook | id=%s group=%s user=%s", message_id, group_id, user_id)


def _on_block(
    message_id: str,
    group_id: str,
    user_id: str,
    response: ModerationResponse,
) -> None:
    """
    Called when message is blocked.
    Extend to: notify admin, increment user violation count, send feedback_message, etc.
    """
    logger.warning(
        "BLOCK hook | id=%s group=%s user=%s rule=%s feedback=%r",
        message_id, group_id, user_id,
        response.violated_rule,
        (response.feedback_message or "")[:80],
    )


# ─── Error result helper ──────────────────────────────────────────────────────

def _error_result(
    message_id: str,
    error_type: str,
    detail: str,
    retried: bool,
) -> dict:
    return {
        "message_id": message_id,
        "status":     "error",
        "error_type": error_type,
        "detail":     detail,
        "retried":    retried,
    }
