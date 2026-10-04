"""Disposable PostgreSQL fixtures and guards for source-only Subject Ask AI."""

from datetime import timedelta
import json
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION
from app.models.flashcard import Enrollment
from app.models.generation import GenerationJob
from app.models.knowledge import SubjectDocumentChunk, SubjectDocumentContentRevision
from app.models.rag import (
    RagAnswerJob,
    RagAnswerQuotaEvent,
    RagAnswerStageAttempt,
    RagMessage,
    RagThread,
)
from app.models.user import AuthSession, User, UserRole
from app.schemas.rag import RagQuestionCreate
from app.services.knowledge_indexing import cutover_subject_embedding_space
from app.services.knowledge_retrieval import KnowledgeRetriever
from app.services.generation import hash_operation_key
from app.services import rag_answers as rag_answer_module
from app.services.rag_answers import RagAnswerService
from app.time_utils import utcnow
from app.workers.knowledge_index import KnowledgeIndexWorker
from app.workers.rag_answer import AnswerProfileMismatch, RagAnswerWorker
from app.workers.rag_answer import _JudgeResponse
from tests.postgres.test_postgres_rag_pipeline import (
    FakeEmbeddingProvider,
    seed_capture,
    settings as index_settings,
)
from tests.test_pdf_processor import pdf_bytes


pytestmark = pytest.mark.postgres


@pytest.fixture(autouse=True)
def source_only_policy(monkeypatch):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", ASK_REQUIRED_RELEASE_POLICY_VERSION)


def _answer_settings(database_url: str):
    return index_settings(database_url).model_copy(update={
        "rag_ask_enabled": True,
        "rag_source_judge_provider_enabled": True,
        "rag_source_judge_api_key": "test-only-source-judge-key",
        "rag_source_judge_quota_bucket": "disposable-test-project",
        "rag_answer_max_active_jobs_per_user": 1,
        "rag_answer_max_active_jobs_deployment": 10,
    })


class FakeSourceJudge:
    """Offline categorical visual verdict for current-policy worker tests."""

    def __init__(self, selected_ids=("S01",)):
        self.selected_ids = selected_ids
        self.calls = 0

    async def judge(self, wire, *, before_dispatch=None):
        if before_dispatch is not None:
            await before_dispatch()
        self.calls += 1
        parts = wire["contents"][0]["parts"]
        candidates = {json.loads(part["text"])["id"] for part in parts[1:] if "text" in part}
        assert sum("inline_data" in part for part in parts) == len(candidates)
        assert set(self.selected_ids).issubset(candidates)
        return _JudgeResponse(
            json.dumps({"question_status": "clear", "pages": [
                {"id": sid, "usefulness": "direct" if sid in self.selected_ids else "unrelated",
                 "cue_locates": sid in self.selected_ids} for sid in sorted(candidates)]}),
            "STOP", 100, 8, 0,
        )


