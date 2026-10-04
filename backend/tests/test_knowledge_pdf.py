"""Original-PDF bounds, exact-revision binding and authenticated block reads."""

import hashlib
import json
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import SecretStr, ValidationError
from sqlalchemy import func, select

from app.config import Settings
from app.ai.chunking import prepare_document
from app.ai.contracts import ExtractedDocument, ExtractedPage
from app.models.generation import GenerationJob
from app.models.knowledge import SubjectDocument, SubjectDocumentContentRevision, SubjectDocumentPdf, SubjectDocumentPdfBlock
from app.models.rag import RagRelatedEvidence
from app.models.user import User, UserRole
from app.routers import rag as rag_router
from app.services.knowledge_management import KnowledgeManagementService
from app.schemas.generation import KnowledgeJobCreate
from app.services.generation import GenerationJobService
from app.services.knowledge_capture import KnowledgeCaptureFailure, capture_prepared_document
from app.services.knowledge_pdf import (
    BLOCK_BYTES, KnowledgePdfError, PdfRange, _decrypt_range, archive_pdf,
    encrypt_pdf_blocks, parse_pdf_range, probe_pdf_archive, read_pdf_range,
)
from app.services.privacy import export_account
from app.time_utils import utcnow
from tests.test_knowledge_capture import seed_owner_subject
from tests.test_knowledge_management import _settings as _knowledge_settings
from tests.test_knowledge_management import _seed_document


def _settings():
    return Settings(
        _env_file=None, environment="test",
        secret_key="test-only-secret-key-with-adequate-entropy-1234567890",
        generation_source_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        knowledge_pdf_encryption_key="AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE",
    )


def _archive(data: bytes):
    return SubjectDocumentPdf(
        content_revision_id=uuid4(), document_id=uuid4(), subject_id=uuid4(), uploader_id=uuid4(),
        source_sha256=hashlib.sha256(data).hexdigest(), byte_size=len(data), page_count=2,
        block_count=(len(data) + BLOCK_BYTES - 1)//BLOCK_BYTES, key_version=1,
    )


def test_pdf_blocks_reconstruct_cross_block_range_and_reject_tampering():
    data = b"%PDF-1.7\n" + b"a" * BLOCK_BYTES + b"tail"
    pdf = _archive(data)
    blocks = encrypt_pdf_blocks(_settings(), pdf, data)
    span = parse_pdf_range(f"bytes={BLOCK_BYTES-4}-{BLOCK_BYTES+8}", len(data))
    assert _decrypt_range(_settings(), pdf, blocks, span) == data[span.start:span.end]
    full = PdfRange(0, len(data), False)
    assert _decrypt_range(_settings(), pdf, blocks, full) == data
    assert b"%PDF-1.7" not in blocks[0].payload
    with pytest.raises(KnowledgePdfError, match="unavailable"):
        _decrypt_range(_settings(), pdf, blocks[::-1], full)
    blocks[0].payload = bytes(blocks[0].payload[:-1]) + bytes([blocks[0].payload[-1] ^ 1])
    with pytest.raises(KnowledgePdfError, match="unavailable"):
        _decrypt_range(_settings(), pdf, blocks, full)


def test_archive_never_exceeds_existing_knowledge_page_limit():
    data = b"%PDF-1.7\nfixture"
    pdf = _archive(data)
    pdf.page_count = 101
    expanded = _settings().model_copy(update={"pdf_max_pages": 2000})
    with pytest.raises(KnowledgePdfError, match="does not match"):
        encrypt_pdf_blocks(expanded, pdf, data)
    with pytest.raises(KnowledgePdfError, match="does not match"):
        encrypt_pdf_blocks(_settings(), pdf, data)


@pytest.mark.parametrize("field", ["document_id", "subject_id", "uploader_id", "content_revision_id"])
def test_block_cannot_be_relabelled_to_another_scope(field):
    data = b"%PDF-1.7\nfixture"
    pdf = _archive(data)
    blocks = encrypt_pdf_blocks(_settings(), pdf, data)
    setattr(pdf, field, uuid4())
    with pytest.raises(KnowledgePdfError, match="unavailable"):
        _decrypt_range(_settings(), pdf, blocks, PdfRange(0, len(data), False))


