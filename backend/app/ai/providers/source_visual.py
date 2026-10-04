"""One bounded visual source-ID request; no answer generation or automatic retry."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json

import httpx

from app.ai import source_judgment_visual_v2 as contract
from app.ai.providers import (
    AIProviderError, _normalize_provider_error, current_attempt_scope,
    provider_attempt_scope,
)
from app.ai.rate_limit import ProviderRateGovernor, ProviderRateLimitExceeded
from app.config import Settings

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/" + contract.MODEL + ":generateContent"
MAX_HTTP_RESPONSE_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class VisualJudgeResponse:
    raw_json: str | None
    finish_reason: str | None
    input_tokens: int | None
    candidate_tokens: int | None
    thinking_tokens: int | None


def parse_http_response(raw: bytes) -> VisualJudgeResponse:
    """Keep only the final closed verdict and content-free, thinking-inclusive usage."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_HTTP_RESPONSE_BYTES:
        raise contract.VisualSourceJudgmentError("provider_response_oversize")
    try:
        payload = json.loads(raw, object_pairs_hook=contract._unique,
                             parse_constant=contract._reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise contract.VisualSourceJudgmentError("provider_json_invalid") from None
    if type(payload) is not dict or payload.get("modelVersion") != contract.MODEL:
        raise contract.VisualSourceJudgmentError("provider_model_mismatch")
    usage = payload.get("usageMetadata")
    if (type(usage) is not dict or
        any(type(usage.get(k)) is not int or usage[k] < 0
            for k in ("promptTokenCount", "candidatesTokenCount")) or
        usage["promptTokenCount"] <= 0 or
        type(usage.get("thoughtsTokenCount", 0)) is not int or usage.get("thoughtsTokenCount", 0) < 0):
        raise contract.VisualSourceJudgmentError("provider_usage_invalid")
    inp, out, thoughts = usage["promptTokenCount"], usage["candidatesTokenCount"], usage.get("thoughtsTokenCount", 0)
    total = usage.get("totalTokenCount")
    if total is not None and (type(total) is not int or total < inp + out + thoughts):
        raise contract.VisualSourceJudgmentError("provider_usage_invalid")
    thoughts = max(thoughts, total - inp - out if total is not None else thoughts)
    candidates = payload.get("candidates")
    candidate = candidates[0] if type(candidates) is list and len(candidates) == 1 and type(candidates[0]) is dict else {}
    content = candidate.get("content")
    parts = content.get("parts") if type(content) is dict else None
    valid_parts = (type(parts) is list and bool(parts) and all(
        type(part) is dict and type(part.get("text")) is str and
        not set(part) - {"text", "thought", "thoughtSignature"} and
        ("thought" not in part or type(part["thought"]) is bool) for part in parts))
    final = [part["text"] for part in parts if part.get("thought") is not True] if valid_parts else []
    verdict = final[0] if len(final) == 1 and len(final[0].encode("utf-8")) <= contract.MAX_VERDICT_BYTES else None
    finish = candidate.get("finishReason")
    return VisualJudgeResponse(verdict, finish if type(finish) is str else None, inp, out, thoughts)


class GeminiVisualSourceJudge:
    """Worker owns durable dispatch fencing; this adapter owns physical admission."""

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        self.settings, self.transport = settings, transport
        self._semaphore = asyncio.Semaphore(settings.rag_source_judge_concurrency)
        self.governor = ProviderRateGovernor(
            requests_per_minute=settings.rag_source_judge_requests_per_minute,
            input_tokens_per_minute=settings.rag_source_judge_input_tokens_per_minute,
            safety_percent=settings.rag_source_judge_rate_limit_safety_percent,
        )

    def attempt_scope(self):
        return provider_attempt_scope(self)

    async def judge(self, request: dict) -> VisualJudgeResponse:
        if (type(request) is not dict or set(request) != {"model", "store", "systemInstruction", "contents", "generationConfig"}
            or request["model"] != contract.MODEL or request["store"] is not False
            or type(request["generationConfig"]) is not dict
            or request["generationConfig"].get("thinkingConfig") != {"thinkingLevel": "HIGH"}
            or request["generationConfig"].get("maxOutputTokens") != contract.MAX_OUTPUT_TOKENS
            or self.settings.rag_source_judge_model != contract.MODEL
            or self.settings.rag_source_judge_contract_version != contract.CONTRACT_VERSION
            or self.settings.rag_source_judge_thinking_level != "high"
            or self.settings.rag_source_judge_provider_max_retries != 0
            or not 0 < self.settings.rag_source_judge_provider_timeout_seconds <= 60):
            raise contract.VisualSourceJudgmentError("source_profile_invalid")
        body = contract.canonical({k: v for k, v in request.items() if k != "model"})
        if (len(body) > contract.MAX_REQUEST_BYTES or
            contract.estimate_input_tokens(request) > self.settings.rag_source_judge_max_input_tokens):
            raise contract.VisualSourceJudgmentError("request_input_budget")
        key = self.settings.rag_source_judge_api_key_value
        if not isinstance(key, str) or not key:
            raise AIProviderError("ai_provider_not_configured", "The source judge is unavailable.", retryable=False)
        async with self._semaphore:
            try:
                reservation = await self.governor.reserve(
                    self.settings.rag_source_judge_max_input_tokens, operation="source_judgment", attempt=0)
            except ProviderRateLimitExceeded:
                raise AIProviderError("ai_provider_request_token_limit", "The source judge request exceeds its rate limit.", retryable=False) from None
            scope = current_attempt_scope(self)
            if scope is not None:
                scope.record_request("source_judgment", retry=False, waited_seconds=reservation.waited_seconds)
            try:
                async with asyncio.timeout(self.settings.rag_source_judge_provider_timeout_seconds):
                    async with httpx.AsyncClient(
                        transport=self.transport if self.transport is not None else httpx.AsyncHTTPTransport(retries=0),
                        trust_env=False, follow_redirects=False,
                        timeout=self.settings.rag_source_judge_provider_timeout_seconds,
                    ) as client:
                        async with client.stream("POST", ENDPOINT, content=body, headers={
                            "x-goog-api-key": key, "Content-Type": "application/json", "Accept-Encoding": "identity",
                        }) as response:
                            response.raise_for_status()
                            raw = bytearray()
                            async for chunk in response.aiter_bytes(chunk_size=2048):
                                raw.extend(chunk)
                                if len(raw) > MAX_HTTP_RESPONSE_BYTES:
                                    raise contract.VisualSourceJudgmentError("provider_response_oversize")
                            return parse_http_response(bytes(raw))
            except asyncio.CancelledError:
                raise
            except contract.VisualSourceJudgmentError:
                raise
            except (TimeoutError, httpx.TimeoutException):
                raise AIProviderError("ai_provider_timeout", "The source judge timed out.", retryable=False,
                                      reason_code="transport_timeout") from None
            except Exception as error:
                normalized = _normalize_provider_error(error)
                raise AIProviderError(normalized.code, "The source judge is unavailable.", retryable=False,
                                      reason_code=normalized.reason_code) from None
