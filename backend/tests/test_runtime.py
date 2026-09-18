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


def test_ai_admission_uses_non_secret_flag_and_worker_validates_credentials():
    disabled_with_key = make_settings(
        flashcard_ai_provider_enabled=False,
        flashcard_ai_api_key="worker-only-key",
    )
    assert disabled_with_key.flashcard_ai_provider_configured is True
    assert disabled_with_key.flashcard_ai_provider_enabled is False

    enabled_without_key = make_settings(
        flashcard_ai_provider_enabled=True,
        flashcard_ai_api_key=None,
    )
    assert enabled_without_key.flashcard_ai_provider_configured is False
    assert enabled_without_key.flashcard_ai_provider_enabled is True
    with pytest.raises(ValueError, match="Enabled Gemini generation requires"):
        enabled_without_key.require_generation_worker_config()

    enabled_with_key = make_settings(
        flashcard_ai_provider_enabled=True,
        flashcard_ai_api_key="worker-only-key",
        flashcard_ai_quota_bucket="test-flashcards",
    )
    assert enabled_with_key.flashcard_ai_provider_configured is True
    assert enabled_with_key.require_generation_worker_config() is enabled_with_key

    enabled_keyless_local_endpoint = make_settings(
        flashcard_ai_provider_enabled=True,
        flashcard_ai_provider="openai_compatible",
        flashcard_ai_base_url="http://model:11434/v1",
        flashcard_ai_api_key=None,
        flashcard_ai_quota_bucket="test-flashcards",
    )
    assert (
        enabled_keyless_local_endpoint.require_generation_worker_config()
        is enabled_keyless_local_endpoint
    )


@pytest.mark.parametrize("rag_enabled,answer_enabled,embedding_enabled", [
    (rag, answer, embedding)
    for rag in (False, True) for answer in (False, True) for embedding in (False, True)
])
def test_rag_flag_matrix_suspends_only_affected_roles(rag_enabled, answer_enabled, embedding_enabled):
    configured = make_settings(
        rag_enabled=rag_enabled,
        rag_ai_provider_enabled=answer_enabled,
        rag_embedding_provider_enabled=embedding_enabled,
    )
    assert configured.rag_index_available is (rag_enabled and embedding_enabled)
    assert configured.rag_answer_available is (rag_enabled and answer_enabled and embedding_enabled)
    # Disabled roles require no key/bucket and never enable a different role.
    if not rag_enabled or not embedding_enabled:
        assert configured.require_rag_index_worker_config() is configured
    else:
        with pytest.raises(ValueError, match="RAG_EMBEDDING_API_KEY"):
            configured.require_rag_index_worker_config()
    if not rag_enabled or not answer_enabled:
        assert configured.require_rag_answer_worker_config() is configured
    elif not embedding_enabled:
        with pytest.raises(ValueError, match="RAG_EMBEDDING_PROVIDER_ENABLED"):
            configured.require_rag_answer_worker_config()
    else:
        with pytest.raises(ValueError, match="RAG_AI_API_KEY"):
            configured.require_rag_answer_worker_config()


def test_enabled_role_keys_and_explicit_quota_buckets_are_independent():
    configured = make_settings(
        flashcard_ai_provider_enabled=True, flashcard_ai_api_key="flashcard-key",
        flashcard_ai_quota_bucket="flashcard-budget",
        rag_enabled=True, rag_ai_provider_enabled=True, rag_embedding_provider_enabled=True,
        rag_ai_api_key="answer-key", rag_embedding_api_key="embedding-key",
        rag_ai_quota_bucket="answer-budget", rag_embedding_quota_bucket="embedding-budget",
    )
    assert configured.require_generation_worker_config() is configured
    assert configured.require_rag_index_worker_config() is configured
    assert configured.require_rag_answer_worker_config() is configured
    for role, changes, code in (
        ("flashcard", {"flashcard_ai_quota_bucket": ""}, "FLASHCARD_AI_QUOTA_BUCKET"),
        ("index", {"rag_embedding_api_key": None}, "RAG_EMBEDDING_API_KEY"),
        ("index", {"rag_embedding_quota_bucket": ""}, "RAG_EMBEDDING_QUOTA_BUCKET"),
        ("answer", {"rag_ai_api_key": None}, "RAG_AI_API_KEY"),
        ("answer", {"rag_ai_quota_bucket": ""}, "RAG_AI_QUOTA_BUCKET"),
    ):
        changed = configured.model_copy(update=changes)
        method = {
            "flashcard": changed.require_generation_worker_config,
            "index": changed.require_rag_index_worker_config,
            "answer": changed.require_rag_answer_worker_config,
        }[role]
        with pytest.raises(ValueError, match=code):
            method()

    # Matching keys are allowed only when deliberately set on both profiles;
    # no method copies them from another role.
    missing_query = configured.model_copy(update={"rag_embedding_api_key": None})
    with pytest.raises(ValueError, match="RAG_EMBEDDING_API_KEY"):
        missing_query.require_rag_answer_worker_config()
    assert "answer-key" not in repr(configured)
    assert "embedding-key" not in repr(configured)
    assert "flashcard-key" not in repr(configured)


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
        super().__init__(settings=settings, worker_id="runtime-generation")
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.finished = False
        self._claimed = False
        self.claim_calls = 0

    async def recover_and_cleanup(self):
        return None

    async def claim_next(self):
        self.claim_calls += 1
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
        super().__init__(settings=settings, worker_id="runtime-email")
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
async def test_disabled_generation_worker_waits_without_claiming_jobs():
    worker = _ControlledGenerationWorker(
        make_settings(
            flashcard_ai_provider_enabled=False,
            generation_worker_poll_seconds=0.1,
        )
    )
    stop_event = asyncio.Event()
    run_task = asyncio.create_task(worker.run(stop_event))
    await asyncio.sleep(0.02)
    assert worker.claim_calls == 0
    assert worker.started.is_set() is False

    stop_event.set()
    await asyncio.wait_for(run_task, timeout=1)


@pytest.mark.asyncio
async def test_generation_worker_drains_short_active_work():
    worker = _ControlledGenerationWorker(
        make_settings(
            flashcard_ai_provider_enabled=True,
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
            flashcard_ai_provider_enabled=True,
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