@pytest.mark.parametrize("value", [None, "bytes=", "items=0-4", "bytes=0-1,4-8", "bytes=8-1", "bytes=-0", "bytes=999-", "bytes=0-99999999"])
def test_http_pdf_ranges_are_required_single_and_bounded(value):
    size = 100 if value != "bytes=0-99999999" else 100 * BLOCK_BYTES
    with pytest.raises(KnowledgePdfError) as denied:
        parse_pdf_range(value, size)
    assert denied.value.status_code == (400 if value is None else 416)


def test_suffix_and_open_ranges_are_bounded_and_capped_at_file_end():
    assert parse_pdf_range("bytes=-4", 100) == PdfRange(96, 100, True)
    assert parse_pdf_range("bytes=99-200", 100) == PdfRange(99, 100, True)
    assert parse_pdf_range("bytes=0-", 100*BLOCK_BYTES) == PdfRange(0, 8*BLOCK_BYTES, True)


def test_archive_key_is_independent_optional_and_never_falls_back():
    configured = _settings()
    missing = configured.model_copy(update={"knowledge_pdf_encryption_key": None})
    with pytest.raises(KnowledgePdfError, match="not configured"):
        encrypt_pdf_blocks(missing, _archive(b"fixture"), b"fixture")
    with pytest.raises(ValidationError, match="must differ"):
        Settings(
            _env_file=None, environment="test",
            secret_key="test-only-secret-key-with-adequate-entropy-1234567890",
            generation_source_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            knowledge_pdf_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        )
    pdf = _archive(b"fixture")
    blocks = encrypt_pdf_blocks(configured, pdf, b"fixture")
    wrong = configured.model_copy(update={"knowledge_pdf_encryption_key": SecretStr("AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgI")})
    with pytest.raises(KnowledgePdfError, match="unavailable"):
        _decrypt_range(wrong, pdf, blocks, PdfRange(0, 7, False))


async def test_attach_exact_original_is_idempotent_without_revision_or_index_changes(db):
    configured, owner, subject, document, revision, index, _job = await _seed_document(db)
    data = b"%PDF-1.7\nfixture"
    revision.source_sha256 = hashlib.sha256(data).hexdigest()
    configured = configured.model_copy(update={"knowledge_pdf_encryption_key": _settings().knowledge_pdf_encryption_key})
    await db.commit()
    service = KnowledgeManagementService(configured)
    for _ in range(2):
        await service.attach_original_pdf(
            db, subject_id=subject.id, document_id=document.id, user=owner,
            expected_revision_id=revision.id, content=data,
        )
        await db.commit()
    assert await db.scalar(select(func.count()).select_from(SubjectDocumentPdf)) == 1
    assert await db.scalar(select(func.count()).select_from(SubjectDocumentPdfBlock)) == 1
    pdf = await db.get(SubjectDocumentPdf, revision.id)
    await probe_pdf_archive(db, settings=configured, pdf=pdf)
    got, _span = await read_pdf_range(db, settings=configured, pdf=pdf, range_header="bytes=0-15")
    assert got == data[:16]
    assert revision.revision_no == 1 and index.revision_no == 1 and revision.published_at is None


async def test_idempotent_attach_rejects_wrong_archive_key_without_replacing_ciphertext(db):
    configured, owner, subject, document, revision, _index, _job = await _seed_document(db)
    data = b"%PDF-1.7\nfixture"
    revision.source_sha256 = hashlib.sha256(data).hexdigest()
    await db.commit()
    good = configured.model_copy(update={"knowledge_pdf_encryption_key": _settings().knowledge_pdf_encryption_key})
    wrong = good.model_copy(update={"knowledge_pdf_encryption_key": SecretStr("AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgI")})
    await KnowledgeManagementService(good).attach_original_pdf(
        db, subject_id=subject.id, document_id=document.id, user=owner,
        expected_revision_id=revision.id, content=data,
    )
    await db.commit()
    original_payload = (await db.get(SubjectDocumentPdfBlock, (revision.id, 0))).payload

    with pytest.raises(HTTPException) as denied:
        await KnowledgeManagementService(wrong).attach_original_pdf(
            db, subject_id=subject.id, document_id=document.id, user=owner,
            expected_revision_id=revision.id, content=data,
        )
    assert denied.value.status_code == 404
    assert denied.value.detail["code"] == "knowledge_pdf_unavailable"
    assert (await db.get(SubjectDocumentPdfBlock, (revision.id, 0))).payload == original_payload


