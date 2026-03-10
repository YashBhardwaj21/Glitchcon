# moderator-sdk

> **Python SDK for the AI Moderation Microservice** — multilingual LLM-powered content safety.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

---

## Installation

```bash
pip install moderator-sdk
```

Or for local development (editable install from this repo):

```bash
pip install -e "moderator-service/sdk[dev]"
```

---

## Quick-start

### Async (recommended)

```python
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
        response = await client.moderate(
            ModerationRequest(
                message="Hello everyone, excited to be here!",
                profile_id="wele_general",
                user_id="user_abc123",
            )
        )
        print(f"Decision: {response.decision}")
        print(f"Language: {response.detected_language}")
        print(f"Total latency: {response.latency_ms.total}ms")

asyncio.run(main())
```

### Sync (Celery tasks, Django views, scripts)

```python
from moderator_sdk import SyncModerationClient
from moderator_sdk.models import ModerationRequest

client = SyncModerationClient(
    base_url="http://localhost:8001",
    api_key="1.your_key_here",
)
response = client.moderate(
    ModerationRequest(message="sup bro", profile_id="wele_general", user_id="u1")
)
print(response.decision)  # "ALLOW" or "BLOCK"
```

---

## API Reference

### `ModerationClient`

**Constructor**

| Param | Type | Default | Description |
|---|---|---|---|
| `base_url` | `str` | — | Service URL, e.g. `http://localhost:8001` |
| `api_key` | `str` | — | API key in `<id>.<secret>` format |
| `timeout` | `float` | `10.0` | Per-request timeout (seconds) |
| `retry` | `RetryConfig` | `RetryConfig()` | Retry policy (see below) |
| `circuit_breaker` | `CircuitBreaker \| None` | `None` | Optional circuit breaker |
| `http2` | `bool` | `False` | Enable HTTP/2 |

**Methods**

| Method | Returns | Description |
|---|---|---|
| `await moderate(request)` | `ModerationResponse` | Single message moderation |
| `await batch_moderate(requests)` | `BatchModerationResult` | Concurrent batch, collects individual failures |
| `await health_check()` | `HealthStatus` | Ping the service `/v1/health` |
| `await open()` / `await close()` | `None` | Manual lifecycle (use `async with` instead) |

### `SyncModerationClient`

Same parameters and methods as `ModerationClient`, but all methods are synchronous.
Safe to use in Celery workers and script contexts.

---

## Models

### `ModerationRequest`

```python
ModerationRequest(
    message="...",         # required — the text to moderate
    profile_id="...",      # required — which rules profile to apply
    user_id="...",         # required — for spam flood tracking
    metadata={"k": "v"},   # optional — passed through in response
)
```

### `ModerationResponse`

```python
response.decision           # "ALLOW" | "BLOCK"
response.detected_language  # "en" | "hi" | "ta" | "te" | "kn" | "ml" | "hi-en"
response.stage_triggered    # "stage1" | "llm" | "stage3_faiss" | None
response.confidence         # 0.0–1.0 | None
response.violated_rule      # brief rule name | None
response.reason             # one-line English explanation | None
response.feedback_message   # message in detected language to show the user | None
response.latency_ms         # LatencyResult with per-stage breakdown
```

---

## Retry Configuration

```python
from moderator_sdk.retry import RetryConfig

retry = RetryConfig(
    max_retries=3,              # total retry attempts after first failure
    base_delay=0.5,             # initial delay (seconds)
    max_delay=10.0,             # cap on computed delay
    jitter=True,                # add ±25% randomness to avoid thundering herd
    retryable_status=(429, 502, 503, 504),  # which HTTP codes to retry
)
```

**Backoff formula:** `min(base_delay × 2^attempt, max_delay) × jitter_factor`

**Non-retried errors:** 401, 403, 404, 422 — raised immediately, no retry.

---

## Circuit Breaker

```python
from moderator_sdk.retry import CircuitBreaker

cb = CircuitBreaker(
    failure_threshold=5,    # consecutive failures before tripping
    recovery_timeout=30.0,  # seconds in OPEN state before probing
    name="my-service",      # label for log messages
)
```

States: **CLOSED** (normal) → **OPEN** (tripped, short-circuits) → **HALF-OPEN** (probe) → **CLOSED** (recovered).

Share a single `CircuitBreaker` across multiple clients to protect a shared upstream.

---

## Error Handling

```python
from moderator_sdk.exceptions import (
    AuthenticationError,   # 401 — bad API key
    RateLimitError,        # 429 — key limit exceeded, wait 60s
    ProfileNotFoundError,  # 404 — profile_id doesn't exist
    ServiceUnavailableError,  # 503 / retries exhausted
    NetworkError,          # connection refused / timeout
    CircuitOpenError,      # circuit breaker is OPEN
)

try:
    resp = await client.moderate(req)
except RateLimitError:
    await asyncio.sleep(60)
except ProfileNotFoundError as e:
    print(f"Profile not found: {e.message}")
except CircuitOpenError:
    # Service is down — use cached result or fail gracefully
    resp = fallback_response()
```

All exceptions carry `.message`, `.status_code`, and `.request_id` attributes.

---

## Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run unit tests (no running service needed)
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=moderator_sdk --cov-report=term-missing
```
