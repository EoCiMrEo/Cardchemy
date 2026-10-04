"""Opt-in, read-only comparison of one published BLEU Ask question.

This operator diagnostic keeps private question, Knowledge and model text in
memory. It emits only fixed labels, counts, ranks and usage. The execution
switch and two charge/privacy acknowledgements are required before constructing
providers; importing this module or running its keyless tests spends nothing.
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import sys
from typing import AsyncIterator
from uuid import UUID


BACKEND_ROOT = (
    Path("/app") if (Path("/app") / "app").is_dir()
    else Path(__file__).resolve().parents[1] / "backend"
)
sys.path.insert(0, str(BACKEND_ROOT))

try:
    from sqlalchemy import select, text
    from app.ai.answering import (
        GroundedAnswerOutput, normalize_text, render_answer_prompts,
        validate_grounded_answer,
    )
    from app.ai.chunking import estimate_tokens
    from app.ai.embeddings import get_embedding_provider
    from app.ai.gemini_catalog import CATALOG_VERSION, SCHEMA_POLICY_VERSION
    from app.ai.local_support import LOCAL_SUPPORT_POLICY_VERSION, create_local_support_verifier
    from app.ai.providers import AIProviderError, get_ai_provider, provider_attempt_scope
    from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION, Settings, get_settings
    from app.database import async_session_maker, close_database
    from app.models.knowledge import embedding_space_hash
    from app.models.rag import RagAnswerJob, RagMessage
    from app.models.user import User
    from app.services.knowledge_retrieval import EXACT_V1_POLICY, KnowledgeRetriever
    from app.time_utils import utcnow
except Exception:
    raise SystemExit("Private Ask diagnostic dependencies unavailable") from None


ANSWER_MODEL = "gemini-3.6-flash"
EMBEDDING_MODEL = "gemini-embedding-001"
ENDPOINT = "https://generativelanguage.googleapis.com"
QUESTION_KIND = "bleu_expansion"
MAX_EMBEDDING_TOKENS = 512
MAX_ANSWER_INPUT_TOKENS = 12_000
MAX_ANSWER_OUTPUT_TOKENS = 1_024
MAX_COST_USD = Decimal("0.04")
MAX_SECONDS = 60
PRICE_INPUT = Decimal("1.50")
PRICE_OUTPUT = Decimal("9.00")
PRICE_EMBEDDING = Decimal("0.15")
_ANCHOR = "bilingual evaluation understudy"
_CANDIDATE_POLICY = replace(
    EXACT_V1_POLICY,
    policy_id="diagnostic_bounded_or_section_v1",
    lexical_max_terms=12,
    lexical_join_or=True,
    lexical_include_section=True,
)
_SAFE_PROVIDER_CODES = frozenset({
    "ai_provider_timeout", "ai_provider_unavailable", "ai_provider_rate_limited",
    "ai_provider_invalid_request", "ai_provider_authentication_failed",
    "ai_provider_access_denied", "ai_model_unavailable", "ai_provider_rejected_request",
    "ai_provider_request_token_limit", "ai_model_output_incompatible",
    "ai_model_schema_incompatible", "invalid_ai_output",
    "embedding_provider_timeout", "embedding_provider_unavailable",
    "embedding_provider_rate_limited", "embedding_provider_invalid_request",
    "embedding_provider_authentication_failed", "embedding_provider_access_denied",
    "embedding_model_unavailable", "embedding_provider_rejected_request",
    "embedding_provider_request_token_limit", "invalid_embedding_output",
})
_SAFE_PROVIDER_REASON_CODES = frozenset({
    "transport_timeout", "transport_protocol", "transport_network",
    "http_invalid_request", "http_authentication", "http_access_denied",
    "http_model_missing", "http_rate_limited", "http_server_error",
    "http_transient", "http_rejected", "sdk_unclassified",
    "output_empty", "output_blocked", "output_unfinished",
    "json_invalid", "schema_invalid",
})
_SAFE_SERVER_HTTP_STATUSES = frozenset({500, 502, 503, 504})
_SAFE_REASONS = frozenset({
    "supported", "missing_evidence", "entailment_rejected",
    "question_relevance_rejected", "equivalence_rejected", "contradiction_detected",
})
_SAFE_FINISH = frozenset({
    "FINISH_REASON_UNSPECIFIED", "STOP", "MAX_TOKENS", "SAFETY", "RECITATION",
    "LANGUAGE", "OTHER", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII",
    "MALFORMED_FUNCTION_CALL", "IMAGE_SAFETY", "UNEXPECTED_TOOL_CALL",
    "IMAGE_PROHIBITED_CONTENT", "NO_IMAGE", "IMAGE_RECITATION", "IMAGE_OTHER",
})


class DiagnosticRefusal(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class SelectedCase:
    job_id: UUID
    question: str
    user_id: UUID
    subject_id: UUID
    document_ids: tuple[UUID, ...]
    corpus_revision: int
    embedding_space_hash: str


def require_live_envelope(settings: Settings, *, execute: bool) -> Settings:
    if (
        not execute
        or os.getenv("RUN_PRIVATE_ASK_COMPARISON") != "1"
        or os.getenv("PRIVATE_ASK_COMPARISON_AUTHORIZED") != "I_ACCEPT_PROVIDER_CHARGES_AND_PRIVATE_EVIDENCE"
    ):
        raise DiagnosticRefusal("authorization_missing")
    # ADR-022 retires answer-generation comparisons, including paid entry points.
    raise DiagnosticRefusal("answer_generation_retired")


def admitted_cost(embedding_tokens: int, answer_input_tokens: int) -> Decimal:
    if not 0 <= embedding_tokens <= MAX_EMBEDDING_TOKENS:
        raise DiagnosticRefusal("embedding_token_limit")
    if not 0 <= answer_input_tokens <= MAX_ANSWER_INPUT_TOKENS:
        raise DiagnosticRefusal("answer_input_limit")
    cost = (
        Decimal(embedding_tokens) * PRICE_EMBEDDING
        + Decimal(answer_input_tokens) * PRICE_INPUT
        + Decimal(MAX_ANSWER_OUTPUT_TOKENS) * PRICE_OUTPUT
    ) / Decimal(1_000_000)
    if cost > MAX_COST_USD:
        raise DiagnosticRefusal("cost_limit")
    return cost


@asynccontextmanager
async def read_only_session(factory) -> AsyncIterator[object]:
    async with factory() as db:
        await db.execute(text("SET TRANSACTION READ ONLY"))
        try:
            yield db
        finally:
            await db.rollback()


def _check_snapshot(job: RagAnswerJob, settings: Settings) -> None:
    if (
        job.status != "completed" or job.support_rejection_count < 1
        or job.answer_policy_version != ASK_REQUIRED_RELEASE_POLICY_VERSION
        or job.support_policy_version != LOCAL_SUPPORT_POLICY_VERSION
        or job.retrieval_policy != EXACT_V1_POLICY.policy_id
        or job.ai_provider != settings.rag_ai_provider
        or job.ai_base_url != settings.rag_ai_endpoint_identity
        or job.ai_model != ANSWER_MODEL
        or job.ai_catalog_version != CATALOG_VERSION
        or job.ai_schema_policy_version != SCHEMA_POLICY_VERSION
        or job.embedding_space_hash != embedding_space_hash(settings.rag_embedding_space_identity)
    ):
        raise DiagnosticRefusal("snapshot_mismatch")


async def select_case(settings: Settings, *, job_id: UUID | None, operator_latest: bool) -> SelectedCase:
    async with read_only_session(async_session_maker) as db:
        if job_id is None:
            if not operator_latest:
                raise DiagnosticRefusal("job_selection_required")
            matching_bleu_job = (
                RagAnswerJob.status == "completed",
                RagAnswerJob.support_rejection_count > 0,
                RagAnswerJob.answer_policy_version == ASK_REQUIRED_RELEASE_POLICY_VERSION,
                RagAnswerJob.support_policy_version == LOCAL_SUPPORT_POLICY_VERSION,
                RagAnswerJob.ai_model == ANSWER_MODEL,
                RagMessage.role == "user",
                RagMessage.content.ilike("%BLEU%"),
                RagMessage.content.ilike("%stand%"),
            )
            matching_owners = (await db.scalars(
                select(RagAnswerJob.user_id)
                .join(RagMessage, RagMessage.id == RagAnswerJob.question_message_id)
                .where(*matching_bleu_job)
                .distinct()
                .limit(2)
            )).all()
            if len(matching_owners) > 1:
                raise DiagnosticRefusal("owner_selection_ambiguous")
            if not matching_owners:
                raise DiagnosticRefusal("job_unavailable")
            selected_id = await db.scalar(
                select(RagAnswerJob.id)
                .join(RagMessage, RagMessage.id == RagAnswerJob.question_message_id)
                .where(*matching_bleu_job, RagAnswerJob.user_id == matching_owners[0])
                .order_by(RagAnswerJob.created_at.desc(), RagAnswerJob.id.desc())
                .limit(1)
            )
            if selected_id is None:
                raise DiagnosticRefusal("job_unavailable")
            job_id = selected_id
        job = await db.get(RagAnswerJob, job_id)
        if job is None:
            raise DiagnosticRefusal("job_unavailable")
        _check_snapshot(job, settings)
        question = await db.get(RagMessage, job.question_message_id)
        if (
            question is None or question.role != "user" or question.thread_id != job.thread_id
            or question.user_id != job.user_id or question.expires_at <= utcnow()
            or "bleu" not in question.content.casefold()
            or "stand" not in question.content.casefold()
        ):
            raise DiagnosticRefusal("question_mismatch")
        try:
            document_ids = tuple(UUID(value) for value in job.document_ids)
        except (TypeError, ValueError, AttributeError):
            raise DiagnosticRefusal("snapshot_mismatch") from None
        case = SelectedCase(
            job_id=job.id, question=question.content,
            user_id=job.user_id, subject_id=job.subject_id,
            document_ids=document_ids, corpus_revision=job.corpus_revision,
            embedding_space_hash=job.embedding_space_hash,
        )
        await _authorized_retriever(db, case, EXACT_V1_POLICY)
        return case


async def _authorized_retriever(db, case: SelectedCase, policy):
    user = await db.get(User, case.user_id)
    if user is None:
        raise DiagnosticRefusal("access_revoked")
    retriever = await KnowledgeRetriever.authorize(
        db, principal=user, subject_id=case.subject_id, query=case.question,
        document_ids=case.document_ids, limit=policy.max_results, policy=policy,
    )
    if (
        retriever.scope.corpus_revision != case.corpus_revision
        or retriever.scope.embedding_space_hash != case.embedding_space_hash
    ):
        raise DiagnosticRefusal("corpus_changed")
    return retriever


async def retrieve_comparison(case: SelectedCase, vector) -> dict[str, object]:
    async with read_only_session(async_session_maker) as db:
        results = {}
        for label, policy in (("baseline", EXACT_V1_POLICY), ("candidate", _CANDIDATE_POLICY)):
            retriever = await _authorized_retriever(db, case, policy)
            results[label] = await retriever.retrieve(
                vector, embedding_space_hash=case.embedding_space_hash
            )
        return results


async def reauthorize_sources(case: SelectedCase, chunks) -> None:
    async with read_only_session(async_session_maker) as db:
        retriever = await _authorized_retriever(db, case, EXACT_V1_POLICY)
        sources = await retriever.read_current_sources([chunk.chunk_id for chunk in chunks])
        by_id = {source.chunk_id: source for source in sources}
        if len(by_id) != len(chunks) or any(
            (source := by_id.get(chunk.chunk_id)) is None
            or source.content != chunk.content
            or source.content_revision_id != chunk.content_revision_id
            or source.index_revision_id != chunk.index_revision_id
            for chunk in chunks
        ):
            raise DiagnosticRefusal("source_changed")


def _retrieval_summary(result) -> dict[str, object]:
    return {
        "policy": result.policy_id,
        "selected_count": len(result.chunks),
        "anchor_present": any(_ANCHOR in chunk.content.casefold() for chunk in result.chunks),
        "ranks": [
            {
                "vector": chunk.vector_rank if type(chunk.vector_rank) is int and 1 <= chunk.vector_rank <= 20 else None,
                "lexical": chunk.lexical_rank if type(chunk.lexical_rank) is int and 1 <= chunk.lexical_rank <= 20 else None,
            }
            for chunk in result.chunks
        ],
    }


def _first_claim_probe(verifier, *, question: str, claim) -> dict[str, object]:
    """Inspect one trusted claim in memory; expose only fixed numeric/boolean fields.

    A failed diagnostic must not replace the ordinary local support verdict.
    Its NLI/QA checks are read-only and use the already loaded local models.
    """

    statement = claim.statement.casefold()
    quote = claim.source_quote.casefold()
    probe: dict[str, object] = {
        "expected_expansion_in_claim": _ANCHOR in statement,
        "expected_expansion_in_quote": _ANCHOR in quote,
        "bleu_in_claim": "bleu" in statement,
        "bleu_in_quote": "bleu" in quote,
        "nli_token_count": None,
        "nli_contradiction": None,
        "nli_entailment": None,
        "nli_neutral": None,
        "qa_span_present": None,
    }
    try:
        encoded = verifier._nli._tokenizer.encode(claim.source_quote, claim.statement)
        count = len(encoded.ids)
        if type(count) is int and 0 < count <= 20_000:
            probe["nli_token_count"] = count
    except Exception:
        pass
    try:
        scores = verifier._nli.score(claim.source_quote, claim.statement)
        values = (scores.contradiction, scores.entailment, scores.neutral)
        if all(type(value) is float and math.isfinite(value) and 0 <= value <= 1 for value in values):
            probe["nli_contradiction"] = round(values[0], 3)
            probe["nli_entailment"] = round(values[1], 3)
            probe["nli_neutral"] = round(values[2], 3)
    except Exception:
        pass
    try:
        span = verifier._qa.answer(question, claim.source_quote)
        probe["qa_span_present"] = bool(
            span and normalize_text(span) in normalize_text(claim.source_quote)
        )
    except Exception:
        pass
    return probe


def _safe_failure_code(exc: BaseException) -> str:
    if isinstance(exc, DiagnosticRefusal):
        return exc.code
    if isinstance(exc, AIProviderError) and exc.code in _SAFE_PROVIDER_CODES:
        return exc.code
    return "diagnostic_failed"


def _safe_provider_reason_code(exc: AIProviderError) -> str:
    return (
        exc.reason_code
        if exc.reason_code in _SAFE_PROVIDER_REASON_CODES
        else "unclassified"
    )


def _safe_server_http_status(exc: AIProviderError) -> int | None:
    """Expose only a fixed server-status integer from a chained SDK failure."""

    if exc.reason_code != "http_server_error":
        return None
    current: BaseException | None = exc
    seen: set[int] = set()
    for _ in range(4):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))
        try:
            response = getattr(current, "response", None)
            values = (
                getattr(current, "status_code", None),
                getattr(current, "code", None),
                getattr(response, "status_code", None),
            )
        except Exception:
            values = ()
        for value in values:
            if type(value) is int and value in _SAFE_SERVER_HTTP_STATUSES:
                return value
        current = current.__cause__
    return None


async def execute_once(settings: Settings, case: SelectedCase, *, answer_from: str) -> dict[str, object]:
    embedding_provider = None
    answer_provider = None
    usage_receipts = 0
    usage_estimated = False
    embedding_input_tokens = 0
    report: dict[str, object] = {
        "question_kind": QUESTION_KIND,
        "answer_from": answer_from,
        "answer_policy": ASK_REQUIRED_RELEASE_POLICY_VERSION,
        "support_policy": LOCAL_SUPPORT_POLICY_VERSION,
        "answer_model": ANSWER_MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "comparison_policy_status": "diagnostic_only",
        "embedding_requests": 0,
        "answer_requests": 0,
        "cost_is_provider_receipt": False,
    }
    try:
        # Verify local model artifacts before any remote provider is constructed.
        verifier = create_local_support_verifier(settings.rag_local_support_model_dir)
        embedding_tokens = estimate_tokens(case.question)
        admitted_cost(embedding_tokens, 0)
        embedding_provider = get_embedding_provider(settings)
        async with asyncio.timeout(MAX_SECONDS):
            async with provider_attempt_scope(embedding_provider) as embedding_scope:
                embedding = await embedding_provider.embed_query(case.question)
            usage_estimated = embedding.usage.estimated
            usage_receipts += int(not embedding.usage.estimated)
            embedding_input_tokens = embedding.usage.input_tokens
            report["embedding_requests"] = embedding_scope.snapshot().request_count
            if report["embedding_requests"] != 1 or len(embedding.vectors) != 1:
                raise DiagnosticRefusal("embedding_call_count")
            results = await retrieve_comparison(case, embedding.vectors[0])
            report["retrieval"] = {
                label: _retrieval_summary(result) for label, result in results.items()
            }
            selected = results[answer_from]
            if selected.insufficient or not report["retrieval"][answer_from]["anchor_present"]:
                raise DiagnosticRefusal("usable_evidence_missing")
            await reauthorize_sources(case, selected.chunks)
            system_prompt, user_prompt = render_answer_prompts(
                question=case.question, history=(), chunks=selected.chunks,
            )
            prompt_tokens = estimate_tokens(f"{system_prompt}\n{user_prompt}")
            report["admitted_cost_usd"] = str(admitted_cost(embedding_tokens, prompt_tokens))
            report["history_messages"] = 0
            answer_provider = get_ai_provider(settings, role="rag_answer")
            async with provider_attempt_scope(answer_provider) as answer_scope:
                answer = await answer_provider.generate_structured(
                    response_model=GroundedAnswerOutput,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_output_tokens=MAX_ANSWER_OUTPUT_TOKENS,
                    operation="rag_answer",
                )
            usage_estimated = usage_estimated or answer.usage.estimated
            usage_receipts += int(not answer.usage.estimated)
            report["answer_requests"] = answer_scope.snapshot().request_count
            if report["answer_requests"] != 1:
                raise DiagnosticRefusal("answer_call_count")
            report["finish_reason"] = (
                answer.finish_reason if answer.finish_reason in _SAFE_FINISH else None
            )
            report["input_tokens"] = embedding.usage.input_tokens + answer.usage.input_tokens
            report["output_tokens"] = answer.usage.output_tokens
            report["usage_estimated"] = usage_estimated
            report["estimated_cost_usd"] = str((
                Decimal(embedding.usage.input_tokens) * PRICE_EMBEDDING
                + Decimal(answer.usage.input_tokens) * PRICE_INPUT
                + Decimal(answer.usage.output_tokens) * PRICE_OUTPUT
            ) / Decimal(1_000_000))
            report["observed_budget_exceeded"] = (
                embedding.usage.input_tokens > MAX_EMBEDDING_TOKENS
                or answer.usage.input_tokens > MAX_ANSWER_INPUT_TOKENS
                or answer.usage.output_tokens > MAX_ANSWER_OUTPUT_TOKENS
                or Decimal(report["estimated_cost_usd"]) > MAX_COST_USD
            )
            if answer.data.outcome == "abstain":
                report["outcome"] = "model_abstained"
            else:
                claims = validate_grounded_answer(answer.data, selected.chunks)
                report["first_claim_probe"] = await asyncio.to_thread(
                    _first_claim_probe, verifier, question=case.question, claim=claims[0],
                )
                verdict = await asyncio.to_thread(
                    verifier.evaluate, question=case.question, claims=claims,
                    chunks=selected.chunks,
                )
                report["outcome"] = "supported" if verdict.supported else "support_rejected"
                report["support_reason"] = (
                    verdict.reason_code if verdict.reason_code in _SAFE_REASONS else "unavailable"
                )
                report["claim_count"] = len(claims)
            await reauthorize_sources(case, selected.chunks)
            report["status"] = "completed"
    except BaseException as exc:
        report["status"] = "failed"
        report["reason"] = _safe_failure_code(exc)
        if isinstance(exc, AIProviderError):
            report["provider_reason_code"] = _safe_provider_reason_code(exc)
            http_status = _safe_server_http_status(exc)
            if http_status is not None:
                report["provider_http_status"] = http_status
        if isinstance(exc, AIProviderError) and exc.finish_reason in _SAFE_FINISH:
            report["finish_reason"] = exc.finish_reason
        if isinstance(exc, AIProviderError) and exc.usage is not None:
            usage_estimated = usage_estimated or exc.usage.estimated
            report["input_tokens"] = embedding_input_tokens + exc.usage.input_tokens
            report["output_tokens"] = exc.usage.output_tokens
            if not exc.usage.estimated:
                usage_receipts += 1
    finally:
        # Snapshot counters even on blocked output, timeout or cancellation.
        report["embedding_requests"] = (
            embedding_provider.telemetry_snapshot().request_count if embedding_provider else 0
        )
        report["answer_requests"] = (
            answer_provider.telemetry_snapshot().request_count if answer_provider else 0
        )
        report["usage_estimated"] = usage_estimated
        report["previous_attempt_cost_unknown"] = (
            report["embedding_requests"] + report["answer_requests"] > usage_receipts
            or usage_estimated
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--answer-job-id", type=UUID)
    parser.add_argument("--operator-latest-bleu", action="store_true")
    parser.add_argument("--answer-from", choices=("baseline", "candidate"), required=True)
    args = parser.parse_args()
    if (args.answer_job_id is None) == (not args.operator_latest_bleu):
        parser.error("Choose exactly one job selector")

    async def run() -> dict[str, object]:
        try:
            if (
                not args.execute
                or os.getenv("RUN_PRIVATE_ASK_COMPARISON") != "1"
                or os.getenv("PRIVATE_ASK_COMPARISON_AUTHORIZED")
                != "I_ACCEPT_PROVIDER_CHARGES_AND_PRIVATE_EVIDENCE"
            ):
                raise DiagnosticRefusal("authorization_missing")
            settings = require_live_envelope(get_settings(), execute=args.execute)
            case = await select_case(
                settings, job_id=args.answer_job_id,
                operator_latest=args.operator_latest_bleu,
            )
            return await execute_once(settings, case, answer_from=args.answer_from)
        finally:
            # asyncpg connections belong to this event loop. A second
            # asyncio.run() can fail during engine disposal after a paid call.
            try:
                await close_database()
            except Exception:
                pass

    try:
        report = asyncio.run(run())
        print(json.dumps(report, separators=(",", ":")))
        return 0 if report["status"] == "completed" else 1
    except BaseException as exc:
        # No exception text/traceback: SDK, SQL and validation exceptions may
        # contain private prompts, content or credentials. A failed remote call
        # can cost money even when no usage receipt is returned.
        failure = {
            "status": "failed", "reason": _safe_failure_code(exc),
            "embedding_requests": None, "answer_requests": None,
            "previous_attempt_cost_unknown": args.execute,
        }
        if isinstance(exc, AIProviderError):
            failure["provider_reason_code"] = _safe_provider_reason_code(exc)
            http_status = _safe_server_http_status(exc)
            if http_status is not None:
                failure["provider_http_status"] = http_status
        print(json.dumps(failure, separators=(",", ":")))
        return 1
if __name__ == "__main__":
    raise SystemExit(main())
