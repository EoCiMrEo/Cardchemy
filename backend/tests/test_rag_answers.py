import asyncio
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION, Settings
from app.models.flashcard import Enrollment
from app.models.knowledge import RagEmbeddingSpace, SubjectDocumentChunk, SubjectDocumentPage, embedding_space_hash
from app.ai.gemini_catalog import CATALOG_VERSION, SCHEMA_POLICY_VERSION
from app.ai.local_support import LOCAL_SUPPORT_POLICY_VERSION
from app.ai.embeddings import EmbeddingResponse
from app.ai.providers import (
    AIProviderError,
    ProviderUsage,
)
from app.models.rag import (
    RagAnswerJob,
    RagAnswerQuestionContext,
    RagAnswerStageAttempt,
    RagAnswerQuotaEvent,
    RagMessage,
    RagRelatedEvidence,
)
from app.models.subject import Subject
from app.models.user import AuthSession, User, UserRole
from app.schemas.rag import RagQuestionCreate
from app.schemas.rag import RagSourceResponse
from app.services.knowledge_retrieval import KnowledgeRetriever, RetrievedKnowledgeChunk
from app.services.rag_answers import RagAnswerService, _attempt_estimate_microusd
from app.services.operations import answer_job_diagnostics
from app.time_utils import utcnow
from app.workers.rag_answer import RagAnswerWorker, _JudgeResponse


@pytest.fixture(autouse=True)
def source_only_release_policy(monkeypatch):
    # Exercise the accepted source-only contract while the operator runtime
    # policy remains fenced until the separate release gate passes.
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", ASK_REQUIRED_RELEASE_POLICY_VERSION)


def _settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "database_url": "sqlite+aiosqlite:///:memory:",
        "secret_key": "test-only-secret-key-with-adequate-entropy-1234567890",
        "generation_source_encryption_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "rag_enabled": True,
        "rag_ask_enabled": True,
        "rag_ai_provider_enabled": True,
        "rag_embedding_provider_enabled": True,
        "rag_source_judge_provider_enabled": True,
        "rag_local_support_enabled": True,
        "rag_ai_api_key": "test-answer-key",
        "rag_embedding_api_key": "test-embedding-key",
        "rag_source_judge_api_key": "test-source-judge-key",
        "rag_ai_quota_bucket": "test-answer",
        "rag_embedding_quota_bucket": "test-embedding",
        "rag_source_judge_quota_bucket": "test-source-judge",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def test_rag_profile_keeps_indexing_available_and_fails_ask_closed_on_subject_space_mismatch(db):
    from app.routers.rag import get_rag_profile

    _owner, student, _outsider, subject, _session = await _seed(db)
    settings = _settings()
    no_active = await get_rag_profile(subject.id, student, db, settings)
    assert no_active.embedding_available is True
    assert no_active.active_embedding_provider is None
    assert no_active.active_embedding_space_matches is False
    assert no_active.ask_enabled is False
    assert no_active.answer_available is False

    identity = list(settings.rag_embedding_space_identity)
    identity[3] = "staged-other-space"
    identity = tuple(identity)
    other = RagEmbeddingSpace(
        identity_hash=embedding_space_hash(identity),
        provider=identity[0], base_url=identity[1], model=identity[2],
        space_revision=identity[3], format_version=identity[4],
        dimensions=identity[5], representation=identity[6], metric=identity[7],
        document_task_mode=identity[8], query_task_mode=identity[9],
    )
    db.add(other)
    subject.active_embedding_space_hash = other.identity_hash
    await db.commit()

    mismatched = await get_rag_profile(subject.id, student, db, settings)
    assert mismatched.embedding_available is True
    assert mismatched.embedding_provider == settings.rag_embedding_provider
    assert mismatched.active_embedding_provider == other.provider
    assert mismatched.active_embedding_model == other.model
    assert mismatched.active_embedding_space_matches is False
    assert mismatched.answer_available is False


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


