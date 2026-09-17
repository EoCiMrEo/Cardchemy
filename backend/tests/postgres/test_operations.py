"""Deployed-schema proofs for content-free operational diagnostics."""

from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

from app.models.operations import RequestEvent, WorkerHeartbeat
from app.services.operations import record_request
from app.time_utils import utcnow


pytestmark = pytest.mark.postgres


async def test_operations_migration_has_only_safe_columns_constraints_and_retention_indexes(postgres_session_factory):
    async with postgres_session_factory() as db:
        rows = (await db.execute(text("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('request_events','worker_heartbeats')"))).all()
        columns = {}
        for table, column in rows:
            columns.setdefault(table, set()).add(column)
        assert columns["request_events"] == {"id", "route", "method", "status_code", "latency_milliseconds", "error_code", "created_at"}
        assert columns["worker_heartbeats"] == {"worker_id", "kind", "last_seen_at", "status"}
        indexes = set((await db.scalars(text("SELECT indexname FROM pg_indexes WHERE schemaname='public'"))).all())
        assert {"ix_request_events_created", "ix_worker_heartbeats_kind_seen", "ix_worker_heartbeats_retention", "ix_generation_jobs_retention"} <= indexes
        correlation_type = await db.scalar(text("SELECT data_type FROM information_schema.columns WHERE table_schema='public' AND table_name='generation_jobs' AND column_name='request_id'"))
        assert correlation_type == "uuid"


async def test_request_correlation_persists_and_failed_diagnostic_transaction_rolls_back(postgres_session_factory):
    identifier = uuid4()
    bad = uuid4()
    try:
        await record_request(postgres_session_factory, identifier, "/flashcards/generation-jobs/{job_id}", "GET", 500, 23, "internal_error")
        async with postgres_session_factory() as db:
            record = await db.get(RequestEvent, identifier)
            assert record.error_code == "internal_error"
            assert record.route == "/flashcards/generation-jobs/{job_id}"
        with pytest.raises(IntegrityError):
            async with postgres_session_factory() as db:
                async with db.begin():
                    db.add(RequestEvent(id=bad, route="unmatched", method="GET", status_code=600, latency_milliseconds=0))
                    await db.flush()
        async with postgres_session_factory() as db:
            assert await db.get(RequestEvent, bad) is None
    finally:
        async with postgres_session_factory() as db:
            async with db.begin():
                await db.execute(delete(RequestEvent).where(RequestEvent.id.in_([identifier, bad])))


async def test_worker_health_uses_kind_status_checks_and_updates_same_instance(postgres_session_factory):
    identifier = f"operations-{uuid4()}"
    try:
        async with postgres_session_factory() as db:
            async with db.begin():
                db.add(WorkerHeartbeat(worker_id=identifier, kind="generation", status="disabled", last_seen_at=utcnow()))
        async with postgres_session_factory() as db:
            async with db.begin():
                heartbeat = await db.get(WorkerHeartbeat, identifier)
                heartbeat.status = "draining"
        async with postgres_session_factory() as db:
            heartbeat = await db.get(WorkerHeartbeat, identifier)
            assert heartbeat.status == "draining"
        with pytest.raises(IntegrityError):
            async with postgres_session_factory() as db:
                async with db.begin():
                    heartbeat = await db.get(WorkerHeartbeat, identifier)
                    heartbeat.kind = "unknown"
                    await db.flush()
        async with postgres_session_factory() as db:
            heartbeat = await db.get(WorkerHeartbeat, identifier)
            assert heartbeat.kind == "generation"
    finally:
        async with postgres_session_factory() as db:
            async with db.begin():
                await db.execute(delete(WorkerHeartbeat).where(WorkerHeartbeat.worker_id == identifier))
