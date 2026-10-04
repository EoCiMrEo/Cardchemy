"""Keyless exact-count, private candidate choice and paid-retry contracts."""

import json
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.agents.graph import FlashcardGraph
from app.ai.contracts import ValidatedCard
from app.ai.grounding import duplicate_similarity
from app.ai.pipeline import FlashcardGenerationPipeline, PipelineError
from app.models.flashcard import Flashcard
from app.models.generation import (
    GenerationCandidateStage, GenerationJob, GenerationJobSource,
    GenerationJobStatus, GenerationQuotaEvent,
)
from app.models.subject import FlashcardSet
from app.services.generation import GenerationJobService
from app.services.candidate_storage import CandidateStorageError, decrypt_candidates
from app.time_utils import utcnow
from app.workers.generation import GenerationWorker
from tests.support.quality_replay import (
    CORPUS, AuthoredUnderproducingProvider, replay_document, replay_settings,
)
from tests.test_generation_jobs import job_data, make_settings, seed_owner_subject
from tests.test_pdf_processor import pdf_bytes


def valid_cards() -> tuple[ValidatedCard, ...]:
    return (
        ValidatedCard(
            front_content="Which pigment absorbs light?", back_content="Chlorophyll",
            options=["Chlorophyll", "Hemoglobin", "Melanin", "Rhodopsin"],
            quality_score=0.95, source_snippet="Chlorophyll absorbs light energy.",
            source_page=1, source_section="Photosynthesis",
        ),
        ValidatedCard(
            front_content="Which tissue moves water?", back_content="Xylem",
            options=["Xylem", "Phloem", "Cambium", "Epidermis"],
            quality_score=0.9, source_snippet="Xylem moves water from roots to leaves.",
            source_page=2, source_section="Transport",
        ),
    )


async def pending_choice(factory, *, settings=None, requested_count=3, cards=None, reservation_key=None):
    settings = settings or make_settings(generation_max_active_jobs_per_user=1)
    async with factory() as db:
        owner, subject = await seed_owner_subject(db)
        service = GenerationJobService(settings)
        async with db.begin():
            job = await service.create_reservation(
                db, user_id=owner.id, data=job_data(subject.id, card_count=requested_count),
                idempotency_key=reservation_key or f"choice-reserve-{uuid4().hex}",
            )
        async with db.begin():
            await service.attach_source(
                db, job_id=job.id, user_id=owner.id,
                media_type="application/pdf", content=b"%PDF-1.7\nsource",
            )
        job_id = job.id
    worker = GenerationWorker(
        settings=settings, session_factory=factory, worker_id=f"choice-worker-{uuid4().hex}"
    )
    claim = await worker.claim_next()
    assert claim and claim[0] == job_id
    await worker._finish_card_choice(
        *claim, cards if cards is not None else valid_cards(), {
            "rejected_card_count": 4,
            "provider_request_count": 2,
            "quality_diagnostics": {
                "rounds": [{
                    "round": 0, "raw_count": 6, "grounded_count": 5,
                    "valid_count": 3, "distinct_count": 2,
                    "accepted_count": 2, "missing_count": 1,
                }],
                "rejections": {"near_duplicate": 1},
                "uncertain_request_count": 1,
            },
        },
    )
    return owner.id, subject.id, job_id, service, worker