async def _activate_space(db, subject: Subject, settings: Settings) -> None:
    identity = settings.rag_embedding_space_identity
    space = RagEmbeddingSpace(
        identity_hash=embedding_space_hash(identity),
        provider=identity[0], base_url=identity[1], model=identity[2],
        space_revision=identity[3], format_version=identity[4],
        dimensions=identity[5], representation=identity[6], metric=identity[7],
        document_task_mode=identity[8], query_task_mode=identity[9],
    )
    db.add(space)
    subject.active_embedding_space_hash = space.identity_hash
    await db.commit()


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


def test_v5_cost_ceiling_matches_snapshot_prices_and_both_stage_limits():
    settings = _settings(
        rag_source_judge_input_cost_per_million_usd="0.3000001",
        rag_source_judge_output_cost_per_million_usd="2.5000001",
    )
    embedding = 308  # ceil(2048 maximum query tokens * USD 0.15/1M)
    judge = (32_768 * 300_001 + 4_096 * 2_500_001 + 999_999) // 1_000_000
    assert _attempt_estimate_microusd(settings) == embedding + judge


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
    assert first.answer_policy_version == ASK_REQUIRED_RELEASE_POLICY_VERSION
    assert first.source_judge_provider == "gemini"
    assert first.source_judge_base_url == "https://generativelanguage.googleapis.com"
    assert first.source_judge_model == "gemini-3.5-flash-lite"
    assert first.source_judge_contract_version == settings.rag_source_judge_contract_version
    assert first.source_judge_input_price_microusd_per_million == 300_000
    assert first.source_judge_output_price_microusd_per_million == 2_500_000
    assert first.source_judge_max_input_tokens == 32_768
    assert first.source_judge_max_output_tokens == 4_096
    assert first.source_judge_thinking_level == "high"
    assert first.source_judge_timeout_seconds == 120
    assert first.estimated_input_tokens == 2_048 + 32_768
    assert first.estimated_output_tokens == 4_096
    assert first.estimated_cost_microusd == 20_379
    assert first.ai_provider is None and first.ai_model is None
    assert first.answer_message_id is None and first.result_kind is None
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
        rag_answer_max_messages_per_thread=2,
        rag_answer_max_messages_per_user=2,
        rag_answer_max_messages_deployment=2,
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
    # Source-only admission stores just a question row. Two questions fit this
    # budget; a third does not reserve a synthetic assistant message.
    async with db.begin():
        await service.enqueue(
            db,
            subject_id=subject_id,
            thread_id=student_thread_id,
            user=student,
            data=RagQuestionCreate(question="First reserved answer"),
            idempotency_key="ask-ai-deployment-storage-0001",
        )
    async with db.begin():
        db.add(RagMessage(
            thread_id=owner_thread_id, user_id=owner_id, subject_id=subject_id,
            role="user", content="Earlier lecture lookup", source_count=0,
            created_at=utcnow(), expires_at=utcnow() + timedelta(days=90),
        ))
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
    await _activate_space(db, subject, settings)
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

    # A retryable embedding failure is a separate explicit transition. The new
    # authentication session replaces the stale submission session.
    now = utcnow()
    second_session = AuthSession(
        user_id=student.id, refresh_jti_hash=uuid4().hex * 2,
        expires_at=now + timedelta(hours=1),
    )
    db.add(second_session)
    await db.flush()
    await db.commit()
    async with db.begin():
        retry_job = await service.enqueue(
            db, subject_id=subject.id, thread_id=thread.id, user=student,
            data=RagQuestionCreate(question="Retry this lecture lookup"),
            idempotency_key="ask-ai-failed-embedding-0001",
        )
        retry_job.status = "failed"
        retry_job.completed_at = now
        retry_job.provider_call_started_at = now
        retry_job.actual_input_tokens = 41
        retry_job.actual_output_tokens = 0
        retry_job.provider_request_count = 1
        retry_job.actual_cost_microusd = 111
        retry_job.attempt_cost_microusd = 111
        retry_job.attempt_cost_unknown = True
        retry_job.usage_estimated = True
        retry_job.execution_uncertain = True
        retry_job.failed_stage = "query_embedding"
        retry_job.provider_error_category = "embedding_provider_timeout"
        retry_job.error_code = "rag_answer_failed"
        retry_job.error_message = "Answer generation failed."
        retry_job.error_retryable = True
    historical_diagnostics = await answer_job_diagnostics(db, retry_job.id)
    assert historical_diagnostics is not None
    assert historical_diagnostics["stages"] == []
    response = service.job_response(retry_job)
    assert response.estimated_additional_cost_microusd == retry_job.estimated_cost_microusd
    assert response.previous_attempt_cost_microusd is None
    unpriced = RagAnswerService(
        settings.model_copy(update={"rag_embedding_input_cost_per_million_usd": 0})
    ).job_response(retry_job)
    assert unpriced.estimated_additional_cost_microusd is None
    assert unpriced.previous_attempt_cost_microusd is None
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
    assert retried.provider_call_started_at is None
    assert retried.retrieval_completed_at is None
    assert retried.attempt_cost_microusd == 0
    assert retried.attempt_cost_unknown is False
    assert service.job_response(retried).actual_cost_microusd is None
    assert retried.execution_uncertain is False
    assert retried.failed_stage is None
    assert retried.provider_error_category is None
    assert retried.provider_request_count == 1
    assert retried.actual_input_tokens == 41
    assert retried.actual_output_tokens == 0
    assert retried.actual_cost_microusd == 111
    assert retried.usage_estimated is True
    assert retried.support_rejection_count == 0


