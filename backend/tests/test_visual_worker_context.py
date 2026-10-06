"""Invented, keyless v8 worker boundaries; no provider, operator env or DB."""
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.ai.providers import current_attempt_scope
from app.ai.providers.source_visual import VisualJudgeResponse
from app.ai.providers.source_visual import GeminiVisualSourceJudge
from app.models.knowledge import embedding_space_hash
from app.services.rag_question_context import HydratedQuestionContext, QuestionContextUnavailable
from app.services.source_visual_preparation import PdfSourceBinding, PreparedVisualSources
from app.workers import rag_answer as module
from tests.test_source_candidate_pool import _selection
from tests.test_source_visual_context import fixture
from tests.test_source_visual_runtime_profile import settings
from tests.test_visual_source_completion_migration import current_sample
from tests.test_visual_source_judgment_worker import verdict


def setup(monkeypatch, *, anchored=False):
    args, request = fixture(anchored)
    snapshot = args["snapshot"]
    binding = module.visual_contract.bind_question_context(
        args["question"], snapshot, checked_at=args["checked_at"],
        raw_navigation_query=args["raw_navigation_query"],
        preceding_question=args["preceding_question"], anchor=args["anchor"],
    )
    local = args["question"] if not anchored else args["question"] + " " + args["anchor"].subject
    context = HydratedQuestionContext(snapshot, binding, args["question"],
        args["preceding_question"], args["raw_navigation_query"], local)
    question = SimpleNamespace(role="user", thread_id=snapshot.current.thread_id,
        content=args["question"], expires_at=snapshot.current.expires_at)
    thread = SimpleNamespace()
    job = SimpleNamespace(id=uuid4(), answer_policy_version=module._VISUAL_SOURCE_JUDGE_POLICY,
        question_message_id=snapshot.current.message_id, user_id=snapshot.current.user_id,
        thread_id=snapshot.current.thread_id, subject_id=snapshot.current.subject_id,
        document_ids=[], corpus_revision=1, embedding_space_hash="space",
        provider_call_started_at=None, retrieval_completed_at=None, manual_retry_count=0,
        attempt_count=1, estimated_cost_microusd=100000, attempt_cost_microusd=0,
        source_judge_max_input_tokens=32768, source_judge_max_output_tokens=4096,
        source_judge_input_price_microusd_per_million=300000,
        source_judge_output_price_microusd_per_million=2500000)
    calls = []
    class Session:
        def begin(self):
            return self
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_args):
            return None
        async def get(self, model, *_args, **_kwargs):
            return question if model is module.RagMessage else thread
        async def scalar(self, _query):
            return None
        async def execute(self, _query):
            calls.append(("write",))
        async def flush(self):
            calls.append(("flush",))
        def add(self, _row):
            calls.append(("add",))
    retriever = SimpleNamespace(scope=SimpleNamespace(corpus_revision=1, embedding_space_hash="space"))
    async def authorize(_cls, _db, **kwargs):
        calls.append(("authorize", kwargs["query"]))
        return retriever
    async def rehydrate(_db, **kwargs):
        assert kwargs["job"] is job
        calls.append(("hydrate",))
        return context
    async def prepare(_db, **kwargs):
        calls.append(("prepare", kwargs))
        return PreparedVisualSources(request, (pdf,))
    async def no_lock(_db):
        return None
    async def claimed(*_args, **_kwargs):
        return job
    async def active(*_args, **_kwargs):
        return True
    async def principal(*_args, **_kwargs):
        return SimpleNamespace(id=job.user_id)
    selected = _selection(1)
    pdf = PdfSourceBinding(selected.source.document_id, selected.source.content_revision_id,
        job.subject_id, "a" * 64, 1)
    monkeypatch.setattr(module.KnowledgeRetriever, "authorize", classmethod(authorize))
    monkeypatch.setattr(module, "rehydrate_question_context", rehydrate)
    monkeypatch.setattr(module, "prepare_visual_sources", prepare)
    monkeypatch.setattr(module, "acquire_knowledge_write_lock", no_lock)
    worker = object.__new__(module.RagAnswerWorker)
    worker.session_factory = Session
    worker.settings = SimpleNamespace(rag_source_judge_provider_timeout_seconds=120,
        rag_source_judge_input_cost_per_million_usd=Decimal("0.30"),
        rag_source_judge_output_cost_per_million_usd=Decimal("2.50"),
        rag_embedding_input_cost_per_million_usd=Decimal("0.20"), rag_answer_job_timeout_seconds=300)
    worker._profile_matches = lambda _job: True
    worker._claimed_job, worker._session_active, worker._current_principal = claimed, active, principal
    return SimpleNamespace(worker=worker, job=job, question=question, context=context,
        retriever=retriever, selected=selected, pdf=pdf, calls=calls, request=request)


