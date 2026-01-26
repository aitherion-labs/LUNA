from typing import List, Optional

from pydantic import Field

try:
    # Pydantic v2
    from pydantic_settings import BaseSettings, SettingsConfigDict
except Exception:  # pragma: no cover
    # Fallback to Pydantic v1 (deprecated path), keeps local dev working if v2 not available
    from pydantic import BaseSettings  # type: ignore

    SettingsConfigDict = dict  # type: ignore


class Settings(BaseSettings):
    """Centralized application settings loaded from environment variables.

    This module provides a minimal, reusable configuration layer for the app
    using Pydantic BaseSettings. It supports loading from a local .env file for
    development, while production should rely on environment variables provided
    by the runtime/orchestrator.
    """

    # Core
    model_id: Optional[str] = Field(default=None, alias="MODEL_ID")
    api_token: Optional[str] = Field(default=None, alias="API_TOKEN")
    s3_bucket_sessions: Optional[str] = Field(default=None, alias="S3_BUCKET_SESSIONS")

    # AWS
    aws_profile: Optional[str] = Field(default=None, alias="AWS_PROFILE")
    aws_region: Optional[str] = Field(default=None, alias="AWS_REGION")
    aws_retry_mode: Optional[str] = Field(default=None, alias="AWS_RETRY_MODE")
    aws_max_attempts: Optional[int] = Field(default=None, alias="AWS_MAX_ATTEMPTS")

    # Reliability/Performance
    agent_max_retries: int = Field(default=2, alias="AGENT_MAX_RETRIES")
    agent_retry_backoff_base_sec: float = Field(
        default=0.5, alias="AGENT_RETRY_BACKOFF_BASE_SEC"
    )
    agent_retry_backoff_max_sec: float = Field(
        default=5.0, alias="AGENT_RETRY_BACKOFF_MAX_SEC"
    )
    agent_call_timeout_sec: float = Field(default=45.0, alias="AGENT_CALL_TIMEOUT_SEC")

    # Server/HTTP
    cors_allow_origins: Optional[str] = Field(default=None, alias="CORS_ALLOW_ORIGINS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Pydantic v2 configuration
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "populate_by_name": True,
    }

    @staticmethod
    def parse_csv(value: Optional[str]) -> List[str]:
        if not value:
            return []
        return [x.strip() for x in value.split(",") if x.strip()]


# Export a singleton settings instance
settings = Settings()
# Normalize list fields if provided as raw CSV by some env providers
if isinstance(settings.cors_allow_origins, str):
    settings.cors_allow_origins = Settings.parse_csv(settings.cors_allow_origins)
