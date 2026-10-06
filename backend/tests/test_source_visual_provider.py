"""Synthetic physical transport limits; no real credential or provider request."""
from types import SimpleNamespace
import json

import httpx
import pytest

from app.ai import source_judgment_visual as contract
from app.ai.providers import AIProviderError, provider_attempt_scope
from app.ai.providers.source_visual import GeminiVisualSourceJudge, parse_http_response
from tests.test_source_judgment_visual import candidates, verdict


def settings():
    return SimpleNamespace(rag_source_judge_concurrency=1, rag_source_judge_requests_per_minute=100,
        rag_source_judge_input_tokens_per_minute=1000000, rag_source_judge_rate_limit_safety_percent=100,
        rag_source_judge_model=contract.MODEL, rag_source_judge_contract_version=contract.CONTRACT_VERSION,
        rag_source_judge_thinking_level="high", rag_source_judge_provider_max_retries=0,
        rag_source_judge_provider_timeout_seconds=60, rag_source_judge_max_input_tokens=32768,
        rag_source_judge_api_key_value="synthetic-test-key")


def response(**changes):
    payload = {"modelVersion": contract.MODEL, "candidates": [{"finishReason": "STOP", "content": {
        "parts": [{"text": "discarded synthetic thought", "thought": True}, {"text": json.dumps(verdict())}]}}],
        "usageMetadata": {"promptTokenCount": 2000, "candidatesTokenCount": 200,
                          "thoughtsTokenCount": 300, "totalTokenCount": 2600}}
    payload.update(changes)
    return payload


def test_usage_accounts_total_and_discards_thought_content():
    parsed = parse_http_response(json.dumps(response()).encode())
    assert parsed.input_tokens == 2000 and parsed.candidate_tokens == 200 and parsed.thinking_tokens == 400
    assert "discarded" not in parsed.raw_json
    assert contract.parse_verdict(parsed.raw_json, ["S01", "S02", "S03", "S04"])["selected_ids"] == []


@pytest.mark.parametrize("mutation", ["model", "boolean_usage", "negative", "total", "duplicate", "oversize"])
def test_invalid_http_metadata_is_never_accepted(mutation):
    payload = response()
    if mutation == "model":
        payload["modelVersion"] = "different-model"
    elif mutation == "boolean_usage":
        payload["usageMetadata"]["promptTokenCount"] = True
    elif mutation == "negative":
        payload["usageMetadata"]["thoughtsTokenCount"] = -1
    elif mutation == "total":
        payload["usageMetadata"]["totalTokenCount"] = 2001
    raw = json.dumps(payload).encode()
    if mutation == "duplicate":
        raw = b'{"modelVersion":"x","modelVersion":"y"}'
    elif mutation == "oversize":
        raw = b" " * 65537
    with pytest.raises(contract.VisualSourceJudgmentError):
        parse_http_response(raw)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 503, 429, 401])
async def test_exactly_one_physical_request_and_no_retry(status):
    calls = []
    async def transport(request):
        calls.append(request)
        return httpx.Response(status, json=response() if status == 200 else {"private": "never retain"})
    judge = GeminiVisualSourceJudge(settings(), transport=httpx.MockTransport(transport))
    wire = contract.build_page_request("Which topic helps?", candidates(), group_id="G01")
    async with provider_attempt_scope(judge) as scope:
        if status == 200:
            parsed = await judge.judge(wire)
            assert parsed.finish_reason == "STOP"
        else:
            with pytest.raises(AIProviderError) as failure:
                await judge.judge(wire)
            assert not failure.value.retryable and "private" not in str(failure.value)
        assert scope.snapshot().request_count == 1 and scope.snapshot().retry_count == 0
    assert len(calls) == 1 and calls[0].method == "POST"
    body = json.loads(calls[0].content)
    assert "model" not in body and body["store"] is False
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "HIGH"}


@pytest.mark.asyncio
async def test_timeout_reports_uncertain_single_attempt_without_retry():
    calls = []
    async def transport(request):
        calls.append(request)
        raise httpx.ReadTimeout("synthetic private transport detail")
    judge = GeminiVisualSourceJudge(settings(), transport=httpx.MockTransport(transport))
    async with provider_attempt_scope(judge) as scope:
        with pytest.raises(AIProviderError, match="timed out") as failure:
            await judge.judge(contract.build_page_request("Which topic helps?", candidates(), group_id="G01"))
        assert failure.value.code == "ai_provider_timeout"
        assert not failure.value.retryable and scope.snapshot().request_count == 1
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_streamed_http_envelope_is_bounded():
    class Huge(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(34):
                yield b" " * 2048
    async def transport(request):
        return httpx.Response(200, stream=Huge())
    judge = GeminiVisualSourceJudge(settings(), transport=httpx.MockTransport(transport))
    with pytest.raises(contract.VisualSourceJudgmentError, match="oversize"):
        await judge.judge(contract.build_page_request("Which topic helps?", candidates(), group_id="G01"))
