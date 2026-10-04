"""Phase 14-16 capture, indexing, cutover and authorized retrieval contract."""

import json
import hashlib
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text

from app.ai.chunking import prepare_document
from app.ai.contracts import ExtractedDocument, ExtractedPage
from app.ai.embeddings import EmbeddingResponse
from app.ai.providers import AIProviderError, ProviderAttemptTelemetry, ProviderUsage
from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION, Settings
from app.models.flashcard import Enrollment
from app.models.generation import GenerationJob
from app.models.knowledge import (
    SubjectDocumentChunk,
    SubjectDocumentContentRevision,
    SubjectDocumentIndexJob,
    SubjectDocumentIndexRevision,
)
from app.models.subject import Subject
from app.models.user import AuthSession, User, UserRole
from app.schemas.rag import RagQuestionCreate
from app.services.knowledge_capture import capture_prepared_document
from app.services.knowledge_indexing import (
    cutover_subject_embedding_space,
    enqueue_subject_reindex,
)
from app.services.knowledge_retrieval import (
    EXACT_V1_POLICY,
    IncompatibleEmbeddingSpace,
    KnowledgeRetriever,
    KnowledgeScopeUnavailable,
    KnowledgeSourceUnavailable,
)
from app.services.rag_answers import RagAnswerService
from app.time_utils import utcnow
from app.workers.knowledge_index import IndexLeaseLost, KnowledgeIndexWorker
from tests.support.rag_evaluation import EvaluationObservation, evaluate, load_corpus


pytestmark = pytest.mark.postgres


def settings(database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=database_url,
        secret_key="test-only-secret-key-with-adequate-entropy-1234567890",
        generation_source_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        rag_enabled=True,
        rag_ask_enabled=True,
        rag_embedding_provider_enabled=True,
        rag_embedding_api_key="test-only-embedding-key",
        rag_embedding_quota_bucket="disposable-test-project",
        rag_embedding_provider_max_retries=0,
        rag_source_judge_provider_enabled=True,
        rag_source_judge_api_key="test-only-source-judge-key",
        rag_source_judge_quota_bucket="disposable-test-project",
    )


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.requests = 0

    async def embed_documents(self, texts):
        self.requests += 1
        vectors = tuple(tuple([1.0, *([0.0] * 1535)]) for _ in texts)
        return EmbeddingResponse(
            vectors=vectors,
            usage=ProviderUsage(input_tokens=sum(len(text.split()) for text in texts), output_tokens=0, estimated=False),
        )

    async def embed_query(self, text):
        self.requests += 1
        return EmbeddingResponse(
            vectors=(tuple([1.0, *([0.0] * 1535)]),),
            usage=ProviderUsage(input_tokens=len(text.split()), output_tokens=0, estimated=False),
        )

    def telemetry_snapshot(self):
        return ProviderAttemptTelemetry(
            request_count=self.requests,
            retry_count=0,
            rate_limit_wait_seconds=0,
            request_counts_by_stage={"embedding_documents": self.requests},
        )


class TitleAwareEmbeddingProvider(FakeEmbeddingProvider):
    def __init__(self) -> None:
        super().__init__()
        self.document_titles = []

    async def embed_documents(self, texts, *, titles=None):
        self.document_titles.extend(titles or [])
        return await super().embed_documents(texts)


class FailSecondBatchProvider(FakeEmbeddingProvider):
    async def embed_documents(self, texts):
        if self.requests == 1:
            self.requests += 1
            raise AIProviderError(
                "embedding_provider_unavailable",
                "The embedding provider is temporarily unavailable.",
                retryable=True,
            )
        return await super().embed_documents(texts)


class CorpusEmbeddingProvider(FakeEmbeddingProvider):
    """Small deterministic semantic space for real pgvector evaluation."""

    @staticmethod
    def _vector(text_value: str):
        value = text_value.casefold()
        weights = [0.0] * 1536
        concept_terms = (
            (0, ("perihelion", "aphelion", "nearest", "farthest", "opposite point")),
            (1, ("eccentricity", "circle", "departs")),
            (2, ("kepler", "equal areas", "elliptical")),
            (3, ("redshift", "wavelength", "receding")),
            (4, ("faster", "slower", "speed")),
            (5, ("instruction", "secret keys", "authority", "reveal")),
        )
        for axis, terms in concept_terms:
            if any(term in value for term in terms):
                weights[axis] = 1.0
        if not any(weights):
            weights[20] = 1.0
        magnitude = sum(weight * weight for weight in weights) ** 0.5
        return tuple(weight / magnitude for weight in weights)

    async def embed_documents(self, texts):
        self.requests += 1
        return EmbeddingResponse(
            vectors=tuple(self._vector(text_value) for text_value in texts),
            usage=ProviderUsage(
                input_tokens=sum(len(text_value.split()) for text_value in texts),
                output_tokens=0,
                estimated=False,
            ),
        )

    async def embed_query(self, text):
        self.requests += 1
        return EmbeddingResponse(
            vectors=(self._vector(text),),
            usage=ProviderUsage(input_tokens=len(text.split()), output_tokens=0, estimated=False),
        )


