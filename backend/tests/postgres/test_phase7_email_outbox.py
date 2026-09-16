"""PostgreSQL proofs for the Phase 7 transactional-email outbox."""

import asyncio
from datetime import timedelta
import os
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings
from app.models.email import EmailOutboxMessage, EmailOutboxStatus
from app.models.user import PasswordResetToken, User, UserRole
from app.services.auth import AuthService
from app.services.email import EmailOutboxService
from app.time_utils import utcnow
from app.workers.email import EmailLeaseLost, EmailWorker


pytestmark = pytest.mark.postgres


@pytest_asyncio.fixture
async def phase7_pg_factory():
    database_url = os.getenv("POSTGRES_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL is not configured")
    engine = create_async_engine(database_url, pool_size=8, max_overflow=0)
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != "20260916_0006":
            pytest.fail(f"PostgreSQL test database is at Alembic revision {revision!r}")
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM users WHERE email LIKE 'phase7-%@example.com'")
            )
        await engine.dispose()


def phase7_settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "database_url": os.getenv(
            "POSTGRES_TEST_DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost/test",
        ),
        "secret_key": "test-only-secret-key-with-adequate-entropy-1234567890",
        "generation_source_encryption_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "frontend_base_url": "https://cards.example.com",
        "smtp_host": "smtp.example.com",
        "smtp_from_email": "no-reply@example.com",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def seed_reset(factory, settings, *, suffix: str) -> tuple:
    async with factory() as db:
        async with db.begin():
            user = User(
                email=f"phase7-{suffix}-{uuid4().hex}@example.com",
                hashed_password=AuthService.hash_password("old password value"),
                role=UserRole.STUDENT,
            )
            db.add(user)
            await db.flush()
            reset, token = await AuthService.create_password_reset_token(db, user)
            outbox = await EmailOutboxService(settings).queue_password_reset(
                db, user=user, reset=reset
            )
            return user.id, reset.id, token, outbox.id


async def test_phase7_migration_installs_constraints_indexes_and_secret_free_columns(
    phase7_pg_factory,
):
    async with phase7_pg_factory() as db:
        indexes = set(
            (
                await db.scalars(
                    text(
                        "SELECT indexname FROM pg_indexes "
                        "WHERE schemaname='public' AND tablename='email_outbox_messages'"
                    )
                )
            ).all()
        )
        assert {
            "ix_email_outbox_messages_queue",
            "ix_email_outbox_messages_sending_lease",
            "ix_email_outbox_messages_expiry",
            "ix_email_outbox_messages_sent_retention",
            "ix_email_outbox_messages_failed_retention",
            "ix_email_outbox_messages_password_reset_token_id",
            "ix_email_outbox_messages_invite_link_id",
        } <= indexes

        columns = set(
            (
                await db.scalars(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name='email_outbox_messages'"
                    )
                )
            ).all()
        )
        assert {"status", "attempt_count", "claim_token", "delivery_started_at"} <= columns
        assert not {"token", "reset_url", "invitation_url", "text_body", "html_body"} & columns

        constraints = set(
            (
                await db.scalars(
                    text(
                        "SELECT conname FROM pg_constraint "
                        "WHERE conrelid='email_outbox_messages'::regclass"
                    )
                )
            ).all()
        )
        assert {
            "ck_email_outbox_messages_attempts",
            "ck_email_outbox_messages_relevant_source",
            "ck_email_outbox_messages_sending_claim",
            "ck_email_outbox_messages_terminal_timestamps",
            "uq_email_outbox_messages_idempotency_key_hash",
        } <= constraints


