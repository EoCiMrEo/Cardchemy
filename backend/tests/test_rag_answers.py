import asyncio
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.config import Settings
from app.models.flashcard import Enrollment
from app.models.knowledge import SubjectDocumentChunk, embedding_space_hash
from app.ai.answering import ClaimSupportOutput, GroundedAnswerOutput
from app.ai.embeddings import EmbeddingResponse
from app.ai.providers import ProviderAttemptTelemetry, ProviderResponse, ProviderUsage
from app.models.rag import (
    RagAnswerJob,
    RagAnswerQuotaEvent,
    RagMessage,
    RagMessageSource,
)
from app.models.subject import Subject
from app.models.user import AuthSession, User, UserRole
from app.schemas.rag import RagQuestionCreate
from app.schemas.rag import RagSourceResponse
from app.services.knowledge_retrieval import KnowledgeRetriever, RetrievedKnowledgeChunk
from app.services.rag_answers import RagAnswerService
from app.time_utils import utcnow
from app.workers.rag_answer import RagAnswerWorker


def _settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "database_url": "sqlite+aiosqlite:///:memory:",
        "secret_key": "test-only-secret-key-with-adequate-entropy-1234567890",
        "generation_source_encryption_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "rag_enabled": True,
        "rag_ai_provider_enabled": True,
        "rag_embedding_provider_enabled": True,
        "rag_ai_api_key": "test-answer-key",
        "rag_embedding_api_key": "test-embedding-key",
        "rag_ai_quota_bucket": "test-answer",
        "rag_embedding_quota_bucket": "test-embedding",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def _seed(db):
    owner = User(
        id=uuid4(), email=f"owner-{uuid4().hex}@example.test",
        hashed_password="not-real", role=UserRole.INSTRUCTOR,
    )
    student = User(
        id=uuid4(), email=f"student-{uuid4().hex}@example.test",
        hashed_password="not-real", role=UserRole.STUDENT,
    )
    outsider = User(
        id=uuid4(), email=f"outsider-{uuid4().hex}@example.test",
        hashed_password="not-real", role=UserRole.STUDENT,
    )
    subject = Subject(id=uuid4(), name="Private biology", instructor_id=owner.id, corpus_revision=7)
    db.add_all([owner, student, outsider, subject])
    await db.flush()
    db.add(Enrollment(student_id=student.id, subject_id=subject.id))
    session = AuthSession(
        user_id=student.id,
        refresh_jti_hash=uuid4().hex * 2,
        expires_at=utcnow() + timedelta(hours=1),
    )
    db.add(session)
    await db.commit()
    setattr(student, "_auth_session_id", session.id)
    return owner, student, outsider, subject, session


def _authorize(settings: Settings):
    scope = SimpleNamespace(
        corpus_revision=7,
        embedding_space_hash=embedding_space_hash(settings.rag_embedding_space_identity),
    )

    async def authorize(cls, db, **kwargs):
        return SimpleNamespace(scope=scope)

    return classmethod(authorize)


async def test_thread_history_is_private_even_from_the_subject_instructor(db):
    owner, student, outsider, subject, _session = await _seed(db)
    service = RagAnswerService(_settings())
    async with db.begin():
        thread = await service.create_thread(db, subject_id=subject.id, user=student)
        now = utcnow()
        db.add(RagMessage(
            thread_id=thread.id, user_id=student.id, subject_id=subject.id,
            role="assistant", outcome="answer", content="Stored answer", source_count=1,
            corpus_revision=7, embedding_space_hash="a" * 64,
            created_at=now, expires_at=now + timedelta(days=90),
        ))

    history = await service.history(
        db, subject_id=subject.id, thread_id=thread.id, user=student, limit=100
    )
    assert history.messages[0].hidden is True
    assert history.messages[0].content is None

    for other in (owner, outsider):
        with pytest.raises(HTTPException) as denied:
            await service.history(
                db, subject_id=subject.id, thread_id=thread.id, user=other, limit=100
            )
        assert denied.value.status_code in (403, 404)


