"""Public API contracts for durable PDF generation jobs."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator


GenerationStatus = Literal[
    "awaiting_upload", "queued", "running", "completed", "failed", "cancelled"
]


class GenerationLimitReason(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=500)


class GenerationJobCreate(BaseModel):
    subject_id: UUID
    set_title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    set_description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000)
    ] | None = None
    source_pdf_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    card_count: int = Field(default=20, ge=1, le=500)

    @field_validator("set_description", mode="before")
    @classmethod
    def blank_description_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class KnowledgeJobCreate(BaseModel):
    subject_id: UUID
    document_id: UUID | None = None
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    source_pdf_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]


class GenerationLimitsResponse(BaseModel):
    generation_available: bool
    ai_provider: str
    ai_model: str
    ai_pricing_configured: bool
    unavailable_reasons: list[GenerationLimitReason]
    max_upload_bytes: int
    max_pages: int
    max_extracted_chars: int
    min_card_count: int
    max_card_count: int
    daily_jobs_per_user: int
    daily_cards_per_user: int
    daily_upload_bytes_per_user: int
    max_active_jobs_per_user: int
    daily_jobs_remaining: int
    daily_cards_remaining: int
    daily_upload_bytes_remaining: int
    active_job_slots_remaining: int
    deployment_queue_slots_remaining: int
    quota_resets_at: datetime
    failed_source_retention_hours: int
    upload_reservation_minutes: int
    ocr_enabled: bool


class GenerationJobResponse(BaseModel):
    id: UUID
    subject_id: UUID
    job_kind: Literal["flashcards", "knowledge_only"]
    document_id: UUID | None
    knowledge_content_revision_id: UUID | None
    knowledge_capture_status: Literal[
        "not_requested", "pending", "captured", "failed", "removed"
    ]
    knowledge_capture_error_code: str | None
    knowledge_capture_error_message: str | None
    flashcard_set_id: UUID | None
    status: GenerationStatus
    progress: int = Field(ge=0, le=100)
    stage: str
    requested_card_count: int
    generated_card_count: int | None
    ai_provider: str
    ai_model: str
    estimated_input_tokens: int = Field(ge=0)
    estimated_output_tokens: int = Field(ge=0)
    estimated_request_count: int = Field(ge=0)
    provider_request_count: int = Field(ge=0)
    provider_retry_count: int = Field(ge=0)
    provider_rate_limit_wait_milliseconds: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    provider_request_counts_by_stage: dict[str, Annotated[int, Field(ge=0)]]
    actual_input_tokens: int | None = Field(default=None, ge=0)
    actual_output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_microusd: int | None = Field(default=None, ge=0)
    actual_cost_microusd: int | None = Field(default=None, ge=0)
    usage_estimated: bool
    accepted_card_count: int = Field(ge=0)
    rejected_card_count: int = Field(ge=0)
    limit_reason_code: str | None
    limit_reason_message: str | None
    source_pdf_name: str
    attempt_count: int
    max_attempts: int
    error_code: str | None
    error_message: str | None
    cancellation_requested_at: datetime | None
    source_retry_expires_at: datetime | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime
    can_cancel: bool
    can_retry: bool


class GenerationJobListResponse(BaseModel):
    jobs: list[GenerationJobResponse]