@pytest.mark.parametrize("change", [
    {"rag_source_judge_model": "gemini-3.7-flash"},
    {"rag_source_judge_input_cost_per_million_usd": Decimal("0.31")},
    {"rag_source_judge_output_cost_per_million_usd": Decimal("2.51")},
    {"rag_source_judge_max_input_tokens": 8_000},
    {"rag_source_judge_max_output_tokens": 1_000},
    {"rag_source_judge_thinking_level": "low"},
    {"rag_source_judge_provider_timeout_seconds": 30},
    "contract",
])
async def test_manual_retry_rejects_changed_source_judge_snapshot(db, monkeypatch, change):
    _owner, student, _outsider, subject, auth = await _seed(db)
    settings = _settings()
    await _activate_space(db, subject, settings)
    monkeypatch.setattr(KnowledgeRetriever, "authorize", _authorize(settings))
    service = RagAnswerService(settings)
    async with db.begin():
        thread = await service.create_thread(db, subject_id=subject.id, user=student)
        job = await service.enqueue(
            db, subject_id=subject.id, thread_id=thread.id, user=student,
            data=RagQuestionCreate(question="Find the lecture page"),
            idempotency_key="v5-retry-snapshot-original",
        )
        job.status = "failed"
        job.completed_at = utcnow()
        job.error_code = "rag_answer_failed"
        job.error_message = "Answer generation failed."
        job.error_retryable = True
    if change == "contract":
        monkeypatch.setattr(
            "app.ai.source_judgment_visual_v5.CONTRACT_VERSION",
            "visual_source_id_incompatible",
        )
        changed_service = RagAnswerService(settings)
    else:
        changed_service = RagAnswerService(settings.model_copy(update=change))
    setattr(student, "_auth_session_id", auth.id)
    with pytest.raises(HTTPException) as rejected:
        async with db.begin():
            await changed_service.retry(
                db, subject_id=subject.id, thread_id=thread.id,
                job_id=job.id, user=student,
                idempotency_key="v5-retry-snapshot-changed",
            )
    assert rejected.value.status_code == 409
    assert rejected.value.detail["code"] == "rag_answer_snapshot_changed"


