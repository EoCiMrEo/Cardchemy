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
from app.models.generation import GenerationJob
from app.models.operations import RequestEvent, WorkerHeartbeat
from app.time_utils import as_utc, utcnow


logger = logging.getLogger(__name__)
_last_pulse: dict[tuple[str, str], tuple[float, str]] = {}


async def record_request(factory, identifier: UUID, route: str, method: str, status_code: int, latency_milliseconds: int, error_code: str | None) -> None:
    async with factory() as db:
        async with db.begin():
            db.add(RequestEvent(id=identifier, route=route, method=method, status_code=status_code, latency_milliseconds=latency_milliseconds, error_code=error_code, created_at=utcnow()))


def worker_health_path(kind: str) -> Path:
    if kind not in {"generation", "email"}:
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
    now = utcnow()
    # Heartbeat history is bounded; stale instances remain visible until cleanup.
    workers = (await db.scalars(select(WorkerHeartbeat).order_by(WorkerHeartbeat.last_seen_at.desc(), WorkerHeartbeat.worker_id).limit(100))).all()
    worker_rows = [{"worker_id": item.worker_id, "kind": item.kind, "status": item.status, "healthy": item.status in {"running", "disabled"} and (now - as_utc(item.last_seen_at)).total_seconds() < settings.worker_health_stale_seconds, "last_seen_at": as_utc(item.last_seen_at).isoformat()} for item in workers]
    return {
        "schema_version": 1,
        "requests": {"retention_days": settings.request_retention_days, "count": int(request_count), "server_error_count": int(error_count), "server_error_rate": error_count / request_count if request_count else 0.0, "latency_milliseconds_sum": int(latency_sum), "latency_milliseconds_average": latency_sum / request_count if request_count else 0.0, "recent_sample_count": len(recent_latencies), "recent_p95_milliseconds": recent_latencies[min(len(recent_latencies) - 1, int(len(recent_latencies) * 0.95))] if recent_latencies else 0, "routes": [{"route": route, "method": method, "status_code": status_code, "count": count} for route, method, status_code, count in request_groups]},
        "generation": {"status_counts": dict(job_groups), "queue_depth": dict(job_groups).get("queued", 0), "duration_sample_count": len(durations), "duration_milliseconds_sum": sum(durations), "duration_milliseconds_average": sum(durations) / len(durations) if durations else 0.0, "models": [dict(zip(("provider", "model", "job_count", "generated_card_count", "estimated_input_tokens", "estimated_output_tokens", "estimated_cost_microusd", "actual_input_tokens", "actual_output_tokens", "actual_cost_microusd", "provider_request_count", "provider_retry_count"), row)) for row in usage_rows]},
        "email": {"status_counts": dict(email_groups), "queue_depth": dict(email_groups).get("pending", 0)},
        "workers": worker_rows,
    }


async def job_diagnostics(db, job_id: UUID) -> dict | None:
    """Diagnose by opaque ID without querying document/card/user columns."""

    columns = ("id", "request_id", "status", "stage", "attempt_count", "error_code", "error_retryable", "generated_card_count", "ai_provider", "ai_model", "estimated_input_tokens", "estimated_output_tokens", "estimated_cost_microusd", "actual_input_tokens", "actual_output_tokens", "actual_cost_microusd", "usage_estimated", "provider_request_count", "provider_retry_count", "provider_rate_limit_wait_milliseconds", "cached_input_tokens", "created_at", "started_at", "completed_at", "heartbeat_at")
    row = (await db.execute(select(*(getattr(GenerationJob, name) for name in columns)).where(GenerationJob.id == job_id))).first()
    if row is None:
        return None
    result = dict(zip(columns, row))
    from app.observability import safe_error_code
    if result["error_code"] is not None:
        result["error_code"] = safe_error_code(result["error_code"])
    for key, value in result.items():
        if isinstance(value, UUID):
            result[key] = str(value)
        elif hasattr(value, "isoformat"):
            result[key] = as_utc(value).isoformat()
    return result


def telemetry_snapshot(metrics: dict) -> dict:
    """Fixed schema of aggregate numbers only; no strings or identifiers."""

    models = metrics["generation"]["models"]
    keys = ("job_count", "generated_card_count", "estimated_input_tokens", "estimated_output_tokens", "estimated_cost_microusd", "actual_input_tokens", "actual_output_tokens", "actual_cost_microusd", "provider_request_count", "provider_retry_count")
    payload = {"schema_version": 1, "request_count": metrics["requests"]["count"], "request_server_error_count": metrics["requests"]["server_error_count"], "request_latency_milliseconds_sum": metrics["requests"]["latency_milliseconds_sum"], "generation_queue_depth": metrics["generation"]["queue_depth"], "email_queue_depth": metrics["email"]["queue_depth"], "generation_duration_milliseconds_sum": metrics["generation"]["duration_milliseconds_sum"], "generation_duration_sample_count": metrics["generation"]["duration_sample_count"], "worker_healthy_count": sum(item["healthy"] for item in metrics["workers"])}
    payload.update({key: sum(int(model[key]) for model in models) for key in keys})
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
