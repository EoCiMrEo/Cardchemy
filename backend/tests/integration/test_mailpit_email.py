"""Opt-in request-to-SMTP integration against PostgreSQL and Mailpit."""

import asyncio
import os
import re
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings
from app.database import get_db
from app.main import app
from app.models.email import EmailOutboxMessage, EmailOutboxStatus
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.services.auth import AuthService
from app.services.email import EmailOutboxService, SmtpTransport
from app.time_utils import utcnow
from app.services.rate_limit import rate_limiter
from app.workers.email import EmailWorker


pytestmark = [pytest.mark.postgres, pytest.mark.mailpit]


@pytest_asyncio.fixture
async def mailpit_environment():
    database_url = os.getenv("POSTGRES_TEST_DATABASE_URL")
    api_url = os.getenv("MAILPIT_API_URL")
    smtp_host = os.getenv("MAILPIT_SMTP_HOST")
    if not database_url or not api_url or not smtp_host:
        pytest.skip("PostgreSQL and Mailpit integration settings are not configured")

    engine = create_async_engine(database_url, pool_size=8, max_overflow=0)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != "20260915_0005":
            pytest.fail(f"PostgreSQL test database is at Alembic revision {revision!r}")
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "DELETE FROM rate_limit_buckets WHERE scope IN "
                    "('login', 'password-reset', 'invitation', 'join')"
                )
            )

        async with httpx.AsyncClient(base_url=api_url, timeout=5) as mailpit:
            ready = await mailpit.get("/readyz")
            ready.raise_for_status()
            cleared = await mailpit.delete("/api/v1/messages")
            cleared.raise_for_status()

        yield factory, integration_settings(database_url, smtp_host), api_url
    finally:
        app.dependency_overrides.clear()
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM users WHERE email LIKE 'mailpit-%@example.com'")
            )
        await engine.dispose()


def integration_settings(database_url: str, smtp_host: str) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=database_url,
        secret_key=os.environ["SECRET_KEY"],
        generation_source_encryption_key=os.environ["GENERATION_SOURCE_ENCRYPTION_KEY"],
        frontend_base_url=os.getenv("FRONTEND_BASE_URL", "http://frontend"),
        smtp_host=smtp_host,
        smtp_port=int(os.getenv("MAILPIT_SMTP_PORT", "1025")),
        smtp_from_email="no-reply@example.com",
        smtp_timeout_seconds=5,
        email_lease_seconds=60,
        email_worker_poll_seconds=0.1,
    )


def install_database_override(factory):
    async def override_db():
        async with factory() as db:
            try:
                yield db
            except Exception:
                await db.rollback()
                raise
            finally:
                if db.in_transaction():
                    await db.rollback()

    app.dependency_overrides[get_db] = override_db
    rate_limiter.session_factory = factory


async def deliver_next(factory, settings):
    worker = EmailWorker(
        settings=settings,
        session_factory=factory,
        transport=SmtpTransport(settings),
        worker_id=f"mailpit-{uuid4().hex[:12]}",
    )
    claim = await worker.claim_next()
    assert claim is not None
    await worker.process_claim(*claim)
    async with factory() as db:
        sent = await db.get(EmailOutboxMessage, claim[0])
        assert sent.status == EmailOutboxStatus.SENT.value
    return claim[0]


async def mailpit_messages(api_url: str, expected: int):
    async with httpx.AsyncClient(base_url=api_url, timeout=5) as client:
        for _ in range(30):
            response = await client.get("/api/v1/messages")
            response.raise_for_status()
            messages = response.json().get("messages", [])
            if len(messages) >= expected:
                return messages
            await asyncio.sleep(0.1)
    pytest.fail(f"Mailpit did not receive {expected} messages")


async def mailpit_detail(api_url: str, summary: dict) -> dict:
    message_id = summary.get("ID") or summary.get("Id") or summary.get("id")
    assert message_id
    async with httpx.AsyncClient(base_url=api_url, timeout=5) as client:
        response = await client.get(f"/api/v1/message/{message_id}")
        response.raise_for_status()
        return response.json()


def token_from_text(text_body: str, path: str) -> str:
    match = re.search(rf"https?://[^\s<>]+{re.escape(path)}\?token=([^\s<>]+)", text_body)
    assert match, f"No {path} link was found in the text email"
    return parse_qs(urlparse(match.group(0)).query)["token"][0]


