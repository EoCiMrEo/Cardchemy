"""Invented v3 transport contracts; never read Settings, keys or live sources."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from uuid import uuid4

import httpx
import pytest

from app.ai import source_judgment_visual as contract
from app.ai.providers import AIProviderError, provider_attempt_scope
from app.ai.providers.source_visual import GeminiVisualSourceJudge
from app.ai.source_navigation_context import resolve_subject_context
from tests.test_source_visual_provider import settings as old_settings, response
from tests.test_source_judgment_visual import candidates


def settings():
    configured = old_settings()
    configured.rag_source_judge_contract_version = contract.CONTRACT_VERSION
    configured.rag_source_judge_provider_timeout_seconds = 120
    return configured


def wire(anchored=False):
    now = datetime.now(timezone.utc)
    owner, thread, subject = uuid4(), uuid4(), uuid4()
    question = "How does it work?" if anchored else "What is Bluebird encoding?"
    prior = "Explain Bluebird encoding."
    def message(text, created):
        return contract.AdmissionUserMessage(uuid4(), owner, thread, subject,
            sha256(text.encode()).hexdigest(), created, now + timedelta(days=1))
    snapshot = contract.SubjectAdmissionSnapshot(message(question, now),
        message(prior, now - timedelta(seconds=1)) if anchored else None,
        1, "a" * 64, now, not anchored)
    anchor = resolve_subject_context(question, (("user", prior),), raw_navigation_query=None).anchor if anchored else None
    return contract.build_request(question, candidates(), group_id="G01", snapshot=snapshot,
        checked_at=now, raw_navigation_query=None if anchored else question,
        preceding_question=prior if anchored else None, anchor=anchor)


@pytest.mark.parametrize("anchored", [False, True])
@pytest.mark.parametrize("status", [200, 503, 429, 401])
async def test_one_current_physical_attempt_and_closed_wire(anchored, status):
    attempts = []
    async def transport(request):
        attempts.append(request)
        return httpx.Response(status, json=response() if status == 200 else {"private": "discard"})
    judge = GeminiVisualSourceJudge(settings(), transport=httpx.MockTransport(transport))
    request = wire(anchored)
    async with provider_attempt_scope(judge) as scope:
        if status == 200:
            actual = await judge.judge(request)
            assert actual.finish_reason == "STOP"
            assert contract.parse_verdict(actual.raw_json, ["S01", "S02", "S03", "S04"])["schema_version"] == contract.CONTRACT_VERSION
        else:
            with pytest.raises(AIProviderError) as failure:
                await judge.judge(request)
            assert failure.value.retryable is False
        assert scope.snapshot().request_count == 1 and scope.snapshot().retry_count == 0
    assert len(attempts) == 1 and attempts[0].method == "POST"
    payload = json.loads(attempts[0].content)
    assert "model" not in payload and payload["store"] is False
    first = json.loads(payload["contents"][0]["parts"][0]["text"])
    assert ("referent_context" in first) is anchored
    assert "Explain Bluebird encoding." not in payload["contents"][0]["parts"][0]["text"]


@pytest.mark.parametrize("field,value", [
    ("rag_source_judge_contract_version", "visual_source_id_v2"),
    ("rag_source_judge_provider_timeout_seconds", 121),
    ("rag_source_judge_provider_timeout_seconds", 0),
    ("rag_source_judge_provider_max_retries", 1),
    ("rag_source_judge_thinking_level", "low"),
    ("rag_source_judge_model", "another-model"),
])
async def test_stale_or_out_of_envelope_profile_never_dispatches(field, value):
    configured = settings()
    setattr(configured, field, value)
    async def transport(request):
        pytest.fail("invalid profile dispatched")
    judge = GeminiVisualSourceJudge(configured, transport=httpx.MockTransport(transport))
    with pytest.raises(contract.VisualSourceJudgmentError, match="source_profile_invalid"):
        await judge.judge(wire())




async def test_timeout_never_retries_and_omits_internal_details():
    attempts = []
    async def transport(request):
        attempts.append(request)
        raise httpx.ReadTimeout("synthetic private detail")
    judge = GeminiVisualSourceJudge(settings(), transport=httpx.MockTransport(transport))
    async with provider_attempt_scope(judge) as scope:
        with pytest.raises(AIProviderError) as failure:
            await judge.judge(wire(True))
        assert failure.value.code == "ai_provider_timeout" and failure.value.retryable is False
        assert "synthetic private" not in str(failure.value)
        assert scope.snapshot().request_count == 1 and scope.snapshot().retry_count == 0
    assert len(attempts) == 1


async def test_stream_limit_stops_once():
    class Oversize(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(34):
                yield b" " * 2048
    attempts = []
    async def transport(request):
        attempts.append(request)
        return httpx.Response(200, stream=Oversize())
    judge = GeminiVisualSourceJudge(settings(), transport=httpx.MockTransport(transport))
    with pytest.raises(contract.VisualSourceJudgmentError, match="oversize"):
        await judge.judge(wire())
    assert len(attempts) == 1


async def test_revoked_dispatch_guard_runs_after_quota_wait_before_physical_attempt():
    from types import SimpleNamespace
    order = []

    class RevokedContext(RuntimeError):
        pass

    async def reserve(*args, **kwargs):
        order.append("quota_wait_completed")
        return SimpleNamespace(waited_seconds=0)

    async def check():
        assert order == ["quota_wait_completed"]
        order.append("context_rechecked")
        raise RevokedContext("context_changed")

    async def transport(request):
        pytest.fail("revoked context dispatched")

    judge = GeminiVisualSourceJudge(settings(), transport=httpx.MockTransport(transport))
    judge.governor.reserve = reserve
    async with provider_attempt_scope(judge) as scope:
        with pytest.raises(RevokedContext):
            await judge.judge(wire(True), before_dispatch=check)
        assert scope.snapshot().request_count == 0
    assert order == ["quota_wait_completed", "context_rechecked"]


async def test_each_request_owns_its_dispatch_guard():
    import asyncio
    seen = []

    async def transport(request):
        seen.append("http")
        return httpx.Response(200, json=response())

    judge = GeminiVisualSourceJudge(settings(), transport=httpx.MockTransport(transport))

    async def run(label):
        async def guard():
            seen.append(label)
        async with provider_attempt_scope(judge) as scope:
            await judge.judge(wire(), before_dispatch=guard)
            assert scope.snapshot().request_count == 1

    await asyncio.gather(run("first"), run("second"))
    assert seen.count("first") == seen.count("second") == 1
    assert seen.count("http") == 2
    assert not hasattr(judge, "before_dispatch")
