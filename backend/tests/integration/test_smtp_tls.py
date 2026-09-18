"""Opt-in actual TLS SMTP/outbox checks, using disposable local capture only."""
import asyncio
from datetime import timedelta
import os
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text

from app.cli import retry_email
from app.config import Settings
from app.models.email import EmailOutboxMessage, EmailOutboxStatus
from app.models.user import User, UserRole
from app.services.auth import AuthService
from app.services.email import EmailOutboxService, SmtpTransport
from app.time_utils import utcnow
from app.workers.email import EmailWorker

pytestmark = [pytest.mark.postgres, pytest.mark.smtp_tls]


@pytest_asyncio.fixture(params=["starttls", "implicit"])
async def tls_environment(request, postgres_engine, postgres_session_factory, postgres_test_database_url):
    mode = request.param
    tcp_port = os.getenv(f"SMTP_TLS_TEST_{mode.upper()}_PORT")
    api_url = os.getenv(f"SMTP_TLS_TEST_{mode.upper()}_API")
    password = os.getenv("SMTP_TLS_TEST_PASSWORD")
    if not all((tcp_port, api_url, password, os.getenv("SSL_CERT_FILE"))):
        pytest.skip("Disposable TLS SMTP verification is not configured")
    parsed_api = urlsplit(api_url)
    if (
        parsed_api.scheme != "http" or parsed_api.hostname != "127.0.0.1"
        or not parsed_api.port or parsed_api.username or parsed_api.password
        or parsed_api.path or parsed_api.query or parsed_api.fragment
    ):
        pytest.fail("TLS SMTP tests require a disposable loopback capture API", pytrace=False)
    settings = Settings(
        _env_file=None, environment="production", database_url=postgres_test_database_url,
        secret_key=os.environ["SECRET_KEY"],
        generation_source_encryption_key=os.environ["GENERATION_SOURCE_ENCRYPTION_KEY"],
        flashcard_ai_provider_enabled=False, flashcard_ai_model="gemini-2.5-flash",
        debug=False, refresh_cookie_secure=True,
        frontend_base_url="https://cards.example.test", cors_origins="https://cards.example.test",
        smtp_host="127.0.0.1", smtp_port=int(tcp_port), smtp_from_email="no-reply@example.com",
        smtp_starttls=mode == "starttls", smtp_implicit_tls=mode == "implicit",
        smtp_username="qa", smtp_password=password, smtp_timeout_seconds=2,
        email_lease_seconds=24, email_retry_base_seconds=0.1, email_retry_max_seconds=1,
    )
    settings.require_email_delivery_config()
    async with httpx.AsyncClient(base_url=api_url, timeout=5) as client:
        (await client.get("/readyz")).raise_for_status()
        (await client.delete("/api/v1/messages")).raise_for_status()
        (await client.put("/api/v1/chaos", json={})).raise_for_status()
    try:
        yield postgres_session_factory, settings, api_url
    finally:
        async with httpx.AsyncClient(base_url=api_url, timeout=5) as client:
            (await client.put("/api/v1/chaos", json={})).raise_for_status()
        async with postgres_engine.begin() as connection:
            await connection.execute(text("DELETE FROM users WHERE email LIKE 'smtp-tls-%@example.com'"))


async def queued_reset(factory, settings):
    async with factory() as db:
        async with db.begin():
            user = User(email=f"smtp-tls-{uuid4().hex}@example.com", hashed_password="unused", role=UserRole.STUDENT)
            db.add(user)
            await db.flush()
            reset, _ = await AuthService.create_password_reset_token(db, user)
            outbox = await EmailOutboxService(settings).queue_password_reset(db, user=user, reset=reset)
            return outbox.id


def worker(factory, settings):
    return EmailWorker(settings=settings, session_factory=factory, transport=SmtpTransport(settings), worker_id=f"smtp-tls-{uuid4().hex}")


async def process_next(instance, outbox_id):
    claim = await instance.claim_next()
    assert claim is not None and claim[0] == outbox_id
    await instance.process_claim(*claim)


async def message_count(api_url):
    async with httpx.AsyncClient(base_url=api_url, timeout=5) as client:
        response = await client.get("/api/v1/messages")
        response.raise_for_status()
        return len(response.json().get("messages", []))


async def test_authenticated_tls_delivers_and_commits_once(tls_environment):
    factory, settings, api_url = tls_environment
    outbox_id = await queued_reset(factory, settings)
    instance = worker(factory, settings)
    await process_next(instance, outbox_id)
    async with factory() as db:
        outbox = await db.get(EmailOutboxMessage, outbox_id)
        assert outbox.status == EmailOutboxStatus.SENT.value
        assert outbox.attempt_count == 1 and outbox.sent_at is not None
        assert outbox.claim_token is None and outbox.last_error_code is None
    assert await instance.claim_next() is None
    assert await message_count(api_url) == 1


