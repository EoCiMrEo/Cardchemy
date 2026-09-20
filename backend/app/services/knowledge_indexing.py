"""Reindex staging and all-or-nothing embedding-space cutover operations."""

from __future__ import annotations

import hashlib
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chunking import prepare_document
from app.ai.contracts import ExtractedDocument, ExtractedPage
from app.config import Settings
from app.models.knowledge import (
    RagEmbeddingSpace,
    SubjectDocumentChunk,
    SubjectDocumentContentRevision,
    SubjectDocumentIndexJob,
    SubjectDocumentIndexRevision,
    SubjectDocumentPage,
    embedding_space_hash,
)
from app.services.knowledge_capture import (
    CHUNKER_VERSION,
    KnowledgeCaptureFailure,
    validate_capture_bounds,
)
from app.models.subject import Subject
from app.services.knowledge_lock import acquire_knowledge_write_lock
from app.observability import current_request_id
from app.time_utils import utcnow


class KnowledgeCutoverError(RuntimeError):
    pass


def _hash(*parts: object) -> str:
    framed = "".join(f"{len(str(part).encode('utf-8'))}:{part}" for part in parts)
    return hashlib.sha256(framed.encode("utf-8")).hexdigest()


async def ensure_embedding_space(db: AsyncSession, settings: Settings) -> RagEmbeddingSpace:
    identity = settings.rag_embedding_space_identity
    identity_hash = embedding_space_hash(identity)
    space = await db.get(RagEmbeddingSpace, identity_hash)
    if space is None:
        space = RagEmbeddingSpace(
            identity_hash=identity_hash,
            provider=identity[0],
            base_url=identity[1],
            model=identity[2],
            space_revision=identity[3],
            format_version=identity[4],
            dimensions=identity[5],
            representation=identity[6],
            metric=identity[7],
            document_task_mode=identity[8],
            query_task_mode=identity[9],
            created_at=utcnow(),
        )
        db.add(space)
        await db.flush()
    return space


