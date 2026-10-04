"""Build one private, SHA-frozen query-vector packet for the published 11-case roster.

Default invocation is a no-input, no-provider preflight. Execution needs a fresh
UUID4 supplied both on the command line and in the process environment. A
private, exclusive receipt consumes that UUID before any remote request. This
script neither opens the application database nor submits an Ask job.
"""
from __future__ import annotations

import argparse
import asyncio
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from time import perf_counter
from uuid import UUID

from diagnose_source_navigation import (
    PRIVATE_MOUNT, VECTOR_DIMENSIONS, VECTOR_MODEL, VECTOR_SCHEMA,
    Case, Refusal, Scope, _under_private_mount, load_roster, validate_scope,
)


ROSTER_SHA256 = "fca9588c20997424e716a726beac7a64db7bdde1036b18734db28ca4c8cdd730"
APPROVAL_ENV = "CARDCH_PRIVATE_QUERY_VECTOR_APPROVAL_ID"
ENDPOINT = "https://generativelanguage.googleapis.com"
MAX_CASES = 11
MAX_INPUT_TOKENS = 512
MAX_CALL_SECONDS = 30
MAX_TOTAL_SECONDS = 360
MAX_COST_USD = Decimal("0.001")
CONSERVATIVE_INPUT_PRICE = Decimal("0.20")  # Admission assumption, not a tariff.
SCHEMA = "cardchemy_private_query_vector_builder_v1"
SAFE_CODES = frozenset({
    "approval_missing", "approval_used", "invalid_arguments", "roster_invalid",
    "roster_changed", "private_mount_required", "profile_incompatible",
    "scope_invalid", "input_budget_invalid", "output_exists", "provider_failed",
    "provider_envelope_invalid", "provider_attempt_invalid", "packet_invalid",
    "time_budget_exceeded", "embedding_credentials_unavailable",
})


def require_approval(approval_id: str | None) -> UUID:
    try:
        parsed = UUID(approval_id or "")
    except (ValueError, TypeError):
        raise Refusal("approval_missing") from None
    if (parsed.version != 4 or str(parsed) != approval_id
        or os.environ.get(APPROVAL_ENV) != approval_id):
        raise Refusal("approval_missing")
    return parsed


def _private_file(path: Path, *, output: bool = False) -> Path:
    resolved = _under_private_mount(path)
    root = PRIVATE_MOUNT.resolve()
    if resolved.parent != root:
        raise Refusal("private_mount_required")
    if os.name == "posix":
        if root.stat().st_mode & 0o077:
            raise Refusal("private_mount_required")
        if not output and resolved.is_file() and resolved.stat().st_mode & 0o077:
            raise Refusal("private_mount_required")
    return resolved


def consume_approval(approval_id: UUID) -> None:
    root = PRIVATE_MOUNT.resolve()
    receipt = root / (".query-vector-approval-" + hashlib.sha256(
        approval_id.bytes
    ).hexdigest() + ".used")
    try:
        descriptor = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise Refusal("approval_used") from None
    os.close(descriptor)


def bounded_profile(settings, scope: Scope, cases: tuple[Case, ...]):
    from app.ai.chunking import estimate_tokens
    from app.models.knowledge import embedding_space_hash

    if (not settings.rag_embedding_provider_enabled
        or settings.rag_embedding_provider != "gemini"
        or settings.rag_embedding_model != VECTOR_MODEL
        or settings.rag_embedding_endpoint_identity != ENDPOINT
        or settings.rag_embedding_base_url is not None
        or settings.rag_embedding_dimensions != VECTOR_DIMENSIONS
        or settings.rag_embedding_format_version != "raw_text_v1"
        or settings.rag_embedding_representation != "float32"
        or settings.rag_embedding_metric != "cosine"
        or settings.rag_embedding_provider_task_modes
           != ("RETRIEVAL_DOCUMENT", "QUESTION_ANSWERING")
        or embedding_space_hash(settings.rag_embedding_space_identity)
           != scope.embedding_space_hash):
        raise Refusal("profile_incompatible")
    if not settings.rag_embedding_api_key_value:
        raise Refusal("embedding_credentials_unavailable")
    if len(cases) != MAX_CASES:
        raise Refusal("roster_invalid")
    tokens = sum(estimate_tokens(case.question) for case in cases)
    if (not 0 < tokens <= MAX_INPUT_TOKENS
        or Decimal(tokens) * CONSERVATIVE_INPUT_PRICE / 1_000_000 > MAX_COST_USD):
        raise Refusal("input_budget_invalid")
    bounded = settings.model_copy(update={
        "rag_embedding_provider_max_retries": 0,
        "rag_embedding_provider_timeout_seconds": MAX_CALL_SECONDS,
        "rag_embedding_batch_size": 1,
        "rag_embedding_max_input_tokens": MAX_INPUT_TOKENS,
        "rag_embedding_input_cost_per_million_usd": CONSERVATIVE_INPUT_PRICE,
        "rag_embedding_max_estimated_cost_usd": MAX_COST_USD,
    })
    if bounded.rag_embedding_space_identity != settings.rag_embedding_space_identity:
        raise Refusal("profile_incompatible")
    return bounded, tokens


