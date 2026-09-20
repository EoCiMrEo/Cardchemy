"""Authorized instructor lifecycle for private Subject Knowledge."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.audit import AuditAction
from app.models.generation import GenerationJob
from app.models.knowledge import (
    SubjectDocument,
    SubjectDocumentContentRevision,
    SubjectDocumentIndexJob,
    SubjectDocumentIndexRevision,
)
from app.models.rag import RagAnswerJob
from app.models.subject import Subject
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeContentRevisionResponse,
    KnowledgeDocumentResponse,
    KnowledgeIndexJobResponse,
    KnowledgeIndexRevisionResponse,
)
from app.services.knowledge_indexing import (
    KnowledgeCutoverError,
    cutover_subject_embedding_space,
    enqueue_content_index,
    ensure_embedding_space,
)
from app.services.knowledge_lock import acquire_knowledge_write_lock
from app.services.audit import AuditService
from app.services.subject import SubjectService
from app.time_utils import utcnow


def knowledge_http_error(status_code: int, code: str, message: str) -> HTTPException:
    error = HTTPException(status_code=status_code, detail={"code": code, "message": message})
    error.safe_detail = error.detail
    return error


class KnowledgeManagementService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def _owned_document(
        self,
        db: AsyncSession,
        *,
        subject_id: UUID,
        document_id: UUID,
        user: User,
        for_update: bool = False,
    ) -> tuple[Subject, SubjectDocument]:
        subject = await SubjectService.check_subject_access(
            db, subject_id, user, require_owner=True
        )
        query = select(SubjectDocument).where(
            SubjectDocument.id == document_id,
            SubjectDocument.subject_id == subject_id,
            SubjectDocument.uploader_id == user.id,
        )
        if for_update:
            query = query.with_for_update()
        document = await db.scalar(query)
        if document is None:
            raise knowledge_http_error(
                status.HTTP_404_NOT_FOUND,
                "knowledge_document_not_found",
                "Knowledge document not found.",
            )
        return subject, document

    async def _latest_rows(
        self, db: AsyncSession, documents: Sequence[SubjectDocument]
    ) -> tuple[
        dict[UUID, SubjectDocumentContentRevision],
        dict[UUID, SubjectDocumentIndexRevision],
        dict[UUID, SubjectDocumentIndexJob],
    ]:
        document_ids = [document.id for document in documents]
        if not document_ids:
            return {}, {}, {}
        contents = list(
            (
                await db.scalars(
                    select(SubjectDocumentContentRevision)
                    .where(SubjectDocumentContentRevision.document_id.in_(document_ids))
                    .order_by(
                        SubjectDocumentContentRevision.document_id,
                        SubjectDocumentContentRevision.revision_no.desc(),
                    )
                )
            ).all()
        )
        latest_content: dict[UUID, SubjectDocumentContentRevision] = {}
        for content in contents:
            latest_content.setdefault(content.document_id, content)
        content_ids = [content.id for content in latest_content.values()]
        indexes = list(
            (
                await db.scalars(
                    select(SubjectDocumentIndexRevision)
                    .where(SubjectDocumentIndexRevision.content_revision_id.in_(content_ids))
                    .order_by(
                        SubjectDocumentIndexRevision.content_revision_id,
                        SubjectDocumentIndexRevision.revision_no.desc(),
                    )
                )
            ).all()
        ) if content_ids else []
        latest_index: dict[UUID, SubjectDocumentIndexRevision] = {}
        for index in indexes:
            latest_index.setdefault(index.content_revision_id, index)
        index_ids = [index.id for index in latest_index.values()]
        jobs = list(
            (
                await db.scalars(
                    select(SubjectDocumentIndexJob)
                    .where(SubjectDocumentIndexJob.index_revision_id.in_(index_ids))
                    .order_by(
                        SubjectDocumentIndexJob.index_revision_id,
                        SubjectDocumentIndexJob.created_at.desc(),
                    )
                )
            ).all()
        ) if index_ids else []
        latest_job: dict[UUID, SubjectDocumentIndexJob] = {}
        for job in jobs:
            latest_job.setdefault(job.index_revision_id, job)
        return latest_content, latest_index, latest_job

    async def list_documents(
        self, db: AsyncSession, *, subject_id: UUID, user: User, limit: int
    ) -> list[KnowledgeDocumentResponse]:
        await SubjectService.check_subject_access(db, subject_id, user, require_owner=True)
        documents = list(
            (
                await db.scalars(
                    select(SubjectDocument)
                    .where(
                        SubjectDocument.subject_id == subject_id,
                        SubjectDocument.uploader_id == user.id,
                    )
                    .order_by(SubjectDocument.updated_at.desc(), SubjectDocument.id)
                    .limit(limit)
                )
            ).all()
        )
        contents, indexes, jobs = await self._latest_rows(db, documents)
        return [
            self.to_response(
                document,
                contents.get(document.id),
                indexes.get(contents[document.id].id) if document.id in contents else None,
                jobs.get(indexes[contents[document.id].id].id)
                if document.id in contents and contents[document.id].id in indexes
                else None,
            )
            for document in documents
        ]

    async def get_document_response(
        self,
        db: AsyncSession,
        *,
        subject_id: UUID,
        document_id: UUID,
        user: User,
    ) -> KnowledgeDocumentResponse:
        _subject, document = await self._owned_document(
            db, subject_id=subject_id, document_id=document_id, user=user
        )
        contents, indexes, jobs = await self._latest_rows(db, [document])
        content = contents.get(document.id)
        index = indexes.get(content.id) if content else None
        job = jobs.get(index.id) if index else None
        return self.to_response(document, content, index, job)

    async def review_and_publish(
        self,
        db: AsyncSession,
        *,
        subject_id: UUID,
        document_id: UUID,
        user: User,
    ) -> None:
        await acquire_knowledge_write_lock(db)
        subject, document = await self._owned_document(
            db,
            subject_id=subject_id,
            document_id=document_id,
            user=user,
            for_update=True,
        )
        content = await db.scalar(
            select(SubjectDocumentContentRevision)
            .where(
                SubjectDocumentContentRevision.document_id == document.id,
                SubjectDocumentContentRevision.is_active.is_(True),
                SubjectDocumentContentRevision.status == "ready",
            )
            .with_for_update()
        )
        if content is None:
            raise knowledge_http_error(
                status.HTTP_409_CONFLICT,
                "knowledge_not_ready",
                "Knowledge must finish indexing before review and publication.",
            )
        ready_index = await db.scalar(
            select(SubjectDocumentIndexRevision)
            .where(
                SubjectDocumentIndexRevision.content_revision_id == content.id,
                SubjectDocumentIndexRevision.status == "ready",
            )
            .order_by(SubjectDocumentIndexRevision.revision_no.desc())
            .limit(1)
            .with_for_update()
        )
        if ready_index is None:
            raise knowledge_http_error(
                status.HTTP_409_CONFLICT,
                "knowledge_index_not_ready",
                "Knowledge has no ready index to publish.",
            )
        if subject.active_embedding_space_hash is None:
            try:
                await cutover_subject_embedding_space(
                    db,
                    subject_id=subject.id,
                    owner_id=user.id,
                    target_space_hash=ready_index.embedding_space_hash,
                )
            except KnowledgeCutoverError as exc:
                raise knowledge_http_error(
                    status.HTTP_409_CONFLICT,
                    "knowledge_space_not_ready",
                    str(exc),
                ) from None
        elif subject.active_embedding_space_hash != ready_index.embedding_space_hash:
            raise knowledge_http_error(
                status.HTTP_409_CONFLICT,
                "knowledge_rebuild_required",
                "Rebuild this document in the active Knowledge index before publication.",
            )
        elif not ready_index.is_active:
            ready_index.is_active = True
        now = utcnow()
        was_published = content.published_at is not None
        content.reviewed_by_id = user.id
        content.reviewed_at = now
        content.published_at = now
        document.updated_at = now
        AuditService.record(
            db,
            action=AuditAction.KNOWLEDGE_PUBLISHED,
            actor_id=user.id,
            target_type="knowledge",
            target_id=document.id,
            subject_id=subject.id,
            state_before=was_published,
            state_after=True,
            affected_count=1,
        )
        await db.flush()

    async def unpublish(
        self,
        db: AsyncSession,
        *,
        subject_id: UUID,
        document_id: UUID,
        user: User,
    ) -> None:
        await acquire_knowledge_write_lock(db)
        subject, document = await self._owned_document(
            db,
            subject_id=subject_id,
            document_id=document_id,
            user=user,
            for_update=True,
        )
        content = await db.scalar(
            select(SubjectDocumentContentRevision)
            .where(
                SubjectDocumentContentRevision.document_id == document.id,
                SubjectDocumentContentRevision.is_active.is_(True),
            )
            .with_for_update()
        )
        if content is None or content.published_at is None:
            raise knowledge_http_error(
                status.HTTP_409_CONFLICT,
                "knowledge_not_published",
                "Knowledge is not currently published.",
            )
        content.published_at = None
        document.updated_at = utcnow()
        AuditService.record(
            db,
            action=AuditAction.KNOWLEDGE_UNPUBLISHED,
            actor_id=user.id,
            target_type="knowledge",
            target_id=document.id,
            subject_id=subject.id,
            state_before=True,
            state_after=False,
            affected_count=1,
        )
        await db.flush()

    async def retry_index(
        self,
        db: AsyncSession,
        *,
        subject_id: UUID,
        document_id: UUID,
        user: User,
    ) -> None:
        await acquire_knowledge_write_lock(db)
        subject, document = await self._owned_document(
            db,
            subject_id=subject_id,
            document_id=document_id,
            user=user,
            for_update=True,
        )
        content = await db.scalar(
            select(SubjectDocumentContentRevision)
            .where(SubjectDocumentContentRevision.document_id == document.id)
            .order_by(SubjectDocumentContentRevision.revision_no.desc())
            .limit(1)
            .with_for_update()
        )
        if content is None or content.status not in {"pending_index", "ready"}:
            raise knowledge_http_error(
                status.HTTP_409_CONFLICT,
                "knowledge_reupload_required",
                "The stored pages are unavailable for retry; upload a new PDF revision.",
            )
        latest_index = await db.scalar(
            select(SubjectDocumentIndexRevision)
            .where(SubjectDocumentIndexRevision.content_revision_id == content.id)
            .order_by(SubjectDocumentIndexRevision.revision_no.desc())
            .limit(1)
        )
        latest_job = (
            await db.scalar(
                select(SubjectDocumentIndexJob).where(
                    SubjectDocumentIndexJob.index_revision_id == latest_index.id
                )
            )
            if latest_index
            else None
        )
        if latest_job is None or latest_job.status not in {"failed", "cancelled"}:
            raise knowledge_http_error(
                status.HTTP_409_CONFLICT,
                "knowledge_index_not_retryable",
                "This Knowledge index is not in a retryable state.",
            )
        target = await ensure_embedding_space(db, self.settings)
        try:
            created = await enqueue_content_index(
                db, content=content, subject=subject, target=target, settings=self.settings
            )
        except KnowledgeCutoverError as exc:
            raise knowledge_http_error(
                status.HTTP_409_CONFLICT,
                "knowledge_rebuild_failed",
                str(exc),
            ) from None
        if created is None:
            raise knowledge_http_error(
                status.HTTP_409_CONFLICT,
                "knowledge_index_already_pending",
                "A compatible Knowledge index already exists or is in progress.",
            )
        document.updated_at = utcnow()

    async def remove(
        self,
        db: AsyncSession,
        *,
        subject_id: UUID,
        document_id: UUID,
        user: User,
    ) -> None:
        await acquire_knowledge_write_lock(db)
        subject, document = await self._owned_document(
            db,
            subject_id=subject_id,
            document_id=document_id,
            user=user,
            for_update=True,
        )
        generation_jobs = list(
            (
                await db.scalars(
                    select(GenerationJob)
                    .where(GenerationJob.document_id == document.id)
                    .order_by(GenerationJob.id)
                    .with_for_update()
                )
            ).all()
        )
        index_jobs = list(
            (
                await db.scalars(
                    select(SubjectDocumentIndexJob)
                    .where(SubjectDocumentIndexJob.document_id == document.id)
                    .order_by(SubjectDocumentIndexJob.id)
                    .with_for_update()
                )
            ).all()
        )
        running_answer_jobs = list(
            (
                await db.scalars(
                    select(RagAnswerJob)
                    .where(
                        RagAnswerJob.subject_id == subject.id,
                        RagAnswerJob.status == "running",
                    )
                    .order_by(RagAnswerJob.id)
                    .with_for_update()
                )
            ).all()
        )
        document_key = str(document.id)
        if (
            any(job.status == "running" for job in generation_jobs)
            or any(job.status == "running" for job in index_jobs)
            or any(document_key in job.document_ids for job in running_answer_jobs)
        ):
            raise knowledge_http_error(
                status.HTTP_409_CONFLICT,
                "knowledge_work_active",
                "Stop or cancel active work for this Knowledge document before removal.",
            )
        await db.execute(delete(SubjectDocument).where(SubjectDocument.id == document.id))
        AuditService.record(
            db,
            action=AuditAction.KNOWLEDGE_REMOVED,
            actor_id=user.id,
            target_type="knowledge",
            target_id=document.id,
            subject_id=subject.id,
            affected_count=1,
        )
        await db.flush()

    @staticmethod
    def to_response(
        document: SubjectDocument,
        content: SubjectDocumentContentRevision | None,
        index: SubjectDocumentIndexRevision | None,
        job: SubjectDocumentIndexJob | None,
    ) -> KnowledgeDocumentResponse:
        content_response = (
            KnowledgeContentRevisionResponse(
                id=content.id,
                revision_no=content.revision_no,
                status=content.status,
                is_active=content.is_active,
                page_count=content.actual_page_count,
                reviewed_at=content.reviewed_at,
                published_at=content.published_at,
                error_code=content.error_code,
                error_message=content.error_message,
            )
            if content
            else None
        )
        index_response = (
            KnowledgeIndexRevisionResponse(
                id=index.id,
                revision_no=index.revision_no,
                status=index.status,
                is_active=index.is_active,
                chunk_count=index.actual_chunk_count,
                embedded_count=index.actual_embedded_count,
                embedding_model=index.embedding_model,
                embedding_space_revision=index.embedding_space_revision,
                error_code=index.error_code,
                error_message=index.error_message,
            )
            if index
            else None
        )
        job_response = (
            KnowledgeIndexJobResponse(
                id=job.id,
                status=job.status,
                attempt_count=job.attempt_count,
                max_attempts=job.max_attempts,
                error_code=job.error_code,
                error_message=job.error_message,
                created_at=job.created_at,
                completed_at=job.completed_at,
            )
            if job
            else None
        )
        ready = bool(content and content.status == "ready" and index and index.status == "ready")
        retryable = bool(job and job.status in {"failed", "cancelled"} and content and content.status in {"pending_index", "ready"})
        return KnowledgeDocumentResponse(
            id=document.id,
            subject_id=document.subject_id,
            title=document.title,
            source_pdf_name=document.source_pdf_name,
            created_at=document.created_at,
            updated_at=document.updated_at,
            content_revision=content_response,
            index_revision=index_response,
            index_job=job_response,
            can_review_publish=ready and content.published_at is None,
            can_unpublish=bool(content and content.published_at is not None),
            can_retry_index=retryable,
            can_rebuild_from_pages=bool(content and content.actual_page_count > 0),
            requires_pdf_reupload=not bool(content and content.actual_page_count > 0),
        )


__all__ = ["KnowledgeManagementService", "knowledge_http_error"]
