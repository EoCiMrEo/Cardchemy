"""Phase 17 durable, private and grounded Subject Ask AI acceptance."""

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError

from app.ai.answering import ClaimSupportOutput, GroundedAnswerOutput
from app.ai.providers import ProviderAttemptTelemetry, ProviderResponse, ProviderUsage
from app.models.flashcard import Enrollment
from app.models.generation import GenerationJob
from app.models.knowledge import SubjectDocumentChunk, SubjectDocumentContentRevision
from app.models.rag import RagAnswerJob, RagAnswerQuotaEvent, RagMessage, RagMessageSource
from app.models.user import AuthSession, User, UserRole
from app.schemas.rag import RagQuestionCreate
from app.services.knowledge_indexing import (
    cutover_subject_embedding_space,
    enqueue_subject_reindex,
)
from app.services.knowledge_management import KnowledgeManagementService
from app.services.rag_answers import RagAnswerService
from app.time_utils import utcnow
from app.workers.knowledge_index import KnowledgeIndexWorker
from app.workers.rag_answer import AnswerLeaseLost, RagAnswerWorker
from tests.postgres.test_postgres_rag_pipeline import (
    FakeEmbeddingProvider,
    seed_capture,
    settings as index_settings,
)


pytestmark = pytest.mark.postgres


class FakeAnswerProvider:
    def __init__(self, chunk_id, quote: str) -> None:
        self.chunk_id = chunk_id
        self.quote = quote
        self.requests = 0

    async def generate_structured(self, *, response_model, **kwargs):
        self.requests += 1
        if response_model is GroundedAnswerOutput:
            data = GroundedAnswerOutput(
                outcome="answer",
                answer="Alpha is the first course concept.",
                claims=[{
                    "statement": "Alpha is the first course concept.",
                    "source_chunk_id": self.chunk_id,
                    "source_quote": self.quote,
                }],
            )
        elif response_model is ClaimSupportOutput:
            data = ClaimSupportOutput(decisions=[{
                "claim_index": 0,
                "entailed_by_quote": True,
                "relevant_to_question": True,
                "not_contradicted": True,
            }])
        else:  # pragma: no cover - a contract regression should identify the unexpected model
            raise AssertionError("unexpected answer model")
        return ProviderResponse(
            data=data,
            usage=ProviderUsage(input_tokens=20, output_tokens=8, estimated=False),
        )

    def telemetry_snapshot(self):
        return ProviderAttemptTelemetry(
            request_count=self.requests,
            retry_count=0,
            rate_limit_wait_seconds=0,
            request_counts_by_stage={"rag": self.requests},
        )


def _answer_settings(database_url: str):
    return index_settings(database_url).model_copy(update={
        "rag_ai_provider_enabled": True,
        "rag_ai_api_key": "test-only-answer-key",
        "rag_ai_quota_bucket": "disposable-answer-tests",
        "rag_ai_provider_max_retries": 0,
        "rag_answer_max_active_jobs_per_user": 1,
        "rag_answer_max_active_jobs_deployment": 10,
    })


