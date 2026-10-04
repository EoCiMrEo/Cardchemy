"""Validated, provider-neutral structured generation adapters.

Provider SDK objects and HTTP response bodies never escape this module. The
pipeline receives only a strictly validated Pydantic value, normalized token
usage, and bounded public errors.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import re
from typing import Any, AsyncIterator, Generic, Literal, Protocol, TypeVar, runtime_checkable

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.chunking import estimate_tokens as estimate_text_tokens
from app.ai.gemini_catalog import GeminiCatalogError, resolve_text_model
from app.ai.rate_limit import ProviderRateGovernor, ProviderRateLimitExceeded
from app.config import Settings


T = TypeVar("T", bound=BaseModel)
_SCHEMA_NAME = re.compile(r"[^A-Za-z0-9_-]+")


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    input_tokens: int
    output_tokens: int
    estimated: bool
    cached_input_tokens: int = 0

    def __post_init__(self) -> None:
        if (
            self.input_tokens < 0
            or self.output_tokens < 0
            or self.cached_input_tokens < 0
        ):
            raise ValueError("provider token usage cannot be negative")


@dataclass(frozen=True, slots=True)
class ProviderAttemptTelemetry:
    request_count: int
    retry_count: int
    rate_limit_wait_seconds: float
    request_counts_by_stage: dict[str, int]


class ProviderAttemptScope:
    """One invocation's physical attempts, isolated from concurrent jobs."""

    def __init__(self, owner: object) -> None:
        self._owner = owner
        self._request_count = 0
        self._retry_count = 0
        self._wait_seconds = 0.0
        self._by_stage: dict[str, int] = {}

    def record_request(self, operation: str, *, retry: bool, waited_seconds: float) -> None:
        self._request_count += 1
        self._retry_count += int(retry)
        self._wait_seconds += waited_seconds
        self._by_stage[operation] = self._by_stage.get(operation, 0) + 1

    def record_retry_wait(self, seconds: float) -> None:
        self._wait_seconds += seconds

    def snapshot(self) -> ProviderAttemptTelemetry:
        return ProviderAttemptTelemetry(
            request_count=self._request_count,
            retry_count=self._retry_count,
            rate_limit_wait_seconds=self._wait_seconds,
            request_counts_by_stage=dict(self._by_stage),
        )


_CURRENT_ATTEMPT_SCOPE: ContextVar[ProviderAttemptScope | None] = ContextVar(
    "current_provider_attempt_scope", default=None
)


def current_attempt_scope(owner: object) -> ProviderAttemptScope | None:
    scope = _CURRENT_ATTEMPT_SCOPE.get()
    return scope if scope is not None and scope._owner is owner else None


@asynccontextmanager
async def provider_attempt_scope(owner: object) -> AsyncIterator[ProviderAttemptScope]:
    scope = ProviderAttemptScope(owner)
    token = _CURRENT_ATTEMPT_SCOPE.set(scope)
    try:
        yield scope
    finally:
        _CURRENT_ATTEMPT_SCOPE.reset(token)


@dataclass(frozen=True, slots=True)
class ProviderResponse(Generic[T]):
    data: T
    usage: ProviderUsage
    finish_reason: str | None = None


class AIProviderError(RuntimeError):
    """A bounded provider failure safe to persist or return to a client."""

    def __init__(
        self,
        code: str,
        safe_message: str,
        *,
        retryable: bool,
        retry_after_seconds: float | None = None,
        reason_code: str | None = None,
        usage: ProviderUsage | None = None,
        finish_reason: str | None = None,
    ) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        # These fixed metadata fields contain no provider response, prompt or
        # exception text. A returned response can carry billable usage even
        # when strict local parsing rejects its output.
        self.reason_code = reason_code
        self.usage = usage
        self.finish_reason = finish_reason


class AIProviderConfigurationError(AIProviderError):
    def __init__(self, safe_message: str = "The AI provider is not configured.") -> None:
        super().__init__("ai_provider_not_configured", safe_message, retryable=False)


