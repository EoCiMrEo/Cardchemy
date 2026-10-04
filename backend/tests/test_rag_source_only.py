"""Source-only Ask contracts; no answer provider or verifier is constructed."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from types import SimpleNamespace

from app.ai.embeddings import EmbeddingResponse
from app.ai.providers import AIProviderError, ProviderUsage

from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION, Settings
from app.models.knowledge import embedding_space_hash
from app.models.rag import (
    RagAnswerJob, RagAnswerQuestionContext, RagAnswerQuotaEvent,
    RagAnswerStageAttempt, RagMessage,
)
from app.schemas.rag import RagQuestionCreate
from app.services.knowledge_retrieval import KnowledgeRetriever
from app.services.knowledge_retrieval import SOURCE_NAVIGATION_RETRIEVAL_POLICY
from app.services.rag_answers import RagAnswerService, locate_page_reference
from app.workers.rag_answer import RagAnswerWorker
from app.time_utils import utcnow
from tests.test_rag_answers import _authorize, _seed, _settings


async def _as_historical_source_job(db, job: RagAnswerJob, policy: str) -> None:
    """Keep immutable judge profiles distinct on historical source fixtures."""

    # SQLite fixtures deliberately synthesize an old immutable snapshot. A
    # retired policy cannot retain the v7 admission fields or context binding.
    # Real PostgreSQL jobs are immutable and are seeded under their old policy.
    with db.no_autoflush:
        context = await db.get(RagAnswerQuestionContext, job.id)
        if context is not None:
            await db.delete(context)
    job.source_context_policy_version = None
    job.source_context_admission_sha256 = None
    job.answer_policy_version = policy
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
    if policy == "related_knowledge_navigation_v4":
        # A valid historical v4 snapshot must still be fenced by the current worker.
        job.source_judge_provider = "gemini"
        job.source_judge_base_url = "https://generativelanguage.googleapis.com"
        job.source_judge_model = "gemini-3.8-flash"
        job.source_judge_contract_version = "source_id_only_public_v1"
        job.source_judge_input_price_microusd_per_million = 1_500_000
        job.source_judge_output_price_microusd_per_million = 7_500_000
        job.source_judge_max_input_tokens = 8192
        job.source_judge_max_output_tokens = 1024
    elif policy == "related_knowledge_navigation_v5":
        job.source_judge_provider = "gemini"
        job.source_judge_base_url = "https://generativelanguage.googleapis.com"
        job.source_judge_model = "gemini-3.5-flash-lite"
        job.source_judge_contract_version = "visual_source_id_v1"
        job.source_judge_input_price_microusd_per_million = 300_000
        job.source_judge_output_price_microusd_per_million = 2_500_000
        job.source_judge_max_input_tokens = 32768
        job.source_judge_max_output_tokens = 2048
        job.source_judge_thinking_level = "high"
        job.source_judge_timeout_seconds = 60


def test_page_reference_locates_only_text_present_on_the_current_page():
    content = "Topic\nBLEU compares n-gram\n overlap with a reference."
    quote = "BLEU compares n-gram overlap with a reference."
    span = locate_page_reference(content, quote)
    assert span is not None
    assert content[span[0]:span[1]] == "BLEU compares n-gram\n overlap with a reference."
    assert locate_page_reference(content, "BLEU generates answers") is None


async def test_source_only_admission_snapshots_embedding_without_answer_profile(db, monkeypatch):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", ASK_REQUIRED_RELEASE_POLICY_VERSION)
    settings: Settings = _settings(
        rag_ai_provider_enabled=False, rag_ai_api_key=None,
        rag_local_support_enabled=False,
    )
    assert settings.rag_source_only_available is True
    _owner, student, _outsider, subject, _session = await _seed(db)
    monkeypatch.setattr(KnowledgeRetriever, "authorize", _authorize(settings))
    service = RagAnswerService(settings)

    async with db.begin():
        thread = await service.create_thread(db, subject_id=subject.id, user=student)
        job = await service.enqueue(
            db, subject_id=subject.id, thread_id=thread.id, user=student,
            data=RagQuestionCreate(question="What does BLEU measure?"),
            idempotency_key=uuid4().hex,
        )

    stored = await db.scalar(select(RagAnswerJob).where(RagAnswerJob.id == job.id))
    assert stored is not None
    assert stored.answer_policy_version == ASK_REQUIRED_RELEASE_POLICY_VERSION
    assert stored.retrieval_policy == SOURCE_NAVIGATION_RETRIEVAL_POLICY.policy_id
    assert stored.embedding_provider == settings.rag_embedding_provider
    assert stored.embedding_model == settings.rag_embedding_model
    assert stored.ai_provider is None and stored.ai_model is None
    assert stored.support_policy_version is None
    assert stored.estimated_output_tokens == settings.rag_source_judge_max_output_tokens
    assert stored.result_kind is None and stored.answer_message_id is None
    assert stored.estimated_cost_microusd is not None
    assert stored.estimated_cost_microusd > 0
    messages = (await db.scalars(select(RagMessage).where(RagMessage.thread_id == thread.id))).all()
    assert [(message.role, message.content) for message in messages] == [
        ("user", "What does BLEU measure?")
    ]


@pytest.mark.parametrize("old_policy", ["hybrid_source_sufficiency_v5", "hybrid_source_sufficiency_v6", "hybrid_source_sufficiency_v7"])
async def test_old_source_selector_snapshot_cannot_execute_under_new_worker(
    db, session_factory, monkeypatch, old_policy,
):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", ASK_REQUIRED_RELEASE_POLICY_VERSION)
    settings = _settings(rag_ai_provider_enabled=False, rag_ai_api_key=None,
                         rag_local_support_enabled=False)
    _owner, student, _outsider, subject, _session = await _seed(db)
    monkeypatch.setattr(KnowledgeRetriever, "authorize", _authorize(settings))
    service = RagAnswerService(settings)
    async with db.begin():
        thread = await service.create_thread(db, subject_id=subject.id, user=student)
        job = await service.enqueue(
            db, subject_id=subject.id, thread_id=thread.id, user=student,
            data=RagQuestionCreate(question="What does BLEU stand for?"),
            idempotency_key=uuid4().hex,
        )
        await _as_historical_source_job(db, job, "related_knowledge_navigation_v3")
        job.retrieval_policy = old_policy

    class NeverEmbedding:
        async def embed_query(self, _text):
            pytest.fail("Old source selector snapshot called the embedding provider")

    worker = RagAnswerWorker(settings=settings, session_factory=session_factory,
                             embedding_provider=NeverEmbedding(), worker_id="old-source-policy")
    assert await worker.claim_next() is None
    async with session_factory() as read_db:
        terminal = await read_db.get(RagAnswerJob, job.id)
        assert terminal.status == "failed"
        assert terminal.error_code == "rag_profile_mismatch"


@pytest.mark.parametrize("retired_policy", ["two_request_local_support_v1", "related_knowledge_v1"])
async def test_source_only_gate_rejects_admission_before_question_write(db, monkeypatch, retired_policy):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", retired_policy)
    settings = _settings()
    _owner, student, _outsider, subject, _session = await _seed(db)
    service = RagAnswerService(settings)
    with pytest.raises(Exception) as denied:
        async with db.begin():
            await service.create_thread(db, subject_id=subject.id, user=student)
    assert getattr(denied.value, "status_code", None) == 503
    assert (await db.scalars(select(RagMessage))).all() == []


@pytest.mark.parametrize("old_policy", ["hybrid_source_sufficiency_v5", "hybrid_source_sufficiency_v6", "hybrid_source_sufficiency_v7"])
async def test_old_source_retrieval_policy_retry_is_hidden_and_rejected_before_quota(db, monkeypatch, old_policy):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", ASK_REQUIRED_RELEASE_POLICY_VERSION)
    settings = _settings()
    _owner, student, _outsider, subject, _session = await _seed(db)
    monkeypatch.setattr(KnowledgeRetriever, "authorize", _authorize(settings))
    service = RagAnswerService(settings)
    async with db.begin():
        thread = await service.create_thread(db, subject_id=subject.id, user=student)
        job = await service.enqueue(
            db, subject_id=subject.id, thread_id=thread.id, user=student,
            data=RagQuestionCreate(question="What does BLEU stand for?"),
            idempotency_key=uuid4().hex,
        )
        await _as_historical_source_job(db, job, "related_knowledge_navigation_v3")
        job.retrieval_policy = old_policy
        job.status = "failed"
        job.completed_at = utcnow()
        job.error_code = "rag_answer_failed"
        job.error_message = "Answer generation failed."
        job.error_retryable = True
    assert service.job_response(job).can_retry is False
    baseline = (await db.scalar(select(func.count()).select_from(RagAnswerQuotaEvent)
                                .where(RagAnswerQuotaEvent.job_id == job.id)))
    await db.commit()

    # Catch inside the transaction so rollback cannot mask a premature write.
    async with db.begin():
        with pytest.raises(HTTPException) as rejected:
            await service.retry(
                db, subject_id=subject.id, thread_id=thread.id, job_id=job.id,
                user=student, idempotency_key=uuid4().hex,
            )
        assert rejected.value.status_code == 409
        assert rejected.value.detail["code"] == "rag_answer_not_retryable"
        assert job.status == "failed" and job.manual_retry_count == 0
        assert job.provider_request_count == 0 and job.provider_call_started_at is None
        assert await db.scalar(select(func.count()).select_from(RagAnswerQuotaEvent)
                               .where(RagAnswerQuotaEvent.job_id == job.id)) == baseline
        history = await service.history(
            db, subject_id=subject.id, thread_id=thread.id, user=student, limit=10,
        )
        assert [message.id for message in history.messages] == [job.question_message_id]


async def test_source_only_worker_completes_no_match_with_one_embedding_and_no_answer(
    db, session_factory, monkeypatch,
):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", ASK_REQUIRED_RELEASE_POLICY_VERSION)
    settings = _settings(rag_ai_provider_enabled=False, rag_ai_api_key=None,
                         rag_local_support_enabled=False)
    _owner, student, _outsider, subject, _session = await _seed(db)
    scope = SimpleNamespace(
        corpus_revision=subject.corpus_revision,
        embedding_space_hash=embedding_space_hash(settings.rag_embedding_space_identity),
    )

    class EmptyRetriever:
        async def retrieve(self, _vector, *, embedding_space_hash):
            assert embedding_space_hash == scope.embedding_space_hash
            return SimpleNamespace(insufficient=True, chunks=())

    retriever = EmptyRetriever()
    retriever.scope = scope

    async def authorize(_cls, _db, **_kwargs):
        return retriever

    monkeypatch.setattr(KnowledgeRetriever, "authorize", classmethod(authorize))
    service = RagAnswerService(settings)
    async with db.begin():
        thread = await service.create_thread(db, subject_id=subject.id, user=student)
        job = await service.enqueue(
            db, subject_id=subject.id, thread_id=thread.id, user=student,
            data=RagQuestionCreate(question="What does BLEU measure?"),
            idempotency_key=uuid4().hex,
        )

    class OneEmbedding:
        def __init__(self):
            self.questions: list[str] = []

        async def embed_query(self, question: str):
            self.questions.append(question)
            return EmbeddingResponse(
                vectors=(tuple([1.0, *([0.0] * 1535)]),),
                usage=ProviderUsage(7, 0, False),
            )

    embedding = OneEmbedding()
    worker = RagAnswerWorker(settings=settings, session_factory=session_factory,
                             embedding_provider=embedding, worker_id="source-only-test")
    claim = await worker.claim_next()
    assert claim is not None and claim[0] == job.id
    await worker.process_claim(*claim)

    async with session_factory() as read_db:
        stored = await read_db.get(RagAnswerJob, job.id)
        assert stored is not None
        assert stored.status == "completed" and stored.result_kind == "no_match"
        assert stored.answer_message_id is None
        assert stored.provider_request_count == 1 and stored.provider_retry_count == 0
        rows = (await read_db.scalars(select(RagAnswerStageAttempt).where(
            RagAnswerStageAttempt.job_id == job.id,
        ))).all()
        assert [(row.stage, row.physical_request_count) for row in rows] == [
            ("query_embedding", 1), ("retrieval", 0),
        ]
        messages = (await read_db.scalars(select(RagMessage).where(
            RagMessage.thread_id == thread.id,
        ))).all()
        assert [message.role for message in messages] == ["user"]
    assert embedding.questions == ["What does BLEU measure?"]


@pytest.mark.parametrize("category", [
    "embedding_provider_unavailable", "embedding_provider_rate_limited", "embedding_provider_timeout",
])
async def test_embedding_outage_finishes_with_local_search_without_remote_retry(
    db, session_factory, monkeypatch, category,
):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", ASK_REQUIRED_RELEASE_POLICY_VERSION)
    settings = _settings(rag_ai_provider_enabled=False, rag_ai_api_key=None,
                         rag_local_support_enabled=False)
    _owner, student, _outsider, subject, _session = await _seed(db)
    counts = {"embedding": 0, "lexical": 0}

    class LocalRetriever:
        scope = SimpleNamespace(corpus_revision=subject.corpus_revision,
                                embedding_space_hash=embedding_space_hash(settings.rag_embedding_space_identity))

        async def retrieve(self, *args, **kwargs):
            pytest.fail("An unavailable embedding must not become a fake query vector")

        async def retrieve_lexical(self):
            counts["lexical"] += 1
            return SimpleNamespace(insufficient=True, chunks=())

    async def authorize(_cls, _db, **kwargs):
        assert kwargs["policy"].policy_id == "hybrid_source_navigation_v9"
        return LocalRetriever()

    monkeypatch.setattr(KnowledgeRetriever, "authorize", classmethod(authorize))
    service = RagAnswerService(settings)
    async with db.begin():
        thread = await service.create_thread(db, subject_id=subject.id, user=student)
        job = await service.enqueue(db, subject_id=subject.id, thread_id=thread.id, user=student,
                                    data=RagQuestionCreate(question="Explain orbital eccentricity"),
                                    idempotency_key=uuid4().hex)

    class OneFailedEmbedding:
        async def embed_query(self, question):
            counts["embedding"] += 1
            assert question == "Explain orbital eccentricity"
            raise AIProviderError(category, "Embedding search is unavailable.", retryable=True,
                                  reason_code="http_rate_limited" if category.endswith("rate_limited")
                                  else "transport_timeout" if category.endswith("timeout") else "http_server_error")

    worker = RagAnswerWorker(settings=settings, session_factory=session_factory,
                             embedding_provider=OneFailedEmbedding(), worker_id="lexical-fallback")
    claim = await worker.claim_next()
    assert claim is not None
    await worker.process_claim(*claim)
    async with session_factory() as read_db:
        stored = await read_db.get(RagAnswerJob, job.id)
        assert stored.status == "completed" and stored.result_kind == "no_match"
        assert stored.answer_message_id is None and stored.error_code is None
        assert stored.provider_request_count == 1 and stored.provider_retry_count == 0
        assert stored.attempt_cost_unknown and stored.usage_estimated
        assert stored.failed_stage == "query_embedding" and stored.provider_error_category == category
        stages = (await read_db.scalars(select(RagAnswerStageAttempt).where(
            RagAnswerStageAttempt.job_id == job.id))).all()
        assert {row.stage for row in stages} == {"query_embedding", "retrieval"}
        assert sum(row.physical_request_count for row in stages) == 1
        assert all(row.retry_count == 0 for row in stages)
        response = service.job_response(stored)
        assert response.search_mode == "lexical_fallback"
        assert response.failure_kind is None and response.can_retry is False
        assert response.actual_cost_microusd is None
    assert counts == {"embedding": 1, "lexical": 1}


@pytest.mark.parametrize(("old_policy", "old_retrieval"), [
    ("related_knowledge_v1", "hybrid_source_sufficiency_v7"),
    ("related_knowledge_navigation_v2", "hybrid_source_navigation_v8"),
    ("related_knowledge_navigation_v4", "hybrid_source_navigation_v9"),
    ("related_knowledge_navigation_v5", "hybrid_source_navigation_v9"),
])
async def test_previous_source_jobs_are_fenced_before_embedding(
    db, session_factory, monkeypatch, old_policy, old_retrieval,
):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", ASK_REQUIRED_RELEASE_POLICY_VERSION)
    settings = _settings()
    _owner, student, _outsider, subject, _session = await _seed(db)
    monkeypatch.setattr(KnowledgeRetriever, "authorize", _authorize(settings))
    service = RagAnswerService(settings)
    async with db.begin():
        thread = await service.create_thread(db, subject_id=subject.id, user=student)
        job = await service.enqueue(db, subject_id=subject.id, thread_id=thread.id, user=student,
                                    data=RagQuestionCreate(question="Explain orbital eccentricity"),
                                    idempotency_key=uuid4().hex)
        await _as_historical_source_job(db, job, old_policy)
        job.retrieval_policy = old_retrieval

    class NeverEmbedding:
        async def embed_query(self, _question):
            pytest.fail("Historical source policy was executed under the navigation worker")

    worker = RagAnswerWorker(settings=settings, session_factory=session_factory,
                             embedding_provider=NeverEmbedding(), worker_id="v1-fenced")
    assert await worker.claim_next() is None
    async with session_factory() as read_db:
        stored = await read_db.get(RagAnswerJob, job.id)
        assert stored.status == "failed" and stored.error_code == "rag_profile_mismatch"
        assert stored.provider_request_count == 0