async def _ready_course(postgres_engine, session_factory):
    configured = _answer_settings(str(postgres_engine.url))
    owner, subject, captured, _prepared = await seed_capture(
        session_factory,
        configured,
        page_texts=("Foundations\n\nAlpha is the first concept in this course.",),
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


async def _student_and_job(session_factory, configured, subject_id, *, key: str):
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


async def test_answer_worker_persists_atomic_grounded_result_and_g2_hides_revoked_sources(
    postgres_engine, postgres_session_factory
):
    configured, owner_id, subject_id, content_id, chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory
    )
    student_id, _auth_id, thread_id, job_id = await _student_and_job(
        postgres_session_factory, configured, subject_id, key="postgres-answer-happy-0001"
    )
    answer_provider = FakeAnswerProvider(chunk_id, "Alpha is the first concept")
    worker = RagAnswerWorker(
        settings=configured,
        session_factory=postgres_session_factory,
        answer_provider=answer_provider,
        embedding_provider=FakeEmbeddingProvider(),
        worker_id="answer-happy-worker",
    )
    claim = await worker.claim_next()
    assert claim and claim[0] == job_id
    await worker.process_claim(*claim)

    service = RagAnswerService(configured)
    async with postgres_session_factory() as db:
        job = await db.get(RagAnswerJob, job_id)
        assert job.status == "completed" and job.answer_message_id is not None
        assert job.provider_request_count == 3
        assert job.actual_input_tokens and job.actual_output_tokens
        assert await db.scalar(select(func.count(RagMessageSource.id)).where(
            RagMessageSource.message_id == job.answer_message_id
        )) == 1
        student = await db.get(User, student_id)
        history = await service.history(
            db, subject_id=subject_id, thread_id=thread_id, user=student, limit=100
        )
        assert history.messages[-1].content == "Alpha is the first course concept."
        assert history.messages[-1].sources[0].chunk_id == chunk_id
        owner = await db.get(User, owner_id)
        with pytest.raises(HTTPException) as private:
            await service.history(
                db, subject_id=subject_id, thread_id=thread_id, user=owner, limit=100
            )
        assert private.value.status_code == 404

    # G2: persisted private history remains, but publication revocation hides
    # both answer text and citations immediately.
    async with postgres_session_factory() as db:
        async with db.begin():
            content = await db.get(SubjectDocumentContentRevision, content_id, with_for_update=True)
            content.published_at = None
    async with postgres_session_factory() as db:
        student = await db.get(User, student_id)
        hidden = await service.history(
            db, subject_id=subject_id, thread_id=thread_id, user=student, limit=100
        )
        assert hidden.messages[-1].hidden is True
        assert hidden.messages[-1].content is None
        with pytest.raises(HTTPException) as unavailable:
            await service.message_sources(
                db,
                subject_id=subject_id,
                thread_id=thread_id,
                message_id=hidden.messages[-1].id,
                user=student,
            )
        assert unavailable.value.detail["code"] == "rag_sources_unavailable"