async def seed_capture(session_factory, configured, *, page_texts, original_pdf=None):
    owner = User(
        id=uuid4(), email=f"rag-batch-{uuid4().hex}@example.test",
        hashed_password="fixture", role=UserRole.INSTRUCTOR,
    )
    subject = Subject(id=uuid4(), name="RAG batch", instructor_id=owner.id)
    job_id = uuid4()
    now = utcnow()
    token = "e" * 64
    async with session_factory() as db:
        async with db.begin():
            db.add_all([owner, subject])
            await db.flush()
            db.add(GenerationJob(
                id=job_id, user_id=owner.id, subject_id=subject.id,
                job_kind="knowledge_only", knowledge_capture_status="pending",
                idempotency_key_hash=uuid4().hex * 2,
                request_fingerprint=uuid4().hex * 2,
                status="running", progress=20, stage="extracting_text",
                set_title="Batch source", requested_card_count=0,
                source_pdf_name="batch.pdf", source_media_type="application/pdf",
                source_size_bytes=len(original_pdf) if original_pdf is not None else 1024,
                source_sha256=hashlib.sha256(original_pdf).hexdigest() if original_pdf is not None else uuid4().hex * 2,
                worker_id="capture-batch", claim_token=token, attempt_count=1,
                heartbeat_at=now, lease_expires_at=now + timedelta(minutes=5),
                max_attempts=3, available_at=now, created_at=now, updated_at=now,
            ))
    prepared = prepare_document(
        ExtractedDocument(pages=[
            ExtractedPage(page_number=index, text=value)
            for index, value in enumerate(page_texts, start=1)
        ]),
        max_tokens=32,
    )
    captured = await capture_prepared_document(
        session_factory, settings=configured, job_id=job_id,
        worker_id="capture-batch", claim_token=token, prepared=prepared, original_pdf=original_pdf,
    )
    return owner, subject, captured, prepared


async def test_model_2_staging_cutover_and_rollback_never_mix_equal_dimension_vectors(
    postgres_engine, postgres_session_factory
):
    configured_001 = settings(str(postgres_engine.url))
    configured_2 = configured_001.model_copy(update={
        "rag_embedding_model": "gemini-embedding-2",
        "rag_embedding_format_version": "gemini2_qa_section_v1",
        "rag_embedding_space_revision": "gemini2-v1",
        "rag_embedding_input_cost_per_million_usd": 0.20,
    })
    owner, subject, captured, _ = await seed_capture(
        postgres_session_factory, configured_001,
        page_texts=("Foundations\n\nAlpha is the first concept.",),
    )
    old_worker = KnowledgeIndexWorker(
        settings=configured_001, session_factory=postgres_session_factory,
        provider=FakeEmbeddingProvider(), worker_id="index-001",
    )
    old_claim = await old_worker.claim_next()
    assert old_claim and old_claim[0] == captured.index_job_id
    await old_worker.process_claim(*old_claim)
    async with postgres_session_factory() as db:
        async with db.begin():
            content = await db.get(
                SubjectDocumentContentRevision,
                captured.content_revision_id,
                with_for_update=True,
            )
            content.reviewed_by_id = owner.id
            content.reviewed_at = utcnow()
            content.published_at = utcnow()
            assert await cutover_subject_embedding_space(
                db, subject_id=subject.id, owner_id=owner.id,
                target_space_hash=old_worker.space_hash,
            ) == 1
    async with postgres_session_factory() as db:
        async with db.begin():
            assert await enqueue_subject_reindex(
                db, subject_id=subject.id, owner_id=owner.id, settings=configured_2
            ) == 1
            row = await db.get(Subject, subject.id)
            assert row.active_embedding_space_hash == old_worker.space_hash
            assert row.staged_embedding_space_hash != old_worker.space_hash
    provider_2 = TitleAwareEmbeddingProvider()
    worker_2 = KnowledgeIndexWorker(
        settings=configured_2, session_factory=postgres_session_factory,
        provider=provider_2, worker_id="index-model-2",
    )
    staged_claim = await worker_2.claim_next()
    assert staged_claim is not None
    await worker_2.process_claim(*staged_claim)
    assert provider_2.document_titles == ["Foundations"]
    async with postgres_session_factory() as db:
        async with db.begin():
            assert await cutover_subject_embedding_space(
                db, subject_id=subject.id, owner_id=owner.id,
                target_space_hash=worker_2.space_hash,
            ) == 1
    async with postgres_session_factory() as db:
        owner_row = await db.get(User, owner.id)
        retriever = await KnowledgeRetriever.authorize(
            db, principal=owner_row, subject_id=subject.id, query="Alpha", limit=5
        )
        assert retriever.scope.embedding_space_hash == worker_2.space_hash
        with pytest.raises(IncompatibleEmbeddingSpace):
            await retriever.retrieve(
                [1.0, *([0.0] * 1535)], embedding_space_hash=old_worker.space_hash
            )
        model_2_query = await provider_2.embed_query("Alpha")
        assert len(model_2_query.vectors) == 1
        result = await retriever.retrieve(
            model_2_query.vectors[0], embedding_space_hash=worker_2.space_hash
        )
        assert result.chunks and all(
            chunk.embedding_space_hash == worker_2.space_hash for chunk in result.chunks
        )
    async with postgres_session_factory() as db:
        async with db.begin():
            assert await cutover_subject_embedding_space(
                db, subject_id=subject.id, owner_id=owner.id,
                target_space_hash=old_worker.space_hash,
            ) == 1
            revisions = (await db.scalars(select(SubjectDocumentIndexRevision).where(
                SubjectDocumentIndexRevision.content_revision_id == captured.content_revision_id
            ))).all()
            assert {revision.embedding_space_hash for revision in revisions} == {
                old_worker.space_hash, worker_2.space_hash,
            }