async def test_answer_diagnostic_constraints_reject_private_reason_payload(db, monkeypatch):
    _owner, student, _outsider, subject, _session = await _seed(db)
    configured = _settings()
    service = RagAnswerService(configured)
    monkeypatch.setattr(KnowledgeRetriever, "authorize", _authorize(configured))
    async with db.begin():
        thread = await service.create_thread(db, subject_id=subject.id, user=student)
        job = await service.enqueue(
            db, subject_id=subject.id, thread_id=thread.id, user=student,
            data=RagQuestionCreate(question="What is the topic?"),
            idempotency_key=str(uuid4()),
        )
        job_id = job.id
    with pytest.raises(IntegrityError):
        async with db.begin():
            job = await db.get(RagAnswerJob, job_id)
            job.failure_reason = "private lecture phrase"
            await db.flush()
    with pytest.raises(IntegrityError):
        async with db.begin():
            db.add(RagAnswerStageAttempt(
                job_id=job_id, manual_retry_number=0, worker_attempt_number=1,
                stage="retrieval", answer_policy_version=ASK_REQUIRED_RELEASE_POLICY_VERSION,
                failure_reason="private claim phrase",
            ))
            await db.flush()
    diagnostics = await answer_job_diagnostics(db, job_id)
    assert diagnostics is not None
    assert diagnostics["failure_reason"] is None
    assert diagnostics["stages"] == []
    assert "private" not in str(diagnostics)
    assert service.job_response(await db.get(RagAnswerJob, job_id)).failure_kind is None


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
        async def embed_query(self, text):
            pytest.fail("expired answer job called the embedding provider")

    worker = RagAnswerWorker(
        settings=settings,
        session_factory=session_factory,
        embedding_provider=NeverProvider(),
        worker_id="deadline-worker",
    )
    assert await worker.claim_next() is None
    async with session_factory() as db:
        terminal = await db.get(RagAnswerJob, job.id)
        assert terminal.status == "failed"
        assert terminal.error_code == "rag_answer_failed"
        assert terminal.error_retryable is True


@pytest.mark.parametrize(
    "snapshot_field,retired_value",
    [
        ("answer_policy_version", "legacy_three_call_v1"),
        ("support_policy_version", "remote_support_v1"),
    ],
)
async def test_retired_answer_snapshots_cannot_claim_or_manual_retry(
    session_factory,
    monkeypatch,
    snapshot_field,
    retired_value,
):
    async with session_factory() as db:
        _owner, student, _outsider, subject, auth = await _seed(db)
        student_id, subject_id, auth_id = student.id, subject.id, auth.id
    settings = _settings()
    service = RagAnswerService(settings)
    monkeypatch.setattr(KnowledgeRetriever, "authorize", _authorize(settings))
    async with session_factory() as db:
        async with db.begin():
            current_student = await db.get(User, student_id)
            setattr(current_student, "_auth_session_id", auth_id)
            thread = await service.create_thread(
                db, subject_id=subject_id, user=current_student
            )
            job = await service.enqueue(
                db,
                subject_id=subject_id,
                thread_id=thread.id,
                user=current_student,
                data=RagQuestionCreate(question="What is the retained policy?"),
                idempotency_key=f"retired-{snapshot_field}-0001",
            )
            # Historical answer jobs keep their old identity shape. They may
            # remain readable but may never be claimed by the source-only worker.
            job.embedding_provider = None
            job.embedding_base_url = None
            job.embedding_model = None
            job.source_judge_provider = None
            job.source_judge_base_url = None
            job.source_judge_model = None
            job.source_judge_contract_version = None
            job.source_judge_input_price_microusd_per_million = None
            job.source_judge_output_price_microusd_per_million = None
            job.source_judge_max_input_tokens = None
            job.source_judge_max_output_tokens = None
            job.source_judge_thinking_level = None
            job.source_judge_timeout_seconds = None
            job.source_context_policy_version = None
            job.source_context_admission_sha256 = None
            with db.no_autoflush:
                await db.execute(delete(RagAnswerQuestionContext).where(RagAnswerQuestionContext.job_id == job.id))
            job.ai_provider = settings.rag_ai_provider
            job.ai_base_url = settings.rag_ai_endpoint_identity
            job.ai_model = settings.rag_ai_model
            job.ai_catalog_version = CATALOG_VERSION
            job.ai_schema_policy_version = SCHEMA_POLICY_VERSION
            job.answer_policy_version = "two_request_local_support_v1"
            job.support_policy_version = LOCAL_SUPPORT_POLICY_VERSION
            setattr(job, snapshot_field, retired_value)
            job_id, thread_id = job.id, thread.id
        historical = service.job_response(job)
        assert historical.ask_policy == job.answer_policy_version
        assert historical.result_kind is None
        assert historical.ai_provider == "gemini"
        assert historical.source_judge_provider is None
        assert historical.source_judge_model is None
        assert historical.can_retry is False

    class NeverProvider:
        async def embed_query(self, _text):
            pytest.fail("retired answer snapshot called the embedding provider")

    worker = RagAnswerWorker(
        settings=settings,
        session_factory=session_factory,
        embedding_provider=NeverProvider(),
        worker_id=f"retired-{snapshot_field}-worker",
    )
    assert await worker.claim_next() is None

    async with session_factory() as db:
        async with db.begin():
            terminal = await db.get(RagAnswerJob, job_id, with_for_update=True)
            assert terminal.status == "failed"
            assert terminal.error_code == "rag_profile_mismatch"
            terminal.error_retryable = True
            current_student = await db.get(User, student_id)
            setattr(current_student, "_auth_session_id", auth_id)
            with pytest.raises(HTTPException) as rejected:
                await service.retry(
                    db,
                    subject_id=subject_id,
                    thread_id=thread_id,
                    job_id=job_id,
                    user=current_student,
                    idempotency_key=f"retired-{snapshot_field}-retry-0001",
                )
            assert rejected.value.status_code == 409
            assert rejected.value.detail["code"] == "rag_answer_not_retryable"


