"""
moderator_sdk
=============
Python SDK for the AI Moderation Microservice.

Quick-start (async)::

    import asyncio
    from moderator_sdk import ModerationClient
    from moderator_sdk.models import ModerationRequest
    from moderator_sdk.retry import RetryConfig, CircuitBreaker

    async def main():
        async with ModerationClient(
            base_url="http://localhost:8001",
            api_key="1.your_key_here",
            retry=RetryConfig(max_retries=3, base_delay=0.5),
            circuit_breaker=CircuitBreaker(failure_threshold=5, recovery_timeout=30),
        ) as client:
            resp = await client.moderate(
                ModerationRequest(
                    message="Hello everyone!",
                    profile_id="wele_general",
                    user_id="user_123",
                )
            )
            print(resp.decision, resp.detected_language)

    asyncio.run(main())

Quick-start (sync, e.g. from a Celery task)::

    from moderator_sdk import SyncModerationClient
    from moderator_sdk.models import ModerationRequest

    client = SyncModerationClient(base_url="http://localhost:8001", api_key="1.abc")
    resp = client.moderate(ModerationRequest(message="hi", profile_id="wele_general", user_id="u1"))
    print(resp.decision)
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

import httpx

from moderator_sdk.exceptions import (
    AuthenticationError,
    CircuitOpenError,
    ForbiddenError,
    InternalServiceError,
    NetworkError,
    ProfileNotFoundError,
    RateLimitError,
    ResponseParseError,
    ServiceUnavailableError,
    ValidationError,
)
from moderator_sdk.models import (
    BatchModerationResult,
    HealthStatus,
    ModerationError,
    ModerationRequest,
    ModerationResponse,
)
from moderator_sdk.retry import CircuitBreaker, RetryConfig, DEFAULT_RETRY

__version__ = "0.1.0"
__all__ = ["ModerationClient", "SyncModerationClient"]

logger = logging.getLogger("moderator_sdk")


# ─── Status → Exception mapping ───────────────────────────────────────────────

def _raise_for_status(response: httpx.Response, body: dict) -> None:
    """Convert a non-2xx response into a typed SDK exception."""
    detail = body.get("detail", response.text)
    request_id = response.headers.get("x-request-id")

    if response.status_code == 401:
        raise AuthenticationError(str(detail), 401, request_id)
    if response.status_code == 403:
        raise ForbiddenError(str(detail), 403, request_id)
    if response.status_code == 404:
        raise ProfileNotFoundError(str(detail), 404, request_id)
    if response.status_code == 422:
        raise ValidationError(str(detail), 422, request_id)
    if response.status_code == 429:
        raise RateLimitError(str(detail), 429, request_id)
    if response.status_code == 503:
        raise ServiceUnavailableError(str(detail), 503, request_id)
    if response.status_code >= 500:
        raise InternalServiceError(str(detail), response.status_code, request_id)

    raise NetworkError(
        f"Unexpected HTTP {response.status_code}: {detail}",
        response.status_code,
        request_id,
    )


# ─── Async Client ─────────────────────────────────────────────────────────────

class ModerationClient:
    """
    Async HTTP client for the AI Moderation Microservice.

    Supports exponential-backoff retry and a three-state circuit breaker
    out of the box.  Use as an async context manager for automatic connection
    cleanup::

        async with ModerationClient(base_url=..., api_key=...) as client:
            result = await client.moderate(req)

    Args:
        base_url:        Service base URL, e.g. ``"http://localhost:8001"``.
        api_key:         API key in ``"<id>.<secret>"`` format.
        timeout:         Per-request timeout in seconds (default: 10.0).
        retry:           :class:`~moderator_sdk.retry.RetryConfig` instance.
                         Defaults to 3 retries with 0.5 s base delay.
                         Pass ``RetryConfig(max_retries=0)`` to disable.
        circuit_breaker: Optional :class:`~moderator_sdk.retry.CircuitBreaker`.
                         If omitted, no circuit breaking is applied.
        http2:           Enable HTTP/2 multiplexing (default: False).
    """

    _MODERATE_PATH = "/v1/moderate/"
    _HEALTH_PATH   = "/v1/health"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 10.0,
        retry: RetryConfig = DEFAULT_RETRY,
        circuit_breaker: Optional[CircuitBreaker] = None,
        http2: bool = False,
    ):
        self._base_url        = base_url.rstrip("/")
        self._api_key         = api_key
        self._timeout         = timeout
        self._retry           = retry
        self._circuit_breaker = circuit_breaker
        self._http2           = http2
        self._client: Optional[httpx.AsyncClient] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def open(self) -> None:
        """Initialise the underlying httpx.AsyncClient."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                http2=self._http2,
                headers={
                    "X-API-Key":    self._api_key,
                    "Content-Type": "application/json",
                    "Accept":       "application/json",
                    "User-Agent":   f"moderator-sdk/{__version__}",
                },
            )

    async def close(self) -> None:
        """Close the HTTP client and release connections."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "ModerationClient":
        await self.open()
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _raw_post(self, path: str, payload: dict) -> dict:
        """Single POST attempt — no retry logic here."""
        if self._client is None:
            await self.open()

        try:
            response = await self._client.post(path, json=payload)
        except httpx.TimeoutException as exc:
            raise NetworkError(f"Request timed out: {exc}") from exc
        except httpx.ConnectError as exc:
            raise NetworkError(
                f"Cannot connect to moderation service at {self._base_url}: {exc}"
            ) from exc
        except httpx.RequestError as exc:
            raise NetworkError(f"HTTP request failed: {exc}") from exc

        try:
            body = response.json()
        except Exception:
            body = {}

        if not response.is_success:
            _raise_for_status(response, body)

        return body

    async def _raw_get(self, path: str) -> dict:
        """Single GET attempt — no retry logic here."""
        if self._client is None:
            await self.open()

        try:
            response = await self._client.get(path)
        except httpx.RequestError as exc:
            raise NetworkError(f"HTTP request failed: {exc}") from exc

        try:
            body = response.json()
        except Exception:
            body = {}

        if not response.is_success:
            _raise_for_status(response, body)

        return body

    async def _post(self, path: str, payload: dict) -> dict:
        """
        POST with retry logic and optional circuit breaker.

        Retries on retryable status codes and network errors as configured.
        Non-retryable errors (4xx except 429) are re-raised immediately.
        """
        retryable_exc = (NetworkError, ServiceUnavailableError, InternalServiceError)

        async def _attempt():
            last_exc: Exception | None = None
            for attempt in range(self._retry.max_retries + 1):
                try:
                    return await self._raw_post(path, payload)
                except RateLimitError:
                    raise  # Never retry 429 automatically — caller must back off
                except AuthenticationError:
                    raise  # Credentials won't fix themselves on retry
                except ForbiddenError:
                    raise
                except ProfileNotFoundError:
                    raise
                except ValidationError:
                    raise
                except retryable_exc as exc:
                    last_exc = exc
                    status = getattr(exc, "status_code", None)
                    if attempt >= self._retry.max_retries or \
                       not self._retry.should_retry(status):
                        raise
                    delay = self._retry.delay_for(attempt)
                    logger.warning(
                        "Retry %d/%d for %s in %.2fs — %s",
                        attempt + 1,
                        self._retry.max_retries,
                        path,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)

            raise last_exc  # Should never reach here

        if self._circuit_breaker is not None:
            return await self._circuit_breaker.call(_attempt)
        return await _attempt()

    async def _get(self, path: str) -> dict:
        """GET with circuit breaker passthrough (no retry — health checks are one-shot)."""
        if self._circuit_breaker is not None:
            return await self._circuit_breaker.call(self._raw_get, path)
        return await self._raw_get(path)

    # ── Public API ────────────────────────────────────────────────────────────

    async def moderate(self, request: ModerationRequest) -> ModerationResponse:
        """
        Submit a single message for moderation.

        Args:
            request: :class:`~moderator_sdk.models.ModerationRequest`.

        Returns:
            :class:`~moderator_sdk.models.ModerationResponse` with decision and
            per-stage latency breakdown.

        Raises:
            :exc:`~moderator_sdk.exceptions.AuthenticationError`: 401.
            :exc:`~moderator_sdk.exceptions.ProfileNotFoundError`: 404.
            :exc:`~moderator_sdk.exceptions.RateLimitError`: 429.
            :exc:`~moderator_sdk.exceptions.ServiceUnavailableError`: 503 / after retries.
            :exc:`~moderator_sdk.exceptions.NetworkError`: Connection/timeout.
            :exc:`~moderator_sdk.exceptions.CircuitOpenError`: Circuit breaker is OPEN.
            :exc:`~moderator_sdk.exceptions.ResponseParseError`: Unexpected response shape.
        """
        logger.debug(
            "moderate | profile=%s user=%s len=%d",
            request.profile_id,
            request.user_id,
            len(request.message),
        )

        body = await self._post(self._MODERATE_PATH, request.model_dump())

        try:
            return ModerationResponse.model_validate(body)
        except Exception as exc:
            raise ResponseParseError(
                f"Could not parse moderation response: {exc}. Body: {body}"
            ) from exc

    async def batch_moderate(
        self,
        requests: List[ModerationRequest],
    ) -> BatchModerationResult:
        """
        Submit multiple messages for moderation concurrently.

        Individual failures are collected in ``BatchModerationResult.errors``
        rather than aborting the entire batch.  The circuit breaker applies
        to each individual call.

        Args:
            requests: List of :class:`~moderator_sdk.models.ModerationRequest`.

        Returns:
            :class:`~moderator_sdk.models.BatchModerationResult`.
        """
        async def _safe(req: ModerationRequest):
            try:
                return await self.moderate(req), None
            except Exception as exc:  # noqa: BLE001
                return None, ModerationError(
                    request=req,
                    error=str(exc),
                    status_code=getattr(exc, "status_code", None),
                )

        pairs = await asyncio.gather(*[_safe(r) for r in requests])

        results, errors = [], []
        for ok, err in pairs:
            if ok is not None:
                results.append(ok)
            if err is not None:
                errors.append(err)

        logger.info(
            "batch_moderate | total=%d ok=%d errors=%d",
            len(requests),
            len(results),
            len(errors),
        )
        return BatchModerationResult(results=results, errors=errors)

    async def health_check(self) -> HealthStatus:
        """
        Call GET /v1/health on the moderation service.

        Returns:
            :class:`~moderator_sdk.models.HealthStatus`.

        Raises:
            :exc:`~moderator_sdk.exceptions.ServiceUnavailableError`: 503.
            :exc:`~moderator_sdk.exceptions.NetworkError`: Unreachable.
            :exc:`~moderator_sdk.exceptions.CircuitOpenError`: Circuit is OPEN.
        """
        body = await self._get(self._HEALTH_PATH)
        try:
            return HealthStatus.model_validate(body)
        except Exception as exc:
            raise ResponseParseError(
                f"Could not parse health response: {exc}"
            ) from exc


# ─── Sync Wrapper ─────────────────────────────────────────────────────────────

class SyncModerationClient:
    """
    Synchronous wrapper around :class:`ModerationClient`.

    For non-async callers such as Django views, Flask routes, or Celery tasks.
    Accepts the same retry and circuit-breaker parameters as the async client.

    .. warning::
        Do **not** call this from inside a running async event loop (e.g.
        from an async FastAPI endpoint) — use :class:`ModerationClient`
        directly instead.

    Example::

        client = SyncModerationClient(
            base_url="http://localhost:8001",
            api_key="1.abc",
            retry=RetryConfig(max_retries=2),
        )
        resp = client.moderate(ModerationRequest(...))
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 10.0,
        retry: RetryConfig = DEFAULT_RETRY,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self._async_client = ModerationClient(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            retry=retry,
            circuit_breaker=circuit_breaker,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _run(coro):
        """Run a coroutine safely regardless of whether a loop exists."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # e.g. Celery + gevent   → offload to a fresh thread with its own loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(asyncio.run, coro).result()
            return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    # ── Public API ────────────────────────────────────────────────────────────

    def moderate(self, request: ModerationRequest) -> ModerationResponse:
        """Synchronous :meth:`ModerationClient.moderate`."""
        async def _call():
            async with self._async_client:
                return await self._async_client.moderate(request)
        return self._run(_call())

    def batch_moderate(self, requests: List[ModerationRequest]) -> BatchModerationResult:
        """Synchronous :meth:`ModerationClient.batch_moderate`."""
        async def _call():
            async with self._async_client:
                return await self._async_client.batch_moderate(requests)
        return self._run(_call())

    def health_check(self) -> HealthStatus:
        """Synchronous :meth:`ModerationClient.health_check`."""
        async def _call():
            async with self._async_client:
                return await self._async_client.health_check()
        return self._run(_call())