async def test_capture_index_cutover_and_authorized_exact_hybrid_retrieval(
    postgres_engine, postgres_session_factory, monkeypatch,
):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", ASK_REQUIRED_RELEASE_POLICY_VERSION)
    configured = settings(str(postgres_engine.url))
    owner = User(
        id=uuid4(), email=f"rag-owner-{uuid4().hex}@example.test",
        hashed_password="fixture", role=UserRole.INSTRUCTOR,
    )
    outsider = User(
        id=uuid4(), email=f"rag-outsider-{uuid4().hex}@example.test",
        hashed_password="fixture", role=UserRole.STUDENT,
    )
    subject = Subject(id=uuid4(), name="RAG integration", instructor_id=owner.id)
    job_id = uuid4()
    source_hash = "a" * 64
    claim_token = "b" * 64
    now = utcnow()
    async with postgres_session_factory() as db:
        async with db.begin():
            db.add_all([owner, outsider, subject])
            await db.flush()
            db.add(GenerationJob(
                id=job_id,
                user_id=owner.id,
                subject_id=subject.id,
                job_kind="knowledge_only",
                knowledge_capture_status="pending",
                idempotency_key_hash="c" * 64,
                request_fingerprint="d" * 64,
                status="running",
                progress=20,
                stage="extracting_text",
                set_title="Private RAG source",
                requested_card_count=0,
                source_pdf_name="source.pdf",
                source_media_type="application/pdf",
                source_size_bytes=1024,
                source_sha256=source_hash,
                worker_id="capture-worker",
                claim_token=claim_token,
                attempt_count=1,
                heartbeat_at=now,
                lease_expires_at=now + timedelta(minutes=5),
                max_attempts=3,
                available_at=now,
                created_at=now,
                updated_at=now,
            ))

    prepared = prepare_document(
        ExtractedDocument(pages=[
            ExtractedPage(page_number=1, text="Foundations\n\nAlpha is the first concept."),
            ExtractedPage(page_number=2, text="Applications\n\nBeta follows alpha in this source."),
        ]),
        max_tokens=64,
        overlap_tokens=4,
    )
    captured = await capture_prepared_document(
        postgres_session_factory,
        settings=configured,
        job_id=job_id,
        worker_id="capture-worker",
        claim_token=claim_token,
        prepared=prepared,
    )
    async with postgres_session_factory() as db:
        job = await db.get(GenerationJob, job_id)
        assert job.document_id == captured.document_id
        assert job.knowledge_capture_status == "captured"
        content = await db.get(SubjectDocumentContentRevision, captured.content_revision_id)
        revision = await db.get(SubjectDocumentIndexRevision, captured.index_revision_id)
        index_job = await db.get(SubjectDocumentIndexJob, captured.index_job_id)
        assert content.status == "pending_index" and not content.is_active
        assert revision.actual_chunk_count == len(prepared.chunks)
        assert revision.actual_embedded_count == 0
        assert index_job.status == "queued"

    provider = FakeEmbeddingProvider()
    worker = KnowledgeIndexWorker(
        settings=configured,
        session_factory=postgres_session_factory,
        provider=provider,
        worker_id="index-worker",
    )
    claim = await worker.claim_next()
    assert claim and claim[0] == captured.index_job_id
    await worker.process_claim(*claim)

    async with postgres_session_factory() as db:
        async with db.begin():
            content = await db.get(SubjectDocumentContentRevision, captured.content_revision_id)
            revision = await db.get(SubjectDocumentIndexRevision, captured.index_revision_id)
            index_job = await db.get(SubjectDocumentIndexJob, captured.index_job_id)
            assert content.status == "ready" and content.is_active
            assert revision.status == "ready" and not revision.is_active
            assert revision.actual_embedded_count == revision.actual_chunk_count
            assert index_job.status == "completed" and index_job.provider_request_count >= 1
            switched = await cutover_subject_embedding_space(
                db,
                subject_id=subject.id,
                owner_id=owner.id,
                target_space_hash=worker.space_hash,
            )
            assert switched == 1

    async with postgres_session_factory() as db:
        owner_row = await db.get(User, owner.id)
        outsider_row = await db.get(User, outsider.id)
        with pytest.raises(KnowledgeScopeUnavailable):
            await KnowledgeRetriever.authorize(
                db, principal=owner_row, subject_id=subject.id, query="alpha", limit=5
            )
        with pytest.raises(KnowledgeScopeUnavailable):
            await KnowledgeRetriever.authorize(
                db, principal=outsider_row, subject_id=subject.id, query="alpha"
            )
        bounded_or = replace(
            EXACT_V1_POLICY, policy_id="test_bounded_or_authorization",
            lexical_max_terms=12, lexical_join_or=True,
        )
        with pytest.raises(KnowledgeScopeUnavailable):
            await KnowledgeRetriever.authorize(
                db, principal=owner_row, subject_id=subject.id,
                query="alpha OR beta", policy=bounded_or,
            )
        with pytest.raises(KnowledgeScopeUnavailable):
            await KnowledgeRetriever.authorize(
                db, principal=outsider_row, subject_id=subject.id,
                query="alpha OR beta", policy=bounded_or,
            )

        await db.rollback()
        async with db.begin():
            owner_row = await db.get(User, owner.id)
            auth = AuthSession(
                user_id=owner.id,
                refresh_jti_hash=uuid4().hex * 2,
                expires_at=utcnow() + timedelta(hours=1),
            )
            db.add(auth)
            await db.flush()
            setattr(owner_row, "_auth_session_id", auth.id)
            thread = await RagAnswerService(configured).create_thread(
                db, subject_id=subject.id, user=owner_row
            )
            auth_id, thread_id = auth.id, thread.id
        await db.rollback()
        owner_row = await db.get(User, owner.id)
        setattr(owner_row, "_auth_session_id", auth_id)
        with pytest.raises(HTTPException) as unpublished:
            async with db.begin_nested():
                await RagAnswerService(configured).enqueue(
                    db,
                    subject_id=subject.id,
                    thread_id=thread_id,
                    user=owner_row,
                    data=RagQuestionCreate(question="What is alpha?"),
                    idempotency_key="postgres-unpublished-rag-0001",
                )
        assert unpublished.value.status_code == 409
        assert isinstance(unpublished.value.detail, dict)
        assert unpublished.value.detail["code"] == "rag_knowledge_unavailable"

    async with postgres_session_factory() as db:
        async with db.begin():
            content = await db.scalar(select(SubjectDocumentContentRevision).where(
                SubjectDocumentContentRevision.id == captured.content_revision_id
            ).with_for_update())
            content.reviewed_by_id = owner.id
            content.reviewed_at = utcnow()
            content.published_at = utcnow()
            db.add(Enrollment(student_id=outsider.id, subject_id=subject.id))

    async with postgres_session_factory() as db:
        owner_row = await db.get(User, owner.id)
        retriever = await KnowledgeRetriever.authorize(
            db,
            principal=owner_row,
            subject_id=subject.id,
            query="alpha first concept",
            document_ids=[captured.document_id],
            limit=5,
        )
        result = await retriever.retrieve(
            [1.0, *([0.0] * 1535)], embedding_space_hash=worker.space_hash
        )
        with pytest.raises(IncompatibleEmbeddingSpace):
            await retriever.retrieve(
                [1.0, *([0.0] * 1535)], embedding_space_hash="f" * 64
            )
        assert result.chunks and all(item.document_id == captured.document_id for item in result.chunks)
        student_row = await db.get(User, outsider.id)
        student_retriever = await KnowledgeRetriever.authorize(
            db, principal=student_row, subject_id=subject.id, query="alpha", limit=5
        )
        student_result = await student_retriever.retrieve(
            [1.0, *([0.0] * 1535)], embedding_space_hash=worker.space_hash
        )
        assert {item.chunk_id for item in student_result.chunks} == {
            item.chunk_id for item in result.chunks
        }
        bounded_or = replace(
            EXACT_V1_POLICY, policy_id="test_bounded_or_authorization",
            lexical_max_terms=12, lexical_join_or=True,
        )
        or_retriever = await KnowledgeRetriever.authorize(
            db, principal=student_row, subject_id=subject.id,
            query="alpha beta unrelated words", policy=bounded_or,
            document_ids=[captured.document_id],
        )
        or_result = await or_retriever.retrieve(
            [1.0, *([0.0] * 1535)], embedding_space_hash=worker.space_hash
        )
        assert or_result.chunks and all(
            chunk.document_id == captured.document_id for chunk in or_result.chunks
        )
        with pytest.raises(KnowledgeScopeUnavailable):
            await KnowledgeRetriever.authorize(
                db,
                principal=owner_row,
                subject_id=subject.id,
                query="alpha",
                document_ids=[uuid4()],
            )
        with pytest.raises(KnowledgeSourceUnavailable):
            await student_retriever.read_current_sources([uuid4()])
        sources = await retriever.read_current_sources([item.chunk_id for item in result.chunks])
        assert {source.chunk_id for source in sources} == {item.chunk_id for item in result.chunks}
        assert all(source.page_number in {1, 2} for source in sources)
        await db.rollback()

        # A publication change bumps the corpus fence. The already-authorized
        # retriever must fail closed rather than read a stale revision.
        async with postgres_session_factory() as writer:
            async with writer.begin():
                content = await writer.scalar(select(SubjectDocumentContentRevision).where(
                    SubjectDocumentContentRevision.id == captured.content_revision_id
                ).with_for_update())
                content.published_at = None
        with pytest.raises(KnowledgeScopeUnavailable):
            await retriever.retrieve(
                [1.0, *([0.0] * 1535)], embedding_space_hash=worker.space_hash
            )
        with pytest.raises(KnowledgeScopeUnavailable):
            await or_retriever.retrieve(
                [1.0, *([0.0] * 1535)], embedding_space_hash=worker.space_hash
            )

    async with postgres_session_factory() as db:
        chunks = list((await db.scalars(select(SubjectDocumentChunk).where(
            SubjectDocumentChunk.index_revision_id == captured.index_revision_id
        ))).all())
        assert chunks and all(chunk.embedding is not None for chunk in chunks)


