"""Strict, bounded embedding providers for Subject Knowledge.

Embedding requests deliberately use a contract separate from structured text
generation.  Only validated vectors and content-free usage/attempt telemetry
leave this module; raw provider responses and credentials never do.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import math
import re
import struct
from typing import Any, Protocol, Sequence, runtime_checkable

import httpx

from app.ai.chunking import estimate_tokens
from app.ai.providers import AIProviderError, ProviderAttemptTelemetry, ProviderUsage
from app.ai.rate_limit import ProviderRateGovernor, ProviderRateLimitExceeded
from app.config import Settings


_FLOAT32_MAX = 3.4028234663852886e38
_MAX_RESPONSE_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class EmbeddingProfile:
    provider: str
    model: str
    api_key_value: str | None
    base_url: str | None
    dimensions: int
    format_version: str
    space_revision: str
    representation: str
    metric: str
    document_task_mode: str
    query_task_mode: str
    batch_size: int
    max_input_tokens: int
    timeout_seconds: float
    max_retries: int
    retry_base_seconds: float
    retry_max_seconds: float
    concurrency: int
    requests_per_minute: int
    input_tokens_per_minute: int
    rate_limit_safety_percent: int
    input_cost_per_million_usd: float
    max_estimated_cost_usd: float
    quota_bucket: str

    @classmethod
    def from_settings(cls, settings: Settings) -> "EmbeddingProfile":
        return cls(
            provider=settings.rag_embedding_provider,
            model=settings.rag_embedding_model,
            api_key_value=settings.rag_embedding_api_key_value,
            base_url=(
                str(settings.rag_embedding_base_url).rstrip("/")
                if settings.rag_embedding_base_url is not None
                else None
            ),
            dimensions=settings.rag_embedding_dimensions,
            format_version=settings.rag_embedding_format_version,
            space_revision=settings.rag_embedding_space_revision,
            representation=settings.rag_embedding_representation,
            metric=settings.rag_embedding_metric,
            document_task_mode=settings.rag_embedding_provider_task_modes[0],
            query_task_mode=settings.rag_embedding_provider_task_modes[1],
            batch_size=settings.rag_embedding_batch_size,
            max_input_tokens=settings.rag_embedding_max_input_tokens,
            timeout_seconds=settings.rag_embedding_provider_timeout_seconds,
            max_retries=settings.rag_embedding_provider_max_retries,
            retry_base_seconds=settings.rag_embedding_retry_base_seconds,
            retry_max_seconds=settings.rag_embedding_retry_max_seconds,
            concurrency=settings.rag_embedding_concurrency,
            requests_per_minute=settings.rag_embedding_requests_per_minute,
            input_tokens_per_minute=settings.rag_embedding_input_tokens_per_minute,
            rate_limit_safety_percent=settings.rag_embedding_rate_limit_safety_percent,
            input_cost_per_million_usd=float(
                settings.rag_embedding_input_cost_per_million_usd
            ),
            max_estimated_cost_usd=float(
                settings.rag_embedding_max_estimated_cost_usd
            ),
            quota_bucket=settings.rag_embedding_quota_bucket,
        )


@dataclass(frozen=True, slots=True)
class EmbeddingResponse:
    vectors: tuple[tuple[float, ...], ...]
    usage: ProviderUsage


@runtime_checkable
class EmbeddingProvider(Protocol):
    async def embed_documents(self, texts: Sequence[str]) -> EmbeddingResponse: ...

    async def embed_query(self, text: str) -> EmbeddingResponse: ...

    def telemetry_snapshot(self) -> ProviderAttemptTelemetry: ...


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


def _normalize_error(exc: Exception) -> AIProviderError:
    if isinstance(exc, AIProviderError):
        return exc
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException)):
        return AIProviderError(
            "embedding_provider_timeout",
            "The embedding provider did not respond before the configured timeout.",
            retryable=True,
        )
    if isinstance(exc, (httpx.NetworkError, httpx.RemoteProtocolError)):
        return AIProviderError(
            "embedding_provider_unavailable",
            "The embedding provider is temporarily unavailable.",
            retryable=True,
        )
    status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
    if status_code is None:
        candidate = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        if isinstance(candidate, int) and not isinstance(candidate, bool):
            status_code = candidate
    if status_code == 400:
        return AIProviderError(
            "embedding_provider_invalid_request",
            "The embedding model rejected the request format.",
            retryable=False,
        )
    if status_code == 401:
        return AIProviderError(
            "embedding_provider_authentication_failed",
            "The embedding provider rejected its credentials.",
            retryable=False,
        )
    if status_code == 403:
        return AIProviderError(
            "embedding_provider_access_denied",
            "The embedding provider denied access.",
            retryable=False,
        )
    if status_code == 404:
        return AIProviderError(
            "embedding_model_unavailable",
            "The configured embedding model is unavailable.",
            retryable=False,
        )
    if status_code == 429:
        return AIProviderError(
            "embedding_provider_rate_limited",
            "The embedding provider rate limit was reached.",
            retryable=True,
            retry_after_seconds=_provider_retry_after(exc),
        )
    if status_code is not None:
        retryable = status_code in {408, 409, 425} or status_code >= 500
        return AIProviderError(
            "embedding_provider_unavailable"
            if retryable
            else "embedding_provider_rejected_request",
            "The embedding provider is temporarily unavailable."
            if retryable
            else "The embedding provider rejected the request.",
            retryable=retryable,
            retry_after_seconds=(
                _provider_retry_after(exc)
                if retryable
                else None
            ),
        )
    return AIProviderError(
        "embedding_provider_unavailable",
        "The embedding provider is temporarily unavailable.",
        retryable=True,
    )


def _float32(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AIProviderError(
            "invalid_embedding_output",
            "The embedding provider returned an invalid vector.",
            retryable=False,
        )
    converted = float(value)
    if not math.isfinite(converted) or abs(converted) > _FLOAT32_MAX:
        raise AIProviderError(
            "invalid_embedding_output",
            "The embedding provider returned an invalid vector.",
            retryable=False,
        )
    try:
        return struct.unpack("!f", struct.pack("!f", converted))[0]
    except (OverflowError, struct.error) as exc:
        raise AIProviderError(
            "invalid_embedding_output",
            "The embedding provider returned an invalid vector.",
            retryable=False,
        ) from exc


class OpenAICompatibleEmbeddingProvider:
    """OpenAI-compatible float embeddings with one retry/rate owner."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
        rate_governor: ProviderRateGovernor | None = None,
        _expected_provider: str = "openai_compatible",
    ) -> None:
        self.profile = EmbeddingProfile.from_settings(settings)
        if self.profile.provider != _expected_provider:
            raise ValueError("The configured embedding provider is not supported")
        if self.profile.format_version != "raw_text_v1":
            raise ValueError("The configured embedding format is not supported")
        if self.profile.representation != "float32" or self.profile.metric != "cosine":
            raise ValueError("The configured embedding representation is not supported")
        if _expected_provider == "openai_compatible" and (
            self.profile.document_task_mode != "shared_input"
            or self.profile.query_task_mode != "shared_input"
        ):
            raise ValueError("The configured embedding task mode is not supported")
        if _expected_provider == "openai_compatible" and self.profile.base_url is None:
            raise ValueError("The OpenAI-compatible embedding provider requires a base URL")
        self._client = client
        self.rate_governor = rate_governor or ProviderRateGovernor.from_profile(
            self.profile
        )
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

    async def embed_documents(self, texts: Sequence[str]) -> EmbeddingResponse:
        return await self._embed(texts, operation="embedding_documents")

    async def embed_query(self, text: str) -> EmbeddingResponse:
        return await self._embed((text,), operation="embedding_query")

    def _validate_inputs(self, texts: Sequence[str]) -> tuple[tuple[str, ...], int]:
        normalized = tuple(texts)
        if not normalized or len(normalized) > self.profile.batch_size:
            raise ValueError("Embedding batch size is outside the configured bounds")
        estimated = 0
        for value in normalized:
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Embedding input must be non-empty text")
            token_count = estimate_tokens(value)
            if token_count > self.profile.max_input_tokens:
                raise ValueError("One embedding input exceeds the configured token bound")
            estimated += token_count
        estimated_cost = (
            estimated * self.profile.input_cost_per_million_usd / 1_000_000
        )
        if estimated_cost > self.profile.max_estimated_cost_usd:
            raise ValueError("Embedding batch exceeds the configured cost bound")
        return normalized, estimated

    async def _embed(
        self, texts: Sequence[str], *, operation: str
    ) -> EmbeddingResponse:
        normalized, estimated_tokens = self._validate_inputs(texts)
        payload = {
            "model": self.profile.model,
            "input": list(normalized),
            "encoding_format": "float",
            "dimensions": self.profile.dimensions,
        }

        async def call_with(client: httpx.AsyncClient) -> EmbeddingResponse:
            headers = {"Content-Type": "application/json"}
            if self.profile.api_key_value:
                headers["Authorization"] = f"Bearer {self.profile.api_key_value}"
            maximum_bytes = min(
                _MAX_RESPONSE_BYTES,
                max(65_536, len(normalized) * self.profile.dimensions * 32 + 65_536),
            )
            async with client.stream(
                "POST",
                f"{self.profile.base_url}/embeddings",
                headers=headers,
                json=payload,
                timeout=self.profile.timeout_seconds,
            ) as response:
                response.raise_for_status()
                length = response.headers.get("Content-Length")
                if length and length.isdigit() and int(length) > maximum_bytes:
                    raise AIProviderError(
                        "invalid_embedding_output",
                        "The embedding provider returned an oversized response.",
                        retryable=False,
                    )
                raw = bytearray()
                async for part in response.aiter_bytes():
                    if len(raw) + len(part) > maximum_bytes:
                        raise AIProviderError(
                            "invalid_embedding_output",
                            "The embedding provider returned an oversized response.",
                            retryable=False,
                        )
                    raw.extend(part)
            try:
                body = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise AIProviderError(
                    "invalid_embedding_output",
                    "The embedding provider returned an invalid response.",
                    retryable=False,
                ) from exc
            return self._validate_response(body, len(normalized), estimated_tokens)

        async def call() -> EmbeddingResponse:
            if self._client is not None:
                return await call_with(self._client)
            async with httpx.AsyncClient(follow_redirects=False) as client:
                return await call_with(client)

        return await self._run_with_retries(
            call,
            estimated_tokens=estimated_tokens,
            operation=operation,
        )

    async def _run_with_retries(
        self,
        call,
        *,
        estimated_tokens: int,
        operation: str,
    ) -> EmbeddingResponse:
        for attempt in range(self.profile.max_retries + 1):
            try:
                reservation = await self.rate_governor.reserve(
                    estimated_tokens, operation=operation, attempt=attempt
                )
                self._request_count += 1
                if attempt:
                    self._retry_count += 1
                self._request_counts_by_stage[operation] = (
                    self._request_counts_by_stage.get(operation, 0) + 1
                )
                self._rate_limit_wait_seconds += reservation.waited_seconds
                async with asyncio.timeout(self.profile.timeout_seconds):
                    result = await call()
                await reservation.commit(result.usage.input_tokens)
                return result
            except asyncio.CancelledError:
                raise
            except ProviderRateLimitExceeded as exc:
                raise AIProviderError(
                    "embedding_provider_request_token_limit",
                    "One embedding request exceeds the configured safe token rate budget.",
                    retryable=False,
                ) from exc
            except Exception as exc:
                normalized_error = _normalize_error(exc)
                if not normalized_error.retryable or attempt >= self.profile.max_retries:
                    raise normalized_error from exc
                delay = max(
                    self.profile.retry_base_seconds,
                    normalized_error.retry_after_seconds or 0,
                )
                if delay > self.profile.retry_max_seconds:
                    raise normalized_error from exc
                self._rate_limit_wait_seconds += delay
                await asyncio.sleep(delay)
        raise AssertionError("embedding retry loop exhausted unexpectedly")

    def _validate_response(
        self, body: object, expected_count: int, estimated_tokens: int
    ) -> EmbeddingResponse:
        if not isinstance(body, dict) or body.get("model") != self.profile.model:
            raise AIProviderError(
                "invalid_embedding_output",
                "The embedding provider returned an incompatible response.",
                retryable=False,
            )
        data = body.get("data")
        if not isinstance(data, list) or len(data) != expected_count:
            raise AIProviderError(
                "invalid_embedding_output",
                "The embedding provider returned the wrong number of vectors.",
                retryable=False,
            )
        vectors: list[tuple[float, ...]] = []
        for expected_index, item in enumerate(data):
            if (
                not isinstance(item, dict)
                or isinstance(item.get("index"), bool)
                or item.get("index") != expected_index
                or not isinstance(item.get("embedding"), list)
                or len(item["embedding"]) != self.profile.dimensions
            ):
                raise AIProviderError(
                    "invalid_embedding_output",
                    "The embedding provider returned an invalid vector order or shape.",
                    retryable=False,
                )
            vector = tuple(_float32(value) for value in item["embedding"])
            norm_squared = math.fsum(value * value for value in vector)
            if not math.isfinite(norm_squared) or norm_squared <= 0:
                raise AIProviderError(
                    "invalid_embedding_output",
                    "The embedding provider returned a vector unsuitable for cosine search.",
                    retryable=False,
                )
            vectors.append(vector)
        raw_usage = body.get("usage")
        actual_tokens: int | None = None
        if isinstance(raw_usage, dict):
            candidate = raw_usage.get("prompt_tokens", raw_usage.get("total_tokens"))
            if isinstance(candidate, int) and not isinstance(candidate, bool) and candidate >= 0:
                actual_tokens = candidate
        return EmbeddingResponse(
            vectors=tuple(vectors),
            usage=ProviderUsage(
                input_tokens=estimated_tokens if actual_tokens is None else actual_tokens,
                output_tokens=0,
                estimated=actual_tokens is None,
            ),
        )


