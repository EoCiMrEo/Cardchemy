from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.config import Settings
from app.models.audit import AuditAction, AuditEvent
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
from app.services.knowledge_management import KnowledgeManagementService
from app.services.privacy import PrivacyOperationError, delete_account
from app.services.subject import SubjectService
from app.time_utils import as_utc, utcnow


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url="sqlite+aiosqlite:///:memory:",
        secret_key="test-only-secret-key-with-adequate-entropy-1234567890",
        generation_source_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        rag_enabled=True,
        rag_embedding_provider_enabled=True,
        rag_embedding_provider="openai_compatible",
        rag_embedding_base_url="https://api.openai.com/v1",
        rag_embedding_model="text-embedding-3-small",
        rag_embedding_api_key="test-key",
        rag_embedding_quota_bucket="test-bucket",
    )


async def _seed_document(db, *, failed: bool = False):
    settings = _settings()
    owner = User(
        id=uuid4(),
        email=f"owner-{uuid4().hex}@example.test",
        hashed_password="not-real",
        role=UserRole.INSTRUCTOR,
    )
    space_hash = embedding_space_hash(settings.rag_embedding_space_identity)
    space = RagEmbeddingSpace(
        identity_hash=space_hash,
        provider=settings.rag_embedding_provider,
        base_url=str(settings.rag_embedding_base_url).rstrip("/"),
        model=settings.rag_embedding_model,
        space_revision=settings.rag_embedding_space_revision,
        format_version=settings.rag_embedding_format_version,
        dimensions=settings.rag_embedding_dimensions,
        representation=settings.rag_embedding_representation,
        metric=settings.rag_embedding_metric,
        document_task_mode=settings.rag_embedding_document_task_mode,
        query_task_mode=settings.rag_embedding_query_task_mode,
    )
    subject = Subject(
        id=uuid4(),
        name="Astronomy",
        instructor_id=owner.id,
        corpus_revision=1,
        active_embedding_space_hash=None if failed else space_hash,
    )
    document = SubjectDocument(
        id=uuid4(),
        subject_id=subject.id,
        uploader_id=owner.id,
        title="Orbital mechanics",
        source_pdf_name="lecture.pdf",
        source_sha256="a" * 64,
    )
    db.add_all([owner, space, subject, document])
    await db.flush()
    content = SubjectDocumentContentRevision(
        id=uuid4(),
        document_id=document.id,
        subject_id=subject.id,
        uploader_id=owner.id,
        revision_no=1,
        source_sha256="a" * 64,
        extraction_version="pypdf_bounded_v1",
        status="pending_index" if failed else "ready",
        is_active=not failed,
        reserved_page_count=1,
        reserved_page_chars=59,
        reserved_page_bytes=59,
        actual_page_count=1,
        actual_page_chars=59,
        actual_page_bytes=59,
    )
    db.add(content)
    await db.flush()
    page_text = "Perihelion is the point of an orbit nearest to the Sun."
    db.add(
        SubjectDocumentPage(
            content_revision_id=content.id,
            document_id=document.id,
            subject_id=subject.id,
            uploader_id=owner.id,
            page_number=1,
            content=page_text,
        )
    )
    index = SubjectDocumentIndexRevision(
        id=uuid4(),
        content_revision_id=content.id,
        document_id=document.id,
        subject_id=subject.id,
        uploader_id=owner.id,
        revision_no=1,
        chunker_version="bounded_v1",
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
        status="index_failed" if failed else "ready",
        is_active=not failed,
        reserved_chunk_count=1,
        reserved_index_bytes=6_500,
        actual_chunk_count=1,
        actual_embedded_count=0 if failed else 1,
        actual_index_bytes=6_500,
        error_code="knowledge_index_failed" if failed else None,
        error_message="Document indexing failed." if failed else None,
    )
    db.add(index)
    await db.flush()
    db.add(
        SubjectDocumentChunk(
            index_revision_id=index.id,
            content_revision_id=content.id,
            document_id=document.id,
            subject_id=subject.id,
            uploader_id=owner.id,
            chunk_index=0,
            local_chunk_id="chunk-0001-p1",
            page_number=1,
            section=None,
            content=page_text,
            token_count=15,
            embedding_space_hash=space.identity_hash,
            embedding=None if failed else [0.1] * 1536,
        )
    )
    now = utcnow()
    job = SubjectDocumentIndexJob(
        id=uuid4(),
        index_revision_id=index.id,
        content_revision_id=content.id,
        document_id=document.id,
        subject_id=subject.id,
        uploader_id=owner.id,
        status="failed" if failed else "completed",
        operation_key_hash="b" * 64,
        request_fingerprint="c" * 64,
        corpus_revision=subject.corpus_revision,
        attempt_count=1,
        max_attempts=3,
        available_at=now,
        deadline_at=now + timedelta(minutes=5),
        completed_at=now,
        error_code="knowledge_index_failed" if failed else None,
        error_message="Document indexing failed." if failed else None,
    )
    db.add(job)
    await db.commit()
    return settings, owner, subject, document, content, index, job