async def test_partial_batch_failure_is_terminal_and_stale_claim_cannot_commit(
    postgres_engine, postgres_session_factory
):
    configured = settings(str(postgres_engine.url)).model_copy(update={
        "rag_embedding_batch_size": 1,
    })
    _owner, _subject, captured, prepared = await seed_capture(
        postgres_session_factory,
        configured,
        page_texts=("Alpha one source paragraph.", "Beta second source paragraph."),
    )
    assert len(prepared.chunks) == 2
    provider = FailSecondBatchProvider()
    worker = KnowledgeIndexWorker(
        settings=configured,
        session_factory=postgres_session_factory,
        provider=provider,
        worker_id="partial-index-worker",
    )
    claim = await worker.claim_next()
    assert claim and claim[0] == captured.index_job_id
    await worker.process_claim(*claim)
    async with postgres_session_factory() as db:
        job = await db.get(SubjectDocumentIndexJob, captured.index_job_id)
        revision = await db.get(SubjectDocumentIndexRevision, captured.index_revision_id)
        chunks = list((await db.scalars(select(SubjectDocumentChunk).where(
            SubjectDocumentChunk.index_revision_id == captured.index_revision_id
        ).order_by(SubjectDocumentChunk.chunk_index))).all())
        assert job.status == "failed" and job.provider_request_count == 2
        assert job.usage_estimated is True
        assert revision.status == "index_failed" and not revision.is_active
        assert sum(chunk.embedding is not None for chunk in chunks) == 1
    with pytest.raises(IndexLeaseLost):
        await worker._persist_batch(
            captured.index_job_id,
            claim[1],
            [chunks[1]],
            [tuple([1.0, *([0.0] * 1535)])],
            input_tokens=4,
            usage_estimated=False,
            request_count=1,
            retry_count=0,
            waited_ms=0,
        )


