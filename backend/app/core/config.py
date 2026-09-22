import json
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "CodeSentinel AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "default-dev-secret-key-please-change-in-production-32chars"

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    CORS_ORIGINS: list[str] | str = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [item.strip() for item in v.split(",") if item.strip()]
        elif isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return []

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./quality_platform.db"
    DATABASE_ECHO: bool = False

    # Security, JWT & Envelope Encryption
    JWT_SECRET_KEY: str = "codesentinel-jwt-secret-key-production-ready-min-32chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ENCRYPTION_KEY: str = "k_B9u4H1pE6mXj7L8zY2qR5wT0aV3sD1fG8hJ9kL2m="

    # GitHub OAuth & GitHub App Integration
    GITHUB_CLIENT_ID: str | None = None
    GITHUB_CLIENT_SECRET: str | None = None
    GITHUB_OAUTH_REDIRECT_URI: str = "http://localhost:5173/auth/callback"
    GITHUB_APP_ID: str | None = None
    GITHUB_APP_PRIVATE_KEY: str | None = None
    GITHUB_APP_WEBHOOK_SECRET: str | None = None

    # Stripe Commercial Billing
    STRIPE_API_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    STRIPE_PRICE_ID_TEAM: str = "price_team_monthly"
    STRIPE_PRICE_ID_ENTERPRISE: str = "price_enterprise_monthly"

    # Redis / Celery Dual-Lane Queues
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CELERY_PR_QUEUE: str = "pr_lane"
    CELERY_BATCH_QUEUE: str = "batch_lane"

    # S3 / MinIO Object Storage
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None
    S3_BUCKET_NAME: str = "codesentinel-artifacts"
    S3_REGION: str = "us-east-1"
    STORAGE_LOCAL_FALLBACK_DIR: str = "./storage_artifacts"

    # Qdrant Vector Store
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_NAME: str = "code_symbols"

    # Ingestion Sandboxing & Resource Guards
    MAX_REPO_SIZE_MB: int = 250
    GIT_CLONE_TIMEOUT_SECONDS: int = 60
    TEMP_STORAGE_PATH: str = "./temp_repos"
    PR_MAX_INLINE_COMMENTS: int = 5

    # AI Engine
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.1


settings = Settings()