async def test_answer_admission_is_idempotent_and_reserves_bounded_capacity(db, monkeypatch):
    _owner, student, _outsider, subject, session = await _seed(db)
    student_id, subject_id, session_id = student.id, subject.id, session.id
    settings = _settings(rag_answer_max_active_jobs_per_user=1)
    service = RagAnswerService(settings)
    monkeypatch.setattr(KnowledgeRetriever, "authorize", _authorize(settings))
    async with db.begin():
        thread = await service.create_thread(db, subject_id=subject_id, user=student)
    thread_id = thread.id
    data = RagQuestionCreate(question="What produces ATP?")

    async with db.begin():
        first = await service.enqueue(
            db, subject_id=subject_id, thread_id=thread_id, user=student,
            data=data, idempotency_key="fixture-1",
        )
    async with db.begin():
        replay = await service.enqueue(
            db, subject_id=subject_id, thread_id=thread_id, user=student,
            data=data, idempotency_key="fixture-1",
        )
    assert replay.id == first.id
    assert await db.scalar(select(func.count(RagAnswerQuotaEvent.id))) == 1
    await db.commit()

    with pytest.raises(HTTPException) as mismatch:
        async with db.begin():
            await service.enqueue(
                db, subject_id=subject_id, thread_id=thread_id, user=student,
                data=RagQuestionCreate(question="Different question"),
                idempotency_key="fixture-1",
            )
    assert mismatch.value.status_code == 409
    assert mismatch.value.detail["code"] == "idempotency_key_reused"

    with pytest.raises(HTTPException) as at_capacity:
        async with db.begin():
            current_student = await db.get(User, student_id)
            setattr(current_student, "_auth_session_id", session_id)
            await service.enqueue(
                db, subject_id=subject_id, thread_id=thread_id, user=current_student,
                data=data, idempotency_key="fixture-2",
            )
    assert at_capacity.value.detail["code"] == "rag_user_active_limit"


async def test_deployment_thread_and_future_message_storage_are_bounded(db, monkeypatch):
    owner, student, _outsider, subject, student_session = await _seed(db)
    owner_id, student_id = owner.id, student.id
    subject_id, student_session_id = subject.id, student_session.id
    thread_settings = _settings(
        rag_answer_max_threads_per_user=1,
        rag_answer_max_threads_deployment=1,
    )
    thread_service = RagAnswerService(thread_settings)
    async with db.begin():
        student_thread = await thread_service.create_thread(
            db, subject_id=subject_id, user=student
        )
    student_thread_id = student_thread.id
    with pytest.raises(HTTPException) as thread_limit:
        async with db.begin():
            await thread_service.create_thread(db, subject_id=subject_id, user=owner)
    assert thread_limit.value.status_code == 503
    assert thread_limit.value.detail["code"] == "rag_deployment_thread_limit"

    message_settings = _settings(
        rag_answer_max_threads_deployment=100,
        rag_answer_max_messages_per_thread=3,
        rag_answer_max_messages_per_user=3,
        rag_answer_max_messages_deployment=3,
    )
    service = RagAnswerService(message_settings)
    monkeypatch.setattr(KnowledgeRetriever, "authorize", _authorize(message_settings))
    async with db.begin():
        owner = await db.get(User, owner_id)
        student = await db.get(User, student_id)
        setattr(student, "_auth_session_id", student_session_id)
        owner_session = AuthSession(
            user_id=owner.id,
            refresh_jti_hash=uuid4().hex * 2,
            expires_at=utcnow() + timedelta(hours=1),
        )
        db.add(owner_session)
        await db.flush()
        setattr(owner, "_auth_session_id", owner_session.id)
        owner_thread = await service.create_thread(
            db, subject_id=subject_id, user=owner
        )
    owner_thread_id = owner_thread.id
    # Admission creates one question row and reserves one future assistant row.
    async with db.begin():
        await service.enqueue(
            db,
            subject_id=subject_id,
            thread_id=student_thread_id,
            user=student,
            data=RagQuestionCreate(question="First reserved answer"),
            idempotency_key="ask-ai-deployment-storage-0001",
        )
    with pytest.raises(HTTPException) as storage_limit:
        async with db.begin():
            await service.enqueue(
                db,
                subject_id=subject_id,
                thread_id=owner_thread_id,
                user=owner,
                data=RagQuestionCreate(question="Second reserved answer"),
                idempotency_key="ask-ai-deployment-storage-0002",
            )
    assert storage_limit.value.status_code == 503
    assert storage_limit.value.detail["code"] == "rag_deployment_message_storage_limit"


