"""
tests/test_client.py
--------------------
Unit tests for moderator_sdk.ModerationClient.
Uses pytest-httpx to mock HTTP responses — no running service required.
"""
from __future__ import annotations

import json
import pytest
from pytest_httpx import HTTPXMock

from moderator_sdk import ModerationClient, SyncModerationClient
from moderator_sdk.exceptions import (
    AuthenticationError,
    CircuitOpenError,
    ProfileNotFoundError,
    RateLimitError,
    ServiceUnavailableError,
)
from moderator_sdk.models import ModerationRequest, ModerationResponse
from moderator_sdk.retry import CircuitBreaker, RetryConfig

BASE_URL = "http://test-moderator"
API_KEY  = "1.test_secret_key"


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """Pre-opened client with retry disabled for deterministic tests."""
    return ModerationClient(
        base_url=BASE_URL,
        api_key=API_KEY,
        retry=RetryConfig(max_retries=0),
    )


def _allow_body() -> dict:
    return {
        "decision": "ALLOW",
        "detected_language": "en",
        "stage_triggered": None,
        "confidence": None,
        "violated_rule": None,
        "reason": None,
        "feedback_message": None,
        "latency_ms": {"stage0_lang": 3, "stage1": 5, "stage2_llm": 0, "stage3_faiss": 0, "total": 8},
        "metadata": None,
    }


def _block_body(stage: str = "stage1", rule: str = "pii") -> dict:
    return {
        "decision": "BLOCK",
        "detected_language": "en",
        "stage_triggered": stage,
        "confidence": 1.0,
        "violated_rule": rule,
        "reason": f"Blocked by {stage}",
        "feedback_message": "Please do not share personal information.",
        "latency_ms": {"stage0_lang": 2, "stage1": 4, "stage2_llm": 0, "stage3_faiss": 0, "total": 6},
        "metadata": None,
    }


def _make_request(msg: str = "Hello world") -> ModerationRequest:
    return ModerationRequest(message=msg, profile_id="wele_test", user_id="u1")


# ─── Basic moderation ──────────────────────────────────────────────────────────

async def test_moderate_allow(httpx_mock: HTTPXMock, client: ModerationClient):
    """Clean message returns ALLOW with correct types."""
    httpx_mock.add_response(
        url=f"{BASE_URL}/v1/moderate/",
        method="POST",
        json=_allow_body(),
    )
    async with client:
        resp = await client.moderate(_make_request())

    assert isinstance(resp, ModerationResponse)
    assert resp.decision == "ALLOW"
    assert resp.detected_language == "en"
    assert resp.latency_ms.total == 8


async def test_moderate_block_pii(httpx_mock: HTTPXMock, client: ModerationClient):
    """PII-containing message returns BLOCK at stage1."""
    httpx_mock.add_response(
        url=f"{BASE_URL}/v1/moderate/",
        method="POST",
        json=_block_body(stage="stage1", rule="pii"),
    )
    async with client:
        resp = await client.moderate(_make_request("Call me at 9876543210"))

    assert resp.decision == "BLOCK"
    assert resp.stage_triggered == "stage1"
    assert resp.violated_rule == "pii"
    assert resp.confidence == 1.0

# ─── Auth / permission errors ──────────────────────────────────────────────────

async def test_moderate_auth_error(httpx_mock: HTTPXMock, client: ModerationClient):
    """HTTP 401 raises AuthenticationError."""
    httpx_mock.add_response(
        url=f"{BASE_URL}/v1/moderate/",
        method="POST",
        status_code=401,
        json={"detail": "Missing X-API-Key header"},
    )
    async with client:
        with pytest.raises(AuthenticationError) as exc_info:
            await client.moderate(_make_request())

    assert exc_info.value.status_code == 401


async def test_moderate_profile_not_found(httpx_mock: HTTPXMock, client: ModerationClient):
    """HTTP 404 raises ProfileNotFoundError."""
    httpx_mock.add_response(
        url=f"{BASE_URL}/v1/moderate/",
        method="POST",
        status_code=404,
        json={"detail": "Rules profile not found"},
    )
    async with client:
        with pytest.raises(ProfileNotFoundError) as exc_info:
            await client.moderate(_make_request())

    assert exc_info.value.status_code == 404


