from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from starlette.requests import Request

from app.config import Settings
from app.main import app
from app.models.flashcard import Flashcard
from app.models.generation import GenerationJob, GenerationJobSource, GenerationJobStatus
from app.models.subject import FlashcardSet, Subject
from app.models.user import User, UserRole
from app.schemas.generation import GenerationJobCreate
from app.services.generation import GenerationJobService, read_bounded_pdf_body
from app.services.pdf_processor import PDFProcessingError
from app.services.source_storage import SourceStorage
from app.time_utils import utcnow
from app.workers.generation import GenerationWorker, LeaseLost, ModelGenerationFailure


def make_settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "database_url": "sqlite+aiosqlite:///:memory:",
        "secret_key": "test-only-secret-key-with-adequate-entropy-1234567890",
        "generation_source_encryption_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "ai_provider_enabled": True,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def test_static_generation_routes_precede_dynamic_flashcard_route(db):
    from httpx import ASGITransport, AsyncClient
    from app.database import get_db
    from app.routers.auth import get_current_instructor

    owner, subject = await seed_owner_subject(db)
    async def test_db():
        yield db
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[get_current_instructor] = lambda: owner
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for path in ["/flashcards/generation-limits", "/flashcards/generation-jobs"]:
                response = await client.get(path, params={"subject_id": str(subject.id)})
                assert response.status_code == 200, response.text
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_generation_worker_owns_one_shared_provider_rate_governor():
    worker = GenerationWorker(settings=make_settings(), worker_id="quota-owner")

    assert worker.provider_rate_governor.requests_per_window == 4
    assert worker.provider_rate_governor.input_tokens_per_window == 200_000


async def seed_owner_subject(db) -> tuple[User, Subject]:
    owner = User(
        id=uuid4(),
        email=f"owner-{uuid4().hex}@example.test",
        hashed_password="not-a-real-password-hash",
        role=UserRole.INSTRUCTOR,
    )
    subject = Subject(id=uuid4(), name="Durable jobs", instructor_id=owner.id)
    db.add_all([owner, subject])
    await db.commit()
    return owner, subject


def job_data(subject_id, **overrides) -> GenerationJobCreate:
    values = {
        "subject_id": subject_id,
        "set_title": "Bounded set",
        "source_pdf_name": "lesson.pdf",
        "card_count": 5,
    }
    values.update(overrides)
    return GenerationJobCreate(**values)


async def test_reservation_idempotency_and_mismatch(db):
    owner, subject = await seed_owner_subject(db)
    service = GenerationJobService(make_settings())
    async with db.begin():
        first = await service.create_reservation(
            db,
            user_id=owner.id,
            data=job_data(subject.id),
            idempotency_key="reservation-key-1",
        )
    async with db.begin():
        replay = await service.create_reservation(
            db,
            user_id=owner.id,
            data=job_data(subject.id),
            idempotency_key="reservation-key-1",
        )
    assert replay.id == first.id
    assert replay.idempotency_key_hash != "reservation-key-1"

    with pytest.raises(HTTPException) as error:
        async with db.begin():
            await service.create_reservation(
                db,
                user_id=owner.id,
                data=job_data(subject.id, set_title="Different"),
                idempotency_key="reservation-key-1",
            )
    assert error.value.status_code == 409
    assert error.value.detail["code"] == "idempotency_key_reused"


async def test_generation_job_response_exposes_request_telemetry(db):
    owner, subject = await seed_owner_subject(db)
    service = GenerationJobService(make_settings())
    async with db.begin():
        job = await service.create_reservation(
            db,
            user_id=owner.id,
            data=job_data(subject.id),
            idempotency_key="request-telemetry-response",
        )
        job.estimated_request_count = 4
        job.provider_request_count = 3
        job.provider_retry_count = 1
        job.provider_rate_limit_wait_milliseconds = 12_500
        job.cached_input_tokens = 8_192
        job.provider_request_counts_by_stage = {"planning": 1, "card_generation": 2}

    response = await service.to_response(db, job)

    assert response.estimated_request_count == 4
    assert response.provider_request_count == 3
    assert response.provider_retry_count == 1
    assert response.provider_rate_limit_wait_milliseconds == 12_500
    assert response.cached_input_tokens == 8_192
    assert response.provider_request_counts_by_stage == {
        "planning": 1,
        "card_generation": 2,
    }