async def test_concurrent_workers_claim_distinct_rows_and_claims_are_fenced(
    phase7_pg_factory,
):
    settings = phase7_settings()
    first = await seed_reset(phase7_pg_factory, settings, suffix="claim-a")
    second = await seed_reset(phase7_pg_factory, settings, suffix="claim-b")
    worker_a = EmailWorker(
        settings=settings,
        session_factory=phase7_pg_factory,
        transport=None,
        worker_id="phase7-pg-a",
    )
    worker_b = EmailWorker(
        settings=settings,
        session_factory=phase7_pg_factory,
        transport=None,
        worker_id="phase7-pg-b",
    )
    claim_a, claim_b = await asyncio.gather(worker_a.claim_next(), worker_b.claim_next())
    assert claim_a is not None and claim_b is not None
    assert {claim_a[0], claim_b[0]} == {first[3], second[3]}

    owning_worker, claim = (
        (worker_a, claim_a)
        if claim_a[0] == first[3]
        else (worker_b, claim_b)
    )
    stale_worker = worker_b if owning_worker is worker_a else worker_a
    with pytest.raises(EmailLeaseLost):
        await stale_worker._finish_success(*claim)


async def test_outbox_enqueue_and_password_change_roll_back_atomically(phase7_pg_factory):
    settings = phase7_settings()
    async with phase7_pg_factory() as db:
        async with db.begin():
            user = User(
                email=f"phase7-atomic-{uuid4().hex}@example.com",
                hashed_password=AuthService.hash_password("old password value"),
                role=UserRole.STUDENT,
            )
            db.add(user)
            await db.flush()
            user_id = user.id

    with pytest.raises(RuntimeError):
        async with phase7_pg_factory() as db:
            async with db.begin():
                user = await db.get(User, user_id)
                reset, _ = await AuthService.create_password_reset_token(db, user)
                await EmailOutboxService(settings).queue_password_reset(
                    db, user=user, reset=reset
                )
                raise RuntimeError("force forgot-password rollback")

    async with phase7_pg_factory() as db:
        assert await db.scalar(
            select(func.count(PasswordResetToken.id)).where(
                PasswordResetToken.user_id == user_id
            )
        ) == 0
        assert await db.scalar(
            select(func.count(EmailOutboxMessage.id)).join(PasswordResetToken).where(
                PasswordResetToken.user_id == user_id
            )
        ) == 0

    async with phase7_pg_factory() as db:
        async with db.begin():
            user = await db.get(User, user_id)
            reset, token = await AuthService.create_password_reset_token(db, user)
            reset_id = reset.id

    with pytest.raises(RuntimeError):
        async with phase7_pg_factory() as db:
            async with db.begin():
                user, reset = await AuthService.reset_password(
                    db, token, "new secure password value"
                )
                await EmailOutboxService(settings).queue_password_changed(
                    db, user=user, reset=reset
                )
                raise RuntimeError("force password-change rollback")

    async with phase7_pg_factory() as db:
        user = await db.get(User, user_id)
        reset = await db.get(PasswordResetToken, reset_id)
        assert AuthService.verify_password("old password value", user.hashed_password)
        assert reset.used_at is None
        assert await db.scalar(
            select(func.count(EmailOutboxMessage.id)).where(
                EmailOutboxMessage.password_reset_token_id == reset_id
            )
        ) == 0


async def test_expired_pre_delivery_lease_is_recoverable(phase7_pg_factory):
    settings = phase7_settings(email_retry_base_seconds=0.1, email_retry_max_seconds=1)
    _, _, _, outbox_id = await seed_reset(
        phase7_pg_factory, settings, suffix="lease-recovery"
    )
    worker = EmailWorker(
        settings=settings,
        session_factory=phase7_pg_factory,
        transport=None,
        worker_id="phase7-lease",
    )
    claim = await worker.claim_next()
    assert claim is not None
    async with phase7_pg_factory() as db:
        async with db.begin():
            outbox = await db.get(EmailOutboxMessage, outbox_id)
            outbox.lease_expires_at = utcnow() - timedelta(seconds=1)
    await worker.recover_and_cleanup()

    async with phase7_pg_factory() as db:
        recovered = await db.get(EmailOutboxMessage, outbox_id)
        assert recovered.status == EmailOutboxStatus.PENDING.value
        assert recovered.last_error_code == "email_worker_lease_expired"
        assert recovered.claim_token is None
