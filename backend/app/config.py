"""Validated application configuration.

Secrets are intentionally required instead of falling back to values that could
accidentally reach production. The environment file is resolved relative to
the repository root, so startup does not depend on the caller's cwd.
"""

import base64
import binascii
from dataclasses import dataclass, field
from decimal import Decimal
from functools import lru_cache
import ipaddress
import os
from pathlib import Path
import re
from typing import Literal
from urllib.parse import quote
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, EmailStr, Field, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import dotenv_values


BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
INSECURE_SECRET_VALUES = {
    "your-super-secret-key-change-in-production",
    "your-super-secret-key-change-in-production-please",
    "dev-secret-key-change-in-production",
    "replace-with-at-least-32-random-characters",
    "secret",
}
UNSTABLE_MODEL_PATTERN = re.compile(r"(?:^|[-_.])(preview|latest|experimental|exp)(?:$|[-_.])", re.I)
DNS_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
API_ROOT_PATH_PATTERN = re.compile(r"^/[A-Za-z0-9._~-]+(?:/[A-Za-z0-9._~-]+)*$")
FORBIDDEN_CORS_ORIGINS = {"*", "null"}
REMOVED_AI_NAMES = frozenset({
    "AI_PROVIDER_ENABLED", "AI_PROVIDER", "AI_MODEL", "AI_API_KEY", "AI_BASE_URL",
    "AI_ALLOW_UNSTABLE_MODEL", "AI_PROVIDER_MAX_RETRIES", "AI_RETRY_BASE_SECONDS",
    "AI_RETRY_MAX_SECONDS", "AI_MAX_OUTPUT_TOKENS", "AI_TEMPERATURE",
    "AI_CONTEXT_WINDOW_TOKENS", "AI_PROVIDER_TIMEOUT_SECONDS", "AI_CONCURRENCY",
    "AI_REQUESTS_PER_MINUTE", "AI_INPUT_TOKENS_PER_MINUTE",
    "AI_RATE_LIMIT_SAFETY_PERCENT", "AI_REQUEST_INPUT_TARGET_TOKENS",
    "AI_CARDS_PER_REQUEST", "AI_CHUNK_INPUT_TOKENS", "AI_CHUNK_OVERLAP_TOKENS",
    "AI_SUMMARY_OUTPUT_TOKENS", "AI_MAX_JOB_INPUT_TOKENS", "AI_MAX_JOB_OUTPUT_TOKENS",
    "AI_REFILL_ROUNDS", "AI_DUPLICATE_SIMILARITY_THRESHOLD",
    "AI_INPUT_COST_PER_MILLION_USD", "AI_OUTPUT_COST_PER_MILLION_USD",
    "AI_MAX_ESTIMATED_COST_USD", "GEMINI_API_KEY",
})


def _removed_ai_names(*, env_file: object, init_values: dict[str, object]) -> tuple[str, ...]:
    """Inspect supported sources without retaining or displaying their values."""

    found = {
        str(key).upper() for key, value in init_values.items()
        if str(key).upper() in REMOVED_AI_NAMES and value is not None and str(value).strip()
    }
    found.update(
        key.upper() for key, value in os.environ.items()
        if key.upper() in REMOVED_AI_NAMES and value.strip()
    )
    if env_file is not None:
        paths = env_file if isinstance(env_file, (tuple, list)) else (env_file,)
        for path in paths:
            if not Path(path).is_file():
                continue
            # dotenv_values follows the same file format used by BaseSettings.
            # Only key presence is retained; parser diagnostics/values never
            # enter the fixed migration error.
            try:
                parsed = dotenv_values(path, encoding="utf-8", interpolate=False)
            except Exception:
                # Let the normal settings loader report malformed file access.
                continue
            found.update(
                key.upper() for key, value in parsed.items()
                if key.upper() in REMOVED_AI_NAMES and value is not None and value.strip()
            )
    return tuple(sorted(found))


def normalize_http_origin(origin: str) -> str:
    """Validate and normalize one exact HTTP(S) origin."""

    if not origin or origin.casefold() in FORBIDDEN_CORS_ORIGINS:
        raise ValueError("CORS_ORIGINS cannot contain wildcard or null origins")
    if any(character.isspace() or ord(character) < 32 for character in origin):
        raise ValueError("CORS_ORIGINS entries cannot contain whitespace or controls")

    parsed = urlsplit(origin)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("CORS_ORIGINS entries must be absolute HTTP(S) origins")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("CORS_ORIGINS entries cannot contain credentials")
    if parsed.path or parsed.query or parsed.fragment:
        raise ValueError("CORS_ORIGINS entries cannot contain a path, query, or fragment")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("CORS_ORIGINS entries must include a hostname")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("CORS_ORIGINS entries must use a valid port") from exc

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            normalized_host = hostname.rstrip(".").encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise ValueError("CORS_ORIGINS entries must use a valid hostname") from exc
        if not normalized_host or len(normalized_host) > 253 or any(
            not DNS_LABEL_PATTERN.fullmatch(label) for label in normalized_host.split(".")
        ):
            raise ValueError("CORS_ORIGINS entries must use a valid hostname")
    else:
        normalized_host = f"[{address}]" if address.version == 6 else str(address)

    scheme = parsed.scheme.casefold()
    default_port = 80 if scheme == "http" else 443
    port_suffix = "" if port is None or port == default_port else f":{port}"
    return f"{scheme}://{normalized_host}{port_suffix}"


@dataclass(frozen=True, slots=True)
class TextProviderProfile:
    """Provider-only controls; flashcard packing/card knobs never enter Ask AI."""

    provider: Literal["gemini", "openai_compatible"]
    model: str
    api_key_value: str | None = field(repr=False)
    base_url: AnyHttpUrl | None
    temperature: float
    thinking_level: Literal["minimal", "low", "medium", "high"]
    max_output_tokens: int
    timeout_seconds: float
    max_retries: int
    retry_base_seconds: float
    retry_max_seconds: float
    concurrency: int
    requests_per_minute: int
    input_tokens_per_minute: int
    rate_limit_safety_percent: int
    quota_bucket: str