async def test_request_telemetry_is_additive_and_stage_json_changes_persist(db):
    owner, subject = await seed_owner_subject(db)
    service = GenerationJobService(make_settings())
    async with db.begin():
        job = await service.create_reservation(
            db,
            user_id=owner.id,
            data=job_data(subject.id),
            idempotency_key="additive-request-telemetry",
        )
        GenerationWorker._apply_telemetry(
            job,
            {
                "estimated_request_count": 6,
                "provider_request_count": 2,
                "provider_retry_count": 1,
                "provider_rate_limit_wait_milliseconds": 500,
                "cached_input_tokens": 20,
                "provider_request_counts_by_stage": {"summary_map": 2},
            },
        )
    async with db.begin():
        GenerationWorker._apply_telemetry(
            job,
            {
                "estimated_request_count": 4,
                "provider_request_count": 3,
                "provider_retry_count": 0,
                "provider_rate_limit_wait_milliseconds": 1_500,
                "cached_input_tokens": 30,
                "provider_request_counts_by_stage": {
                    "summary_map": 1,
                    "card_generation": 2,
                },
            },
        )
    await db.refresh(job)

    assert job.estimated_request_count == 6
    assert job.provider_request_count == 5
    assert job.provider_retry_count == 1
    assert job.provider_rate_limit_wait_milliseconds == 2_000
    assert job.cached_input_tokens == 50
    assert job.provider_request_counts_by_stage == {
        "summary_map": 3,
        "card_generation": 2,
    }


async def test_source_is_encrypted_and_queued_then_cancelled(db):
    owner, subject = await seed_owner_subject(db)
    service = GenerationJobService(make_settings())
    source_bytes = b"%PDF-1.7\nprivate-document-bytes"
    async with db.begin():
        job = await service.create_reservation(
            db,
            user_id=owner.id,
            data=job_data(subject.id),
            idempotency_key="reservation-key-2",
        )
    async with db.begin():
        job = await service.attach_source(
            db,
            job_id=job.id,
            user_id=owner.id,
            media_type="application/pdf",
            content=source_bytes,
        )
    source = await db.get(GenerationJobSource, job.id)
    assert source is not None
    assert source.payload != source_bytes
    assert SourceStorage.decrypt(source.nonce, source.payload, job.request_fingerprint) == source_bytes
    assert job.status == GenerationJobStatus.QUEUED.value
    job_id = job.id
    owner_id = owner.id
    await db.rollback()

    async with db.begin():
        cancelled = await service.cancel(db, job_id=job_id, user_id=owner_id)
    assert cancelled.status == GenerationJobStatus.CANCELLED.value
    assert await db.get(GenerationJobSource, job_id) is None


async def test_daily_quota_is_charged_when_source_is_accepted(db):
    owner, subject = await seed_owner_subject(db)
    service = GenerationJobService(
        make_settings(generation_daily_jobs_per_user=1, generation_max_active_jobs_per_user=2)
    )
    async with db.begin():
        first = await service.create_reservation(
            db,
            user_id=owner.id,
            data=job_data(subject.id),
            idempotency_key="quota-reservation-1",
        )
    async with db.begin():
        await service.attach_source(
            db,
            job_id=first.id,
            user_id=owner.id,
            media_type="application/pdf",
            content=b"%PDF-1.7\nfirst",
        )
    async with db.begin():
        second = await service.create_reservation(
            db,
            user_id=owner.id,
            data=job_data(subject.id),
            idempotency_key="quota-reservation-2",
        )
    with pytest.raises(HTTPException) as error:
        async with db.begin():
            await service.attach_source(
                db,
                job_id=second.id,
                user_id=owner.id,
                media_type="application/pdf",
                content=b"%PDF-1.7\nsecond",
            )
    assert error.value.status_code == 429
    assert error.value.detail["code"] == "user_daily_job_limit"