async def test_access_revocation_blocks_provider_use_and_dead_leases_never_replay_remote_work(
    postgres_engine, postgres_session_factory
):
    configured, _owner_id, subject_id, _content_id, chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory
    )
    student_id, _auth_id, _thread_id, job_id = await _student_and_job(
        postgres_session_factory, configured, subject_id, key="postgres-answer-revoked-0001"
    )
    provider = FakeAnswerProvider(chunk_id, "Alpha is the first concept")
    embedding = FakeEmbeddingProvider()
    worker = RagAnswerWorker(
        settings=configured,
        session_factory=postgres_session_factory,
        answer_provider=provider,
        embedding_provider=embedding,
        worker_id="answer-revocation-worker",
    )
    async with postgres_session_factory() as db:
        async with db.begin():
            enrollment = await db.scalar(select(Enrollment).where(
                Enrollment.student_id == student_id,
                Enrollment.subject_id == subject_id,
            ).with_for_update())
            await db.delete(enrollment)
    claim = await worker.claim_next()
    assert claim and claim[0] == job_id
    await worker.process_claim(*claim)
    async with postgres_session_factory() as db:
        revoked = await db.get(RagAnswerJob, job_id)
        assert revoked.status == "failed" and revoked.error_code == "rag_access_revoked"
        assert provider.requests == 0 and embedding.requests == 0

    # A separate instructor job exercises infrastructure recovery. Before the
    # provider boundary it can be requeued; after that boundary it is terminal
    # and the stale claim cannot commit.
    service = RagAnswerService(configured)
    async with postgres_session_factory() as db:
        async with db.begin():
            from app.models.subject import Subject
            subject = await db.get(Subject, subject_id)
            owner = await db.get(User, subject.instructor_id)
            auth = AuthSession(
                user_id=owner.id,
                refresh_jti_hash=uuid4().hex * 2,
                expires_at=utcnow() + timedelta(hours=1),
            )
            db.add(auth)
            await db.flush()
            setattr(owner, "_auth_session_id", auth.id)
            thread = await service.create_thread(db, subject_id=subject_id, user=owner)
            durable = await service.enqueue(
                db,
                subject_id=subject_id,
                thread_id=thread.id,
                user=owner,
                data=RagQuestionCreate(question="Explain alpha from the course."),
                idempotency_key="postgres-answer-recovery-0001",
            )
            owner_id, owner_auth_id, owner_thread_id = owner.id, auth.id, thread.id
    first_claim = await worker.claim_next()
    assert first_claim and first_claim[0] == durable.id
    async with postgres_session_factory() as db:
        async with db.begin():
            row = await db.get(RagAnswerJob, durable.id, with_for_update=True)
            row.lease_expires_at = utcnow() - timedelta(seconds=1)
            row.heartbeat_at = row.lease_expires_at
    await worker.recover_expired()
    async with postgres_session_factory() as db:
        async with db.begin():
            row = await db.get(RagAnswerJob, durable.id, with_for_update=True)
            assert row.status == "queued"
            row.available_at = utcnow()
    second_claim = await worker.claim_next()
    assert second_claim and second_claim[0] == durable.id
    await worker._mark_provider_boundary(durable.id, second_claim[1])
    async with postgres_session_factory() as db:
        async with db.begin():
            row = await db.get(RagAnswerJob, durable.id, with_for_update=True)
            row.lease_expires_at = utcnow() - timedelta(seconds=1)
            row.heartbeat_at = row.lease_expires_at
    await worker.recover_expired()
    async with postgres_session_factory() as db:
        row = await db.get(RagAnswerJob, durable.id)
        assert row.status == "failed" and row.error_code == "rag_answer_lease_expired"
    with pytest.raises(AnswerLeaseLost):
        await worker._complete(durable.id, second_claim[1], answer=None, claims=())

    # Database completion is all-or-nothing: an answer claiming one source but
    # persisting none is rejected, and the running job/message remain unchanged.
    async with postgres_session_factory() as db:
        async with db.begin():
            owner = await db.get(User, owner_id)
            setattr(owner, "_auth_session_id", owner_auth_id)
            atomic = await service.enqueue(
                db,
                subject_id=subject_id,
                thread_id=owner_thread_id,
                user=owner,
                data=RagQuestionCreate(question="Atomic answer fixture."),
                idempotency_key="postgres-answer-atomic-0001",
            )
    atomic_claim = await worker.claim_next()
    assert atomic_claim and atomic_claim[0] == atomic.id
    bad_message_id = None
    async with postgres_session_factory() as db:
        async with db.begin():
            with pytest.raises(DBAPIError) as rejected:
                async with db.begin_nested():
                    row = await db.get(RagAnswerJob, atomic.id, with_for_update=True)
                    now = utcnow()
                    bad = RagMessage(
                        thread_id=row.thread_id,
                        user_id=row.user_id,
                        subject_id=row.subject_id,
                        role="assistant",
                        outcome="answer",
                        content="Unbacked answer.",
                        source_count=1,
                        corpus_revision=row.corpus_revision,
                        embedding_space_hash=row.embedding_space_hash,
                        created_at=now,
                        expires_at=now + timedelta(days=90),
                    )
                    db.add(bad)
                    await db.flush()
                    bad_message_id = bad.id
                    row.status = "completed"
                    row.answer_message_id = bad.id
                    row.completed_at = now
                    row.worker_id = None
                    row.claim_token = None
                    row.heartbeat_at = None
                    row.lease_expires_at = None
                    await db.flush()
            assert rejected.value.orig.sqlstate == "23514"
    async with postgres_session_factory() as db:
        assert await db.get(RagMessage, bad_message_id) is None
        row = await db.get(RagAnswerJob, atomic.id)
        assert row.status == "running" and row.answer_message_id is None

    # A running cancellation is a user-requested terminal transition and does
    # not cross either provider boundary.
    async with postgres_session_factory() as db:
        async with db.begin():
            owner = await db.get(User, owner_id)
            await service.cancel(
                db,
                subject_id=subject_id,
                thread_id=owner_thread_id,
                job_id=atomic.id,
                user=owner,
            )
    await worker.process_claim(*atomic_claim)
    async with postgres_session_factory() as db:
        row = await db.get(RagAnswerJob, atomic.id)
        assert row.status == "cancelled" and row.error_code == "rag_answer_cancelled"
        assert provider.requests == 0 and embedding.requests == 0


