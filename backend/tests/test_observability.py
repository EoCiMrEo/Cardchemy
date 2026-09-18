"""Privacy, correlation, health, and bounded diagnostic contracts."""

import asyncio
from datetime import timedelta
import io
import json
import logging
import os
import sys
from time import monotonic, time
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import HTTPException
import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings
from app.database import Base
from app.main import create_app
from app.models.generation import GenerationJob
from app.models.operations import RequestEvent, WorkerHeartbeat
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.observability import SafeJsonFormatter, SafeLogFilter, configure_logging, current_request_id, job_context, safe_error_code, sanitize_validation
from app.schemas.generation import GenerationJobCreate
from app.services.generation import GenerationJobService, generation_http_error
import app.services.operations as operations
from app.time_utils import utcnow
from app.workers.generation import GenerationWorker


PRIVATE = "private_lowercase_secret"


@pytest_asyncio.fixture
async def session_factory(tmp_path):
    # Best-effort cancellation may invalidate a connection. A file-backed
    # SQLite DB retains the schema, like the production PostgreSQL database.
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'operations.sqlite'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def settings(**overrides):
    return Settings(_env_file=None, **({
        "environment": "test", "database_url": "sqlite+aiosqlite:///:memory:",
        "secret_key": "test-only-secret-key-with-adequate-entropy-1234567890",
        "generation_source_encryption_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "flashcard_ai_provider_enabled": True,
    } | overrides))


class PasswordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=10)

    @field_validator("password")
    @classmethod
    def reject(cls, value):
        if value == PRIVATE:
            raise ValueError(value)
        return value


def application(factory):
    app = create_app(settings())
    app.state.operations_session_factory = factory

    @app.get("/diagnostic/{token}")
    async def diagnostic(token: str):
        return {"request_id": str(current_request_id())}

    @app.post("/validated")
    async def validated(value: PasswordInput):
        return {"ok": True}

    @app.get("/unexpected")
    async def unexpected():
        raise RuntimeError(PRIVATE)

    @app.get("/domain")
    async def domain():
        raise generation_http_error(409, "idempotency_key_reused", "This Idempotency-Key was already used for different job metadata.")

    @app.get("/untrusted/{kind}")
    async def untrusted(kind: str):
        if kind == "string":
            raise HTTPException(400, detail=PRIVATE)
        error = HTTPException(409, detail={"code": PRIVATE, "message": PRIVATE})
        if kind == "forged":
            error.safe_detail = {"code": "idempotency_key_reused", "message": PRIVATE}
        raise error

    return app


def test_json_log_allowlist_discards_private_messages_args_extras_and_traceback():
    formatter = SafeJsonFormatter()
    record = logging.LogRecord(PRIVATE, logging.ERROR, PRIVATE, 1, PRIVATE + " %s", (PRIVATE,), (ValueError, ValueError(PRIVATE), None))
    record.token = PRIVATE
    record.error_code = PRIVATE
    record.email = PRIVATE
    record.job_id = PRIVATE
    record.stack_info = PRIVATE
    text = formatter.format(record)
    assert PRIVATE not in text
    assert json.loads(text)["event"] == "external_log"
    SafeLogFilter().filter(record)
    assert record.args == () and record.exc_info is None and record.stack_info is None
    assert safe_error_code(PRIVATE) == "internal_error"
    assert safe_error_code("smtp_delivery_ambiguous") == "smtp_delivery_ambiguous"


def test_configured_named_third_party_sink_is_sanitized():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger("test.observability.transport")
    logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(logging.INFO)
    try:
        configure_logging("INFO")
        logger.error(PRIVATE, extra={"error_code": PRIVATE, "prompt": PRIVATE})
        assert PRIVATE not in stream.getvalue()
        assert json.loads(stream.getvalue())["event"] == "external_log"
        assert logging.getLogger("uvicorn.access").disabled
    finally:
        logger.removeHandler(handler)
        logger.propagate = True


async def test_concurrent_job_contexts_are_isolated_and_restored():
    pairs = [(uuid4(), uuid4()), (uuid4(), uuid4())]
    outputs = []

    async def log(job, request):
        with job_context(job, request_id=request):
            await asyncio.sleep(0)
            record = logging.LogRecord("test", logging.INFO, "", 1, "generation_started", (), None)
            outputs.append(json.loads(SafeJsonFormatter().format(record)))
            assert current_request_id() == request
        assert current_request_id() is None

    await asyncio.gather(*(log(*pair) for pair in pairs))
    assert {(item["job_id"], item["request_id"]) for item in outputs} == {(str(job), str(request)) for job, request in pairs}


async def test_request_ids_are_server_generated_and_only_route_templates_persist(session_factory):
    app = application(session_factory)
    incoming = str(uuid4())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/diagnostic/{PRIVATE}?token={PRIVATE}", headers={"X-Request-ID": incoming, "Authorization": f"Bearer {PRIVATE}"})
        unknown = await client.get(f"/{PRIVATE}")
    identifier = UUID(response.headers["X-Request-ID"])
    assert str(identifier) != incoming
    assert response.json()["request_id"] == str(identifier)
    assert unknown.status_code == 404
    async with session_factory() as db:
        records = list((await db.scalars(select(RequestEvent))).all())
    assert {row.route for row in records} == {"/diagnostic/{token}", "unmatched"}
    assert any(row.id == identifier for row in records)
    assert PRIVATE not in str([row.__dict__ for row in records])
    assert current_request_id() is None


