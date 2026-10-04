"""Owner-scoped duplicate uploads and no-op revision contracts (offline DB)."""

from datetime import timedelta
import hashlib
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.config import Settings
from app.models.generation import GenerationJobSource, GenerationQuotaEvent, KnowledgeUploadQuotaEvent
from app.models.knowledge import (
    RagEmbeddingSpace, SubjectDocument, SubjectDocumentContentRevision,
    SubjectDocumentIndexRevision, embedding_space_hash,
)
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.schemas.generation import GenerationJobCreate, KnowledgeJobCreate
from app.services.generation import GenerationJobService
from app.services.knowledge_management import KnowledgeManagementService
from app.time_utils import utcnow
from app.services.pdf_processor import PDFProcessingError
from app.workers.generation import GenerationWorker


PDF = b"%PDF-1.7\nprivate synthetic duplicate fixture"


def configured() -> Settings:
    return Settings(
        _env_file=None, environment="test", database_url="sqlite+aiosqlite:///:memory:",
        secret_key="test-only-secret-key-with-adequate-entropy-1234567890",
        generation_source_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        flashcard_ai_provider_enabled=True, rag_enabled=True,
        rag_embedding_provider_enabled=True, rag_embedding_provider="gemini",
        rag_embedding_model="gemini-embedding-001", rag_embedding_api_key="test-key",
        rag_embedding_quota_bucket="test-bucket",
    )


async def seed(db, *, ready=True, active=True, published=False):
    settings = configured()
    owner = User(id=uuid4(), email=f"owner-{uuid4().hex}@example.test", hashed_password="fixture", role=UserRole.INSTRUCTOR)
    space_hash = embedding_space_hash(settings.rag_embedding_space_identity)
    space = RagEmbeddingSpace(
        identity_hash=space_hash, provider=settings.rag_embedding_provider,
        base_url=settings.rag_embedding_endpoint_identity, model=settings.rag_embedding_model,
        space_revision=settings.rag_embedding_space_revision,
        format_version=settings.rag_embedding_format_version,
        dimensions=settings.rag_embedding_dimensions,
        representation=settings.rag_embedding_representation,
        metric=settings.rag_embedding_metric,
        document_task_mode=settings.rag_embedding_provider_task_modes[0],
        query_task_mode=settings.rag_embedding_provider_task_modes[1],
    )
    subject = Subject(id=uuid4(), name="A", instructor_id=owner.id, active_embedding_space_hash=space_hash if active else None)
    doc = SubjectDocument(id=uuid4(), subject_id=subject.id, uploader_id=owner.id, title="Original", source_pdf_name="original.pdf", source_sha256=hashlib.sha256(PDF).hexdigest())
    db.add_all([owner, space, subject, doc])
    await db.flush()
    revision = SubjectDocumentContentRevision(
        id=uuid4(), document_id=doc.id, subject_id=subject.id, uploader_id=owner.id,
        revision_no=1, source_sha256=hashlib.sha256(PDF).hexdigest(),
        extraction_version="pypdf_bounded_v1", status="ready" if ready else "pending_index",
        is_active=ready, reserved_page_count=1, reserved_page_chars=8,
        reserved_page_bytes=8, actual_page_count=1 if ready else 0,
        actual_page_chars=8 if ready else 0, actual_page_bytes=8 if ready else 0,
        reviewed_at=utcnow() if published else None,
        reviewed_by_id=owner.id if published else None,
        published_at=utcnow() if published else None,
    )
    db.add(revision)
    await db.flush()
    index = SubjectDocumentIndexRevision(
        id=uuid4(), content_revision_id=revision.id, document_id=doc.id,
        subject_id=subject.id, uploader_id=owner.id, revision_no=1,
        chunker_version="bounded_v1", embedding_provider=space.provider,
        embedding_base_url=space.base_url, embedding_model=space.model,
        embedding_space_revision=space.space_revision,
        embedding_format_version=space.format_version,
        embedding_dimensions=space.dimensions,
        embedding_representation=space.representation,
        embedding_metric=space.metric, document_task_mode=space.document_task_mode,
        query_task_mode=space.query_task_mode, embedding_space_hash=space_hash,
        status="ready" if ready else "pending_index", is_active=ready and active,
        reserved_chunk_count=1, reserved_index_bytes=100,
        actual_chunk_count=1 if ready else 0,
        actual_embedded_count=1 if ready else 0,
        actual_index_bytes=100 if ready else 0,
    )
    db.add(index)
    await db.flush()
    return owner, subject, doc, revision, index