@pytest.mark.parametrize(
    "mode,expected_status,expected_result_kind,expected_stages",
    [
        ("related_knowledge", "completed", "related_knowledge", {"query_embedding", "retrieval", "source_judgment"}),
        ("canonical_page", "completed", "related_knowledge", {"query_embedding", "retrieval", "source_judgment"}),
        ("canonical_page_changed", "failed", None, {"query_embedding", "retrieval"}),
        ("canonical_anchor_changed", "failed", None, {"query_embedding", "retrieval"}),
        ("no_match", "completed", "no_match", {"query_embedding", "retrieval"}),
        ("embedding_failure", "failed", None, {"query_embedding"}),
        ("embedding_timeout", "completed", "no_match", {"query_embedding", "retrieval"}),
        ("retrieval_timeout", "failed", None, {"query_embedding", "retrieval"}),
    ],
)
async def test_historical_v4_source_worker_uses_one_embedding_and_no_answer_provider(
    session_factory, monkeypatch, mode, expected_status,
    expected_result_kind, expected_stages,
):
    """Retain explicit historical v4 text-selection regression without provider I/O.

    The separate visual worker suite exercises current v5 PDF/image preparation.
    This fixture deliberately restores the complete historical snapshot and
    release identity rather than feeding text-only fake output to a v5 job.
    """

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
            id=uuid4(), email=f"worker-{uuid4().hex}@example.test",
            hashed_password="not-real", role=UserRole.STUDENT,
        )
        db.add(student)
        await db.flush()
        db.add(Enrollment(student_id=student.id, subject_id=subject.id))
        auth = AuthSession(
            user_id=student.id, refresh_jti_hash=uuid4().hex * 2,
            expires_at=now + timedelta(hours=1),
        )
        db.add(auth)
        chunk_row = await db.scalar(select(SubjectDocumentChunk).where(
            SubjectDocumentChunk.index_revision_id == index.id
        ))
        assert chunk_row is not None
        canonical_mode = mode.startswith("canonical_")
        canonical_page_text = "Perihelion\n- Is the point of an orbit nearest to the Sun."
        if canonical_mode:
            chunk_row.content = "- Is the point of an orbit nearest to the Sun."
            chunk_row.section = "Perihelion"
            page_row = await db.scalar(select(SubjectDocumentPage).where(
                SubjectDocumentPage.content_revision_id == content.id,
                SubjectDocumentPage.page_number == chunk_row.page_number,
            ))
            assert page_row is not None
            page_row.content = canonical_page_text
        await db.commit()

    settings = seeded.model_copy(update={
        "rag_ask_enabled": True,
        "rag_ai_provider_enabled": False,
        "rag_ai_api_key": None,
        "rag_local_support_enabled": False,
        "rag_source_judge_provider_enabled": True,
        "rag_source_judge_api_key": "test-source-judge-key",
        "rag_source_judge_quota_bucket": "test-source-judge",
    })
    assert settings.rag_source_only_available
    source = RetrievedKnowledgeChunk(
        chunk_id=chunk_row.id, document_id=document.id,
        document_title=document.title, content_revision_id=content.id,
        index_revision_id=index.id, page_number=chunk_row.page_number,
        section=chunk_row.section, content=chunk_row.content,
        token_count=chunk_row.token_count,
        embedding_space_hash=index.embedding_space_hash,
        corpus_revision=subject.corpus_revision,
        vector_similarity=1.0, lexical_score=1.0,
        vector_rank=1, lexical_rank=1, fusion_score=1.0,
    )

    class FakeRetriever:
        page_reads = 0
        scope = SimpleNamespace(
            corpus_revision=subject.corpus_revision,
            embedding_space_hash=index.embedding_space_hash,
        )

        async def retrieve(self, _vector, *, embedding_space_hash):
            assert embedding_space_hash == index.embedding_space_hash
            if mode == "retrieval_timeout":
                raise TimeoutError("private retrieval fixture detail")
            if mode == "no_match":
                return SimpleNamespace(insufficient=True, chunks=())
            return SimpleNamespace(insufficient=False, chunks=(source,))

        async def retrieve_lexical(self):
            assert mode == "embedding_timeout"
            return SimpleNamespace(insufficient=True, chunks=())

        async def expand_source_neighbors(self, anchors, **kwargs):
            assert tuple(anchors) == (source,) and kwargs["radius"] == 2
            return ()

        async def read_current_sources(self, chunk_ids):
            assert tuple(chunk_ids) == (source.chunk_id,)
            if mode == "canonical_anchor_changed":
                return (replace(source, content="- Is a different point."),)
            return (source,)

        async def read_current_source_pages(self, chunk_ids, *, max_pages=12, max_tokens=8_192):
            assert tuple(chunk_ids) == (source.chunk_id,)
            self.page_reads += 1
            if mode == "canonical_page_changed" and self.page_reads > 1:
                return {source.chunk_id: "Perihelion\n- Is a different point."}
            return {source.chunk_id: canonical_page_text if canonical_mode else source.content}

    retriever = FakeRetriever()

    async def authorize(_cls, _db, **_kwargs):
        return retriever

    monkeypatch.setattr(KnowledgeRetriever, "authorize", classmethod(authorize))
    service = RagAnswerService(settings)
    async with session_factory() as db:
        async with db.begin():
            principal = await db.get(User, student.id)
            setattr(principal, "_auth_session_id", auth.id)
            thread = await service.create_thread(
                db, subject_id=subject.id, user=principal
            )
            job = await service.enqueue(
                db, subject_id=subject.id, thread_id=thread.id, user=principal,
                data=RagQuestionCreate(question="What is perihelion?"),
                idempotency_key=f"source-worker-{mode}-0001",
            )
            job_id = job.id
            job.answer_policy_version = "related_knowledge_navigation_v4"
            job.source_context_policy_version = None
            job.source_context_admission_sha256 = None
            with db.no_autoflush:
                await db.execute(delete(RagAnswerQuestionContext).where(RagAnswerQuestionContext.job_id == job.id))
            job.source_judge_model = "gemini-3.8-flash"
            job.source_judge_contract_version = "source_id_only_public_v1"
            job.source_judge_input_price_microusd_per_million = 1_500_000
            job.source_judge_output_price_microusd_per_million = 7_500_000
            job.source_judge_max_input_tokens = 8192
            job.source_judge_max_output_tokens = 1024
            job.source_judge_thinking_level = None
            job.source_judge_timeout_seconds = None
            job.estimated_input_tokens = 2048 + 8192
            job.estimated_output_tokens = 1024
            job.estimated_cost_microusd = 20_276

    for module in ("app.config", "app.services.rag_answers", "app.workers.rag_answer"):
        monkeypatch.setattr(module + ".ASK_REQUIRED_RELEASE_POLICY_VERSION", "related_knowledge_navigation_v4")
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", "related_knowledge_navigation_v4")
    monkeypatch.setattr(Settings, "rag_source_judge_contract_version", property(lambda _self: "source_id_only_public_v1"))
    settings = settings.model_copy(update={
        "rag_source_judge_model": "gemini-3.8-flash",
        "rag_source_judge_max_input_tokens": 8192, "rag_source_judge_max_output_tokens": 1024,
        "rag_source_judge_provider_timeout_seconds": 30,
        "rag_source_judge_input_cost_per_million_usd": Decimal("1.50"),
        "rag_source_judge_output_cost_per_million_usd": Decimal("7.50"),
    })

    class FakeEmbeddingProvider:
        def __init__(self):
            self.questions = []

        async def embed_query(self, question):
            self.questions.append(question)
            if mode == "embedding_timeout":
                raise TimeoutError("private embedding fixture detail")
            if mode == "embedding_failure":
                raise AIProviderError(
                    "embedding_provider_invalid_request",
                    "Embedding request failed.", retryable=False,
                )
            return EmbeddingResponse(
                vectors=(tuple([1.0, *([0.0] * 1535)]),),
                usage=ProviderUsage(3, 0, False),
            )

    embedding_provider = FakeEmbeddingProvider()
    class FakeJudge:
        def __init__(self):
            self.wires = []

        async def judge(self, wire):
            self.wires.append(wire)
            return _JudgeResponse('{"selected_ids":["S01"]}', "STOP", 20, 4, 2)

    judge = FakeJudge()
    worker = RagAnswerWorker(
        settings=settings, session_factory=session_factory,
        embedding_provider=embedding_provider,
        source_judge=judge,
        worker_id="offline-source-worker",
    )
    assert not hasattr(worker, "answer_provider")
    assert not hasattr(worker, "local_support_verifier")
    claim = await worker.claim_next()
    assert claim and claim[0] == job_id
    await worker.process_claim(*claim)

    async with session_factory() as db:
        stored = await db.get(RagAnswerJob, job_id)
        assert stored.answer_policy_version == "related_knowledge_navigation_v4"
        assert stored.source_judge_thinking_level is stored.source_judge_timeout_seconds is None
        assert stored.status == expected_status, (
            stored.failed_stage, stored.provider_error_category, stored.failure_reason
        )
        assert stored.result_kind == expected_result_kind
        assert stored.answer_message_id is None
        assert stored.provider_request_count == (2 if "source_judgment" in expected_stages else 1)
        assert stored.provider_retry_count == 0
        assert stored.actual_output_tokens in (None, 0, 6)
        assert embedding_provider.questions == ["What is perihelion?"]
        messages = (await db.scalars(select(RagMessage).where(
            RagMessage.thread_id == thread.id
        ))).all()
        assert [(message.role, message.content) for message in messages] == [
            ("user", "What is perihelion?")
        ]
        stages = (await db.scalars(select(RagAnswerStageAttempt).where(
            RagAnswerStageAttempt.job_id == job_id
        ))).all()
        assert {stage.stage for stage in stages} == expected_stages
        assert sum(stage.physical_request_count for stage in stages) == stored.provider_request_count
        assert all(stage.completed_at is not None for stage in stages)
        refs = (await db.scalars(select(RagRelatedEvidence).where(
            RagRelatedEvidence.job_id == job_id
        ))).all()
        if mode in {"related_knowledge", "canonical_page"}:
            assert len(refs) == 1
            assert refs[0].chunk_id == source.chunk_id
            if mode == "canonical_page":
                assert refs[0].source_kind == "canonical_page"
                assert canonical_page_text[refs[0].start_offset:refs[0].end_offset] == canonical_page_text
                assert refs[0].end_offset > len(source.content)
            else:
                authoritative = source.content
                assert authoritative[refs[0].start_offset:refs[0].end_offset] == source.content
            assert stored.actual_input_tokens == 23
            assert not stored.attempt_cost_unknown
        else:
            assert refs == []
        if mode == "no_match":
            assert stored.error_code is None
            assert stored.actual_input_tokens == 3
        elif mode == "embedding_failure":
            assert stored.failed_stage == "query_embedding"
            assert stored.provider_error_category == "embedding_provider_invalid_request"
            assert stored.attempt_cost_unknown
        elif mode == "embedding_timeout":
            assert stored.failed_stage == "query_embedding"
            assert stored.provider_error_category == "embedding_provider_timeout"
            assert stored.execution_uncertain and stored.attempt_cost_unknown
        elif mode == "retrieval_timeout":
            assert stored.failed_stage == "retrieval"
            assert stored.provider_error_category == "retrieval_failed"
            assert stored.failure_reason == "retrieval_timeout"
        if mode in {"canonical_page_changed", "canonical_anchor_changed"}:
            assert stored.error_code == "rag_corpus_changed"
        elif expected_status == "failed":
            assert stored.error_code == "rag_answer_failed"
        diagnostics = await answer_job_diagnostics(db, job_id)
        assert diagnostics is not None
        assert len(diagnostics["stages"]) == len(expected_stages)