class AIProviderInvalidOutputError(AIProviderError):
    def __init__(
        self,
        reason_code: str = "schema_invalid",
        *,
        usage: ProviderUsage | None = None,
        finish_reason: str | None = None,
    ) -> None:
        super().__init__(
            "invalid_ai_output",
            "The AI provider returned output that did not match the required schema.",
            retryable=False,
            reason_code=reason_code,
            usage=usage,
            finish_reason=finish_reason,
        )


@runtime_checkable
class AIProvider(Protocol):
    async def generate_structured(
        self,
        *,
        response_model: type[T],
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
        operation: str,
    ) -> ProviderResponse[T]: ...


def _estimate_tokens(value: str) -> int:
    """Conservative provider-independent fallback when usage is unavailable."""

    return estimate_text_tokens(value)


def _closed_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Return an object schema with unknown keys forbidden at every level."""

    schema = deepcopy(model.model_json_schema())

    def close(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" or "properties" in node:
                node.setdefault("additionalProperties", False)
            for child in node.values():
                close(child)
        elif isinstance(node, list):
            for child in node:
                close(child)

    close(schema)
    return schema


def _gemini_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Return a minimal schema accepted by Gemini structured output.

    The application keeps the full strict Pydantic contract authoritative after
    generation. The provider receives only structural keywords and inline
    object definitions to avoid model-specific schema-complexity rejections.
    """

    source = deepcopy(model.model_json_schema())
    definitions = source.get("$defs", {})

    def simplify(node: Any) -> Any:
        if not isinstance(node, dict):
            return node
        reference = node.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/$defs/"):
            name = reference.removeprefix("#/$defs/")
            target = definitions.get(name)
            if isinstance(target, dict):
                return simplify(target)

        result: dict[str, Any] = {}
        # The app keeps formats such as UUID and string constraints in its
        # strict Pydantic validator.  The smaller wire subset avoids passing
        # model-specific format annotations that Gemini may reject with 400.
        for keyword in ("type", "enum"):
            if keyword in node:
                result[keyword] = deepcopy(node[keyword])
        if "properties" in node:
            result["properties"] = {
                name: simplify(child)
                for name, child in node["properties"].items()
            }
        if "required" in node:
            result["required"] = list(node["required"])
        if "items" in node:
            result["items"] = simplify(node["items"])
        if "anyOf" in node:
            result["anyOf"] = [simplify(child) for child in node["anyOf"]]
        return result

    return simplify(source)


def _strict_validate(response_model: type[T], raw_text: str) -> T:
    try:
        json.loads(raw_text)
    except (ValueError, TypeError) as exc:
        raise AIProviderInvalidOutputError("json_invalid") from exc
    try:
        return response_model.model_validate_json(raw_text, strict=True)
    except (ValidationError, ValueError, TypeError) as exc:
        raise AIProviderInvalidOutputError("schema_invalid") from exc


_FINISH_REASONS = frozenset({
    "FINISH_REASON_UNSPECIFIED", "STOP", "MAX_TOKENS", "SAFETY",
    "RECITATION", "LANGUAGE", "OTHER", "BLOCKLIST",
    "PROHIBITED_CONTENT", "SPII", "MALFORMED_FUNCTION_CALL",
    "IMAGE_SAFETY", "UNEXPECTED_TOOL_CALL", "IMAGE_PROHIBITED_CONTENT",
    "NO_IMAGE", "IMAGE_RECITATION", "IMAGE_OTHER",
})
_BLOCKED_FINISH_REASONS = frozenset({
    "SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII",
    "IMAGE_SAFETY", "IMAGE_PROHIBITED_CONTENT", "IMAGE_RECITATION",
})


def _safe_finish_reason(response: Any) -> str | None:
    candidates = getattr(response, "candidates", None)
    if not candidates:
        return None
    reason = getattr(candidates[0], "finish_reason", None)
    if reason is None:
        return None
    name = getattr(reason, "name", None)
    if not isinstance(name, str):
        name = str(reason)
        if "." in name:
            name = name.rsplit(".", 1)[-1]
    return name if name in _FINISH_REASONS else "OTHER"