async def enqueue_content_index(
    db: AsyncSession,
    *,
    content: SubjectDocumentContentRevision,
    subject: Subject,
    target: RagEmbeddingSpace,
    settings: Settings,
) -> SubjectDocumentIndexJob | None:
    """Stage one missing index from canonical pages.

    This is shared by whole-Subject reindexing and the instructor-facing retry
    path for an initial failed index.  It deliberately creates a fresh revision
    and job because terminal jobs and their snapshots are immutable.
    """

    existing = await db.scalar(
        select(SubjectDocumentIndexRevision.id).where(
            SubjectDocumentIndexRevision.content_revision_id == content.id,
            SubjectDocumentIndexRevision.embedding_space_hash == target.identity_hash,
            SubjectDocumentIndexRevision.status.in_(("pending_index", "indexing", "ready")),
        )
    )
    if existing is not None:
        return None
    source_revision = await db.scalar(
        select(SubjectDocumentIndexRevision)
        .where(SubjectDocumentIndexRevision.content_revision_id == content.id)
        .order_by(SubjectDocumentIndexRevision.revision_no.desc())
        .limit(1)
    )
    if source_revision is None:
        raise KnowledgeCutoverError("The content revision has no chunk snapshot.")
    if source_revision.chunker_version != CHUNKER_VERSION:
        raise KnowledgeCutoverError("The stored content requires a reviewed chunker migration.")
    pages = list(
        (
            await db.scalars(
                select(SubjectDocumentPage)
                .where(SubjectDocumentPage.content_revision_id == content.id)
                .order_by(SubjectDocumentPage.page_number)
            )
        ).all()
    )
    if not pages:
        raise KnowledgeCutoverError("The content revision has no canonical pages.")
    try:
        prepared = prepare_document(
            ExtractedDocument(
                pages=[
                    ExtractedPage(page_number=page.page_number, text=page.content)
                    for page in pages
                ]
            ),
            max_tokens=settings.flashcard_ai_chunk_input_tokens,
            overlap_tokens=settings.flashcard_ai_chunk_overlap_tokens,
        )
        validate_capture_bounds(prepared)
    except (ValueError, KnowledgeCaptureFailure) as exc:
        raise KnowledgeCutoverError(
            "The canonical pages cannot be rebuilt within current Knowledge bounds."
        ) from exc
    target_chunks = prepared.chunks
    next_revision = int(
        await db.scalar(
            select(func.coalesce(func.max(SubjectDocumentIndexRevision.revision_no), 0)).where(
                SubjectDocumentIndexRevision.content_revision_id == content.id
            )
        )
        or 0
    ) + 1
    reserved_bytes = sum(
        len(chunk.text.encode("utf-8"))
        + len((chunk.section or "").encode("utf-8"))
        + 6_408
        for chunk in target_chunks
    )
    now = utcnow()
    revision = SubjectDocumentIndexRevision(
        content_revision_id=content.id,
        document_id=content.document_id,
        subject_id=content.subject_id,
        uploader_id=content.uploader_id,
        revision_no=next_revision,
        chunker_version=CHUNKER_VERSION,
        embedding_provider=target.provider,
        embedding_base_url=target.base_url,
        embedding_model=target.model,
        embedding_space_revision=target.space_revision,
        embedding_format_version=target.format_version,
        embedding_dimensions=target.dimensions,
        embedding_representation=target.representation,
        embedding_metric=target.metric,
        document_task_mode=target.document_task_mode,
        query_task_mode=target.query_task_mode,
        embedding_space_hash=target.identity_hash,
        status="pending_index",
        is_active=False,
        reserved_chunk_count=len(target_chunks),
        reserved_index_bytes=reserved_bytes,
        created_at=now,
        updated_at=now,
    )
    db.add(revision)
    await db.flush()
    db.add_all(
        [
            SubjectDocumentChunk(
                index_revision_id=revision.id,
                content_revision_id=content.id,
                document_id=content.document_id,
                subject_id=content.subject_id,
                uploader_id=content.uploader_id,
                chunk_index=index,
                local_chunk_id=chunk.chunk_id,
                page_number=chunk.page_number,
                section=chunk.section,
                content=chunk.text,
                token_count=chunk.token_count,
                embedding_space_hash=target.identity_hash,
                embedding=None,
            )
            for index, chunk in enumerate(target_chunks)
        ]
    )
    await db.flush()
    operation_key = _hash("reindex", content.subject_id, content.id, target.identity_hash, revision.id)
    job = SubjectDocumentIndexJob(
        index_revision_id=revision.id,
        content_revision_id=content.id,
        document_id=content.document_id,
        subject_id=content.subject_id,
        uploader_id=content.uploader_id,
        request_id=current_request_id(),
        status="queued",
        operation_key_hash=operation_key,
        request_fingerprint=_hash(
            content.source_sha256, target.identity_hash, revision.chunker_version
        ),
        corpus_revision=subject.corpus_revision,
        attempt_count=0,
        max_attempts=settings.rag_index_max_attempts,
        available_at=now,
        deadline_at=now + timedelta(seconds=settings.rag_index_job_timeout_seconds),
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    await db.flush()
    return job


async def enqueue_subject_reindex(
    db: AsyncSession,
    *,
    subject_id: UUID,
    owner_id: UUID,
    settings: Settings,
) -> int:
    """Stage missing compatible indexes without changing the active corpus."""

    await acquire_knowledge_write_lock(db)
    subject = await db.scalar(
        select(Subject)
        .where(Subject.id == subject_id, Subject.instructor_id == owner_id)
        .with_for_update()
    )
    if subject is None:
        raise KnowledgeCutoverError("Subject is unavailable.")
    target = await ensure_embedding_space(db, settings)
    subject.staged_embedding_space_hash = target.identity_hash
    # The PostgreSQL subject guard advances corpus_revision when the staged
    # embedding space changes.  Flush and refresh that server-maintained value
    # before snapshotting it into immutable index jobs; otherwise the first job
    # for a new space can carry the pre-trigger revision and be rejected by the
    # index-job guard.
    await db.flush()
    await db.refresh(subject, attribute_names=["corpus_revision"])
    contents = list((await db.scalars(
        select(SubjectDocumentContentRevision)
        .where(
            SubjectDocumentContentRevision.subject_id == subject_id,
            SubjectDocumentContentRevision.is_active.is_(True),
            SubjectDocumentContentRevision.status == "ready",
        )
        .order_by(SubjectDocumentContentRevision.document_id, SubjectDocumentContentRevision.id)
        .with_for_update()
    )).all())
    created = 0
    for content in contents:
        if await enqueue_content_index(
            db, content=content, subject=subject, target=target, settings=settings
        ) is not None:
            created += 1
    return created


async def cutover_subject_embedding_space(
    db: AsyncSession,
    *,
    subject_id: UUID,
    owner_id: UUID,
    target_space_hash: str,
) -> int:
    """Switch only when every active ready revision has a ready target index."""

    await acquire_knowledge_write_lock(db)
    subject = await db.scalar(
        select(Subject)
        .where(Subject.id == subject_id, Subject.instructor_id == owner_id)
        .with_for_update()
    )
    if subject is None or await db.get(RagEmbeddingSpace, target_space_hash) is None:
        raise KnowledgeCutoverError("Subject or embedding space is unavailable.")
    contents = list((await db.scalars(
        select(SubjectDocumentContentRevision)
        .where(
            SubjectDocumentContentRevision.subject_id == subject_id,
            SubjectDocumentContentRevision.is_active.is_(True),
            SubjectDocumentContentRevision.status == "ready",
        )
        .order_by(SubjectDocumentContentRevision.document_id, SubjectDocumentContentRevision.id)
        .with_for_update()
    )).all())
    targets: list[SubjectDocumentIndexRevision] = []
    for content in contents:
        target = await db.scalar(
            select(SubjectDocumentIndexRevision)
            .where(
                SubjectDocumentIndexRevision.content_revision_id == content.id,
                SubjectDocumentIndexRevision.embedding_space_hash == target_space_hash,
                SubjectDocumentIndexRevision.status == "ready",
            )
            .order_by(SubjectDocumentIndexRevision.revision_no.desc())
            .limit(1)
            .with_for_update()
        )
        if target is None:
            raise KnowledgeCutoverError(
                "Cutover is blocked until every active content revision has a ready compatible index."
            )
        targets.append(target)
    # Empty Subjects may still record an explicit compatible active space.
    active_indexes = list((await db.scalars(
        select(SubjectDocumentIndexRevision)
        .where(
            SubjectDocumentIndexRevision.subject_id == subject_id,
            SubjectDocumentIndexRevision.is_active.is_(True),
        )
        .with_for_update()
    )).all())
    for revision in active_indexes:
        revision.is_active = False
    await db.flush()
    for target in targets:
        target.is_active = True
    subject.active_embedding_space_hash = target_space_hash
    subject.staged_embedding_space_hash = None
    await db.flush()
    return len(targets)