async def test_answer_worker_disabled_lifecycle_reports_health_and_drains(
    monkeypatch,
):
    stop = asyncio.Event()
    worker = RagAnswerWorker(
        settings=_settings(rag_enabled=False),
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

    settings = _settings()
    async with session_factory() as seed_db:
        owner, student, outsider, subject, auth = await _seed(seed_db)
        identity = settings.rag_embedding_space_identity
        space = RagEmbeddingSpace(
            identity_hash=embedding_space_hash(identity),
            provider=identity[0], base_url=identity[1], model=identity[2],
            space_revision=identity[3], format_version=identity[4],
            dimensions=identity[5], representation=identity[6], metric=identity[7],
            document_task_mode=identity[8], query_task_mode=identity[9],
        )
        seed_db.add(space)
        subject.active_embedding_space_hash = space.identity_hash
        await seed_db.commit()
        owner_id, student_id, outsider_id = owner.id, student.id, outsider.id
        subject_id, auth_id = subject.id, auth.id

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
                "ask_enabled": True,
                "ask_available": True,
                "ask_policy": ASK_REQUIRED_RELEASE_POLICY_VERSION,
                "answer_available": False,
                "answer_provider": None,
                "answer_model": None,
                "source_judge_available": True,
                "source_judge_provider": settings.rag_source_judge_provider,
                "source_judge_model": settings.rag_source_judge_model,
                "source_judge_transfers_published_content": True,
                "source_judge_transfers_page_images": True,
                "source_judge_transfers_literal_subject_context": True,
                "source_judge_thinking_level": "HIGH",
                "source_judge_contract_version": "visual_source_id_v5",
                "embedding_available": True,
                "embedding_provider": settings.rag_embedding_provider,
                "embedding_model": settings.rag_embedding_model,
                "active_embedding_provider": settings.rag_embedding_provider,
                "active_embedding_model": settings.rag_embedding_model,
                "active_embedding_space_matches": True,
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
