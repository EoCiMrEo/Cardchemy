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
    ask_enabled: bool
    ask_available: bool
    ask_policy: Literal["related_knowledge_v1", "related_knowledge_navigation_v2", "related_knowledge_navigation_v3", "related_knowledge_navigation_v4", "related_knowledge_navigation_v5", "related_knowledge_navigation_v6", "related_knowledge_navigation_v7", "related_knowledge_navigation_v8"] | None = None
    answer_available: bool
    answer_provider: str | None = Field(default=None, min_length=1, max_length=32)
    answer_model: str | None = Field(default=None, min_length=1, max_length=128)
    source_judge_available: bool = False
    source_judge_provider: str | None = Field(default=None, min_length=1, max_length=32)
    source_judge_model: str | None = Field(default=None, min_length=1, max_length=128)
    source_judge_transfers_published_content: bool = False
    source_judge_thinking_level: Literal["LOW", "HIGH"] | None = None
    source_judge_transfers_page_images: bool = False
    source_judge_transfers_literal_subject_context: bool = False
    source_judge_contract_version: str | None = Field(default=None, min_length=1, max_length=128)
    embedding_available: bool
    embedding_provider: str = Field(min_length=1, max_length=32)
    embedding_model: str = Field(min_length=1, max_length=128)
    active_embedding_provider: str | None = Field(default=None, min_length=1, max_length=32)
    active_embedding_model: str | None = Field(default=None, min_length=1, max_length=128)
    active_embedding_space_matches: bool
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


class RagRelatedExcerptResponse(BaseModel):
    """Source browsing aid; it makes no claim that the question was answered."""

    excerpt_order: int = Field(ge=1, le=3)
    document_title: str = Field(min_length=1, max_length=255)
    page_number: int = Field(ge=1)
    section: str | None = Field(default=None, max_length=255)
    source_quote: str = Field(min_length=1, max_length=480)


class RagRelatedPageResponse(BaseModel):
    document_title: str = Field(min_length=1, max_length=255)
    page_number: int = Field(ge=1)
    section: str | None = Field(default=None, max_length=255)
    source_quote: str = Field(min_length=1, max_length=480)
    page_content: str = Field(max_length=500_000)
    reference_start: int | None = Field(default=None, ge=0)
    reference_end: int | None = Field(default=None, ge=1)


class RagMessageResponse(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    outcome: Literal["answer", "abstained"] | None
    abstention_kind: Literal["retrieval_insufficient", "model_abstained", "support_rejected"] | None = None
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
    ask_policy: str | None = None
    result_kind: Literal["related_knowledge", "no_match", "clarification_needed"] | None = None
    search_mode: Literal["hybrid", "lexical_fallback", "not_searched"] = "not_searched"
    embedding_provider: str | None = None
    embedding_model: str | None = None
    source_judge_provider: str | None = None
    source_judge_model: str | None = None
    ai_provider: str | None
    ai_model: str | None
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
    estimated_additional_cost_microusd: int | None = Field(default=None, ge=0)
    previous_attempt_cost_microusd: int | None = Field(default=None, ge=0)
    usage_estimated: bool
    support_rejection_count: int = Field(ge=0)
    error_code: str | None
    error_message: str | None
    failure_kind: Literal[
        "provider_temporarily_unavailable", "provider_rejected", "invalid_output",
        "support_unavailable", "internal_failure",
    ] | None = None
    cancellation_requested_at: datetime | None
    created_at: datetime
    completed_at: datetime | None
    updated_at: datetime
    can_cancel: bool
    can_retry: bool
    related_excerpts: list[RagRelatedExcerptResponse] = Field(default_factory=list, max_length=3)


class RagAnswerJobListResponse(BaseModel):
    jobs: list[RagAnswerJobResponse]


__all__ = [
    "RagAnswerJobResponse",
    "RagAnswerJobListResponse",
    "RagHistoryResponse",
    "RagMessageResponse",
    "RagProfileResponse",
    "RagRelatedExcerptResponse",
    "RagRelatedPageResponse",
    "RagQuestionCreate",
    "RagSourceResponse",
    "RagThreadListResponse",
    "RagThreadResponse",
]