async def forbidden(*_args, **_kwargs):
    pytest.fail("This boundary must not execute")


async def test_invalid_admission_stops_before_embedding_and_history(monkeypatch):
    state = setup(monkeypatch, anchored=True)
    async def changed(*_args, **_kwargs):
        raise QuestionContextUnavailable()
    monkeypatch.setattr(module, "rehydrate_question_context", changed)
    state.worker._bounded_history = forbidden
    state.worker._mark_provider_boundary = forbidden
    with pytest.raises(module.AnswerQuestionContextChanged) as caught:
        await state.worker._source_first(state.job.id, "claim")
    assert str(caught.value) == ""


async def test_unresolved_v8_clarifies_without_history_provider_or_preparation(monkeypatch):
    state = setup(monkeypatch)
    async def unresolved(*_args, **_kwargs):
        return replace(state.context, local_query=None,
            binding=replace(state.context.binding, status="needs_clarification"))
    monkeypatch.setattr(module, "rehydrate_question_context", unresolved)
    state.worker._bounded_history = forbidden
    state.worker._mark_provider_boundary = forbidden
    results = []
    async def complete(*_args, **kwargs):
        results.append(kwargs)
    state.worker._complete_source = complete
    await state.worker._source_first(state.job.id, "claim")
    assert results == [{"selections": (), "clarification_needed": True}]
    assert not any(row[0] == "prepare" for row in state.calls)


async def test_literal_subject_is_local_only_and_embedding_keeps_exact_current_question(monkeypatch):
    state = setup(monkeypatch, anchored=True)
    embedding_calls = []
    class Embedding:
        async def embed_query(self, question):
            embedding_calls.append(question)
            return SimpleNamespace(vectors=((0.25,),), usage=SimpleNamespace(input_tokens=7, estimated=False))
    state.worker._embedding_provider = Embedding()
    state.worker._bounded_history = forbidden
    async def mark(*_args):
        state.calls.append(("boundary",))
    async def begin(*_args, **_kwargs):
        return uuid4()
    async def finish(*_args, **_kwargs):
        return None
    async def retrieve(*_args, **_kwargs):
        return SimpleNamespace(insufficient=True, chunks=())
    async def complete(*_args, **kwargs):
        assert kwargs["selections"] == ()
    state.worker._mark_provider_boundary, state.worker._begin_stage = mark, begin
    state.worker._finish_stage, state.worker._complete_source = finish, complete
    state.retriever.retrieve = retrieve
    await state.worker._source_first(state.job.id, "claim")
    assert embedding_calls == [state.question.content]
    assert state.context.preceding_question not in embedding_calls
    assert state.calls[-1] == ("authorize", state.context.local_query)


@pytest.mark.parametrize("boundary", ["mark", "embedding_stage"])
async def test_revalidation_at_each_embedding_boundary_blocks_changed_context(monkeypatch, boundary):
    state = setup(monkeypatch, anchored=True)
    async def changed(*_args, **_kwargs):
        raise QuestionContextUnavailable()
    monkeypatch.setattr(module, "rehydrate_question_context", changed)
    with pytest.raises(module.AnswerQuestionContextChanged):
        if boundary == "mark":
            await state.worker._mark_provider_boundary(state.job.id, "claim")
        else:
            await state.worker._begin_stage(state.job.id, "claim", "query_embedding", remote=True)
    assert state.job.provider_call_started_at is None
    assert not any(row[0] in {"add", "flush"} for row in state.calls)


