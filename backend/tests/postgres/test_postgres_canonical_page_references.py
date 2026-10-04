"""Canonical-page references in a guarded synthetic disposable PostgreSQL DB."""

from datetime import timedelta
from dataclasses import replace
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select, text
from sqlalchemy.exc import DBAPIError

from app.models.flashcard import Enrollment
from app.models.knowledge import SubjectDocumentChunk, SubjectDocumentContentRevision, SubjectDocumentPage
from app.models.rag import RagAnswerJob, RagMessage, RagRelatedEvidence
from app.models.user import User
from app.services.knowledge_retrieval import SOURCE_NAVIGATION_RETRIEVAL_POLICY
from app.services.rag_answers import RagAnswerService, _read_related_pages
from app.services.privacy import export_account
from app.time_utils import utcnow
from tests.postgres.test_postgres_rag_answers import _ready_course, _student_and_job


pytestmark = pytest.mark.postgres


@pytest.fixture(autouse=True)
def source_only_policy(monkeypatch):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", "related_knowledge_navigation_v3")


@pytest_asyncio.fixture(autouse=True)
async def clean_owned_course_and_students(postgres_session_factory, monkeypatch):
    """Keep committed reference fixtures out of later quota and queue tests."""

    owners, students = [], []
    ready_course, student_and_job = _ready_course, _student_and_job

    async def tracked_course(*args, **kwargs):
        result = await ready_course(*args, **kwargs)
        owners.append(result[1])
        return result

    async def tracked_student(*args, **kwargs):
        result = await student_and_job(*args, **kwargs)
        students.append(result[0])
        return result

    monkeypatch.setitem(globals(), "_ready_course", tracked_course)
    monkeypatch.setitem(globals(), "_student_and_job", tracked_student)
    try:
        yield
    finally:
        async with postgres_session_factory() as db:
            async with db.begin():
                for ids in (students, owners):
                    if ids:
                        await db.execute(delete(User).where(User.id.in_(ids)))


async def _running_reference(session_factory, job_id, chunk_id):
    async with session_factory() as db:
        async with db.begin():
            job = await db.get(RagAnswerJob, job_id, with_for_update=True)
            assert job is not None
            question = await db.get(RagMessage, job.question_message_id)
            chunk = await db.get(SubjectDocumentChunk, chunk_id)
            assert question is not None and chunk is not None
            page = await db.scalar(select(SubjectDocumentPage).where(
                SubjectDocumentPage.content_revision_id == chunk.content_revision_id,
                SubjectDocumentPage.page_number == chunk.page_number,
            ))
            assert page is not None
            now = utcnow()
            job.status = "running"
            job.attempt_count += 1
            job.worker_id = "canonical-page-reference-worker"
            job.claim_token = "c" * 64
            job.heartbeat_at = now
            job.lease_expires_at = min(job.deadline_at, now + timedelta(seconds=30))
            job.provider_call_started_at = now
            job.retrieval_completed_at = now
            await db.flush()
            fields = dict(
                job_id=job.id, excerpt_order=1, bundle_size=1,
                thread_id=job.thread_id, user_id=job.user_id, subject_id=job.subject_id,
                chunk_id=chunk.id, document_id=chunk.document_id,
                content_revision_id=chunk.content_revision_id,
                index_revision_id=chunk.index_revision_id, source_kind="canonical_page",
                start_offset=0, end_offset=len(page.content), manual_retry_number=job.manual_retry_count,
                created_at=now, expires_at=question.expires_at,
            )
            return fields, page.content, chunk.content


