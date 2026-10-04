"""Keyless worker contracts for the dormant v4 source-ID judgment stage."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import timedelta
from decimal import Decimal
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.ai.related_evidence import RelatedExcerptSelection
from app.ai.source_judgment import SourceJudgmentError
from app.services.knowledge_retrieval import (
    AuthorizedKnowledgeSource, ExpandedKnowledgeNeighbor, RetrievedKnowledgeChunk,
)
from app.workers import rag_answer as module


def _chunk(page: int, content: str, *, fusion: float = 0.1) -> RetrievedKnowledgeChunk:
    return RetrievedKnowledgeChunk(
        chunk_id=uuid4(), document_id=uuid4(), document_title="Public PDF",
        content_revision_id=uuid4(), index_revision_id=uuid4(),
        page_number=page, section="Methods", content=content,
        token_count=20, embedding_space_hash="space", corpus_revision=1,
        vector_similarity=0.8, lexical_score=0.5, vector_rank=1,
        lexical_rank=1, fusion_score=fusion,
    )


def _selection(page: int) -> RelatedExcerptSelection:
    text = f"Methods page {page}. The method updates weights after each example."
    return RelatedExcerptSelection(
        _chunk(page, text), 16, len(text), "canonical_page", text,
    )


class _Retriever:
    def __init__(self, chunks: tuple[RetrievedKnowledgeChunk, ...],
                 neighbor: RetrievedKnowledgeChunk | None = None):
        self.chunks = chunks
        self.neighbor = neighbor
        self.calls = []

    async def expand_source_neighbors(self, anchors, **kwargs):
        self.calls.append(("expand", kwargs))
        return (ExpandedKnowledgeNeighbor(self.neighbor, anchors[0].chunk_id, 1),) if self.neighbor else ()

    async def read_current_sources(self, ids):
        self.calls.append(("sources", ids))
        by_id = {chunk.chunk_id: chunk for chunk in (*self.chunks, *((self.neighbor,) if self.neighbor else ())) }
        return tuple(AuthorizedKnowledgeSource(**{
            key: value for key, value in asdict(by_id[chunk_id]).items()
            if key in AuthorizedKnowledgeSource.__dataclass_fields__
        }) for chunk_id in ids)

    async def read_current_source_pages(self, ids, **kwargs):
        self.calls.append(("pages", kwargs))
        by_id = {chunk.chunk_id: chunk for chunk in (*self.chunks, *((self.neighbor,) if self.neighbor else ())) }
        return {chunk_id: by_id[chunk_id].content for chunk_id in ids}


@pytest.mark.asyncio
async def test_candidate_pool_uses_current_canonical_pages_and_bounded_neighbors():
    first = _chunk(1, "The method updates weights after each example.")
    neighbor = replace(
        _chunk(2, "A neighbor page explains the update rule in detail."),
        document_id=first.document_id,
        content_revision_id=first.content_revision_id,
        index_revision_id=first.index_revision_id,
    )
    retriever = _Retriever((first,), neighbor)
    pool = await module._v4_candidate_pool("How does the method update weights?", (first,), retriever)
    assert len(pool.selections) == 2
    assert pool.examined_pages == 2
    assert all(item.source_kind == "canonical_page" for item in pool.selections)
    assert any(item.source.chunk_id == neighbor.chunk_id for item in pool.selections)
    assert retriever.calls[0] == ("expand", {
        "radius": 2, "max_chunks": 30, "max_pages": 12, "max_tokens": 8192,
    })
    wire = module._v4_wire("How does the method update weights?", pool.selections)
    assert set(wire["user_payload"]) == {"question", "candidates"}
    assert all(set(item) == {"id", "page", "page_text", "cue"}
               for item in wire["user_payload"]["candidates"])
    assert all(item["cue"] in item["page_text"] for item in wire["user_payload"]["candidates"])


@pytest.mark.asyncio
async def test_candidate_pool_inspects_twelve_pages_but_sends_at_most_four():
    docs = (uuid4(), uuid4())
    chunks = tuple(
        replace(
            _chunk(page, "The method updates weights after each example."),
            document_id=docs[(page - 1) // 6],
        )
        for page in range(1, 13)
    )
    retriever = _Retriever(chunks)
    pool = await module._v4_candidate_pool(
        "How does the method update weights?", chunks, retriever,
    )
    assert len(pool.selections) == 4
    assert pool.examined_pages == 12
    assert pool.examined_chunks == 12
    assert any(call[0] == "sources" and len(call[1]) == 12 for call in retriever.calls)
    assert all(item.source_kind == "canonical_page" for item in pool.selections)


@pytest.mark.asyncio
async def test_candidate_pool_rejects_a_changed_source_before_egress():
    chunk = _chunk(1, "The method updates weights after each example.")

    class _Changed(_Retriever):
        async def read_current_source_pages(self, ids, **kwargs):
            return {chunk_id: "A changed page" for chunk_id in ids}

        async def read_current_sources(self, ids):
            rows = await super().read_current_sources(ids)
            return tuple(replace(row, content="changed") for row in rows)

    retriever = _Changed((chunk,))
    with pytest.raises(module.KnowledgeSourceUnavailable):
        await module._v4_candidate_pool("How are weights updated?", (chunk,), retriever)


@pytest.mark.asyncio
async def test_candidate_pool_does_not_treat_a_missing_canonical_page_as_no_match():
    chunk = _chunk(1, "The method updates weights after each example.")

    class _Missing(_Retriever):
        async def read_current_source_pages(self, ids, **kwargs):
            return {}

    with pytest.raises(module.KnowledgeSourceUnavailable):
        await module._v4_candidate_pool(
            "How are weights updated?", (chunk,), _Missing((chunk,)),
        )


@pytest.mark.asyncio
async def test_unresolved_v4_referent_completes_as_clarification_without_provider(monkeypatch):
    question_id = uuid4()
    thread_id = uuid4()
    job = SimpleNamespace(
        answer_policy_version=module._SOURCE_JUDGE_POLICY,
        question_message_id=question_id,
        thread_id=thread_id,
        document_ids=[],
        subject_id=uuid4(),
        corpus_revision=1,
        embedding_space_hash="space",
    )
    question = SimpleNamespace(
        role="user", thread_id=thread_id, content="What does it mean?",
    )

    class _Db:
        async def get(self, _model, _id):
            return question

    class _Session:
        async def __aenter__(self):
            return _Db()

        async def __aexit__(self, *_args):
            return None

    class _Retriever:
        scope = SimpleNamespace(corpus_revision=1, embedding_space_hash="space")

    async def authorize(_cls, _db, **_kwargs):
        return _Retriever()

    monkeypatch.setattr(module.KnowledgeRetriever, "authorize", classmethod(authorize))
    worker = object.__new__(module.RagAnswerWorker)
    worker.session_factory = _Session
    worker._profile_matches = lambda _job: True

    async def claimed(*_args):
        return job

    async def active(*_args):
        return True

    async def principal(*_args):
        return SimpleNamespace()

    async def history(*_args):
        return ()

    outcomes = []

    async def complete(*_args, **kwargs):
        outcomes.append(kwargs)

    async def no_provider(*_args):
        pytest.fail("An unresolved referent must not start a provider stage")

    worker._claimed_job = claimed
    worker._session_active = active
    worker._current_principal = principal
    worker._bounded_history = history
    worker._complete_source = complete
    worker._mark_provider_boundary = no_provider
    await worker._source_first(uuid4(), "claim")
    assert outcomes == [{"selections": (), "clarification_needed": True}]


@pytest.mark.asyncio
async def test_v4_clarification_persists_distinct_source_free_result(monkeypatch):
    thread_id = uuid4()
    question = SimpleNamespace(
        role="user", thread_id=thread_id,
        content="What does it mean?",
        expires_at=module.utcnow() + timedelta(minutes=5),
    )
    thread = SimpleNamespace()
    job = SimpleNamespace(
        id=uuid4(), answer_policy_version=module._SOURCE_JUDGE_POLICY,
        thread_id=thread_id, question_message_id=uuid4(),
        subject_id=uuid4(), document_ids=[], corpus_revision=1,
        embedding_space_hash="space", provider_call_started_at=None,
        retrieval_completed_at=None,
    )

    class _Db:
        def begin(self):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, model, _id, **_kwargs):
            return question if model is module.RagMessage else thread

        async def execute(self, _query):
            return None

        async def flush(self):
            return None

    async def no_lock(_db):
        return None

    class _Retriever:
        scope = SimpleNamespace(corpus_revision=1, embedding_space_hash="space")

    async def authorize(_cls, _db, **_kwargs):
        return _Retriever()

    monkeypatch.setattr(module, "acquire_knowledge_write_lock", no_lock)
    monkeypatch.setattr(module.KnowledgeRetriever, "authorize", classmethod(authorize))
    worker = object.__new__(module.RagAnswerWorker)
    worker.session_factory = _Db
    worker._profile_matches = lambda _job: True

    async def claimed(*_args, **_kwargs):
        return job

    async def active(*_args, **_kwargs):
        return True

    async def principal(*_args, **_kwargs):
        return SimpleNamespace()

    worker._claimed_job = claimed
    worker._session_active = active
    worker._current_principal = principal
    await worker._complete_source(
        job.id, "claim", selections=(), clarification_needed=True,
    )
    assert job.status == "completed"
    assert job.result_kind == "clarification_needed"
    assert job.answer_message_id is None
    assert job.retrieval_completed_at is None


def test_v4_profile_requires_exact_snapshot_and_release_fence(monkeypatch):
    settings = SimpleNamespace(
        rag_embedding_provider="gemini",
        rag_embedding_endpoint_identity="https://generativelanguage.googleapis.com",
        rag_embedding_model="gemini-embedding-001",
        rag_answer_available=True,
        rag_source_judge_provider_enabled=True,
        rag_source_judge_provider="gemini",
        rag_source_judge_endpoint_identity="https://generativelanguage.googleapis.com",
        rag_source_judge_model="gemini-3.8-flash",
        rag_source_judge_contract_version="source_id_only_public_v1",
        rag_source_judge_input_cost_per_million_usd=Decimal("1.50"),
        rag_source_judge_output_cost_per_million_usd=Decimal("7.50"),
        rag_source_judge_max_input_tokens=8192,
        rag_source_judge_max_output_tokens=1024,
        rag_source_judge_provider_max_retries=0,
    )
    worker = object.__new__(module.RagAnswerWorker)
    worker.settings = settings
    worker.space_hash = "space"
    job = SimpleNamespace(
        result_kind=None,
        embedding_provider="gemini",
        embedding_base_url="https://generativelanguage.googleapis.com",
        embedding_model="gemini-embedding-001",
        ai_provider=None, ai_base_url=None, ai_model=None,
        ai_catalog_version=None, ai_schema_policy_version=None,
        support_policy_version=None, embedding_space_hash="space",
        retrieval_policy=module.SOURCE_NAVIGATION_RETRIEVAL_POLICY.policy_id,
        answer_policy_version=module._SOURCE_JUDGE_POLICY,
        source_judge_provider="gemini",
        source_judge_base_url="https://generativelanguage.googleapis.com",
        source_judge_model="gemini-3.8-flash",
        source_judge_contract_version="source_id_only_public_v1",
        source_judge_input_price_microusd_per_million=1_500_000,
        source_judge_output_price_microusd_per_million=7_500_000,
        source_judge_max_input_tokens=8192,
        source_judge_max_output_tokens=1024,
    )
    monkeypatch.setattr(module, "ASK_REQUIRED_RELEASE_POLICY_VERSION", "related_knowledge_navigation_v3")
    assert worker._profile_matches(job) is False
    monkeypatch.setattr(module, "ASK_REQUIRED_RELEASE_POLICY_VERSION", module._SOURCE_JUDGE_POLICY)
    assert worker._profile_matches(job) is True
    job.source_judge_model = "gemini-3.5-flash"
    assert worker._profile_matches(job) is False
    job.source_judge_model = "gemini-3.8-flash"
    settings.rag_source_judge_provider_enabled = False
    assert worker._profile_matches(job) is False


def test_v4_profile_matches_ceiled_price_snapshot(monkeypatch):
    monkeypatch.setattr(module, "ASK_REQUIRED_RELEASE_POLICY_VERSION", module._SOURCE_JUDGE_POLICY)
    settings = SimpleNamespace(
        rag_embedding_provider="gemini",
        rag_embedding_endpoint_identity="https://generativelanguage.googleapis.com",
        rag_embedding_model="gemini-embedding-001",
        rag_answer_available=True, rag_source_judge_provider_enabled=True,
        rag_source_judge_provider="gemini",
        rag_source_judge_endpoint_identity="https://generativelanguage.googleapis.com",
        rag_source_judge_model="gemini-3.8-flash",
        rag_source_judge_contract_version="source_id_only_public_v1",
        rag_source_judge_input_cost_per_million_usd=Decimal("1.5000001"),
        rag_source_judge_output_cost_per_million_usd=Decimal("7.5000001"),
        rag_source_judge_max_input_tokens=8192,
        rag_source_judge_max_output_tokens=1024,
        rag_source_judge_provider_max_retries=0,
    )
    worker = object.__new__(module.RagAnswerWorker)
    worker.settings = settings
    worker.space_hash = "space"
    job = SimpleNamespace(
        result_kind=None, embedding_provider="gemini",
        embedding_base_url="https://generativelanguage.googleapis.com",
        embedding_model="gemini-embedding-001",
        ai_provider=None, ai_base_url=None, ai_model=None,
        ai_catalog_version=None, ai_schema_policy_version=None,
        support_policy_version=None, embedding_space_hash="space",
        retrieval_policy=module.SOURCE_NAVIGATION_RETRIEVAL_POLICY.policy_id,
        answer_policy_version=module._SOURCE_JUDGE_POLICY,
        source_judge_provider="gemini",
        source_judge_base_url="https://generativelanguage.googleapis.com",
        source_judge_model="gemini-3.8-flash",
        source_judge_contract_version="source_id_only_public_v1",
        source_judge_input_price_microusd_per_million=1_500_001,
        source_judge_output_price_microusd_per_million=7_500_001,
        source_judge_max_input_tokens=8192,
        source_judge_max_output_tokens=1024,
    )
    assert worker._profile_matches(job) is True


class _FakeJudge:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    async def judge(self, wire):
        self.calls.append(wire)
        if self.error:
            raise self.error
        return self.response


def _worker(judge: _FakeJudge):
    worker = object.__new__(module.RagAnswerWorker)
    worker.settings = SimpleNamespace(
        rag_source_judge_provider_timeout_seconds=30,
        rag_source_judge_max_input_tokens=8192,
        rag_source_judge_max_output_tokens=1024,
        rag_source_judge_input_cost_per_million_usd=Decimal("1.50"),
        rag_source_judge_output_cost_per_million_usd=Decimal("7.50"),
    )
    worker._source_judge = judge
    events = []

    async def begin(*_args, **_kwargs):
        events.append("claimed")
        return uuid4()

    async def finish(*_args, **kwargs):
        events.append(("finished", _args[3], _args[4], kwargs))

    worker._begin_stage = begin
    worker._finish_stage = finish
    return worker, events


@pytest.mark.asyncio
async def test_judge_claims_before_one_call_and_maps_ordered_ids_only():
    candidates = (_selection(1), _selection(2))
    judge = _FakeJudge(module._JudgeResponse(
        '{"selected_ids":["S02","S01"]}', "STOP", 100, 8, 12,
    ))
    worker, events = _worker(judge)
    result = await worker._judge_sources(uuid4(), "claim", "How does it update?", candidates)
    assert events[0] == "claimed"
    assert len(judge.calls) == 1
    assert result == (candidates[1], candidates[0])
    usage = events[1][1]
    assert (usage.request_count, usage.retry_count, usage.input_tokens,
            usage.output_tokens, usage.cost_microusd) == (1, 0, 100, 20, 300)
    assert events[1][2] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [
    module._JudgeResponse('{"selected_ids":["S01","S01"]}', "STOP", 100, 2, 0),
    module._JudgeResponse('{"selected_ids":["S03"]}', "STOP", 100, 2, 0),
    module._JudgeResponse('{"selected_ids":[]}', "MAX_TOKENS", 100, 2, 0),
    module._JudgeResponse('{"selected_ids":[]}', "STOP", None, 2, 0),
    module._JudgeResponse('{"selected_ids":[]}', "STOP", 8193, 2, 0),
    module._JudgeResponse('{"selected_ids":[]}', "STOP", 100, 1000, 25),
])
async def test_judge_rejects_invalid_finish_ids_and_unknown_or_excess_usage(response):
    judge = _FakeJudge(response)
    worker, events = _worker(judge)
    with pytest.raises(SourceJudgmentError):
        await worker._judge_sources(uuid4(), "claim", "What is the method?", (_selection(1), _selection(2)))
    assert len(judge.calls) == 1
    assert events[0] == "claimed"
    assert events[1][2] == "invalid_ai_output"
    assert events[1][3]["uncertain"] is True


@pytest.mark.asyncio
async def test_judge_uses_configured_token_caps_and_prices():
    judge = _FakeJudge(module._JudgeResponse(
        '{"selected_ids":["S01"]}', "STOP", 100, 8, 12,
    ))
    worker, events = _worker(judge)
    worker.settings.rag_source_judge_max_input_tokens = 1024
    worker.settings.rag_source_judge_max_output_tokens = 32
    worker.settings.rag_source_judge_input_cost_per_million_usd = Decimal("3")
    worker.settings.rag_source_judge_output_cost_per_million_usd = Decimal("9")
    result = await worker._judge_sources(
        uuid4(), "claim", "How does it update?", (_selection(1),),
    )
    assert len(result) == 1
    assert events[1][1].cost_microusd == 480

    judge.response = module._JudgeResponse(
        '{"selected_ids":["S01"]}', "STOP", 1025, 8, 12,
    )
    with pytest.raises(SourceJudgmentError, match="usage_over_budget"):
        await worker._judge_sources(
            uuid4(), "claim", "How does it update?", (_selection(1),),
        )
    assert events[-1][2] == "invalid_ai_output"

    judge.response = module._JudgeResponse(
        '{"selected_ids":["S01"]}', "STOP", 100, 8, 12,
    )
    worker.settings.rag_source_judge_max_output_tokens = 19
    with pytest.raises(SourceJudgmentError, match="usage_over_budget"):
        await worker._judge_sources(
            uuid4(), "claim", "How does it update?", (_selection(1),),
        )
    assert events[-1][2] == "invalid_ai_output"


@pytest.mark.asyncio
async def test_judge_stage_reserves_the_configured_snapshot_cost():
    worker, _events = _worker(_FakeJudge())
    del worker._begin_stage
    worker.worker_id = "test-worker"
    judge_cost = module._judge_cost(1024, 32)
    job = SimpleNamespace(
        id=uuid4(), manual_retry_count=0, attempt_count=1,
        answer_policy_version=module._SOURCE_JUDGE_POLICY,
        estimated_cost_microusd=judge_cost,
        attempt_cost_microusd=0,
        source_judge_max_input_tokens=1024,
        source_judge_max_output_tokens=32,
        source_judge_input_price_microusd_per_million=1_500_000,
        source_judge_output_price_microusd_per_million=7_500_000,
    )

    class _Db:
        def __init__(self):
            self.scalar_count = 0

        def begin(self):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def scalar(self, _query):
            self.scalar_count += 1
            return None if self.scalar_count == 1 else SimpleNamespace()

    db = _Db()
    worker.session_factory = lambda: db
    worker._profile_matches = lambda _job: True

    async def claimed(*_args, **_kwargs):
        return job

    class _ReachedAccessCheck(Exception):
        pass

    async def active(*_args):
        raise _ReachedAccessCheck()

    worker._claimed_job = claimed
    worker._session_active = active
    with pytest.raises(_ReachedAccessCheck):
        await worker._begin_stage(
            job.id, "claim", "source_judgment", remote=True,
            judge_selections=(_selection(1),),
        )


@pytest.mark.asyncio
async def test_stale_claim_cannot_commit_judge_usage():
    worker, _events = _worker(_FakeJudge())
    del worker._finish_stage

    class _Db:
        def begin(self):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            pytest.fail("A stale claim must be rejected before stage mutation")

    worker.session_factory = _Db

    async def stale(*_args, **_kwargs):
        raise module.AnswerLeaseLost()

    worker._claimed_job = stale
    with pytest.raises(module.AnswerLeaseLost):
        await worker._finish_stage(
            uuid4(), "expired-claim", uuid4(),
            module._Usage(request_count=1), None, False,
        )


@pytest.mark.asyncio
async def test_judge_transport_error_is_one_shot_and_usage_unknown():
    judge = _FakeJudge(error=module.AIProviderError(
        "ai_provider_timeout", "safe", retryable=False,
        reason_code="transport_timeout",
    ))
    worker, events = _worker(judge)
    with pytest.raises(module.AIProviderError):
        await worker._judge_sources(uuid4(), "claim", "What is the method?", (_selection(1),))
    assert len(judge.calls) == 1
    assert events[1][1].estimated is True
    assert events[1][2] == "ai_provider_timeout"
    assert events[1][3]["uncertain"] is True


@pytest.mark.asyncio
async def test_rest_adapter_sends_store_false_and_one_bounded_request(monkeypatch):
    requests = []
    options = {}

    async def handler(request):
        requests.append(request)
        return httpx.Response(200, json={
            "candidates": [{"finishReason": "STOP", "content": {
                "parts": [{"text": '{"selected_ids":[]}'}],
            }}],
            "usageMetadata": {"promptTokenCount": 30,
                              "candidatesTokenCount": 4,
                              "thoughtsTokenCount": 3,
                              "totalTokenCount": 37},
        })

    original_client = httpx.AsyncClient

    def fake_client(**kwargs):
        options.update(kwargs)
        return original_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(module.httpx, "AsyncClient", fake_client)
    settings = SimpleNamespace(
        rag_source_judge_api_key_value="fake-test-key",
        rag_source_judge_model="gemini-3.8-flash",
        rag_source_judge_max_input_tokens=8192,
        rag_source_judge_max_output_tokens=1024,
        rag_source_judge_provider_timeout_seconds=30,
        rag_source_judge_concurrency=1,
        rag_source_judge_requests_per_minute=10,
        rag_source_judge_input_tokens_per_minute=100_000,
        rag_source_judge_rate_limit_safety_percent=100,
    )
    judge = module._GeminiSourceJudge(settings)
    wire = module._v4_wire("What is the method?", (_selection(1),))
    response = await judge.judge(wire)
    assert response == module._JudgeResponse('{"selected_ids":[]}', "STOP", 30, 4, 3)
    assert options == {"timeout": 30, "follow_redirects": False}
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-3.8-flash:generateContent"
    )
    assert request.headers["x-goog-api-key"] == "fake-test-key"
    body = json.loads(request.content)
    assert set(body) == {"systemInstruction", "contents", "generationConfig", "store"}
    assert body["store"] is False
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}
    assert "tools" not in body and "temperature" not in body
    assert "Current question:\nWhat is the method?" in body["contents"][0]["parts"][0]["text"]