def _read_usage(
    *,
    input_tokens: Any,
    output_tokens: Any,
    cached_input_tokens: Any = None,
    system_prompt: str,
    user_prompt: str,
    output_text: str,
) -> ProviderUsage:
    input_actual = isinstance(input_tokens, int) and input_tokens >= 0
    output_actual = isinstance(output_tokens, int) and output_tokens >= 0
    cached_actual = (
        isinstance(cached_input_tokens, int) and cached_input_tokens >= 0
    )
    return ProviderUsage(
        input_tokens=(
            input_tokens
            if input_actual
            else _estimate_tokens(f"{system_prompt}\n{user_prompt}")
        ),
        output_tokens=output_tokens if output_actual else _estimate_tokens(output_text),
        estimated=not (input_actual and output_actual),
        cached_input_tokens=cached_input_tokens if cached_actual else 0,
    )


def _parse_retry_after(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(0.0, float(value))
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    try:
        return max(0.0, float(stripped))
    except ValueError:
        pass
    duration = re.fullmatch(r"(\d+(?:\.\d+)?)s", stripped, re.IGNORECASE)
    if duration:
        return max(0.0, float(duration.group(1)))
    try:
        parsed = parsedate_to_datetime(stripped)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (parsed - datetime.now(timezone.utc)).total_seconds())


def _retry_hint_from_details(value: Any) -> float | None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = re.sub(r"[^a-z]", "", str(key).casefold())
            if normalized_key in {"retryafter", "retrydelay"}:
                parsed = _parse_retry_after(child)
                if parsed is not None:
                    return parsed
        for child in value.values():
            parsed = _retry_hint_from_details(child)
            if parsed is not None:
                return parsed
    elif isinstance(value, list):
        for child in value:
            parsed = _retry_hint_from_details(child)
            if parsed is not None:
                return parsed
    return None


def _provider_retry_after(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is not None:
        try:
            parsed = _parse_retry_after(headers.get("Retry-After"))
        except (AttributeError, TypeError):
            parsed = None
        if parsed is not None:
            return parsed
    return _retry_hint_from_details(getattr(exc, "details", None))


def _normalize_provider_error(exc: Exception) -> AIProviderError:
    if isinstance(exc, AIProviderError):
        return exc
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException)):
        return AIProviderError(
            "ai_provider_timeout",
            "The AI provider did not respond before the configured timeout.",
            retryable=True,
            reason_code="transport_timeout",
        )
    if isinstance(exc, httpx.RemoteProtocolError):
        return AIProviderError(
            "ai_provider_unavailable",
            "The AI provider is temporarily unavailable.",
            retryable=True,
            reason_code="transport_protocol",
        )
    if isinstance(exc, httpx.NetworkError):
        return AIProviderError(
            "ai_provider_unavailable",
            "The AI provider is temporarily unavailable.",
            retryable=True,
            reason_code="transport_network",
        )

    status_code: int | None = None
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
    else:
        candidate = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        if isinstance(candidate, int):
            status_code = candidate

    if status_code == 400:
        return AIProviderError(
            "ai_provider_invalid_request",
            "The configured AI model rejected the request format. Check the selected model compatibility.",
            retryable=False,
            reason_code="http_invalid_request",
        )
    if status_code == 401:
        return AIProviderError(
            "ai_provider_authentication_failed",
            "The AI provider rejected its credentials. Update the provider API key.",
            retryable=False,
            reason_code="http_authentication",
        )
    if status_code == 403:
        return AIProviderError(
            "ai_provider_access_denied",
            "The AI provider denied access. Check API-key restrictions and project permissions.",
            retryable=False,
            reason_code="http_access_denied",
        )
    if status_code == 404:
        return AIProviderError(
            "ai_model_unavailable",
            "The configured AI model is unavailable. Update the selected model and create a new job.",
            retryable=False,
            reason_code="http_model_missing",
        )
    if status_code == 429:
        return AIProviderError(
            "ai_provider_rate_limited",
            "The AI provider rate limit was reached. Wait before retrying the job.",
            retryable=True,
            retry_after_seconds=_provider_retry_after(exc),
            reason_code="http_rate_limited",
        )
    if status_code is not None:
        retryable = status_code in {408, 409, 425} or status_code >= 500
        return AIProviderError(
            "ai_provider_unavailable" if retryable else "ai_provider_rejected_request",
            (
                "The AI provider is temporarily unavailable."
                if retryable
                else "The AI provider rejected the generation request."
            ),
            retryable=retryable,
            retry_after_seconds=_provider_retry_after(exc) if retryable else None,
            reason_code=(
                "http_server_error" if status_code >= 500 else
                "http_transient" if retryable else "http_rejected"
            ),
        )

    return AIProviderError(
        "ai_provider_unavailable",
        "The AI provider is temporarily unavailable.",
        retryable=True,
        reason_code="sdk_unclassified",
    )


