"""Disposable PostgreSQL acceptance for source-only Ask AI.

The fixtures use a synthetic published page and an offline embedding provider.
No answer model or local answer verifier participates in these tests.
"""

from datetime import timedelta
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.flashcard import Enrollment
from app.models.knowledge import SubjectDocumentContentRevision
from app.models.rag import RagAnswerJob, RagAnswerQuotaEvent, RagAnswerStageAttempt, RagMessage, RagRelatedEvidence
from app.models.user import AuthSession, User, UserRole
from app.schemas.rag import RagQuestionCreate
from app.services.knowledge_retrieval import SOURCE_NAVIGATION_RETRIEVAL_POLICY
from app.services.rag_answers import RagAnswerService
from app.time_utils import utcnow
from app.workers.rag_answer import RagAnswerWorker
from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION
from tests.support.visual_renderer import fake_visual_renderer
from tests.postgres.test_postgres_rag_answers import (
    FakeSourceJudge, _ready_course, _student_and_job, _student_and_current_job,
)
from tests.postgres.test_postgres_rag_pipeline import FakeEmbeddingProvider


pytestmark = pytest.mark.postgres


@pytest.fixture(autouse=True)
def current_visual_profile(monkeypatch):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", ASK_REQUIRED_RELEASE_POLICY_VERSION)
    fake_visual_renderer(monkeypatch)


async def _complete_related_job(postgres_engine, session_factory, monkeypatch):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", ASK_REQUIRED_RELEASE_POLICY_VERSION)
    settings, owner_id, subject_id, content_id, chunk_id = await _ready_course(
        postgres_engine, session_factory,
    )
    student_id, _auth_id, thread_id, job_id = await _student_and_current_job(
        session_factory, settings, subject_id, key=f"source-only-{uuid4().hex}",
    )
    # Other disposable tests intentionally leave queued jobs in this shared
    # database. Make this test's job the next deterministic claim.
    async with session_factory() as db:
        async with db.begin():
            job = await db.get(RagAnswerJob, job_id, with_for_update=True)
            assert job is not None
            job.available_at = utcnow() - timedelta(hours=1)
    judge = FakeSourceJudge()
    worker = RagAnswerWorker(
        settings=settings, session_factory=session_factory,
        embedding_provider=FakeEmbeddingProvider(), source_judge=judge,
        worker_id=f"source-{uuid4().hex}",
    )
    claim = await worker.claim_next()
    assert claim is not None and claim[0] == job_id
    await worker.process_claim(*claim)
    assert judge.calls == 1
    return settings, owner_id, subject_id, content_id, chunk_id, student_id, thread_id, job_id


async def test_published_page_creates_only_exact_related_reference(
    postgres_engine, postgres_session_factory, monkeypatch,
):
    (settings, owner_id, subject_id, _content_id, chunk_id,
     student_id, thread_id, job_id) = await _complete_related_job(
        postgres_engine, postgres_session_factory, monkeypatch,
    )
    service = RagAnswerService(settings)
    async with postgres_session_factory() as db:
        job = await db.get(RagAnswerJob, job_id)
        assert job is not None
        assert (job.status, job.result_kind, job.answer_message_id) == (
            "completed", "related_knowledge", None,
        )
        assert job.provider_request_count == 2 and job.provider_retry_count == 0
        assert job.actual_output_tokens == 8
        assert job.ai_provider is None and job.ai_model is None
        stages = (await db.scalars(select(RagAnswerStageAttempt).where(
            RagAnswerStageAttempt.job_id == job_id,
        ).order_by(RagAnswerStageAttempt.started_at, RagAnswerStageAttempt.id))).all()
        assert [(stage.stage, stage.physical_request_count) for stage in stages] == [
            ("query_embedding", 1), ("retrieval", 0), ("source_judgment", 1),
        ]
        messages = (await db.scalars(select(RagMessage).where(
            RagMessage.thread_id == thread_id,
        ))).all()
        assert [(message.role, message.content) for message in messages] == [
            ("user", "What does the course say about alpha?"),
        ]
        refs = (await db.scalars(select(RagRelatedEvidence).where(
            RagRelatedEvidence.job_id == job_id,
        ))).all()
        assert len(refs) == 1 and refs[0].chunk_id == chunk_id
        student = await db.get(User, student_id)
        assert student is not None
        jobs = await service.list_jobs(
            db, subject_id=subject_id, thread_id=thread_id, user=student, limit=10,
        )
        excerpt = jobs.jobs[0].related_excerpts[0]
        assert "Alpha is the first concept" in excerpt.source_quote
        page = await service.related_page(
            db, subject_id=subject_id, thread_id=thread_id, job_id=job_id,
            excerpt_order=1, user=student,
        )
        assert page.page_number == 1
        assert "Alpha is the first concept" in page.page_content
        assert page.source_quote in page.page_content
        assert page.reference_start is not None and page.reference_end is not None
        assert page.page_content[page.reference_start:page.reference_end] == page.source_quote
        owner = await db.get(User, owner_id)
        assert owner is not None
        with pytest.raises(HTTPException) as forbidden:
            await service.related_page(
                db, subject_id=subject_id, thread_id=thread_id, job_id=job_id,
                excerpt_order=1, user=owner,
            )
        assert forbidden.value.status_code == 404


