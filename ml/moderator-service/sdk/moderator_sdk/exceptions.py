"""
moderator_sdk.exceptions
-------------------------
Typed exception hierarchy for the Moderation SDK.

Usage::

    from moderator_sdk.exceptions import RateLimitError, AuthenticationError

    try:
        response = await client.moderate(req)
    except RateLimitError:
        await asyncio.sleep(60)
    except AuthenticationError:
        raise  # bubble up, nothing to retry
"""
from __future__ import annotations

from typing import Optional


class ModerationClientError(Exception):
    """
    Base for all SDK errors.
    Attributes:
        message:     Human-readable explanation.
        status_code: HTTP status code (None for network-level errors).
        request_id:  X-Request-ID header value if present.
    """
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        request_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.request_id = request_id

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"status_code={self.status_code}, "
            f"request_id={self.request_id!r})"
        )


# ─── 4xx ──────────────────────────────────────────────────────────────────────

class AuthenticationError(ModerationClientError):
    """Raised on HTTP 401 — missing or invalid X-API-Key."""


class ForbiddenError(ModerationClientError):
    """Raised on HTTP 403 — key exists but lacks permission for this profile."""


class ProfileNotFoundError(ModerationClientError):
    """Raised on HTTP 404 when the requested profile_id does not exist."""


class ValidationError(ModerationClientError):
    """Raised on HTTP 422 — request body failed schema validation."""


class RateLimitError(ModerationClientError):
    """
    Raised on HTTP 429 — API key rate limit exceeded.
    Wait at least 60 seconds before retrying.
    """


# ─── 5xx ──────────────────────────────────────────────────────────────────────

class ServiceUnavailableError(ModerationClientError):
    """Raised on HTTP 503 or when the service health check fails."""


class InternalServiceError(ModerationClientError):
    """Raised on HTTP 500 — unexpected server error."""


# ─── Transport / client-side ───────────────────────────────────────────────────

class NetworkError(ModerationClientError):
    """Raised when the HTTP request itself fails (connection refused, timeout, etc.)."""


class ResponseParseError(ModerationClientError):
    """Raised when the response body cannot be parsed into the expected model."""


# ─── Circuit breaker ──────────────────────────────────────────────────────────

class CircuitOpenError(ModerationClientError):
    """
    Raised when the circuit breaker is OPEN and requests are short-circuited.
    The client will automatically attempt recovery after the configured
    ``recovery_timeout`` seconds.
    """
