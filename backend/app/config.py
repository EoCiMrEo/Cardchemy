"""Validated application configuration.

Secrets are intentionally required instead of falling back to values that could
accidentally reach production. The environment file is resolved relative to
the backend directory, so startup does not depend on the caller's cwd.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import EmailStr, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
INSECURE_SECRET_VALUES = {
    "your-super-secret-key-change-in-production",
    "your-super-secret-key-change-in-production-please",
    "dev-secret-key-change-in-production",
    "replace-with-at-least-32-random-characters",
    "secret",
}


class Settings(BaseSettings):
    """Settings loaded from the process environment and ``backend/.env``."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_ignore_empty=True,
    )

    app_name: str = "Flashcard Generator"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False

    database_url: str

    secret_key: SecretStr = Field(min_length=32)
    algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "flashcard-generator-api"
    jwt_audience: str = "flashcard-generator-web"
    jwt_clock_skew_seconds: int = Field(default=30, ge=0, le=300)
    access_token_expire_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=30)
    refresh_session_expire_days: int = Field(default=30, ge=1, le=90)

    refresh_cookie_name: str = "flashcard_refresh"
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: Literal["lax", "strict"] = "lax"
    refresh_cookie_domain: str | None = None

    frontend_base_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    invitation_min_hours: int = Field(default=1, ge=1, le=24)
    invitation_max_hours: int = Field(default=720, ge=24, le=2160)
    password_reset_expire_minutes: int = Field(default=30, ge=5, le=120)
    email_verification_required: bool = False

    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: EmailStr | None = None
    smtp_starttls: bool = True

    gemini_api_key: SecretStr | None = None

    @property
    def secret_key_value(self) -> str:
        return self.secret_key.get_secret_value()

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        secret = self.secret_key_value
        if secret.lower() in INSECURE_SECRET_VALUES or len(set(secret)) < 8:
            raise ValueError("SECRET_KEY is known-insecure or lacks sufficient entropy")

        if self.invitation_min_hours > self.invitation_max_hours:
            raise ValueError("INVITATION_MIN_HOURS cannot exceed INVITATION_MAX_HOURS")

        if self.environment == "production":
            if self.debug:
                raise ValueError("DEBUG must be false in production")
            if not self.refresh_cookie_secure:
                raise ValueError("REFRESH_COOKIE_SECURE must be true in production")
            if not self.smtp_host or not self.smtp_from_email:
                raise ValueError("SMTP_HOST and SMTP_FROM_EMAIL are required in production")
            if any("localhost" in origin or "127.0.0.1" in origin for origin in self.cors_origin_list):
                raise ValueError("Production CORS_ORIGINS cannot contain localhost origins")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