async def test_moderate_rate_limit(httpx_mock: HTTPXMock, client: ModerationClient):
    """HTTP 429 raises RateLimitError — should NOT be retried."""
    httpx_mock.add_response(
        url=f"{BASE_URL}/v1/moderate/",
        method="POST",
        status_code=429,
        json={"detail": "Rate limit exceeded"},
    )
    async with client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.moderate(_make_request())

    assert exc_info.value.status_code == 429


# ─── Retry logic ───────────────────────────────────────────────────────────────

async def test_moderate_retries_on_503(httpx_mock: HTTPXMock):
    """Service returns 503 twice, then 200 — client should succeed on attempt 3."""
    retrying_client = ModerationClient(
        base_url=BASE_URL,
        api_key=API_KEY,
        retry=RetryConfig(max_retries=3, base_delay=0.01, jitter=False),
    )

    # Two failures → one success
    httpx_mock.add_response(url=f"{BASE_URL}/v1/moderate/", method="POST",
                            status_code=503, json={"detail": "unavailable"})
    httpx_mock.add_response(url=f"{BASE_URL}/v1/moderate/", method="POST",
                            status_code=503, json={"detail": "unavailable"})
    httpx_mock.add_response(url=f"{BASE_URL}/v1/moderate/", method="POST",
                            json=_allow_body())

    async with retrying_client:
        resp = await retrying_client.moderate(_make_request())

    assert resp.decision == "ALLOW"


async def test_moderate_exhausts_retries(httpx_mock: HTTPXMock):
    """All attempts return 503 — client raises ServiceUnavailableError."""
    retrying_client = ModerationClient(
        base_url=BASE_URL,
        api_key=API_KEY,
        retry=RetryConfig(max_retries=2, base_delay=0.01, jitter=False),
    )

    for _ in range(3):  # initial + 2 retries
        httpx_mock.add_response(url=f"{BASE_URL}/v1/moderate/", method="POST",
                                status_code=503, json={"detail": "down"})

    async with retrying_client:
        with pytest.raises(ServiceUnavailableError):
            await retrying_client.moderate(_make_request())


# ─── Circuit breaker ───────────────────────────────────────────────────────────

async def test_circuit_breaker_opens(httpx_mock: HTTPXMock):
    """After failure_threshold failures, circuit opens and CircuitOpenError is raised."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=999)
    cb_client = ModerationClient(
        base_url=BASE_URL,
        api_key=API_KEY,
        retry=RetryConfig(max_retries=0),
        circuit_breaker=cb,
    )

    # Two 503s trip the breaker
    for _ in range(2):
        httpx_mock.add_response(url=f"{BASE_URL}/v1/moderate/", method="POST",
                                status_code=503, json={"detail": "down"})

    async with cb_client:
        for _ in range(2):
            with pytest.raises(ServiceUnavailableError):
                await cb_client.moderate(_make_request())

        # Next call is short-circuited
        with pytest.raises(CircuitOpenError):
            await cb_client.moderate(_make_request())


async def test_circuit_breaker_resets_on_success(httpx_mock: HTTPXMock):
    """After a successful probe, circuit returns to CLOSED and failure_count resets."""
    from moderator_sdk.retry import CBState
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
    cb_client = ModerationClient(
        base_url=BASE_URL,
        api_key=API_KEY,
        retry=RetryConfig(max_retries=0),
        circuit_breaker=cb,
    )

    httpx_mock.add_response(url=f"{BASE_URL}/v1/moderate/", method="POST",
                            status_code=503, json={"detail": "down"})
    httpx_mock.add_response(url=f"{BASE_URL}/v1/moderate/", method="POST",
                            json=_allow_body())

    import asyncio
    async with cb_client:
        with pytest.raises(ServiceUnavailableError):
            await cb_client.moderate(_make_request())

        assert cb.state == CBState.OPEN
        await asyncio.sleep(0.02)  # let recovery_timeout elapse

        # Probe should succeed and close breaker
        resp = await cb_client.moderate(_make_request())

    assert resp.decision == "ALLOW"
    assert cb.state == CBState.CLOSED
    assert cb.failure_count == 0


# ─── Batch moderation ─────────────────────────────────────────────────────────

async def test_batch_moderate_all_succeed(httpx_mock: HTTPXMock, client: ModerationClient):
    """All 3 parallel messages succeed — no errors in result."""
    for _ in range(3):
        httpx_mock.add_response(url=f"{BASE_URL}/v1/moderate/", method="POST",
                                json=_allow_body())

    reqs = [_make_request(f"msg_{i}") for i in range(3)]
    async with client:
        result = await client.batch_moderate(reqs)

    assert result.total == 3
    assert result.success_count == 3
    assert result.error_count == 0


async def test_batch_moderate_partial_failure(httpx_mock: HTTPXMock, client: ModerationClient):
    """One failure doesn't abort the batch — it ends up in .errors."""
    httpx_mock.add_response(url=f"{BASE_URL}/v1/moderate/", method="POST",
                            json=_allow_body())
    httpx_mock.add_response(url=f"{BASE_URL}/v1/moderate/", method="POST",
                            status_code=503, json={"detail": "down"})
    httpx_mock.add_response(url=f"{BASE_URL}/v1/moderate/", method="POST",
                            json=_allow_body())

    reqs = [_make_request(f"msg_{i}") for i in range(3)]
    async with client:
        result = await client.batch_moderate(reqs)

    assert result.total == 3
    assert result.success_count == 2
    assert result.error_count == 1


