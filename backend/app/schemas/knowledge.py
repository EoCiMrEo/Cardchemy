"""Instructor-facing, content-free Subject Knowledge management contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeContentRevisionResponse(BaseModel):
    id: UUID
    revision_no: int = Field(ge=1)
    status: Literal[
        "processing", "pending_index", "ready", "extraction_failed", "cancelled"
    ]
    is_active: bool
    page_count: int = Field(ge=0)
    reviewed_at: datetime | None
    published_at: datetime | None
    error_code: str | None
    error_message: str | None


class KnowledgeIndexRevisionResponse(BaseModel):
    id: UUID
    revision_no: int = Field(ge=1)
    status: Literal[
        "pending_index", "indexing", "ready", "index_failed", "cancelled"
    ]
    is_active: bool
    chunk_count: int = Field(ge=0)
    embedded_count: int = Field(ge=0)
    embedding_model: str
    embedding_space_revision: str
    error_code: str | None
    error_message: str | None


class KnowledgeIndexJobResponse(BaseModel):
    id: UUID
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    attempt_count: int = Field(ge=0)
    max_attempts: int = Field(ge=1)
    error_code: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class KnowledgeDocumentResponse(BaseModel):
    id: UUID
    subject_id: UUID
    title: str = Field(min_length=1, max_length=255)
    source_pdf_name: str = Field(min_length=1, max_length=255)
    created_at: datetime
    updated_at: datetime
    content_revision: KnowledgeContentRevisionResponse | None
    index_revision: KnowledgeIndexRevisionResponse | None
    index_job: KnowledgeIndexJobResponse | None
    can_review_publish: bool
    can_unpublish: bool
    can_retry_index: bool
    can_rebuild_from_pages: bool
    requires_pdf_reupload: bool


class KnowledgeDocumentListResponse(BaseModel):
    documents: list[KnowledgeDocumentResponse]


__all__ = [
    "KnowledgeContentRevisionResponse",
    "KnowledgeDocumentListResponse",
    "KnowledgeDocumentResponse",
    "KnowledgeIndexJobResponse",
    "KnowledgeIndexRevisionResponse",
]