async def test_instructor_can_list_publish_unpublish_and_remove_knowledge(db):
    settings, owner, subject, document, content, _index, _job = await _seed_document(db)
    owner_id = owner.id
    subject_id = subject.id
    document_id = document.id
    content_id = content.id
    service = KnowledgeManagementService(settings)
    listed = await service.list_documents(
        db, subject_id=subject_id, user=owner, limit=50
    )
    assert len(listed) == 1
    assert listed[0].content_revision.status == "ready"
    assert listed[0].index_revision.status == "ready"
    assert listed[0].can_review_publish is True

    await db.rollback()
    owner = await db.get(User, owner_id)
    db.expunge(owner)
    await db.rollback()
    async with db.begin():
        await service.review_and_publish(
            db, subject_id=subject_id, document_id=document_id, user=owner
        )
    content = await db.get(SubjectDocumentContentRevision, content_id)
    assert content.reviewed_at is not None and content.published_at is not None
    published_audit = await db.scalar(
        select(AuditEvent).where(AuditEvent.action == AuditAction.KNOWLEDGE_PUBLISHED.value)
    )
    assert published_audit is not None
    assert (
        published_audit.actor_id,
        published_audit.target_type,
        published_audit.target_id,
        published_audit.subject_id,
        published_audit.state_before,
        published_audit.state_after,
        published_audit.affected_count,
    ) == (owner_id, "knowledge", document_id, subject_id, False, True, 1)
    await db.rollback()
    owner = await db.get(User, owner_id)
    db.expunge(owner)
    await db.rollback()
    async with db.begin():
        await service.unpublish(
            db, subject_id=subject_id, document_id=document_id, user=owner
        )
    content = await db.get(SubjectDocumentContentRevision, content_id)
    assert content.reviewed_at is not None and content.published_at is None
    unpublished_audit = await db.scalar(
        select(AuditEvent).where(AuditEvent.action == AuditAction.KNOWLEDGE_UNPUBLISHED.value)
    )
    assert unpublished_audit is not None
    assert (unpublished_audit.state_before, unpublished_audit.state_after) == (True, False)

    await db.rollback()
    owner = await db.get(User, owner_id)
    db.expunge(owner)
    await db.rollback()
    async with db.begin():
        await service.remove(
            db, subject_id=subject_id, document_id=document_id, user=owner
        )
    assert await db.get(SubjectDocument, document_id) is None
    removed_audit = await db.scalar(
        select(AuditEvent).where(AuditEvent.action == AuditAction.KNOWLEDGE_REMOVED.value)
    )
    assert removed_audit is not None
    assert removed_audit.target_id == document_id
    assert removed_audit.affected_count == 1


