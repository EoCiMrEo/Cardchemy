"""Atomic private Knowledge capture from one bounded PDF preparation result."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.chunking import PreparedDocument
from app.config import Settings
from app.models.generation import GenerationJob
from app.models.knowledge import (
    RagEmbeddingSpace,
    SubjectDocument,
    SubjectDocumentChunk,
    SubjectDocumentContentRevision,
    SubjectDocumentIndexJob,
    SubjectDocumentIndexRevision,
    SubjectDocumentPage,
    embedding_space_hash,
)
from app.models.subject import Subject
from app.services.knowledge_lock import acquire_knowledge_write_lock
from app.time_utils import as_utc, utcnow


EXTRACTION_VERSION = "pypdf_bounded_v1"
CHUNKER_VERSION = "bounded_v1"
MAX_CAPTURE_PAGES = 100
MAX_CAPTURE_PAGE_CHARS = 500_000
MAX_CAPTURE_PAGE_BYTES = 2_097_152
MAX_CAPTURE_CHUNKS = 512
MAX_CAPTURE_INDEX_BYTES = 16_777_216


class KnowledgeCaptureFailure(RuntimeError):
    """A safe, independent capture failure that need not fail flashcards."""

    def __init__(self, code: str, safe_message: str):
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


class KnowledgeCaptureUnsafeFailure(RuntimeError):
    """A claim/ownership/cancellation failure that aborts the whole job."""


@dataclass(frozen=True)
class KnowledgeCaptureResult:
    document_id: UUID
    content_revision_id: UUID
    index_revision_id: UUID
    index_job_id: UUID


def _hash(*parts: object) -> str:
    framed = "".join(
        f"{len(str(part).encode('utf-8'))}:{part}" for part in parts
    )
    return hashlib.sha256(framed.encode("utf-8")).hexdigest()


def validate_capture_bounds(prepared: PreparedDocument) -> tuple[int, int, int]:
    pages = prepared.document.pages
    page_chars = sum(len(page.text) for page in pages)
    page_bytes = sum(len(page.text.encode("utf-8")) for page in pages)
    index_bytes = sum(
        len(chunk.text.encode("utf-8"))
        + len((chunk.section or "").encode("utf-8"))
        + 6_408
        for chunk in prepared.chunks
    )
    if (
        not prepared.chunks
        or len(pages) > MAX_CAPTURE_PAGES
        or page_chars > MAX_CAPTURE_PAGE_CHARS
        or page_bytes > MAX_CAPTURE_PAGE_BYTES
        or len(prepared.chunks) > MAX_CAPTURE_CHUNKS
        or any(chunk.token_count > 8_192 for chunk in prepared.chunks)
        or index_bytes > MAX_CAPTURE_INDEX_BYTES
    ):
        raise KnowledgeCaptureFailure(
            "knowledge_capture_unsupported",
            "The document exceeds the supported Knowledge capture bounds.",
        )
    return page_chars, page_bytes, index_bytes


async def capture_prepared_document(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    settings: Settings,
    job_id: UUID,
    worker_id: str,
    claim_token: str,
    prepared: PreparedDocument,
) -> KnowledgeCaptureResult:
    """Persist pages/chunks and enqueue indexing in one short transaction."""

    page_chars, page_bytes, index_bytes = validate_capture_bounds(prepared)
    now = utcnow()
    space_identity = settings.rag_embedding_space_identity
    space_hash = embedding_space_hash(space_identity)

    async with session_factory() as db:
        async with db.begin():
            await acquire_knowledge_write_lock(db)
            job = await db.scalar(
                select(GenerationJob)
                .where(GenerationJob.id == job_id)
                .with_for_update()
            )
            if job is None or job.worker_id != worker_id or job.claim_token != claim_token:
                raise KnowledgeCaptureUnsafeFailure("Generation claim was lost.")
            if job.status != "running" or job.cancellation_requested_at is not None:
                raise KnowledgeCaptureUnsafeFailure("Knowledge capture was cancelled.")
            if job.lease_expires_at is None or as_utc(job.lease_expires_at) <= now:
                raise KnowledgeCaptureUnsafeFailure("Generation lease expired.")
            if job.knowledge_capture_status == "captured":
                if job.document_id is None or job.knowledge_content_revision_id is None:
                    raise KnowledgeCaptureUnsafeFailure("Captured Knowledge association is invalid.")
                index_revision = await db.scalar(
                    select(SubjectDocumentIndexRevision)
                    .where(
                        SubjectDocumentIndexRevision.content_revision_id
                        == job.knowledge_content_revision_id
                    )
                    .order_by(SubjectDocumentIndexRevision.revision_no.desc())
                )
                index_job = await db.scalar(
                    select(SubjectDocumentIndexJob).where(
                        SubjectDocumentIndexJob.index_revision_id == index_revision.id
                    )
                ) if index_revision else None
                if index_revision is None or index_job is None:
                    raise KnowledgeCaptureUnsafeFailure("Captured Knowledge queue is invalid.")
                return KnowledgeCaptureResult(
                    job.document_id,
                    job.knowledge_content_revision_id,
                    index_revision.id,
                    index_job.id,
                )
            if job.knowledge_capture_status not in {"pending", "not_requested"}:
                raise KnowledgeCaptureUnsafeFailure("Knowledge capture is not writable.")

            subject = await db.scalar(
                select(Subject)
                .where(Subject.id == job.subject_id, Subject.instructor_id == job.user_id)
                .with_for_update()
            )
            if subject is None:
                raise KnowledgeCaptureUnsafeFailure("Knowledge ownership was lost.")

            space = await db.get(RagEmbeddingSpace, space_hash)
            if space is None:
                space = RagEmbeddingSpace(
                    identity_hash=space_hash,
                    provider=space_identity[0],
                    base_url=space_identity[1],
                    model=space_identity[2],
                    space_revision=space_identity[3],
                    format_version=space_identity[4],
                    dimensions=space_identity[5],
                    representation=space_identity[6],
                    metric=space_identity[7],
                    document_task_mode=space_identity[8],
                    query_task_mode=space_identity[9],
                    created_at=now,
                )
                db.add(space)

            document = None
            if job.document_id is not None:
                document = await db.scalar(
                    select(SubjectDocument)
                    .where(
                        SubjectDocument.id == job.document_id,
                        SubjectDocument.subject_id == job.subject_id,
                        SubjectDocument.uploader_id == job.user_id,
                    )
                    .with_for_update()
                )
                if document is None:
                    raise KnowledgeCaptureUnsafeFailure("Knowledge target is unavailable.")
            if document is None:
                document = SubjectDocument(
                    subject_id=job.subject_id,
                    uploader_id=job.user_id,
                    title=job.set_title,
                    source_pdf_name=job.source_pdf_name,
                    source_sha256=job.source_sha256,
                    created_at=now,
                    updated_at=now,
                )
                db.add(document)
                await db.flush()
                job.document_id = document.id
                job.knowledge_created_document = True
            else:
                document.title = job.set_title
                document.updated_at = now

            revision_no = int(
                await db.scalar(
                    select(func.coalesce(func.max(SubjectDocumentContentRevision.revision_no), 0))
                    .where(SubjectDocumentContentRevision.document_id == document.id)
                )
                or 0
            ) + 1
            content_revision = SubjectDocumentContentRevision(
                document_id=document.id,
                subject_id=job.subject_id,
                uploader_id=job.user_id,
                revision_no=revision_no,
                source_sha256=job.source_sha256,
                extraction_version=EXTRACTION_VERSION,
                status="processing",
                is_active=False,
                reserved_page_count=len(prepared.document.pages),
                reserved_page_chars=page_chars,
                reserved_page_bytes=page_bytes,
                created_at=now,
                updated_at=now,
            )
            db.add(content_revision)
            await db.flush()
            db.add_all(
                [
                    SubjectDocumentPage(
                        content_revision_id=content_revision.id,
                        document_id=document.id,
                        subject_id=job.subject_id,
                        uploader_id=job.user_id,
                        page_number=page.page_number,
                        content=page.text,
                    )
                    for page in prepared.document.pages
                ]
            )
            await db.flush()
            content_revision.status = "pending_index"

            index_revision = SubjectDocumentIndexRevision(
                content_revision_id=content_revision.id,
                document_id=document.id,
                subject_id=job.subject_id,
                uploader_id=job.user_id,
                revision_no=1,
                chunker_version=CHUNKER_VERSION,
                embedding_provider=space.provider,
                embedding_base_url=space.base_url,
                embedding_model=space.model,
                embedding_space_revision=space.space_revision,
                embedding_format_version=space.format_version,
                embedding_dimensions=space.dimensions,
                embedding_representation=space.representation,
                embedding_metric=space.metric,
                document_task_mode=space.document_task_mode,
                query_task_mode=space.query_task_mode,
                embedding_space_hash=space.identity_hash,
                status="pending_index",
                is_active=False,
                reserved_chunk_count=len(prepared.chunks),
                reserved_index_bytes=index_bytes,
                created_at=now,
                updated_at=now,
            )
            db.add(index_revision)
            await db.flush()
            db.add_all(
                [
                    SubjectDocumentChunk(
                        index_revision_id=index_revision.id,
                        content_revision_id=content_revision.id,
                        document_id=document.id,
                        subject_id=job.subject_id,
                        uploader_id=job.user_id,
                        chunk_index=index,
                        local_chunk_id=chunk.chunk_id,
                        page_number=chunk.page_number,
                        section=chunk.section,
                        content=chunk.text,
                        token_count=chunk.token_count,
                        embedding_space_hash=space.identity_hash,
                        embedding=None,
                    )
                    for index, chunk in enumerate(prepared.chunks)
                ]
            )
            await db.flush()

            operation_key = _hash("knowledge-index", job.id, content_revision.id, space_hash)
            fingerprint = _hash(
                job.subject_id,
                document.id,
                content_revision.id,
                job.source_sha256,
                space_hash,
                CHUNKER_VERSION,
            )
            index_job = SubjectDocumentIndexJob(
                index_revision_id=index_revision.id,
                content_revision_id=content_revision.id,
                document_id=document.id,
                subject_id=job.subject_id,
                uploader_id=job.user_id,
                request_id=job.request_id,
                status="queued",
                operation_key_hash=operation_key,
                request_fingerprint=fingerprint,
                corpus_revision=subject.corpus_revision,
                attempt_count=0,
                max_attempts=settings.rag_index_max_attempts,
                available_at=now,
                deadline_at=now + timedelta(seconds=settings.rag_index_job_timeout_seconds),
                created_at=now,
                updated_at=now,
            )
            db.add(index_job)
            job.knowledge_content_revision_id = content_revision.id
            job.knowledge_capture_status = "captured"
            job.knowledge_capture_started_at = job.knowledge_capture_started_at or now
            job.knowledge_capture_completed_at = now
            job.knowledge_capture_error_code = None
            job.knowledge_capture_error_message = None
            job.updated_at = now
            await db.flush()
            return KnowledgeCaptureResult(
                document.id, content_revision.id, index_revision.id, index_job.id
            )


async def record_capture_failure(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    job_id: UUID,
    worker_id: str,
    claim_token: str,
    code: str,
    message: str,
) -> None:
    async with session_factory() as db:
        async with db.begin():
            job = await db.scalar(
                select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
            )
            if (
                job is None
                or job.worker_id != worker_id
                or job.claim_token != claim_token
                or job.status != "running"
            ):
                raise KnowledgeCaptureUnsafeFailure("Generation claim was lost.")
            now = utcnow()
            job.knowledge_capture_status = "failed"
            job.knowledge_capture_started_at = job.knowledge_capture_started_at or now
            job.knowledge_capture_completed_at = now
            job.knowledge_capture_error_code = code
            job.knowledge_capture_error_message = message
            job.updated_at = now


async def remove_captured_knowledge(db: AsyncSession, job: GenerationJob) -> None:
    """Delete only the revision created by this job, or its new document."""

    await acquire_knowledge_write_lock(db)
    if job.knowledge_created_document and job.document_id is not None:
        document = await db.get(SubjectDocument, job.document_id)
        if document is not None:
            await db.delete(document)
    elif job.knowledge_content_revision_id is not None:
        revision = await db.get(
            SubjectDocumentContentRevision, job.knowledge_content_revision_id
        )
        if revision is not None:
            await db.delete(revision)
    job.document_id = None
    job.knowledge_content_revision_id = None
    job.knowledge_capture_removed = True
    job.knowledge_capture_status = "removed"
    job.knowledge_capture_completed_at = job.knowledge_capture_completed_at or utcnow()
    job.knowledge_capture_error_code = None
    job.knowledge_capture_error_message = None
