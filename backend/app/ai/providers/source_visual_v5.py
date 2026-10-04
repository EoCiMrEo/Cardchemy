"""One versioned v8 source-ID request; historical visual contracts stay unchanged."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import httpx

from app.ai import source_judgment_visual_v5 as contract
from app.ai.providers import AIProviderError, _normalize_provider_error, current_attempt_scope
from app.ai.providers.source_visual import (
    GeminiVisualSourceJudge as HistoricalVisualSourceJudge,
    MAX_HTTP_RESPONSE_BYTES,
    VisualJudgeResponse,
    parse_http_response,
)
from app.ai.rate_limit import ProviderRateLimitExceeded

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/" + contract.MODEL + ":generateContent"


class GeminiVisualSourceJudgeV5(HistoricalVisualSourceJudge):
    """Reuse physical admission accounting, with a separate immutable v5 profile.

    The worker must construct the admission-bound wire and fence durable dispatch
    before calling this adapter. This adapter does not discover conversation
    context, infer an answer, retry, or authorize source access.
    """

    async def judge(
        self, request: dict, *, before_dispatch: Callable[[], Awaitable[None]] | None = None,
    ) -> VisualJudgeResponse:
        if (
            type(request) is not dict
            or set(request) != {"model", "store", "systemInstruction", "contents", "generationConfig"}
            or request["model"] != contract.MODEL
            or request["store"] is not False
            or type(request["generationConfig"]) is not dict
            or request["generationConfig"].get("thinkingConfig") != {"thinkingLevel": "HIGH"}
            or request["generationConfig"].get("maxOutputTokens") != contract.MAX_OUTPUT_TOKENS
            or self.settings.rag_source_judge_model != contract.MODEL
            or self.settings.rag_source_judge_contract_version != contract.CONTRACT_VERSION
            or self.settings.rag_source_judge_thinking_level != "high"
            or self.settings.rag_source_judge_provider_max_retries != 0
            or not 0 < self.settings.rag_source_judge_provider_timeout_seconds <= contract.PROVIDER_TIMEOUT_SECONDS
        ):
            raise contract.VisualSourceJudgmentError("source_profile_invalid")
        body = contract.canonical({key: value for key, value in request.items() if key != "model"})
        if (len(body) > contract.MAX_REQUEST_BYTES or
                contract.estimate_input_tokens(request) > self.settings.rag_source_judge_max_input_tokens):
            raise contract.VisualSourceJudgmentError("request_input_budget")
        key = self.settings.rag_source_judge_api_key_value
        if not isinstance(key, str) or not key:
            raise AIProviderError("ai_provider_not_configured", "The source judge is unavailable.", retryable=False)
        async with self._semaphore:
            try:
                reservation = await self.governor.reserve(
                    self.settings.rag_source_judge_max_input_tokens, operation="source_judgment", attempt=0,
                )
            except ProviderRateLimitExceeded:
                raise AIProviderError("ai_provider_request_token_limit", "The source judge request exceeds its rate limit.",
                                      retryable=False) from None
            # Quota waits may outlive the local admission/source snapshot. The
            # worker rechecks its grants, context and lease after that wait,
            # before physical accounting or any HTTP request. Keep this guard
            # per invocation; a shared mutable callback would cross jobs.
            if before_dispatch is not None:
                await before_dispatch()
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