async def test_unpublishing_hides_whole_related_bundle_and_page(
    postgres_engine, postgres_session_factory, monkeypatch,
):
    (settings, _owner_id, subject_id, content_id, _chunk_id,
     student_id, thread_id, job_id) = await _complete_related_job(
        postgres_engine, postgres_session_factory, monkeypatch,
    )
    async with postgres_session_factory() as db:
        async with db.begin():
            content = await db.get(
                SubjectDocumentContentRevision, content_id, with_for_update=True,
            )
            assert content is not None
            content.published_at = None
    service = RagAnswerService(settings)
    async with postgres_session_factory() as db:
        student = await db.get(User, student_id)
        assert student is not None
        jobs = await service.list_jobs(
            db, subject_id=subject_id, thread_id=thread_id, user=student, limit=10,
        )
        assert jobs.jobs[0].related_excerpts == []
        with pytest.raises(HTTPException) as unavailable:
            await service.related_page(
                db, subject_id=subject_id, thread_id=thread_id, job_id=job_id,
                excerpt_order=1, user=student,
            )
        assert unavailable.value.status_code == 404


@pytest.mark.parametrize("old_policy", ["hybrid_source_sufficiency_v4", "hybrid_source_sufficiency_v6"])
async def test_old_source_retrieval_policy_retry_is_hidden_and_rejected_before_quota(
    postgres_engine, postgres_session_factory, monkeypatch, old_policy,
):
    """Stale source policy remains readable but cannot reserve a paid retry."""
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", ASK_REQUIRED_RELEASE_POLICY_VERSION)
    settings, _owner_id, subject_id, _content_id, _chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory,
    )
    # Enqueue under the old immutable snapshot rather than rewriting a
    # persisted identity, which PostgreSQL correctly forbids.
    with monkeypatch.context() as legacy_policy:
        legacy_policy.setattr("app.services.rag_answers.SOURCE_NAVIGATION_RETRIEVAL_POLICY",
                              replace(SOURCE_NAVIGATION_RETRIEVAL_POLICY,
                                      policy_id=old_policy))
        student_id, auth_id, thread_id, job_id = await _student_and_job(
            postgres_session_factory, settings, subject_id, key=f"stale-retry-{uuid4().hex}",
        )
    async with postgres_session_factory() as db:
        async with db.begin():
            job = await db.get(RagAnswerJob, job_id, with_for_update=True)
            assert job is not None
            job.status = "failed"
            job.completed_at = utcnow()
            job.error_code = "rag_answer_failed"
            job.error_message = "Answer generation failed."
            job.error_retryable = True

    service = RagAnswerService(settings)
    async with postgres_session_factory() as db:
        async with db.begin():
            student = await db.get(User, student_id)
            assert student is not None
            setattr(student, "_auth_session_id", auth_id)
            jobs = await service.list_jobs(
                db, subject_id=subject_id, thread_id=thread_id, user=student, limit=10,
            )
            assert jobs.jobs[0].can_retry is False
            baseline = await db.scalar(select(func.count()).select_from(RagAnswerQuotaEvent)
                                       .where(RagAnswerQuotaEvent.job_id == job_id))
            # Commit after catching: a rollback cannot conceal quota mutations.
            with pytest.raises(HTTPException) as rejected:
                await service.retry(
                    db, subject_id=subject_id, thread_id=thread_id, job_id=job_id,
                    user=student, idempotency_key=f"refused-retry-{uuid4().hex}",
                )
            assert rejected.value.status_code == 409
            assert rejected.value.detail["code"] == "rag_answer_not_retryable"
            assert await db.scalar(select(func.count()).select_from(RagAnswerQuotaEvent)
                                   .where(RagAnswerQuotaEvent.job_id == job_id)) == baseline
            history = await service.history(
                db, subject_id=subject_id, thread_id=thread_id, user=student, limit=10,
            )
            assert len(history.messages) == 1 and history.messages[0].role == "user"

    async with postgres_session_factory() as db:
        job = await db.get(RagAnswerJob, job_id)
        assert job is not None and job.status == "failed"
        assert job.manual_retry_count == job.provider_request_count == 0
        assert job.provider_call_started_at is None
        assert await db.scalar(select(func.count()).select_from(RagAnswerQuotaEvent)
                               .where(RagAnswerQuotaEvent.job_id == job_id)) == baseline