class Settings(BaseSettings):
    """Settings loaded from process environment and the root ``.env``."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_ignore_empty=True,
        hide_input_in_errors=True,
    )

    def __init__(self, **values: object) -> None:
        selected_file = values.get("_env_file", self.model_config["env_file"])
        removed = _removed_ai_names(env_file=selected_file, init_values=values)
        if removed:
            raise ValueError(
                "Removed AI configuration keys: " + ", ".join(removed)
                + ". Move nonempty values to FLASHCARD_AI_* and remove old names; "
                "GEMINI_API_KEY must migrate to FLASHCARD_AI_API_KEY."
            )
        super().__init__(**values)

    app_name: str = Field(default="Cardchemy", min_length=1, max_length=128)
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    api_docs_enabled: bool | None = None
    api_root_path: str = ""
    worker_shutdown_grace_seconds: float = Field(default=30, ge=0, le=7_200)

    # Diagnostics contain only approved operational metadata. Business content
    # and account deletion remain explicit operator actions.
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    request_retention_days: int = Field(default=7, ge=1, le=365)
    generation_job_retention_days: int = Field(default=30, ge=1, le=3_650)
    database_metadata_retention_days: int = Field(default=30, ge=1, le=3_650)
    audit_retention_days: int = Field(default=90, ge=1, le=3_650)
    retention_batch_size: int = Field(default=500, ge=1, le=10_000)
    worker_health_stale_seconds: int = Field(default=60, ge=10, le=3_600)
    telemetry_enabled: bool = False
    telemetry_endpoint: AnyHttpUrl | None = None
    telemetry_timeout_seconds: float = Field(default=5, ge=1, le=30)

    # Compose injects DATABASE_URL with its internal ``db`` host. Native
    # processes derive a localhost URL from the same root PostgreSQL settings.
    database_url: str = ""
    postgres_db: str = Field(default="cardchemy", pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    postgres_user: str = Field(default="admin", pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    postgres_password: SecretStr | None = None
    postgres_port: int = Field(default=5432, ge=1, le=65535)

    secret_key: SecretStr = Field(min_length=32)
    algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "cardchemy-api"
    jwt_audience: str = "cardchemy-web"
    jwt_clock_skew_seconds: int = Field(default=30, ge=0, le=300)
    access_token_expire_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=30)
    refresh_session_expire_days: int = Field(default=30, ge=1, le=90)

    refresh_cookie_name: str = "cardchemy_refresh"
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: Literal["lax", "strict"] = "lax"
    refresh_cookie_domain: str | None = None

    frontend_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:5173")
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    invitation_min_hours: int = Field(default=1, ge=1, le=720)
    invitation_max_hours: int = Field(default=720, ge=1, le=720)
    password_reset_expire_minutes: int = Field(default=30, ge=5, le=120)

    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: EmailStr | None = None
    smtp_from_name: str | None = Field(default=None, max_length=128)
    smtp_reply_to: EmailStr | None = None
    smtp_starttls: bool = False
    smtp_implicit_tls: bool = False
    smtp_timeout_seconds: float = Field(default=15, ge=1, le=120)

    email_worker_concurrency: int = Field(default=4, ge=1, le=32)
    email_worker_poll_seconds: float = Field(default=1, ge=0.1, le=30)
    email_lease_seconds: int = Field(default=240, ge=5, le=3_600)
    email_max_attempts: int = Field(default=5, ge=1, le=10)
    email_retry_base_seconds: float = Field(default=5, ge=0.1, le=3_600)
    email_retry_max_seconds: float = Field(default=300, ge=1, le=86_400)
    email_cleanup_interval_seconds: int = Field(default=3_600, ge=60, le=86_400)
    email_sent_retention_days: int = Field(default=7, ge=1, le=365)
    email_failed_retention_days: int = Field(default=30, ge=1, le=3_650)
    email_security_notification_expire_hours: int = Field(default=24, ge=1, le=168)

    # Flashcard text-generation profile. The 29 former AI_* names are removed.
    flashcard_ai_provider_enabled: bool = False
    flashcard_ai_provider: Literal["gemini", "openai_compatible"] = "gemini"
    flashcard_ai_model: str = Field(default="gemini-3.8-flash", min_length=1, max_length=128)
    flashcard_ai_api_key: SecretStr | None = None
    flashcard_ai_base_url: AnyHttpUrl | None = None
    flashcard_ai_allow_unstable_model: bool = False
    flashcard_ai_temperature: float = Field(default=0.2, ge=0, le=2)
    flashcard_ai_thinking_level: Literal["minimal", "low", "medium", "high"] = "low"
    flashcard_ai_max_output_tokens: int = Field(default=8_192, ge=64, le=131_072)
    flashcard_ai_context_window_tokens: int = Field(default=1_048_576, ge=2_048, le=4_194_304)
    flashcard_ai_provider_timeout_seconds: float = Field(default=90, ge=1, le=600)
    flashcard_ai_provider_max_retries: int = Field(default=3, ge=0, le=3)
    flashcard_ai_retry_base_seconds: float = Field(default=3, ge=3, le=60)
    flashcard_ai_retry_max_seconds: float = Field(default=30, ge=3, le=600)
    flashcard_ai_concurrency: int = Field(default=3, ge=1, le=32)
    flashcard_ai_requests_per_minute: int = Field(default=5, ge=1, le=100_000)
    flashcard_ai_input_tokens_per_minute: int = Field(default=250_000, ge=1, le=100_000_000)
    flashcard_ai_rate_limit_safety_percent: int = Field(default=80, ge=1, le=100)
    flashcard_ai_chunk_input_tokens: int = Field(default=1_200, ge=128, le=131_072)
    flashcard_ai_chunk_overlap_tokens: int = Field(default=120, ge=0, le=32_768)
    flashcard_ai_request_input_target_tokens: int = Field(
        default=40_000, ge=2_048, le=4_000_000
    )
    flashcard_ai_cards_per_request: int = Field(default=10, ge=1, le=100)
    flashcard_ai_summary_output_tokens: int = Field(default=1_024, ge=64, le=32_768)
    flashcard_ai_max_job_input_tokens: int = Field(default=200_000, ge=1_024, le=20_000_000)
    flashcard_ai_max_job_output_tokens: int = Field(default=262_144, ge=64, le=5_000_000)
    flashcard_ai_input_cost_per_million_usd: Decimal = Field(
        default=Decimal("0"), ge=Decimal("0"), le=Decimal("10000")
    )
    flashcard_ai_output_cost_per_million_usd: Decimal = Field(
        default=Decimal("0"), ge=Decimal("0"), le=Decimal("10000")
    )
    flashcard_ai_max_estimated_cost_usd: Decimal = Field(
        default=Decimal("5"), gt=Decimal("0"), le=Decimal("100000")
    )
    flashcard_ai_refill_rounds: int = Field(default=2, ge=0, le=5)
    flashcard_ai_duplicate_similarity_threshold: float = Field(default=0.88, ge=0.5, le=1)
    flashcard_ai_quota_bucket: str = Field(default="", max_length=128)

    # RAG remains off by default. Answer and embedding roles have independent
    # connection material and divided local capacity; no implicit key fallback.
    rag_enabled: bool = False
    rag_ai_provider_enabled: bool = False
    rag_ai_provider: Literal["gemini", "openai_compatible"] = "gemini"
    rag_ai_model: str = Field(default="gemini-3.5-flash", min_length=1, max_length=128)
    rag_ai_api_key: SecretStr | None = None
    rag_ai_base_url: AnyHttpUrl | None = None
    rag_ai_allow_unstable_model: bool = False
    rag_ai_temperature: float = Field(default=0.2, ge=0, le=2)
    rag_ai_thinking_level: Literal["minimal", "low", "medium", "high"] = "minimal"
    rag_ai_max_output_tokens: int = Field(default=2_048, ge=64, le=131_072)
    rag_ai_context_window_tokens: int = Field(default=1_048_576, ge=2_048, le=4_194_304)
    rag_ai_provider_timeout_seconds: float = Field(default=90, ge=1, le=600)
    rag_ai_provider_max_retries: int = Field(default=3, ge=0, le=3)
    rag_ai_retry_base_seconds: float = Field(default=3, ge=3, le=60)
    rag_ai_retry_max_seconds: float = Field(default=30, ge=3, le=600)
    rag_ai_concurrency: int = Field(default=1, ge=1, le=32)
    rag_ai_requests_per_minute: int = Field(default=5, ge=1, le=100_000)
    rag_ai_input_tokens_per_minute: int = Field(default=250_000, ge=1, le=100_000_000)
    rag_ai_rate_limit_safety_percent: int = Field(default=80, ge=1, le=100)
    rag_ai_max_job_input_tokens: int = Field(default=40_000, ge=1_024, le=20_000_000)
    rag_ai_max_job_output_tokens: int = Field(default=4_096, ge=64, le=5_000_000)
    rag_ai_input_cost_per_million_usd: Decimal = Field(default=Decimal("1.50"), ge=0, le=10_000)
    rag_ai_output_cost_per_million_usd: Decimal = Field(default=Decimal("9.00"), ge=0, le=10_000)
    rag_ai_max_estimated_cost_usd: Decimal = Field(default=Decimal("1"), gt=0, le=100_000)
    rag_ai_quota_bucket: str = Field(default="", max_length=128)

    rag_embedding_provider_enabled: bool = False
    rag_embedding_provider: Literal["gemini", "openai_compatible"] = "gemini"
    rag_embedding_model: str = Field(default="gemini-embedding-001", min_length=1, max_length=128)
    rag_embedding_api_key: SecretStr | None = None
    rag_embedding_base_url: AnyHttpUrl | None = None
    rag_embedding_dimensions: int = Field(default=1_536, ge=1_536, le=1_536)
    rag_embedding_format_version: Literal["raw_text_v1"] = "raw_text_v1"
    rag_embedding_space_revision: str = Field(default="gemini-v1", min_length=1, max_length=64)
    rag_embedding_representation: Literal["float32"] = "float32"
    rag_embedding_metric: Literal["cosine"] = "cosine"
    rag_embedding_document_task_mode: Literal["shared_input"] = "shared_input"
    rag_embedding_query_task_mode: Literal["shared_input"] = "shared_input"
    rag_embedding_batch_size: int = Field(default=32, ge=1, le=256)
    rag_embedding_max_input_tokens: int = Field(default=2_048, ge=128, le=1_000_000)
    rag_embedding_provider_timeout_seconds: float = Field(default=90, ge=1, le=600)
    rag_embedding_provider_max_retries: int = Field(default=3, ge=0, le=3)
    rag_embedding_retry_base_seconds: float = Field(default=3, ge=3, le=60)
    rag_embedding_retry_max_seconds: float = Field(default=30, ge=3, le=600)
    rag_embedding_concurrency: int = Field(default=1, ge=1, le=32)
    rag_embedding_requests_per_minute: int = Field(default=5, ge=1, le=100_000)
    rag_embedding_input_tokens_per_minute: int = Field(default=250_000, ge=1, le=100_000_000)
    rag_embedding_rate_limit_safety_percent: int = Field(default=80, ge=1, le=100)
    rag_embedding_input_cost_per_million_usd: Decimal = Field(default=Decimal("0.15"), ge=0, le=10_000)
    rag_embedding_max_estimated_cost_usd: Decimal = Field(default=Decimal("1"), gt=0, le=100_000)
    rag_embedding_quota_bucket: str = Field(default="", max_length=128)

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
    generation_daily_jobs_per_user: int = Field(default=20, ge=1, le=10_000)
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

    # Knowledge-only capture has a separate conservative admission lane. It
    # reuses the encrypted PDF source queue without consuming flashcard units.
    knowledge_max_active_jobs_per_user: int = Field(default=1, ge=1, le=25)
    knowledge_max_active_jobs_deployment: int = Field(default=10, ge=1, le=10_000)
    knowledge_max_queued_jobs_deployment: int = Field(default=50, ge=1, le=100_000)
    knowledge_daily_jobs_per_user: int = Field(default=10, ge=1, le=10_000)
    knowledge_daily_upload_bytes_per_user: int = Field(
        default=50 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024 * 1024
    )
    knowledge_daily_jobs_deployment: int = Field(default=500, ge=1, le=1_000_000)
    knowledge_daily_upload_bytes_deployment: int = Field(
        default=5 * 1024 * 1024 * 1024,
        ge=1024,
        le=10 * 1024 * 1024 * 1024 * 1024,
    )
    knowledge_max_retained_source_bytes_per_user: int = Field(
        default=25 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024 * 1024
    )
    knowledge_max_retained_source_bytes_deployment: int = Field(
        default=512 * 1024 * 1024,
        ge=1024,
        le=10 * 1024 * 1024 * 1024 * 1024,
    )

    # Durable index workers are independent from generation workers. A call
    # that crossed the provider boundary is never replayed automatically after
    # an uncertain lease/deadline outcome; an operator may explicitly reindex.
    rag_index_worker_concurrency: int = Field(default=1, ge=1, le=32)
    rag_index_max_job_input_tokens: int = Field(default=500_000, ge=1_024, le=20_000_000)
    rag_index_job_timeout_seconds: int = Field(default=600, ge=30, le=7_200)
    rag_index_lease_seconds: int = Field(default=60, ge=15, le=600)
    rag_index_worker_poll_seconds: float = Field(default=1.0, ge=0.1, le=30)
    rag_index_heartbeat_seconds: float = Field(default=10.0, ge=1, le=120)
    rag_index_max_attempts: int = Field(default=3, ge=1, le=10)
    rag_index_retry_base_seconds: float = Field(default=3.0, ge=3, le=300)
    rag_index_retry_max_seconds: float = Field(default=60.0, ge=3, le=3_600)
    rag_index_cleanup_interval_seconds: int = Field(default=60, ge=5, le=3_600)

    # Subject Ask AI has its own durable queue, chat capacity and retention.
    # These bounds are independent from flashcard generation and Knowledge
    # upload quotas even when the same provider account is deliberately shared.
    rag_chat_retention_days: int = Field(default=90, ge=1, le=365)
    rag_answer_max_threads_per_user: int = Field(default=50, ge=1, le=1_000)
    rag_answer_max_threads_deployment: int = Field(default=10_000, ge=1, le=1_000_000)
    rag_answer_max_messages_per_thread: int = Field(default=200, ge=2, le=2_000)
    rag_answer_max_messages_per_user: int = Field(default=5_000, ge=2, le=100_000)
    rag_answer_max_messages_deployment: int = Field(default=1_000_000, ge=2, le=100_000_000)
    rag_answer_max_question_chars: int = Field(default=4_000, ge=1, le=4_000)
    rag_answer_max_answer_chars: int = Field(default=12_000, ge=1, le=12_000)
    rag_answer_max_history_messages: int = Field(default=12, ge=0, le=100)
    rag_answer_history_token_limit: int = Field(default=8_192, ge=128, le=64_000)
    rag_answer_max_active_jobs_per_user: int = Field(default=1, ge=1, le=25)
    rag_answer_max_active_jobs_deployment: int = Field(default=10, ge=1, le=10_000)
    rag_answer_max_queued_jobs_deployment: int = Field(default=100, ge=1, le=100_000)
    rag_answer_daily_jobs_per_user: int = Field(default=100, ge=1, le=100_000)
    rag_answer_daily_jobs_deployment: int = Field(default=10_000, ge=1, le=1_000_000)
    rag_answer_worker_concurrency: int = Field(default=1, ge=1, le=32)
    rag_answer_job_timeout_seconds: int = Field(default=300, ge=30, le=3_600)
    rag_answer_lease_seconds: int = Field(default=60, ge=15, le=600)
    rag_answer_worker_poll_seconds: float = Field(default=1.0, ge=0.1, le=30)
    rag_answer_heartbeat_seconds: float = Field(default=10.0, ge=1, le=120)
    rag_answer_max_attempts: int = Field(default=3, ge=1, le=10)
    rag_answer_max_manual_retries: int = Field(default=2, ge=0, le=10)
    rag_answer_retry_base_seconds: float = Field(default=3.0, ge=3, le=300)
    rag_answer_retry_max_seconds: float = Field(default=60.0, ge=3, le=3_600)
    rag_answer_cleanup_interval_seconds: int = Field(default=60, ge=5, le=3_600)

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
    def api_docs_are_enabled(self) -> bool:
        """Keep local documentation convenient while defaulting production closed."""

        if self.api_docs_enabled is not None:
            return self.api_docs_enabled
        return self.environment != "production"

    @property
    def smtp_security(self) -> Literal["none", "starttls", "implicit_tls"]:
        if self.smtp_implicit_tls:
            return "implicit_tls"
        if self.smtp_starttls:
            return "starttls"
        return "none"

    def require_email_delivery_config(self) -> "Settings":
        """Fail an email worker startup unless its delivery settings are usable."""

        missing = []
        if not self.smtp_host:
            missing.append("SMTP_HOST")
        if not self.smtp_from_email:
            missing.append("SMTP_FROM_EMAIL")
        if missing:
            raise ValueError(f"Email delivery requires {', '.join(missing)}")
        if self.environment == "production":
            if self.smtp_security == "none":
                raise ValueError("Production email delivery requires STARTTLS or implicit TLS")
            if self.smtp_host.casefold() == "mailpit":
                raise ValueError("Mailpit cannot be used for production email delivery")
        return self

    @property
    def flashcard_ai_api_key_value(self) -> str | None:
        """Return the configured key without ever including it in model output."""

        configured = self.flashcard_ai_api_key
        if configured is None:
            return None
        value = configured.get_secret_value().strip()
        return value or None

    @property
    def flashcard_ai_provider_configured(self) -> bool:
        """Return whether this process has the provider connection material."""

        if self.flashcard_ai_provider == "gemini":
            return self.flashcard_ai_api_key_value is not None
        return self.flashcard_ai_base_url is not None

    def require_generation_worker_config(self) -> "Settings":
        """Fail worker startup when an enabled provider lacks credentials."""

        if (
            self.flashcard_ai_provider_enabled
            and self.flashcard_ai_provider == "gemini"
            and self.flashcard_ai_api_key_value is None
        ):
            raise ValueError(
                "Enabled Gemini generation requires FLASHCARD_AI_API_KEY"
            )
        if self.flashcard_ai_provider_enabled and not self.flashcard_ai_quota_bucket:
            raise ValueError("Enabled flashcard generation requires FLASHCARD_AI_QUOTA_BUCKET")
        return self

    @staticmethod
    def _secret_value(value: SecretStr | None) -> str | None:
        if value is None:
            return None
        return value.get_secret_value().strip() or None

    @property
    def rag_ai_api_key_value(self) -> str | None:
        return self._secret_value(self.rag_ai_api_key)

    @property
    def rag_embedding_api_key_value(self) -> str | None:
        return self._secret_value(self.rag_embedding_api_key)

    @property
    def rag_answer_available(self) -> bool:
        """Nonsecret admission metadata; authorization is checked elsewhere."""

        return self.rag_enabled and self.rag_ai_provider_enabled and self.rag_embedding_provider_enabled

    @property
    def rag_index_available(self) -> bool:
        return self.rag_enabled and self.rag_embedding_provider_enabled

    @property
    def rag_ai_endpoint_identity(self) -> str:
        if self.rag_ai_provider == "gemini":
            return "https://generativelanguage.googleapis.com"
        assert self.rag_ai_base_url is not None
        return str(self.rag_ai_base_url).rstrip("/")

    @property
    def rag_embedding_endpoint_identity(self) -> str:
        if self.rag_embedding_provider == "gemini":
            return "https://generativelanguage.googleapis.com"
        assert self.rag_embedding_base_url is not None
        return str(self.rag_embedding_base_url).rstrip("/")

    @property
    def rag_embedding_provider_task_modes(self) -> tuple[str, str]:
        """Return the physical provider task modes that define vector compatibility."""

        if self.rag_embedding_provider == "gemini":
            return ("RETRIEVAL_DOCUMENT", "QUESTION_ANSWERING")
        return (
            self.rag_embedding_document_task_mode,
            self.rag_embedding_query_task_mode,
        )

    @property
    def rag_embedding_space_identity(
        self,
    ) -> tuple[str, str, str, str, str, int, str, str, str, str]:
        """Nonsecret exact embedding-space identity for future revision fences."""

        document_task_mode, query_task_mode = self.rag_embedding_provider_task_modes
        return (
            self.rag_embedding_provider,
            self.rag_embedding_endpoint_identity,
            self.rag_embedding_model,
            self.rag_embedding_space_revision,
            self.rag_embedding_format_version,
            self.rag_embedding_dimensions,
            self.rag_embedding_representation,
            self.rag_embedding_metric,
            document_task_mode,
            query_task_mode,
        )

    def text_provider_profile(self, role: Literal["flashcard", "rag_answer"] = "flashcard") -> TextProviderProfile:
        prefix = "flashcard_ai" if role == "flashcard" else "rag_ai"
        if role not in ("flashcard", "rag_answer"):
            raise ValueError("Unknown text provider role")
        return TextProviderProfile(
            provider=getattr(self, f"{prefix}_provider"),
            model=getattr(self, f"{prefix}_model"),
            api_key_value=self._secret_value(getattr(self, f"{prefix}_api_key")),
            base_url=getattr(self, f"{prefix}_base_url"),
            temperature=getattr(self, f"{prefix}_temperature"),
            thinking_level=getattr(self, f"{prefix}_thinking_level"),
            max_output_tokens=getattr(self, f"{prefix}_max_output_tokens"),
            timeout_seconds=getattr(self, f"{prefix}_provider_timeout_seconds"),
            max_retries=getattr(self, f"{prefix}_provider_max_retries"),
            retry_base_seconds=getattr(self, f"{prefix}_retry_base_seconds"),
            retry_max_seconds=getattr(self, f"{prefix}_retry_max_seconds"),
            concurrency=getattr(self, f"{prefix}_concurrency"),
            requests_per_minute=getattr(self, f"{prefix}_requests_per_minute"),
            input_tokens_per_minute=getattr(self, f"{prefix}_input_tokens_per_minute"),
            rate_limit_safety_percent=getattr(self, f"{prefix}_rate_limit_safety_percent"),
            quota_bucket=getattr(self, f"{prefix}_quota_bucket"),
        )

    def require_rag_answer_worker_config(self) -> "Settings":
        """Require only answer/query credentials when that role is enabled."""

        if not self.rag_enabled or not self.rag_ai_provider_enabled:
            return self
        if not self.rag_embedding_provider_enabled:
            raise ValueError("Ask AI requires RAG_EMBEDDING_PROVIDER_ENABLED")
        if self.rag_ai_api_key_value is None:
            raise ValueError("Ask AI worker requires RAG_AI_API_KEY")
        if self.rag_embedding_api_key_value is None:
            raise ValueError("Ask AI worker requires RAG_EMBEDDING_API_KEY")
        if not self.rag_ai_quota_bucket or not self.rag_embedding_quota_bucket:
            raise ValueError("Ask AI worker requires RAG_AI_QUOTA_BUCKET and RAG_EMBEDDING_QUOTA_BUCKET")
        return self

    def require_rag_index_worker_config(self) -> "Settings":
        """Require only document-embedding credentials for an enabled index role."""

        if self.rag_index_available:
            if self.rag_embedding_api_key_value is None:
                raise ValueError("Index worker requires RAG_EMBEDDING_API_KEY")
            if not self.rag_embedding_quota_bucket:
                raise ValueError("Index worker requires RAG_EMBEDDING_QUOTA_BUCKET")
        return self

    @property
    def flashcard_ai_pricing_configured(self) -> bool:
        return bool(
            self.flashcard_ai_input_cost_per_million_usd > 0
            or self.flashcard_ai_output_cost_per_million_usd > 0
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

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [entry.strip() for entry in value.split(",") if entry.strip()]
        if not origins:
            raise ValueError("CORS_ORIGINS must contain at least one exact origin")
        normalized = [normalize_http_origin(origin) for origin in origins]
        if len(set(normalized)) != len(normalized):
            raise ValueError("CORS_ORIGINS cannot contain duplicate origins")
        return ",".join(normalized)

    @field_validator("api_root_path")
    @classmethod
    def validate_api_root_path(cls, value: str) -> str:
        if value == "":
            return value
        if not API_ROOT_PATH_PATTERN.fullmatch(value):
            raise ValueError(
                "API_ROOT_PATH must be empty or an absolute URL path without a trailing slash"
            )
        return value

    @field_validator("app_name", "smtp_from_name")
    @classmethod
    def validate_email_header_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized or any(ord(character) < 32 or ord(character) == 127 for character in normalized):
            raise ValueError("Email header text must be non-empty and contain no control characters")
        return normalized

    @field_validator("smtp_host", mode="before")
    @classmethod
    def validate_smtp_host(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            return None
        if any(ord(character) <= 32 or ord(character) == 127 for character in normalized):
            raise ValueError("SMTP_HOST cannot contain whitespace or control characters")
        if any(delimiter in normalized for delimiter in ("://", "/", "@", "?", "#")):
            raise ValueError("SMTP_HOST must be a hostname or IP address without a URL or port")

        ip_candidate = normalized[1:-1] if normalized.startswith("[") and normalized.endswith("]") else normalized
        try:
            return str(ipaddress.ip_address(ip_candidate))
        except ValueError:
            pass

        try:
            ascii_host = normalized.rstrip(".").encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValueError("SMTP_HOST is not a valid hostname") from exc
        if not ascii_host or len(ascii_host) > 253:
            raise ValueError("SMTP_HOST is not a valid hostname")
        if any(not DNS_LABEL_PATTERN.fullmatch(label) for label in ascii_host.split(".")):
            raise ValueError("SMTP_HOST is not a valid hostname")
        return ascii_host

    @field_validator("smtp_username", mode="before")
    @classmethod
    def validate_smtp_username(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        if not value:
            return None
        if len(value) > 320 or any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("SMTP_USERNAME is too long or contains control characters")
        return value

    @field_validator("frontend_base_url")
    @classmethod
    def validate_frontend_base_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.username or value.password or value.query or value.fragment:
            raise ValueError(
                "FRONTEND_BASE_URL cannot contain credentials, a query, or a fragment"
            )
        return value

    @field_validator("flashcard_ai_model", "rag_ai_model", "rag_embedding_model")
    @classmethod
    def validate_ai_model_name(cls, value: str, info: ValidationInfo) -> str:
        normalized = value.strip()
        if not normalized or any(ord(character) < 32 for character in normalized):
            raise ValueError(f"{info.field_name.upper()} must be a non-empty printable model identifier")
        return normalized

    @field_validator("flashcard_ai_base_url", "rag_ai_base_url", "rag_embedding_base_url")
    @classmethod
    def validate_ai_base_url(cls, value: AnyHttpUrl | None, info: ValidationInfo) -> AnyHttpUrl | None:
        if value is None:
            return None
        if value.username or value.password or value.query or value.fragment:
            raise ValueError(f"{info.field_name.upper()} cannot contain credentials, a query, or a fragment")
        return value

    @field_validator("rag_embedding_space_revision")
    @classmethod
    def validate_embedding_revision(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", value):
            raise ValueError("RAG_EMBEDDING_SPACE_REVISION must be a non-secret stable label")
        return value

    @field_validator("flashcard_ai_quota_bucket", "rag_ai_quota_bucket", "rag_embedding_quota_bucket")
    @classmethod
    def validate_quota_bucket(cls, value: str) -> str:
        if value and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value):
            raise ValueError("Quota bucket must be a non-secret provider account/project label")
        return value

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        if self.telemetry_endpoint is not None:
            endpoint = urlsplit(str(self.telemetry_endpoint))
            if (endpoint.scheme != "https" or endpoint.username or endpoint.password
                    or endpoint.query or endpoint.fragment):
                raise ValueError("TELEMETRY_ENDPOINT must use HTTPS without credentials, query or fragment")
        if self.telemetry_enabled and self.telemetry_endpoint is None:
            raise ValueError("Enabled telemetry requires TELEMETRY_ENDPOINT")
        if self.worker_health_stale_seconds < 2 * max(
            self.generation_worker_poll_seconds,
            self.rag_index_worker_poll_seconds,
            self.email_worker_poll_seconds,
            5,
        ):
            raise ValueError("Worker health stale threshold must cover two scheduling poll intervals")
        if not self.database_url:
            if not self.postgres_password or not self.postgres_password.get_secret_value():
                raise ValueError("DATABASE_URL or POSTGRES_PASSWORD is required")
            password = quote(self.postgres_password.get_secret_value(), safe="")
            self.database_url = (
                f"postgresql+asyncpg://{self.postgres_user}:{password}"
                f"@127.0.0.1:{self.postgres_port}/{self.postgres_db}"
            )
        secret = self.secret_key_value
        if secret.lower() in INSECURE_SECRET_VALUES or len(set(secret)) < 8:
            raise ValueError("SECRET_KEY is known-insecure or lacks sufficient entropy")

        if self.invitation_min_hours > self.invitation_max_hours:
            raise ValueError("INVITATION_MIN_HOURS cannot exceed INVITATION_MAX_HOURS")

        username_configured = self.smtp_username is not None
        password_configured = bool(
            self.smtp_password and self.smtp_password.get_secret_value()
        )
        if username_configured != password_configured:
            raise ValueError("SMTP_USERNAME and SMTP_PASSWORD must be configured together")
        if self.smtp_starttls and self.smtp_implicit_tls:
            raise ValueError("SMTP_STARTTLS and SMTP_IMPLICIT_TLS cannot both be enabled")
        if username_configured and self.smtp_security == "none":
            raise ValueError("SMTP credentials require STARTTLS or implicit TLS")
        if self.email_lease_seconds < self.smtp_timeout_seconds * 12:
            raise ValueError(
                "EMAIL_LEASE_SECONDS must be at least twelve times SMTP_TIMEOUT_SECONDS"
            )
        if self.email_retry_base_seconds > self.email_retry_max_seconds:
            raise ValueError("EMAIL_RETRY_BASE_SECONDS cannot exceed EMAIL_RETRY_MAX_SECONDS")

        if self.generation_min_card_count > self.generation_max_card_count:
            raise ValueError("GENERATION_MIN_CARD_COUNT cannot exceed GENERATION_MAX_CARD_COUNT")
        if self.generation_retry_base_seconds > self.generation_retry_max_seconds:
            raise ValueError(
                "GENERATION_RETRY_BASE_SECONDS cannot exceed GENERATION_RETRY_MAX_SECONDS"
            )
        if self.flashcard_ai_retry_base_seconds > self.flashcard_ai_retry_max_seconds:
            raise ValueError("FLASHCARD_AI_RETRY_BASE_SECONDS cannot exceed FLASHCARD_AI_RETRY_MAX_SECONDS")
        if self.flashcard_ai_chunk_overlap_tokens >= self.flashcard_ai_chunk_input_tokens:
            raise ValueError("FLASHCARD_AI_CHUNK_OVERLAP_TOKENS must be lower than FLASHCARD_AI_CHUNK_INPUT_TOKENS")
        if self.flashcard_ai_chunk_input_tokens > self.flashcard_ai_request_input_target_tokens:
            raise ValueError(
                "FLASHCARD_AI_CHUNK_INPUT_TOKENS cannot exceed FLASHCARD_AI_REQUEST_INPUT_TARGET_TOKENS"
            )
        if self.flashcard_ai_summary_output_tokens > self.flashcard_ai_max_output_tokens:
            raise ValueError("FLASHCARD_AI_SUMMARY_OUTPUT_TOKENS cannot exceed FLASHCARD_AI_MAX_OUTPUT_TOKENS")
        if self.flashcard_ai_max_output_tokens >= self.flashcard_ai_context_window_tokens:
            raise ValueError("FLASHCARD_AI_MAX_OUTPUT_TOKENS must be lower than FLASHCARD_AI_CONTEXT_WINDOW_TOKENS")
        if (
            self.flashcard_ai_request_input_target_tokens + self.flashcard_ai_max_output_tokens
            > self.flashcard_ai_context_window_tokens
        ):
            raise ValueError(
                "AI request input and output token budgets exceed "
                "FLASHCARD_AI_CONTEXT_WINDOW_TOKENS"
            )
        effective_input_tpm = (
            self.flashcard_ai_input_tokens_per_minute * self.flashcard_ai_rate_limit_safety_percent // 100
        )
        if self.flashcard_ai_request_input_target_tokens > effective_input_tpm:
            raise ValueError(
                "FLASHCARD_AI_REQUEST_INPUT_TARGET_TOKENS cannot exceed the safety-adjusted "
                "FLASHCARD_AI_INPUT_TOKENS_PER_MINUTE budget"
            )
        if (
            self.flashcard_ai_chunk_input_tokens
            + self.flashcard_ai_summary_output_tokens
            + self.flashcard_ai_max_output_tokens
            > self.flashcard_ai_context_window_tokens
        ):
            raise ValueError(
                "AI chunk, summary, and output token budgets exceed FLASHCARD_AI_CONTEXT_WINDOW_TOKENS"
            )
        if self.flashcard_ai_max_job_input_tokens < self.flashcard_ai_chunk_input_tokens:
            raise ValueError("FLASHCARD_AI_MAX_JOB_INPUT_TOKENS cannot be lower than FLASHCARD_AI_CHUNK_INPUT_TOKENS")
        if self.flashcard_ai_max_job_output_tokens < self.flashcard_ai_max_output_tokens:
            raise ValueError("FLASHCARD_AI_MAX_JOB_OUTPUT_TOKENS cannot be lower than FLASHCARD_AI_MAX_OUTPUT_TOKENS")
        prices = (
            self.flashcard_ai_input_cost_per_million_usd,
            self.flashcard_ai_output_cost_per_million_usd,
        )
        if (prices[0] == 0) != (prices[1] == 0):
            raise ValueError("AI input and output prices must both be configured or both be zero")
        if self.flashcard_ai_provider == "openai_compatible" and self.flashcard_ai_base_url is None:
            raise ValueError("FLASHCARD_AI_BASE_URL is required for the openai_compatible provider")
        if self.flashcard_ai_provider == "gemini" and self.flashcard_ai_base_url is not None:
            raise ValueError("FLASHCARD_AI_BASE_URL is only valid for the openai_compatible provider")
        if self.rag_ai_provider == "openai_compatible" and self.rag_ai_base_url is None:
            raise ValueError("RAG_AI_BASE_URL is required for the openai_compatible provider")
        if self.rag_ai_provider == "gemini" and self.rag_ai_base_url is not None:
            raise ValueError(
                "RAG_AI_BASE_URL is only valid for the openai_compatible provider"
            )
        if (
            self.rag_embedding_provider == "openai_compatible"
            and self.rag_embedding_base_url is None
        ):
            raise ValueError(
                "RAG_EMBEDDING_BASE_URL is required for the openai_compatible provider"
            )
        if (
            self.rag_embedding_provider == "gemini"
            and self.rag_embedding_base_url is not None
        ):
            raise ValueError(
                "RAG_EMBEDDING_BASE_URL is only valid for the openai_compatible provider"
            )
        if self.rag_embedding_provider == "gemini" and (
            self.rag_embedding_model != "gemini-embedding-001"
            or self.rag_embedding_dimensions != 1_536
        ):
            raise ValueError(
                "The Gemini embedding profile requires gemini-embedding-001 with 1536 dimensions"
            )
        if self.rag_ai_retry_base_seconds > self.rag_ai_retry_max_seconds:
            raise ValueError("RAG_AI_RETRY_BASE_SECONDS cannot exceed RAG_AI_RETRY_MAX_SECONDS")
        if self.rag_embedding_retry_base_seconds > self.rag_embedding_retry_max_seconds:
            raise ValueError("RAG_EMBEDDING_RETRY_BASE_SECONDS cannot exceed RAG_EMBEDDING_RETRY_MAX_SECONDS")
        if self.rag_ai_max_output_tokens >= self.rag_ai_context_window_tokens:
            raise ValueError("RAG_AI_MAX_OUTPUT_TOKENS must be lower than RAG_AI_CONTEXT_WINDOW_TOKENS")
        if self.rag_ai_max_job_input_tokens + self.rag_ai_max_output_tokens > self.rag_ai_context_window_tokens:
            raise ValueError("RAG_AI_MAX_JOB_INPUT_TOKENS and RAG_AI_MAX_OUTPUT_TOKENS exceed RAG_AI_CONTEXT_WINDOW_TOKENS")
        if self.rag_ai_max_job_output_tokens < self.rag_ai_max_output_tokens:
            raise ValueError("RAG_AI_MAX_JOB_OUTPUT_TOKENS cannot be lower than RAG_AI_MAX_OUTPUT_TOKENS")
        if self.rag_ai_max_job_input_tokens > self.rag_ai_input_tokens_per_minute * self.rag_ai_rate_limit_safety_percent // 100:
            raise ValueError("RAG_AI_MAX_JOB_INPUT_TOKENS exceeds safety-adjusted RAG_AI_INPUT_TOKENS_PER_MINUTE")
        if self.rag_embedding_max_input_tokens > self.rag_embedding_input_tokens_per_minute * self.rag_embedding_rate_limit_safety_percent // 100:
            raise ValueError("RAG_EMBEDDING_MAX_INPUT_TOKENS exceeds safety-adjusted RAG_EMBEDDING_INPUT_TOKENS_PER_MINUTE")
        if self.generation_heartbeat_seconds >= self.generation_lease_seconds:
            raise ValueError("GENERATION_HEARTBEAT_SECONDS must be lower than GENERATION_LEASE_SECONDS")
        if self.generation_worker_concurrency > self.generation_max_active_jobs_deployment:
            raise ValueError(
                "GENERATION_WORKER_CONCURRENCY cannot exceed "
                "GENERATION_MAX_ACTIVE_JOBS_DEPLOYMENT"
            )
        if self.rag_index_retry_base_seconds > self.rag_index_retry_max_seconds:
            raise ValueError("RAG_INDEX_RETRY_BASE_SECONDS cannot exceed RAG_INDEX_RETRY_MAX_SECONDS")
        if self.rag_index_heartbeat_seconds >= self.rag_index_lease_seconds:
            raise ValueError("RAG_INDEX_HEARTBEAT_SECONDS must be lower than RAG_INDEX_LEASE_SECONDS")
        if self.rag_index_max_job_input_tokens < self.rag_embedding_max_input_tokens:
            raise ValueError("RAG_INDEX_MAX_JOB_INPUT_TOKENS cannot be lower than RAG_EMBEDDING_MAX_INPUT_TOKENS")
        if self.rag_answer_retry_base_seconds > self.rag_answer_retry_max_seconds:
            raise ValueError("RAG_ANSWER_RETRY_BASE_SECONDS cannot exceed RAG_ANSWER_RETRY_MAX_SECONDS")
        if self.rag_answer_heartbeat_seconds >= self.rag_answer_lease_seconds:
            raise ValueError("RAG_ANSWER_HEARTBEAT_SECONDS must be lower than RAG_ANSWER_LEASE_SECONDS")
        if self.rag_answer_max_active_jobs_per_user > self.rag_answer_max_active_jobs_deployment:
            raise ValueError("RAG answer per-user active limit cannot exceed the deployment active limit")
        if self.rag_answer_max_threads_per_user > self.rag_answer_max_threads_deployment:
            raise ValueError("RAG per-user thread limit cannot exceed the deployment thread limit")
        if self.rag_answer_max_messages_per_thread > self.rag_answer_max_messages_per_user:
            raise ValueError("RAG per-thread message limit cannot exceed the per-user message limit")
        if self.rag_answer_max_messages_per_user > self.rag_answer_max_messages_deployment:
            raise ValueError("RAG per-user message limit cannot exceed the deployment message limit")
        self.generation_source_encryption_key_bytes

        if self.environment == "production":
            if not self.flashcard_ai_allow_unstable_model and UNSTABLE_MODEL_PATTERN.search(self.flashcard_ai_model):
                raise ValueError(
                    "Preview, latest, and experimental AI models require "
                    "FLASHCARD_AI_ALLOW_UNSTABLE_MODEL=true in production"
                )
            if not self.rag_ai_allow_unstable_model and UNSTABLE_MODEL_PATTERN.search(self.rag_ai_model):
                raise ValueError("Unstable RAG_AI_MODEL requires RAG_AI_ALLOW_UNSTABLE_MODEL=true in production")
            if self.debug:
                raise ValueError("DEBUG must be false in production")
            if not self.refresh_cookie_secure:
                raise ValueError("REFRESH_COOKIE_SECURE must be true in production")
            if self.frontend_base_url.scheme != "https":
                raise ValueError("FRONTEND_BASE_URL must use HTTPS in production")
            for origin in self.cors_origin_list:
                parsed_origin = urlsplit(origin)
                if parsed_origin.scheme != "https":
                    raise ValueError("Production CORS_ORIGINS must use HTTPS")
                hostname = parsed_origin.hostname
                if hostname == "localhost":
                    raise ValueError("Production CORS_ORIGINS cannot contain localhost origins")
                try:
                    address = ipaddress.ip_address(hostname) if hostname else None
                except ValueError:
                    address = None
                if address and address.is_loopback:
                    raise ValueError("Production CORS_ORIGINS cannot contain loopback origins")

        return self


@lru_cache
def get_settings() -> Settings:
    # The test runner injects every required setting and must never pick up an
    # operator's real root .env through an imported application module.
    return Settings(_env_file=None if os.getenv("ENVIRONMENT") == "test" else ROOT_DIR / ".env")
