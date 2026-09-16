import asyncio
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app import healthcheck
from app.config import Settings
import app.main as main_module
from app.main import create_app
from app.workers.email import EmailWorker
from app.workers.generation import GenerationWorker


BASE_SETTINGS = {
    "database_url": "postgresql+asyncpg://user:password@database/app",
    "secret_key": "a-test-secret-with-real-entropy-1234567890",
    "generation_source_encryption_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
}


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **(BASE_SETTINGS | overrides))


@pytest.mark.parametrize(
    "origins",
    [
        "*",
        "null",
        "ftp://cards.example.test",
        "https://user@cards.example.test",
        "https://cards.example.test/",
        "https://cards.example.test/path",
        "https://cards.example.test?mode=one",
        "https://cards.example.test#fragment",
        "https://cards.example.test,https://cards.example.test:443",
    ],
)
def test_cors_origins_must_be_exact_http_origins(origins):
    with pytest.raises(ValidationError):
        make_settings(cors_origins=origins)


def test_cors_origins_are_normalized_and_production_requires_https():
    settings = make_settings(
        cors_origins="HTTPS://CARDS.EXAMPLE.TEST:443,http://127.0.0.1:5173"
    )
    assert settings.cors_origin_list == [
        "https://cards.example.test",
        "http://127.0.0.1:5173",
    ]

    with pytest.raises(ValidationError, match="must use HTTPS"):
        make_settings(
            environment="production",
            refresh_cookie_secure=True,
            frontend_base_url="https://cards.example.test",
            cors_origins="http://cards.example.test",
        )


@pytest.mark.parametrize("root_path", ["api", "/", "/api/", "/api//v1", "/api?debug=1"])
def test_api_root_path_is_an_empty_or_canonical_absolute_path(root_path):
    with pytest.raises(ValidationError):
        make_settings(api_root_path=root_path)


@pytest.mark.asyncio
async def test_production_docs_default_closed_and_explicit_override_uses_root_path():
    closed = create_app(
        make_settings(
            environment="production",
            refresh_cookie_secure=True,
            frontend_base_url="https://cards.example.test",
            cors_origins="https://cards.example.test",
            api_root_path="/api",
        )
    )
    assert closed.openapi_url is None
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=closed), base_url="http://test"
    ) as client:
        assert (await client.get("/docs")).status_code == 404
        root = await client.get("/")
        assert root.status_code == 200
        assert "docs" not in root.json()

    enabled = create_app(
        make_settings(
            environment="production",
            refresh_cookie_secure=True,
            frontend_base_url="https://cards.example.test",
            cors_origins="https://cards.example.test",
            api_docs_enabled=True,
            api_root_path="/api",
        )
    )
    assert enabled.openapi_url == "/openapi.json"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=enabled), base_url="http://test"
    ) as client:
        assert (await client.get("/docs")).status_code == 200
        assert (await client.get("/")).json()["docs"] == "/api/docs"


@pytest.mark.asyncio
async def test_cors_preflight_allows_only_the_browser_contract():
    application = create_app(make_settings(cors_origins="https://cards.example.test"))
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        allowed = await client.options(
            "/health/live",
            headers={
                "Origin": "https://cards.example.test",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "Authorization,Idempotency-Key",
            },
        )
        forbidden_method = await client.options(
            "/health/live",
            headers={
                "Origin": "https://cards.example.test",
                "Access-Control-Request-Method": "PATCH",
            },
        )
        forbidden_header = await client.options(
            "/health/live",
            headers={
                "Origin": "https://cards.example.test",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Unsafe",
            },
        )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://cards.example.test"
    assert forbidden_method.status_code == 400
    assert forbidden_header.status_code == 400


@pytest.mark.asyncio
async def test_liveness_is_process_only_and_readiness_is_database_aware(monkeypatch):
    calls = 0

    async def database_ready():
        nonlocal calls
        calls += 1

    monkeypatch.setattr(main_module, "check_database_readiness", database_ready)
    application = create_app(make_settings())
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/health/live")).status_code == 200
        assert (await client.get("/health/ready")).status_code == 200
        assert (await client.get("/health")).status_code == 200
    assert calls == 2

    async def database_down():
        raise OSError("database detail must not escape")

    monkeypatch.setattr(main_module, "check_database_readiness", database_down)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/health/live")).status_code == 200
        response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy"}
    assert "database detail" not in response.text


@pytest.mark.asyncio
async def test_non_http_healthcheck_always_disposes_the_engine(monkeypatch):
    closed = False

    async def database_down():
        raise OSError("unavailable")

    async def close_database():
        nonlocal closed
        closed = True

    monkeypatch.setattr(healthcheck, "check_database_readiness", database_down)
    monkeypatch.setattr(healthcheck, "close_database", close_database)
    with pytest.raises(OSError):
        await healthcheck.run_healthcheck()
    assert closed


def test_http_healthcheck_mode_supports_the_api_container(monkeypatch):
    class HealthyResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    monkeypatch.setattr(
        healthcheck.urllib.request,
        "urlopen",
        lambda url, timeout: HealthyResponse(),
    )
    assert healthcheck.main(["--url", "http://localhost:8000/health/ready"]) == 0


class _ControlledGenerationWorker(GenerationWorker):
    def __init__(self, settings):
        super().__init__(settings=settings, worker_id="phase8-generation")
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.finished = False
        self._claimed = False

    async def recover_and_cleanup(self):
        return None

    async def claim_next(self):
        if self._claimed:
            return None
        self._claimed = True
        return uuid4(), "claim"

    async def process_claim(self, job_id, claim_token):
        self.started.set()
        await self.release.wait()
        self.finished = True


class _ControlledEmailWorker(EmailWorker):
    def __init__(self, settings):
        super().__init__(settings=settings, worker_id="phase8-email")
        self.started = asyncio.Event()
        self.cancelled = False
        self._claimed = False

    async def recover_and_cleanup(self):
        return None

    async def claim_next(self):
        if self._claimed:
            return None
        self._claimed = True
        return uuid4(), "claim"

    async def process_claim(self, outbox_id, claim_token):
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise


@pytest.mark.asyncio
async def test_generation_worker_drains_short_active_work():
    worker = _ControlledGenerationWorker(
        make_settings(
            generation_worker_concurrency=1,
            generation_worker_poll_seconds=0.1,
            worker_shutdown_grace_seconds=0.5,
        )
    )
    stop_event = asyncio.Event()
    run_task = asyncio.create_task(worker.run(stop_event))
    await asyncio.wait_for(worker.started.wait(), timeout=1)
    stop_event.set()
    worker.release.set()
    await asyncio.wait_for(run_task, timeout=1)
    assert worker.finished


@pytest.mark.asyncio
async def test_email_worker_cancels_work_only_after_shutdown_grace():
    worker = _ControlledEmailWorker(
        make_settings(
            email_worker_concurrency=1,
            email_worker_poll_seconds=0.1,
            worker_shutdown_grace_seconds=0.01,
            smtp_host="mailpit",
            smtp_from_email="no-reply@example.com",
        )
    )
    stop_event = asyncio.Event()
    run_task = asyncio.create_task(worker.run(stop_event))
    await asyncio.wait_for(worker.started.wait(), timeout=1)
    stop_event.set()
    await asyncio.wait_for(run_task, timeout=1)
    assert worker.cancelled