async def test_visual_preparation_receives_binding_and_dispatch_receives_same_context(monkeypatch):
    state = setup(monkeypatch, anchored=True)
    async def begin(*_args, **kwargs):
        state.calls.append(("begin", kwargs))
        return uuid4()
    async def finish(*_args, **kwargs):
        state.calls.append(("finish", kwargs))
    class Judge:
        async def judge(self, request):
            assert request is state.request
            state.calls.append(("judge",))
            return VisualJudgeResponse(verdict(), "STOP", 100, 25, 30)
    state.worker._begin_stage, state.worker._finish_stage, state.worker._source_judge = begin, finish, Judge()
    result = await state.worker._judge_visual_sources(state.job.id, "claim", state.question.content, (state.selected,))
    assert result == ((state.selected,), False, (state.pdf,))
    preparation = next(row[1] for row in state.calls if row[0] == "prepare")
    assert preparation["snapshot"] == state.context.snapshot
    assert preparation["anchor"] == state.context.binding.anchor
    assert preparation["raw_navigation_query"] is None
    dispatch = next(row[1] for row in state.calls if row[0] == "begin")
    assert dispatch["judge_question_context"] == state.context


async def test_changed_binding_after_render_stops_physical_dispatch(monkeypatch):
    state = setup(monkeypatch, anchored=True)
    async def begin(*_args, **kwargs):
        await state.worker._question_context(object(), state.job, expected=kwargs["judge_question_context"])
    async def changed_prepare(_db, **_kwargs):
        async def changed(*_args, **_kwargs):
            return replace(state.context, local_query="Different local context")
        monkeypatch.setattr(module, "rehydrate_question_context", changed)
        return PreparedVisualSources(state.request, (state.pdf,))
    monkeypatch.setattr(module, "prepare_visual_sources", changed_prepare)
    state.worker._begin_stage = begin
    state.worker._source_judge = SimpleNamespace(judge=forbidden)
    with pytest.raises(module.AnswerQuestionContextChanged):
        await state.worker._judge_visual_sources(state.job.id, "claim", state.question.content, (state.selected,))


async def test_real_adapter_branch_passes_per_invocation_post_governor_fence(monkeypatch):
    state = setup(monkeypatch)
    async def begin(*_args, **_kwargs):
        return uuid4()
    async def finish(*_args, **_kwargs):
        return None
    async def recheck(job_id, token, candidates, bindings, context):
        assert (job_id, token, candidates, bindings, context) == (
            state.job.id, "claim", (state.selected,), (state.pdf,), state.context)
        state.calls.append(("actual_dispatch_check",))
    class InjectedV3(GeminiVisualSourceJudge):
        def __init__(self):
            pass
        async def judge(self, request, *, before_dispatch=None):
            assert before_dispatch is not None
            state.calls.append(("governor_admitted",))
            await before_dispatch()
            current_attempt_scope(self).record_request("source_judgment", retry=False, waited_seconds=0)
            state.calls.append(("physical_request",))
            return VisualJudgeResponse(verdict(), "STOP", 100, 25, 30)
    state.worker._begin_stage, state.worker._finish_stage = begin, finish
    state.worker._source_judge, state.worker._recheck_visual_dispatch = InjectedV3(), recheck
    await state.worker._judge_visual_sources(state.job.id, "claim", state.question.content, (state.selected,))
    assert [row[0] for row in state.calls][-3:] == ["governor_admitted", "actual_dispatch_check", "physical_request"]


async def test_post_governor_revocation_has_zero_physical_attempts(monkeypatch):
    state = setup(monkeypatch)
    async def begin(*_args, **_kwargs):
        return uuid4()
    usages = []
    async def finish(*args, **kwargs):
        usages.append((args[3], kwargs))
    async def recheck(*_args):
        raise module.AnswerQuestionContextChanged()
    class RevokedV3(GeminiVisualSourceJudge):
        def __init__(self):
            pass
        async def judge(self, request, *, before_dispatch=None):
            await before_dispatch()
            pytest.fail("Revoked context reached physical dispatch")
    state.worker._begin_stage, state.worker._finish_stage = begin, finish
    state.worker._source_judge, state.worker._recheck_visual_dispatch = RevokedV3(), recheck
    with pytest.raises(module.AnswerQuestionContextChanged):
        await state.worker._judge_visual_sources(state.job.id, "claim", state.question.content, (state.selected,))
    assert usages[0][0].request_count == 0 and usages[0][0].retry_count == 0
    assert usages[0][1]["uncertain"] is False


