"""Validated, provider-neutral structured generation adapters.

Provider SDK objects and HTTP response bodies never escape this module. The
pipeline receives only a strictly validated Pydantic value, normalized token
usage, and bounded public errors.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
import json
import math
import random
import re
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings


T = TypeVar("T", bound=BaseModel)
_SCHEMA_NAME = re.compile(r"[^A-Za-z0-9_-]+")


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    input_tokens: int
    output_tokens: int
    estimated: bool

    def __post_init__(self) -> None:
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("provider token usage cannot be negative")


@dataclass(frozen=True, slots=True)
class ProviderResponse(Generic[T]):
    data: T
    usage: ProviderUsage


class AIProviderError(RuntimeError):
    """A bounded provider failure safe to persist or return to a client."""

    def __init__(self, code: str, safe_message: str, *, retryable: bool) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.retryable = retryable


class AIProviderConfigurationError(AIProviderError):
    def __init__(self, safe_message: str = "The AI provider is not configured.") -> None:
        super().__init__("ai_provider_not_configured", safe_message, retryable=False)


class AIProviderInvalidOutputError(AIProviderError):
    def __init__(self) -> None:
        super().__init__(
            "invalid_ai_output",
            "The AI provider returned output that did not match the required schema.",
            retryable=False,
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

    if not value:
        return 0
    return max(1, math.ceil(len(value.encode("utf-8")) / 3))


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


def _strict_validate(response_model: type[T], raw_text: str) -> T:
    try:
        return response_model.model_validate_json(raw_text, strict=True)
    except (ValidationError, ValueError, TypeError) as exc:
        raise AIProviderInvalidOutputError() from exc


def _read_usage(
    *,
    input_tokens: Any,
    output_tokens: Any,
    system_prompt: str,
    user_prompt: str,
    output_text: str,
) -> ProviderUsage:
    input_actual = isinstance(input_tokens, int) and input_tokens >= 0
    output_actual = isinstance(output_tokens, int) and output_tokens >= 0
    return ProviderUsage(
        input_tokens=(
            input_tokens
            if input_actual
            else _estimate_tokens(f"{system_prompt}\n{user_prompt}")
        ),
        output_tokens=output_tokens if output_actual else _estimate_tokens(output_text),
        estimated=not (input_actual and output_actual),
    )


def _normalize_provider_error(exc: Exception) -> AIProviderError:
    if isinstance(exc, AIProviderError):
        return exc
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException)):
        return AIProviderError(
            "ai_provider_timeout",
            "The AI provider did not respond before the configured timeout.",
            retryable=True,
        )
    if isinstance(exc, (httpx.NetworkError, httpx.RemoteProtocolError)):
        return AIProviderError(
            "ai_provider_unavailable",
            "The AI provider is temporarily unavailable.",
            retryable=True,
        )

    status_code: int | None = None
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
    else:
        candidate = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        if isinstance(candidate, int):
            status_code = candidate

    if status_code is not None:
        retryable = status_code in {408, 409, 425, 429} or status_code >= 500
        return AIProviderError(
            "ai_provider_unavailable" if retryable else "ai_provider_rejected_request",
            (
                "The AI provider is temporarily unavailable."
                if retryable
                else "The AI provider rejected the generation request."
            ),
            retryable=retryable,
        )

    return AIProviderError(
        "ai_provider_unavailable",
        "The AI provider is temporarily unavailable.",
        retryable=True,
    )


class _RetryingProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def _run_with_retries(self, call: Any) -> ProviderResponse[Any]:
        for attempt in range(self.settings.ai_provider_max_retries + 1):
            try:
                async with asyncio.timeout(self.settings.ai_provider_timeout_seconds):
                    return await call()
            except Exception as exc:
                normalized = _normalize_provider_error(exc)
                if not normalized.retryable or attempt >= self.settings.ai_provider_max_retries:
                    raise normalized from exc
                cap = min(
                    self.settings.ai_retry_max_seconds,
                    self.settings.ai_retry_base_seconds * (2**attempt),
                )
                await asyncio.sleep(random.uniform(0, cap))
        raise AssertionError("provider retry loop exhausted unexpectedly")


class GeminiProvider(_RetryingProvider):
    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
        super().__init__(settings)
        api_key = settings.ai_api_key_value
        if client is None:
            if not api_key:
                raise AIProviderConfigurationError()
            try:
                from google import genai
            except ImportError as exc:  # pragma: no cover - installation defect
                raise AIProviderConfigurationError(
                    "The Gemini provider dependency is not installed."
                ) from exc
            client = genai.Client(api_key=api_key)
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
        del operation  # Used for accounting by the caller; Gemini needs no request label.
        output_limit = min(max_output_tokens, self.settings.ai_max_output_tokens)
        if output_limit < 1:
            raise AIProviderConfigurationError("The AI output-token limit must be positive.")

        async def call() -> ProviderResponse[T]:
            response = await self._client.aio.models.generate_content(
                model=self.settings.ai_model,
                contents=user_prompt,
                config={
                    "system_instruction": system_prompt,
                    "temperature": self.settings.ai_temperature,
                    "max_output_tokens": output_limit,
                    "response_mime_type": "application/json",
                    "response_json_schema": _closed_schema(response_model),
                },
            )
            output_text = getattr(response, "text", None)
            if not isinstance(output_text, str) or not output_text.strip():
                raise AIProviderInvalidOutputError()
            parsed = _strict_validate(response_model, output_text)
            usage_metadata = getattr(response, "usage_metadata", None)
            usage = _read_usage(
                input_tokens=getattr(usage_metadata, "prompt_token_count", None),
                output_tokens=getattr(usage_metadata, "candidates_token_count", None),
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_text=output_text,
            )
            return ProviderResponse(data=parsed, usage=usage)

        return await self._run_with_retries(call)


class OpenAICompatibleProvider(_RetryingProvider):
    def __init__(self, settings: Settings, *, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(settings)
        if settings.ai_base_url is None:
            raise AIProviderConfigurationError(
                "AI_BASE_URL is required for the OpenAI-compatible provider."
            )
        self._base_url = str(settings.ai_base_url).rstrip("/")
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
        output_limit = min(max_output_tokens, self.settings.ai_max_output_tokens)
        if output_limit < 1:
            raise AIProviderConfigurationError("The AI output-token limit must be positive.")
        schema_name = _SCHEMA_NAME.sub("_", operation).strip("_")[:64] or "structured_output"
        payload = {
            "model": self.settings.ai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.settings.ai_temperature,
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
            if self.settings.ai_api_key_value:
                headers["Authorization"] = f"Bearer {self.settings.ai_api_key_value}"
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.settings.ai_provider_timeout_seconds,
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

        return await self._run_with_retries(call)


def get_ai_provider(settings: Settings) -> AIProvider:
    if settings.ai_provider == "gemini":
        return GeminiProvider(settings)
    if settings.ai_provider == "openai_compatible":
        return OpenAICompatibleProvider(settings)
    raise AIProviderConfigurationError("The configured AI provider is not supported.")


__all__ = [
    "AIProvider",
    "AIProviderConfigurationError",
    "AIProviderError",
    "AIProviderInvalidOutputError",
    "GeminiProvider",
    "OpenAICompatibleProvider",
    "ProviderResponse",
    "ProviderUsage",
    "get_ai_provider",
]
