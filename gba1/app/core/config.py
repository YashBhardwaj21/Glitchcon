"""
gba1/app/core/config.py
-----------------------
Settings loaded from environment variables via pydantic-settings.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Moderation service ────────────────────────────────────────────────────
    MODERATOR_BASE_URL: str = Field(
        default="http://localhost:8001",
        description="Base URL of the AI Moderation Microservice",
    )
    MODERATOR_API_KEY: str = Field(
        description="API key for the moderation service (format: <id>.<secret>)"
    )
    MODERATOR_TIMEOUT: float = Field(
        default=12.0,
        description="Per-request timeout for moderation calls (seconds)",
    )
    MODERATOR_MAX_RETRIES: int = Field(
        default=3,
        description="Max retry attempts on network/5xx errors",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME: str = "GBA1 Consumer Service"
    SERVICE_HOST: str = "0.0.0.0"
    SERVICE_PORT: int = 8002
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://gba1:gba1_pass@localhost:5432/gba1_db"
    )

    # ── Redis / Celery ────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/3"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/4"

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]


settings = Settings()