async def test_idempotent_attach_authenticates_interior_blocks_and_full_digest(db):
    configured, owner, subject, document, revision, _index, _job = await _seed_document(db)
    data = b"%PDF-1.7\n" + b"a" * (2 * BLOCK_BYTES)
    revision.source_sha256 = hashlib.sha256(data).hexdigest()
    await db.commit()
    configured = configured.model_copy(update={"knowledge_pdf_encryption_key": _settings().knowledge_pdf_encryption_key})
    service = KnowledgeManagementService(configured)
    await service.attach_original_pdf(
        db, subject_id=subject.id, document_id=document.id, user=owner,
        expected_revision_id=revision.id, content=data,
    )
    await db.commit()
    middle = await db.get(SubjectDocumentPdfBlock, (revision.id, 1))
    middle.payload = bytes(middle.payload[:-1]) + bytes([middle.payload[-1] ^ 1])
    await db.commit()

    with pytest.raises(HTTPException) as denied:
        await service.attach_original_pdf(
            db, subject_id=subject.id, document_id=document.id, user=owner,
            expected_revision_id=revision.id, content=data,
        )
    assert denied.value.status_code == 404
    assert denied.value.detail["code"] == "knowledge_pdf_unavailable"


async def test_attach_denies_student_foreign_owner_wrong_hash_and_stale_revision(db):
    configured, owner, subject, document, revision, _index, _job = await _seed_document(db)
    owner_id, subject_id, document_id, revision_id = owner.id, subject.id, document.id, revision.id
    service = KnowledgeManagementService(configured)
    for role in (UserRole.STUDENT, UserRole.INSTRUCTOR):
        stranger = User(id=uuid4(), email=f"stranger-{uuid4().hex}@example.test", hashed_password="fixture", role=role)
        db.add(stranger)
        await db.commit()
        with pytest.raises(HTTPException):
            await service.attach_original_pdf(db, subject_id=subject_id, document_id=document_id,
                user=stranger, expected_revision_id=revision_id, content=b"%PDF-1.7\nfixture")
        await db.rollback()
    with pytest.raises(HTTPException) as stale:
        await service.attach_original_pdf(db, subject_id=subject_id, document_id=document_id,
            user=await db.get(User, owner_id), expected_revision_id=uuid4(), content=b"%PDF-1.7\nfixture")
    assert stale.value.detail["code"] == "knowledge_pdf_revision_changed"
    await db.rollback()
    with pytest.raises(HTTPException) as mismatch:
        await service.attach_original_pdf(db, subject_id=subject_id, document_id=document_id,
            user=await db.get(User, owner_id), expected_revision_id=revision_id, content=b"%PDF-1.7\nfixture")
    assert mismatch.value.detail["code"] == "knowledge_pdf_revision_mismatch"
    assert await db.scalar(select(func.count()).select_from(SubjectDocumentPdf)) == 0


async def test_quota_failure_does_not_leave_manifest_or_blocks(db, monkeypatch):
    _configured, _owner, _subject, _document, revision, _index, _job = await _seed_document(db)
    data = b"%PDF-1.7\nfixture"
    revision.source_sha256 = hashlib.sha256(data).hexdigest()
    await db.commit()
    monkeypatch.setattr("app.services.knowledge_pdf.MAX_SUBJECT_BYTES", 1)
    with pytest.raises(KnowledgePdfError) as denied:
        await archive_pdf(db, settings=_settings(), revision=revision, data=data)
    assert denied.value.code == "knowledge_pdf_capacity_exceeded"
    assert await db.scalar(select(func.count()).select_from(SubjectDocumentPdf)) == 0


async def test_account_export_keeps_source_text_but_excludes_original_pdf_ciphertext(db):
    _configured, owner, _subject, _document, revision, _index, _job = await _seed_document(db)
    data = b"%PDF-1.7\nprivate-original-only-marker"
    revision.source_sha256 = hashlib.sha256(data).hexdigest()
    await db.commit()
    await archive_pdf(db, settings=_settings(), revision=revision, data=data)
    await db.commit()
    result = await export_account(db, owner.id)
    assert result["knowledge_pages"]
    assert not {"knowledge_pdfs", "knowledge_pdf_blocks", "subject_document_pdfs", "subject_document_pdf_blocks"} & result.keys()
    serialized = json.dumps(result)
    for excluded in ("private-original-only-marker", "payload", "nonce", "knowledge_pdf_encryption_key"):
        assert excluded not in serialized