async def test_canonical_page_reference_preserves_heading_and_opens_exact_offsets(
    postgres_engine, postgres_session_factory,
):
    settings, _owner, subject_id, content_id, chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory,
    )
    student_id, _auth, thread_id, job_id = await _student_and_job(
        postgres_session_factory, settings, subject_id, key=f"canonical-page-{uuid4().hex}",
    )
    fields, page_text, chunk_text = await _running_reference(postgres_session_factory, job_id, chunk_id)
    assert page_text.startswith("Foundations\n") and not chunk_text.startswith("Foundations")
    assert len(page_text) > len(chunk_text)
    async with postgres_session_factory() as db:
        async with db.begin():
            db.add(RagRelatedEvidence(**fields))
            await db.flush()
            job = await db.get(RagAnswerJob, job_id, with_for_update=True)
            assert job.retrieval_policy == "hybrid_source_navigation_v9"
            job.status = "completed"
            job.result_kind = "related_knowledge"
            job.completed_at = utcnow()
            job.worker_id = job.claim_token = job.heartbeat_at = job.lease_expires_at = None
            await db.flush()

    service = RagAnswerService(settings)
    async with postgres_session_factory() as db:
        student = await db.get(User, student_id)
        jobs = await service.list_jobs(db, subject_id=subject_id, thread_id=thread_id, user=student, limit=10)
        assert jobs.jobs[0].related_excerpts[0].source_quote == page_text
        page = await service.related_page(
            db, subject_id=subject_id, thread_id=thread_id, job_id=job_id,
            excerpt_order=1, user=student,
        )
        assert (page.reference_start, page.reference_end) == (0, len(page_text))
        assert page.page_content[page.reference_start:page.reference_end] == page.source_quote == page_text
        row = await db.get(RagRelatedEvidence, (job_id, 1))
        assert row.source_kind == "canonical_page"
    async with postgres_session_factory() as db:
        exported = await export_account(db, student_id)
        reference = exported["rag_related_evidence"][0]
        assert reference["source_kind"] == "canonical_page"
        assert (reference["start_offset"], reference["end_offset"]) == (0, len(page_text))
        assert "source_quote" not in reference and "page_content" not in reference

    async with postgres_session_factory() as db:
        async with db.begin():
            revision = await db.get(SubjectDocumentContentRevision, content_id, with_for_update=True)
            revision.published_at = None
    async with postgres_session_factory() as db:
        student = await db.get(User, student_id)
        jobs = await service.list_jobs(db, subject_id=subject_id, thread_id=thread_id, user=student, limit=10)
        assert jobs.jobs[0].related_excerpts == []
        with pytest.raises(HTTPException) as denied:
            await service.related_page(
                db, subject_id=subject_id, thread_id=thread_id, job_id=job_id,
                excerpt_order=1, user=student,
            )
        assert denied.value.status_code == 404


async def test_canonical_reference_trigger_rejects_invalid_kinds_scopes_offsets_and_expiry(
    postgres_engine, postgres_session_factory,
):
    settings, _owner, subject_id, _content_id, chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory,
    )
    _student, _auth, _thread, job_id = await _student_and_job(
        postgres_session_factory, settings, subject_id, key=f"canonical-guards-{uuid4().hex}",
    )
    fields, page_text, chunk_text = await _running_reference(postgres_session_factory, job_id, chunk_id)
    for change in (
        {"source_kind": "invented"},
        {"source_kind": "chunk"},  # Page offsets cannot be accepted as chunk offsets.
        {"end_offset": len(page_text) + 1},
        {"start_offset": -1},
        {"end_offset": 481},
        {"start_offset": len("Foundations"), "end_offset": len("Foundations") + 2},
        {"document_id": uuid4()},
        {"subject_id": uuid4()},
        {"content_revision_id": uuid4()},
        {"index_revision_id": uuid4()},
        {"manual_retry_number": 1},
        {"expires_at": fields["expires_at"] + timedelta(seconds=1)},
    ):
        with pytest.raises(DBAPIError):
            async with postgres_session_factory() as db:
                async with db.begin():
                    db.add(RagRelatedEvidence(**(fields | change)))
                    await db.flush()
    assert len(page_text) > len(chunk_text)
    async with postgres_session_factory() as db:
        async with db.begin():
            # Omitting the source kind still means a historical chunk reference.
            historical = fields | {"end_offset": len(chunk_text)}
            historical.pop("source_kind")
            db.add(RagRelatedEvidence(**historical))
            await db.flush()
    async with postgres_session_factory() as db:
        row = await db.get(RagRelatedEvidence, (job_id, 1))
        assert row.source_kind == "chunk"


@pytest.mark.parametrize("old_policy", ["hybrid_source_sufficiency_v5", "hybrid_source_sufficiency_v6", "hybrid_source_sufficiency_v7"])
async def test_old_selector_snapshot_cannot_insert_canonical_page_reference(
    postgres_engine, postgres_session_factory, monkeypatch, old_policy,
):
    settings, _owner, subject_id, _content_id, chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory,
    )
    with monkeypatch.context() as stale:
        stale.setattr(
            "app.services.rag_answers.SOURCE_NAVIGATION_RETRIEVAL_POLICY",
            replace(SOURCE_NAVIGATION_RETRIEVAL_POLICY, policy_id=old_policy),
        )
        _student, _auth, _thread, job_id = await _student_and_job(
            postgres_session_factory, settings, subject_id,
            key=f"canonical-old-policy-{uuid4().hex}",
        )
    fields, _page_text, _chunk_text = await _running_reference(
        postgres_session_factory, job_id, chunk_id,
    )
    with pytest.raises(DBAPIError):
        async with postgres_session_factory() as db:
            async with db.begin():
                db.add(RagRelatedEvidence(**fields))
                await db.flush()


