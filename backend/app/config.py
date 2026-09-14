"""Validated application configuration.

Secrets are intentionally required instead of falling back to values that could
accidentally reach production. The environment file is resolved relative to
the backend directory, so startup does not depend on the caller's cwd.
"""

import base64
import binascii
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
import re
from typing import Literal

from pydantic import AnyHttpUrl, EmailStr, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
INSECURE_SECRET_VALUES = {
    "your-super-secret-key-change-in-production",
    "your-super-secret-key-change-in-production-please",
    "dev-secret-key-change-in-production",
    "replace-with-at-least-32-random-characters",
    "secret",
}
UNSTABLE_MODEL_PATTERN = re.compile(r"(?:^|[-_.])(preview|latest|experimental|exp)(?:$|[-_.])", re.I)


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

    invitation_min_hours: int = Field(default=1, ge=1, le=720)
    invitation_max_hours: int = Field(default=720, ge=1, le=720)
    password_reset_expire_minutes: int = Field(default=30, ge=5, le=120)
    email_verification_required: bool = False

    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: EmailStr | None = None
    smtp_starttls: bool = True

    # Provider-independent AI settings. ``GEMINI_API_KEY`` remains as a
    # compatibility fallback while deployments migrate to ``AI_API_KEY``.
    ai_provider: Literal["gemini", "openai_compatible"] = "gemini"
    ai_model: str = Field(default="gemini-3.8-flash", min_length=1, max_length=128)
    ai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    ai_base_url: AnyHttpUrl | None = None
    ai_allow_unstable_model: bool = False
    ai_temperature: float = Field(default=0.2, ge=0, le=2)
    ai_max_output_tokens: int = Field(default=4_096, ge=64, le=131_072)
    ai_context_window_tokens: int = Field(default=1_048_576, ge=2_048, le=4_194_304)
    ai_provider_timeout_seconds: float = Field(default=90, ge=1, le=600)
    ai_provider_max_retries: int = Field(default=1, ge=0, le=5)
    ai_retry_base_seconds: float = Field(default=1, ge=0.1, le=60)
    ai_retry_max_seconds: float = Field(default=10, ge=0.1, le=600)
    ai_concurrency: int = Field(default=3, ge=1, le=32)
    ai_chunk_input_tokens: int = Field(default=1_200, ge=128, le=131_072)
    ai_chunk_overlap_tokens: int = Field(default=120, ge=0, le=32_768)
    ai_summary_output_tokens: int = Field(default=1_024, ge=64, le=32_768)
    ai_max_job_input_tokens: int = Field(default=200_000, ge=1_024, le=20_000_000)
    ai_max_job_output_tokens: int = Field(default=262_144, ge=64, le=5_000_000)
    ai_input_cost_per_million_usd: Decimal = Field(
        default=Decimal("0"), ge=Decimal("0"), le=Decimal("10000")
    )
    ai_output_cost_per_million_usd: Decimal = Field(
        default=Decimal("0"), ge=Decimal("0"), le=Decimal("10000")
    )
    ai_max_estimated_cost_usd: Decimal = Field(
        default=Decimal("5"), gt=Decimal("0"), le=Decimal("100000")
    )
    ai_refill_rounds: int = Field(default=2, ge=0, le=5)
    ai_duplicate_similarity_threshold: float = Field(default=0.88, ge=0.5, le=1)

    generation_source_encryption_key: SecretStr

    # PDF ingestion and durable generation-job limits. These defaults are
    # intentionally conservative for a small self-hosted deployment and can be
    # raised only after measuring worker memory, database growth, and AI cost.
    pdf_max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)
    pdf_max_pages: int = Field(default=100, ge=1, le=2_000)
    pdf_max_extracted_chars: int = Field(default=500_000, ge=1_000, le=10_000_000)
    pdf_extraction_timeout_seconds: int = Field(default=60, ge=5, le=600)
    pdf_extraction_memory_limit_mb: int = Field(default=512, ge=128, le=4_096)

    generation_min_card_count: int = Field(default=1, ge=1, le=100)
    generation_max_card_count: int = Field(default=100, ge=1, le=500)
    generation_max_active_jobs_per_user: int = Field(default=2, ge=1, le=100)
    generation_max_active_jobs_deployment: int = Field(default=20, ge=1, le=10_000)
    generation_max_queued_jobs_deployment: int = Field(default=100, ge=1, le=100_000)
    generation_daily_jobs_per_user: int = Field(default=10, ge=1, le=10_000)
    generation_daily_cards_per_user: int = Field(default=500, ge=1, le=1_000_000)
    generation_daily_upload_bytes_per_user: int = Field(
        default=100 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024 * 1024
    )
    generation_daily_jobs_deployment: int = Field(default=1_000, ge=1, le=1_000_000)
    generation_daily_cards_deployment: int = Field(default=50_000, ge=1, le=10_000_000)
    generation_daily_upload_bytes_deployment: int = Field(
        default=10 * 1024 * 1024 * 1024,
        ge=1024,
        le=10 * 1024 * 1024 * 1024 * 1024,
    )
    generation_max_retained_source_bytes_per_user: int = Field(
        default=50 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024 * 1024
    )
    generation_max_retained_source_bytes_deployment: int = Field(
        default=1024 * 1024 * 1024,
        ge=1024,
        le=10 * 1024 * 1024 * 1024 * 1024,
    )

    generation_worker_concurrency: int = Field(default=2, ge=1, le=64)
    generation_job_timeout_seconds: int = Field(default=600, ge=30, le=7_200)
    generation_lease_seconds: int = Field(default=60, ge=15, le=600)
    generation_worker_poll_seconds: float = Field(default=1.0, ge=0.1, le=30)
    generation_heartbeat_seconds: float = Field(default=10.0, ge=1, le=120)
    generation_max_attempts: int = Field(default=3, ge=1, le=10)
    generation_max_manual_retries: int = Field(default=2, ge=0, le=10)
    generation_retry_base_seconds: float = Field(default=2.0, ge=0.1, le=300)
    generation_retry_max_seconds: float = Field(default=60.0, ge=1, le=3_600)
    generation_source_retry_retention_hours: int = Field(default=24, ge=1, le=168)
    generation_upload_reservation_minutes: int = Field(default=15, ge=1, le=120)
    generation_cleanup_interval_seconds: int = Field(default=60, ge=5, le=3_600)

    # OCR is local, opt-in, and used only when normal PDF extraction produces
    # no text. The worker checks for the required executables at runtime.
    pdf_ocr_enabled: bool = False
    pdf_ocr_language: str = Field(default="eng", pattern=r"^[A-Za-z0-9_+.-]{1,64}$")
    pdf_ocr_dpi: int = Field(default=200, ge=72, le=400)
    pdf_ocr_page_timeout_seconds: int = Field(default=30, ge=5, le=300)

    @property
    def secret_key_value(self) -> str:
        return self.secret_key.get_secret_value()

    @property
    def ai_api_key_value(self) -> str | None:
        """Return the configured key without ever including it in model output."""

        configured = self.ai_api_key
        if configured is None and self.ai_provider == "gemini":
            configured = self.gemini_api_key
        if configured is None:
            return None
        value = configured.get_secret_value().strip()
        return value or None

    @property
    def ai_provider_configured(self) -> bool:
        if self.ai_provider == "gemini":
            return self.ai_api_key_value is not None
        return self.ai_base_url is not None

    @property
    def ai_pricing_configured(self) -> bool:
        return bool(
            self.ai_input_cost_per_million_usd > 0
            or self.ai_output_cost_per_million_usd > 0
        )

    @property
    def generation_source_encryption_key_bytes(self) -> bytes:
        encoded = self.generation_source_encryption_key.get_secret_value()
        try:
            key = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        except (ValueError, binascii.Error) as exc:
            raise ValueError(
                "GENERATION_SOURCE_ENCRYPTION_KEY must be URL-safe base64"
            ) from exc
        if len(key) != 32:
            raise ValueError(
                "GENERATION_SOURCE_ENCRYPTION_KEY must decode to exactly 32 bytes"
            )
        return key

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @field_validator("ai_model")
    @classmethod
    def validate_ai_model_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(ord(character) < 32 for character in normalized):
            raise ValueError("AI_MODEL must be a non-empty printable model identifier")
        return normalized

    @field_validator("ai_base_url")
    @classmethod
    def validate_ai_base_url(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is None:
            return None
        if value.username or value.password or value.query or value.fragment:
            raise ValueError("AI_BASE_URL cannot contain credentials, a query, or a fragment")
        return value

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        secret = self.secret_key_value
        if secret.lower() in INSECURE_SECRET_VALUES or len(set(secret)) < 8:
            raise ValueError("SECRET_KEY is known-insecure or lacks sufficient entropy")

        if self.invitation_min_hours > self.invitation_max_hours:
            raise ValueError("INVITATION_MIN_HOURS cannot exceed INVITATION_MAX_HOURS")

        if self.generation_min_card_count > self.generation_max_card_count:
            raise ValueError("GENERATION_MIN_CARD_COUNT cannot exceed GENERATION_MAX_CARD_COUNT")
        if self.generation_retry_base_seconds > self.generation_retry_max_seconds:
            raise ValueError(
                "GENERATION_RETRY_BASE_SECONDS cannot exceed GENERATION_RETRY_MAX_SECONDS"
            )
        if self.ai_retry_base_seconds > self.ai_retry_max_seconds:
            raise ValueError("AI_RETRY_BASE_SECONDS cannot exceed AI_RETRY_MAX_SECONDS")
        if self.ai_chunk_overlap_tokens >= self.ai_chunk_input_tokens:
            raise ValueError("AI_CHUNK_OVERLAP_TOKENS must be lower than AI_CHUNK_INPUT_TOKENS")
        if self.ai_summary_output_tokens > self.ai_max_output_tokens:
            raise ValueError("AI_SUMMARY_OUTPUT_TOKENS cannot exceed AI_MAX_OUTPUT_TOKENS")
        if self.ai_max_output_tokens >= self.ai_context_window_tokens:
            raise ValueError("AI_MAX_OUTPUT_TOKENS must be lower than AI_CONTEXT_WINDOW_TOKENS")
        if (
            self.ai_chunk_input_tokens
            + self.ai_summary_output_tokens
            + self.ai_max_output_tokens
            > self.ai_context_window_tokens
        ):
            raise ValueError(
                "AI chunk, summary, and output token budgets exceed AI_CONTEXT_WINDOW_TOKENS"
            )
        if self.ai_max_job_input_tokens < self.ai_chunk_input_tokens:
            raise ValueError("AI_MAX_JOB_INPUT_TOKENS cannot be lower than AI_CHUNK_INPUT_TOKENS")
        if self.ai_max_job_output_tokens < self.ai_max_output_tokens:
            raise ValueError("AI_MAX_JOB_OUTPUT_TOKENS cannot be lower than AI_MAX_OUTPUT_TOKENS")
        prices = (
            self.ai_input_cost_per_million_usd,
            self.ai_output_cost_per_million_usd,
        )
        if (prices[0] == 0) != (prices[1] == 0):
            raise ValueError("AI input and output prices must both be configured or both be zero")
        if self.ai_provider == "openai_compatible" and self.ai_base_url is None:
            raise ValueError("AI_BASE_URL is required for the openai_compatible provider")
        if self.ai_provider == "gemini" and self.ai_base_url is not None:
            raise ValueError("AI_BASE_URL is only valid for the openai_compatible provider")
        if self.generation_heartbeat_seconds >= self.generation_lease_seconds:
            raise ValueError("GENERATION_HEARTBEAT_SECONDS must be lower than GENERATION_LEASE_SECONDS")
        if self.generation_worker_concurrency > self.generation_max_active_jobs_deployment:
            raise ValueError(
                "GENERATION_WORKER_CONCURRENCY cannot exceed "
                "GENERATION_MAX_ACTIVE_JOBS_DEPLOYMENT"
            )
        self.generation_source_encryption_key_bytes

        if self.environment == "production":
            if not self.ai_allow_unstable_model and UNSTABLE_MODEL_PATTERN.search(self.ai_model):
                raise ValueError(
                    "Preview, latest, and experimental AI models require "
                    "AI_ALLOW_UNSTABLE_MODEL=true in production"
                )
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