@pytest.mark.parametrize("fact_count", [0, 2])
async def test_real_pipeline_shortfall_reaches_worker_choice_or_failure(
    session_factory, monkeypatch, fact_count,
):
    """Exercise the actual pipeline-to-worker handoff with an offline provider."""

    manifest = json.loads(CORPUS.read_text(encoding="utf-8"))
    case = next(item for item in manifest["cases"] if item["id"] == "feasible_short_underproduction_refill")
    provider = AuthoredUnderproducingProvider(manifest["facts"][:fact_count])
    settings = make_settings(generation_max_active_jobs_per_user=1)
    service = GenerationJobService(settings)
    async with session_factory() as db:
        owner, subject = await seed_owner_subject(db)
        async with db.begin():
            job = await service.create_reservation(
                db, user_id=owner.id, data=job_data(subject.id, card_count=3),
                idempotency_key=f"actual-pipeline-shortfall-{fact_count}",
            )
        async with db.begin():
            await service.attach_source(
                db, job_id=job.id, user_id=owner.id,
                media_type="application/pdf", content=b"%PDF-1.7\nsynthetic",
            )
        job_id = job.id

    worker = GenerationWorker(
        settings=settings, session_factory=session_factory,
        worker_id=f"actual-pipeline-shortfall-{fact_count}",
    )
    claim = await worker.claim_next()
    assert claim is not None and claim[0] == job_id
    pipeline_calls = 0

    async def run_real_pipeline(*_args):
        nonlocal pipeline_calls
        pipeline_calls += 1
        await FlashcardGenerationPipeline(replay_settings(case), provider).run(
            replay_document(case), 3,
        )

    monkeypatch.setattr(worker, "_pipeline", run_real_pipeline)
    await worker.process_claim(*claim)

    async with session_factory() as db:
        job = await db.get(GenerationJob, job_id)
        stage = await db.get(GenerationCandidateStage, job_id)
        assert job.error_code == "insufficient_grounded_cards"
        assert job.requested_card_count == 3
        assert job.accepted_card_count == 0
        assert job.provider_request_count == len(provider.calls)
        assert await db.scalar(select(func.count(FlashcardSet.id)).where(
            FlashcardSet.generation_job_id == job_id,
        )) == 0
        if fact_count:
            assert job.status == GenerationJobStatus.AWAITING_CARD_CHOICE.value
            assert stage is not None and stage.candidate_count == fact_count
            assert (await service.to_response(db, job)).valid_candidate_count == fact_count
            assert b"Chlorophyll" not in bytes(stage.payload)
        else:
            assert job.status == GenerationJobStatus.FAILED.value
            assert stage is None
            assert (await service.to_response(db, job)).valid_candidate_count == 0
    assert pipeline_calls == 1
    assert provider.calls