async def test_cancel_and_manual_retry_are_explicit_and_refresh_authorization_session(db, monkeypatch):
    _owner, student, _outsider, subject, first_session = await _seed(db)
    settings = _settings()
    service = RagAnswerService(settings)
    monkeypatch.setattr(KnowledgeRetriever, "authorize", _authorize(settings))
    async with db.begin():
        thread = await service.create_thread(db, subject_id=subject.id, user=student)
        job = await service.enqueue(
            db, subject_id=subject.id, thread_id=thread.id, user=student,
            data=RagQuestionCreate(question="Explain ATP."),
            idempotency_key="ask-ai-cancel-0001",
        )
    async with db.begin():
        cancelled = await service.cancel(
            db, subject_id=subject.id, thread_id=thread.id, job_id=job.id, user=student
        )
    assert cancelled.status == "cancelled"
    assert cancelled.error_code == "rag_answer_cancelled"

    # A retryable failure is a separate explicit transition. The new current
    # authentication session replaces the stale submission session.
    now = utcnow()
    second_session = AuthSession(
        user_id=student.id, refresh_jti_hash=uuid4().hex * 2,
        expires_at=now + timedelta(hours=1),
    )
    db.add(second_session)
    await db.flush()
    retry_job = RagAnswerJob(
        thread_id=thread.id,
        question_message_id=job.question_message_id,
        auth_session_id=first_session.id,
        user_id=student.id,
        subject_id=subject.id,
        status="failed",
        operation_key_hash="1" * 64,
        request_fingerprint="2" * 64,
        document_ids=[],
        corpus_revision=7,
        retrieval_policy="hybrid_exact_v1",
        embedding_space_hash=embedding_space_hash(settings.rag_embedding_space_identity),
        ai_provider=settings.rag_ai_provider,
        ai_base_url=settings.rag_ai_endpoint_identity,
        ai_model=settings.rag_ai_model,
        max_attempts=settings.rag_answer_max_attempts,
        available_at=now,
        deadline_at=now + timedelta(minutes=5),
        completed_at=now,
        error_code="rag_answer_failed",
        error_message="Answer generation failed.",
        error_retryable=True,
        created_at=now,
        updated_at=now,
    )
    # One question can own only one job; use a fresh question for this fixture.
    question = RagMessage(
        thread_id=thread.id, user_id=student.id, subject_id=subject.id,
        role="user", content="Retry me", source_count=0,
        created_at=now, expires_at=now + timedelta(days=90),
    )
    db.add(question)
    await db.flush()
    retry_job.question_message_id = question.id
    db.add(retry_job)
    await db.commit()
    setattr(student, "_auth_session_id", second_session.id)
    async with db.begin():
        retried = await service.retry(
            db, subject_id=subject.id, thread_id=thread.id, job_id=retry_job.id,
            user=student, idempotency_key="ask-ai-manual-retry-0001",
        )
    assert retried.status == "queued"
    assert retried.auth_session_id == second_session.id
    assert retried.manual_retry_count == 1
    assert retried.attempt_count == 0