class _RetryingProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        rate_governor: ProviderRateGovernor | None = None,
        role: Literal["flashcard", "rag_answer"] = "flashcard",
    ) -> None:
        self.settings = settings
        self.profile = settings.text_provider_profile(role)
        self.rate_governor = rate_governor or ProviderRateGovernor.from_profile(self.profile)
        self._request_count = 0
        self._retry_count = 0
        self._rate_limit_wait_seconds = 0.0
        self._request_counts_by_stage: dict[str, int] = {}

    def telemetry_snapshot(self) -> ProviderAttemptTelemetry:
        return ProviderAttemptTelemetry(
            request_count=self._request_count,
            retry_count=self._retry_count,
            rate_limit_wait_seconds=self._rate_limit_wait_seconds,
            request_counts_by_stage=dict(self._request_counts_by_stage),
        )

    def attempt_scope(self):
        return provider_attempt_scope(self)

    async def _run_with_retries(
        self,
        call: Any,
        *,
        estimated_input_tokens: int,
        operation: str,
    ) -> ProviderResponse[Any]:
        for attempt in range(self.profile.max_retries + 1):
            reservation = None
            try:
                reservation = await self.rate_governor.reserve(
                    estimated_input_tokens,
                    operation=operation,
                    attempt=attempt,
                )
                self._request_count += 1
                if attempt > 0:
                    self._retry_count += 1
                self._rate_limit_wait_seconds += float(
                    getattr(reservation, "waited_seconds", 0.0)
                )
                self._request_counts_by_stage[operation] = (
                    self._request_counts_by_stage.get(operation, 0) + 1
                )
                scope = current_attempt_scope(self)
                if scope is not None:
                    scope.record_request(
                        operation,
                        retry=attempt > 0,
                        waited_seconds=float(getattr(reservation, "waited_seconds", 0.0)),
                    )
                async with asyncio.timeout(self.profile.timeout_seconds):
                    response = await call()
                await reservation.commit(response.usage.input_tokens)
                return response
            except asyncio.CancelledError:
                raise
            except ProviderRateLimitExceeded as exc:
                raise AIProviderError(
                    "ai_provider_request_token_limit",
                    "One AI request exceeds the configured safe input-token rate budget.",
                    retryable=False,
                ) from exc
            except Exception as exc:
                normalized = _normalize_provider_error(exc)
                if reservation is not None and normalized.usage is not None:
                    await reservation.commit(normalized.usage.input_tokens)
                if not normalized.retryable or attempt >= self.profile.max_retries:
                    raise normalized from exc
                delay = max(
                    self.profile.retry_base_seconds,
                    normalized.retry_after_seconds or 0,
                )
                if delay > self.profile.retry_max_seconds:
                    # Never retry before a provider's explicit hint. If that
                    # hint exceeds our bounded wait, retain the retryable error
                    # for a later manual job retry instead.
                    raise normalized from exc
                self._rate_limit_wait_seconds += delay
                scope = current_attempt_scope(self)
                if scope is not None:
                    scope.record_retry_wait(delay)
                await asyncio.sleep(delay)
        raise AssertionError("provider retry loop exhausted unexpectedly")


