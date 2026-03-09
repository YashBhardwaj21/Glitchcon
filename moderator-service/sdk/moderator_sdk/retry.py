"""
moderator_sdk.retry
-------------------
Retry configuration and circuit breaker for the Moderation SDK.

Classes:
    RetryConfig     — dataclass controlling backoff behaviour.
    CircuitBreaker  — three-state (CLOSED/OPEN/HALF-OPEN) circuit breaker.

These are wired into :class:`~moderator_sdk.ModerationClient` automatically
when you pass them to the constructor.  You can also construct them standalone
and share a single :class:`CircuitBreaker` across multiple clients if several
workers talk to the same upstream service.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Tuple, Type

from moderator_sdk.exceptions import CircuitOpenError

logger = logging.getLogger("moderator_sdk.retry")


# ─── Retry Configuration ──────────────────────────────────────────────────────

@dataclass
class RetryConfig:
    """
    Controls how the client retries failed requests.

    Args:
        max_retries:      Maximum number of retry attempts (0 = no retries).
        base_delay:       Initial delay in seconds before the first retry.
        max_delay:        Cap on the computed delay (seconds).
        jitter:           Add randomness (±25 %) to avoid retry storms.
        retryable_status: HTTP status codes that should trigger a retry.
                          Defaults to 429, 502, 503, 504.

    Example — aggressive retry for a high-availability worker::

        RetryConfig(max_retries=5, base_delay=1.0, max_delay=30.0, jitter=True)

    Example — fail fast for interactive use::

        RetryConfig(max_retries=1, base_delay=0.2, max_delay=2.0)
    """
    max_retries: int = 3
    base_delay: float = 0.5
    max_delay: float = 10.0
    jitter: bool = True
    retryable_status: Tuple[int, ...] = (429, 500, 502, 503, 504)

    def delay_for(self, attempt: int) -> float:
        """
        Return the computed sleep duration for a given retry attempt (0-indexed).

        Uses exponential backoff: ``base_delay * 2^attempt``, capped at
        ``max_delay``, with optional ±25 % jitter to de-correlate parallel
        retriers.
        """
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        if self.jitter:
            delay *= (0.75 + random.random() * 0.5)   # ±25 %
        return delay

    def should_retry(self, status_code: int | None) -> bool:
        """Return True if the given HTTP status code warrants a retry."""
        if status_code is None:
            return True   # Network error — always retry
        return status_code in self.retryable_status


# ─── Default (shared, no-op) config ──────────────────────────────────────────

DEFAULT_RETRY = RetryConfig()
NO_RETRY      = RetryConfig(max_retries=0)


# ─── Circuit Breaker ──────────────────────────────────────────────────────────

class CBState(Enum):
    CLOSED    = "CLOSED"     # Normal operation — all requests pass through
    OPEN      = "OPEN"       # Tripped — requests are short-circuited immediately
    HALF_OPEN = "HALF_OPEN"  # Recovery probe — one request let through


class CircuitBreaker:
    """
    Three-state circuit breaker protecting the moderation service.

    State machine::

        CLOSED ──(failure_threshold reached)──► OPEN
          ▲                                        │
          │                             recovery_timeout elapsed
          │                                        │
          └──(probe succeeds)──── HALF_OPEN ◄──────┘
                                      │
                               (probe fails)
                                      │
                                    OPEN

    Args:
        failure_threshold: Consecutive failures needed to trip the breaker.
        recovery_timeout:  Seconds to wait in OPEN state before probing.
        name:              Human-readable label for log messages.

    Example::

        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30)
        client = ModerationClient(..., circuit_breaker=cb)
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        name: str = "moderation-service",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout  = recovery_timeout
        self.name              = name

        self._state:            CBState = CBState.CLOSED
        self._failure_count:    int     = 0
        self._last_failure_at:  float   = 0.0
        self._lock = asyncio.Lock()

    # ── Public accessors ──────────────────────────────────────────────────────

    @property
    def state(self) -> CBState:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    # ── Core gate ─────────────────────────────────────────────────────────────

    async def call(self, coro_fn: Callable, *args, **kwargs):
        """
        Execute *coro_fn(\\*args, \\*\\*kwargs)* through the circuit breaker.

        Raises:
            :exc:`~moderator_sdk.exceptions.CircuitOpenError`: Circuit is OPEN
                and the recovery timeout has not yet elapsed.
        """
        async with self._lock:
            if self._state == CBState.OPEN:
                elapsed = time.monotonic() - self._last_failure_at
                if elapsed >= self.recovery_timeout:
                    logger.info(
                        "CircuitBreaker[%s] → HALF_OPEN (elapsed %.1fs)",
                        self.name, elapsed,
                    )
                    self._state = CBState.HALF_OPEN
                else:
                    remaining = self.recovery_timeout - elapsed
                    raise CircuitOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Retry in {remaining:.1f}s."
                    )

        try:
            result = await coro_fn(*args, **kwargs)
            await self._on_success()
            return result
        except Exception:
            await self._on_failure()
            raise

    # ── State transitions ─────────────────────────────────────────────────────

    async def _on_success(self) -> None:
        async with self._lock:
            if self._state == CBState.HALF_OPEN:
                logger.info(
                    "CircuitBreaker[%s] → CLOSED (probe succeeded)", self.name
                )
            self._state         = CBState.CLOSED
            self._failure_count = 0

    async def _on_failure(self) -> None:
        async with self._lock:
            self._failure_count    += 1
            self._last_failure_at   = time.monotonic()

            if self._state == CBState.HALF_OPEN or \
               self._failure_count >= self.failure_threshold:
                logger.warning(
                    "CircuitBreaker[%s] → OPEN (failures=%d)",
                    self.name, self._failure_count,
                )
                self._state = CBState.OPEN

    # ── Manual controls ───────────────────────────────────────────────────────

    async def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED (useful in tests)."""
        async with self._lock:
            self._state         = CBState.CLOSED
            self._failure_count = 0
            self._last_failure_at = 0.0

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name={self.name!r}, state={self._state.value}, "
            f"failures={self._failure_count}/{self.failure_threshold})"
        )