async def _ready_course(postgres_engine, session_factory):
    configured = _answer_settings(str(postgres_engine.url))
    owner, subject, captured, _prepared = await seed_capture(
        session_factory,
        configured,
        page_texts=("Foundations\n\nAlpha is the first concept in this course.",),
        original_pdf=pdf_bytes(pages=1, text="Foundations Alpha is the first concept in this course."),
    )
    indexer = KnowledgeIndexWorker(
        settings=configured,
        session_factory=session_factory,
        provider=FakeEmbeddingProvider(),
        worker_id=f"index-{uuid4().hex}",
    )
    claim = await indexer.claim_next()
    assert claim and claim[0] == captured.index_job_id
    await indexer.process_claim(*claim)
    async with session_factory() as db:
        async with db.begin():
            content = await db.get(
                SubjectDocumentContentRevision, captured.content_revision_id, with_for_update=True
            )
            content.reviewed_by_id = owner.id
            content.reviewed_at = utcnow()
            content.published_at = utcnow()
    async with session_factory() as db:
        async with db.begin():
            assert await cutover_subject_embedding_space(
                db,
                subject_id=subject.id,
                owner_id=owner.id,
                target_space_hash=indexer.space_hash,
            ) == 1
            # seed_capture models the capture point inside a still-running
            # knowledge-only job. These answer lifecycle scenarios begin after
            # that independent lane has completed, so do not leave a synthetic
            # active capture that should correctly block document deletion.
            capture_job = await db.scalar(
                select(GenerationJob).where(
                    GenerationJob.knowledge_content_revision_id
                    == captured.content_revision_id
                ).with_for_update()
            )
            assert capture_job is not None
            capture_job.status = "completed"
            capture_job.stage = "completed"
            capture_job.progress = 100
            capture_job.generated_card_count = 0
            capture_job.completed_at = utcnow()
            capture_job.worker_id = None
            capture_job.claim_token = None
            capture_job.heartbeat_at = None
            capture_job.lease_expires_at = None
    async with session_factory() as db:
        chunk = await db.scalar(select(SubjectDocumentChunk).where(
            SubjectDocumentChunk.index_revision_id == captured.index_revision_id
        ).order_by(SubjectDocumentChunk.chunk_index))
        assert chunk is not None and "Alpha is the first concept" in chunk.content
    return configured, owner.id, subject.id, captured.content_revision_id, chunk.id


async def _student_and_job(
    session_factory, configured, subject_id, *, key: str,
    policy_version: str = "related_knowledge_navigation_v3",
):
    """Seed an immutable v3 job for historical storage and read contracts.

    The current API intentionally cannot admit this retired policy.
    """
    student_id = uuid4()
    data = RagQuestionCreate(question="What does the course say about alpha?")
    async with session_factory() as db:
        async with db.begin():
            student = User(
                id=student_id,
                email=f"rag-student-{student_id.hex}@example.test",
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
            now = utcnow()
            thread = RagThread(user_id=student.id, subject_id=subject_id,
                               created_at=now, updated_at=now)
            db.add(thread)
            await db.flush()
            policy = rag_answer_module.SOURCE_NAVIGATION_RETRIEVAL_POLICY
            retriever = await KnowledgeRetriever.authorize(
                db, principal=student, subject_id=subject_id, query=data.question,
                document_ids=data.document_ids, limit=policy.max_results, policy=policy,
            )
            question = RagMessage(
                thread_id=thread.id, user_id=student.id, subject_id=subject_id,
                role="user", content=data.question, source_count=0,
                created_at=now, expires_at=now + timedelta(days=configured.rag_chat_retention_days),
            )
            db.add(question)
            await db.flush()
            job = RagAnswerJob(
                thread_id=thread.id, question_message_id=question.id,
                auth_session_id=auth.id, user_id=student.id, subject_id=subject_id,
                status="queued", operation_key_hash=hash_operation_key(key),
                request_fingerprint=rag_answer_module.question_fingerprint(thread.id, data),
                document_ids=[], corpus_revision=retriever.scope.corpus_revision,
                retrieval_policy=policy.policy_id,
                embedding_space_hash=retriever.scope.embedding_space_hash,
                embedding_provider=configured.rag_embedding_provider,
                embedding_base_url=configured.rag_embedding_endpoint_identity,
                embedding_model=configured.rag_embedding_model,
                answer_policy_version=policy_version,
                max_attempts=configured.rag_answer_max_attempts,
                available_at=now + timedelta(minutes=30),
                deadline_at=now + timedelta(hours=1),
                created_at=now, updated_at=now,
            )
            db.add(job)
            await db.flush()
            db.add(RagAnswerQuotaEvent(
                user_id=student.id, job_id=job.id,
                operation_key_hash=hash_operation_key(key), job_units=1, created_at=now,
            ))
        return student.id, auth.id, thread.id, job.id


async def _student_and_current_job(session_factory, configured, subject_id, *, key: str):
    service = RagAnswerService(configured)
    student_id = uuid4()
    async with session_factory() as db:
        async with db.begin():
            student = User(
                id=student_id,
                email=f"rag-student-{student_id.hex}@example.test",
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
                db,
                subject_id=subject_id,
                thread_id=thread.id,
                user=student,
                data=RagQuestionCreate(question="What does the course say about alpha?"),
                idempotency_key=key,
            )
        return student.id, auth.id, thread.id, job.id


async def test_source_only_stage_guard_rejects_answer_and_second_embedding(
    postgres_engine, postgres_session_factory,
):
    settings, _owner_id, subject_id, _content_id, _chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory,
    )
    _student_id, _auth_id, _thread_id, job_id = await _student_and_current_job(
        postgres_session_factory, settings, subject_id, key=f"source-stage-{uuid4().hex}",
    )
    embedding = FakeEmbeddingProvider()
    worker = RagAnswerWorker(
        settings=settings, session_factory=postgres_session_factory,
        embedding_provider=embedding, worker_id=f"stage-{uuid4().hex}",
    )
    claim = await worker.claim_next()
    assert claim is not None and claim[0] == job_id
    stage_id = await worker._begin_stage(job_id, claim[1], "query_embedding", remote=True)
    assert stage_id is not None
    with pytest.raises(AnswerProfileMismatch):
        await worker._begin_stage(job_id, claim[1], "query_embedding", remote=True)
    with pytest.raises(AnswerProfileMismatch):
        await worker._begin_stage(job_id, claim[1], "answer", remote=True)
    async with postgres_session_factory() as db:
        async with db.begin():
            with pytest.raises(DBAPIError):
                async with db.begin_nested():
                    db.add(RagAnswerStageAttempt(
                        job_id=job_id, manual_retry_number=0, worker_attempt_number=1,
                        stage="answer", answer_policy_version=ASK_REQUIRED_RELEASE_POLICY_VERSION,
                        execution_uncertain=True,
                    ))
                    await db.flush()