async def test_password_reset_request_delivers_and_token_resets_password(mailpit_environment):
    factory, settings, api_url = mailpit_environment
    install_database_override(factory)
    email = f"mailpit-reset-{uuid4().hex}@example.com"
    old_password = "old password value"
    new_password = "new secure password value"
    async with factory() as db:
        async with db.begin():
            db.add(
                User(
                    email=email,
                    hashed_password=AuthService.hash_password(old_password),
                    role=UserRole.STUDENT,
                )
            )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as api:
        known = await api.post("/auth/password/forgot", json={"email": email})
        unknown = await api.post(
            "/auth/password/forgot",
            json={"email": f"mailpit-unknown-{uuid4().hex}@example.com"},
        )
        assert known.status_code == unknown.status_code == 202
        assert known.json() == unknown.json()

        await deliver_next(factory, settings)
        messages = await mailpit_messages(api_url, 1)
        reset_summary = next(
            message for message in messages if message["Subject"].startswith("Reset your")
        )
        reset_message = await mailpit_detail(api_url, reset_summary)
        text_body = reset_message.get("Text", "")
        html_body = reset_message.get("HTML", "")
        token = token_from_text(text_body, "/reset-password")
        assert "/reset-password?token=" in html_body

        reset = await api.post(
            "/auth/password/reset",
            json={"token": token, "new_password": new_password},
        )
        assert reset.status_code == 200
        await deliver_next(factory, settings)

        assert (
            await api.post("/auth/login", data={"username": email, "password": old_password})
        ).status_code == 401
        assert (
            await api.post("/auth/login", data={"username": email, "password": new_password})
        ).status_code == 200
        assert (
            await api.post(
                "/auth/password/reset",
                json={"token": token, "new_password": "another secure password"},
            )
        ).status_code == 400

    messages = await mailpit_messages(api_url, 2)
    changed_summary = next(
        message for message in messages if "password was changed" in message["Subject"]
    )
    changed = await mailpit_detail(api_url, changed_summary)
    assert "/reset-password?token=" not in changed.get("Text", "")
    assert "/reset-password?token=" not in changed.get("HTML", "")


async def test_instructor_email_invitation_delivers_and_is_consumable(mailpit_environment):
    factory, settings, api_url = mailpit_environment
    install_database_override(factory)
    instructor_email = f"mailpit-instructor-{uuid4().hex}@example.com"
    student_email = f"mailpit-student-{uuid4().hex}@example.com"
    password = "secure password value"
    async with factory() as db:
        async with db.begin():
            instructor = User(
                email=instructor_email,
                hashed_password=AuthService.hash_password(password),
                role=UserRole.INSTRUCTOR,
            )
            student = User(
                email=student_email,
                hashed_password=AuthService.hash_password(password),
                role=UserRole.STUDENT,
            )
            subject = Subject(name="Mailpit Security", instructor=instructor)
            db.add_all([instructor, student, subject])
            await db.flush()
            subject_id = subject.id

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as api:
        instructor_login = await api.post(
            "/auth/login",
            data={"username": instructor_email, "password": password},
        )
        assert instructor_login.status_code == 200
        instructor_headers = {
            "Authorization": f"Bearer {instructor_login.json()['access_token']}"
        }
        invitation = await api.post(
            f"/subjects/{subject_id}/invite",
            headers=instructor_headers,
            json={"expires_in_hours": 24, "recipient_email": student_email},
        )
        assert invitation.status_code == 200
        assert invitation.json()["delivery_queued"] is True

        await deliver_next(factory, settings)
        messages = await mailpit_messages(api_url, 1)
        summary = next(message for message in messages if "Invitation to join" in message["Subject"])
        detail = await mailpit_detail(api_url, summary)
        token = token_from_text(detail.get("Text", ""), "/join")
        assert "/join?token=" in detail.get("HTML", "")
        assert AuthService.verify_invitation_token(token).email == student_email

        student_login = await api.post(
            "/auth/login", data={"username": student_email, "password": password}
        )
        assert student_login.status_code == 200
        accepted = await api.post(
            "/subjects/invitations/accept",
            headers={"Authorization": f"Bearer {student_login.json()['access_token']}"},
            json={"token": token},
        )
        assert accepted.status_code == 200

    async with factory() as db:
        outbox = await db.scalar(
            select(EmailOutboxMessage).where(
                EmailOutboxMessage.recipient_email == student_email
            )
        )
        assert outbox.status == EmailOutboxStatus.SENT.value


async def test_mailpit_chaos_temporary_rejection_is_retried(mailpit_environment):
    factory, settings, api_url = mailpit_environment
    email = f"mailpit-chaos-{uuid4().hex}@example.com"
    async with factory() as db:
        async with db.begin():
            user = User(
                email=email,
                hashed_password=AuthService.hash_password("old password value"),
                role=UserRole.STUDENT,
            )
            db.add(user)
            await db.flush()
            reset, _ = await AuthService.create_password_reset_token(db, user)
            outbox = await EmailOutboxService(settings).queue_password_reset(
                db, user=user, reset=reset
            )
            outbox_id = outbox.id

    async with httpx.AsyncClient(base_url=api_url, timeout=5) as mailpit:
        configured = await mailpit.put(
            "/api/v1/chaos",
            json={"Recipient": {"ErrorCode": 451, "Probability": 100}},
        )
        configured.raise_for_status()
        try:
            worker = EmailWorker(
                settings=settings,
                session_factory=factory,
                transport=SmtpTransport(settings),
                worker_id="mailpit-chaos",
            )
            claim = await worker.claim_next()
            assert claim is not None and claim[0] == outbox_id
            await worker.process_claim(*claim)
        finally:
            reset_chaos = await mailpit.put("/api/v1/chaos", json={})
            reset_chaos.raise_for_status()

    async with factory() as db:
        async with db.begin():
            outbox = await db.get(EmailOutboxMessage, outbox_id)
            assert outbox.status == EmailOutboxStatus.PENDING.value
            assert outbox.last_error_code == "smtp_temporary_rejection"
            assert outbox.attempt_count == 1
            outbox.available_at = utcnow()

    await deliver_next(factory, settings)
    assert len(await mailpit_messages(api_url, 1)) == 1