async def test_retry_is_bounded_and_idempotent(db):
    owner, subject = await seed_owner_subject(db)
    service = GenerationJobService(make_settings())
    async with db.begin():
        job = await service.create_reservation(
            db,
            user_id=owner.id,
            data=job_data(subject.id),
            idempotency_key="retry-reservation-1",
        )
    async with db.begin():
        job = await service.attach_source(
            db,
            job_id=job.id,
            user_id=owner.id,
            media_type="application/pdf",
            content=b"%PDF-1.7\nretry",
        )
        job.status = GenerationJobStatus.FAILED.value
        job.stage = "failed"
        job.progress = 100
        job.error_retryable = True
        job.completed_at = utcnow()
        source = await db.get(GenerationJobSource, job.id)
        source.expires_at = utcnow() + timedelta(hours=1)
    async with db.begin():
        retried = await service.retry(
            db,
            job_id=job.id,
            user_id=owner.id,
            idempotency_key="manual-retry-key-1",
        )
    async with db.begin():
        replay = await service.retry(
            db,
            job_id=job.id,
            user_id=owner.id,
            idempotency_key="manual-retry-key-1",
        )
    assert retried.status == GenerationJobStatus.QUEUED.value
    assert replay.id == retried.id
    assert retried.manual_retry_count == 1


async def test_worker_completion_is_atomic_and_stale_claim_cannot_repeat(session_factory):
    async with session_factory() as db:
        owner, subject = await seed_owner_subject(db)
        service = GenerationJobService(make_settings())
        async with db.begin():
            job = await service.create_reservation(
                db,
                user_id=owner.id,
                data=job_data(subject.id),
                idempotency_key="worker-reservation-1",
            )
        async with db.begin():
            await service.attach_source(
                db,
                job_id=job.id,
                user_id=owner.id,
                media_type="application/pdf",
                content=b"%PDF-1.7\nworker",
            )
        job_id = job.id

    worker = GenerationWorker(settings=make_settings(), session_factory=session_factory, worker_id="test")
    claim = await worker.claim_next()
    assert claim is not None
    claimed_id, token = claim
    assert claimed_id == job_id
    cards = [
        {
            "front_content": "Question?",
            "back_content": "Answer",
            "options": ["Answer", "B", "C", "D"],
            "quality_score": 1.0,
            "source_snippet": "Source",
            "source_page": 1,
            "source_section": "Test",
        }
    ]
    await worker._finish_success(job_id, token, cards)

    async with session_factory() as db:
        completed = await db.get(GenerationJob, job_id)
        assert completed.status == GenerationJobStatus.COMPLETED.value
        assert completed.generated_card_count == 1
        assert await db.scalar(
            select(func.count(FlashcardSet.id)).where(FlashcardSet.generation_job_id == job_id)
        ) == 1
        assert await db.scalar(select(func.count(Flashcard.id))) == 1
        assert await db.get(GenerationJobSource, job_id) is None
        created = await db.scalar(select(Flashcard))
        assert created.is_approved is False
        assert created.quality_score == 1.0
        assert created.source_page == 1

    with pytest.raises(LeaseLost):
        await worker._finish_success(job_id, token, cards)


async def test_worker_permanent_failure_is_terminal_and_deletes_source(
    session_factory, monkeypatch
):
    async with session_factory() as db:
        owner, subject = await seed_owner_subject(db)
        service = GenerationJobService(make_settings())
        async with db.begin():
            job = await service.create_reservation(
                db,
                user_id=owner.id,
                data=job_data(subject.id),
                idempotency_key="worker-permanent-failure",
            )
        async with db.begin():
            await service.attach_source(
                db,
                job_id=job.id,
                user_id=owner.id,
                media_type="application/pdf",
                content=b"%PDF-1.7\npermanent",
            )
        job_id = job.id

    worker = GenerationWorker(
        settings=make_settings(), session_factory=session_factory, worker_id="permanent"
    )
    claim = await worker.claim_next()
    assert claim is not None

    async def fail_pipeline(*_):
        raise PDFProcessingError("image_only_pdf", "No selectable text was found.")

    monkeypatch.setattr(worker, "_pipeline", fail_pipeline)
    await worker.process_claim(*claim)

    async with session_factory() as db:
        failed = await db.get(GenerationJob, job_id)
        assert failed.status == GenerationJobStatus.FAILED.value
        assert failed.error_code == "image_only_pdf"
        assert failed.error_retryable is False
        assert await db.get(GenerationJobSource, job_id) is None