@pytest.mark.parametrize(
    ("case_id", "requested_count", "expected_count"),
    [
        ("feasible_short_underproduction_refill", 3, 2),
        ("impossible_sparse", 20, 1),
    ],
)
async def test_extracted_pdf_shortfall_stages_cards_and_confirms_without_provider(
    session_factory, monkeypatch, case_id, requested_count, expected_count,
):
    """Bridge actual PDF extraction, grounded pipeline, worker staging, and choice."""

    manifest = json.loads(CORPUS.read_text(encoding="utf-8"))
    case = next(item for item in manifest["cases"] if item["id"] == case_id)
    provider = AuthoredUnderproducingProvider([manifest["facts"][index] for index in case["facts"]])
    settings = make_settings(generation_max_active_jobs_per_user=1, rag_enabled=False)
    service = GenerationJobService(settings)
    source = pdf_bytes(text=case["pages"][0])

    async with session_factory() as db:
        owner, subject = await seed_owner_subject(db)
        async with db.begin():
            job = await service.create_reservation(
                db, user_id=owner.id, data=job_data(subject.id, card_count=requested_count),
                idempotency_key=f"extracted-pdf-shortfall-{case_id}",
            )
        async with db.begin():
            await service.attach_source(
                db, job_id=job.id, user_id=owner.id,
                media_type="application/pdf", content=source,
            )
        owner_id, job_id = owner.id, job.id

    def offline_graph(*, settings, provider_semaphore, rate_governor):
        return FlashcardGraph(
            settings=settings, provider=provider,
            provider_semaphore=provider_semaphore, rate_governor=rate_governor,
        )

    monkeypatch.setattr("app.workers.generation.create_flashcard_graph", offline_graph)
    worker = GenerationWorker(
        settings=settings, session_factory=session_factory,
        worker_id="extracted-pdf-shortfall-worker",
    )
    claim = await worker.claim_next()
    assert claim is not None and claim[0] == job_id
    await worker.process_claim(*claim)
    requests_before_choice = len(provider.calls)
    assert requests_before_choice > 0

    async with session_factory() as db:
        job = await db.get(GenerationJob, job_id)
        stage = await db.get(GenerationCandidateStage, job_id)
        assert job.status == GenerationJobStatus.AWAITING_CARD_CHOICE.value
        assert job.error_code == "insufficient_grounded_cards"
        assert job.requested_card_count == requested_count
        assert job.accepted_card_count == 0
        assert job.provider_request_count == requests_before_choice
        assert stage is not None and stage.candidate_count == expected_count
        assert b"Chlorophyll" not in bytes(stage.payload)
        assert await db.get(GenerationJobSource, job_id) is not None
        assert await db.scalar(select(func.count(FlashcardSet.id)).where(
            FlashcardSet.generation_job_id == job_id,
        )) == 0

    async with session_factory() as db:
        async with db.begin():
            completed = await service.submit_card_choice(
                db, job_id=job_id, user_id=owner_id, card_count=expected_count,
                idempotency_key=f"extracted-pdf-choice-{case_id}",
            )
            assert completed.status == GenerationJobStatus.COMPLETED.value
        job = await db.get(GenerationJob, job_id)
        cards = (await db.scalars(select(Flashcard).join(FlashcardSet).where(
            FlashcardSet.generation_job_id == job_id,
        ))).all()
        assert job.requested_card_count == requested_count
        assert job.selected_card_count == job.accepted_card_count == expected_count
        assert len(cards) == expected_count
        assert all(card.source_page == 1 and not card.is_approved for card in cards)
        assert all(card.source_snippet in case["pages"][0] for card in cards)
        assert all(len(card.options) == len({option.casefold() for option in card.options}) == 4
                   and card.back_content in card.options for card in cards)
        assert await db.get(GenerationCandidateStage, job_id) is None
        assert await db.get(GenerationJobSource, job_id) is None
        assert await db.scalar(select(func.count(FlashcardSet.id)).where(
            FlashcardSet.generation_job_id == job_id,
        )) == 1
    assert len(provider.calls) == requests_before_choice