async def test_expired_deadline_fails_before_any_provider_call(
    session_factory, monkeypatch
):
    async with session_factory() as db:
        _owner, student, _outsider, subject, _session = await _seed(db)
        settings = _settings()
        service = RagAnswerService(settings)
        monkeypatch.setattr(KnowledgeRetriever, "authorize", _authorize(settings))
        async with db.begin():
            thread = await service.create_thread(db, subject_id=subject.id, user=student)
            job = await service.enqueue(
                db,
                subject_id=subject.id,
                thread_id=thread.id,
                user=student,
                data=RagQuestionCreate(question="Deadline fixture"),
                idempotency_key="ask-ai-deadline-0001",
            )
        async with db.begin():
            expired = await db.get(RagAnswerJob, job.id)
            expired.created_at = utcnow() - timedelta(minutes=2)
            expired.available_at = expired.created_at
            expired.deadline_at = utcnow() - timedelta(minutes=1)

    class NeverProvider:
        async def generate_structured(self, **kwargs):
            pytest.fail("expired answer job called the text provider")

        async def embed_query(self, text):
            pytest.fail("expired answer job called the embedding provider")

    worker = RagAnswerWorker(
        settings=settings,
        session_factory=session_factory,
        answer_provider=NeverProvider(),
        embedding_provider=NeverProvider(),
        worker_id="deadline-worker",
    )
    assert await worker.claim_next() is None
    async with session_factory() as db:
        terminal = await db.get(RagAnswerJob, job.id)
        assert terminal.status == "failed"
        assert terminal.error_code == "rag_answer_failed"
        assert terminal.error_retryable is True


