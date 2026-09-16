"""Transactional-email unit and SQLite worker proofs."""

from datetime import timedelta
import smtplib
import ssl
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.cli import email_outbox_status, retry_email
from app.config import Settings
from app.models.email import EmailOutboxMessage, EmailOutboxStatus
from app.models.subject import Subject
from app.models.user import PasswordResetToken, User, UserRole
from app.services.auth import AuthService
from app.services.email import (
    EmailDeliveryError,
    EmailOutboxService,
    EmailTemplates,
    SmtpTransport,
    TransactionalEmail,
)
from app.time_utils import utcnow
from app.workers.email import EmailLeaseLost, EmailWorker


def email_settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "database_url": "sqlite+aiosqlite:///:memory:",
        "secret_key": "test-only-secret-key-with-adequate-entropy-1234567890",
        "generation_source_encryption_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "frontend_base_url": "https://cards.example.test",
        "smtp_host": "smtp.example.test",
        "smtp_port": 2525,
        "smtp_from_email": "no-reply@example.com",
        "smtp_timeout_seconds": 1,
        "email_lease_seconds": 12,
        "email_retry_base_seconds": 0.1,
        "email_retry_max_seconds": 1,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def seed_user_and_reset(db) -> tuple[User, PasswordResetToken]:
    user = User(
        id=uuid4(),
        email=f"email-delivery-{uuid4().hex}@example.com",
        hashed_password=AuthService.hash_password("old password value"),
        role=UserRole.STUDENT,
    )
    db.add(user)
    await db.flush()
    reset, _ = await AuthService.create_password_reset_token(db, user)
    return user, reset


def test_smtp_configuration_rejects_unsafe_or_incomplete_modes():
    with pytest.raises(ValidationError):
        email_settings(smtp_username="mailer", smtp_password="secret", smtp_starttls=False)
    with pytest.raises(ValidationError):
        email_settings(smtp_starttls=True, smtp_implicit_tls=True)
    with pytest.raises(ValidationError):
        email_settings(smtp_host="smtp.example.test\r\nBcc: victim@example.test")
    with pytest.raises(ValueError):
        email_settings(smtp_host=None).require_email_delivery_config()
    with pytest.raises(ValueError):
        email_settings(
            environment="production",
            frontend_base_url="https://cards.example.test",
            refresh_cookie_secure=True,
            cors_origins="https://cards.example.test",
            smtp_host="mailpit",
        ).require_email_delivery_config()


def test_templates_are_multipart_safe_escaped_and_keep_a_visible_link():
    reset_url = "https://cards.example.test/reset-password?token=opaque%2Btoken"
    message = EmailTemplates.password_reset(
        app_name="Cards & Notes",
        recipient="STUDENT@EXAMPLE.COM",
        reset_url=reset_url,
        expires_minutes=30,
        message_id="<email-delivery@example.com>",
    )
    assert message.recipient == "student@example.com"
    assert reset_url in message.text_body
    assert "Cards &amp; Notes" in message.html_body
    assert "opaque%2Btoken" in message.html_body


class FakeSmtp:
    def __init__(self, *args, failure=None, calls=None, **kwargs):
        self.failure = failure
        self.calls = calls if calls is not None else []
        self.calls.append(("connect", args, kwargs))

    def ehlo(self):
        self.calls.append(("ehlo",))

    def starttls(self, **kwargs):
        self.calls.append(("starttls", kwargs))

    def login(self, username, password):
        self.calls.append(("login", username, password))

    def send_message(self, message, **kwargs):
        self.calls.append(("send", message, kwargs))
        if self.failure:
            raise self.failure

    def quit(self):
        self.calls.append(("quit",))

    def close(self):
        self.calls.append(("close",))


def sample_message() -> TransactionalEmail:
    return TransactionalEmail(
        recipient="student@example.com",
        subject="Security notification",
        text_body="Plain text\n",
        html_body="<p>HTML</p>",
        message_id="<email-delivery@example.com>",
    )