async def test_atomic_completion_rehydrates_before_writing_even_for_empty_result(monkeypatch):
    state = setup(monkeypatch)
    async def changed(*_args, **_kwargs):
        raise QuestionContextUnavailable()
    monkeypatch.setattr(module, "rehydrate_question_context", changed)
    with pytest.raises(module.AnswerQuestionContextChanged):
        await state.worker._complete_source(state.job.id, "claim", selections=())
    assert not any(row[0] in {"write", "add", "flush"} for row in state.calls)
    assert not hasattr(state.job, "status")


@pytest.mark.parametrize("denial", [None, "profile", "lease", "session", "corpus", "page", "context"])
async def test_actual_dispatch_rechecks_scope_sources_and_exact_admission(monkeypatch, denial):
    state = setup(monkeypatch, anchored=True)
    async def current_sources(_ids):
        return (state.selected.source,)
    async def current_pages(_ids, **_kwargs):
        return {state.selected.source.chunk_id: state.selected.page_content}
    async def check_pdf(_db, bindings):
        assert bindings == (state.pdf,)
        state.calls.append(("pdf_check",))
    state.retriever.read_current_sources = current_sources
    state.retriever.read_current_source_pages = current_pages
    monkeypatch.setattr(module, "check_pdf_bindings", check_pdf)
    if denial == "profile":
        state.worker._profile_matches = lambda _job: False
    elif denial == "lease":
        async def lost(*_args, **_kwargs):
            raise module.AnswerLeaseLost()
        state.worker._claimed_job = lost
    elif denial == "session":
        async def inactive(*_args):
            return False
        state.worker._session_active = inactive
    elif denial == "corpus":
        state.retriever.scope.corpus_revision = 2
    elif denial == "page":
        async def changed_page(_ids, **_kwargs):
            return {state.selected.source.chunk_id: "Changed authorized page"}
        state.retriever.read_current_source_pages = changed_page
    elif denial == "context":
        async def changed_context(*_args, **_kwargs):
            return replace(state.context, local_query="Changed literal subject")
        monkeypatch.setattr(module, "rehydrate_question_context", changed_context)
    dispatch = state.worker._recheck_visual_dispatch(state.job.id, "claim", (state.selected,),
        (state.pdf,), state.context)
    if denial is None:
        await dispatch
        assert [row[0] for row in state.calls] == ["authorize", "pdf_check", "hydrate"]
    else:
        with pytest.raises((module.AnswerProfileMismatch, module.AnswerLeaseLost,
            module.AnswerAccessRevoked, module.AnswerCorpusChanged, module.AnswerQuestionContextChanged)):
            await dispatch
    assert not any(row[0] in {"prepare", "write", "add", "flush"} for row in state.calls)


def test_profile_requires_v8_v5_admission_and120_second_ceiling(monkeypatch):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", module._VISUAL_SOURCE_JUDGE_POLICY)
    configured = settings()
    worker = object.__new__(module.RagAnswerWorker)
    worker.settings = configured
    worker.space_hash = embedding_space_hash(configured.rag_embedding_space_identity)
    values = current_sample()
    values.update(answer_policy_version=module._VISUAL_SOURCE_JUDGE_POLICY,
        source_judge_contract_version=module.visual_contract.CONTRACT_VERSION,
        source_judge_timeout_seconds=120, embedding_space_hash=worker.space_hash,
        source_context_policy_version=module.visual_contract.ADMISSION_SCHEMA,
        source_context_admission_sha256="a" * 64)
    assert worker._profile_matches(SimpleNamespace(**values))
    for name, invalid in [("answer_policy_version", "related_knowledge_navigation_v6"),
        ("source_judge_contract_version", "visual_source_id_v2"),
        ("source_context_policy_version", None), ("source_context_admission_sha256", None),
        ("source_context_admission_sha256", "g" * 64),
        ("source_judge_timeout_seconds", 121)]:
        changed = dict(values)
        changed[name] = invalid
        assert not worker._profile_matches(SimpleNamespace(**changed))