async def test_answer_worker_completes_grounded_result_with_fenced_usage(
    session_factory, monkeypatch
):
    """Exercise the complete worker path without provider or PostgreSQL I/O."""

    from tests.test_knowledge_management import _seed_document

    async with session_factory() as db:
        seeded, owner, subject, document, content, index, _index_job = (
            await _seed_document(db)
        )
        now = utcnow()
        content.reviewed_by_id = owner.id
        content.reviewed_at = now
        content.published_at = now
        student = User(
            id=uuid4(),
            email=f"worker-{uuid4().hex}@example.test",
            hashed_password="not-real",
            role=UserRole.STUDENT,
        )
        db.add(student)
        await db.flush()
        db.add(Enrollment(student_id=student.id, subject_id=subject.id))
        auth = AuthSession(
            user_id=student.id,
            refresh_jti_hash=uuid4().hex * 2,
            expires_at=now + timedelta(hours=1),
        )
        db.add(auth)
        await db.flush()
        setattr(student, "_auth_session_id", auth.id)
        chunk_row = await db.scalar(
            select(SubjectDocumentChunk).where(
                SubjectDocumentChunk.index_revision_id == index.id
            )
        )
        assert chunk_row is not None
        await db.commit()

    settings = seeded.model_copy(
        update={
            "rag_ai_provider_enabled": True,
            "rag_ai_api_key": "test-answer-key",
            "rag_ai_quota_bucket": "test-answer",
            "rag_ai_provider_max_retries": 0,
        }
    )
    source = RetrievedKnowledgeChunk(
        chunk_id=chunk_row.id,
        document_id=document.id,
        document_title=document.title,
        content_revision_id=content.id,
        index_revision_id=index.id,
        page_number=chunk_row.page_number,
        section=chunk_row.section,
        content=chunk_row.content,
        token_count=chunk_row.token_count,
        embedding_space_hash=index.embedding_space_hash,
        corpus_revision=subject.corpus_revision,
        vector_similarity=1.0,
        lexical_score=1.0,
        vector_rank=1,
        lexical_rank=1,
        fusion_score=1.0,
    )

    class FakeRetriever:
        scope = SimpleNamespace(
            corpus_revision=subject.corpus_revision,
            embedding_space_hash=index.embedding_space_hash,
        )

        async def retrieve(self, _vector, *, embedding_space_hash):
            assert embedding_space_hash == index.embedding_space_hash
            return SimpleNamespace(insufficient=False, chunks=(source,))

        async def read_current_sources(self, chunk_ids):
            assert chunk_ids == [source.chunk_id]
            return (source,)

    retriever = FakeRetriever()

    async def authorize(_cls, _db, **_kwargs):
        return retriever

    monkeypatch.setattr(KnowledgeRetriever, "authorize", classmethod(authorize))

    service = RagAnswerService(settings)
    async with session_factory() as db:
        async with db.begin():
            student = await db.get(User, student.id)
            setattr(student, "_auth_session_id", auth.id)
            thread = await service.create_thread(
                db, subject_id=subject.id, user=student
            )
            job = await service.enqueue(
                db,
                subject_id=subject.id,
                thread_id=thread.id,
                user=student,
                data=RagQuestionCreate(question="What is perihelion?"),
                idempotency_key="offline-worker-happy-0001",
            )
            job_id = job.id

    class FakeEmbeddingProvider:
        def __init__(self):
            self.requests = 0

        def telemetry_snapshot(self):
            return ProviderAttemptTelemetry(
                self.requests, 0, 0.0, {"embedding_query": self.requests}
            )

        async def embed_query(self, _text):
            self.requests += 1
            return EmbeddingResponse(
                vectors=(tuple([1.0, *([0.0] * 1535)]),),
                usage=ProviderUsage(3, 0, False),
            )

    class FakeAnswerProvider:
        def __init__(self):
            self.requests = 0

        def telemetry_snapshot(self):
            return ProviderAttemptTelemetry(
                self.requests, 0, 0.0, {"rag": self.requests}
            )

        async def generate_structured(self, *, response_model, **_kwargs):
            self.requests += 1
            if response_model is GroundedAnswerOutput:
                data = GroundedAnswerOutput(
                    outcome="answer",
                    answer="Perihelion is the nearest orbital point to the Sun.",
                    claims=[
                        {
                            "statement": "Perihelion is the nearest orbital point to the Sun.",
                            "source_chunk_id": source.chunk_id,
                            "source_quote": "Perihelion is the point of an orbit nearest to the Sun.",
                        }
                    ],
                )
            else:
                assert response_model is ClaimSupportOutput
                data = ClaimSupportOutput(
                    decisions=[
                        {
                            "claim_index": 0,
                            "entailed_by_quote": True,
                            "relevant_to_question": True,
                            "not_contradicted": True,
                        }
                    ]
                )
            return ProviderResponse(
                data=data,
                usage=ProviderUsage(input_tokens=20, output_tokens=8, estimated=False),
            )

    answer_provider = FakeAnswerProvider()
    embedding_provider = FakeEmbeddingProvider()
    worker = RagAnswerWorker(
        settings=settings,
        session_factory=session_factory,
        answer_provider=answer_provider,
        embedding_provider=embedding_provider,
        worker_id="offline-answer-worker",
    )
    claim = await worker.claim_next()
    assert claim and claim[0] == job_id
    await worker.process_claim(*claim)

    async with session_factory() as db:
        completed = await db.get(RagAnswerJob, job_id)
        assert completed.status == "completed"
        assert completed.provider_request_count == 3
        assert completed.actual_input_tokens == 43
        assert completed.actual_output_tokens == 16
        assert completed.answer_message_id is not None
        assert await db.scalar(
            select(func.count(RagMessageSource.id)).where(
                RagMessageSource.message_id == completed.answer_message_id
            )
        ) == 1


async def test_answer_worker_disabled_lifecycle_reports_health_and_drains(
    monkeypatch,
):
    stop = asyncio.Event()
    worker = RagAnswerWorker(
        settings=_settings(rag_enabled=False),
        answer_provider=SimpleNamespace(),
        embedding_provider=SimpleNamespace(),
        worker_id="disabled-answer-worker",
    )
    statuses = []

    async def pulse(status):
        statuses.append(status)
        if status == "disabled":
            stop.set()

    monkeypatch.setattr(worker, "_pulse", pulse)
    await worker.run(stop)
    assert statuses == ["disabled", "draining"]