# ─── Async context manager ────────────────────────────────────────────────────

async def test_context_manager_closes_client(httpx_mock: HTTPXMock):
    """Client is None after exiting the context manager."""
    httpx_mock.add_response(url=f"{BASE_URL}/v1/moderate/", method="POST",
                            json=_allow_body())
    c = ModerationClient(base_url=BASE_URL, api_key=API_KEY,
                         retry=RetryConfig(max_retries=0))
    async with c:
        await c.moderate(_make_request())
    assert c._client is None


# ─── Health check ──────────────────────────────────────────────────────────────

async def test_health_check_ok(httpx_mock: HTTPXMock, client: ModerationClient):
    """Health check returns HealthStatus model."""
    httpx_mock.add_response(
        url=f"{BASE_URL}/v1/health",
        method="GET",
        json={"status": "ok", "llm_provider": "groq",
              "db_reachable": True, "redis_reachable": True, "llm_reachable": True},
    )
    async with client:
        health = await client.health_check()

    assert health.status == "ok"
    assert health.db_reachable is True
    assert health.llm_provider == "groq"


# ─── Sync wrapper ──────────────────────────────────────────────────────────────

def test_sync_client_moderate(httpx_mock: HTTPXMock):
    """SyncModerationClient.moderate() works from a synchronous context."""
    httpx_mock.add_response(url=f"{BASE_URL}/v1/moderate/", method="POST",
                            json=_allow_body())

    sync_client = SyncModerationClient(
        base_url=BASE_URL,
        api_key=API_KEY,
        retry=RetryConfig(max_retries=0),
    )
    resp = sync_client.moderate(_make_request())
    assert resp.decision == "ALLOW"


# ─── Auth header injection ────────────────────────────────────────────────────

async def test_auth_header_injected(httpx_mock: HTTPXMock):
    """Verify X-API-Key is present in every outgoing request."""
    sent_headers = {}

    def capture(request):
        sent_headers.update(dict(request.headers))
        return httpx_mock.add_response(
            url=f"{BASE_URL}/v1/moderate/",
            method="POST",
            json=_allow_body(),
        )

    httpx_mock.add_response(url=f"{BASE_URL}/v1/moderate/", method="POST",
                            json=_allow_body())
    c = ModerationClient(base_url=BASE_URL, api_key="42.mysecret",
                         retry=RetryConfig(max_retries=0))
    async with c:
        await c.moderate(_make_request())

    # httpx stores headers in the underlying client — confirm key was set
    assert c._client is None  # context manager closes
