from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    LLM_PROVIDER: str = "groq"
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "mistralai/mistral-7b-instruct:free"

    DATABASE_URL: str
    REDIS_URL: str

    SECRET_KEY: str
    DEFAULT_RATE_LIMIT_PER_MIN: int = 60

    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"
    FAISS_INDEX_DIR: str = "./data/faiss_indices"

    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "pretty"

    SERVICE_HOST: str = "0.0.0.0"
    SERVICE_PORT: int = 8001
    CORS_ORIGINS: list[str] | str = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