@pytest.mark.parametrize(
    ("mode", "expected_call"),
    [("none", "send"), ("starttls", "starttls"), ("implicit", "ssl-connect")],
)
def test_smtp_transport_supports_none_starttls_and_implicit_tls(mode, expected_call):
    calls = []

    def plain_factory(*args, **kwargs):
        return FakeSmtp(*args, calls=calls, **kwargs)

    def ssl_factory(*args, **kwargs):
        calls.append(("ssl-connect", args, kwargs))
        return FakeSmtp(*args, calls=calls, **kwargs)

    settings = email_settings(
        smtp_starttls=mode == "starttls",
        smtp_implicit_tls=mode == "implicit",
    )
    transport = SmtpTransport(
        settings, smtp_factory=plain_factory, smtp_ssl_factory=ssl_factory
    )
    transport._send_blocking(sample_message())
    call_names = [entry[0] for entry in calls]
    assert expected_call in call_names
    assert "send" in call_names


@pytest.mark.parametrize(
    ("failure", "code", "retryable"),
    [
        (smtplib.SMTPServerDisconnected("private server detail"), "smtp_delivery_ambiguous", False),
        (smtplib.SMTPDataError(451, b"private rejection detail"), "smtp_temporary_rejection", True),
        (smtplib.SMTPDataError(550, b"private rejection detail"), "smtp_rejected", False),
        (
            smtplib.SMTPRecipientsRefused(
                {"student@example.com": (451, b"private rejection detail")}
            ),
            "smtp_temporary_rejection",
            True,
        ),
        (smtplib.SMTPAuthenticationError(535, b"private auth detail"), "smtp_authentication_failed", False),
        (ssl.SSLError("private certificate detail"), "smtp_tls_failed", False),
    ],
)
def test_smtp_failures_are_sanitized_and_classified(failure, code, retryable):
    def factory(*args, **kwargs):
        return FakeSmtp(*args, failure=failure, **kwargs)

    transport = SmtpTransport(email_settings(), smtp_factory=factory)
    with pytest.raises(EmailDeliveryError) as error:
        transport._send_blocking(sample_message())
    assert error.value.code == code
    assert error.value.retryable is retryable
    assert "private" not in str(error.value)


@pytest.mark.parametrize(
    ("failure", "code", "retryable"),
    [
        (TimeoutError("private timeout detail"), "smtp_connection_failed", True),
        (smtplib.SMTPServerDisconnected("private disconnect"), "smtp_disconnected", True),
    ],
)
def test_smtp_connect_failures_are_retryable_and_sanitized(failure, code, retryable):
    def factory(*args, **kwargs):
        raise failure

    transport = SmtpTransport(email_settings(), smtp_factory=factory)
    with pytest.raises(EmailDeliveryError) as error:
        transport._send_blocking(sample_message())
    assert error.value.code == code
    assert error.value.retryable is retryable
    assert "private" not in str(error.value)


async def test_outbox_is_idempotent_and_does_not_persist_secret_content(db):
    user, reset = await seed_user_and_reset(db)
    service = EmailOutboxService(email_settings())
    first = await service.queue_password_reset(db, user=user, reset=reset)
    replay = await service.queue_password_reset(db, user=user, reset=reset)
    await db.commit()

    assert replay.id == first.id
    assert await db.scalar(select(func.count(EmailOutboxMessage.id))) == 1
    columns = set(EmailOutboxMessage.__table__.columns.keys())
    assert not {"token", "reset_url", "invitation_url", "text_body", "html_body"} & columns
    assert first.idempotency_key_hash != str(reset.id)


class CapturingTransport:
    def __init__(self, failure: Exception | None = None):
        self.failure = failure
        self.messages = []

    async def send(self, message):
        self.messages.append(message)
        if self.failure:
            raise self.failure


async def queued_reset(factory, settings) -> object:
    async with factory() as db:
        async with db.begin():
            user, reset = await seed_user_and_reset(db)
            outbox = await EmailOutboxService(settings).queue_password_reset(
                db, user=user, reset=reset
            )
            return outbox.id