async def reserve_knowledge(db, service, owner, subject, *, document_id=None, key=None):
    return await service.create_knowledge_reservation(
        db, user_id=owner.id,
        data=KnowledgeJobCreate(subject_id=subject.id, document_id=document_id,
                                title="New title", source_pdf_name="new.pdf"),
        idempotency_key=key or f"knowledge-{uuid4().hex}",
    )


async def upload(db, service, job, owner, content=PDF):
    return await service.attach_source(db, job_id=job.id, user_id=owner.id,
                                       media_type="application/pdf", content=content)


async def test_explicit_unchanged_revision_is_noop_and_raw_upload_still_charged(db):
    owner, subject, doc, revision, _index = await seed(db)
    service = GenerationJobService(configured())
    job = await reserve_knowledge(db, service, owner, subject, document_id=doc.id)
    await upload(db, service, job, owner)
    assert job.status == "completed" and job.knowledge_upload_outcome == "no_changes"
    assert job.knowledge_capture_status == "unchanged"
    assert (job.document_id, job.knowledge_content_revision_id) == (doc.id, revision.id)
    assert await db.get(GenerationJobSource, job.id) is None
    assert (await db.get(SubjectDocument, doc.id)).title == "Original"
    assert await db.scalar(select(func.count(SubjectDocumentContentRevision.id))) == 1
    assert await db.scalar(select(func.count(SubjectDocumentIndexRevision.id))) == 1
    assert await db.scalar(select(func.sum(KnowledgeUploadQuotaEvent.upload_bytes))) == len(PDF)
    assert (await service.to_response(db, job)).knowledge_upload_outcome == "no_changes"


async def test_combined_unchanged_revision_keeps_source_for_cards_and_cancel_preserves_document(db):
    owner, subject, doc, revision, _index = await seed(db)
    service = GenerationJobService(configured())
    job = await service.create_reservation(db, user_id=owner.id,
        data=GenerationJobCreate(subject_id=subject.id, document_id=doc.id,
                                 set_title="Cards", source_pdf_name="same.pdf", card_count=4),
        idempotency_key="combined-unchanged-key")
    await upload(db, service, job, owner)
    assert job.status == "queued" and job.knowledge_capture_status == "unchanged"
    assert job.knowledge_content_revision_id == revision.id
    assert await db.get(GenerationJobSource, job.id) is not None
    assert await db.scalar(select(func.sum(GenerationQuotaEvent.upload_bytes))) == len(PDF)
    await service.cancel(db, job_id=job.id, user_id=owner.id)
    assert await db.get(GenerationJobSource, job.id) is None
    assert await db.get(SubjectDocumentContentRevision, revision.id) is not None


@pytest.mark.parametrize("published", [False, True], ids=["private", "published"])
async def test_duplicate_choice_reuses_ready_revision_and_replay_is_safe(db, published):
    owner, subject, doc, revision, _index = await seed(db, published=published)
    service = GenerationJobService(configured())
    job = await reserve_knowledge(db, service, owner, subject)
    await upload(db, service, job, owner)
    response = await service.to_response(db, job)
    assert response.status == "awaiting_choice"
    assert response.duplicate_candidate is not None
    assert response.duplicate_candidate.document_id == doc.id
    assert response.duplicate_candidate.can_reuse
    assert response.choice_expires_at is not None
    assert await db.get(GenerationJobSource, job.id) is not None
    await service.submit_knowledge_choice(db, job_id=job.id, user_id=owner.id,
                                          choice="reuse", idempotency_key="reuse-choice-one")
    assert job.status == "completed" and job.knowledge_capture_status == "reused"
    assert (job.document_id, job.knowledge_content_revision_id) == (doc.id, revision.id)
    assert await db.get(GenerationJobSource, job.id) is None
    replay = await service.submit_knowledge_choice(db, job_id=job.id, user_id=owner.id,
                                                   choice="reuse", idempotency_key="reuse-choice-two")
    assert replay.id == job.id
    with pytest.raises(HTTPException) as conflict:
        await service.submit_knowledge_choice(db, job_id=job.id, user_id=owner.id,
                                              choice="separate_copy", idempotency_key="different-choice")
    assert conflict.value.detail["code"] == "knowledge_choice_conflict"
    assert await db.scalar(select(func.count(SubjectDocument.id))) == 1
    assert await db.scalar(select(func.count(SubjectDocumentContentRevision.id))) == 1