@pytest.mark.parametrize("key_configured", [False, True])
async def test_runtime_capture_archives_original_atomically_or_rolls_back(session_factory, key_configured):
    data = b"%PDF-1.7\nprivate-capture-fixture"
    settings = _knowledge_settings().model_copy(update={
        "knowledge_pdf_encryption_key": _settings().knowledge_pdf_encryption_key if key_configured else None,
    })
    async with session_factory() as db:
        owner, subject = await seed_owner_subject(db)
        service = GenerationJobService(settings)
        job = await service.create_knowledge_reservation(db, user_id=owner.id,
            data=KnowledgeJobCreate(subject_id=subject.id, title="Capture fixture", source_pdf_name="fixture.pdf"),
            idempotency_key="archive-capture-fixture")
        await service.attach_source(db, job_id=job.id, user_id=owner.id, media_type="application/pdf", content=data)
        job.status = "running"
        job.worker_id = "archive-capture-worker"
        job.claim_token = "archive-capture-token"
        job.lease_expires_at = utcnow() + timedelta(minutes=2)
        job_id = job.id
        await db.commit()
    prepared = prepare_document(ExtractedDocument(pages=[ExtractedPage(page_number=1, text="A useful lecture definition.")]), max_tokens=32)
    arguments = dict(settings=settings, job_id=job_id, worker_id="archive-capture-worker",
        claim_token="archive-capture-token", prepared=prepared, original_pdf=data)
    if key_configured:
        captured = await capture_prepared_document(session_factory, **arguments)
    else:
        with pytest.raises(KnowledgeCaptureFailure) as failed:
            await capture_prepared_document(session_factory, **arguments)
        assert failed.value.code == "knowledge_pdf_key_unavailable"
    async with session_factory() as db:
        job = await db.get(GenerationJob, job_id)
        for model in (SubjectDocument, SubjectDocumentContentRevision, SubjectDocumentPdf, SubjectDocumentPdfBlock):
            assert await db.scalar(select(func.count()).select_from(model)) == int(key_configured)
        if key_configured:
            archive = await db.get(SubjectDocumentPdf, captured.content_revision_id)
            assert job.knowledge_capture_status == "captured" and archive.source_sha256 == hashlib.sha256(data).hexdigest()
            assert (await read_pdf_range(db, settings=settings, pdf=archive, range_header="bytes=0-7"))[0] == data[:8]
        else:
            assert job.document_id is None and job.knowledge_capture_status == "pending"


async def test_pdf_route_reauthorizes_bundle_before_loading_archive(monkeypatch):
    calls = []
    async def denied(*_args, **_kwargs):
        calls.append("authorize")
        raise HTTPException(404, "unavailable")
    class NoReads:
        async def get(self, *_args):
            pytest.fail("PDF read occurred before authorization")
    monkeypatch.setattr(rag_router.answers, "related_page", denied)
    with pytest.raises(HTTPException):
        await rag_router._authorized_original_pdf(NoReads(), subject_id=uuid4(), thread_id=uuid4(),
            job_id=uuid4(), excerpt_order=1, user=SimpleNamespace(id=uuid4()))
    assert calls == ["authorize"]


def _route_fixture():
    data = b"%PDF-1.7\nfixture"
    pdf = _archive(data)
    reference = SimpleNamespace(content_revision_id=pdf.content_revision_id, document_id=pdf.document_id)
    revision = SimpleNamespace(uploader_id=pdf.uploader_id, source_sha256=pdf.source_sha256, actual_page_count=pdf.page_count)
    blocks = encrypt_pdf_blocks(_settings(), pdf, data)
    class DB:
        async def get(self, model, _key):
            return {RagRelatedEvidence: reference, SubjectDocumentPdf: pdf, SubjectDocumentContentRevision: revision}[model]
        async def scalars(self, _query):
            return SimpleNamespace(all=lambda: blocks)
        async def execute(self, _query):
            return SimpleNamespace(one=lambda: (pdf.block_count, 0, pdf.block_count - 1))
    arguments = dict(subject_id=pdf.subject_id, thread_id=uuid4(), job_id=uuid4(), excerpt_order=1,
                     user=SimpleNamespace(id=uuid4()), db=DB())
    return data, pdf, arguments


