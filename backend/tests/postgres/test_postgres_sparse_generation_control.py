"""Published one-fact authored PDF control, never a remote model yield claim."""

import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, func, select

from app.agents.graph import FlashcardGraph
from app.models.flashcard import Flashcard
from app.models.generation import GenerationCandidateStage, GenerationJob, GenerationJobSource
from app.models.knowledge import (
    SubjectDocumentContentRevision, SubjectDocumentIndexRevision,
    SubjectDocumentPage, SubjectDocumentPdf, SubjectDocumentPdfBlock,
)
from app.models.subject import FlashcardSet
from app.models.user import User
from app.schemas.generation import KnowledgeJobCreate
from app.services.generation import GenerationJobService
from app.services.knowledge_management import KnowledgeManagementService
from app.services.knowledge_pdf import read_complete_pdf_archive
from app.services.knowledge_retrieval import KnowledgeRetriever, KnowledgeScopeUnavailable
from app.workers.generation import GenerationWorker
from app.workers.knowledge_index import KnowledgeIndexWorker
from tests.postgres.test_postgres_rag_pipeline import FakeEmbeddingProvider
from tests.support.quality_replay import CORPUS, AuthoredUnderproducingProvider
from tests.test_generation_jobs import job_data, make_settings, seed_owner_subject
from tests.test_pdf_processor import pdf_bytes


pytestmark = pytest.mark.postgres

# Independently inspected the complete rendered original and authored card,
# before exercising persistence. These pins bind the reviewed public fixture,
# not a credential, operator document, or inference-quality measurement.
REVIEWED_PDF_SHA256 = "fa7bc9f4b9163c36a6e1a5d3afdafdc08fad52329157a07f92ea0b76716aed46"
REVIEWED_CARD_SHA256 = "d7adf2da38f1b7eb3f407e86be08d4390c8b2b7654eea4d60fce4f0ebe934248"


@pytest_asyncio.fixture
async def cleanup_sparse_control_owners(postgres_session_factory):
    owners = []
    yield owners.append
    if owners:
        async with postgres_session_factory() as db:
            async with db.begin():
                await db.execute(delete(User).where(User.id.in_(owners)))


