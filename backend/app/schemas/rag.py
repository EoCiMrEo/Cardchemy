"""Typed HTTP contracts for private Subject Ask AI conversations."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator


class RagQuestionCreate(BaseModel):
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4_000)
    ]
    document_ids: list[UUID] = Field(default_factory=list, max_length=50)

    @field_validator("document_ids")
    @classmethod
    def unique_documents(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("document_ids must be unique")
        return value


class RagProfileResponse(BaseModel):
    rag_enabled: bool
    answer_available: bool
    answer_provider: str = Field(min_length=1, max_length=32)
    answer_model: str = Field(min_length=1, max_length=128)
    embedding_available: bool
    embedding_provider: str = Field(min_length=1, max_length=32)
    embedding_model: str = Field(min_length=1, max_length=128)
    chat_retention_days: int = Field(ge=1, le=365)


class RagThreadResponse(BaseModel):
    id: UUID
    subject_id: UUID
    created_at: datetime
    updated_at: datetime


class RagThreadListResponse(BaseModel):
    threads: list[RagThreadResponse]


class RagSourceResponse(BaseModel):
    citation_order: int = Field(ge=1, le=5)
    chunk_id: UUID
    document_id: UUID
    document_title: str = Field(min_length=1, max_length=255)
    content_revision_id: UUID
    index_revision_id: UUID
    page_number: int = Field(ge=1)
    section: str | None = Field(default=None, max_length=255)
    claim_text: str = Field(min_length=1, max_length=4_000)
    source_quote: str = Field(min_length=1, max_length=12_000)


class RagMessageResponse(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    outcome: Literal["answer", "abstained"] | None
    content: str | None
    hidden: bool
    sources: list[RagSourceResponse]
    created_at: datetime
    expires_at: datetime


class RagHistoryResponse(BaseModel):
    thread: RagThreadResponse
    messages: list[RagMessageResponse]


class RagAnswerJobResponse(BaseModel):
    id: UUID
    thread_id: UUID
    subject_id: UUID
    question_message_id: UUID
    answer_message_id: UUID | None
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    ai_provider: str
    ai_model: str
    retrieval_policy: str
    attempt_count: int = Field(ge=0)
    manual_retry_count: int = Field(ge=0)
    max_attempts: int = Field(ge=1)
    estimated_input_tokens: int = Field(ge=0)
    estimated_output_tokens: int = Field(ge=0)
    actual_input_tokens: int | None = Field(default=None, ge=0)
    actual_output_tokens: int | None = Field(default=None, ge=0)
    provider_request_count: int = Field(ge=0)
    provider_retry_count: int = Field(ge=0)
    provider_rate_limit_wait_milliseconds: int = Field(ge=0)
    estimated_cost_microusd: int | None = Field(default=None, ge=0)
    actual_cost_microusd: int | None = Field(default=None, ge=0)
    usage_estimated: bool
    support_rejection_count: int = Field(ge=0)
    error_code: str | None
    error_message: str | None
    cancellation_requested_at: datetime | None
    created_at: datetime
    completed_at: datetime | None
    updated_at: datetime
    can_cancel: bool
    can_retry: bool


class RagAnswerJobListResponse(BaseModel):
    jobs: list[RagAnswerJobResponse]


__all__ = [
    "RagAnswerJobResponse",
    "RagAnswerJobListResponse",
    "RagHistoryResponse",
    "RagMessageResponse",
    "RagProfileResponse",
    "RagQuestionCreate",
    "RagSourceResponse",
    "RagThreadListResponse",
    "RagThreadResponse",
]