@pytest.mark.parametrize("boundary", ["cancelled", "expired_lease", "replaced_claim"])
async def test_shortfall_finalization_fences_cancellation_and_lease_loss_before_staging(
    session_factory, monkeypatch, boundary,
):
    settings = make_settings(generation_max_active_jobs_per_user=1, rag_enabled=False)
    service = GenerationJobService(settings)
    async with session_factory() as db:
        owner, subject = await seed_owner_subject(db)
        async with db.begin():
            job = await service.create_reservation(
                db, user_id=owner.id, data=job_data(subject.id, card_count=3),
                idempotency_key=f"shortfall-boundary-{boundary}",
            )
        async with db.begin():
            await service.attach_source(
                db, job_id=job.id, user_id=owner.id,
                media_type="application/pdf", content=b"%PDF-1.7\nshortfall-boundary",
            )
        owner_id, job_id = owner.id, job.id

    worker = GenerationWorker(
        settings=settings, session_factory=session_factory,
        worker_id=f"shortfall-boundary-{boundary}",
    )
    claim = await worker.claim_next()
    assert claim is not None and claim[0] == job_id
    pipeline_calls = staging_calls = 0

    async def shortfall(*_args):
        nonlocal pipeline_calls
        pipeline_calls += 1
        raise PipelineError(
            "insufficient_grounded_cards", "Fewer validated cards are available.",
            retryable=True, validated_cards=valid_cards(),
        )

    finish_card_choice = worker._finish_card_choice

    async def change_boundary_before_real_staging(*args):
        nonlocal staging_calls
        staging_calls += 1
        # Change durable state after the pipeline has raised its shortfall,
        # then let the real staging transaction perform its fencing check.
        async with session_factory() as db:
            async with db.begin():
                if boundary == "cancelled":
                    await service.cancel(db, job_id=job_id, user_id=owner_id)
                else:
                    current = await db.get(GenerationJob, job_id)
                    if boundary == "expired_lease":
                        current.lease_expires_at = utcnow() - timedelta(seconds=1)
                    else:
                        current.worker_id = "replacement-worker"
                        current.claim_token = "replacement-claim"
                        current.lease_expires_at = utcnow() + timedelta(minutes=5)
        await finish_card_choice(*args)

    monkeypatch.setattr(worker, "_pipeline", shortfall)
    monkeypatch.setattr(worker, "_finish_card_choice", change_boundary_before_real_staging)
    await worker.process_claim(*claim)

    async with session_factory() as db:
        current = await db.get(GenerationJob, job_id)
        assert current.requested_card_count == 3
        assert current.accepted_card_count == 0
        assert current.attempt_count == 1
        assert await db.get(GenerationCandidateStage, job_id) is None
        assert await db.scalar(select(func.count(FlashcardSet.id)).where(
            FlashcardSet.generation_job_id == job_id,
        )) == 0
        source = await db.get(GenerationJobSource, job_id)
        if boundary == "cancelled":
            assert current.status == GenerationJobStatus.CANCELLED.value
            assert current.completed_at is not None
            assert current.worker_id is current.claim_token is current.lease_expires_at is None
            assert source is None
        else:
            assert current.status == GenerationJobStatus.RUNNING.value
            assert source is not None
            assert current.completed_at is None
            assert current.claim_token == ("replacement-claim" if boundary == "replaced_claim" else claim[1])
            assert current.worker_id == ("replacement-worker" if boundary == "replaced_claim" else worker.worker_id)
    # Neither cancellation nor a stale finalizer queues or replays the pipeline.
    assert pipeline_calls == staging_calls == 1
    assert await worker.claim_next() is None