async def test_source_stage_cannot_disguise_parent_policy_or_attempt_identity(
    postgres_engine, postgres_session_factory,
):
    settings, _owner_id, subject_id, _content_id, _chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory,
    )
    _student_id, _auth_id, _thread_id, job_id = await _student_and_current_job(
        postgres_session_factory, settings, subject_id, key=f"source-parent-{uuid4().hex}",
    )
    embedding = FakeEmbeddingProvider()
    worker = RagAnswerWorker(settings=settings, session_factory=postgres_session_factory,
                             embedding_provider=embedding, worker_id=f"parent-{uuid4().hex}")
    claim = await worker.claim_next()
    assert claim is not None and claim[0] == job_id
    await worker._begin_stage(job_id, claim[1], "query_embedding", remote=True)
    async with postgres_session_factory() as db:
        async with db.begin():
            for overrides in (
                {"answer_policy_version": None, "stage": "answer"},
                {"answer_policy_version": "two_request_local_support_v1", "stage": "answer"},
                {"answer_policy_version": None, "worker_attempt_number": 2},
                {"manual_retry_number": 1},
                {"worker_attempt_number": 2},
            ):
                with pytest.raises(DBAPIError):
                    async with db.begin_nested():
                        db.add(RagAnswerStageAttempt(**(dict(
                            job_id=job_id, manual_retry_number=0, worker_attempt_number=1,
                            stage="query_embedding", answer_policy_version=ASK_REQUIRED_RELEASE_POLICY_VERSION,
                            physical_request_count=1, retry_count=0,
                        ) | overrides)))
                        await db.flush()
            with pytest.raises(DBAPIError):
                async with db.begin_nested():
                    stage = await db.scalar(select(RagAnswerStageAttempt).where(RagAnswerStageAttempt.job_id == job_id))
                    assert stage is not None
                    stage.answer_policy_version = None
                    await db.flush()
    assert embedding.requests == 0


