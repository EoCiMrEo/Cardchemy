"""Disposable PostgreSQL guards for private, source-exact related excerpts."""

from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app.models.flashcard import Enrollment
from app.models.knowledge import SubjectDocumentChunk, SubjectDocumentContentRevision
from app.models.rag import RagAnswerJob, RagMessage, RagRelatedEvidence
from app.models.user import User
from app.services.knowledge_retrieval import read_eligible_source_batch
from app.services.rag_answers import RagAnswerService
from app.time_utils import utcnow
from app.workers.rag_answer import RagAnswerWorker
from tests.postgres.test_postgres_rag_answers import (
    _ready_course,
    _student_and_job,
)
from tests.postgres.test_postgres_rag_pipeline import FakeEmbeddingProvider


pytestmark = pytest.mark.postgres


@pytest.fixture(autouse=True)
def source_only_policy(monkeypatch):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", "related_knowledge_navigation_v3")


async def _stage_related_reference(
    session_factory, *, job_id, chunk_id, failed: bool,
) -> str:
    """Store one exact synthetic-course reference while its claim is current."""

    async with session_factory() as db:
        async with db.begin():
            job = await db.get(RagAnswerJob, job_id, with_for_update=True)
            assert job is not None
            question = await db.get(RagMessage, job.question_message_id)
            chunk = await db.get(SubjectDocumentChunk, chunk_id)
            assert question is not None and chunk is not None
            now = utcnow()
            job.status = "running"
            job.attempt_count += 1
            job.worker_id = "related-evidence-read-worker"
            job.claim_token = "b" * 64
            job.heartbeat_at = now
            job.lease_expires_at = min(job.deadline_at, now + timedelta(seconds=30))
            job.provider_call_started_at = now
            job.retrieval_completed_at = now
            await db.flush()
            quote = chunk.content[:min(40, len(chunk.content))]
            db.add(RagRelatedEvidence(
                job_id=job.id, excerpt_order=1, bundle_size=1,
                thread_id=job.thread_id, user_id=job.user_id,
                subject_id=job.subject_id, chunk_id=chunk.id,
                document_id=chunk.document_id,
                content_revision_id=chunk.content_revision_id,
                index_revision_id=chunk.index_revision_id,
                start_offset=0, end_offset=len(quote),
                manual_retry_number=job.manual_retry_count,
                created_at=now, expires_at=question.expires_at,
            ))
            await db.flush()
            if failed:
                await RagAnswerWorker._fail_locked(
                    job, "rag_answer_failed", "Answer generation failed.", retryable=False,
                )
    return quote


@pytest.mark.parametrize("revocation", ["unpublish", "unenroll"])
async def test_related_read_uses_current_postgres_source_and_principal_scope(
    postgres_engine, postgres_session_factory, revocation
):
    configured, _owner_id, subject_id, content_id, chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory
    )
    user_id, _auth_id, thread_id, job_id = await _student_and_job(
        postgres_session_factory, configured, subject_id,
        key=f"related-evidence-read-{revocation}-0001",
    )
    expected_quote = await _stage_related_reference(
        postgres_session_factory, job_id=job_id, chunk_id=chunk_id, failed=True,
    )
    service = RagAnswerService(configured)
    async with postgres_session_factory() as db:
        student = await db.get(User, user_id)
        assert student is not None
        current = await read_eligible_source_batch(
            db, principal_id=user_id, subject_id=subject_id, chunk_ids=[chunk_id],
        )
        assert current[chunk_id].content.startswith(expected_quote)
        jobs = await service.list_jobs(
            db, subject_id=subject_id, thread_id=thread_id, user=student, limit=10,
        )
        assert len(jobs.jobs) == 1
        assert [item.source_quote for item in jobs.jobs[0].related_excerpts] == [expected_quote]

    async with postgres_session_factory() as db:
        async with db.begin():
            if revocation == "unpublish":
                content = await db.get(
                    SubjectDocumentContentRevision, content_id, with_for_update=True,
                )
                assert content is not None
                content.published_at = None
            else:
                enrollment = await db.scalar(select(Enrollment).where(
                    Enrollment.student_id == user_id,
                    Enrollment.subject_id == subject_id,
                ).with_for_update())
                assert enrollment is not None
                await db.delete(enrollment)

    async with postgres_session_factory() as db:
        student = await db.get(User, user_id)
        assert student is not None
        assert await read_eligible_source_batch(
            db, principal_id=user_id, subject_id=subject_id, chunk_ids=[chunk_id],
        ) == {}
        if revocation == "unpublish":
            jobs = await service.list_jobs(
                db, subject_id=subject_id, thread_id=thread_id, user=student, limit=10,
            )
            assert len(jobs.jobs) == 1
            assert jobs.jobs[0].related_excerpts == []
        else:
            with pytest.raises(HTTPException) as denied:
                await service.list_jobs(
                    db, subject_id=subject_id, thread_id=thread_id, user=student, limit=10,
                )
            assert denied.value.status_code == 403