async def test_ambiguous_question_requests_clarification_without_embedding(
    postgres_engine, postgres_session_factory, monkeypatch,
):
    """An unresolved follow-up completes without sending history to a provider."""
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", ASK_REQUIRED_RELEASE_POLICY_VERSION)
    settings, _owner_id, subject_id, _content_id, _chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory,
    )
    service = RagAnswerService(settings)
    student_id = uuid4()
    async with postgres_session_factory() as db:
        async with db.begin():
            student = User(
                id=student_id,
                email=f"rag-ambiguous-{student_id.hex}@example.test",
                hashed_password="fixture",
                role=UserRole.STUDENT,
            )
            db.add(student)
            await db.flush()
            db.add(Enrollment(student_id=student.id, subject_id=subject_id))
            auth = AuthSession(
                user_id=student.id,
                refresh_jti_hash=uuid4().hex * 2,
                expires_at=utcnow() + timedelta(hours=1),
            )
            db.add(auth)
            await db.flush()
            setattr(student, "_auth_session_id", auth.id)
            thread = await service.create_thread(db, subject_id=subject_id, user=student)
            job = await service.enqueue(
                db, subject_id=subject_id, thread_id=thread.id, user=student,
                data=RagQuestionCreate(question="What does it stand for?"),
                idempotency_key=f"ambiguous-{uuid4().hex}",
            )
            job_id = job.id

    async with postgres_session_factory() as db:
        async with db.begin():
            job = await db.get(RagAnswerJob, job_id, with_for_update=True)
            assert job is not None
            job.available_at = utcnow() - timedelta(hours=1)

    class NeverEmbedding:
        async def embed_query(self, _question):
            pytest.fail("Ambiguous question called an embedding provider")

    worker = RagAnswerWorker(
        settings=settings, session_factory=postgres_session_factory,
        embedding_provider=NeverEmbedding(), worker_id=f"ambiguous-{uuid4().hex}",
    )
    claim = await worker.claim_next()
    assert claim is not None and claim[0] == job_id
    await worker.process_claim(*claim)

    async with postgres_session_factory() as db:
        stored = await db.get(RagAnswerJob, job_id)
        assert stored is not None
        assert (stored.status, stored.result_kind, stored.provider_request_count) == (
            "completed", "clarification_needed", 0,
        )
        assert stored.retrieval_completed_at is None
        assert stored.provider_call_started_at is None
        assert stored.answer_message_id is None
        assert stored.error_code is None and stored.provider_error_category is None
        assert (await db.scalars(select(RagAnswerStageAttempt).where(
            RagAnswerStageAttempt.job_id == job_id,
        ))).all() == []
        assert (await db.scalars(select(RagRelatedEvidence).where(
            RagRelatedEvidence.job_id == job_id,
        ))).all() == []
        assert (await db.scalars(select(RagMessage.role).where(
            RagMessage.thread_id == thread.id,
        ))).all() == ["user"]