@pytest.mark.parametrize(
    ("ready", "active"),
    [(False, False), (True, False)],
    ids=["incomplete", "incompatible-space"],
)
async def test_incomplete_or_incompatible_match_cannot_be_reused_and_cancel_cleans_source(
    db, ready, active
):
    owner, subject, doc, _revision, _index = await seed(db, ready=ready, active=active)
    service = GenerationJobService(configured())
    job = await reserve_knowledge(db, service, owner, subject)
    await upload(db, service, job, owner)
    assert job.status == "awaiting_choice"
    assert not (await service.to_response(db, job)).duplicate_candidate.can_reuse
    with pytest.raises(HTTPException) as unavailable:
        await service.submit_knowledge_choice(db, job_id=job.id, user_id=owner.id,
                                              choice="reuse", idempotency_key="not-ready-reuse")
    assert unavailable.value.detail["code"] == "knowledge_choice_stale"
    await service.cancel(db, job_id=job.id, user_id=owner.id)
    assert job.status == "cancelled"
    assert await db.get(GenerationJobSource, job.id) is None
    assert await db.get(SubjectDocument, doc.id) is not None


async def test_changed_explicit_revision_bypasses_duplicate_prompt_and_cross_subject_is_hidden(db):
    owner, subject, doc, _revision, _index = await seed(db)
    service = GenerationJobService(configured())
    changed = await reserve_knowledge(db, service, owner, subject, document_id=doc.id)
    await upload(db, service, changed, owner, b"%PDF-1.7\nchanged content")
    assert changed.status == "queued" and changed.knowledge_upload_outcome is None
    await service.cancel(db, job_id=changed.id, user_id=owner.id)
    assert await db.get(SubjectDocument, doc.id) is not None
    other_subject = Subject(id=uuid4(), name="Other", instructor_id=owner.id)
    db.add(other_subject)
    await db.flush()
    cross = await reserve_knowledge(db, service, owner, other_subject)
    await upload(db, service, cross, owner)
    assert cross.status == "queued" and cross.knowledge_choice_candidate_id is None
    with pytest.raises(HTTPException) as denied:
        await reserve_knowledge(db, service, owner, other_subject, document_id=doc.id)
    assert denied.value.status_code == 404


async def test_choice_is_owner_scoped_and_deleted_candidate_can_only_continue_as_copy(db):
    owner, subject, doc, _revision, _index = await seed(db)
    intruder = User(
        id=uuid4(), email=f"intruder-{uuid4().hex}@example.test",
        hashed_password="fixture", role=UserRole.INSTRUCTOR,
    )
    db.add(intruder)
    await db.flush()
    service = GenerationJobService(configured())
    job = await reserve_knowledge(db, service, owner, subject)
    await upload(db, service, job, owner)

    with pytest.raises(HTTPException) as hidden:
        await service.submit_knowledge_choice(
            db, job_id=job.id, user_id=intruder.id,
            choice="reuse", idempotency_key="intruder-choice",
        )
    assert hidden.value.status_code == 404

    await KnowledgeManagementService(configured()).remove(
        db, subject_id=subject.id, document_id=doc.id, user=owner,
    )
    assert job.knowledge_choice_candidate_id is None
    with pytest.raises(HTTPException) as stale:
        await service.submit_knowledge_choice(
            db, job_id=job.id, user_id=owner.id,
            choice="reuse", idempotency_key="stale-candidate",
        )
    assert stale.value.detail["code"] == "knowledge_choice_stale"

    await service.submit_knowledge_choice(
        db, job_id=job.id, user_id=owner.id,
        choice="separate_copy", idempotency_key="continue-as-copy",
    )
    assert job.status == "queued"
    assert job.knowledge_upload_outcome == "separate_copy"
    assert await db.get(GenerationJobSource, job.id) is not None