async def test_source_read_keeps_two_published_subjects_isolated_for_one_student(
    postgres_engine, postgres_session_factory,
):
    configured, _owner_a, subject_a, _content_a, chunk_a = await _ready_course(
        postgres_engine, postgres_session_factory,
    )
    _configured_b, _owner_b, subject_b, _content_b, chunk_b = await _ready_course(
        postgres_engine, postgres_session_factory,
    )
    student_id, _auth_id, _thread_id, _job_id = await _student_and_job(
        postgres_session_factory, configured, subject_a,
        key="related-two-subjects-one-student-0001",
    )
    async with postgres_session_factory() as db:
        async with db.begin():
            db.add(Enrollment(student_id=student_id, subject_id=subject_b))

    async with postgres_session_factory() as db:
        first = await read_eligible_source_batch(
            db, principal_id=student_id, subject_id=subject_a,
            chunk_ids=[chunk_a, chunk_b],
        )
        second = await read_eligible_source_batch(
            db, principal_id=student_id, subject_id=subject_b,
            chunk_ids=[chunk_a, chunk_b],
        )
    assert set(first) == {chunk_a}
    assert set(second) == {chunk_b}


async def test_expired_lease_cancellation_deletes_related_references(
    postgres_engine, postgres_session_factory
):
    configured, _owner_id, subject_id, _content_id, chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory
    )
    _user_id, _auth_id, _thread_id, job_id = await _student_and_job(
        postgres_session_factory, configured, subject_id,
        key="related-evidence-lease-cancel-0001",
    )
    await _stage_related_reference(
        postgres_session_factory, job_id=job_id, chunk_id=chunk_id, failed=False,
    )
    async with postgres_session_factory() as db:
        async with db.begin():
            job = await db.get(RagAnswerJob, job_id, with_for_update=True)
            assert job is not None
            job.cancellation_requested_at = utcnow()
            job.lease_expires_at = utcnow() - timedelta(seconds=1)
            job.heartbeat_at = job.lease_expires_at

    worker = RagAnswerWorker(
        settings=configured, session_factory=postgres_session_factory,
        embedding_provider=FakeEmbeddingProvider(),
        worker_id="related-evidence-recovery-worker",
    )
    await worker.recover_expired()
    async with postgres_session_factory() as db:
        job = await db.get(RagAnswerJob, job_id)
        assert job is not None and job.status == "cancelled"
        assert (await db.scalars(select(RagRelatedEvidence).where(
            RagRelatedEvidence.job_id == job_id,
        ))).all() == []


async def test_related_evidence_requires_current_scoped_published_source(
    postgres_engine, postgres_session_factory
):
    configured, _owner_id, subject_id, content_id, chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory
    )
    user_id, _auth_id, thread_id, job_id = await _student_and_job(
        postgres_session_factory, configured, subject_id, key="related-evidence-schema-0001"
    )
    async with postgres_session_factory() as db:
        async with db.begin():
            job = await db.get(RagAnswerJob, job_id, with_for_update=True)
            question = await db.get(RagMessage, job.question_message_id)
            chunk = await db.get(SubjectDocumentChunk, chunk_id)
            assert question is not None and chunk is not None
            now = utcnow()
            job.status = "running"
            job.attempt_count += 1
            job.worker_id = "related-evidence-schema-worker"
            job.claim_token = "a" * 64
            job.heartbeat_at = now
            job.lease_expires_at = min(job.deadline_at, now + timedelta(seconds=30))
            job.provider_call_started_at = now
            job.retrieval_completed_at = now
            await db.flush()
            fields = dict(
                job_id=job_id,
                thread_id=thread_id,
                user_id=user_id,
                subject_id=subject_id,
                chunk_id=chunk_id,
                document_id=chunk.document_id,
                content_revision_id=chunk.content_revision_id,
                index_revision_id=chunk.index_revision_id,
                start_offset=0,
                end_offset=min(40, len(chunk.content)),
                manual_retry_number=job.manual_retry_count,
                expires_at=question.expires_at,
            )
            db.add(RagRelatedEvidence(excerpt_order=1, bundle_size=1, **fields))
            await db.flush()

    async with postgres_session_factory() as db:
        row = await db.scalar(select(RagRelatedEvidence).where(RagRelatedEvidence.job_id == job_id))
        assert row is not None and row.excerpt_order == 1

    for changes in (
        {"manual_retry_number": 1},
        {"user_id": uuid4()},
        {"end_offset": len(chunk.content) + 1},
        {"start_offset": -1},
        {"excerpt_order": 3},
    ):
        invalid = dict(fields)
        invalid.update(changes)
        order = invalid.pop("excerpt_order", 2)
        with pytest.raises(DBAPIError):
            async with postgres_session_factory() as db:
                async with db.begin():
                    db.add(RagRelatedEvidence(excerpt_order=order, bundle_size=2, **invalid))
                    await db.flush()

    with pytest.raises(DBAPIError):
        async with postgres_session_factory() as db:
            async with db.begin():
                row = await db.get(RagRelatedEvidence, (job_id, 1))
                assert row is not None
                row.start_offset = 1
                await db.flush()

    async with postgres_session_factory() as db:
        async with db.begin():
            content = await db.get(SubjectDocumentContentRevision, content_id, with_for_update=True)
            assert content is not None
            content.published_at = None

    with pytest.raises(DBAPIError):
        async with postgres_session_factory() as db:
            async with db.begin():
                db.add(RagRelatedEvidence(excerpt_order=2, bundle_size=2, **fields))
                await db.flush()