async def test_worker_transient_failure_requeues_with_retained_source(
    session_factory, monkeypatch
):
    async with session_factory() as db:
        owner, subject = await seed_owner_subject(db)
        settings = make_settings(generation_max_attempts=2)
        service = GenerationJobService(settings)
        async with db.begin():
            job = await service.create_reservation(
                db,
                user_id=owner.id,
                data=job_data(subject.id),
                idempotency_key="worker-transient-failure",
            )
        async with db.begin():
            await service.attach_source(
                db,
                job_id=job.id,
                user_id=owner.id,
                media_type="application/pdf",
                content=b"%PDF-1.7\ntransient",
            )
        job_id = job.id

    worker = GenerationWorker(
        settings=settings, session_factory=session_factory, worker_id="transient"
    )
    claim = await worker.claim_next()
    assert claim is not None

    async def fail_pipeline(*_):
        raise ModelGenerationFailure("provider unavailable")

    monkeypatch.setattr(worker, "_pipeline", fail_pipeline)
    await worker.process_claim(*claim)

    async with session_factory() as db:
        queued = await db.get(GenerationJob, job_id)
        assert queued.status == GenerationJobStatus.QUEUED.value
        assert queued.stage == "retry_wait"
        assert queued.error_code == "generation_temporarily_unavailable"
        assert queued.error_retryable is True
        assert queued.claim_token is None
        assert await db.get(GenerationJobSource, job_id) is not None


async def test_worker_records_pipeline_limit_telemetry_and_retains_retryable_source(
    session_factory, monkeypatch
):
    async with session_factory() as db:
        owner, subject = await seed_owner_subject(db)
        service = GenerationJobService(make_settings(generation_max_attempts=1))
        async with db.begin():
            job = await service.create_reservation(
                db,
                user_id=owner.id,
                data=job_data(subject.id),
                idempotency_key="worker-quality-limit",
            )
        async with db.begin():
            await service.attach_source(
                db,
                job_id=job.id,
                user_id=owner.id,
                media_type="application/pdf",
                content=b"%PDF-1.7\nquality",
            )
        job_id = job.id

    worker = GenerationWorker(
        settings=make_settings(generation_max_attempts=1),
        session_factory=session_factory,
        worker_id="quality-limit",
    )
    claim = await worker.claim_next()
    assert claim is not None

    from app.ai.pipeline import PipelineError

    async def fail_pipeline(*_):
        raise PipelineError(
            "insufficient_grounded_cards",
            "Not enough grounded cards.",
            retryable=True,
            estimated_input_tokens=500,
            estimated_output_tokens=250,
            actual_input_tokens=100,
            actual_output_tokens=50,
            usage_estimated=False,
            rejected_card_count=3,
            estimated_request_count=4,
            provider_request_count=3,
            provider_retry_count=1,
            provider_rate_limit_wait_milliseconds=3_500,
            cached_input_tokens=20,
            provider_request_counts_by_stage={
                "summary_map": 1,
                "card_generation": 2,
            },
        )

    monkeypatch.setattr(worker, "_pipeline", fail_pipeline)
    await worker.process_claim(*claim)

    async with session_factory() as db:
        failed = await db.get(GenerationJob, job_id)
        assert failed.status == GenerationJobStatus.FAILED.value
        assert failed.limit_reason_code == "insufficient_grounded_cards"
        assert failed.estimated_input_tokens == 500
        assert failed.actual_input_tokens == 100
        assert failed.actual_output_tokens == 50
        assert failed.rejected_card_count == 3
        assert failed.estimated_request_count == 4
        assert failed.provider_request_count == 3
        assert failed.provider_retry_count == 1
        assert failed.provider_rate_limit_wait_milliseconds == 3_500
        assert failed.cached_input_tokens == 20
        assert failed.provider_request_counts_by_stage == {
            "summary_map": 1,
            "card_generation": 2,
        }
        assert await db.get(GenerationJobSource, job_id) is not None


@pytest.mark.parametrize(
    "failure_code", ["ai_provider_rate_limited", "generation_job_timeout"]
)
async def test_worker_does_not_automatically_repeat_pipeline_provider_failure(
    session_factory, monkeypatch, failure_code
):
    async with session_factory() as db:
        owner, subject = await seed_owner_subject(db)
        configured = make_settings(generation_max_attempts=3)
        service = GenerationJobService(configured)
        async with db.begin():
            job = await service.create_reservation(
                db,
                user_id=owner.id,
                data=job_data(subject.id),
                idempotency_key="provider-rate-limit-reservation",
            )
        async with db.begin():
            await service.attach_source(
                db,
                job_id=job.id,
                user_id=owner.id,
                media_type="application/pdf",
                content=b"%PDF-1.7\nprovider-rate-limit",
            )
        job_id = job.id

    worker = GenerationWorker(
        settings=configured,
        session_factory=session_factory,
        worker_id="provider-rate-limit",
    )
    claim = await worker.claim_next()
    assert claim is not None

    from app.ai.pipeline import PipelineError

    async def fail_pipeline(*_):
        if failure_code == "generation_job_timeout":
            raise TimeoutError("job time budget exhausted")
        raise PipelineError(
            failure_code,
            "The AI provider rate limit was reached. Wait before retrying the job.",
            retryable=True,
        )

    monkeypatch.setattr(worker, "_pipeline", fail_pipeline)
    await worker.process_claim(*claim)

    async with session_factory() as db:
        failed = await db.get(GenerationJob, job_id)
        source = await db.get(GenerationJobSource, job_id)
        assert failed.status == GenerationJobStatus.FAILED.value
        assert failed.stage == "failed"
        assert failed.attempt_count == 1
        assert failed.error_code == failure_code
        assert failed.error_retryable is True
        assert source is not None
        assert source.expires_at is not None