class GeminiProvider(_RetryingProvider):
    def __init__(
        self,
        settings: Settings,
        *,
        client: Any | None = None,
        rate_governor: ProviderRateGovernor | None = None,
        role: Literal["flashcard", "rag_answer"] = "flashcard",
    ) -> None:
        super().__init__(settings, rate_governor=rate_governor, role=role)
        if self.profile.provider != "gemini":
            raise AIProviderConfigurationError(
                "The selected profile is not configured for the Gemini provider."
            )
        prefix = "flashcard_ai" if role == "flashcard" else "rag_ai"
        try:
            self.capability = resolve_text_model(
                self.profile.model,
                role=role,
                thinking_level=self.profile.thinking_level,
                context_window_tokens=getattr(settings, f"{prefix}_context_window_tokens"),
                max_output_tokens=self.profile.max_output_tokens,
            )
        except GeminiCatalogError as exc:
            raise AIProviderError(exc.code, str(exc), retryable=False) from exc
        api_key = self.profile.api_key_value
        if client is None:
            if not api_key:
                raise AIProviderConfigurationError()
            try:
                from google import genai
                from google.genai import types as genai_types
            except ImportError as exc:  # pragma: no cover - installation defect
                raise AIProviderConfigurationError(
                    "The Gemini provider dependency is not installed."
                ) from exc
            client = genai.Client(
                api_key=api_key,
                http_options=genai_types.HttpOptions(
                    retry_options=genai_types.HttpRetryOptions(attempts=1)
                ),
            )
        self._client = client

    async def generate_structured(
        self,
        *,
        response_model: type[T],
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
        operation: str,
    ) -> ProviderResponse[T]:
        output_limit = min(max_output_tokens, self.profile.max_output_tokens)
        if output_limit < 1:
            raise AIProviderConfigurationError("The AI output-token limit must be positive.")
        if output_limit > self.capability.max_output_tokens:
            raise AIProviderError(
                "ai_model_output_incompatible",
                "The requested output budget exceeds the selected Gemini model limit.",
                retryable=False,
            )
        schema = _gemini_schema(response_model)
        if schema.get("type") != "object":
            raise AIProviderError(
                "ai_model_schema_incompatible",
                "The response schema is incompatible with the selected Gemini model policy.",
                retryable=False,
            )

        async def call() -> ProviderResponse[T]:
            config: dict[str, Any] = {
                "system_instruction": system_prompt,
                "max_output_tokens": output_limit,
                "response_mime_type": "application/json",
                "response_json_schema": schema,
            }
            # The catalog pins provider-default sampling and validated thinking
            # for each Gemini 3 selection; the Settings temperature is retained
            # only for historical configuration readback.
            config["thinking_config"] = {"thinking_level": self.profile.thinking_level}
            response = await self._client.aio.models.generate_content(
                model=self.profile.model,
                contents=user_prompt,
                config=config,
            )
            finish_reason = _safe_finish_reason(response)
            try:
                output_text = getattr(response, "text", None)
            except Exception:
                output_text = None
            usage_metadata = getattr(response, "usage_metadata", None)
            candidate_tokens = getattr(
                usage_metadata, "candidates_token_count", None
            )
            thought_tokens = getattr(usage_metadata, "thoughts_token_count", None)
            if isinstance(candidate_tokens, int) and candidate_tokens >= 0:
                # Gemini bills thinking tokens as output. Keep the durable output
                # and cost envelope complete even though they are not visible in
                # the structured response body.
                output_tokens = candidate_tokens + (
                    thought_tokens
                    if isinstance(thought_tokens, int) and thought_tokens >= 0
                    else 0
                )
            else:
                output_tokens = None
            usage = _read_usage(
                input_tokens=getattr(usage_metadata, "prompt_token_count", None),
                output_tokens=output_tokens,
                cached_input_tokens=getattr(
                    usage_metadata, "cached_content_token_count", None
                ),
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_text=output_text if isinstance(output_text, str) else "",
            )
            if finish_reason is not None and finish_reason != "STOP":
                raise AIProviderInvalidOutputError(
                    "output_blocked" if finish_reason in _BLOCKED_FINISH_REASONS
                    else "output_unfinished",
                    usage=usage,
                    finish_reason=finish_reason,
                )
            if not isinstance(output_text, str) or not output_text.strip():
                raise AIProviderInvalidOutputError(
                    "output_empty", usage=usage, finish_reason=finish_reason
                )
            try:
                parsed = _strict_validate(response_model, output_text)
            except AIProviderInvalidOutputError as exc:
                raise AIProviderInvalidOutputError(
                    exc.reason_code or "schema_invalid",
                    usage=usage,
                    finish_reason=finish_reason,
                ) from exc
            return ProviderResponse(data=parsed, usage=usage, finish_reason=finish_reason)

        return await self._run_with_retries(
            call,
            estimated_input_tokens=_estimate_tokens(f"{system_prompt}\n{user_prompt}"),
            operation=operation,
        )