@pytest.mark.parametrize("payload", [{"password": PRIVATE}, {"password": "xq123", PRIVATE: PRIVATE}])
async def test_request_validation_omits_private_input_context_and_extra_keys(session_factory, payload):
    app = application(session_factory)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/validated", json=payload)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"
    assert PRIVATE not in response.text and "xq123" not in response.text
    assert all(set(issue) == {"type", "loc", "msg"} for issue in response.json()["detail"])


def test_service_validation_sanitizes_values_validator_messages_and_locations():
    result = sanitize_validation([{"type": "value_error", "loc": ("body", PRIVATE), "msg": PRIVATE, "input": PRIVATE, "ctx": {"error": ValueError(PRIVATE)}}])
    assert result == [{"type": "value_error", "loc": ["body", "field"], "msg": "Invalid value"}]


@pytest.mark.parametrize("path,status", [("/unexpected", 500), ("/untrusted/string", 400), ("/untrusted/dict", 409), ("/untrusted/forged", 409)])
async def test_central_errors_omit_private_details_and_return_correlation(session_factory, path, status):
    app = application(session_factory)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)
    assert response.status_code == status
    assert PRIVATE not in response.text
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert response.headers["Cache-Control"] == "no-store"
    async with session_factory() as db:
        record = await db.get(RequestEvent, UUID(response.headers["X-Request-ID"]))
    assert record.error_code == response.json()["code"]


async def test_domain_conflict_keeps_typed_code_and_safe_detail(session_factory):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application(session_factory)), base_url="http://test") as client:
        response = await client.get("/domain")
    assert response.status_code == 409
    assert response.json()["detail"] == {"code": "idempotency_key_reused", "message": "This Idempotency-Key was already used for different job metadata."}


async def test_request_record_write_timeout_never_holds_response_indefinitely(session_factory, monkeypatch):
    async def blocked(*args):
        await asyncio.Event().wait()
    monkeypatch.setattr(operations, "record_request", blocked)
    started = monotonic()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application(session_factory)), base_url="http://test") as client:
        response = await client.get("/health/live")
    assert response.status_code == 200
    assert monotonic() - started < 2.0


async def test_local_and_database_worker_health_fresh_disabled_stale_and_draining(session_factory, tmp_path, monkeypatch):
    monkeypatch.setattr(operations.tempfile, "gettempdir", lambda: str(tmp_path))
    worker_id = f"health-{uuid4()}"
    await operations.pulse_worker(session_factory, worker_id=worker_id, kind="generation", status="disabled", stale_seconds=60)
    operations.check_local_worker_health("generation", 60)
    async with session_factory() as db:
        metrics = await operations.collect_metrics(db, settings())
    assert metrics["workers"][0]["healthy"] is True
    assert metrics["workers"][0]["status"] == "disabled"
    path = operations.worker_health_path("generation")
    payload = json.loads(path.read_text())
    assert set(payload) == {"kind", "status", "last_seen", "pid"}
    path.write_text(json.dumps(payload | {"last_seen": time() - 61}))
    with pytest.raises(ValueError, match="stale"):
        operations.check_local_worker_health("generation", 60)
    await operations.pulse_worker(session_factory, worker_id=worker_id, kind="generation", status="draining", stale_seconds=60)
    with pytest.raises(ValueError, match="not accepting"):
        operations.check_local_worker_health("generation", 60)
    async with session_factory() as db:
        metrics = await operations.collect_metrics(db, settings())
    assert metrics["workers"][0]["healthy"] is False


def test_windows_worker_probe_never_calls_os_kill(tmp_path, monkeypatch):
    path = tmp_path / "health.json"
    path.write_text(json.dumps({"kind": "email", "status": "running", "last_seen": time(), "pid": os.getpid()}))
    monkeypatch.setattr(operations, "worker_health_path", lambda kind: path)
    monkeypatch.setattr(operations.os, "name", "nt")
    monkeypatch.setattr(operations.os, "kill", lambda *args: pytest.fail("Windows kill must not be called"))
    operations.check_local_worker_health("email", 60)


async def seed_job(factory, *, origin=None):
    owner = User(id=uuid4(), email=f"obs-{uuid4().hex}@example.test", hashed_password="test-hash", role=UserRole.INSTRUCTOR)
    subject = Subject(id=uuid4(), name="Private subject", instructor_id=owner.id)
    async with factory() as db:
        async with db.begin():
            db.add_all([owner, subject])
            await db.flush()
        with job_context(uuid4(), request_id=origin):
            async with db.begin():
                job = await GenerationJobService(settings()).create_reservation(db, user_id=owner.id, data=GenerationJobCreate(subject_id=subject.id, set_title=PRIVATE, source_pdf_name="private.pdf", card_count=1), idempotency_key=f"obs-{uuid4().hex}")
    return job.id