async def test_head_and_every_range_reauthorize_and_never_return_unbounded_bytes(monkeypatch):
    data, pdf, arguments = _route_fixture()
    authorizations = []
    async def authorize(_db, **kwargs):
        authorizations.append(kwargs)
    monkeypatch.setattr(rag_router.answers, "related_page", authorize)
    monkeypatch.setattr(rag_router, "get_settings", _settings)
    head = await rag_router.get_related_original_pdf_metadata(**arguments)
    assert head.body == b"" and head.headers["content-length"] == str(len(data))
    assert head.headers["x-pdf-page-count"] == str(pdf.page_count)
    response = await rag_router.get_related_original_pdf(**arguments, range_header="bytes=0-7")
    assert response.status_code == 206 and response.body == data[:8]
    assert response.headers["content-range"] == f"bytes 0-7/{len(data)}"
    assert response.headers["cache-control"] == "no-store"
    with pytest.raises(HTTPException) as missing_range:
        await rag_router.get_related_original_pdf(**arguments, range_header=None)
    assert missing_range.value.status_code == 400
    assert len(authorizations) == 3
    assert all(item["subject_id"] == pdf.subject_id and item["job_id"] == arguments["job_id"] for item in authorizations)


async def test_head_rejects_wrong_archive_key_even_when_manifest_matches(monkeypatch):
    _data, _pdf, arguments = _route_fixture()
    async def authorize(*_args, **_kwargs):
        return None
    monkeypatch.setattr(rag_router.answers, "related_page", authorize)
    wrong = _settings().model_copy(update={
        "knowledge_pdf_encryption_key": SecretStr("AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgI"),
    })
    monkeypatch.setattr(rag_router, "get_settings", lambda: wrong)
    with pytest.raises(HTTPException) as denied:
        await rag_router.get_related_original_pdf_metadata(**arguments)
    assert denied.value.status_code == 404
    assert denied.value.detail["code"] == "knowledge_pdf_unavailable"


async def test_head_rejects_incomplete_archive_shape(monkeypatch):
    _data, _pdf, arguments = _route_fixture()
    async def authorize(*_args, **_kwargs):
        return None
    async def incomplete(_query):
        return SimpleNamespace(one=lambda: (0, None, None))
    monkeypatch.setattr(rag_router.answers, "related_page", authorize)
    monkeypatch.setattr(rag_router, "get_settings", _settings)
    monkeypatch.setattr(arguments["db"], "execute", incomplete)
    with pytest.raises(HTTPException) as denied:
        await rag_router.get_related_original_pdf_metadata(**arguments)
    assert denied.value.status_code == 404
    assert denied.value.detail["code"] == "knowledge_pdf_unavailable"


async def test_original_pdf_is_rejected_after_bundle_access_changes(monkeypatch):
    _data, _pdf, arguments = _route_fixture()
    revoked = False
    async def authorize(_db, **_kwargs):
        if revoked:
            raise HTTPException(404, "Current source bundle is unavailable.")
    monkeypatch.setattr(rag_router.answers, "related_page", authorize)
    monkeypatch.setattr(rag_router, "get_settings", _settings)
    assert (await rag_router.get_related_original_pdf_metadata(**arguments)).status_code == 200
    revoked = True
    for function in (rag_router.get_related_original_pdf_metadata, rag_router.get_related_original_pdf):
        with pytest.raises(HTTPException) as denied:
            await function(**arguments)
        assert denied.value.status_code == 404


@pytest.mark.parametrize("field,value", [
    ("document_id", uuid4()), ("subject_id", uuid4()), ("uploader_id", uuid4()),
    ("source_sha256", "f"*64), ("page_count", 99),
])
async def test_pdf_archive_cannot_use_stale_or_mismatched_reference(monkeypatch, field, value):
    _data, pdf, arguments = _route_fixture()
    async def authorize(*_args, **_kwargs):
        return None
    monkeypatch.setattr(rag_router.answers, "related_page", authorize)
    setattr(pdf, field, value)
    with pytest.raises(HTTPException) as denied:
        await rag_router.get_related_original_pdf_metadata(**arguments)
    assert denied.value.status_code == 404
