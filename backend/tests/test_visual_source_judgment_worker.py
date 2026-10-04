"""Current v8 dispatch/access and ID-only telemetry, entirely keyless.

The v5/v6 stored profiles are fenced separately; these fixtures exercise the
current visual dispatch with an invented immutable raw-clear context.
"""
from dataclasses import replace
from decimal import Decimal
from hashlib import sha256
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.ai.providers import AIProviderError, current_attempt_scope, provider_attempt_scope
from app.ai.providers.source_visual import VisualJudgeResponse
from app.ai.source_judgment_visual import VisualSourceJudgmentError
from app.services.source_visual_preparation import PdfSourceBinding, PreparedVisualSources
from app.services.rag_question_context_v2 import HydratedQuestionContext
from app.workers import rag_answer as module
from tests.test_source_judgment_worker import _selection
from tests.test_source_visual_preparation_v5 import fixture


QUESTION = "How does the method update weights?"


def verdict(label="direct", *, status="clear", ids=("S01",)):
    return json.dumps({"question_status": status, "pages": [
        {"id": sid, "usefulness": label, "cue_locates": label == "direct"}
        for sid in ids
    ]})


def setup(monkeypatch, *, response=None, error=None, physical_calls=1):
    context_args, _ = fixture(False)
    original = context_args["snapshot"]
    snapshot = replace(original, current=replace(original.current,
        content_sha256=sha256(QUESTION.encode()).hexdigest()))
    context_binding = module.visual_contract.bind_question_context(
        QUESTION, snapshot, checked_at=context_args["checked_at"],
        raw_navigation_query=QUESTION, preceding_question=None, anchor=None)
    context = HydratedQuestionContext(snapshot, context_binding, QUESTION, None, QUESTION, QUESTION)
    selected = _selection(1)
    job = SimpleNamespace(answer_policy_version=module._VISUAL_SOURCE_JUDGE_POLICY,
        subject_id=snapshot.current.subject_id, question_message_id=snapshot.current.message_id,
        user_id=snapshot.current.user_id, thread_id=snapshot.current.thread_id, document_ids=[],
        corpus_revision=1, embedding_space_hash="space")
    binding = PdfSourceBinding(selected.source.document_id, selected.source.content_revision_id,
                               job.subject_id, "a" * 64, 1)
    calls = []
    class Session:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_args):
            return None
        async def get(self, *_args):
            return SimpleNamespace(content=QUESTION)
    retriever = SimpleNamespace(scope=SimpleNamespace(corpus_revision=1, embedding_space_hash="space"))
    async def authorize(_cls, _db, **kwargs):
        calls.append(("authorize", kwargs))
        return retriever
    async def prepare(_db, **kwargs):
        calls.append(("prepare", kwargs))
        return PreparedVisualSources({"synthetic": True}, (binding,))
    monkeypatch.setattr(module.KnowledgeRetriever, "authorize", classmethod(authorize))
    monkeypatch.setattr(module, "prepare_visual_sources_v5", prepare)
    async def rehydrate(_db, **kwargs):
        assert kwargs["job"] is job
        return context
    monkeypatch.setattr(module, "rehydrate_question_context", rehydrate)
    class Judge:
        def attempt_scope(self):
            return provider_attempt_scope(self)
        async def judge(self, request):
            calls.append(("judge", request))
            for _ in range(physical_calls):
                current_attempt_scope(self).record_request("source_judgment", retry=False, waited_seconds=0)
            if error is not None:
                raise error
            return response or VisualJudgeResponse(verdict(), "STOP", 100, 25, 30)
    worker = object.__new__(module.RagAnswerWorker)
    worker.settings = SimpleNamespace(rag_source_judge_provider_timeout_seconds=120,
        rag_source_judge_input_cost_per_million_usd=Decimal("0.30"),
        rag_source_judge_output_cost_per_million_usd=Decimal("2.50"))
    worker.session_factory, worker._source_judge = Session, Judge()
    worker._profile_matches = lambda _job: True
    async def claimed(*_args, **_kwargs):
        return job
    async def active(*_args):
        return True
    async def principal(*_args):
        return SimpleNamespace(id=uuid4())
    async def begin(*_args, **kwargs):
        calls.append(("begin", kwargs))
        return uuid4()
    async def finish(*args, **kwargs):
        calls.append(("finish", args[3], args[4], kwargs))
    worker._claimed_job, worker._session_active, worker._current_principal = claimed, active, principal
    worker._begin_stage, worker._finish_stage = begin, finish
    return worker, job, retriever, selected, binding, calls


async def run(worker, selected):
    return await worker._judge_visual_sources(uuid4(), "synthetic-claim",
        QUESTION, (selected,))


