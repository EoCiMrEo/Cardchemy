"""Guarded source-only displayed-window probe, with no default DB or provider.

The default CLI is a design preflight only. Execution requires an explicitly
scoped read-only reader, frozen owner-reviewed cases and a freshly approved
envelope. No automatic corpus discovery, root settings file,
answer model, answer verifier, policy switch or database mutation exists here.
Private rows require separate window review and real page-route/browser proof.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
from decimal import Decimal
import hashlib
from html import escape
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from time import perf_counter
from typing import Any, Callable, Protocol, Sequence
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://generativelanguage.googleapis.com"
MODEL = "gemini-embedding-001"
TASK = "QUESTION_ANSWERING"
AUTHORIZATION_ENV = "CARDCH_SOURCE_DISPLAY_APPROVAL"
SCHEMA = "source_only_display_probe_v2"
PROFILE_FIELDS = frozenset({
    "rag_embedding_provider_enabled", "rag_embedding_provider", "rag_embedding_model",
    "rag_embedding_dimensions", "rag_embedding_format_version", "rag_embedding_space_revision",
    "rag_embedding_representation", "rag_embedding_metric", "rag_embedding_document_task_mode",
    "rag_embedding_query_task_mode", "rag_embedding_batch_size", "rag_embedding_max_input_tokens",
    "rag_embedding_provider_timeout_seconds", "rag_embedding_provider_max_retries",
    "rag_embedding_retry_base_seconds", "rag_embedding_retry_max_seconds", "rag_embedding_concurrency",
    "rag_embedding_requests_per_minute", "rag_embedding_input_tokens_per_minute",
    "rag_embedding_rate_limit_safety_percent", "rag_embedding_input_cost_per_million_usd",
    "rag_embedding_max_estimated_cost_usd", "rag_embedding_quota_bucket",
})
SAFE_FAILURES = frozenset({"approval_missing", "approval_consumed", "envelope_invalid",
    "roster_not_frozen", "runtime_changed", "scope_changed", "source_changed",
    "page_unavailable", "provider_contract_invalid", "token_budget_exceeded",
    "cost_budget_exceeded", "probe_failed", "private_output_invalid", "profile_incompatible",
    "explicit_credentials_missing", "private_inputs_invalid", "database_target_invalid"})


class Refusal(RuntimeError):
    """Fixed code only; callers must never print a raw exception."""


@dataclass(frozen=True)
class Case:
    case_id: str
    question: str
    gold_document_id: UUID
    gold_page_number: int
    owner_reviewed_gold: bool
    history: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Scope:
    principal_id: UUID
    subject_id: UUID
    document_ids: tuple[UUID, ...]
    corpus_revision: int
    space_hash: str


@dataclass(frozen=True)
class FrozenRoster:
    cases: tuple[Case, ...]
    scope: Scope
    roster_sha256: str
    runtime_sha256: str


@dataclass(frozen=True)
class Envelope:
    """Proposed ceilings, not authorization or a current provider price claim."""

    approval_id: str
    roster_sha256: str
    runtime_sha256: str
    endpoint: str = ENDPOINT
    model: str = MODEL
    task: str = TASK
    max_requests: int = 25
    max_input_tokens: int = 8192
    max_call_seconds: int = 30
    max_total_seconds: int = 900
    input_price_guard: Decimal = Decimal("0.20")
    max_cost_usd: Decimal = Decimal("0.002")
    profile_sha256: str = ""

    def digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True)
class EmbeddingAttempt:
    vector: tuple[float, ...]
    requests: int
    retries: int
    input_tokens: int


class Reader(Protocol):
    async def authorize(self, query: str) -> Any: ...
    async def retrieve(self, query: str, vector: Sequence[float]) -> Any: ...
    async def neighbors(self, query: str, anchors: Sequence[Any], radius: int,
                        max_chunks: int, max_pages: int, max_tokens: int) -> Sequence[Any]: ...
    async def page_units(self, query: str, chunk_ids: Sequence[UUID],
                         max_pages: int, max_tokens: int) -> dict[UUID, str]: ...
    async def current_pages(self, sources: Sequence[Any], query: str) -> dict[UUID, str]: ...


class QueryProvider(Protocol):
    async def embed_current(self, question: str) -> EmbeddingAttempt: ...
    def attempts(self) -> tuple[int, int]: ...
    async def close(self) -> None: ...


class NativeGeminiQueryProvider:
    """Official native transport with one application/SDK attempt and governor.

    Construction performs no request. Only ``embed_current`` can execute, and
    it reserves request/token/cost budgets before entering the existing adapter.
    The SDK receives only one current question, never source text or history.
    """

    def __init__(self, settings, envelope: Envelope, *, http_client=None):
        from app.ai.embeddings import GeminiEmbeddingProvider
        from google import genai
        from google.genai import types
        if (not settings.rag_enabled or not settings.rag_embedding_provider_enabled
            or settings.rag_embedding_provider != "gemini"
            or settings.rag_embedding_model != envelope.model
            or settings.rag_embedding_endpoint_identity != envelope.endpoint
            or settings.rag_embedding_base_url is not None
            or settings.rag_embedding_dimensions != 1536
            or settings.rag_embedding_format_version != "raw_text_v1"
            or settings.rag_embedding_representation != "float32"
            or settings.rag_embedding_metric != "cosine"
            or settings.rag_embedding_provider_task_modes != ("RETRIEVAL_DOCUMENT", TASK)
            or envelope.input_price_guard < settings.rag_embedding_input_cost_per_million_usd
            or not settings.rag_embedding_quota_bucket):
            raise Refusal("profile_incompatible")
        if settings.rag_embedding_api_key is None:
            raise Refusal("explicit_credentials_missing")
        bounded = settings.model_copy(update={
            "rag_embedding_provider_max_retries": 0,
            "rag_embedding_provider_timeout_seconds": envelope.max_call_seconds,
            "rag_embedding_batch_size": 1,
            "rag_embedding_max_input_tokens": envelope.max_input_tokens,
            "rag_embedding_input_cost_per_million_usd": envelope.input_price_guard,
            "rag_embedding_max_estimated_cost_usd": envelope.max_cost_usd,
        })
        if bounded.rag_embedding_space_identity != settings.rag_embedding_space_identity:
            raise Refusal("profile_incompatible")
        options = dict(base_url=envelope.endpoint, api_version="v1beta",
            timeout=envelope.max_call_seconds * 1000,
            retry_options=types.HttpRetryOptions(attempts=1),
            async_client_args={"follow_redirects": False, "trust_env": False})
        if http_client is not None:
            options["httpx_async_client"] = http_client
        self.client = genai.Client(vertexai=False, api_key=settings.rag_embedding_api_key_value,
                                   http_options=types.HttpOptions(**options))
        self.provider = GeminiEmbeddingProvider(bounded, client=self.client)
        self.envelope = envelope
        self.reserved_requests = 0
        self.reserved_tokens = 0

    async def embed_current(self, question):
        from app.ai.chunking import estimate_tokens
        tokens = estimate_tokens(question)
        if self.reserved_requests + 1 > self.envelope.max_requests:
            raise Refusal("provider_contract_invalid")
        if self.reserved_tokens + tokens > self.envelope.max_input_tokens:
            raise Refusal("token_budget_exceeded")
        if (Decimal(self.reserved_tokens + tokens) * self.envelope.input_price_guard / 1_000_000
            > self.envelope.max_cost_usd):
            raise Refusal("cost_budget_exceeded")
        self.reserved_requests += 1
        self.reserved_tokens += tokens
        async with self.provider.attempt_scope() as attempt:
            response = await self.provider.embed_query(question)
            telemetry = attempt.snapshot()
        if (len(response.vectors) != 1 or telemetry.request_count != 1
            or telemetry.retry_count != 0
            or telemetry.request_counts_by_stage != {"embedding_query": 1}):
            raise Refusal("provider_contract_invalid")
        return EmbeddingAttempt(response.vectors[0], telemetry.request_count,
                                telemetry.retry_count, response.usage.input_tokens)

    def attempts(self):
        snapshot = self.provider.telemetry_snapshot()
        return snapshot.request_count, snapshot.retry_count

    async def close(self):
        await self.client.aio.aclose()


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    default=str, ensure_ascii=False).encode()).hexdigest()


def runtime_fingerprint() -> str:
    """Bind observations to selector, retriever, worker and page mapping source."""

    paths = ("backend/app/ai/source_sufficiency.py", "backend/app/ai/source_structure.py",
             "backend/app/services/knowledge_retrieval.py",
             "backend/app/workers/rag_answer.py", "backend/app/services/rag_answers.py",
             "backend/app/ai/related_evidence.py", "scripts/score_source_first_display.py",
             "scripts/evaluate_private_source_display.py")
    return _digest({name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in paths})


def roster_fingerprint(cases: Sequence[Case], scope: Scope) -> str:
    return _digest({"scope": asdict(scope), "cases": [asdict(case) for case in cases]})


def validate_roster(roster: FrozenRoster) -> None:
    if (not 1 <= len(roster.cases) <= 25
        or len({case.case_id for case in roster.cases}) != len(roster.cases)
        or any(not re.fullmatch(r"[A-Z][0-9]{2}", case.case_id)
               or case.owner_reviewed_gold is not True
               or type(case.gold_page_number) is not int or not 1 <= case.gold_page_number <= 10000
               or not isinstance(case.gold_document_id, UUID)
               or (roster.scope.document_ids and case.gold_document_id not in roster.scope.document_ids)
               or not isinstance(case.question, str) or not case.question.strip()
               or "\x00" in case.question or len(case.question) > 4000
               or len(case.history) > 12
               or any(role != "user" or not isinstance(value, str) or len(value) > 1000
                      for role, value in case.history)
               for case in roster.cases)
        or roster.roster_sha256 != roster_fingerprint(roster.cases, roster.scope)):
        raise Refusal("roster_not_frozen")
    if roster.runtime_sha256 != runtime_fingerprint():
        raise Refusal("runtime_changed")
    if (not isinstance(roster.scope.principal_id, UUID)
        or not isinstance(roster.scope.subject_id, UUID)
        or type(roster.scope.corpus_revision) is not int or roster.scope.corpus_revision < 0
        or not re.fullmatch(r"[0-9a-f]{64}", roster.scope.space_hash)
        or len(roster.scope.document_ids) > 50
        or any(not isinstance(value, UUID) for value in roster.scope.document_ids)
        or len(set(roster.scope.document_ids)) != len(roster.scope.document_ids)):
        raise Refusal("scope_changed")


def validate_envelope(roster: FrozenRoster, envelope: Envelope) -> None:
    if (envelope.endpoint != ENDPOINT or envelope.model != MODEL or envelope.task != TASK
        or envelope.roster_sha256 != roster.roster_sha256
        or envelope.runtime_sha256 != roster.runtime_sha256
        or type(envelope.max_requests) is not int
        or not len(roster.cases) <= envelope.max_requests <= 25
        or type(envelope.max_input_tokens) is not int or not 1 <= envelope.max_input_tokens <= 8192
        or type(envelope.max_call_seconds) is not int or not 1 <= envelope.max_call_seconds <= 30
        or type(envelope.max_total_seconds) is not int or not 1 <= envelope.max_total_seconds <= 900
        or not envelope.input_price_guard.is_finite() or envelope.input_price_guard < Decimal("0.20")
        or not envelope.max_cost_usd.is_finite() or not Decimal("0") < envelope.max_cost_usd <= Decimal("0.01")
        or (envelope.profile_sha256 and not re.fullmatch(r"[0-9a-f]{64}", envelope.profile_sha256))
        or not re.fullmatch(r"[a-zA-Z0-9_-]{16,80}", envelope.approval_id)):
        raise Refusal("envelope_invalid")


def validate_input_budget(roster: FrozenRoster, envelope: Envelope) -> None:
    from app.ai.chunking import estimate_tokens
    planned_tokens = sum(estimate_tokens(case.question) for case in roster.cases)
    if planned_tokens > envelope.max_input_tokens:
        raise Refusal("token_budget_exceeded")
    if Decimal(planned_tokens) * envelope.input_price_guard / 1_000_000 > envelope.max_cost_usd:
        raise Refusal("cost_budget_exceeded")


def _private_directory(path: Path) -> Path:
    root = Path(tempfile.gettempdir()).resolve()
    resolved = path.resolve()
    if (resolved == root or not resolved.is_relative_to(root)
        or any(parent.is_symlink() for parent in (path, *path.parents))):
        raise Refusal("private_output_invalid")
    return resolved


def approval_marker(envelope: Envelope) -> Path:
    """One fixed local marker per approved envelope; output paths cannot replay it."""

    return Path(tempfile.gettempdir()) / "cardchemy-source-display-approvals" / (envelope.digest() + ".once")


def consume_approval(roster: FrozenRoster, envelope: Envelope, marker: Path, token: str | None) -> None:
    """Consume before provider construction; never erase a failed-attempt mark."""

    validate_roster(roster)
    validate_envelope(roster, envelope)
    validate_input_budget(roster, envelope)
    if token != envelope.digest() or os.getenv(AUTHORIZATION_ENV) != token:
        raise Refusal("approval_missing")
    marker = _private_directory(marker)
    if marker != _private_directory(approval_marker(envelope)):
        raise Refusal("envelope_invalid")
    marker.parent.mkdir(mode=0o700, exist_ok=True)
    try:
        with marker.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps({"schema": SCHEMA, "approval_id": envelope.approval_id,
                                     "envelope_sha256": envelope.digest()}))
        marker.chmod(0o600)
    except FileExistsError:
        raise Refusal("approval_consumed") from None


def _scope_matches(scope: Any, expected: Scope) -> bool:
    return all(getattr(scope, key, None) == value for key, value in {
        "principal_id": expected.principal_id, "subject_id": expected.subject_id,
        "document_ids": tuple(sorted(expected.document_ids, key=str)),
        "corpus_revision": expected.corpus_revision, "embedding_space_hash": expected.space_hash,
    }.items())


class ReadOnlyPostgresReader:
    """Explicit scope/session injection; current authorized SQL in every read.

    This opens canonical pages directly for source alignment. It does NOT call
    the saved-job page endpoint and cannot establish ``opened_current_page``.
    """

    def __init__(self, *, session_factory: Callable, scope: Scope):
        self.session_factory, self.expected = session_factory, scope

    async def _bind(self, db, query):
        from sqlalchemy import text
        from app.services.knowledge_retrieval import (
            KnowledgeRetriever, SOURCE_SUFFICIENCY_RETRIEVAL_POLICY,
        )
        from types import SimpleNamespace
        if db.get_bind().dialect.name != "postgresql":
            raise Refusal("scope_changed")
        await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        bound = await KnowledgeRetriever.authorize(db,
            principal=SimpleNamespace(id=self.expected.principal_id),
            subject_id=self.expected.subject_id, query=query,
            document_ids=self.expected.document_ids,
            limit=SOURCE_SUFFICIENCY_RETRIEVAL_POLICY.max_results,
            policy=SOURCE_SUFFICIENCY_RETRIEVAL_POLICY)
        if not _scope_matches(bound.scope, self.expected):
            raise Refusal("scope_changed")
        return bound

    async def authorize(self, query):
        async with self.session_factory() as db:
            bound = await self._bind(db, query)
            await db.rollback()
            return bound.scope

    async def retrieve(self, query, vector):
        async with self.session_factory() as db:
            bound = await self._bind(db, query)
            result = await bound.retrieve(vector, embedding_space_hash=self.expected.space_hash)
            await db.rollback()
            return result

    async def neighbors(self, query, anchors, radius, max_chunks, max_pages, max_tokens):
        async with self.session_factory() as db:
            bound = await self._bind(db, query)
            expanded = await bound.expand_source_neighbors(
                anchors, radius=radius, max_chunks=max_chunks,
                max_pages=max_pages, max_tokens=max_tokens,
            )
            await db.rollback()
            return expanded

    async def page_units(self, query, chunk_ids, max_pages, max_tokens):
        async with self.session_factory() as db:
            bound = await self._bind(db, query)
            pages = await bound.read_current_source_pages(
                chunk_ids, max_pages=max_pages, max_tokens=max_tokens,
            )
            await db.rollback()
            return pages

    async def current_pages(self, sources, query):
        if not sources:
            await self.authorize(query)
            return {}
        async with self.session_factory() as db:
            bound = await self._bind(db, query)
            current = await bound.read_current_sources([source.chunk_id for source in sources])
            by_id = {source.chunk_id: source for source in current}
            fields = ("document_id", "content_revision_id", "index_revision_id", "page_number",
                      "section", "document_title", "content", "token_count",
                      "embedding_space_hash", "corpus_revision")
            if (len(by_id) != len(sources) or any(source.chunk_id not in by_id or any(
                    getattr(source, key) != getattr(by_id[source.chunk_id], key) for key in fields)
                    for source in sources)):
                raise Refusal("source_changed")
            pages = await bound.read_current_source_pages(
                [source.chunk_id for source in sources], max_pages=len(sources), max_tokens=8192,
            )
            if set(pages) != set(by_id):
                raise Refusal("page_unavailable")
            await db.rollback()
            return pages


async def _probe_cases(roster: FrozenRoster, reader: Reader, provider: QueryProvider,
                       envelope: Envelope) -> tuple[list[dict], list[dict], int]:
    from app.ai.source_sufficiency import describe_question, qualify_with_neighbors
    from app.services.rag_answers import locate_page_reference
    from score_source_first_display import inspect_source_window
    validate_roster(roster)
    validate_envelope(roster, envelope)
    validate_input_budget(roster, envelope)
    rows, private, used_tokens = [], [], 0
    for case in roster.cases:
        started = perf_counter()
        scope = await reader.authorize(case.question)
        if not _scope_matches(scope, roster.scope):
            raise Refusal("scope_changed")
        descriptor = describe_question(case.question, case.history)
        local_query = descriptor.local_query
        attempt = None
        chunks = ()
        if local_query is not None:
            async with asyncio.timeout(envelope.max_call_seconds):
                attempt = await provider.embed_current(case.question)
            if (type(attempt.requests) is not int or type(attempt.retries) is not int
                or attempt.requests != 1 or attempt.retries != 0 or type(attempt.input_tokens) is not int
                or attempt.input_tokens < 0 or len(attempt.vector) != 1536
                or not all(math.isfinite(value) for value in attempt.vector)
                or not any(attempt.vector)):
                raise Refusal("provider_contract_invalid")
            used_tokens += attempt.input_tokens
            if used_tokens > envelope.max_input_tokens:
                raise Refusal("token_budget_exceeded")
            if Decimal(used_tokens) * envelope.input_price_guard / 1_000_000 > envelope.max_cost_usd:
                raise Refusal("cost_budget_exceeded")
            result = await reader.retrieve(local_query, attempt.vector)
            if (result.subject_id != roster.scope.subject_id
                or result.corpus_revision != roster.scope.corpus_revision
                or result.embedding_space_hash != roster.scope.space_hash):
                raise Refusal("scope_changed")
            chunks = () if result.insufficient else result.chunks
        assessment, _neighbor_radius = await qualify_with_neighbors(
            descriptor, chunks,
            lambda anchors, radius, max_chunks, max_pages, max_tokens: reader.neighbors(
                local_query, anchors, radius, max_chunks, max_pages, max_tokens,
            ),
            load_pages=lambda chunk_ids, max_pages, max_tokens: reader.page_units(
                local_query, chunk_ids, max_pages, max_tokens,
            ),
        )
        selections = assessment.selections
        pages = await reader.current_pages([item.source for item in selections], local_query or case.question)
        windows, texts = [], []
        for item in selections:
            page = pages.get(item.source.chunk_id)
            if not isinstance(page, str):
                raise Refusal("page_unavailable")
            if item.source_kind not in ("chunk", "canonical_page"):
                raise Refusal("source_changed")
            measured = inspect_source_window(
                chunk_text=item.source.content, start_offset=item.start_offset,
                end_offset=item.end_offset, canonical_page_text=page, source_kind=item.source_kind,
            )
            if item.source_kind == "canonical_page":
                if (page != item.page_content or not measured["exact_source_slice"]
                    or page[item.start_offset:item.end_offset] != item.quote):
                    raise Refusal("source_changed")
                span = (item.start_offset, item.end_offset)
            else:
                if not measured["exact_chunk_slice"]:
                    raise Refusal("source_changed")
                span = locate_page_reference(page, item.quote)
            windows.append({"page_key": _digest([item.source.document_id, item.source.page_number]),
                "chars": measured["chars"], "question_relevant": False,
                "source_kind": item.source_kind,
                "exact_source_slice": measured.get("exact_source_slice", measured["exact_chunk_slice"]),
                "exact_chunk_slice": measured["exact_chunk_slice"],
                "canonical_page_aligned": bool(measured["canonical_page_aligned"] and span is not None),
                "opened_current_page": False,
                "current_authorized": True, "known_irrelevant_u01_pair": False})
            texts.append({"document_id": str(item.source.document_id),
                          "document_title": item.source.document_title, "section": item.source.section,
                          "page_number": item.source.page_number,
                          "source_kind": item.source_kind,
                          "quote": item.quote, "reference_start": span[0] if span else None,
                          "reference_end": span[1] if span else None})
        # New transaction/snapshot reauthorization before emitting a bundle.
        current_pages = await reader.current_pages(
            [item.source for item in selections], local_query or case.question,
        )
        if current_pages != pages:
            raise Refusal("source_changed")
        rows.append({"case_id": case.case_id, "gold_document_key": _digest(case.gold_document_id),
            "gold_page_key": _digest([case.gold_document_id, case.gold_page_number]),
            "gold_page_rank": next((index for index, chunk in enumerate(chunks, 1)
                if chunk.document_id == case.gold_document_id and chunk.page_number == case.gold_page_number), None),
            "owner_reviewed_gold": case.owner_reviewed_gold, "owner_reviewed_windows": False,
            "result_kind": "related_knowledge" if windows else "no_match", "windows": windows,
            "embedding_calls": attempt.requests if attempt else 0, "answer_calls": 0,
            "automatic_retries": attempt.retries if attempt else 0, "answer_assertion_present": False,
            "retrieval_ms": round((perf_counter()-started)*1000, 3)})
        private.append({"case_id": case.case_id, "question": case.question,
                        "history": case.history, "displayed_windows": texts})
    return rows, private, used_tokens


async def run_live(*, roster: FrozenRoster, envelope: Envelope, approval_token: str | None,
                   marker: Path, reader_factory: Callable[[], Reader],
                   provider_factory: Callable[[Envelope], QueryProvider]) -> dict:
    """No client/reader construction before fresh one-shot approval validation.

    Factories must be explicit; there is deliberately no ambient Settings/DB
    loader. The CLI binds the native adapter only after explicit credentials,
    a frozen nonsecret profile and this one-shot approval pass.
    """

    provider = None
    started = perf_counter()
    try:
        consume_approval(roster, envelope, marker, approval_token)
        async with asyncio.timeout(envelope.max_total_seconds):
            reader = reader_factory()
            # Validate every current authorized scope before constructing even
            # an idle SDK client. Gold review remains separate from this check.
            for case in roster.cases:
                if not _scope_matches(await reader.authorize(case.question), roster.scope):
                    raise Refusal("scope_changed")
            provider = provider_factory(envelope)
            rows, private, input_tokens = await _probe_cases(roster, reader, provider, envelope)
            validate_roster(roster)
            requests, retries = provider.attempts()
            if (type(requests) is not int or type(retries) is not int
                or requests != sum(row["embedding_calls"] for row in rows)
                or retries != 0 or requests > envelope.max_requests):
                raise Refusal("provider_contract_invalid")
            return {"schema": SCHEMA, "status": "observed_pending_window_review_and_page_open",
                "observations": rows, "private_review": private, "provider_requests": requests,
                "automatic_retries": retries, "database_writes": 0, "answer_requests": 0,
                "runtime_policy_changed": False, "release_gate_passed": False,
                "history_source": "authored_owner_reviewed_context_not_saved_chat",
                "cost_provenance": "estimated_not_provider_receipt",
                "estimated_input_tokens": input_tokens,
                "estimated_cost_usd": str(Decimal(input_tokens) * envelope.input_price_guard / 1_000_000),
                "elapsed_seconds": round(perf_counter()-started, 3)}
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, Refusal) and exc.args and exc.args[0] in SAFE_FAILURES else "probe_failed"
        try:
            requests, retries = provider.attempts() if provider else (0, 0)
        except Exception:
            requests, retries = None, None
        return {"schema": SCHEMA, "status": "probe_refused_or_failed", "failure_code": code,
                "provider_requests": requests, "automatic_retries": retries,
                "previous_attempt_cost": "unknown" if provider is not None else "no_provider_attempt",
                "database_writes": 0, "answer_requests": 0, "release_gate_passed": False}
    finally:
        if provider is not None:
            try:
                remaining = max(0, envelope.max_total_seconds - (perf_counter()-started))
                async with asyncio.timeout(min(5, remaining)):
                    await provider.close()
            except Exception:
                pass


def write_private_packet(report: dict, directory: Path) -> tuple[Path, Path]:
    """Write private observations/text only to a new owner-private Temp directory."""

    directory = _private_directory(directory)
    directory.mkdir(mode=0o700, exist_ok=False)
    sections = []
    for row in report.get("private_review", []):
        history = "".join(f'<p><strong>Previous user turn:</strong> {escape(content)}</p>'
                          for role, content in row.get("history", []) if role == "user")
        windows = "".join(f'<p>{escape(window.get("document_title", "Source document"))} · '
                          f'Extracted page {window["page_number"]}</p><pre>{escape(window["quote"])}</pre>'
                          for window in row["displayed_windows"])
        sections.append(f'<section><h2>{escape(row["case_id"])}</h2>{history}'
                        f'<p><strong>Current question:</strong> {escape(row["question"])}</p>{windows}</section>')
    html = ('<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="referrer" content="no-referrer"><meta http-equiv="Content-Security-Policy" '
        'content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; form-action &#39;none&#39;; base-uri &#39;none&#39;">'
        '<title>Private displayed-window review</title><style>'
        'body{font:16px/1.5 system-ui;max-width:960px;margin:2rem auto;padding:1rem}'
        'section{border:1px solid #aab;padding:1rem;margin:1rem 0}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef;padding:1rem}</style>'
        '<h1>Actual selector windows</h1>'
        '<p>Relevance is pending owner review. Direct canonical reads do not prove that the '
        'saved-job page route or browser action opened the current page. These checks are pending.</p>'
        + ''.join(sections) + '</html>')
    output = directory / "observations.json"
    packet = directory / "review.html"
    output.write_text(json.dumps(report, ensure_ascii=False, default=str), encoding="utf-8")
    packet.write_text(html, encoding="utf-8")
    for path in (output, packet):
        path.chmod(0o600)
    return output, packet


def aggregate(report: dict) -> dict:
    """The only supported stdout/log projection; no private rows, keys or text."""

    keys = ("schema", "status", "failure_code", "provider_requests", "automatic_retries",
            "database_writes", "answer_requests", "release_gate_passed", "previous_attempt_cost",
            "estimated_cost_usd", "cost_provenance", "estimated_input_tokens", "elapsed_seconds")
    result = {key: report[key] for key in keys if key in report}
    result["observed_cases"] = len(report.get("observations", []))
    result["owner_window_review_pending"] = True
    result["page_route_and_browser_proof_pending"] = True
    return result


def _read_private_json(path: Path) -> Any:
    path = _private_directory(path)
    if not path.is_file() or path.stat().st_size > 512 * 1024:
        raise Refusal("private_inputs_invalid")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, OSError, json.JSONDecodeError):
        raise Refusal("private_inputs_invalid") from None


def load_frozen_inputs(roster_path: Path, envelope_path: Path, profile_path: Path):
    """Private inputs only; no settings/client/database creation during parsing."""

    raw = _read_private_json(roster_path)
    budget = _read_private_json(envelope_path)
    profile = _read_private_json(profile_path)
    try:
        if (set(raw) != {"schema", "frozen", "scope", "cases", "roster_sha256", "runtime_sha256"}
            or raw["schema"] != "source_only_display_roster_v1" or raw["frozen"] is not True
            or set(raw["scope"]) != set(Scope.__dataclass_fields__)
            or set(budget) != set(Envelope.__dataclass_fields__)
            or not isinstance(profile, dict) or set(profile) != PROFILE_FIELDS):
            raise Refusal("private_inputs_invalid")
        scope = Scope(UUID(raw["scope"]["principal_id"]), UUID(raw["scope"]["subject_id"]),
            tuple(UUID(value) for value in raw["scope"]["document_ids"]),
            raw["scope"]["corpus_revision"], raw["scope"]["space_hash"])
        cases = []
        for row in raw["cases"]:
            if set(row) != set(Case.__dataclass_fields__):
                raise Refusal("private_inputs_invalid")
            cases.append(Case(row["case_id"], row["question"], UUID(row["gold_document_id"]),
                row["gold_page_number"], row["owner_reviewed_gold"],
                tuple(tuple(turn) for turn in row["history"])))
        frozen = FrozenRoster(tuple(cases), scope, raw["roster_sha256"], raw["runtime_sha256"])
        budget["input_price_guard"] = Decimal(str(budget["input_price_guard"]))
        budget["max_cost_usd"] = Decimal(str(budget["max_cost_usd"]))
        proposed = Envelope(**budget)
        if proposed.profile_sha256 != _digest(profile):
            raise Refusal("profile_incompatible")
        validate_roster(frozen)
        validate_envelope(frozen, proposed)
        return frozen, proposed, profile
    except Refusal:
        raise
    except (ValueError, TypeError, KeyError, AttributeError):
        raise Refusal("private_inputs_invalid") from None


def explicit_bindings(profile: dict, scope: Scope, proposed: Envelope):
    """Dedicated CLI process settings from explicit inputs, never root .env.

    Database URL and embedding credential must already be injected into this
    worker process. No signing/source keys are read: unused fixed probe values
    satisfy Settings only. Existing validated governor settings are preserved.
    """

    from app import config
    from sqlalchemy.engine import make_url
    if "app.database" in sys.modules:
        # An already-imported global engine may hold ambient root settings.
        # Execute only in a fresh dedicated process with these explicit inputs.
        raise Refusal("database_target_invalid")
    key = os.getenv("RAG_EMBEDDING_API_KEY")
    url = os.getenv("CARDCH_SOURCE_DISPLAY_DATABASE_URL")
    if not key or not url:
        raise Refusal("explicit_credentials_missing")
    parsed = make_url(url)
    local = (parsed.host or "").lower() in {"127.0.0.1", "localhost", "::1"}
    container_local = Path("/.dockerenv").is_file() and parsed.host == "db"
    if parsed.drivername != "postgresql+asyncpg" or not parsed.database or not (local or container_local):
        raise Refusal("database_target_invalid")
    if proposed.profile_sha256 != _digest(profile) or set(profile) != PROFILE_FIELDS:
        raise Refusal("profile_incompatible")
    if any(name not in config.Settings.model_fields for name in profile):
        raise Refusal("profile_incompatible")
    settings = config.Settings(_env_file=None, environment="test", database_url=url,
        secret_key="private-read-only-probe-unused-secret-key-1234567890",
        generation_source_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        rag_enabled=True, rag_ask_enabled=False, rag_embedding_base_url=None,
        rag_embedding_api_key=key, **profile)
    # This isolated diagnostic process must not load root .env when model Base
    # imports app.database. No runtime policy constant or environment is changed.
    config.get_settings = lambda: settings
    from app.models.knowledge import embedding_space_hash
    if embedding_space_hash(settings.rag_embedding_space_identity) != scope.space_hash:
        raise Refusal("profile_incompatible")
    from app.database import async_session_maker, close_database
    reader = ReadOnlyPostgresReader(session_factory=async_session_maker, scope=scope)
    return reader, settings, close_database


async def execute_cli(roster, proposed, profile, approval_token, output_directory):
    # Reject invalid/existing output before the first provider construction.
    output_directory = _private_directory(output_directory)
    if output_directory.exists():
        raise Refusal("private_output_invalid")
    bindings = {}
    started = perf_counter()
    def reader_factory():
        reader, settings, close = explicit_bindings(profile, roster.scope, proposed)
        bindings.update(settings=settings, close=close)
        return reader
    try:
        report = await run_live(roster=roster, envelope=proposed,
            approval_token=approval_token, marker=approval_marker(proposed),
            reader_factory=reader_factory,
            provider_factory=lambda budget: NativeGeminiQueryProvider(bindings["settings"], budget))
        try:
            write_private_packet(report, output_directory)
        except Exception:
            report["status"] = "private_packet_write_failed"
        return aggregate(report)
    finally:
        if "close" in bindings:
            try:
                remaining = max(0, proposed.max_total_seconds-(perf_counter()-started))
                async with asyncio.timeout(min(5, remaining)):
                    await bindings["close"]()
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--roster", type=Path)
    parser.add_argument("--envelope", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--approval-token")
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args()
    if not args.execute and not any((args.roster, args.envelope, args.profile)):
        print(json.dumps({"schema": SCHEMA, "status": "design_preflight_unexecuted",
        "provider_requests": 0, "database_reads": 0, "database_writes": 0,
        "answer_requests": 0, "release_gate_passed": False,
        "live_binding_and_fresh_approval_required": True}, separators=(",", ":")))
        return 0
    execution_entered = False
    try:
        if not all((args.roster, args.envelope, args.profile)):
            raise Refusal("private_inputs_invalid")
        roster, proposed, profile = load_frozen_inputs(args.roster, args.envelope, args.profile)
        sys.path.insert(0, str(ROOT / "backend"))
        validate_input_budget(roster, proposed)
        if args.execute:
            if args.output_directory is None:
                raise Refusal("private_output_invalid")
            execution_entered = True
            report = asyncio.run(execute_cli(roster, proposed, profile, args.approval_token, args.output_directory))
        else:
            report = {"schema": SCHEMA, "status": "frozen_preflight_ready", "cases": len(roster.cases),
                "envelope_sha256": proposed.digest(), "endpoint": proposed.endpoint,
                "model": proposed.model, "task": proposed.task, "max_requests": proposed.max_requests,
                "max_input_tokens": proposed.max_input_tokens, "max_call_seconds": proposed.max_call_seconds,
                "max_total_seconds": proposed.max_total_seconds, "input_price_guard": str(proposed.input_price_guard),
                "max_cost_usd": str(proposed.max_cost_usd), "provider_requests": 0, "database_reads": 0,
                "database_writes": 0, "release_gate_passed": False}
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, Refusal) and exc.args and exc.args[0] in SAFE_FAILURES else "probe_failed"
        report = {"schema": SCHEMA, "status": "probe_refused_or_failed", "failure_code": code,
                  "provider_requests": None if execution_entered else 0, "release_gate_passed": False,
                  "previous_attempt_cost": "unknown" if execution_entered else "no_provider_attempt"}
    print(json.dumps(report, separators=(",", ":")))
    return 0 if report["status"] in {"frozen_preflight_ready", "observed_pending_window_review_and_page_open"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
