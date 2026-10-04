"""Bounded local diagnostics and explicit content-free telemetry export."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import json
import logging
import os
from pathlib import Path
import tempfile
from time import monotonic, time
from uuid import UUID

import httpx
from sqlalchemy import func, select

from app.models.email import EmailOutboxMessage
from app.models.generation import GenerationJob, GenerationJobSource
from app.models.operations import RequestEvent, WorkerHeartbeat
from app.models.knowledge import RagEmbeddingSpace, SubjectDocumentIndexJob, SubjectDocumentIndexRevision
from app.models.rag import RagAnswerJob, RagAnswerStageAttempt, RagMessage
from app.models.subject import Subject
from app.time_utils import as_utc, utcnow


logger = logging.getLogger(__name__)
_last_pulse: dict[tuple[str, str], tuple[float, str]] = {}


async def provider_migration_inventory(db, settings) -> dict:
    """Return a content-free, credential-free inventory before Gemini-only cutover.

    The result is operator-private. It never selects document text, model output,
    endpoints, API keys, source ciphertext, question text or user identifiers.
    """

    generation_rows = (await db.execute(
        select(GenerationJob.ai_provider, GenerationJob.status,
               GenerationJob.error_retryable, func.count(GenerationJob.id))
        .group_by(GenerationJob.ai_provider, GenerationJob.status,
                  GenerationJob.error_retryable)
        .order_by(GenerationJob.ai_provider, GenerationJob.status,
                  GenerationJob.error_retryable)
    )).all()
    retained_sources = (await db.execute(
        select(GenerationJob.ai_provider, GenerationJob.status,
               func.count(GenerationJobSource.job_id))
        .join(GenerationJobSource, GenerationJobSource.job_id == GenerationJob.id)
        .group_by(GenerationJob.ai_provider, GenerationJob.status)
        .order_by(GenerationJob.ai_provider, GenerationJob.status)
    )).all()
    index_rows = (await db.execute(
        select(SubjectDocumentIndexRevision.embedding_provider,
               SubjectDocumentIndexJob.status,
               func.count(SubjectDocumentIndexJob.id))
        .join(SubjectDocumentIndexRevision,
              SubjectDocumentIndexRevision.id == SubjectDocumentIndexJob.index_revision_id)
        .group_by(SubjectDocumentIndexRevision.embedding_provider,
                  SubjectDocumentIndexJob.status)
        .order_by(SubjectDocumentIndexRevision.embedding_provider,
                  SubjectDocumentIndexJob.status)
    )).all()
    answer_rows = (await db.execute(
        select(RagAnswerJob.ai_provider, RagAnswerJob.status,
               RagAnswerJob.error_retryable, func.count(RagAnswerJob.id))
        .group_by(RagAnswerJob.ai_provider, RagAnswerJob.status,
                  RagAnswerJob.error_retryable)
        .order_by(RagAnswerJob.ai_provider, RagAnswerJob.status,
                  RagAnswerJob.error_retryable)
    )).all()
    space_rows = (await db.execute(
        select(RagEmbeddingSpace.provider, func.count(RagEmbeddingSpace.identity_hash))
        .group_by(RagEmbeddingSpace.provider).order_by(RagEmbeddingSpace.provider)
    )).all()
    active_rows = (await db.execute(
        select(RagEmbeddingSpace.provider, func.count(Subject.id))
        .join(Subject, Subject.active_embedding_space_hash == RagEmbeddingSpace.identity_hash)
        .group_by(RagEmbeddingSpace.provider).order_by(RagEmbeddingSpace.provider)
    )).all()
    staged_rows = (await db.execute(
        select(RagEmbeddingSpace.provider, func.count(Subject.id))
        .join(Subject, Subject.staged_embedding_space_hash == RagEmbeddingSpace.identity_hash)
        .group_by(RagEmbeddingSpace.provider).order_by(RagEmbeddingSpace.provider)
    )).all()
    return {
        "configured": {
            "flashcard_provider": settings.flashcard_ai_provider,
            "answer_provider": settings.rag_ai_provider,
            "embedding_provider": settings.rag_embedding_provider,
            "ask_enabled": settings.rag_ask_effective_enabled,
            "legacy_provider_configured": any(provider == "openai_compatible" for provider in (
                settings.flashcard_ai_provider, settings.rag_ai_provider,
                settings.rag_embedding_provider,
            )),
        },
        "generation_jobs": [
            {"provider": provider, "status": state, "retryable": retryable, "count": count}
            for provider, state, retryable, count in generation_rows
        ],
        "retained_generation_sources": [
            {"provider": provider, "status": state, "count": count}
            for provider, state, count in retained_sources
        ],
        "index_jobs": [
            {"provider": provider, "status": state, "count": count}
            for provider, state, count in index_rows
        ],
        "answer_jobs": [
            {"provider": provider, "status": state, "retryable": retryable, "count": count}
            for provider, state, retryable, count in answer_rows
        ],
        "embedding_spaces": [
            {"provider": provider, "count": count,
             "active_subjects": dict(active_rows).get(provider, 0),
             "staged_subjects": dict(staged_rows).get(provider, 0)}
            for provider, count in space_rows
        ],
    }


async def record_request(factory, identifier: UUID, route: str, method: str, status_code: int, latency_milliseconds: int, error_code: str | None) -> None:
    async with factory() as db:
        async with db.begin():
            db.add(RequestEvent(id=identifier, route=route, method=method, status_code=status_code, latency_milliseconds=latency_milliseconds, error_code=error_code, created_at=utcnow()))


def worker_health_path(kind: str) -> Path:
    if kind not in {"generation", "email", "index", "answer"}:
        raise ValueError("Unknown worker kind")
    return Path(tempfile.gettempdir()) / f"cardchemy-{kind}-health.json"


def _write_local_health(kind: str, status: str) -> None:
    path = worker_health_path(kind)
    payload = {"kind": kind, "status": status, "last_seen": time(), "pid": os.getpid()}
    descriptor, temporary = tempfile.mkstemp(prefix=f"cardchemy-{kind}-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, separators=(",", ":"))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def check_local_worker_health(kind: str, stale_seconds: int) -> None:
    path = worker_health_path(kind)
    with path.open("r", encoding="utf-8") as source:
        raw = source.read(4097)
    if len(raw) > 4096:
        raise ValueError("Worker heartbeat is invalid")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get("kind") != kind or payload.get("status") not in {"running", "disabled"}:
        raise ValueError("Worker is not accepting work")
    seen = payload.get("last_seen")
    pid = payload.get("pid")
    if type(seen) not in {int, float} or not -5 <= time() - seen < stale_seconds or type(pid) is not int or pid <= 0:
        raise ValueError("Worker heartbeat is stale")
    # On Windows os.kill(pid, 0) can terminate the target. Freshness and the
    # disabled/running state suffice there; POSIX permits a safe existence test.
    if os.name == "posix":
        os.kill(pid, 0)


async def pulse_worker(factory, *, worker_id: str, kind: str, status: str, stale_seconds: int) -> None:
    """Pulse the local loop; DB metadata is bounded best effort, not a lease."""

    key = (kind, worker_id)
    now = monotonic()
    previous = _last_pulse.get(key)
    if previous and previous[1] == status and now - previous[0] < min(5.0, stale_seconds / 3):
        return
    try:
        _write_local_health(kind, status)
        _last_pulse[key] = (now, status)
    except Exception:
        logger.warning("worker_heartbeat_failed", extra={"kind": kind})
    try:
        async with asyncio.timeout(0.25):
            async with factory() as db:
                async with db.begin():
                    heartbeat = await db.get(WorkerHeartbeat, worker_id)
                    if heartbeat is None:
                        db.add(WorkerHeartbeat(worker_id=worker_id, kind=kind, last_seen_at=utcnow(), status=status))
                    else:
                        heartbeat.last_seen_at = utcnow()
                        heartbeat.status = status
    except Exception:
        logger.warning("worker_heartbeat_failed", extra={"kind": kind})


async def collect_metrics(db, settings) -> dict:
    async with asyncio.timeout(5):
        return await _collect_metrics(db, settings)


async def _collect_metrics(db, settings) -> dict:
    """Return local retained aggregates, plus bounded recent diagnostics."""

    window = utcnow() - timedelta(days=settings.request_retention_days)
    request_count, error_count, latency_sum = (await db.execute(select(
        func.count(RequestEvent.id),
        func.count(RequestEvent.id).filter(RequestEvent.status_code >= 500),
        func.coalesce(func.sum(RequestEvent.latency_milliseconds), 0),
    ).where(RequestEvent.created_at >= window))).one()
    recent_latencies = sorted((await db.scalars(select(RequestEvent.latency_milliseconds).where(RequestEvent.created_at >= window).order_by(RequestEvent.created_at.desc(), RequestEvent.id).limit(1000))).all())
    request_groups = (await db.execute(select(RequestEvent.route, RequestEvent.method, RequestEvent.status_code, func.count(RequestEvent.id)).where(RequestEvent.created_at >= window).group_by(RequestEvent.route, RequestEvent.method, RequestEvent.status_code).order_by(RequestEvent.route, RequestEvent.method, RequestEvent.status_code).limit(1000))).all()
    job_groups = (await db.execute(select(GenerationJob.status, func.count(GenerationJob.id)).group_by(GenerationJob.status))).all()
    email_groups = (await db.execute(select(EmailOutboxMessage.status, func.count(EmailOutboxMessage.id)).group_by(EmailOutboxMessage.status))).all()
    index_groups = (await db.execute(select(SubjectDocumentIndexJob.status, func.count(SubjectDocumentIndexJob.id)).group_by(SubjectDocumentIndexJob.status))).all()
    answer_groups = (await db.execute(select(RagAnswerJob.status, func.count(RagAnswerJob.id)).group_by(RagAnswerJob.status))).all()
    capture_groups = (await db.execute(select(
        GenerationJob.knowledge_capture_status,
        func.count(GenerationJob.id),
    ).group_by(GenerationJob.knowledge_capture_status))).all()
    usage_rows = (await db.execute(select(
        GenerationJob.ai_provider, GenerationJob.ai_model, func.count(GenerationJob.id),
        func.coalesce(func.sum(GenerationJob.generated_card_count), 0),
        func.coalesce(func.sum(GenerationJob.estimated_input_tokens), 0),
        func.coalesce(func.sum(GenerationJob.estimated_output_tokens), 0),
        func.coalesce(func.sum(GenerationJob.estimated_cost_microusd), 0),
        func.coalesce(func.sum(GenerationJob.actual_input_tokens), 0),
        func.coalesce(func.sum(GenerationJob.actual_output_tokens), 0),
        func.coalesce(func.sum(GenerationJob.actual_cost_microusd), 0),
        func.coalesce(func.sum(GenerationJob.provider_request_count), 0),
        func.coalesce(func.sum(GenerationJob.provider_retry_count), 0),
    ).group_by(GenerationJob.ai_provider, GenerationJob.ai_model).order_by(GenerationJob.ai_provider, GenerationJob.ai_model).limit(100))).all()
    recent_jobs = (await db.execute(select(GenerationJob.started_at, GenerationJob.completed_at).order_by(GenerationJob.created_at.desc(), GenerationJob.id).limit(1000))).all()
    durations = [max(0, int((as_utc(completed_at) - as_utc(started_at)).total_seconds() * 1000)) for started_at, completed_at in recent_jobs if completed_at is not None and started_at is not None]
    capture_rows = (await db.execute(select(
        GenerationJob.knowledge_capture_started_at,
        GenerationJob.knowledge_capture_completed_at,
    ).where(
        GenerationJob.knowledge_capture_status != "not_requested"
    ).order_by(GenerationJob.created_at.desc(), GenerationJob.id).limit(1000))).all()
    capture_durations = [
        max(0, int((as_utc(completed) - as_utc(started)).total_seconds() * 1000))
        for started, completed in capture_rows
        if started is not None and completed is not None
    ]
    index_rows = (await db.execute(select(
        SubjectDocumentIndexJob.created_at,
        SubjectDocumentIndexJob.completed_at,
    ).order_by(
        SubjectDocumentIndexJob.created_at.desc(), SubjectDocumentIndexJob.id
    ).limit(1000))).all()
    index_durations = [
        max(0, int((as_utc(completed) - as_utc(created)).total_seconds() * 1000))
        for created, completed in index_rows
        if completed is not None
    ]
    index_usage_rows = (await db.execute(select(
        SubjectDocumentIndexRevision.embedding_provider,
        SubjectDocumentIndexRevision.embedding_model,
        func.count(SubjectDocumentIndexJob.id),
        func.coalesce(func.sum(SubjectDocumentIndexJob.estimated_input_tokens), 0),
        func.coalesce(func.sum(SubjectDocumentIndexJob.actual_input_tokens), 0),
        func.coalesce(func.sum(SubjectDocumentIndexJob.estimated_cost_microusd), 0),
        func.coalesce(func.sum(SubjectDocumentIndexJob.actual_cost_microusd), 0),
        func.coalesce(func.sum(SubjectDocumentIndexJob.provider_request_count), 0),
        func.coalesce(func.sum(SubjectDocumentIndexJob.provider_retry_count), 0),
        func.coalesce(func.sum(SubjectDocumentIndexJob.provider_rate_limit_wait_milliseconds), 0),
    ).join(
        SubjectDocumentIndexRevision,
        SubjectDocumentIndexRevision.id == SubjectDocumentIndexJob.index_revision_id,
    ).group_by(
        SubjectDocumentIndexRevision.embedding_provider,
        SubjectDocumentIndexRevision.embedding_model,
    ).order_by(
        SubjectDocumentIndexRevision.embedding_provider,
        SubjectDocumentIndexRevision.embedding_model,
    ).limit(100))).all()
    answer_rows = (await db.execute(select(
        RagAnswerJob.created_at,
        RagAnswerJob.provider_call_started_at,
        RagAnswerJob.retrieval_completed_at,
        RagAnswerJob.completed_at,
    ).order_by(RagAnswerJob.created_at.desc(), RagAnswerJob.id).limit(1000))).all()
    answer_durations = [
        max(0, int((as_utc(completed) - as_utc(created)).total_seconds() * 1000))
        for created, _provider_started, _retrieval_completed, completed in answer_rows
        if completed is not None
    ]
    retrieval_durations = [
        max(0, int((as_utc(retrieval_completed) - as_utc(provider_started)).total_seconds() * 1000))
        for _created, provider_started, retrieval_completed, _completed in answer_rows
        if provider_started is not None and retrieval_completed is not None
    ]
    answer_usage_rows = (await db.execute(select(
        RagAnswerJob.ai_provider,
        RagAnswerJob.ai_model,
        func.count(RagAnswerJob.id),
        func.coalesce(func.sum(RagAnswerJob.estimated_input_tokens), 0),
        func.coalesce(func.sum(RagAnswerJob.estimated_output_tokens), 0),
        func.coalesce(func.sum(RagAnswerJob.actual_input_tokens), 0),
        func.coalesce(func.sum(RagAnswerJob.actual_output_tokens), 0),
        func.coalesce(func.sum(RagAnswerJob.estimated_cost_microusd), 0),
        func.coalesce(func.sum(RagAnswerJob.actual_cost_microusd), 0),
        func.coalesce(func.sum(RagAnswerJob.provider_request_count), 0),
        func.coalesce(func.sum(RagAnswerJob.provider_retry_count), 0),
        func.coalesce(func.sum(RagAnswerJob.provider_rate_limit_wait_milliseconds), 0),
        func.coalesce(func.sum(RagAnswerJob.support_rejection_count), 0),
    ).group_by(
        RagAnswerJob.ai_provider, RagAnswerJob.ai_model,
    ).order_by(RagAnswerJob.ai_provider, RagAnswerJob.ai_model).limit(100))).all()
    answer_outcomes = (await db.execute(select(
        RagMessage.outcome, func.count(RagMessage.id)
    ).where(
        RagMessage.role == "assistant",
        RagMessage.created_at >= window,
    ).group_by(RagMessage.outcome))).all()
    now = utcnow()
    # Heartbeat history is bounded; stale instances remain visible until cleanup.
    workers = (await db.scalars(select(WorkerHeartbeat).order_by(WorkerHeartbeat.last_seen_at.desc(), WorkerHeartbeat.worker_id).limit(100))).all()
    worker_rows = [{"worker_id": item.worker_id, "kind": item.kind, "status": item.status, "healthy": item.status in {"running", "disabled"} and (now - as_utc(item.last_seen_at)).total_seconds() < settings.worker_health_stale_seconds, "last_seen_at": as_utc(item.last_seen_at).isoformat()} for item in workers]
    return {
        "schema_version": 2,
        "requests": {"retention_days": settings.request_retention_days, "count": int(request_count), "server_error_count": int(error_count), "server_error_rate": error_count / request_count if request_count else 0.0, "latency_milliseconds_sum": int(latency_sum), "latency_milliseconds_average": latency_sum / request_count if request_count else 0.0, "recent_sample_count": len(recent_latencies), "recent_p95_milliseconds": recent_latencies[min(len(recent_latencies) - 1, int(len(recent_latencies) * 0.95))] if recent_latencies else 0, "routes": [{"route": route, "method": method, "status_code": status_code, "count": count} for route, method, status_code, count in request_groups]},
        "generation": {"status_counts": dict(job_groups), "queue_depth": dict(job_groups).get("queued", 0), "duration_sample_count": len(durations), "duration_milliseconds_sum": sum(durations), "duration_milliseconds_average": sum(durations) / len(durations) if durations else 0.0, "models": [dict(zip(("provider", "model", "job_count", "generated_card_count", "estimated_input_tokens", "estimated_output_tokens", "estimated_cost_microusd", "actual_input_tokens", "actual_output_tokens", "actual_cost_microusd", "provider_request_count", "provider_retry_count"), row)) for row in usage_rows]},
        "email": {"status_counts": dict(email_groups), "queue_depth": dict(email_groups).get("pending", 0)},
        "knowledge_capture": {"status_counts": dict(capture_groups), "failure_count": dict(capture_groups).get("failed", 0), "throughput_count": dict(capture_groups).get("captured", 0), "duration_sample_count": len(capture_durations), "duration_milliseconds_sum": sum(capture_durations), "duration_milliseconds_average": sum(capture_durations) / len(capture_durations) if capture_durations else 0.0},
        "knowledge_index": {"status_counts": dict(index_groups), "queue_depth": dict(index_groups).get("queued", 0), "failure_count": dict(index_groups).get("failed", 0), "throughput_count": dict(index_groups).get("completed", 0), "duration_sample_count": len(index_durations), "duration_milliseconds_sum": sum(index_durations), "duration_milliseconds_average": sum(index_durations) / len(index_durations) if index_durations else 0.0, "models": [dict(zip(("provider", "model", "job_count", "estimated_input_tokens", "actual_input_tokens", "estimated_cost_microusd", "actual_cost_microusd", "provider_request_count", "provider_retry_count", "provider_rate_limit_wait_milliseconds"), row)) for row in index_usage_rows]},
        "rag_answer": {"status_counts": dict(answer_groups), "queue_depth": dict(answer_groups).get("queued", 0), "failure_count": dict(answer_groups).get("failed", 0), "throughput_count": dict(answer_groups).get("completed", 0), "duration_sample_count": len(answer_durations), "duration_milliseconds_sum": sum(answer_durations), "duration_milliseconds_average": sum(answer_durations) / len(answer_durations) if answer_durations else 0.0, "retrieval_duration_sample_count": len(retrieval_durations), "retrieval_duration_milliseconds_sum": sum(retrieval_durations), "retrieval_duration_milliseconds_average": sum(retrieval_durations) / len(retrieval_durations) if retrieval_durations else 0.0, "outcome_counts": {str(outcome): count for outcome, count in answer_outcomes if outcome is not None}, "models": [dict(zip(("provider", "model", "job_count", "estimated_input_tokens", "estimated_output_tokens", "actual_input_tokens", "actual_output_tokens", "estimated_cost_microusd", "actual_cost_microusd", "provider_request_count", "provider_retry_count", "provider_rate_limit_wait_milliseconds", "support_rejection_count"), row)) for row in answer_usage_rows]},
        "workers": worker_rows,
    }


async def job_diagnostics(db, job_id: UUID) -> dict | None:
    """Diagnose by opaque ID without querying document/card/user columns."""

    columns = ("id", "request_id", "status", "stage", "attempt_count", "manual_retry_count", "error_code", "error_retryable", "requested_card_count", "generated_card_count", "accepted_card_count", "rejected_card_count", "selected_card_count", "quality_attempts", "ai_provider", "ai_model", "estimated_input_tokens", "estimated_output_tokens", "estimated_cost_microusd", "actual_input_tokens", "actual_output_tokens", "actual_cost_microusd", "usage_estimated", "provider_request_count", "provider_retry_count", "provider_rate_limit_wait_milliseconds", "cached_input_tokens", "created_at", "started_at", "completed_at", "heartbeat_at")
    row = (await db.execute(select(*(getattr(GenerationJob, name) for name in columns)).where(GenerationJob.id == job_id))).first()
    if row is None:
        return None
    result = dict(zip(columns, row))
    from app.observability import safe_error_code
    from app.ai.grounding import REJECTION_CATEGORIES

    # JSON is retained for durable diagnostics. Re-allowlist it at the operator
    # boundary so unexpected stored keys can never expose document/model text.
    attempts = result.pop("quality_attempts")
    result["quality_attempt_count"] = min(128, len(attempts)) if isinstance(attempts, list) else 0
    latest = attempts[-1] if isinstance(attempts, list) and attempts else None
    if isinstance(latest, dict):
        def safe_count(value: object) -> int:
            try:
                return min(1_000_000, max(0, int(value)))
            except (TypeError, ValueError, OverflowError):
                return 0

        scalar_names = (
            "manual_retry_number", "attempt_number", "raw_count",
            "grounded_count", "valid_count", "distinct_count", "accepted_count",
            "missing_count", "rejected_count", "refill_rounds_used",
            "uncertain_request_count",
        )
        round_names = (
            "round", "raw_count", "grounded_count", "valid_count",
            "distinct_count", "accepted_count", "missing_count",
        )
        rounds = latest.get("rounds")
        rejections = latest.get("rejections")
        summary = {name: safe_count(latest.get(name)) for name in scalar_names}
        summary["rounds"] = [
            {name: safe_count(item.get(name)) for name in round_names}
            for item in (rounds[:10] if isinstance(rounds, list) else [])
            if isinstance(item, dict)
        ]
        summary["rejections"] = {
            name: safe_count(rejections.get(name))
            for name in REJECTION_CATEGORIES
        } if isinstance(rejections, dict) else {}
        result["latest_attempt_quality_diagnostics"] = summary
        result["latest_attempt_rejected_card_count"] = summary["rejected_count"]
    else:
        result["latest_attempt_quality_diagnostics"] = None
        result["latest_attempt_rejected_card_count"] = 0
    if result["error_code"] is not None:
        result["error_code"] = safe_error_code(result["error_code"])
    for key, value in result.items():
        if isinstance(value, UUID):
            result[key] = str(value)
        elif hasattr(value, "isoformat"):
            result[key] = as_utc(value).isoformat()
    return result


async def answer_job_diagnostics(db, job_id: UUID) -> dict | None:
    """Return bounded, content-free Ask stage and attempt diagnostics by opaque ID."""

    from app.observability import safe_error_code

    fields = (
        "id", "request_id", "status", "attempt_count", "manual_retry_count",
        "error_code", "error_retryable", "failed_stage", "provider_error_category",
        "failure_reason",
        "execution_uncertain", "ai_provider", "ai_model", "answer_policy_version",
        "support_policy_version", "attempt_cost_microusd", "attempt_cost_unknown",
        "estimated_input_tokens", "estimated_output_tokens",
        "actual_input_tokens", "actual_output_tokens", "estimated_cost_microusd",
        "actual_cost_microusd", "usage_estimated", "provider_request_count",
        "provider_retry_count", "provider_rate_limit_wait_milliseconds",
        "support_rejection_count", "created_at", "provider_call_started_at",
        "retrieval_completed_at", "completed_at",
    )
    row = (await db.execute(select(*(getattr(RagAnswerJob, field) for field in fields))
                            .where(RagAnswerJob.id == job_id))).first()
    if row is None:
        return None
    result = dict(zip(fields, row))
    if result["error_code"] is not None:
        result["error_code"] = safe_error_code(result["error_code"])
    safe_stages = {"query_embedding", "retrieval", "answer", "support", "local_support",
                   "shutdown", "preflight", "worker_lease"}
    if result["failed_stage"] not in safe_stages:
        result["failed_stage"] = None
    safe_categories = {"internal_failure", "retrieval_failed", "timeout",
                       "shutdown", "cancelled", "lease_expired", "local_support_unavailable"}
    safe_reasons = {
        "transport_timeout", "transport_protocol", "transport_network",
        "http_invalid_request", "http_authentication", "http_access_denied",
        "http_model_missing", "http_rate_limited", "http_server_error",
        "http_transient", "http_rejected", "sdk_unclassified",
        "output_empty", "output_blocked", "output_unfinished", "json_invalid",
        "schema_invalid", "citation_invalid", "answer_too_long",
        "retrieval_failed", "retrieval_timeout", "local_support_unavailable",
        "local_support_timeout", "rag_access_revoked", "rag_corpus_changed",
        "internal_failure",
    }
    safe_finish_reasons = {
        "FINISH_REASON_UNSPECIFIED", "STOP", "MAX_TOKENS", "SAFETY",
        "RECITATION", "LANGUAGE", "OTHER", "BLOCKLIST",
        "PROHIBITED_CONTENT", "SPII", "MALFORMED_FUNCTION_CALL",
        "IMAGE_SAFETY", "UNEXPECTED_TOOL_CALL", "IMAGE_PROHIBITED_CONTENT",
        "NO_IMAGE", "IMAGE_RECITATION", "IMAGE_OTHER",
    }
    safe_support_reasons = {
        "supported", "missing_evidence", "entailment_rejected",
        "question_relevance_rejected", "equivalence_rejected",
        "contradiction_detected", "support_rejected",
    }

    def category(value: str | None) -> str | None:
        if value is None:
            return None
        return value if value in safe_categories else safe_error_code(value)

    result["provider_error_category"] = category(result["provider_error_category"])
    result["failure_reason"] = (
        result["failure_reason"] if result["failure_reason"] in safe_reasons
        else "internal_failure" if result["failure_reason"] else None
    )
    for key, value in result.items():
        if isinstance(value, UUID):
            result[key] = str(value)
        elif hasattr(value, "isoformat"):
            result[key] = as_utc(value).isoformat()

    attempts = (await db.scalars(select(RagAnswerStageAttempt)
                                 .where(RagAnswerStageAttempt.job_id == job_id)
                                 .order_by(RagAnswerStageAttempt.manual_retry_number,
                                           RagAnswerStageAttempt.worker_attempt_number,
                                           RagAnswerStageAttempt.started_at,
                                           RagAnswerStageAttempt.id)
                                 .limit(400))).all()
    def safe_ranks(value: object) -> list[dict[str, int | None]] | None:
        if not isinstance(value, list) or len(value) > 5:
            return None
        ranks = []
        for entry in value:
            if not isinstance(entry, dict) or set(entry) != {"vector_rank", "lexical_rank"}:
                return None
            pair = {}
            for key in ("vector_rank", "lexical_rank"):
                rank = entry[key]
                if rank is not None and (type(rank) is not int or not 1 <= rank <= 20):
                    return None
                pair[key] = rank
            ranks.append(pair)
        return ranks

    result["stages"] = [
        {
            "manual_retry_number": item.manual_retry_number,
            "worker_attempt_number": item.worker_attempt_number,
            "stage": item.stage if item.stage in safe_stages else "unknown",
            "started_at": as_utc(item.started_at).isoformat(),
            "completed_at": as_utc(item.completed_at).isoformat() if item.completed_at else None,
            "elapsed_milliseconds": item.elapsed_milliseconds,
            "physical_request_count": item.physical_request_count,
            "retry_count": item.retry_count,
            "rate_limit_wait_milliseconds": item.rate_limit_wait_milliseconds,
            "error_category": category(item.error_category),
            "failure_reason": item.failure_reason if item.failure_reason in safe_reasons else "internal_failure" if item.failure_reason else None,
            "provider_finish_reason": item.provider_finish_reason if item.provider_finish_reason in safe_finish_reasons else "OTHER" if item.provider_finish_reason else None,
            "input_tokens": item.input_tokens,
            "output_tokens": item.output_tokens,
            "usage_estimated": item.usage_estimated,
            "retrieval_ranks": safe_ranks(item.retrieval_ranks),
            "support_reason": item.support_reason if item.support_reason in safe_support_reasons else None,
            "support_entailment": item.support_entailment if item.support_entailment in {"pass", "fail", "not_run"} else None,
            "support_question_relevance": item.support_question_relevance if item.support_question_relevance in {"pass", "fail", "not_run"} else None,
            "support_equivalence": item.support_equivalence if item.support_equivalence in {"pass", "fail", "not_run", "not_required"} else None,
            "support_contradiction": item.support_contradiction if item.support_contradiction in {"pass", "fail", "not_run"} else None,
            "execution_uncertain": item.execution_uncertain,
        }
        for item in attempts
    ]
    return result


def telemetry_snapshot(metrics: dict) -> dict:
    """Fixed schema of aggregate numbers only; no strings or identifiers."""

    models = metrics["generation"]["models"]
    keys = ("job_count", "generated_card_count", "estimated_input_tokens", "estimated_output_tokens", "estimated_cost_microusd", "actual_input_tokens", "actual_output_tokens", "actual_cost_microusd", "provider_request_count", "provider_retry_count")
    payload = {"schema_version": 2, "request_count": metrics["requests"]["count"], "request_server_error_count": metrics["requests"]["server_error_count"], "request_latency_milliseconds_sum": metrics["requests"]["latency_milliseconds_sum"], "generation_queue_depth": metrics["generation"]["queue_depth"], "email_queue_depth": metrics["email"]["queue_depth"], "knowledge_index_queue_depth": metrics["knowledge_index"]["queue_depth"], "rag_answer_queue_depth": metrics["rag_answer"]["queue_depth"], "generation_duration_milliseconds_sum": metrics["generation"]["duration_milliseconds_sum"], "generation_duration_sample_count": metrics["generation"]["duration_sample_count"], "knowledge_capture_failure_count": metrics["knowledge_capture"]["failure_count"], "knowledge_capture_throughput_count": metrics["knowledge_capture"]["throughput_count"], "knowledge_capture_duration_milliseconds_sum": metrics["knowledge_capture"]["duration_milliseconds_sum"], "knowledge_index_failure_count": metrics["knowledge_index"]["failure_count"], "knowledge_index_throughput_count": metrics["knowledge_index"]["throughput_count"], "knowledge_index_duration_milliseconds_sum": metrics["knowledge_index"]["duration_milliseconds_sum"], "rag_answer_failure_count": metrics["rag_answer"]["failure_count"], "rag_answer_throughput_count": metrics["rag_answer"]["throughput_count"], "rag_answer_duration_milliseconds_sum": metrics["rag_answer"]["duration_milliseconds_sum"], "rag_retrieval_duration_milliseconds_sum": metrics["rag_answer"]["retrieval_duration_milliseconds_sum"], "rag_answer_count": metrics["rag_answer"]["outcome_counts"].get("answer", 0), "rag_abstention_count": metrics["rag_answer"]["outcome_counts"].get("abstained", 0), "worker_healthy_count": sum(item["healthy"] for item in metrics["workers"])}
    payload.update({key: sum(int(model[key]) for model in models) for key in keys})
    for prefix, collection in (
        ("knowledge_index", metrics["knowledge_index"]["models"]),
        ("rag_answer", metrics["rag_answer"]["models"]),
    ):
        for key in ("job_count", "estimated_input_tokens", "actual_input_tokens", "estimated_cost_microusd", "actual_cost_microusd", "provider_request_count", "provider_retry_count", "provider_rate_limit_wait_milliseconds"):
            payload[f"{prefix}_{key}"] = sum(int(model[key]) for model in collection)
    payload["rag_answer_estimated_output_tokens"] = sum(int(model["estimated_output_tokens"]) for model in metrics["rag_answer"]["models"])
    payload["rag_answer_actual_output_tokens"] = sum(int(model["actual_output_tokens"]) for model in metrics["rag_answer"]["models"])
    payload["rag_support_rejection_count"] = sum(int(model["support_rejection_count"]) for model in metrics["rag_answer"]["models"])
    return payload


async def send_telemetry(db, settings) -> bool:
    """Explicit operator trigger; never called by API startup or request code."""

    if not settings.telemetry_enabled or settings.telemetry_endpoint is None:
        return False
    payload = telemetry_snapshot(await collect_metrics(db, settings))
    try:
        async with httpx.AsyncClient(timeout=settings.telemetry_timeout_seconds, follow_redirects=False, trust_env=False) as client:
            response = await client.post(str(settings.telemetry_endpoint), json=payload)
            response.raise_for_status()
    except Exception:
        logger.warning("telemetry_failed")
        return False
    logger.info("telemetry_sent")
    return True


async def operations_status(db, settings, *, job_id: UUID | None = None) -> dict:
    if job_id is not None:
        result = await job_diagnostics(db, job_id)
        return {"status": "found", "job": result} if result is not None else {"status": "not_found"}
    return await collect_metrics(db, settings)


async def report_telemetry(db, settings) -> dict:
    if not settings.telemetry_enabled or settings.telemetry_endpoint is None:
        return {"status": "disabled"}
    return {"status": "sent" if await send_telemetry(db, settings) else "failed"}
