"""
gba1/app/main.py
----------------
GBA1 Consumer Service — FastAPI entrypoint.

On startup, validates connectivity to the AI Moderation Microservice.
If the service is unreachable the application refuses to start (fail-fast),
preventing the app from silently running without moderation coverage.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.api.v1 import messages, health as health_router

from moderator_sdk import ModerationClient
from moderator_sdk.exceptions import NetworkError, ServiceUnavailableError
from moderator_sdk.retry import RetryConfig

setup_logging("DEBUG" if settings.DEBUG else "INFO")


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("Starting GBA1 Consumer Service")
    logger.info("Connecting to Moderation Service at %s", settings.MODERATOR_BASE_URL)

    # Validate the moderation service is reachable before accepting traffic.
    # A single health-check attempt — no retry — intentional fail-fast.
    async with ModerationClient(
        base_url=settings.MODERATOR_BASE_URL,
        api_key=settings.MODERATOR_API_KEY,
        timeout=5.0,
        retry=RetryConfig(max_retries=0),
    ) as client:
        try:
            health = await client.health_check()
            logger.info(
                "Moderation service is healthy | db=%s redis=%s llm=%s provider=%s",
                health.db_reachable,
                health.redis_reachable,
                health.llm_reachable,
                health.llm_provider,
            )
        except (NetworkError, ServiceUnavailableError) as exc:
            logger.error(
                "FATAL: Cannot reach moderation service at %s — %s",
                settings.MODERATOR_BASE_URL,
                exc,
            )
            raise RuntimeError(
                f"Moderation service unreachable at startup: {exc}"
            ) from exc

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("GBA1 Consumer Service shutting down")


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="GBA1 Consumer Service",
    description="Consumer application integrating the AI Moderation Microservice",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# Routers
app.include_router(health_router.router, prefix="/v1", tags=["system"])
app.include_router(messages.router,      prefix="/v1/messages", tags=["messages"])