class GeminiEmbeddingProvider(OpenAICompatibleEmbeddingProvider):
    """Native Gemini embeddings with provider retries disabled in the SDK."""

    def __init__(
        self,
        settings: Settings,
        *,
        client=None,
        rate_governor: ProviderRateGovernor | None = None,
    ) -> None:
        super().__init__(
            settings,
            client=None,
            rate_governor=rate_governor,
            _expected_provider="gemini",
        )
        if (
            self.profile.model != "gemini-embedding-001"
            or self.profile.dimensions != 1_536
        ):
            raise ValueError(
                "The Gemini embedding provider requires gemini-embedding-001 with 1536 dimensions"
            )
        if (
            self.profile.document_task_mode != "RETRIEVAL_DOCUMENT"
            or self.profile.query_task_mode != "QUESTION_ANSWERING"
        ):
            raise ValueError("The configured Gemini embedding task modes are not supported")
        if client is None:
            if not self.profile.api_key_value:
                raise ValueError("The Gemini embedding provider requires an API key")
            try:
                from google import genai
                from google.genai import types as genai_types
            except ImportError as exc:  # pragma: no cover - installation defect
                raise ValueError("The Gemini embedding provider dependency is not installed") from exc
            client = genai.Client(
                api_key=self.profile.api_key_value,
                http_options=genai_types.HttpOptions(
                    retry_options=genai_types.HttpRetryOptions(attempts=1)
                ),
            )
        self._client = client

    async def _embed(
        self, texts: Sequence[str], *, operation: str
    ) -> EmbeddingResponse:
        normalized, estimated_tokens = self._validate_inputs(texts)
        task_mode = (
            self.profile.document_task_mode
            if operation == "embedding_documents"
            else self.profile.query_task_mode
        )

        async def call() -> EmbeddingResponse:
            response = await self._client.aio.models.embed_content(
                model=self.profile.model,
                contents=list(normalized),
                config={
                    "task_type": task_mode,
                    "output_dimensionality": self.profile.dimensions,
                },
            )
            embeddings = getattr(response, "embeddings", None)
            if not isinstance(embeddings, list) or len(embeddings) != len(normalized):
                raise AIProviderError(
                    "invalid_embedding_output",
                    "The embedding provider returned the wrong number of vectors.",
                    retryable=False,
                )
            vectors: list[tuple[float, ...]] = []
            for embedding in embeddings:
                values = getattr(embedding, "values", None)
                if not isinstance(values, list) or len(values) != self.profile.dimensions:
                    raise AIProviderError(
                        "invalid_embedding_output",
                        "The embedding provider returned an invalid vector order or shape.",
                        retryable=False,
                    )
                raw_vector = tuple(_float32(value) for value in values)
                norm = math.sqrt(math.fsum(value * value for value in raw_vector))
                if not math.isfinite(norm) or norm <= 0:
                    raise AIProviderError(
                        "invalid_embedding_output",
                        "The embedding provider returned a vector unsuitable for cosine search.",
                        retryable=False,
                    )
                vector = (
                    tuple(_float32(value / norm) for value in raw_vector)
                    if self.profile.dimensions < 3_072
                    else raw_vector
                )
                vectors.append(vector)
            return EmbeddingResponse(
                vectors=tuple(vectors),
                usage=ProviderUsage(
                    input_tokens=estimated_tokens,
                    output_tokens=0,
                    estimated=True,
                ),
            )

        return await self._run_with_retries(
            call,
            estimated_tokens=estimated_tokens,
            operation=operation,
        )


def get_embedding_provider(
    settings: Settings,
    *,
    rate_governor: ProviderRateGovernor | None = None,
) -> EmbeddingProvider:
    if settings.rag_embedding_provider == "gemini":
        return GeminiEmbeddingProvider(settings, rate_governor=rate_governor)
    if settings.rag_embedding_provider == "openai_compatible":
        return OpenAICompatibleEmbeddingProvider(settings, rate_governor=rate_governor)
    raise ValueError("The configured embedding provider is not supported")


__all__ = [
    "EmbeddingProfile",
    "EmbeddingProvider",
    "EmbeddingResponse",
    "GeminiEmbeddingProvider",
    "OpenAICompatibleEmbeddingProvider",
    "get_embedding_provider",
]