async def test_worker_claims_composes_and_marks_success_once(session_factory):
    settings = email_settings()
    outbox_id = await queued_reset(session_factory, settings)
    transport = CapturingTransport()
    worker = EmailWorker(
        settings=settings,
        session_factory=session_factory,
        transport=transport,
        worker_id="email-delivery-success",
    )
    claim = await worker.claim_next()
    assert claim is not None
    await worker.process_claim(*claim)

    async with session_factory() as db:
        sent = await db.get(EmailOutboxMessage, outbox_id)
        assert sent.status == EmailOutboxStatus.SENT.value
        assert sent.attempt_count == 1
        assert sent.delivery_started_at is not None
        assert sent.claim_token is None
    assert len(transport.messages) == 1
    assert "/reset-password?token=" in transport.messages[0].text_body
    with pytest.raises(EmailLeaseLost):
        await worker._finish_success(*claim)


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (EmailDeliveryError("smtp_connection_failed", retryable=True), "pending"),
        (EmailDeliveryError("smtp_delivery_ambiguous", retryable=False), "failed"),
    ],
)
async def test_worker_retries_only_unambiguous_transient_failures(
    session_factory, error, expected_status
):
    settings = email_settings(email_max_attempts=2)
    outbox_id = await queued_reset(session_factory, settings)
    worker = EmailWorker(
        settings=settings,
        session_factory=session_factory,
        transport=CapturingTransport(error),
        worker_id="email-delivery-failure",
    )
    claim = await worker.claim_next()
    assert claim is not None
    await worker.process_claim(*claim)

    async with session_factory() as db:
        outbox = await db.get(EmailOutboxMessage, outbox_id)
        assert outbox.status == expected_status
        assert outbox.last_error_code == error.code
        assert outbox.claim_token is None
        if expected_status == EmailOutboxStatus.PENDING.value:
            assert outbox.delivery_started_at is None
        else:
            assert outbox.failed_at is not None


async def test_worker_logs_exclude_recipient_body_url_and_provider_detail(
    session_factory, caplog
):
    settings = email_settings(email_max_attempts=1)
    outbox_id = await queued_reset(session_factory, settings)
    private_detail = (
        "student@example.com https://cards.example.com/reset-password?token=secret-value"
    )
    worker = EmailWorker(
        settings=settings,
        session_factory=session_factory,
        transport=CapturingTransport(RuntimeError(private_detail)),
        worker_id="email-delivery-safe-logs",
    )
    caplog.set_level("INFO")
    claim = await worker.claim_next()
    assert claim is not None
    await worker.process_claim(*claim)

    log_text = caplog.text
    assert str(outbox_id) in log_text
    assert "email_internal_error" in log_text
    for secret in ("student@example.com", "reset-password", "secret-value"):
        assert secret not in log_text


async def test_expired_lease_after_delivery_is_not_automatically_retried(session_factory):
    settings = email_settings()
    outbox_id = await queued_reset(session_factory, settings)
    worker = EmailWorker(
        settings=settings,
        session_factory=session_factory,
        transport=CapturingTransport(),
        worker_id="email-delivery-abandoned",
    )
    claim = await worker.claim_next()
    assert claim is not None
    async with session_factory() as db:
        async with db.begin():
            outbox = await db.get(EmailOutboxMessage, outbox_id)
            outbox.delivery_started_at = utcnow()
            outbox.lease_expires_at = utcnow() - timedelta(seconds=1)
    await worker.recover_and_cleanup()

    async with session_factory() as db:
        outbox = await db.get(EmailOutboxMessage, outbox_id)
        assert outbox.status == EmailOutboxStatus.FAILED.value
        assert outbox.last_error_code == "smtp_delivery_ambiguous"