async def test_current_worker_uses_admitted_literal_subject_only_for_search_and_never_sends_history(
    db, session_factory, monkeypatch,
):
    """Only the admission-bound subject extends local search; embeddings stay raw."""

    from datetime import timedelta
    from app.ai.embeddings import EmbeddingResponse
    from app.ai.providers import ProviderUsage
    from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION
    from app.models.rag import RagAnswerJob, RagMessage
    from app.schemas.rag import RagQuestionCreate
    from app.services.knowledge_retrieval import KnowledgeRetriever
    from app.services.rag_answers import RagAnswerService
    from app.time_utils import utcnow
    from app.workers.rag_answer import RagAnswerWorker
    from tests.test_rag_answers import _seed, _settings

    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", ASK_REQUIRED_RELEASE_POLICY_VERSION)
    settings = _settings(rag_ai_provider_enabled=False, rag_ai_api_key=None,
                         rag_local_support_enabled=False)
    _owner, student, _outsider, subject, _session = await _seed(db)
    scope = SimpleNamespace(
        corpus_revision=subject.corpus_revision,
        embedding_space_hash=embedding_space_hash(settings.rag_embedding_space_identity),
    )
    seen_queries: list[str] = []

    class EmptyRetriever:
        async def retrieve(self, _vector, *, embedding_space_hash):
            assert embedding_space_hash == scope.embedding_space_hash
            return SimpleNamespace(insufficient=True, chunks=())

    retriever = EmptyRetriever()
    retriever.scope = scope

    async def authorize(_cls, _db, **kwargs):
        seen_queries.append(kwargs["query"])
        return retriever

    monkeypatch.setattr(KnowledgeRetriever, "authorize", classmethod(authorize))

    async def forbid_history(*_args, **_kwargs):
        raise AssertionError("Current source-only worker must use its admission binding")

    monkeypatch.setattr(RagAnswerWorker, "_bounded_history", forbid_history, raising=False)
    service = RagAnswerService(settings)
    current = "How does it work?"
    async with db.begin():
        thread = await service.create_thread(db, subject_id=subject.id, user=student)
        now = utcnow()
        db.add(RagMessage(
            id=uuid4(), thread_id=thread.id, user_id=student.id, subject_id=subject.id,
            role="user", outcome=None, content="What is spectral index?", source_count=0,
            created_at=now - timedelta(seconds=1), expires_at=now + timedelta(days=1),
        ))
        await db.flush()
        job = await service.enqueue(
            db, subject_id=subject.id, thread_id=thread.id, user=student,
            data=RagQuestionCreate(question=current), idempotency_key=uuid4().hex,
        )

    class OneEmbedding:
        def __init__(self):
            self.questions: list[str] = []

        async def embed_query(self, text: str):
            self.questions.append(text)
            return EmbeddingResponse(
                vectors=(tuple([1.0, *([0.0] * 1535)]),),
                usage=ProviderUsage(7, 0, False),
            )

    embedding = OneEmbedding()
    worker = RagAnswerWorker(settings=settings, session_factory=session_factory,
                             embedding_provider=embedding, worker_id="candidate-spy")
    claim = await worker.claim_next()
    assert claim is not None and claim[0] == job.id
    await worker.process_claim(*claim)
    assert embedding.questions == [current]
    expanded = "How does it work? spectral index"
    assert seen_queries.count(expanded) == 1
    assert all(query == current or query == expanded for query in seen_queries)
    async with session_factory() as read_db:
        stored = await read_db.get(RagAnswerJob, job.id)
        assert stored is not None
        assert stored.status == "completed" and stored.result_kind == "no_match"
        assert stored.provider_request_count == 1 and stored.provider_retry_count == 0
        assert stored.answer_message_id is None
