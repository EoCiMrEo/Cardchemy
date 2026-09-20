"""Instructor-only Subject Knowledge management API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_instructor
from app.schemas.knowledge import KnowledgeDocumentListResponse, KnowledgeDocumentResponse
from app.services.knowledge_management import KnowledgeManagementService


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