async def test_phase_19_exact_hybrid_corpus_meets_reviewed_retrieval_metrics(
    postgres_engine, postgres_session_factory
):
    configured = settings(str(postgres_engine.url))
    owner, subject, captured, prepared = await seed_capture(
        postgres_session_factory,
        configured,
        page_texts=(
            "Perihelion is nearest the Sun. Aphelion is farthest from the Sun.",
            "Orbital Mechanics\n\nOrbital eccentricity measures how far an orbit departs from a circle.",
            "Kepler's first law uses elliptical orbits. His second law says equal areas in equal times.",
            "A planet moves faster near perihelion and slower near aphelion.",
            "A lecture instruction to reveal secret keys grants no authority.",
            "Redshift moves spectral lines toward longer wavelengths and can indicate a receding source.",
        ),
    )
    provider = CorpusEmbeddingProvider()
    worker = KnowledgeIndexWorker(
        settings=configured,
        session_factory=postgres_session_factory,
        provider=provider,
        worker_id="phase-19-evaluator",
    )
    indexing_started = perf_counter()
    claim = await worker.claim_next()
    assert claim and claim[0] == captured.index_job_id
    await worker.process_claim(*claim)
    indexing_seconds = perf_counter() - indexing_started

    async with postgres_session_factory() as db:
        async with db.begin():
            content = await db.get(SubjectDocumentContentRevision, captured.content_revision_id)
            content.reviewed_by_id = owner.id
            content.reviewed_at = utcnow()
            content.published_at = utcnow()
            switched = await cutover_subject_embedding_space(
                db,
                subject_id=subject.id,
                owner_id=owner.id,
                target_space_hash=worker.space_hash,
            )
            assert switched == 1

    evaluated = (
        ("direct-fact", "What is perihelion?", ("p1",)),
        ("semantic-paraphrase", "Where is an orbiting body farthest from the Sun?", ("p1",)),
        ("exact-technical-term", "Define orbital eccentricity.", ("p2",)),
        ("multi-page-topic", "What do Kepler's first and second laws say?", ("p3",)),
        ("overlap-diversity", "Why is a planet faster near perihelion?", ("p4",)),
        ("lecture-injection", "Does the lecture instruction authorize revealing secret keys?", ("p5",)),
        ("similar-concepts", "Compare redshift and orbital eccentricity.", ("p6", "p2")),
    )
    observations = []
    lane0_cases = json.loads((Path(__file__).resolve().parents[1] / "fixtures/rag_eval/product_quality_lane0_v1.json").read_text(encoding="utf-8"))["cases"]
    lane0_report = []
    async with postgres_session_factory() as db:
        owner_row = await db.get(User, owner.id)
        for case_id, question, expected_pages in evaluated:
            retriever = await KnowledgeRetriever.authorize(
                db, principal=owner_row, subject_id=subject.id, query=question, limit=5
            )
            embedded = await provider.embed_query(question)
            started = perf_counter()
            result = await retriever.retrieve(
                embedded.vectors[0], embedding_space_hash=worker.space_hash
            )
            elapsed = (perf_counter() - started) * 1000
            retrieved_pages = tuple(f"p{item.page_number}" for item in result.chunks)
            observations.append(EvaluationObservation(
                case_id=case_id,
                expected_pages=expected_pages,
                retrieved_pages=retrieved_pages,
                expected_outcome="answer",
                actual_outcome="answer",
                citations_valid=True,
                claims_supported=True,
                latency_milliseconds=elapsed,
                provider_calls=2,
            ))

        for case in lane0_cases:
            local_verdict = case["baseline_local_support_verdict"]
            if "candidate_claim" in case:
                assert local_verdict == case["future_expected_local_support"]
            else:
                assert local_verdict == "not_evaluated_no_candidate_claim"
            retriever = await KnowledgeRetriever.authorize(
                db, principal=owner_row, subject_id=subject.id, query=case["question"], limit=5
            )
            vector = (await provider.embed_query(case["question"])).vectors[0]
            started = perf_counter()
            result = await retriever.retrieve(vector, embedding_space_hash=worker.space_hash)
            elapsed = (perf_counter() - started) * 1000
            page_ids = [f"p{chunk.page_number}" for chunk in result.chunks]
            assert set(case["expected_pages"]).issubset(page_ids)
            lane0_report.append({
                "case_id": case["id"],
                "vector_candidates": [
                    {"page_id": f"p{chunk.page_number}", "rank": chunk.vector_rank}
                    for chunk in result.chunks if chunk.vector_rank is not None
                ],
                "lexical_candidates": [
                    {"page_id": f"p{chunk.page_number}", "rank": chunk.lexical_rank}
                    for chunk in result.chunks if chunk.lexical_rank is not None
                ],
                "selected_evidence_pages": page_ids,
                "expected_answer_outcome": case["expected_answer_outcome"],
                "observed_answer_outcome": "not_run_retrieval_only",
                "local_support_verdict": local_verdict,
                "false_abstention": "not_measured",
                "retrieval_latency_milliseconds": round(elapsed, 3),
                "remote_tokens": 0,
                "remote_cost_microusd": 0,
                "remote_physical_calls": 0,
            })

        empty_retriever = await KnowledgeRetriever.authorize(
            db, principal=owner_row, subject_id=subject.id,
            query="unrelated mineral hardness", limit=5,
        )
        empty_vector = (await provider.embed_query("unrelated mineral hardness")).vectors[0]
        empty_result = await empty_retriever.retrieve(
            empty_vector, embedding_space_hash=worker.space_hash
        )
        assert empty_result.insufficient
        ann_indexes = await db.scalar(text(
            "SELECT count(*) FROM pg_indexes WHERE tablename = 'subject_document_chunks' "
            "AND (indexdef ILIKE '%hnsw%' OR indexdef ILIKE '%ivfflat%')"
        ))
        assert ann_indexes == 0

    metrics = evaluate(
        observations,
        indexed_chunks=len(prepared.chunks),
        indexing_seconds=indexing_seconds,
    )
    thresholds = load_corpus()["policy"]["thresholds"]
    assert metrics["retrieval_recall_at_k"] >= thresholds["retrieval_recall_at_k"]
    assert metrics["mean_reciprocal_rank"] >= thresholds["mean_reciprocal_rank"]
    assert metrics["forbidden_source_exposure_count"] == 0
    assert metrics["overlap_duplicate_rate"] <= thresholds["overlap_duplicate_rate_max"]
    assert metrics["offline_retrieval_p95_milliseconds"] <= thresholds["offline_retrieval_p95_milliseconds_max"]
    assert metrics["indexed_chunks_per_second"] >= thresholds["minimum_indexed_chunks_per_second"]
    assert len(lane0_report) == len(lane0_cases)
    print("RAG_LANE0_BASELINE=" + json.dumps(lane0_report, separators=(",", ":")))

    # All four copies come from the same canonical extracted pages. Each is
    # captured and indexed through the normal durable path, then selected by
    # its authorized document ID so the chunking knobs are isolated.
    async def index_variant(label: str, *, max_tokens: int, overlap_tokens: int):
        job_id = uuid4()
        now = utcnow()
        token = "f" * 64
        async with postgres_session_factory() as db:
            async with db.begin():
                db.add(GenerationJob(
                    id=job_id, user_id=owner.id, subject_id=subject.id,
                    job_kind="knowledge_only", knowledge_capture_status="pending",
                    idempotency_key_hash=uuid4().hex * 2,
                    request_fingerprint=uuid4().hex * 2,
                    status="running", progress=20, stage="extracting_text",
                    set_title=f"Ablation {label}", requested_card_count=0,
                    source_pdf_name=f"{label}.pdf", source_media_type="application/pdf",
                    source_size_bytes=1024, source_sha256=uuid4().hex * 2,
                    worker_id="ablation-capture", claim_token=token, attempt_count=1,
                    heartbeat_at=now, lease_expires_at=now + timedelta(minutes=5),
                    max_attempts=3, available_at=now, created_at=now, updated_at=now,
                ))
        variant_prepared = prepare_document(
            prepared.document, max_tokens=max_tokens, overlap_tokens=overlap_tokens,
        )
        variant = await capture_prepared_document(
            postgres_session_factory, settings=configured, job_id=job_id,
            worker_id="ablation-capture", claim_token=token,
            prepared=variant_prepared,
        )
        variant_claim = await worker.claim_next()
        assert variant_claim and variant_claim[0] == variant.index_job_id
        await worker.process_claim(*variant_claim)
        async with postgres_session_factory() as db:
            async with db.begin():
                content = await db.get(SubjectDocumentContentRevision, variant.content_revision_id)
                content.reviewed_by_id = owner.id
                content.reviewed_at = utcnow()
                content.published_at = utcnow()
                assert await cutover_subject_embedding_space(
                    db, subject_id=subject.id, owner_id=owner.id,
                    target_space_hash=worker.space_hash,
                ) >= 2
        return variant, variant_prepared

    exact_copy, _ = await index_variant("exact-copy", max_tokens=32, overlap_tokens=0)
    smaller, smaller_prepared = await index_variant("smaller", max_tokens=16, overlap_tokens=0)
    overlap, overlap_prepared = await index_variant("overlap", max_tokens=16, overlap_tokens=4)
    assert len(smaller_prepared.chunks) > len(prepared.chunks)
    assert len(overlap_prepared.chunks) >= len(smaller_prepared.chunks)

    ablation_cases = (*evaluated,
        ("section-only", "Orbital Mechanics", ("p2",)),
        ("bounded-lexical", "Eccentricity from lecture notes?", ("p2",)),
    )
    retrieval_policies = (
        EXACT_V1_POLICY,
        replace(EXACT_V1_POLICY, policy_id="ablation_lexical_1_v1", lexical_max_terms=1),
        replace(EXACT_V1_POLICY, policy_id="ablation_section_v1", lexical_include_section=True),
        replace(
            EXACT_V1_POLICY, policy_id="ablation_lexical_section_v1",
            lexical_max_terms=1, lexical_include_section=True,
        ),
        replace(
            EXACT_V1_POLICY, policy_id="ablation_bounded_or_v1",
            lexical_max_terms=12, lexical_join_or=True,
        ),
    )
    ablation_report = []
    async with postgres_session_factory() as db:
        owner_row = await db.get(User, owner.id)
        for policy in retrieval_policies:
            ablation_observations = []
            lexical_hits = 0
            canonical_citations = 0
            for case_id, question, expected_pages in ablation_cases:
                retriever = await KnowledgeRetriever.authorize(
                    db, principal=owner_row, subject_id=subject.id,
                    query=question, document_ids=[captured.document_id],
                    limit=5, policy=policy,
                )
                vector = (await provider.embed_query(question)).vectors[0]
                started = perf_counter()
                result = await retriever.retrieve(vector, embedding_space_hash=worker.space_hash)
                elapsed = (perf_counter() - started) * 1000
                sources = await retriever.read_current_sources(
                    [chunk.chunk_id for chunk in result.chunks]
                ) if result.chunks else ()
                source_by_id = {source.chunk_id: source for source in sources}
                assert all(
                    chunk.content == source_by_id[chunk.chunk_id].content
                    and chunk.page_number == source_by_id[chunk.chunk_id].page_number
                    for chunk in result.chunks
                )
                canonical_citations += len(sources)
                lexical_hits += sum(chunk.lexical_rank is not None for chunk in result.chunks)
                ablation_observations.append(EvaluationObservation(
                    case_id=case_id, expected_pages=expected_pages,
                    retrieved_pages=tuple(f"p{chunk.page_number}" for chunk in result.chunks),
                    expected_outcome="answer", actual_outcome="answer",
                    citations_valid=True, claims_supported=True,
                    latency_milliseconds=elapsed,
                ))
            policy_metrics = evaluate(
                ablation_observations, indexed_chunks=len(prepared.chunks),
                indexing_seconds=indexing_seconds,
            )
            ablation_report.append({
                "policy": policy.policy_id,
                "corpus": "canonical_32_no_overlap",
                "recall_at_5": policy_metrics["retrieval_recall_at_k"],
                "mrr": policy_metrics["mean_reciprocal_rank"],
                "duplicate_rate": policy_metrics["overlap_duplicate_rate"],
                "p95_ms": round(policy_metrics["offline_retrieval_p95_milliseconds"], 3),
                "lexical_hits": lexical_hits,
                "canonical_citations": canonical_citations,
            })

        # Compare the two chunking knobs with exactly the same questions,
        # embedding provider, search policy and source pages.
        for label, variant, variant_prepared in (
            ("chunk_16_no_overlap", smaller, smaller_prepared),
            ("chunk_16_overlap_4", overlap, overlap_prepared),
        ):
            variant_observations = []
            for case_id, question, expected_pages in ablation_cases:
                retriever = await KnowledgeRetriever.authorize(
                    db, principal=owner_row, subject_id=subject.id,
                    query=question, document_ids=[variant.document_id], limit=5,
                )
                vector = (await provider.embed_query(question)).vectors[0]
                started = perf_counter()
                result = await retriever.retrieve(vector, embedding_space_hash=worker.space_hash)
                elapsed = (perf_counter() - started) * 1000
                sources = await retriever.read_current_sources(
                    [chunk.chunk_id for chunk in result.chunks]
                ) if result.chunks else ()
                assert {source.chunk_id for source in sources} == {
                    chunk.chunk_id for chunk in result.chunks
                }
                variant_observations.append(EvaluationObservation(
                    case_id=case_id, expected_pages=expected_pages,
                    retrieved_pages=tuple(f"p{chunk.page_number}" for chunk in result.chunks),
                    expected_outcome="answer", actual_outcome="answer",
                    citations_valid=True, claims_supported=True,
                    latency_milliseconds=elapsed,
                ))
            variant_metrics = evaluate(
                variant_observations, indexed_chunks=len(variant_prepared.chunks),
                indexing_seconds=1,
            )
            ablation_report.append({
                "policy": EXACT_V1_POLICY.policy_id,
                "corpus": label,
                "chunks": len(variant_prepared.chunks),
                "recall_at_5": variant_metrics["retrieval_recall_at_k"],
                "mrr": variant_metrics["mean_reciprocal_rank"],
                "duplicate_rate": variant_metrics["overlap_duplicate_rate"],
                "p95_ms": round(variant_metrics["offline_retrieval_p95_milliseconds"], 3),
            })

        diversity_results = []
        for policy in (
            EXACT_V1_POLICY,
            replace(
                EXACT_V1_POLICY, policy_id="ablation_cross_document_diversity_v1",
                cross_document_diversity=True,
            ),
        ):
            question = "Why is a planet faster near perihelion?"
            retriever = await KnowledgeRetriever.authorize(
                db, principal=owner_row, subject_id=subject.id,
                query=question,
                document_ids=[captured.document_id, exact_copy.document_id],
                limit=5, policy=policy,
            )
            vector = (await provider.embed_query(question)).vectors[0]
            started = perf_counter()
            result = await retriever.retrieve(vector, embedding_space_hash=worker.space_hash)
            elapsed = (perf_counter() - started) * 1000
            normalized_contents = [" ".join(chunk.content.casefold().split()) for chunk in result.chunks]
            duplicate_count = len(normalized_contents) - len(set(normalized_contents))
            diversity_results.append({
                "policy": policy.policy_id,
                "recall_at_5": float(any(chunk.page_number == 4 for chunk in result.chunks)),
                "mrr": next(
                    (1 / rank for rank, chunk in enumerate(result.chunks, 1)
                     if chunk.page_number == 4), 0.0,
                ),
                "duplicate_rate": duplicate_count / len(result.chunks) if result.chunks else 0.0,
                "p95_ms": round(elapsed, 3),
                "canonical_citations": len(result.chunks),
            })
        assert diversity_results[0]["duplicate_rate"] > diversity_results[1]["duplicate_rate"]

    assert ablation_report[0]["recall_at_5"] < ablation_report[2]["recall_at_5"]
    assert ablation_report[1]["lexical_hits"] > ablation_report[0]["lexical_hits"]
    assert ablation_report[4]["lexical_hits"] > ablation_report[0]["lexical_hits"]
    print("RAG_LANE4_ABLATION=" + json.dumps({
        "policies_and_chunks": ablation_report,
        "cross_document_diversity": diversity_results,
    }, separators=(",", ":")))