def make_native_query_provider(settings, *, http_client=None):
    """Create the production Gemini adapter with both retry layers disabled."""
    from google import genai
    from google.genai import types
    from app.ai.embeddings import GeminiEmbeddingProvider

    if not settings.rag_embedding_api_key_value:
        raise Refusal("embedding_credentials_unavailable")
    options = dict(
        base_url=ENDPOINT, timeout=MAX_CALL_SECONDS * 1000,
        retry_options=types.HttpRetryOptions(attempts=1),
        async_client_args={"follow_redirects": False, "trust_env": False},
    )
    if http_client is not None:
        options["httpx_async_client"] = http_client
    client = genai.Client(
        vertexai=False, api_key=settings.rag_embedding_api_key_value,
        http_options=types.HttpOptions(**options),
    )
    return GeminiEmbeddingProvider(settings, client=client), client


def _check_provider(provider) -> None:
    profile = provider.profile
    telemetry = provider.telemetry_snapshot()
    if (telemetry.request_count != 0 or telemetry.retry_count != 0
        or profile.provider != "gemini" or profile.model != VECTOR_MODEL
        or profile.query_task_mode != "QUESTION_ANSWERING"
        or profile.dimensions != VECTOR_DIMENSIONS or profile.max_retries != 0
        or profile.batch_size != 1 or profile.timeout_seconds != MAX_CALL_SECONDS
        or profile.max_input_tokens != MAX_INPUT_TOKENS
        or profile.input_cost_per_million_usd != float(CONSERVATIVE_INPUT_PRICE)
        or profile.max_estimated_cost_usd != float(MAX_COST_USD)):
        raise Refusal("provider_envelope_invalid")


def _valid_vector(values: tuple[float, ...]) -> bool:
    if (len(values) != VECTOR_DIMENSIONS
        or any(type(value) not in (int, float) or not math.isfinite(value)
               for value in values)):
        return False
    norm = math.sqrt(math.fsum(value * value for value in values))
    return math.isfinite(norm) and abs(norm - 1.0) <= 0.001


def _write_packet(path: Path, encoded: bytes) -> None:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise Refusal("output_exists") from None
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # Only this invocation's O_EXCL-created file can be removed here.
        try:
            path.unlink()
        except OSError:
            pass
        raise


