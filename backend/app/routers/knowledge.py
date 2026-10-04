"""Instructor-only Subject Knowledge management API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_instructor
from app.schemas.knowledge import KnowledgeDocumentListResponse, KnowledgeDocumentResponse
from app.services.knowledge_management import KnowledgeManagementService
from app.services.generation import read_bounded_pdf_body
from app.services.pdf_processor import PDFProcessingError, PDFProcessor
from app.services.rate_limit import limit_pdf_upload


router = APIRouter(prefix="/subjects/{subject_id}/knowledge", tags=["Subject Knowledge"])
knowledge = KnowledgeManagementService(get_settings())


async def _prepare_mutation(db: AsyncSession, user: User) -> None:
    """Keep the authenticated instructor loaded across the transaction reset."""

    if user in db.sync_session:
        db.expunge(user)
    await db.rollback()


@router.get("/documents", response_model=KnowledgeDocumentListResponse)
async def list_documents(
    subject_id: UUID,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeDocumentListResponse:
    documents = await knowledge.list_documents(
        db, subject_id=subject_id, user=user, limit=limit
    )
    return KnowledgeDocumentListResponse(documents=documents)


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentResponse)
async def get_document(
    subject_id: UUID,
    document_id: UUID,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeDocumentResponse:
    return await knowledge.get_document_response(
        db, subject_id=subject_id, document_id=document_id, user=user
    )


async def _mutate(
    db: AsyncSession,
    *,
    action: str,
    subject_id: UUID,
    document_id: UUID,
    user: User,
) -> KnowledgeDocumentResponse:
    await _prepare_mutation(db, user)
    async with db.begin():
        operation = getattr(knowledge, action)
        await operation(db, subject_id=subject_id, document_id=document_id, user=user)
    return await knowledge.get_document_response(
        db, subject_id=subject_id, document_id=document_id, user=user
    )


@router.post("/documents/{document_id}/review-publish", response_model=KnowledgeDocumentResponse)
async def review_publish_document(
    subject_id: UUID,
    document_id: UUID,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeDocumentResponse:
    return await _mutate(
        db,
        action="review_and_publish",
        subject_id=subject_id,
        document_id=document_id,
        user=user,
    )


@router.post(
    "/documents/{document_id}/attach-original-pdf", response_model=KnowledgeDocumentResponse,
    dependencies=[Depends(limit_pdf_upload)],
)
async def attach_original_pdf(
    subject_id: UUID, document_id: UUID, request: Request,
    user: User = Depends(get_current_instructor), db: AsyncSession = Depends(get_db),
) -> KnowledgeDocumentResponse:
    """Reattach only the original matching the active revision's exact SHA."""
    from app.services.knowledge_management import knowledge_http_error
    _subject, document = await knowledge._owned_document(
        db, subject_id=subject_id, document_id=document_id, user=user,
    )
    response = await knowledge.get_document_response(
        db, subject_id=subject_id, document_id=document.id, user=user,
    )
    revision = response.content_revision
    if revision is None or not revision.is_active or revision.status != "ready":
        raise knowledge_http_error(409, "knowledge_not_ready", "Knowledge must be ready before attaching its original PDF.")
    expected_revision_id = revision.id
    try:
        PDFProcessor.validate_media_type(request.headers.get("content-type"))
        content = await read_bounded_pdf_body(request, knowledge.settings.pdf_max_upload_bytes)
        PDFProcessor.validate_signature(content)
    except PDFProcessingError as exc:
        code = 415 if exc.code == "unsupported_media_type" else 422
        raise knowledge_http_error(code, exc.code, exc.safe_message) from None
    await _prepare_mutation(db, user)
    async with db.begin():
        await knowledge.attach_original_pdf(
            db, subject_id=subject_id, document_id=document_id, user=user,
            expected_revision_id=expected_revision_id, content=content,
        )
    return await knowledge.get_document_response(db, subject_id=subject_id, document_id=document_id, user=user)


@router.post("/documents/{document_id}/unpublish", response_model=KnowledgeDocumentResponse)
async def unpublish_document(
    subject_id: UUID,
    document_id: UUID,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeDocumentResponse:
    return await _mutate(
        db,
        action="unpublish",
        subject_id=subject_id,
        document_id=document_id,
        user=user,
    )


@router.post("/documents/{document_id}/retry-index", response_model=KnowledgeDocumentResponse)
async def retry_document_index(
    subject_id: UUID,
    document_id: UUID,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeDocumentResponse:
    return await _mutate(
        db,
        action="retry_index",
        subject_id=subject_id,
        document_id=document_id,
        user=user,
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    subject_id: UUID,
    document_id: UUID,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _prepare_mutation(db, user)
    async with db.begin():
        await knowledge.remove(
            db, subject_id=subject_id, document_id=document_id, user=user
        )


__all__ = ["router"]
