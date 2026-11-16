"""Application settings, loaded from environment variables (and `.env` in development)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-insecure-secret-change-me"  # noqa: S105 - placeholder, rejected in prod


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    app_name: str = "CareerPilot AI"
    log_level: str = "INFO"
    log_json: bool = True

    database_url: str = "postgresql+asyncpg://careerpilot:careerpilot@localhost:5432/careerpilot"
    valkey_url: str = "redis://localhost:6379/0"

    secret_key: SecretStr = SecretStr(_DEV_SECRET)

    session_cookie_name: str = "cp_session"
    csrf_cookie_name: str = "cp_csrf"
    csrf_header_name: str = "X-CSRF-Token"
    session_ttl_seconds: int = 7 * 24 * 3600
    cookie_secure: bool = False

    registration_open: bool = True
    password_min_length: int = 12

    login_max_attempts: int = 10
    login_window_seconds: int = 15 * 60

    cors_origins: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_production_safety(self) -> Settings:
        if self.env == "prod":
            if (
                self.secret_key.get_secret_value() == _DEV_SECRET
                or len(self.secret_key.get_secret_value()) < 32
            ):
                raise ValueError("SECRET_KEY must be set to a random value of at least 32 characters in prod")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in prod")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