async def test_published_sparse_pdf_real_capture_index_shortfall_and_exact_choice(
    postgres_engine, postgres_session_factory, cleanup_sparse_control_owners, monkeypatch,
):
    """Exercise real transactions with injected, explicitly scripted providers."""
    manifest = json.loads(CORPUS.read_text(encoding="utf-8"))
    case = next(item for item in manifest["cases"] if item["id"] == "impossible_sparse")
    fact = manifest["facts"][case["facts"][0]]
    source = pdf_bytes(text=case["pages"][0])
    assert hashlib.sha256(source).hexdigest() == REVIEWED_PDF_SHA256
    # The independently reviewed Windows artifact uses explicit CRLF bytes.
    card_bytes = (json.dumps(fact, ensure_ascii=False, indent=2) + "\n").replace("\n", "\r\n").encode("utf-8")
    assert hashlib.sha256(card_bytes).hexdigest() == REVIEWED_CARD_SHA256
    assert len(case["pages"]) == len(case["facts"]) == 1

    settings = make_settings(
        database_url=str(postgres_engine.url), rag_enabled=True, rag_ask_enabled=False,
        rag_embedding_provider_enabled=True, rag_embedding_api_key="test-only-embedding-key",
        rag_embedding_quota_bucket="disposable-test-project", rag_embedding_provider_max_retries=0,
        knowledge_pdf_encryption_key="AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE",
        flashcard_ai_api_key="offline-no-network", generation_max_active_jobs_per_user=1,
        flashcard_ai_chunk_overlap_tokens=0, flashcard_ai_chunk_input_tokens=1200,
        flashcard_ai_request_input_target_tokens=4096, flashcard_ai_cards_per_request=10,
        flashcard_ai_concurrency=1, flashcard_ai_summary_output_tokens=128,
    )
    service = GenerationJobService(settings)
    embedding_provider = FakeEmbeddingProvider()
    generation_provider = AuthoredUnderproducingProvider([fact])

    async def reject_http(*_args, **_kwargs):
        pytest.fail("The synthetic control must not issue an HTTP provider request.")

    def reject_provider_resolution(*_args, **_kwargs):
        pytest.fail("The synthetic control must use the injected embedding provider.")

    monkeypatch.setattr("httpx.AsyncClient.request", reject_http)
    monkeypatch.setattr("app.workers.knowledge_index.get_embedding_provider", reject_provider_resolution)

    def offline_graph(*, settings, provider_semaphore, rate_governor):
        return FlashcardGraph(
            settings=settings, provider=generation_provider,
            provider_semaphore=provider_semaphore, rate_governor=rate_governor,
        )

    monkeypatch.setattr("app.workers.generation.create_flashcard_graph", offline_graph)
    worker = GenerationWorker(
        settings=settings, session_factory=postgres_session_factory,
        worker_id=f"sparse-control-generation-{uuid4().hex}",
    )
    index_worker = KnowledgeIndexWorker(
        settings=settings, session_factory=postgres_session_factory, provider=embedding_provider,
        worker_id=f"sparse-control-index-{uuid4().hex}",
    )

    async with postgres_session_factory() as db:
        owner, subject = await seed_owner_subject(db)
        outsider, _ = await seed_owner_subject(db)
        cleanup_sparse_control_owners(owner.id)
        cleanup_sparse_control_owners(outsider.id)
        async with db.begin():
            capture_job = await service.create_knowledge_reservation(
                db, user_id=owner.id,
                data=KnowledgeJobCreate(
                    subject_id=subject.id, title="Authored one-fact sparse control",
                    source_pdf_name="authored-one-fact.pdf",
                ), idempotency_key=f"sparse-capture-{uuid4().hex}",
            )
        async with db.begin():
            await service.attach_source(
                db, job_id=capture_job.id, user_id=owner.id,
                media_type="application/pdf", content=source,
            )
        capture_id = capture_job.id

    claim = await worker.claim_next()
    assert claim is not None and claim[0] == capture_id
    await worker.process_claim(*claim)
    assert not generation_provider.calls
    async with postgres_session_factory() as db:
        captured = await db.get(GenerationJob, capture_id)
        assert captured.status == "completed" and captured.knowledge_capture_status == "captured"
        document_id, revision_id = captured.document_id, captured.knowledge_content_revision_id
        assert document_id is not None and revision_id is not None
        assert await db.get(GenerationJobSource, capture_id) is None
        pages = list((await db.scalars(select(SubjectDocumentPage).where(
            SubjectDocumentPage.content_revision_id == revision_id,
        ))).all())
        assert len(pages) == 1 and pages[0].page_number == 1
        assert pages[0].content.strip() == case["pages"][0]

    index_claim = await index_worker.claim_next()
    assert index_claim is not None
    await index_worker.process_claim(*index_claim)
    index_requests_before_generation = embedding_provider.requests
    assert index_requests_before_generation == 1
    async with postgres_session_factory() as db:
        index = await db.scalar(select(SubjectDocumentIndexRevision).where(
            SubjectDocumentIndexRevision.content_revision_id == revision_id,
        ))
        assert index is not None and index.status == "ready"
        with pytest.raises(KnowledgeScopeUnavailable):
            await KnowledgeRetriever.authorize(
                db, principal=owner, subject_id=subject.id, query=fact["question"],
                document_ids=[document_id],
            )
        await db.rollback()
        async with db.begin():
            await KnowledgeManagementService(settings).review_and_publish(
                db, subject_id=subject.id, document_id=document_id, user=owner,
            )

    async with postgres_session_factory() as db:
        revision = await db.get(SubjectDocumentContentRevision, revision_id)
        assert revision.reviewed_by_id == owner.id
        assert revision.reviewed_at is not None and revision.published_at is not None
        retriever = await KnowledgeRetriever.authorize(
            db, principal=owner, subject_id=subject.id, query=fact["question"],
            document_ids=[document_id],
        )
        retrieved = await retriever.retrieve(
            tuple([1.0, *([0.0] * 1535)]), embedding_space_hash=index_worker.space_hash,
        )
        assert len(retrieved.chunks) == 1
        assert retrieved.chunks[0].page_number == 1
        assert fact["quote"] in retrieved.chunks[0].content
        pdf = await db.get(SubjectDocumentPdf, revision_id)
        assert pdf is not None and pdf.source_sha256 == REVIEWED_PDF_SHA256 and pdf.page_count == 1
        blocks = list((await db.scalars(select(SubjectDocumentPdfBlock).where(
            SubjectDocumentPdfBlock.content_revision_id == revision_id,
        ))).all())
        assert blocks and all(fact["quote"].encode() not in bytes(block.payload) for block in blocks)
        assert await read_complete_pdf_archive(db, settings=settings, pdf=pdf) == source
        with pytest.raises(KnowledgeScopeUnavailable):
            await KnowledgeRetriever.authorize(
                db, principal=outsider, subject_id=subject.id, query=fact["question"],
                document_ids=[document_id],
            )

    async with postgres_session_factory() as db:
        async with db.begin():
            job = await service.create_reservation(
                db, user_id=owner.id,
                data=job_data(subject.id, card_count=20, document_id=document_id),
                idempotency_key=f"sparse-generate-{uuid4().hex}",
            )
        async with db.begin():
            await service.attach_source(
                db, job_id=job.id, user_id=owner.id,
                media_type="application/pdf", content=source,
            )
        assert job.knowledge_capture_status == "unchanged"
        assert job.knowledge_content_revision_id == revision_id
        job_id = job.id
    claim = await worker.claim_next()
    assert claim is not None and claim[0] == job_id
    await worker.process_claim(*claim)
    generation_calls_before_choice = len(generation_provider.calls)
    assert generation_calls_before_choice > 0
    assert embedding_provider.requests == index_requests_before_generation

    async with postgres_session_factory() as db:
        job = await db.get(GenerationJob, job_id)
        stage = await db.get(GenerationCandidateStage, job_id)
        assert job.status == "awaiting_card_choice" and job.error_code == "insufficient_grounded_cards"
        assert job.requested_card_count == 20 and job.accepted_card_count == 0
        assert job.provider_request_count == generation_calls_before_choice
        assert stage is not None and stage.candidate_count == 1
        assert fact["answer"].encode() not in bytes(stage.payload)
        assert await db.get(GenerationJobSource, job_id) is not None
        assert (await service.to_response(db, job)).valid_candidate_count == 1
        assert await db.scalar(select(func.count(FlashcardSet.id)).where(
            FlashcardSet.generation_job_id == job_id,
        )) == 0

    for user_id, count, expected_status in ((outsider.id, 1, 404), (owner.id, 2, 422)):
        async with postgres_session_factory() as db:
            with pytest.raises(HTTPException) as rejected:
                async with db.begin():
                    await service.submit_card_choice(
                        db, job_id=job_id, user_id=user_id, card_count=count,
                        idempotency_key=f"sparse-denied-choice-{uuid4().hex}",
                    )
            assert rejected.value.status_code == expected_status

    choice_key = f"sparse-exact-one-{uuid4().hex}"
    for _ in range(2):
        async with postgres_session_factory() as db:
            async with db.begin():
                completed = await service.submit_card_choice(
                    db, job_id=job_id, user_id=owner.id, card_count=1,
                    idempotency_key=choice_key,
                )
                assert completed.status == "completed"
    assert len(generation_provider.calls) == generation_calls_before_choice
    assert embedding_provider.requests == index_requests_before_generation

    async with postgres_session_factory() as db:
        job = await db.get(GenerationJob, job_id)
        assert job.requested_card_count == 20
        assert job.selected_card_count == job.generated_card_count == job.accepted_card_count == 1
        sets = list((await db.scalars(select(FlashcardSet).where(
            FlashcardSet.generation_job_id == job_id,
        ))).all())
        assert len(sets) == 1 and not sets[0].is_published
        cards = list((await db.scalars(select(Flashcard).where(Flashcard.set_id == sets[0].id))).all())
        assert len(cards) == 1 and not cards[0].is_approved
        card = cards[0]
        assert card.front_content == fact["question"] and card.back_content == fact["answer"]
        assert card.options == fact["options"] and len({option.casefold() for option in card.options}) == 4
        assert card.source_page == 1 and card.source_snippet == fact["quote"]
        assert await db.get(GenerationCandidateStage, job_id) is None
        assert await db.get(GenerationJobSource, job_id) is None
        revision = await db.get(SubjectDocumentContentRevision, revision_id)
        assert revision.published_at is not None and revision.reviewed_by_id == owner.id
        pdf = await db.get(SubjectDocumentPdf, revision_id)
        assert await read_complete_pdf_archive(db, settings=settings, pdf=pdf) == source

    report_path = os.environ.get("SPARSE_CONTROL_REPORT_PATH")
    if report_path:
        Path(report_path).write_text(json.dumps({
            "source_pages": 1, "authored_facts": 1, "published_revisions": 1,
            "original_requested_count": 20, "pending_validated_count": 1,
            "sets_before_choice": 0, "sets_after_choice": 1,
            "exact_selected_count": 1, "injected_generation_calls": generation_calls_before_choice,
            "injected_index_calls": index_requests_before_generation,
            "additional_calls_on_choice": 0, "physical_remote_calls": 0,
            "actual_cost_usd": 0, "same_choice_replays": 1,
            "denied_foreign_choice": 1, "denied_excess_choice": 1,
            "temporary_sources_after_choice": 0, "candidate_stages_after_choice": 0,
            "published_original_preserved": 1,
        }, sort_keys=True) + "\n", encoding="utf-8")