@pytest.mark.parametrize("choice", ["confirm", "cancel"])
async def test_process_claim_stages_partial_pipeline_yield_before_owner_choice(
    session_factory, monkeypatch, choice
):
    settings = make_settings(generation_max_active_jobs_per_user=1)
    service = GenerationJobService(settings)
    async with session_factory() as db:
        owner, subject = await seed_owner_subject(db)
        async with db.begin():
            job = await service.create_reservation(
                db, user_id=owner.id, data=job_data(subject.id, card_count=3),
                idempotency_key=f"partial-pipeline-{choice}",
            )
        async with db.begin():
            await service.attach_source(
                db, job_id=job.id, user_id=owner.id,
                media_type="application/pdf", content=b"%PDF-1.7\npartial-yield",
            )
        owner_id, job_id = owner.id, job.id

    worker = GenerationWorker(
        settings=settings, session_factory=session_factory,
        worker_id=f"partial-pipeline-{choice}",
    )
    claim = await worker.claim_next()
    assert claim is not None and claim[0] == job_id
    pipeline_calls = 0

    async def partial_pipeline(*_args):
        nonlocal pipeline_calls
        pipeline_calls += 1
        raise PipelineError(
            "insufficient_grounded_cards",
            "The provider could not produce enough distinct, source-grounded cards.",
            retryable=True, validated_cards=valid_cards(),
            rejected_card_count=4, provider_request_count=2,
            quality_diagnostics={
                "rounds": [{
                    "round": 0, "raw_count": 6, "grounded_count": 5,
                    "valid_count": 3, "distinct_count": 2,
                    "accepted_count": 2, "missing_count": 1,
                }],
                "rejections": {"near_duplicate": 1},
            },
        )

    monkeypatch.setattr(worker, "_pipeline", partial_pipeline)
    await worker.process_claim(*claim)
    assert pipeline_calls == 1

    async with session_factory() as db:
        job = await db.get(GenerationJob, job_id)
        stage = await db.get(GenerationCandidateStage, job_id)
        assert job.status == GenerationJobStatus.AWAITING_CARD_CHOICE.value
        assert job.error_code == "insufficient_grounded_cards"
        assert job.requested_card_count == 3
        assert job.accepted_card_count == 0
        assert job.generated_card_count is None
        assert job.provider_request_count == 2
        assert job.rejected_card_count == 4
        assert stage is not None and stage.candidate_count == 2
        assert b"Chlorophyll" not in bytes(stage.payload)
        assert await db.get(GenerationJobSource, job_id) is not None
        assert await db.scalar(select(func.count(FlashcardSet.id)).where(
            FlashcardSet.generation_job_id == job_id,
        )) == 0
        assert (await service.to_response(db, job)).valid_candidate_count == 2

    async with session_factory() as db:
        async with db.begin():
            if choice == "confirm":
                result = await service.submit_card_choice(
                    db, job_id=job_id, user_id=owner_id, card_count=2,
                    idempotency_key="partial-confirm-abc123",
                )
                assert result.status == GenerationJobStatus.COMPLETED.value
            else:
                result = await service.cancel(db, job_id=job_id, user_id=owner_id)
                assert result.status == GenerationJobStatus.CANCELLED.value

        job = await db.get(GenerationJob, job_id)
        assert job.requested_card_count == 3
        assert job.provider_request_count == 2
        assert await db.get(GenerationCandidateStage, job_id) is None
        assert await db.get(GenerationJobSource, job_id) is None
        set_count = await db.scalar(select(func.count(FlashcardSet.id)).where(
            FlashcardSet.generation_job_id == job_id,
        ))
        card_count = await db.scalar(select(func.count(Flashcard.id)).join(FlashcardSet).where(
            FlashcardSet.generation_job_id == job_id,
        ))
        assert (set_count, card_count) == ((1, 2) if choice == "confirm" else (0, 0))
        if choice == "confirm":
            assert job.selected_card_count == job.accepted_card_count == 2
        else:
            assert job.accepted_card_count == 0
    assert pipeline_calls == 1


