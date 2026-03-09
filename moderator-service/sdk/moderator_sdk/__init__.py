"""
moderator_sdk
=============
Python SDK for the AI Moderation Microservice.

Quick-start (async)::

    import asyncio
    from moderator_sdk import ModerationClient
    from moderator_sdk.models import ModerationRequest

    async def main():
        async with ModerationClient(
            base_url="http://localhost:8001",
            api_key="1.your_key_here",
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

Quick-start (sync)::

    from moderator_sdk import SyncModerationClient
    from moderator_sdk.models import ModerationRequest

    client = SyncModerationClient(base_url="http://localhost:8001", api_key="1.your_key")
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

__version__ = "0.1.0"
__all__ = ["ModerationClient", "SyncModerationClient"]

logger = logging.getLogger("moderator_sdk")


# ─── Status→Exception mapping ────────────────────────────────────────────────

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

    # Catch-all for unexpected 4xx
    raise NetworkError(
        f"Unexpected HTTP {response.status_code}: {detail}",
        response.status_code,
        request_id,
    )


# ─── Async Client ─────────────────────────────────────────────────────────────

class ModerationClient:
    """
    Async HTTP client for the AI Moderation Microservice.

    Usage via async context manager (recommended — ensures connection cleanup)::

        async with ModerationClient(base_url=..., api_key=...) as client:
            result = await client.moderate(req)

    Or manage the lifecycle manually::

        client = ModerationClient(...)
        await client.open()
        ...
        await client.close()

    Args:
        base_url:   Service base URL, e.g. ``"http://localhost:8001"``.
        api_key:    API key string in ``"<id>.<secret>"`` format.
        timeout:    Per-request timeout in seconds (default: 10.0).
        http2:      Enable HTTP/2 multiplexing (default: False).
    """

    _MODERATE_PATH = "/v1/moderate/"
    _HEALTH_PATH   = "/v1/health"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 10.0,
        http2: bool = False,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key  = api_key
        self._timeout  = timeout
        self._http2    = http2
        self._client: Optional[httpx.AsyncClient] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def open(self) -> None:
        """Initialise the underlying httpx.AsyncClient. Called automatically by __aenter__."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                http2=self._http2,
                headers={
                    "X-API-Key": self._api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": f"moderator-sdk/{__version__}",
                },
            )

    async def close(self) -> None:
        """Cleanly close the HTTP client and release connections."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "ModerationClient":
        await self.open()
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    # ── Internal helper ───────────────────────────────────────────────────────

    async def _post(self, path: str, payload: dict) -> dict:
        """
        Execute a POST request and return the parsed JSON body.
        Raises a typed SDK exception on any error.
        """
        if self._client is None:
            await self.open()

        try:
            response = await self._client.post(path, json=payload)
        except httpx.TimeoutException as exc:
            raise NetworkError(f"Request timed out: {exc}") from exc
        except httpx.ConnectError as exc:
            raise NetworkError(f"Cannot connect to moderation service at {self._base_url}: {exc}") from exc
        except httpx.RequestError as exc:
            raise NetworkError(f"HTTP request failed: {exc}") from exc

        try:
            body = response.json()
        except Exception:
            body = {}

        if not response.is_success:
            _raise_for_status(response, body)

        return body

    async def _get(self, path: str) -> dict:
        """Execute a GET and return parsed JSON."""
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

    # ── Public API ────────────────────────────────────────────────────────────

    async def moderate(self, request: ModerationRequest) -> ModerationResponse:
        """
        Submit a single message for moderation.

        Args:
            request: :class:`ModerationRequest` with message, profile_id, user_id.

        Returns:
            :class:`ModerationResponse` with decision, detected_language, latency, etc.

        Raises:
            :exc:`AuthenticationError`: Invalid or missing API key.
            :exc:`ProfileNotFoundError`: The requested profile_id does not exist.
            :exc:`RateLimitError`: API key rate limit exceeded.
            :exc:`ServiceUnavailableError`: Service is down or restarting.
            :exc:`NetworkError`: Connection failure or timeout.
            :exc:`ResponseParseError`: Unexpected response shape.
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
            raise ResponseParseError(f"Could not parse response: {exc}. Body: {body}") from exc

    async def batch_moderate(
        self,
        requests: List[ModerationRequest],
    ) -> BatchModerationResult:
        """
        Submit multiple messages for moderation concurrently.

        Failures on individual items are collected into ``BatchModerationResult.errors``
        rather than raising, so a single bad message does not abort the entire batch.

        Args:
            requests: List of :class:`ModerationRequest` objects.

        Returns:
            :class:`BatchModerationResult` with ``.results`` and ``.errors``.
        """
        async def _safe_moderate(req: ModerationRequest):
            try:
                return await self.moderate(req), None
            except Exception as exc:  # noqa: BLE001
                status_code = getattr(exc, "status_code", None)
                return None, ModerationError(
                    request=req,
                    error=str(exc),
                    status_code=status_code,
                )

        pairs = await asyncio.gather(*[_safe_moderate(r) for r in requests])

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
            :class:`HealthStatus` with db/redis/llm reachability flags.

        Raises:
            :exc:`ServiceUnavailableError`: If the service responds with 503.
            :exc:`NetworkError`: If the service is unreachable.
        """
        body = await self._get(self._HEALTH_PATH)
        try:
            return HealthStatus.model_validate(body)
        except Exception as exc:
            raise ResponseParseError(f"Could not parse health response: {exc}") from exc


# ─── Sync Wrapper ─────────────────────────────────────────────────────────────

class SyncModerationClient:
    """
    Synchronous wrapper around :class:`ModerationClient`.

    Intended for non-async frameworks (Django, Flask, Celery tasks).
    Creates its own event loop per call — do **not** use this inside an
    already-running async event loop.

    Args:
        base_url, api_key, timeout: Same semantics as :class:`ModerationClient`.

    Example::

        from moderator_sdk import SyncModerationClient
        from moderator_sdk.models import ModerationRequest

        client = SyncModerationClient(base_url="http://localhost:8001", api_key="1.abc")
        resp = client.moderate(ModerationRequest(message="hi", profile_id="wele_general", user_id="u1"))
        print(resp.decision)
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 10.0,
    ):
        self._async_client = ModerationClient(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
        )

    def _run(self, coro):
        """Run a coroutine, reusing a loop if one is already running via anyio/nest_asyncio."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Inside Celery concurrency with gevent/threads — use a new loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result()
            return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    def moderate(self, request: ModerationRequest) -> ModerationResponse:
        """Synchronous version of :meth:`ModerationClient.moderate`."""
        async def _call():
            async with self._async_client:
                return await self._async_client.moderate(request)
        return self._run(_call())

    def batch_moderate(self, requests: List[ModerationRequest]) -> BatchModerationResult:
        """Synchronous version of :meth:`ModerationClient.batch_moderate`."""
        async def _call():
            async with self._async_client:
                return await self._async_client.batch_moderate(requests)
        return self._run(_call())

    def health_check(self) -> HealthStatus:
        """Synchronous version of :meth:`ModerationClient.health_check`."""
        async def _call():
            async with self._async_client:
                return await self._async_client.health_check()
        return self._run(_call())
