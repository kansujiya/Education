"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime config. Loaded from env or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""

    database_url: str = "postgresql://education:education@localhost:5432/education"
    redis_url: str = "redis://localhost:6379/0"

    default_model: str = "claude-opus-4-7"
    judgement_model: str = "claude-sonnet-4-6"
    high_volume_model: str = "claude-haiku-4-5-20251001"

    daily_token_budget: int = 20_000

    jwt_secret: str = "change-me"
    rate_limit_per_minute: int = 60

    langfuse_host: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "education-api"
    sentry_dsn: str = ""
    environment: str = "dev"


settings = Settings()