async def test_revoked_enrollment_fails_queued_job_before_embedding(
    postgres_engine, postgres_session_factory,
):
    settings, _owner_id, subject_id, _content_id, _chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory,
    )
    student_id, _auth_id, _thread_id, job_id = await _student_and_current_job(
        postgres_session_factory, settings, subject_id, key=f"source-revoked-{uuid4().hex}",
    )
    async with postgres_session_factory() as db:
        async with db.begin():
            enrollment = await db.scalar(select(Enrollment).where(
                Enrollment.student_id == student_id,
                Enrollment.subject_id == subject_id,
            ).with_for_update())
            assert enrollment is not None
            await db.delete(enrollment)
    embedding = FakeEmbeddingProvider()
    worker = RagAnswerWorker(
        settings=settings, session_factory=postgres_session_factory,
        embedding_provider=embedding, worker_id=f"revoked-{uuid4().hex}",
    )
    claim = await worker.claim_next()
    assert claim is not None and claim[0] == job_id
    await worker.process_claim(*claim)
    async with postgres_session_factory() as db:
        job = await db.get(RagAnswerJob, job_id)
        assert job is not None and job.status == "failed"
        assert job.provider_request_count == 0
    assert embedding.requests == 0


async def test_expired_remote_boundary_never_replays_embedding(
    postgres_engine, postgres_session_factory,
):
    settings, _owner_id, subject_id, _content_id, _chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory,
    )
    _student_id, _auth_id, _thread_id, job_id = await _student_and_current_job(
        postgres_session_factory, settings, subject_id, key=f"source-lease-{uuid4().hex}",
    )
    embedding = FakeEmbeddingProvider()
    worker = RagAnswerWorker(
        settings=settings, session_factory=postgres_session_factory,
        embedding_provider=embedding, worker_id=f"lease-{uuid4().hex}",
    )
    claim = await worker.claim_next()
    assert claim is not None and claim[0] == job_id
    await worker._mark_provider_boundary(job_id, claim[1])
    await worker._begin_stage(job_id, claim[1], "query_embedding", remote=True)
    async with postgres_session_factory() as db:
        async with db.begin():
            job = await db.get(RagAnswerJob, job_id, with_for_update=True)
            assert job is not None
            job.lease_expires_at = utcnow() - timedelta(seconds=1)
            job.heartbeat_at = job.lease_expires_at
    await worker.recover_expired()
    async with postgres_session_factory() as db:
        job = await db.get(RagAnswerJob, job_id)
        assert job is not None and job.status == "failed"
        assert job.execution_uncertain and job.attempt_cost_unknown
        assert await worker.claim_next() is None
    assert embedding.requests == 0


async def test_active_capacity_and_idempotency_do_not_create_extra_questions(
    postgres_engine, postgres_session_factory,
):
    settings, _owner_id, subject_id, _content_id, _chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory,
    )
    student_id, auth_id, thread_id, job_id = await _student_and_current_job(
        postgres_session_factory, settings, subject_id, key="source-capacity-first",
    )
    service = RagAnswerService(settings)
    async with postgres_session_factory() as db:
        student = await db.get(User, student_id)
        assert student is not None
        setattr(student, "_auth_session_id", auth_id)
        async with db.begin_nested():
            repeated = await service.enqueue(
                db, subject_id=subject_id, thread_id=thread_id, user=student,
                data=RagQuestionCreate(question="What does the course say about alpha?"),
                idempotency_key="source-capacity-first",
            )
            assert repeated.id == job_id
        with pytest.raises(HTTPException) as busy:
            async with db.begin_nested():
                await service.enqueue(
                    db, subject_id=subject_id, thread_id=thread_id, user=student,
                    data=RagQuestionCreate(question="What is beta?"),
                    idempotency_key="source-capacity-second",
                )
        assert busy.value.status_code in (409, 429)
        messages = (await db.scalars(select(RagMessage).where(
            RagMessage.thread_id == thread_id,
        ))).all()
        assert len(messages) == 1 and messages[0].role == "user"