async def test_generation_origin_is_durable_and_worker_logs_restore_it(session_factory, monkeypatch):
    origin = uuid4()
    identifier = await seed_job(session_factory, origin=origin)
    outputs = []

    class Worker(GenerationWorker):
        async def _process_claim(self, job_id, claim_token):
            assert current_request_id() == origin
            outputs.append(json.loads(SafeJsonFormatter().format(logging.LogRecord("test", logging.INFO, "", 1, "generation_failed", (), None))))
    worker = Worker(settings=settings(), session_factory=session_factory)
    await worker.process_claim(identifier, PRIVATE)
    assert outputs[0]["request_id"] == str(origin)
    assert outputs[0]["job_id"] == str(identifier)
    assert current_request_id() is None


async def test_retained_metrics_and_job_diagnostics_use_safe_columns(session_factory):
    identifier = await seed_job(session_factory, origin=uuid4())
    now = utcnow()
    async with session_factory() as db:
        async with db.begin():
            job = await db.get(GenerationJob, identifier)
            job.status = "completed"
            job.stage = "completed"
            job.progress = 100
            job.started_at = now - timedelta(seconds=2)
            job.completed_at = now
            job.generated_card_count = 1
            job.estimated_input_tokens = 100
            job.estimated_output_tokens = 50
            job.estimated_cost_microusd = 42
            db.add_all([RequestEvent(id=uuid4(), route="/safe", method="GET", status_code=200, latency_milliseconds=20, created_at=now), RequestEvent(id=uuid4(), route="/safe", method="GET", status_code=500, latency_milliseconds=40, error_code="internal_error", created_at=now), RequestEvent(id=uuid4(), route="/safe", method="GET", status_code=500, latency_milliseconds=99, created_at=now - timedelta(days=8))])
        metrics = await operations.operations_status(db, settings())
        diagnostic = await operations.operations_status(db, settings(), job_id=identifier)
        assert (await operations.operations_status(db, settings(), job_id=uuid4()))["status"] == "not_found"
    assert metrics["requests"]["count"] == 2
    assert metrics["requests"]["server_error_rate"] == 0.5
    assert metrics["requests"]["latency_milliseconds_average"] == 30
    assert metrics["generation"]["models"][0]["generated_card_count"] == 1
    assert metrics["generation"]["duration_milliseconds_average"] == 2000
    assert PRIVATE not in json.dumps(metrics) + json.dumps(diagnostic)
    assert "source_pdf_name" not in diagnostic["job"]
    payload = operations.telemetry_snapshot(metrics)
    assert all(type(value) in {int, float} for value in payload.values())
    assert payload["estimated_cost_microusd"] == 42


async def test_default_telemetry_has_no_queries_or_outgoing_requests(monkeypatch):
    monkeypatch.setattr(operations, "collect_metrics", lambda *args: pytest.fail("Disabled telemetry must not query metrics"))
    monkeypatch.setattr(operations.httpx, "AsyncClient", lambda **kwargs: pytest.fail("Disabled telemetry must not open a client"))
    assert await operations.report_telemetry(None, settings()) == {"status": "disabled"}


async def test_explicit_telemetry_posts_only_fixed_aggregate_numbers(session_factory, monkeypatch):
    calls = []
    class Client:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
            assert kwargs["timeout"] == 5
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, endpoint, *, json):
            calls.append(json)
            return httpx.Response(204, request=httpx.Request("POST", endpoint))
    monkeypatch.setattr(operations.httpx, "AsyncClient", Client)
    async with session_factory() as db:
        assert await operations.report_telemetry(db, settings(telemetry_enabled=True, telemetry_endpoint="https://telemetry.example.test/aggregate")) == {"status": "sent"}
    assert len(calls) == 1
    assert all(type(value) in {int, float} for value in calls[0].values())
    assert not {"request_id", "job_id", "routes", "model", "provider", "email", "exception"} & calls[0].keys()


def test_pdf_child_initializes_redaction_before_parser_warnings_and_sanitizes_pipe(monkeypatch):
    from app.services.pdf_processor import PDFProcessor, _extract_child
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger("pypdf.test.private-warning")
    logger.addHandler(handler)
    logger.propagate = False
    def parse(*args, **kwargs):
        logger.warning(PRIVATE)
        raise ValueError(PRIVATE)
    monkeypatch.setattr(PDFProcessor, "extract_text_from_bytes", parse)
    monkeypatch.setitem(sys.modules, "resource", SimpleNamespace(RLIMIT_AS=1, RLIMIT_CPU=2, setrlimit=lambda *args: None))
    messages = []
    connection = SimpleNamespace(send=messages.append, close=lambda: None)
    try:
        _extract_child(connection, PRIVATE.encode(), {}, 5, 512)
        assert PRIVATE not in stream.getvalue() + str(messages)
        assert messages == [(False, "pdf_processing_failed", "The PDF could not be processed safely.")]
        assert json.loads(stream.getvalue())["event"] == "external_log"
    finally:
        logger.removeHandler(handler)
        logger.propagate = True