async def test_knowledge_mutations_and_fixed_audits_roll_back_together(db):
    settings, owner, subject, document, content, _index, _job = await _seed_document(db)
    owner_id, subject_id, document_id, content_id = (
        owner.id,
        subject.id,
        document.id,
        content.id,
    )
    service = KnowledgeManagementService(settings)

    await service.review_and_publish(
        db, subject_id=subject_id, document_id=document_id, user=owner
    )
    assert await db.scalar(
        select(AuditEvent.id).where(
            AuditEvent.action == AuditAction.KNOWLEDGE_PUBLISHED.value
        )
    ) is not None
    await db.rollback()
    assert (await db.get(SubjectDocumentContentRevision, content_id)).published_at is None
    assert (
        await db.scalar(
            select(AuditEvent.id).where(
                AuditEvent.action == AuditAction.KNOWLEDGE_PUBLISHED.value
            )
        )
        is None
    )

    owner = await db.get(User, owner_id)
    await service.review_and_publish(
        db, subject_id=subject_id, document_id=document_id, user=owner
    )
    await db.commit()
    published_at = (await db.get(SubjectDocumentContentRevision, content_id)).published_at

    await db.rollback()
    owner = await db.get(User, owner_id)
    await service.unpublish(
        db, subject_id=subject_id, document_id=document_id, user=owner
    )
    assert await db.scalar(
        select(AuditEvent.id).where(
            AuditEvent.action == AuditAction.KNOWLEDGE_UNPUBLISHED.value
        )
    ) is not None
    await db.rollback()
    assert as_utc(
        (await db.get(SubjectDocumentContentRevision, content_id)).published_at
    ) == as_utc(published_at)
    assert (
        await db.scalar(
            select(AuditEvent.id).where(
                AuditEvent.action == AuditAction.KNOWLEDGE_UNPUBLISHED.value
            )
        )
        is None
    )

    await db.rollback()
    owner = await db.get(User, owner_id)
    await service.unpublish(
        db, subject_id=subject_id, document_id=document_id, user=owner
    )
    await db.commit()

    await db.rollback()
    owner = await db.get(User, owner_id)
    await service.remove(
        db, subject_id=subject_id, document_id=document_id, user=owner
    )
    assert await db.get(SubjectDocument, document_id) is None
    assert await db.scalar(
        select(AuditEvent.id).where(
            AuditEvent.action == AuditAction.KNOWLEDGE_REMOVED.value
        )
    ) is not None
    await db.rollback()
    assert await db.get(SubjectDocument, document_id) is not None
    assert (
        await db.scalar(
            select(AuditEvent.id).where(
                AuditEvent.action == AuditAction.KNOWLEDGE_REMOVED.value
            )
        )
        is None
    )


async def test_remove_refuses_running_index_claim_without_staging_audit(db):
    settings, owner, subject, document, _content, _index, job = await _seed_document(db)
    now = utcnow()
    job.status = "running"
    job.attempt_count = 1
    job.worker_id = "index-test-worker"
    job.claim_token = "d" * 64
    job.heartbeat_at = now
    job.lease_expires_at = now + timedelta(minutes=1)
    job.completed_at = None
    await db.commit()

    service = KnowledgeManagementService(settings)
    with pytest.raises(HTTPException) as active:
        await service.remove(
            db,
            subject_id=subject.id,
            document_id=document.id,
            user=owner,
        )
    assert active.value.detail["code"] == "knowledge_work_active"
    assert await db.get(SubjectDocument, document.id) is not None
    assert await db.scalar(
        select(AuditEvent.id).where(
            AuditEvent.action == AuditAction.KNOWLEDGE_REMOVED.value
        )
    ) is None
    with pytest.raises(PrivacyOperationError) as account_active:
        await delete_account(db, owner.id)
    assert account_active.value.code == "account_work_active"
    with pytest.raises(HTTPException) as subject_active:
        await SubjectService.delete_subject(db, subject)
    assert subject_active.value.detail["code"] == "subject_work_active"
    assert await db.get(SubjectDocumentIndexJob, job.id) is not None


