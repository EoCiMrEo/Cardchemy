"""Student-facing, published-only lecture navigation contracts."""

from uuid import UUID

from pydantic import BaseModel, Field


class PublishedKnowledgeDocument(BaseModel):
    id: UUID
    title: str = Field(min_length=1, max_length=255)
    page_count: int = Field(ge=1, le=100)
    has_original_pdf: bool


class PublishedKnowledgeList(BaseModel):
    documents: list[PublishedKnowledgeDocument] = Field(max_length=100)


class PublishedKnowledgeSearchHit(BaseModel):
    document_id: UUID
    document_title: str = Field(min_length=1, max_length=255)
    page_number: int = Field(ge=1, le=100)


class PublishedKnowledgeSearch(BaseModel):
    pages: list[PublishedKnowledgeSearchHit] = Field(max_length=20)


class PublishedKnowledgePage(BaseModel):
    document_title: str = Field(min_length=1, max_length=255)
    page_number: int = Field(ge=1, le=100)
    page_content: str = Field(max_length=20_000)
    truncated: bool