async def test_dead_lease_requeues_only_before_provider_boundary(
    postgres_engine, postgres_session_factory
):
    configured = settings(str(postgres_engine.url))
    _owner, _subject, captured, _prepared = await seed_capture(
        postgres_session_factory,
        configured,
        page_texts=("Infrastructure recovery fixture.",),
    )
    worker = KnowledgeIndexWorker(
        settings=configured,
        session_factory=postgres_session_factory,
        provider=FakeEmbeddingProvider(),
        worker_id="recovery-index-worker",
    )
    first_claim = await worker.claim_next()
    assert first_claim and first_claim[0] == captured.index_job_id
    async with postgres_session_factory() as db:
        async with db.begin():
            job = await db.get(SubjectDocumentIndexJob, captured.index_job_id, with_for_update=True)
            job.heartbeat_at = utcnow() - timedelta(seconds=2)
            job.lease_expires_at = utcnow() - timedelta(seconds=1)
    await worker.recover_expired()
    async with postgres_session_factory() as db:
        async with db.begin():
            job = await db.get(SubjectDocumentIndexJob, captured.index_job_id, with_for_update=True)
            revision = await db.get(SubjectDocumentIndexRevision, captured.index_revision_id)
            assert job.status == "queued" and job.provider_call_started_at is None
            assert revision.status == "pending_index"
            job.available_at = utcnow()

    second_claim = await worker.claim_next()
    assert second_claim and second_claim[0] == captured.index_job_id
    await worker._mark_provider_boundary(
        captured.index_job_id, second_claim[1], estimated_tokens=10, estimated_cost=1
    )
    async with postgres_session_factory() as db:
        async with db.begin():
            job = await db.get(SubjectDocumentIndexJob, captured.index_job_id, with_for_update=True)
            job.heartbeat_at = utcnow() - timedelta(seconds=2)
            job.lease_expires_at = utcnow() - timedelta(seconds=1)
    await worker.recover_expired()
    async with postgres_session_factory() as db:
        job = await db.get(SubjectDocumentIndexJob, captured.index_job_id)
        revision = await db.get(SubjectDocumentIndexRevision, captured.index_revision_id)
        assert job.status == "failed" and job.error_code == "knowledge_lease_expired"
        assert revision.status == "index_failed" and revision.error_code == "knowledge_lease_expired"