class OpenAICompatibleProvider(_RetryingProvider):
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
        rate_governor: ProviderRateGovernor | None = None,
        role: Literal["flashcard", "rag_answer"] = "flashcard",
    ) -> None:
        super().__init__(settings, rate_governor=rate_governor, role=role)
        if self.profile.base_url is None:
            raise AIProviderConfigurationError(
                "The selected profile requires a base URL for the OpenAI-compatible provider."
            )
        self._base_url = str(self.profile.base_url).rstrip("/")
        self._client = client

    async def generate_structured(
        self,
        *,
        response_model: type[T],
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
        operation: str,
    ) -> ProviderResponse[T]:
        output_limit = min(max_output_tokens, self.profile.max_output_tokens)
        if output_limit < 1:
            raise AIProviderConfigurationError("The AI output-token limit must be positive.")
        schema_name = _SCHEMA_NAME.sub("_", operation).strip("_")[:64] or "structured_output"
        payload = {
            "model": self.profile.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.profile.temperature,
            "max_tokens": output_limit,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": _closed_schema(response_model),
                },
            },
        }

        async def call_with(client: httpx.AsyncClient) -> ProviderResponse[T]:
            headers = {"Content-Type": "application/json"}
            if self.profile.api_key_value:
                headers["Authorization"] = f"Bearer {self.profile.api_key_value}"
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.profile.timeout_seconds,
            )
            response.raise_for_status()
            maximum_response_bytes = max(65_536, output_limit * 16)
            if len(response.content) > maximum_response_bytes:
                raise AIProviderInvalidOutputError()
            try:
                body = response.json()
                output_text = body["choices"][0]["message"]["content"]
            except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
                raise AIProviderInvalidOutputError() from exc
            if not isinstance(output_text, str) or not output_text.strip():
                raise AIProviderInvalidOutputError()
            parsed = _strict_validate(response_model, output_text)
            raw_usage = body.get("usage") or {}
            usage = _read_usage(
                input_tokens=raw_usage.get("prompt_tokens"),
                output_tokens=raw_usage.get("completion_tokens"),
                cached_input_tokens=(
                    raw_usage.get("prompt_tokens_details") or {}
                ).get("cached_tokens"),
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_text=output_text,
            )
            return ProviderResponse(data=parsed, usage=usage)

        async def call() -> ProviderResponse[T]:
            if self._client is not None:
                return await call_with(self._client)
            async with httpx.AsyncClient(follow_redirects=False) as client:
                return await call_with(client)

        return await self._run_with_retries(
            call,
            estimated_input_tokens=_estimate_tokens(f"{system_prompt}\n{user_prompt}"),
            operation=operation,
        )


def get_ai_provider(
    settings: Settings,
    *,
    rate_governor: ProviderRateGovernor | None = None,
    role: Literal["flashcard", "rag_answer"] = "flashcard",
) -> AIProvider:
    profile = settings.text_provider_profile(role)
    if profile.provider == "gemini":
        return GeminiProvider(settings, rate_governor=rate_governor, role=role)
    raise AIProviderConfigurationError("The configured AI provider is not supported.")


__all__ = [
    "AIProvider",
    "AIProviderConfigurationError",
    "AIProviderError",
    "AIProviderInvalidOutputError",
    "GeminiProvider",
    "OpenAICompatibleProvider",
    "ProviderAttemptTelemetry",
    "ProviderAttemptScope",
    "ProviderResponse",
    "ProviderUsage",
    "current_attempt_scope",
    "get_ai_provider",
    "provider_attempt_scope",
]