async def test_choice_confirm_exact_count_without_provider_or_partial_set(session_factory):
    owner_id, _subject_id, job_id, service, worker = await pending_choice(session_factory)
    async with session_factory() as db:
        job = await db.get(GenerationJob, job_id)
        stage = await db.get(GenerationCandidateStage, job_id)
        assert job.status == GenerationJobStatus.AWAITING_CARD_CHOICE.value
        assert job.requested_card_count == 3
        assert job.accepted_card_count == 0
        assert job.rejected_card_count == 4
        assert stage.candidate_count == 2
        assert len(bytes(stage.payload)) > 16
        assert b"Chlorophyll" not in bytes(stage.payload)
        assert await db.scalar(select(func.count(FlashcardSet.id)).where(
            FlashcardSet.generation_job_id == job_id
        )) == 0
        response = await service.to_response(db, job)
        assert response.valid_candidate_count == 2
        assert response.can_accept_smaller_target
        assert response.latest_attempt_rejected_card_count == 4
        assert response.previous_attempt_cost_unknown
        original_requests = response.provider_request_count
        original_charges = await db.scalar(select(func.count(GenerationQuotaEvent.id)).where(
            GenerationQuotaEvent.job_id == job_id
        ))
        with pytest.raises(CandidateStorageError):
            decrypt_candidates(
                service.settings, job_id=job_id, fingerprint=job.request_fingerprint,
                manual_retry_number=stage.manual_retry_number,
                attempt_number=stage.attempt_number + 1,
                nonce=bytes(stage.nonce), payload=bytes(stage.payload),
                expected_count=stage.candidate_count,
            )
        decoded = decrypt_candidates(
            service.settings, job_id=job_id, fingerprint=job.request_fingerprint,
            manual_retry_number=stage.manual_retry_number,
            attempt_number=stage.attempt_number,
            nonce=bytes(stage.nonce), payload=bytes(stage.payload),
            expected_count=stage.candidate_count,
        )
        assert len(decoded.cards) == 2
        assert decoded.duplicate_similarity_threshold == service.settings.flashcard_ai_duplicate_similarity_threshold
    async with session_factory() as db:
        async with db.begin():
            chosen = await service.submit_card_choice(
                db, job_id=job_id, user_id=owner_id, card_count=1,
                idempotency_key="choice-confirm-abc123",
            )
            assert chosen.status == GenerationJobStatus.COMPLETED.value
        async with db.begin():
            replay = await service.submit_card_choice(
                db, job_id=job_id, user_id=owner_id, card_count=1,
                idempotency_key="choice-confirm-abc123",
            )
            assert replay.id == job_id
        assert await db.get(GenerationCandidateStage, job_id) is None
        assert await db.get(GenerationJobSource, job_id) is None
        assert await db.scalar(select(func.count(Flashcard.id)).join(FlashcardSet).where(
            FlashcardSet.generation_job_id == job_id
        )) == 1
        assert await db.scalar(select(func.count(GenerationQuotaEvent.id)).where(
            GenerationQuotaEvent.job_id == job_id
        )) == original_charges
        job = await db.get(GenerationJob, job_id)
        assert job.provider_request_count == original_requests
        assert job.generated_card_count == job.accepted_card_count == job.selected_card_count == 1
        assert job.requested_card_count == 3
        await db.rollback()
        with pytest.raises(HTTPException) as conflict:
            async with db.begin():
                await service.submit_card_choice(
                    db, job_id=job_id, user_id=owner_id, card_count=2,
                    idempotency_key="choice-confirm-abc123",
                )
        assert conflict.value.status_code == 409


async def test_choice_retry_requires_extra_cost_ack_and_charges_once(session_factory):
    owner_id, _subject_id, job_id, service, _worker = await pending_choice(session_factory)
    async with session_factory() as db:
        with pytest.raises(HTTPException) as missing:
            async with db.begin():
                await service.retry(
                    db, job_id=job_id, user_id=owner_id,
                    idempotency_key="choice-paid-retry-abc123",
                )
        assert missing.value.status_code == 422
        assert await db.get(GenerationCandidateStage, job_id) is not None
        await db.rollback()
        async with db.begin():
            retried = await service.retry(
                db, job_id=job_id, user_id=owner_id,
                idempotency_key="choice-paid-retry-abc123",
                acknowledge_additional_cost=True,
            )
            assert retried.status == GenerationJobStatus.QUEUED.value
        assert await db.get(GenerationCandidateStage, job_id) is None
        assert await db.get(GenerationJobSource, job_id) is not None
        assert await db.scalar(select(func.count(GenerationQuotaEvent.id)).where(
            GenerationQuotaEvent.job_id == job_id
        )) == 2


async def test_retry_rejects_original_upload_key_without_changing_pending_choice(session_factory):
    reservation_key = "choice-reserve-original-key-abc123"
    owner_id, _subject_id, job_id, service, _worker = await pending_choice(
        session_factory, reservation_key=reservation_key,
    )
    async with session_factory() as db:
        with pytest.raises(HTTPException) as reused:
            async with db.begin():
                await service.retry(
                    db, job_id=job_id, user_id=owner_id,
                    idempotency_key=reservation_key,
                    acknowledge_additional_cost=True,
                )
        assert reused.value.status_code == 409
        assert reused.value.detail["code"] == "idempotency_key_reused"
        job = await db.get(GenerationJob, job_id)
        assert job.status == GenerationJobStatus.AWAITING_CARD_CHOICE.value
        assert await db.get(GenerationCandidateStage, job_id) is not None
        assert await db.scalar(select(func.count(GenerationQuotaEvent.id)).where(
            GenerationQuotaEvent.job_id == job_id,
        )) == 1