async def test_failed_initial_index_retry_creates_fresh_revision_and_job(db):
    settings, owner, subject, document, _content, old_index, old_job = await _seed_document(
        db, failed=True
    )
    owner_id = owner.id
    subject_id = subject.id
    document_id = document.id
    old_index_id = old_index.id
    service = KnowledgeManagementService(settings)
    async with db.begin():
        await service.retry_index(
            db, subject_id=subject_id, document_id=document_id, user=owner
        )
    indexes = list(
        (
            await db.scalars(
                select(SubjectDocumentIndexRevision)
                .where(SubjectDocumentIndexRevision.document_id == document_id)
                .order_by(SubjectDocumentIndexRevision.revision_no)
            )
        ).all()
    )
    assert [item.status for item in indexes] == ["index_failed", "pending_index"]
    assert old_index_id != indexes[-1].id
    jobs = list(
        (
            await db.scalars(
                select(SubjectDocumentIndexJob).where(
                    SubjectDocumentIndexJob.document_id == document_id
                )
            )
        ).all()
    )
    assert {item.status for item in jobs} == {"failed", "queued"}
    assert old_job.status == "failed"

    await db.rollback()
    owner = await db.get(User, owner_id)
    db.expunge(owner)
    await db.rollback()
    with pytest.raises(HTTPException) as duplicate:
        async with db.begin():
            await service.retry_index(
                db, subject_id=subject_id, document_id=document_id, user=owner
            )
    assert duplicate.value.detail["code"] == "knowledge_index_not_retryable"


async def test_knowledge_http_endpoints_enforce_owner_and_expose_independent_states(
    session_factory, monkeypatch
):
    from httpx import ASGITransport, AsyncClient

    from app.database import get_db
    from app.main import app
    from app.routers import knowledge as knowledge_router
    from app.routers.auth import get_current_instructor

    async with session_factory() as seed_db:
        settings, owner, subject, document, _content, _index, _job = await _seed_document(seed_db)
        owner_id, subject_id, document_id = owner.id, subject.id, document.id
        foreign = User(
            id=uuid4(), email=f"foreign-{uuid4().hex}@example.test",
            hashed_password="not-real", role=UserRole.INSTRUCTOR,
        )
        seed_db.add(foreign)
        await seed_db.commit()
        foreign_id = foreign.id

    principals = {}
    async with session_factory() as read_db:
        for name, identifier in (("owner", owner_id), ("foreign", foreign_id)):
            principal = await read_db.get(User, identifier)
            read_db.expunge(principal)
            principals[name] = principal

    current = {"user": principals["owner"]}

    async def test_db():
        async with session_factory() as request_db:
            yield request_db

    async def test_user():
        return current["user"]

    monkeypatch.setattr(knowledge_router, "knowledge", KnowledgeManagementService(settings))
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[get_current_instructor] = test_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            listed = await client.get(f"/subjects/{subject_id}/knowledge/documents")
            assert listed.status_code == 200, listed.text
            row = listed.json()["documents"][0]
            assert row["id"] == str(document_id)
            assert row["content_revision"]["status"] == "ready"
            assert row["index_revision"]["status"] == "ready"
            assert row["can_review_publish"] is True
            assert row["requires_pdf_reupload"] is False

            detail = await client.get(
                f"/subjects/{subject_id}/knowledge/documents/{document_id}"
            )
            assert detail.status_code == 200
            published = await client.post(
                f"/subjects/{subject_id}/knowledge/documents/{document_id}/review-publish"
            )
            assert published.status_code == 200, published.text
            assert published.json()["content_revision"]["published_at"] is not None
            unpublished = await client.post(
                f"/subjects/{subject_id}/knowledge/documents/{document_id}/unpublish"
            )
            assert unpublished.status_code == 200, unpublished.text
            assert unpublished.json()["content_revision"]["published_at"] is None

            current["user"] = principals["foreign"]
            denied = await client.get(f"/subjects/{subject_id}/knowledge/documents")
            assert denied.status_code == 403

            current["user"] = principals["owner"]
            removed = await client.delete(
                f"/subjects/{subject_id}/knowledge/documents/{document_id}"
            )
            assert removed.status_code == 204
            missing = await client.get(
                f"/subjects/{subject_id}/knowledge/documents/{document_id}"
            )
            assert missing.status_code == 404
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