async def test_historical_v6_page_reference_remains_readable_after_v7_guard(
    postgres_engine, postgres_session_factory, monkeypatch,
):
    settings, _owner, subject_id, _content_id, chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory,
    )
    with monkeypatch.context() as previous:
        previous.setattr(
            "app.services.rag_answers.SOURCE_NAVIGATION_RETRIEVAL_POLICY",
            replace(SOURCE_NAVIGATION_RETRIEVAL_POLICY, policy_id="hybrid_source_sufficiency_v6"),
        )
        student_id, _auth, thread_id, job_id = await _student_and_job(
            postgres_session_factory, settings, subject_id,
            key=f"canonical-retained-v6-{uuid4().hex}",
            policy_version="related_knowledge_v1",
        )
    fields, page_text, _chunk_text = await _running_reference(
        postgres_session_factory, job_id, chunk_id,
    )
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/20260927_0025_structural_source_policy.py"
    )
    spec = importlib.util.spec_from_file_location("structural_source_policy_fixture", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    # Emulate an existing 0024 row, then install the 0025 guard atomically.
    # Save the installed head's guard before replacing it. Restoring a pinned
    # historical definition would silently downgrade this shared disposable
    # database and make later current-policy tests fail due to test order.
    # A failing fixture rolls back the function replacement as well as its rows.
    async with postgres_session_factory() as db:
        async with db.begin():
            current_guard = await db.scalar(text(
                "SELECT pg_get_functiondef(to_regprocedure('rag_related_evidence_guard()'))"
            ))
            assert isinstance(current_guard, str) and "CREATE OR REPLACE FUNCTION" in current_guard
            await db.execute(text(migration._guard_sql(retrieval_policy="hybrid_source_sufficiency_v6")))
            db.add(RagRelatedEvidence(**fields))
            await db.flush()
            job = await db.get(RagAnswerJob, job_id, with_for_update=True)
            job.status = "completed"
            job.result_kind = "related_knowledge"
            job.completed_at = utcnow()
            job.worker_id = job.claim_token = job.heartbeat_at = job.lease_expires_at = None
            await db.flush()
            # Restore the actual current guard, keeping historical snapshots
            # readable without leaving this shared disposable DB at an old head.
            await db.execute(text(current_guard))
            assert await db.scalar(text(
                "SELECT pg_get_functiondef(to_regprocedure('rag_related_evidence_guard()'))"
            )) == current_guard

    async with postgres_session_factory() as db:
        student = await db.get(User, student_id)
        job = await db.get(RagAnswerJob, job_id)
        assert job.retrieval_policy == "hybrid_source_sufficiency_v6"
        service = RagAnswerService(settings)
        jobs = await service.list_jobs(
            db, subject_id=subject_id, thread_id=thread_id, user=student, limit=10,
        )
        assert jobs.jobs[0].related_excerpts[0].source_quote == page_text
        page = await service.related_page(
            db, subject_id=subject_id, thread_id=thread_id, job_id=job_id,
            excerpt_order=1, user=student,
        )
        assert page.page_content[page.reference_start:page.reference_end] == page_text


async def test_revoked_enrollment_blocks_canonical_insert_and_page_read(
    postgres_engine, postgres_session_factory,
):
    settings, _owner, subject_id, _content_id, chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory,
    )
    student_id, _auth, _thread, job_id = await _student_and_job(
        postgres_session_factory, settings, subject_id,
        key=f"canonical-revoked-{uuid4().hex}",
    )
    fields, _page_text, _chunk_text = await _running_reference(
        postgres_session_factory, job_id, chunk_id,
    )
    async with postgres_session_factory() as db:
        async with db.begin():
            enrollment = await db.scalar(select(Enrollment).where(
                Enrollment.student_id == student_id,
                Enrollment.subject_id == subject_id,
            ))
            assert enrollment is not None
            await db.delete(enrollment)
    with pytest.raises(DBAPIError):
        async with postgres_session_factory() as db:
            async with db.begin():
                db.add(RagRelatedEvidence(**fields))
                await db.flush()
    async with postgres_session_factory() as db:
        job = await db.get(RagAnswerJob, job_id)
        assert await _read_related_pages(
            db, principal_id=student_id, subject_id=subject_id,
            corpus_revision=job.corpus_revision,
            embedding_space_hash=job.embedding_space_hash,
            chunk_ids=[chunk_id],
        ) == {}