async def test_choice_cancel_and_expiry_remove_private_bytes(session_factory):
    owner_id, _subject_id, job_id, service, _worker = await pending_choice(session_factory)
    async with session_factory() as db:
        async with db.begin():
            cancelled = await service.cancel(db, job_id=job_id, user_id=owner_id)
            assert cancelled.status == GenerationJobStatus.CANCELLED.value
        assert await db.get(GenerationCandidateStage, job_id) is None
        assert await db.get(GenerationJobSource, job_id) is None

    _owner_id, _subject_id, expired_id, _service, worker = await pending_choice(session_factory)
    async with session_factory() as db:
        async with db.begin():
            job = await db.get(GenerationJob, expired_id)
            stage = await db.get(GenerationCandidateStage, expired_id)
            source = await db.get(GenerationJobSource, expired_id)
            old = utcnow()
            job.card_choice_expires_at = old
            stage.expires_at = old
            source.expires_at = old
    await worker.recover_and_cleanup()
    async with session_factory() as db:
        job = await db.get(GenerationJob, expired_id)
        assert job.status == GenerationJobStatus.FAILED.value
        assert job.error_code == "card_choice_expired"
        assert await db.get(GenerationCandidateStage, expired_id) is None
        assert await db.get(GenerationJobSource, expired_id) is None


async def test_choice_rejects_foreign_owner_and_invalid_target(session_factory):
    owner_id, _subject_id, job_id, service, _worker = await pending_choice(session_factory)
    async with session_factory() as db:
        with pytest.raises(HTTPException) as foreign:
            async with db.begin():
                await service.submit_card_choice(
                    db, job_id=job_id, user_id=uuid4(), card_count=1,
                    idempotency_key=str(uuid4()),
                )
        assert foreign.value.status_code == 404
        with pytest.raises(HTTPException) as invalid:
            async with db.begin():
                await service.submit_card_choice(
                    db, job_id=job_id, user_id=owner_id, card_count=3,
                    idempotency_key=str(uuid4()),
                )
        assert invalid.value.status_code == 422
        assert await db.get(GenerationCandidateStage, job_id) is not None


async def test_choice_uses_authenticated_attempt_threshold_after_settings_change(session_factory):
    settings = make_settings(
        generation_max_active_jobs_per_user=1,
        flashcard_ai_duplicate_similarity_threshold=0.88,
    )
    first, second = valid_cards()
    second = second.model_copy(update={"front_content": first.front_content})
    assert 0.5 <= duplicate_similarity(first, second) < 0.88
    owner_id, _subject_id, job_id, _service, _worker = await pending_choice(
        session_factory, settings=settings, cards=(first, second),
    )
    current_settings = settings.model_copy(update={"flashcard_ai_duplicate_similarity_threshold": 0.5})
    async with session_factory() as db:
        async with db.begin():
            chosen = await GenerationJobService(current_settings).submit_card_choice(
                db, job_id=job_id, user_id=owner_id, card_count=2,
                idempotency_key=str(uuid4()),
            )
            assert chosen.generated_card_count == 2


async def test_legacy_choice_without_threshold_snapshot_fails_closed(session_factory):
    owner_id, _subject_id, job_id, service, _worker = await pending_choice(session_factory)
    async with session_factory() as db:
        async with db.begin():
            stage = await db.get(GenerationCandidateStage, job_id)
            stage.validation_policy_version = "grounded_candidate_choice_v1"
        with pytest.raises(HTTPException) as unavailable:
            async with db.begin():
                await service.submit_card_choice(
                    db, job_id=job_id, user_id=owner_id, card_count=1,
                    idempotency_key=str(uuid4()),
                )
        assert unavailable.value.status_code == 409
        assert await db.get(GenerationCandidateStage, job_id) is not None