async def test_answer_worker_active_lifecycle_claims_one_job_and_drains(
    monkeypatch,
):
    stop = asyncio.Event()
    worker = RagAnswerWorker(
        settings=_settings(rag_answer_worker_poll_seconds=0.1),
        answer_provider=SimpleNamespace(),
        embedding_provider=SimpleNamespace(),
        worker_id="active-answer-worker",
    )
    statuses = []
    recovered = []
    processed = []
    claimed_id = uuid4()

    async def pulse(status):
        statuses.append(status)

    async def recover():
        recovered.append(True)

    async def claim():
        return claimed_id, "claim-token"

    async def process(job_id, token):
        processed.append((job_id, token))
        stop.set()

    monkeypatch.setattr(worker, "_pulse", pulse)
    monkeypatch.setattr(worker, "recover_expired", recover)
    monkeypatch.setattr(worker, "claim_next", claim)
    monkeypatch.setattr(worker, "process_claim", process)
    await worker.run(stop)
    assert recovered == [True]
    assert processed == [(claimed_id, "claim-token")]
    assert statuses == ["running", "draining"]


async def test_every_rag_endpoint_enforces_current_subject_and_private_thread_ownership(
    session_factory, monkeypatch
):
    from httpx import ASGITransport, AsyncClient
    from app.config import get_settings
    from app.database import get_db
    from app.main import app
    from app.routers import rag as rag_router
    from app.routers.auth import get_current_user

    async with session_factory() as seed_db:
        owner, student, outsider, subject, auth = await _seed(seed_db)
        owner_id, student_id, outsider_id = owner.id, student.id, outsider.id
        subject_id, auth_id = subject.id, auth.id

    settings = _settings()
    service = RagAnswerService(settings)
    monkeypatch.setattr(KnowledgeRetriever, "authorize", _authorize(settings))
    monkeypatch.setattr(rag_router, "answers", service)
    principals = {}
    async with session_factory() as read_db:
        for key, identifier in (("owner", owner_id), ("student", student_id), ("outsider", outsider_id)):
            principals[key] = await read_db.get(User, identifier)
    setattr(principals["student"], "_auth_session_id", auth_id)
    current = {"user": principals["student"]}

    async def test_db():
        async with session_factory() as request_db:
            yield request_db

    async def test_user():
        return current["user"]

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[get_current_user] = test_user
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            profile = await client.get(f"/subjects/{subject_id}/rag/profile")
            assert profile.status_code == 200
            assert profile.json() == {
                "rag_enabled": True,
                "answer_available": True,
                "answer_provider": settings.rag_ai_provider,
                "answer_model": settings.rag_ai_model,
                "embedding_available": True,
                "embedding_provider": settings.rag_embedding_provider,
                "embedding_model": settings.rag_embedding_model,
                "chat_retention_days": 90,
            }
            created = await client.post(f"/subjects/{subject_id}/rag/threads")
            assert created.status_code == 201, created.text
            thread_id = created.json()["id"]
            thread_uuid = UUID(thread_id)
            listed = await client.get(f"/subjects/{subject_id}/rag/threads")
            assert listed.status_code == 200 and [row["id"] for row in listed.json()["threads"]] == [thread_id]
            history = await client.get(f"/subjects/{subject_id}/rag/threads/{thread_id}")
            assert history.status_code == 200 and history.json()["messages"] == []
            queued = await client.post(
                f"/subjects/{subject_id}/rag/threads/{thread_id}/answer-jobs",
                headers={"Idempotency-Key": "rag-route-answer-0001"},
                json={"question": "What is alpha?", "document_ids": []},
            )
            assert queued.status_code == 202, queued.text
            job_id = queued.json()["id"]
            polled = await client.get(
                f"/subjects/{subject_id}/rag/threads/{thread_id}/answer-jobs/{job_id}"
            )
            assert polled.status_code == 200 and polled.json()["status"] == "queued"
            job_list = await client.get(
                f"/subjects/{subject_id}/rag/threads/{thread_id}/answer-jobs"
            )
            assert job_list.status_code == 200
            assert [row["id"] for row in job_list.json()["jobs"]] == [job_id]
            cancelled = await client.post(
                f"/subjects/{subject_id}/rag/threads/{thread_id}/answer-jobs/{job_id}/cancel"
            )
            assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"

            # Convert the synthetic cancelled row into a safe retryable failure
            # to exercise the HTTP retry contract without invoking a provider.
            async with session_factory() as mutate_db:
                async with mutate_db.begin():
                    job = await mutate_db.get(RagAnswerJob, UUID(job_id))
                    job.status = "failed"
                    job.cancellation_requested_at = None
                    job.error_code = "rag_answer_failed"
                    job.error_message = "Answer generation failed."
                    job.error_retryable = True
            retried = await client.post(
                f"/subjects/{subject_id}/rag/threads/{thread_id}/answer-jobs/{job_id}/retry",
                headers={"Idempotency-Key": "rag-route-retry-0001"},
            )
            assert retried.status_code == 200 and retried.json()["status"] == "queued"

            async with session_factory() as mutate_db:
                async with mutate_db.begin():
                    message = RagMessage(
                        thread_id=thread_uuid,
                        user_id=student_id,
                        subject_id=subject_id,
                        role="assistant",
                        outcome="answer",
                        content="Alpha is first.",
                        source_count=1,
                        corpus_revision=7,
                        embedding_space_hash="a" * 64,
                        created_at=utcnow(),
                        expires_at=utcnow() + timedelta(days=90),
                    )
                    mutate_db.add(message)
                    await mutate_db.flush()
                    message_id = message.id
            source = RagSourceResponse(
                citation_order=1,
                chunk_id=uuid4(),
                document_id=uuid4(),
                document_title="Private course source",
                content_revision_id=uuid4(),
                index_revision_id=uuid4(),
                page_number=1,
                section=None,
                claim_text="Alpha is first.",
                source_quote="Alpha is first",
            )

            async def eligible_sources(db, message_ids):
                return {message_id: [source]} if message_id in message_ids else {}

            monkeypatch.setattr(service, "_eligible_source_rows", eligible_sources)
            sources = await client.get(
                f"/subjects/{subject_id}/rag/threads/{thread_id}/messages/{message_id}/sources"
            )
            assert sources.status_code == 200 and sources.json()[0]["page_number"] == 1

            current["user"] = principals["owner"]
            assert (await client.get(f"/subjects/{subject_id}/rag/threads")).json()["threads"] == []
            private_paths = (
                ("get", f"/subjects/{subject_id}/rag/threads/{thread_id}"),
                ("post", f"/subjects/{subject_id}/rag/threads/{thread_id}/answer-jobs"),
                ("get", f"/subjects/{subject_id}/rag/threads/{thread_id}/answer-jobs"),
                ("get", f"/subjects/{subject_id}/rag/threads/{thread_id}/answer-jobs/{job_id}"),
                ("post", f"/subjects/{subject_id}/rag/threads/{thread_id}/answer-jobs/{job_id}/retry"),
                ("post", f"/subjects/{subject_id}/rag/threads/{thread_id}/answer-jobs/{job_id}/cancel"),
                ("get", f"/subjects/{subject_id}/rag/threads/{thread_id}/messages/{message_id}/sources"),
                ("delete", f"/subjects/{subject_id}/rag/threads/{thread_id}"),
            )
            for method, path in private_paths:
                kwargs = {}
                if path.endswith("answer-jobs"):
                    kwargs = {
                        "headers": {"Idempotency-Key": "fixture-denied"},
                        "json": {"question": "Denied", "document_ids": []},
                    }
                elif path.endswith("/retry"):
                    kwargs = {"headers": {"Idempotency-Key": "fixture-retry"}}
                denied = await client.request(method, path, **kwargs)
                assert denied.status_code == 404, (method, path, denied.text)

            current["user"] = principals["outsider"]
            denied_profile = await client.get(f"/subjects/{subject_id}/rag/profile")
            assert denied_profile.status_code == 403
            denied_create = await client.post(f"/subjects/{subject_id}/rag/threads")
            assert denied_create.status_code == 403

            current["user"] = principals["student"]
            deleted = await client.delete(f"/subjects/{subject_id}/rag/threads/{thread_id}")
            assert deleted.status_code == 204
            missing = await client.get(f"/subjects/{subject_id}/rag/threads/{thread_id}")
            assert missing.status_code == 404
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