async def test_combined_reuse_cancel_and_failure_preserve_existing_revision(
    session_factory, monkeypatch
):
    settings = configured()
    service = GenerationJobService(settings)
    async with session_factory() as db:
        async with db.begin():
            owner, subject, doc, revision, _index = await seed(db)

            cancelled = await service.create_reservation(
                db, user_id=owner.id,
                data=GenerationJobCreate(
                    subject_id=subject.id, set_title="Cancelled cards",
                    source_pdf_name="same.pdf", card_count=4,
                ),
                idempotency_key="combined-reuse-cancel",
            )
            await upload(db, service, cancelled, owner)
            await service.submit_knowledge_choice(
                db, job_id=cancelled.id, user_id=owner.id,
                choice="reuse", idempotency_key="combined-reuse-cancel-choice",
            )
            await service.cancel(db, job_id=cancelled.id, user_id=owner.id)
            assert cancelled.status == "cancelled"
            assert cancelled.knowledge_capture_status == "reused"
            assert await db.get(SubjectDocumentContentRevision, revision.id) is not None

            failed = await service.create_reservation(
                db, user_id=owner.id,
                data=GenerationJobCreate(
                    subject_id=subject.id, set_title="Failed cards",
                    source_pdf_name="same-again.pdf", card_count=4,
                ),
                idempotency_key="combined-reuse-failure",
            )
            await upload(db, service, failed, owner)
            await service.submit_knowledge_choice(
                db, job_id=failed.id, user_id=owner.id,
                choice="reuse", idempotency_key="combined-reuse-failure-choice",
            )
            failed_id = failed.id
            owner_id = owner.id
            document_id = doc.id
            revision_id = revision.id

    worker = GenerationWorker(
        settings=settings, session_factory=session_factory, worker_id="reused-failure",
    )
    claim = await worker.claim_next()
    assert claim is not None and claim[0] == failed_id

    async def fail_pipeline(*_args):
        raise PDFProcessingError("image_only_pdf", "No selectable text was found.")

    monkeypatch.setattr(worker, "_pipeline", fail_pipeline)
    await worker.process_claim(*claim)

    async with session_factory() as db:
        persisted = await service.get_owner_job(db, failed_id, owner_id)
        assert persisted.status == "failed"
        assert persisted.knowledge_capture_status == "reused"
        assert await db.get(SubjectDocument, document_id) is not None
        assert await db.get(SubjectDocumentContentRevision, revision_id) is not None
        assert await db.get(GenerationJobSource, failed_id) is None


async def test_pending_choice_expires_and_encrypted_source_is_removed(session_factory):
    async with session_factory() as db:
        async with db.begin():
            owner, subject, _doc, _revision, _index = await seed(db)
            service = GenerationJobService(configured())
            job = await reserve_knowledge(db, service, owner, subject)
            await upload(db, service, job, owner)
            job.knowledge_choice_expires_at = utcnow() - timedelta(seconds=1)
            job_id = job.id
            owner_id = owner.id
    worker = GenerationWorker(settings=configured(), session_factory=session_factory, worker_id="choice-cleanup")
    await worker.recover_and_cleanup()
    async with session_factory() as db:
        job = await service.get_owner_job(db, job_id, owner_id)
        assert job.status == "cancelled" and job.stage == "choice_expired"
        assert await db.get(GenerationJobSource, job_id) is None
        assert not (await service.to_response(db, job)).can_cancel
        assert await db.scalar(select(func.sum(KnowledgeUploadQuotaEvent.upload_bytes))) == len(PDF)