async def test_cleanup_expires_pending_events_and_removes_old_terminal_rows(session_factory):
    settings = email_settings(email_sent_retention_days=1, email_failed_retention_days=1)
    pending_id = await queued_reset(session_factory, settings)
    old_sent_id = await queued_reset(session_factory, settings)
    async with session_factory() as db:
        async with db.begin():
            pending = await db.get(EmailOutboxMessage, pending_id)
            pending.expires_at = utcnow() - timedelta(seconds=1)
            old_sent = await db.get(EmailOutboxMessage, old_sent_id)
            old_sent.status = EmailOutboxStatus.SENT.value
            old_sent.sent_at = utcnow() - timedelta(days=2)

    worker = EmailWorker(
        settings=settings,
        session_factory=session_factory,
        transport=CapturingTransport(),
        worker_id="email-delivery-cleanup",
    )
    await worker.recover_and_cleanup()
    async with session_factory() as db:
        expired = await db.get(EmailOutboxMessage, pending_id)
        assert expired.status == EmailOutboxStatus.FAILED.value
        assert expired.last_error_code == "email_event_expired"
        assert await db.get(EmailOutboxMessage, old_sent_id) is None


async def test_reset_and_outbox_share_one_rollback_boundary(db):
    user = User(
        id=uuid4(),
        email="atomic-reset@example.com",
        hashed_password=AuthService.hash_password("old password value"),
        role=UserRole.STUDENT,
    )
    db.add(user)
    await db.commit()
    settings = email_settings()

    with pytest.raises(RuntimeError):
        async with db.begin():
            reset, _ = await AuthService.create_password_reset_token(db, user)
            await EmailOutboxService(settings).queue_password_reset(db, user=user, reset=reset)
            raise RuntimeError("force rollback")

    assert await db.scalar(select(func.count(PasswordResetToken.id))) == 0
    assert await db.scalar(select(func.count(EmailOutboxMessage.id))) == 0


async def test_operator_retry_is_guarded_for_ambiguous_delivery(session_factory, monkeypatch):
    settings = email_settings()
    outbox_id = await queued_reset(session_factory, settings)
    async with session_factory() as db:
        async with db.begin():
            outbox = await db.get(EmailOutboxMessage, outbox_id)
            outbox.status = EmailOutboxStatus.FAILED.value
            outbox.failed_at = utcnow()
            outbox.last_error_code = "smtp_delivery_ambiguous"

    monkeypatch.setattr("app.cli.async_session_maker", session_factory)
    with pytest.raises(SystemExit, match="may already have succeeded"):
        await retry_email(outbox_id, allow_ambiguous=False)
    await retry_email(outbox_id, allow_ambiguous=True)

    async with session_factory() as db:
        outbox = await db.get(EmailOutboxMessage, outbox_id)
        assert outbox.status == EmailOutboxStatus.PENDING.value
        assert outbox.failed_at is None
        assert outbox.last_error_code is None


async def test_operator_status_does_not_print_recipient(session_factory, monkeypatch, capsys):
    settings = email_settings()
    outbox_id = await queued_reset(session_factory, settings)
    async with session_factory() as db:
        async with db.begin():
            outbox = await db.get(EmailOutboxMessage, outbox_id)
            outbox.status = EmailOutboxStatus.FAILED.value
            outbox.failed_at = utcnow()
            outbox.last_error_code = "smtp_rejected"

    monkeypatch.setattr("app.cli.async_session_maker", session_factory)
    await email_outbox_status(20)
    output = capsys.readouterr().out
    assert str(outbox_id) in output
    assert "smtp_rejected" in output
    assert "@example.com" not in output


async def test_invitation_event_is_bound_to_recipient_and_domain_record(db):
    instructor = User(
        id=uuid4(),
        email="email-delivery-instructor@example.com",
        hashed_password="unused",
        role=UserRole.INSTRUCTOR,
    )
    subject = Subject(id=uuid4(), name="Security <Basics>", instructor_id=instructor.id)
    db.add_all([instructor, subject])
    await db.flush()
    invite, token = await AuthService.create_invitation(
        db,
        instructor.id,
        subject.id,
        24,
        recipient_email="INVITED@EXAMPLE.COM",
    )
    outbox = await EmailOutboxService(email_settings()).queue_student_invitation(
        db, invite=invite
    )
    await db.commit()

    claims = AuthService.verify_invitation_token(token)
    assert claims.email == "invited@example.com"
    assert outbox.recipient_email == "invited@example.com"
