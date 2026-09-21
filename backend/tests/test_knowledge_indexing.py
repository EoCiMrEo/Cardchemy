import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.config import Settings
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
from app.models.user import User, UserRole
from app.services.knowledge_indexing import (
    KnowledgeCutoverError,
    cutover_subject_embedding_space,
    enqueue_subject_reindex,
)
from app.workers.knowledge_index import KnowledgeIndexWorker


async def test_index_worker_disabled_lifecycle_needs_no_provider_credentials(
    monkeypatch,
):
    stop = asyncio.Event()
    worker = KnowledgeIndexWorker(
        settings=Settings(_env_file=None, environment="test", rag_enabled=False),
        worker_id="disabled-index-worker",
    )
    statuses = []

    async def pulse(status):
        statuses.append(status)
        if status == "disabled":
            stop.set()

    monkeypatch.setattr(worker, "_pulse", pulse)
    await worker.run(stop)
    assert statuses == ["disabled", "draining"]


def space(revision: str) -> RagEmbeddingSpace:
    identity = (
        "openai_compatible", "https://api.openai.com/v1",
        "text-embedding-3-small", revision, "raw_text_v1", 1536,
        "float32", "cosine",
    )
    return RagEmbeddingSpace(
        identity_hash=embedding_space_hash(identity),
        provider=identity[0], base_url=identity[1], model=identity[2],
        space_revision=identity[3], format_version=identity[4],
        dimensions=identity[5], representation=identity[6], metric=identity[7],
    )


async def seed_cutover(db):
    owner = User(
        id=uuid4(), email=f"cutover-{uuid4().hex}@example.test",
        hashed_password="fixture", role=UserRole.INSTRUCTOR,
    )
    old, target = space("old"), space("target")
    subject = Subject(
        id=uuid4(), name="Cutover", instructor_id=owner.id,
        active_embedding_space_hash=old.identity_hash,
    )
    db.add_all([owner, old, target, subject])
    await db.flush()
    contents = []
    target_indexes = []
    for index in range(2):
        document = SubjectDocument(
            subject_id=subject.id, uploader_id=owner.id, title=f"Document {index}",
            source_pdf_name=f"{index}.pdf", source_sha256=f"{index + 1:064x}",
        )
        db.add(document)
        await db.flush()
        content = SubjectDocumentContentRevision(
            document_id=document.id, subject_id=subject.id, uploader_id=owner.id,
            revision_no=1, source_sha256=document.source_sha256,
            extraction_version="pypdf_bounded_v1", status="ready", is_active=True,
            reserved_page_count=1, reserved_page_chars=0, reserved_page_bytes=0,
            actual_page_count=1, actual_page_chars=0, actual_page_bytes=0,
        )
        db.add(content)
        await db.flush()
        old_index = SubjectDocumentIndexRevision(
            content_revision_id=content.id, document_id=document.id,
            subject_id=subject.id, uploader_id=owner.id, revision_no=1,
            chunker_version="bounded_v1", embedding_provider=old.provider,
            embedding_base_url=old.base_url, embedding_model=old.model,
            embedding_space_revision=old.space_revision,
            embedding_format_version=old.format_version,
            embedding_dimensions=old.dimensions,
            embedding_representation=old.representation,
            embedding_metric=old.metric, embedding_space_hash=old.identity_hash,
            status="ready", is_active=True, reserved_chunk_count=1,
            reserved_index_bytes=6408, actual_chunk_count=1,
            actual_embedded_count=1, actual_index_bytes=6408,
        )
        target_index = SubjectDocumentIndexRevision(
            content_revision_id=content.id, document_id=document.id,
            subject_id=subject.id, uploader_id=owner.id, revision_no=2,
            chunker_version="bounded_v1", embedding_provider=target.provider,
            embedding_base_url=target.base_url, embedding_model=target.model,
            embedding_space_revision=target.space_revision,
            embedding_format_version=target.format_version,
            embedding_dimensions=target.dimensions,
            embedding_representation=target.representation,
            embedding_metric=target.metric, embedding_space_hash=target.identity_hash,
            status="ready" if index == 0 else "pending_index", is_active=False,
            reserved_chunk_count=1, reserved_index_bytes=6408,
            actual_chunk_count=1, actual_embedded_count=1 if index == 0 else 0,
            actual_index_bytes=6408,
        )
        db.add_all([old_index, target_index])
        await db.flush()
        contents.append(content)
        target_indexes.append(target_index)
    return owner, subject, old, target, contents, target_indexes