async def test_worker_job_timeout_snapshots_pipeline_request_telemetry(monkeypatch):
    from types import SimpleNamespace

    from app.ai.pipeline import PipelineError

    worker = GenerationWorker(settings=make_settings(), worker_id="timeout-telemetry")
    error = PipelineError(
        "generation_job_timeout",
        "Job time limit reached.",
        retryable=True,
        provider_request_count=4,
        provider_retry_count=1,
        provider_rate_limit_wait_milliseconds=60_000,
    )

    async def time_out(_job_id, _claim_token, holder):
        holder["graph"] = SimpleNamespace(
            pipeline=SimpleNamespace(job_timeout_error=lambda: error)
        )
        raise TimeoutError("job time limit reached")

    monkeypatch.setattr(worker, "_pipeline_with_graph", time_out)
    with pytest.raises(PipelineError) as raised:
        await worker._pipeline(uuid4(), "claim")

    assert raised.value is error
    assert raised.value.provider_request_count == 4
    assert raised.value.provider_retry_count == 1
    assert raised.value.provider_rate_limit_wait_milliseconds == 60_000


async def test_limits_explain_provider_unavailability(db):
    owner, subject = await seed_owner_subject(db)
    owner_id = owner.id
    subject_id = subject.id
    service = GenerationJobService(
        make_settings(ai_provider_enabled=False, ai_api_key="worker-only-key")
    )

    limits = await service.limits(db, owner_id)

    assert limits.generation_available is False
    assert limits.unavailable_reasons[0].code == "ai_provider_not_configured"
    assert limits.ai_provider == "gemini"
    await db.rollback()

    with pytest.raises(HTTPException) as error:
        async with db.begin():
            await service.create_reservation(
                db,
                user_id=owner_id,
                data=job_data(subject_id),
                idempotency_key="disabled-provider-reservation",
            )
    assert error.value.status_code == 503
    assert error.value.detail["code"] == "ai_provider_not_configured"


async def test_limits_use_non_secret_enablement_without_api_credentials(db):
    owner, _ = await seed_owner_subject(db)
    settings = make_settings(
        ai_provider_enabled=True,
        ai_api_key=None,
        gemini_api_key=None,
    )
    assert settings.ai_provider_configured is False

    limits = await GenerationJobService(settings).limits(db, owner.id)

    assert limits.generation_available is True
    assert limits.unavailable_reasons == []


async def test_bounded_raw_request_rejects_declared_and_chunked_overflow():
    scope = {
        "type": "http",
        "method": "PUT",
        "path": "/source",
        "headers": [(b"content-length", b"6")],
    }

    async def no_body():
        return {"type": "http.request", "body": b"", "more_body": False}

    with pytest.raises(HTTPException) as declared:
        await read_bounded_pdf_body(Request(scope, no_body), 5)
    assert declared.value.status_code == 413

    messages = iter(
        [
            {"type": "http.request", "body": b"123", "more_body": True},
            {"type": "http.request", "body": b"456", "more_body": False},
        ]
    )

    async def chunked():
        return next(messages)

    chunked_scope = {**scope, "headers": []}
    with pytest.raises(HTTPException) as streamed:
        await read_bounded_pdf_body(Request(chunked_scope, chunked), 5)
    assert streamed.value.status_code == 413

    invalid_scope = {**scope, "headers": [(b"content-length", b"-1")]}
    with pytest.raises(HTTPException) as invalid:
        await read_bounded_pdf_body(Request(invalid_scope, no_body), 5)
    assert invalid.value.status_code == 400
    assert invalid.value.detail["code"] == "invalid_content_length"