@pytest.mark.asyncio
async def test_v8_rechecks_access_and_context_before_render_then_fences_one_id_only_call(monkeypatch):
    worker, job, _, selected, binding, calls = setup(monkeypatch)
    result = await run(worker, selected)
    assert result == ((selected,), False, (binding,))
    assert [row[0] for row in calls] == ["authorize", "prepare", "begin", "judge", "finish"]
    assert calls[0][1]["query"] == "How does the method update weights?"
    assert calls[0][1]["subject_id"] == job.subject_id
    assert calls[2][1]["remote"] is True
    assert calls[2][1]["judge_selections"] == (selected,)
    assert calls[2][1]["judge_pdf_bindings"] == (binding,)
    assert calls[2][1]["judge_question_context"].snapshot.current.message_id == job.question_message_id
    usage = calls[-1][1]
    assert usage.request_count == 1 and usage.retry_count == 0
    assert usage.input_tokens == 100 and usage.output_tokens == 55 and usage.cost_microusd == 168
    assert usage.has_usage and not usage.estimated and calls[-1][3]["uncertain"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("status,label", [("clear", "topic_only"), ("needs_clarification", "uncertain")])
async def test_v8_empty_and_clarification_outcomes_keep_distinct_closed_status(monkeypatch, status, label):
    response = VisualJudgeResponse(verdict(label, status=status), "STOP", 100, 25, 30)
    worker, _, _, selected, binding, calls = setup(monkeypatch, response=response)
    result = await run(worker, selected)
    assert result == ((), status == "needs_clarification", (binding,))
    assert sum(row[0] == "judge" for row in calls) == 1


@pytest.mark.asyncio
async def test_v8_negative_cue_conflict_excludes_page_without_losing_known_usage(monkeypatch):
    raw = json.dumps({"question_status": "clear", "pages": [
        {"id": "S01", "usefulness": "topic_only", "cue_locates": True},
    ]})
    response = VisualJudgeResponse(raw, "STOP", 100, 25, 30)
    worker, _, _, selected, binding, calls = setup(monkeypatch, response=response)
    assert await run(worker, selected) == ((), False, (binding,))
    usage = calls[-1][1]
    assert usage.request_count == 1 and usage.retry_count == 0 and usage.has_usage
    assert usage.output_tokens == 55 and usage.cost_microusd == 168
    assert calls[-1][2] is None and calls[-1][3]["uncertain"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("denial", ["profile", "session", "principal", "question", "corpus", "space"])
async def test_v8_denials_cannot_decrypt_render_or_dispatch(monkeypatch, denial):
    worker, job, retriever, selected, _, calls = setup(monkeypatch)
    async def denied(*_args):
        return False
    async def missing(*_args):
        return None
    if denial == "profile":
        worker._profile_matches = lambda _job: False
    elif denial == "session":
        worker._session_active = denied
    elif denial == "principal":
        worker._current_principal = missing
    elif denial == "question":
        async def wrong_question(*_args):
            return SimpleNamespace(content="Changed current question")
        monkeypatch.setattr(worker.session_factory, "get", wrong_question)
    elif denial == "corpus":
        retriever.scope.corpus_revision = 2
    else:
        retriever.scope.embedding_space_hash = "other-space"
    with pytest.raises((module.AnswerProfileMismatch, module.AnswerAccessRevoked, module.AnswerCorpusChanged)):
        await run(worker, selected)
    assert not any(row[0] in {"prepare", "begin", "judge", "finish"} for row in calls)


@pytest.mark.asyncio
async def test_v8_revocation_after_render_prevents_physical_dispatch(monkeypatch):
    worker, _, _, selected, _, calls = setup(monkeypatch)
    async def revoked(*_args, **_kwargs):
        raise module.AnswerCorpusChanged()
    worker._begin_stage = revoked
    with pytest.raises(module.AnswerCorpusChanged):
        await run(worker, selected)
    assert any(row[0] == "prepare" for row in calls)
    assert not any(row[0] in {"judge", "finish"} for row in calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [
    VisualJudgeResponse(verdict(), "MAX_TOKENS", 100, 25, 2023),
    VisualJudgeResponse(verdict(ids=("unissued",)), "STOP", 100, 25, 30),
    VisualJudgeResponse(verdict(), "STOP", 100, 25, 4096),
    VisualJudgeResponse(verdict(), "STOP", 32769, 25, 30),
])
async def test_v8_invalid_verdict_finish_or_usage_preserves_failure_cost_and_no_retry(monkeypatch, response):
    worker, _, _, selected, _, calls = setup(monkeypatch, response=response)
    with pytest.raises(VisualSourceJudgmentError):
        await run(worker, selected)
    assert [row[0] for row in calls].count("judge") == 1
    assert calls[-1][2] == "invalid_ai_output" and calls[-1][3]["uncertain"] is True
    usage = calls[-1][1]
    assert usage.request_count == 1 and usage.retry_count == 0 and usage.has_usage
    assert usage.output_tokens == response.candidate_tokens + response.thinking_tokens


@pytest.mark.asyncio
async def test_v8_provider_timeout_is_one_attempt_with_unknown_cost(monkeypatch):
    failure = AIProviderError("ai_provider_timeout", "Safe unavailable message", retryable=False,
                              reason_code="transport_timeout")
    worker, _, _, selected, _, calls = setup(monkeypatch, error=failure)
    with pytest.raises(AIProviderError):
        await run(worker, selected)
    usage = calls[-1][1]
    assert usage.request_count == 1 and usage.retry_count == 0 and usage.estimated
    assert not usage.has_usage and calls[-1][3]["uncertain"] is True
    assert calls[-1][3]["failure_reason"] == "transport_timeout"


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, 2])
async def test_v8_judge_must_report_exactly_one_physical_attempt(monkeypatch, count):
    worker, _, _, selected, _, calls = setup(monkeypatch, physical_calls=count)
    with pytest.raises(module.AnswerProfileMismatch):
        await run(worker, selected)
    assert [row[0] for row in calls].count("judge") == 1
    assert calls[-1][1].request_count == count