async def test_cutover_failure_preserves_old_corpus_then_switches_atomically(db):
    owner, subject, old, target, _contents, targets = await seed_cutover(db)
    with pytest.raises(KnowledgeCutoverError, match="every active"):
        await cutover_subject_embedding_space(
            db, subject_id=subject.id, owner_id=owner.id,
            target_space_hash=target.identity_hash,
        )
    assert subject.active_embedding_space_hash == old.identity_hash
    active_before = list((await db.scalars(select(SubjectDocumentIndexRevision).where(
        SubjectDocumentIndexRevision.is_active.is_(True)
    ))).all())
    assert len(active_before) == 2

    targets[1].status = "ready"
    targets[1].actual_embedded_count = 1
    await db.flush()
    count = await cutover_subject_embedding_space(
        db, subject_id=subject.id, owner_id=owner.id,
        target_space_hash=target.identity_hash,
    )
    assert count == 2
    assert subject.active_embedding_space_hash == target.identity_hash
    active_after = list((await db.scalars(select(SubjectDocumentIndexRevision).where(
        SubjectDocumentIndexRevision.is_active.is_(True)
    ))).all())
    assert {revision.id for revision in active_after} == {revision.id for revision in targets}


async def test_reindex_rebuilds_chunks_from_canonical_pages_without_pdf(db):
    owner = User(
        id=uuid4(), email=f"reindex-{uuid4().hex}@example.test",
        hashed_password="fixture", role=UserRole.INSTRUCTOR,
    )
    old = space("old")
    subject = Subject(
        id=uuid4(), name="Canonical rebuild", instructor_id=owner.id,
        active_embedding_space_hash=old.identity_hash,
    )
    db.add_all([owner, old, subject])
    await db.flush()
    document = SubjectDocument(
        subject_id=subject.id, uploader_id=owner.id, title="Lecture",
        source_pdf_name="lecture.pdf", source_sha256="a" * 64,
    )
    db.add(document)
    await db.flush()
    page_text = "Canonical page content supports a PDF-free reindex rebuild."
    content = SubjectDocumentContentRevision(
        document_id=document.id, subject_id=subject.id, uploader_id=owner.id,
        revision_no=1, source_sha256=document.source_sha256,
        extraction_version="pypdf_bounded_v1", status="ready", is_active=True,
        reserved_page_count=1, reserved_page_chars=len(page_text),
        reserved_page_bytes=len(page_text.encode("utf-8")), actual_page_count=1,
        actual_page_chars=len(page_text), actual_page_bytes=len(page_text.encode("utf-8")),
    )
    db.add(content)
    await db.flush()
    db.add(SubjectDocumentPage(
        content_revision_id=content.id, document_id=document.id,
        subject_id=subject.id, uploader_id=owner.id, page_number=1,
        content=page_text,
    ))
    old_index = SubjectDocumentIndexRevision(
        content_revision_id=content.id, document_id=document.id,
        subject_id=subject.id, uploader_id=owner.id, revision_no=1,
        chunker_version="bounded_v1", embedding_provider=old.provider,
        embedding_base_url=old.base_url, embedding_model=old.model,
        embedding_space_revision=old.space_revision,
        embedding_format_version=old.format_version,
        embedding_dimensions=old.dimensions,
        embedding_representation=old.representation,
        embedding_metric=old.metric, embedding_space_hash=old.identity_hash,
        status="ready", is_active=True, reserved_chunk_count=1,
        reserved_index_bytes=6416, actual_chunk_count=1,
        actual_embedded_count=1, actual_index_bytes=6416,
    )
    db.add(old_index)
    await db.flush()
    db.add(SubjectDocumentChunk(
        index_revision_id=old_index.id, content_revision_id=content.id,
        document_id=document.id, subject_id=subject.id, uploader_id=owner.id,
        chunk_index=0, local_chunk_id="chunk-0001-p1", page_number=1,
        section=None, content="Stale chunk snapshot must not be copied.",
        token_count=10, embedding_space_hash=old.identity_hash, embedding=None,
    ))
    await db.flush()

    settings = Settings(
        _env_file=None, environment="test", rag_embedding_space_revision="target",
        flashcard_ai_chunk_input_tokens=128, flashcard_ai_chunk_overlap_tokens=0,
    )
    assert await enqueue_subject_reindex(
        db, subject_id=subject.id, owner_id=owner.id, settings=settings,
    ) == 1
    target_hash = embedding_space_hash(settings.rag_embedding_space_identity)
    target = await db.scalar(select(SubjectDocumentIndexRevision).where(
        SubjectDocumentIndexRevision.embedding_space_hash == target_hash
    ))
    rebuilt = list((await db.scalars(select(SubjectDocumentChunk).where(
        SubjectDocumentChunk.index_revision_id == target.id
    ).order_by(SubjectDocumentChunk.chunk_index))).all())
    assert [chunk.content for chunk in rebuilt] == [page_text]
    assert await db.scalar(select(SubjectDocumentIndexJob.id).where(
        SubjectDocumentIndexJob.index_revision_id == target.id
    )) is not None