async def build_packet(cases: tuple[Case, ...], roster_sha256: str, roster_path: Path,
                       output_path: Path, scope: Scope, approval_id: UUID, settings,
                       *, provider_factory=make_native_query_provider) -> dict:
    """Run a single serial attempt per question; stop on the first failure."""
    bounded, tokens = bounded_profile(settings, scope, cases)
    if output_path.exists():
        raise Refusal("output_exists")
    # No approval is consumed until every local bound and output precondition passes.
    consume_approval(approval_id)
    provider = client = None
    started = perf_counter()
    try:
        async with asyncio.timeout(MAX_TOTAL_SECONDS):
            provider, client = provider_factory(bounded)
            _check_provider(provider)
            rows = []
            for case in cases:
                before = provider.telemetry_snapshot()
                if before.request_count != len(rows) or before.retry_count != 0:
                    raise Refusal("provider_attempt_invalid")
                # The adapter times the physical request at 30 seconds. Its
                # rate-governor admission wait may legitimately take longer.
                response = await provider.embed_query(case.question)
                after = provider.telemetry_snapshot()
                if (after.request_count != len(rows) + 1 or after.retry_count != 0
                    or len(response.vectors) != 1 or not _valid_vector(response.vectors[0])):
                    raise Refusal("provider_attempt_invalid")
                rows.append({
                    "case_id": case.case_id,
                    "question_sha256": hashlib.sha256(case.question.encode("utf-8")).hexdigest(),
                    "embedding": list(response.vectors[0]),
                })
            if hashlib.sha256(roster_path.read_bytes()).hexdigest() != roster_sha256:
                raise Refusal("roster_changed")
            packet = {
                "schema": VECTOR_SCHEMA, "roster_sha256": roster_sha256,
                "embedding_space_hash": scope.embedding_space_hash,
                "model": VECTOR_MODEL, "vectors": rows,
            }
            encoded = json.dumps(packet, ensure_ascii=False, separators=(",", ":"),
                                 allow_nan=False).encode("utf-8")
            if len(encoded) > 1_000_000:
                raise Refusal("packet_invalid")
            _write_packet(output_path, encoded)
            return {
                "schema": SCHEMA, "status": "completed_private_packet",
                "packet_sha256": hashlib.sha256(encoded).hexdigest(),
                "case_count": len(rows), "provider_requests": len(rows),
                "retry_count": 0, "estimated_input_tokens": tokens,
                "max_input_tokens": MAX_INPUT_TOKENS,
                "estimated_cost_usd": str(Decimal(tokens) * CONSERVATIVE_INPUT_PRICE / 1_000_000),
                "cost_provenance": "local_estimate_not_provider_receipt",
                "database_reads": 0, "database_writes": 0,
                "answer_requests": 0, "release_gate_passed": False,
                "elapsed_seconds": round(perf_counter() - started, 3),
            }
    except Exception as exc:
        telemetry = provider.telemetry_snapshot() if provider is not None else None
        count = telemetry.request_count if telemetry is not None else 0
        code = exc.args[0] if isinstance(exc, Refusal) and exc.args and exc.args[0] in SAFE_CODES else (
            "time_budget_exceeded" if isinstance(exc, TimeoutError) else "provider_failed"
        )
        return {
            "schema": SCHEMA, "status": "refused_or_failed", "failure_code": code,
            "provider_requests": count, "retry_count": telemetry.retry_count if telemetry else 0,
            "previous_attempt_cost": "unknown" if count else "no_provider_attempt",
            "database_reads": 0, "database_writes": 0, "answer_requests": 0,
            "release_gate_passed": False,
        }
    finally:
        if client is not None:
            try:
                async with asyncio.timeout(max(0.001, MAX_TOTAL_SECONDS - (perf_counter() - started))):
                    await client.aio.aclose()
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--preflight-inputs", action="store_true")
    parser.add_argument("--approval-id")
    parser.add_argument("--roster", type=Path)
    parser.add_argument("--roster-sha256")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--principal-id")
    parser.add_argument("--subject-id")
    parser.add_argument("--corpus-revision", type=int)
    parser.add_argument("--embedding-space-hash")
    parser.add_argument("--document-id", action="append", default=[])
    args = parser.parse_args()
    if args.execute and args.preflight_inputs:
        print(json.dumps({
            "schema": SCHEMA, "status": "refused_or_failed",
            "failure_code": "invalid_arguments", "provider_requests": 0,
            "database_reads": 0, "database_writes": 0, "release_gate_passed": False,
        }, separators=(",", ":")))
        return 1
    if not args.execute and not args.preflight_inputs:
        print(json.dumps({
            "schema": SCHEMA, "status": "preflight_unexecuted",
            "max_provider_requests": MAX_CASES, "max_input_tokens": MAX_INPUT_TOKENS,
            "max_call_seconds": MAX_CALL_SECONDS, "max_total_seconds": MAX_TOTAL_SECONDS,
            "conservative_input_price_per_million_usd": str(CONSERVATIVE_INPUT_PRICE),
            "max_cost_usd": str(MAX_COST_USD), "provider_requests": 0,
            "database_reads": 0, "database_writes": 0, "release_gate_passed": False,
        }, separators=(",", ":")))
        return 0
    try:
        approval_id = require_approval(args.approval_id) if args.execute else None
        if not all((args.roster, args.roster_sha256, args.output, args.principal_id,
                    args.subject_id, args.corpus_revision, args.embedding_space_hash)):
            raise Refusal("invalid_arguments")
        if args.roster_sha256 != ROSTER_SHA256:
            raise Refusal("roster_changed")
        roster_path = _private_file(args.roster)
        output_path = _private_file(args.output, output=True)
        scope = Scope(UUID(args.principal_id), UUID(args.subject_id),
                      args.corpus_revision, args.embedding_space_hash,
                      tuple(sorted((UUID(value) for value in args.document_id), key=str)))
        validate_scope(scope)
        cases, roster_sha256 = load_roster(roster_path, args.roster_sha256)
        if len(cases) != MAX_CASES:
            raise Refusal("roster_invalid")
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from app.config import Settings
        settings = Settings()
        _bounded, tokens = bounded_profile(settings, scope, cases)
        if output_path.exists():
            raise Refusal("output_exists")
        if args.execute:
            report = asyncio.run(build_packet(
                cases, roster_sha256, roster_path, output_path, scope, approval_id, settings,
            ))
        else:
            report = {
                "schema": SCHEMA, "status": "preflight_ready", "case_count": len(cases),
                "estimated_input_tokens": tokens,
                "max_input_tokens": MAX_INPUT_TOKENS,
                "estimated_cost_usd": str(Decimal(tokens) * CONSERVATIVE_INPUT_PRICE / 1_000_000),
                "max_provider_requests": MAX_CASES, "max_call_seconds": MAX_CALL_SECONDS,
                "max_total_seconds": MAX_TOTAL_SECONDS,
                "conservative_input_price_per_million_usd": str(CONSERVATIVE_INPUT_PRICE),
                "max_cost_usd": str(MAX_COST_USD), "provider_requests": 0,
                "database_reads": 0, "database_writes": 0,
                "release_gate_passed": False,
            }
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, Refusal) and exc.args and exc.args[0] in SAFE_CODES else "invalid_arguments"
        report = {
            "schema": SCHEMA, "status": "refused_or_failed", "failure_code": code,
            "provider_requests": 0, "database_reads": 0, "database_writes": 0,
            "release_gate_passed": False,
        }
    print(json.dumps(report, separators=(",", ":")))
    return 0 if report["status"] in ("completed_private_packet", "preflight_ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
