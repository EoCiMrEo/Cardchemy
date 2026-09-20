from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.ai.chunking import prepare_document
from app.ai.contracts import ExtractedDocument, ExtractedPage
from app.config import Settings
from app.models.generation import GenerationJob, GenerationQuotaEvent, KnowledgeUploadQuotaEvent
from app.models.knowledge import SubjectDocument
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.schemas.generation import KnowledgeJobCreate
from app.services.generation import GenerationJobService
from app.services.knowledge_capture import KnowledgeCaptureFailure, validate_capture_bounds


def settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "database_url": "sqlite+aiosqlite:///:memory:",
        "secret_key": "test-only-secret-key-with-adequate-entropy-1234567890",
        "generation_source_encryption_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "rag_enabled": True,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def seed_owner_subject(db):
    owner = User(
        id=uuid4(), email=f"knowledge-{uuid4().hex}@example.test",
        hashed_password="fixture", role=UserRole.INSTRUCTOR,
    )
    subject = Subject(id=uuid4(), name="Knowledge", instructor_id=owner.id)
    db.add_all([owner, subject])
    await db.flush()
    return owner, subject


def test_one_prepared_document_has_stable_page_and_chunk_provenance():
    document = ExtractedDocument(pages=[
        ExtractedPage(page_number=1, text="Section One\n\nAlpha beta gamma."),
        ExtractedPage(page_number=2, text="Section Two\n\nDelta epsilon."),
    ])
    prepared = prepare_document(document, max_tokens=16, overlap_tokens=2)
    chars, byte_count, index_bytes = validate_capture_bounds(prepared)
    assert prepared.document is document
    assert {chunk.page_number for chunk in prepared.chunks} == {1, 2}
    assert chars == sum(len(page.text) for page in document.pages)
    assert byte_count == sum(len(page.text.encode()) for page in document.pages)
    assert index_bytes > byte_count


def test_capture_bounds_fail_cleanly_before_any_write():
    document = ExtractedDocument(pages=[
        ExtractedPage(page_number=index, text="usable text") for index in range(1, 102)
    ])
    prepared = prepare_document(document, max_tokens=32)
    with pytest.raises(KnowledgeCaptureFailure) as failure:
        validate_capture_bounds(prepared)
    assert failure.value.code == "knowledge_capture_unsupported"


async def test_knowledge_only_admission_is_idempotent_and_uses_separate_quota(db):
    owner, subject = await seed_owner_subject(db)
    service = GenerationJobService(settings())
    data = KnowledgeJobCreate(
        subject_id=subject.id,
        title="Private source",
        source_pdf_name="private.pdf",
    )
    job = await service.create_knowledge_reservation(
        db, user_id=owner.id, data=data, idempotency_key="fixture-1"
    )
    replay = await service.create_knowledge_reservation(
        db, user_id=owner.id, data=data, idempotency_key="fixture-1"
    )
    assert replay.id == job.id
    assert job.job_kind == "knowledge_only" and job.requested_card_count == 0
    assert job.knowledge_capture_status == "pending"
    await service.attach_source(
        db,
        job_id=job.id,
        user_id=owner.id,
        media_type="application/pdf",
        content=b"%PDF-1.7\nprivate fixture",
    )
    assert await db.scalar(select(func.count(KnowledgeUploadQuotaEvent.id))) == 1
    assert await db.scalar(select(func.count(GenerationQuotaEvent.id))) == 0


async def test_cancelling_pending_explicit_revision_detaches_without_deleting_target(db):
    owner, subject = await seed_owner_subject(db)
    target = SubjectDocument(
        subject_id=subject.id, uploader_id=owner.id, title="Existing",
        source_pdf_name="old.pdf", source_sha256="a" * 64,
    )
    db.add(target)
    await db.flush()
    service = GenerationJobService(settings())
    job = await service.create_knowledge_reservation(
        db,
        user_id=owner.id,
        data=KnowledgeJobCreate(
            subject_id=subject.id, document_id=target.id,
            title="Changed", source_pdf_name="changed.pdf",
        ),
        idempotency_key="fixture-2",
    )
    await service.cancel(db, job_id=job.id, user_id=owner.id)
    assert job.status == "cancelled"
    assert job.document_id is None and job.knowledge_capture_status == "removed"
    assert await db.get(SubjectDocument, target.id) is not None
    assert await db.get(GenerationJob, job.id) is not None