@pytest.mark.parametrize("change_kind,change_while", [
    ("unpublish", "queued"),
    # Active answer work now blocks document deletion; the separate lifecycle
    # contract covers that refusal. A queued receipt is safe to delete beneath
    # and must fail closed when the worker later claims it.
    ("delete", "queued"),
    ("reindex", "running"),
])
async def test_document_lifecycle_changes_fail_queued_or_running_answers_closed(
    postgres_engine,
    postgres_session_factory,
    change_kind,
    change_while,
):
    configured, owner_id, subject_id, content_id, chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory
    )
    _student_id, _auth_id, _thread_id, job_id = await _student_and_job(
        postgres_session_factory,
        configured,
        subject_id,
        key=f"postgres-answer-{change_kind}-0001",
    )
    answer_provider = FakeAnswerProvider(chunk_id, "Alpha is the first concept")
    embedding_provider = FakeEmbeddingProvider()
    worker = RagAnswerWorker(
        settings=configured,
        session_factory=postgres_session_factory,
        answer_provider=answer_provider,
        embedding_provider=embedding_provider,
        worker_id=f"answer-{change_kind}-worker",
    )
    claim = await worker.claim_next() if change_while == "running" else None
    if change_while == "running":
        assert claim and claim[0] == job_id

    reindex_settings = None
    async with postgres_session_factory() as db:
        async with db.begin():
            owner = await db.get(User, owner_id)
            if change_kind == "unpublish":
                content = await db.get(
                    SubjectDocumentContentRevision, content_id, with_for_update=True
                )
                await KnowledgeManagementService(configured).unpublish(
                    db,
                    subject_id=subject_id,
                    document_id=content.document_id,
                    user=owner,
                )
            elif change_kind == "delete":
                content = await db.get(
                    SubjectDocumentContentRevision, content_id, with_for_update=True
                )
                await KnowledgeManagementService(configured).remove(
                    db,
                    subject_id=subject_id,
                    document_id=content.document_id,
                    user=owner,
                )
            else:
                reindex_settings = configured.model_copy(update={
                    "rag_embedding_space_revision": "v2",
                })
                created = await enqueue_subject_reindex(
                    db,
                    subject_id=subject_id,
                    owner_id=owner_id,
                    settings=reindex_settings,
                )
                assert created == 1

    if claim is None:
        claim = await worker.claim_next()
        assert claim and claim[0] == job_id
    await worker.process_claim(*claim)

    async with postgres_session_factory() as db:
        job = await db.get(RagAnswerJob, job_id)
        assert job.status == "failed"
        assert job.error_code == "rag_corpus_changed"
    assert answer_provider.requests == 0
    assert embedding_provider.requests == 0
    if reindex_settings is not None:
        # Leave the shared disposable service database with no queued work so
        # later worker-ordering tests cannot claim this scenario's staged job.
        reindex_worker = KnowledgeIndexWorker(
            settings=reindex_settings,
            session_factory=postgres_session_factory,
            provider=FakeEmbeddingProvider(),
            worker_id="answer-reindex-cleanup-worker",
        )
        reindex_claim = await reindex_worker.claim_next()
        assert reindex_claim is not None
        await reindex_worker.process_claim(*reindex_claim)


async def test_concurrent_idempotency_and_capacity_are_serialized(
    postgres_engine, postgres_session_factory
):
    configured, _owner_id, subject_id, _content_id, _chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory
    )
    student_id, auth_id, thread_id, first_job_id = await _student_and_job(
        postgres_session_factory, configured, subject_id, key="postgres-race-seed-0001"
    )
    service = RagAnswerService(configured)
    async with postgres_session_factory() as db:
        async with db.begin():
            student = await db.get(User, student_id)
            setattr(student, "_auth_session_id", auth_id)
            await service.cancel(
                db,
                subject_id=subject_id,
                thread_id=thread_id,
                job_id=first_job_id,
                user=student,
            )

    async def submit(key: str):
        async with postgres_session_factory() as db:
            async with db.begin():
                student = await db.get(User, student_id)
                setattr(student, "_auth_session_id", auth_id)
                return await service.enqueue(
                    db,
                    subject_id=subject_id,
                    thread_id=thread_id,
                    user=student,
                    data=RagQuestionCreate(question="What is alpha?"),
                    idempotency_key=key,
                )

    same = await asyncio.gather(
        submit("postgres-idempotent-race-0001"),
        submit("postgres-idempotent-race-0001"),
    )
    assert same[0].id == same[1].id
    async with postgres_session_factory() as db:
        assert await db.scalar(select(func.count(RagAnswerQuotaEvent.id)).where(
            RagAnswerQuotaEvent.job_id == same[0].id
        )) == 1
        await db.commit()
        async with db.begin():
            student = await db.get(User, student_id)
            setattr(student, "_auth_session_id", auth_id)
            await service.cancel(
                db,
                subject_id=subject_id,
                thread_id=thread_id,
                job_id=same[0].id,
                user=student,
            )

    results = await asyncio.gather(
        submit("postgres-capacity-race-0001"),
        submit("postgres-capacity-race-0002"),
        return_exceptions=True,
    )
    accepted = [result for result in results if isinstance(result, RagAnswerJob)]
    rejected = [result for result in results if isinstance(result, HTTPException)]
    assert len(accepted) == 1 and len(rejected) == 1
    assert rejected[0].detail["code"] == "rag_user_active_limit"