@pytest.mark.parametrize("failure", ["untrusted_ca", "wrong_hostname"])
async def test_certificate_validation_failure_is_terminal(tls_environment, monkeypatch, failure):
    factory, settings, api_url = tls_environment
    if failure == "untrusted_ca":
        monkeypatch.setenv("SSL_CERT_FILE", os.environ["SMTP_TLS_TEST_UNTRUSTED_CA"])
    else:
        # Certificate SAN deliberately contains only 127.0.0.1, not localhost.
        settings = settings.model_copy(update={"smtp_host": "localhost"})
    outbox_id = await queued_reset(factory, settings)
    instance = worker(factory, settings)
    await process_next(instance, outbox_id)
    async with factory() as db:
        outbox = await db.get(EmailOutboxMessage, outbox_id)
        assert outbox.status == EmailOutboxStatus.FAILED.value
        assert outbox.last_error_code == "smtp_tls_failed"
        assert outbox.attempt_count == 1 and outbox.claim_token is None
    assert await instance.claim_next() is None
    assert await message_count(api_url) == 0


async def test_temporary_smtp_rejection_recovers_with_same_durable_event(tls_environment):
    factory, settings, api_url = tls_environment
    outbox_id = await queued_reset(factory, settings)
    instance = worker(factory, settings)
    async with httpx.AsyncClient(base_url=api_url, timeout=5) as client:
        (await client.put("/api/v1/chaos", json={"Recipient": {"ErrorCode": 451, "Probability": 100}})).raise_for_status()
        await process_next(instance, outbox_id)
        (await client.put("/api/v1/chaos", json={})).raise_for_status()
    async with factory() as db:
        outbox = await db.get(EmailOutboxMessage, outbox_id)
        assert outbox.status == EmailOutboxStatus.PENDING.value
        assert outbox.last_error_code == "smtp_temporary_rejection"
        assert outbox.attempt_count == 1 and outbox.delivery_started_at is None
        message_id = outbox.message_id
    assert await message_count(api_url) == 0
    await asyncio.sleep(0.15)  # Greater than the injected bounded 0.1-second first retry.
    await process_next(instance, outbox_id)
    async with factory() as db:
        outbox = await db.get(EmailOutboxMessage, outbox_id)
        assert outbox.status == EmailOutboxStatus.SENT.value
        assert outbox.attempt_count == 2 and outbox.message_id == message_id
        assert outbox.last_error_code is None
    assert await message_count(api_url) == 1


async def test_authentication_failure_can_be_explicitly_recovered(tls_environment, monkeypatch):
    factory, settings, api_url = tls_environment
    outbox_id = await queued_reset(factory, settings)
    failed_settings = Settings(_env_file=None, **(settings.model_dump() | {"smtp_password": "wrong-disposable-password"}))
    failed_worker = worker(factory, failed_settings)
    await process_next(failed_worker, outbox_id)
    async with factory() as db:
        outbox = await db.get(EmailOutboxMessage, outbox_id)
        assert outbox.status == EmailOutboxStatus.FAILED.value
        assert outbox.last_error_code == "smtp_authentication_failed"
    assert await failed_worker.claim_next() is None
    assert await message_count(api_url) == 0
    monkeypatch.setattr("app.cli.async_session_maker", factory)
    await retry_email(outbox_id, allow_ambiguous=False)
    await process_next(worker(factory, settings), outbox_id)
    async with factory() as db:
        outbox = await db.get(EmailOutboxMessage, outbox_id)
        assert outbox.status == EmailOutboxStatus.SENT.value and outbox.attempt_count == 2
    assert await message_count(api_url) == 1


async def test_accepted_tls_mail_with_lost_worker_lease_requires_operator_review(tls_environment, monkeypatch):
    factory, settings, api_url = tls_environment
    outbox_id = await queued_reset(factory, settings)
    instance = worker(factory, settings)
    claim = await instance.claim_next()
    assert claim is not None and claim[0] == outbox_id
    async with factory() as db:
        outbox = await instance._claimed(db, *claim)
        message = await instance.composer.compose(db, outbox)
    await instance._mark_delivery_started(*claim)
    await instance.transport.send(message)  # Real authenticated, certificate-validated TLS.
    assert await message_count(api_url) == 1
    # Rehearse worker interruption after SMTP acceptance, before success commits.
    async with factory() as db:
        async with db.begin():
            outbox = await db.get(EmailOutboxMessage, outbox_id)
            outbox.lease_expires_at = utcnow() - timedelta(seconds=1)
    await instance.recover_and_cleanup()
    async with factory() as db:
        outbox = await db.get(EmailOutboxMessage, outbox_id)
        assert outbox.status == EmailOutboxStatus.FAILED.value
        assert outbox.last_error_code == "smtp_delivery_ambiguous" and outbox.attempt_count == 1
    assert await instance.claim_next() is None
    monkeypatch.setattr("app.cli.async_session_maker", factory)
    with pytest.raises(SystemExit, match="may already have succeeded"):
        await retry_email(outbox_id, allow_ambiguous=False)
    assert await message_count(api_url) == 1
