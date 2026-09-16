"""Lease-based PostgreSQL worker for durable transactional email delivery."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import timedelta
import logging
import os
import random
import secrets
import socket
from uuid import UUID, uuid4

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, get_settings
from app.database import async_session_maker
from app.models.email import EmailOutboxMessage, EmailOutboxStatus
from app.services.email import (
    EmailCompositionError,
    EmailComposer,
    EmailDeliveryError,
    EmailTransport,
    SmtpTransport,
)
from app.time_utils import as_utc, utcnow
from app.workers.shutdown import drain_active_tasks


logger = logging.getLogger(__name__)


class EmailLeaseLost(RuntimeError):
    pass


class EmailWorker:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session_factory: async_sessionmaker[AsyncSession] = async_session_maker,
        transport: EmailTransport | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory
        self.transport = transport or SmtpTransport(self.settings)
        self.composer = EmailComposer(self.settings)
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:12]}"

    async def run(self, stop_event: asyncio.Event) -> None:
        """Poll and deliver with independently bounded local concurrency."""

        tasks: set[asyncio.Task[None]] = set()
        last_cleanup = 0.0
        loop = asyncio.get_running_loop()
        try:
            while not stop_event.is_set():
                now_monotonic = loop.time()
                if now_monotonic - last_cleanup >= self.settings.email_cleanup_interval_seconds:
                    await self.recover_and_cleanup()
                    last_cleanup = now_monotonic

                while len(tasks) < self.settings.email_worker_concurrency and not stop_event.is_set():
                    claim = await self.claim_next()
                    if claim is None:
                        break
                    outbox_id, claim_token = claim
                    task = asyncio.create_task(
                        self.process_claim(outbox_id, claim_token),
                        name=f"email-{outbox_id}",
                    )
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)

                if tasks:
                    await asyncio.wait(
                        tasks,
                        timeout=self.settings.email_worker_poll_seconds,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in tuple(tasks):
                        if task.done():
                            with suppress(Exception, asyncio.CancelledError):
                                task.result()
                else:
                    try:
                        await asyncio.wait_for(
                            stop_event.wait(), timeout=self.settings.email_worker_poll_seconds
                        )
                    except TimeoutError:
                        pass
        finally:
            forced_cancellations = await drain_active_tasks(
                tasks, self.settings.worker_shutdown_grace_seconds
            )
            if forced_cancellations:
                logger.warning(
                    "Email worker shutdown grace expired; cancelled active_messages=%s",
                    forced_cancellations,
                )

    async def claim_next(self) -> tuple[UUID, str] | None:
        async with self.session_factory() as db:
            async with db.begin():
                now = utcnow()
                query = (
                    select(EmailOutboxMessage)
                    .where(
                        EmailOutboxMessage.status == EmailOutboxStatus.PENDING.value,
                        EmailOutboxMessage.available_at <= now,
                        EmailOutboxMessage.expires_at > now,
                        EmailOutboxMessage.attempt_count < EmailOutboxMessage.max_attempts,
                    )
                    .order_by(
                        EmailOutboxMessage.available_at,
                        EmailOutboxMessage.created_at,
                        EmailOutboxMessage.id,
                    )
                    .limit(1)
                )
                if db.get_bind().dialect.name == "postgresql":
                    query = query.with_for_update(skip_locked=True)
                else:
                    query = query.with_for_update()
                outbox = await db.scalar(query)
                if outbox is None:
                    return None

                claim_token = secrets.token_hex(32)
                outbox.status = EmailOutboxStatus.SENDING.value
                outbox.attempt_count += 1
                outbox.claimed_at = now
                outbox.last_attempt_at = now
                outbox.delivery_started_at = None
                outbox.lease_expires_at = now + timedelta(seconds=self.settings.email_lease_seconds)
                outbox.worker_id = self.worker_id
                outbox.claim_token = claim_token
                outbox.last_error_code = None
                outbox.updated_at = now
                await db.flush()
                return outbox.id, claim_token

    async def _claimed(
        self,
        db: AsyncSession,
        outbox_id: UUID,
        claim_token: str,
        *,
        for_update: bool = False,
    ) -> EmailOutboxMessage:
        query = select(EmailOutboxMessage).where(EmailOutboxMessage.id == outbox_id)
        if for_update:
            query = query.with_for_update()
        outbox = await db.scalar(query)
        if (
            outbox is None
            or outbox.status != EmailOutboxStatus.SENDING.value
            or outbox.worker_id != self.worker_id
            or outbox.claim_token != claim_token
            or outbox.lease_expires_at is None
            or as_utc(outbox.lease_expires_at) <= utcnow()
        ):
            raise EmailLeaseLost("email outbox lease is no longer valid")
        return outbox

    async def process_claim(self, outbox_id: UUID, claim_token: str) -> None:
        try:
            async with self.session_factory() as db:
                outbox = await self._claimed(db, outbox_id, claim_token)
                message_type = outbox.message_type
                attempt_count = outbox.attempt_count
                message = await self.composer.compose(db, outbox)
            await self._mark_delivery_started(outbox_id, claim_token)
            await self.transport.send(message)
            await self._finish_success(outbox_id, claim_token)
            logger.info(
                "Transactional email sent outbox_id=%s type=%s attempt=%s",
                outbox_id,
                message_type,
                attempt_count,
            )
        except EmailCompositionError as exc:
            await self._finish_failure(
                outbox_id, claim_token, code=exc.code, retryable=False
            )
        except EmailDeliveryError as exc:
            await self._finish_failure(
                outbox_id, claim_token, code=exc.code, retryable=exc.retryable
            )
        except EmailLeaseLost:
            return
        except Exception:
            logger.error("Transactional email failed unexpectedly outbox_id=%s", outbox_id)
            await self._finish_failure(
                outbox_id,
                claim_token,
                code="email_internal_error",
                retryable=True,
            )

    async def _mark_delivery_started(self, outbox_id: UUID, claim_token: str) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                outbox = await self._claimed(db, outbox_id, claim_token, for_update=True)
                outbox.delivery_started_at = utcnow()
                outbox.updated_at = utcnow()

    async def _finish_success(self, outbox_id: UUID, claim_token: str) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                outbox = await self._claimed(db, outbox_id, claim_token, for_update=True)
                now = utcnow()
                outbox.status = EmailOutboxStatus.SENT.value
                outbox.sent_at = now
                outbox.failed_at = None
                outbox.last_error_code = None
                self._clear_claim(outbox)
                outbox.updated_at = now

    async def _finish_failure(
        self,
        outbox_id: UUID,
        claim_token: str,
        *,
        code: str,
        retryable: bool,
    ) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                try:
                    outbox = await self._claimed(db, outbox_id, claim_token, for_update=True)
                except EmailLeaseLost:
                    return
                now = utcnow()
                can_retry = (
                    retryable
                    and outbox.attempt_count < outbox.max_attempts
                    and as_utc(outbox.expires_at) > now
                )
                if can_retry:
                    cap = min(
                        self.settings.email_retry_max_seconds,
                        self.settings.email_retry_base_seconds
                        * (2 ** max(0, outbox.attempt_count - 1)),
                    )
                    outbox.status = EmailOutboxStatus.PENDING.value
                    outbox.available_at = now + timedelta(seconds=random.uniform(0, cap))
                    outbox.failed_at = None
                    outbox.delivery_started_at = None
                else:
                    outbox.status = EmailOutboxStatus.FAILED.value
                    outbox.failed_at = now
                outbox.last_error_code = code[:64]
                self._clear_claim(outbox)
                outbox.updated_at = now
                logger.warning(
                    "Transactional email attempt failed outbox_id=%s type=%s attempt=%s code=%s retry=%s",
                    outbox.id,
                    outbox.message_type,
                    outbox.attempt_count,
                    outbox.last_error_code,
                    can_retry,
                )

    @staticmethod
    def _clear_claim(outbox: EmailOutboxMessage) -> None:
        outbox.claimed_at = None
        outbox.lease_expires_at = None
        outbox.worker_id = None
        outbox.claim_token = None

    async def recover_and_cleanup(self) -> None:
        """Recover abandoned leases, expire stale events, and apply retention."""

        async with self.session_factory() as db:
            async with db.begin():
                now = utcnow()
                terminal = list(
                    (
                        await db.scalars(
                            select(EmailOutboxMessage)
                            .where(
                                EmailOutboxMessage.status == EmailOutboxStatus.PENDING.value,
                                or_(
                                    EmailOutboxMessage.expires_at <= now,
                                    EmailOutboxMessage.attempt_count
                                    >= EmailOutboxMessage.max_attempts,
                                ),
                            )
                            .with_for_update()
                            .limit(100)
                        )
                    ).all()
                )
                for outbox in terminal:
                    outbox.status = EmailOutboxStatus.FAILED.value
                    outbox.failed_at = now
                    outbox.last_error_code = (
                        "email_event_expired"
                        if as_utc(outbox.expires_at) <= now
                        else "email_attempts_exhausted"
                    )
                    outbox.updated_at = now

                expired_query = (
                    select(EmailOutboxMessage)
                    .where(
                        EmailOutboxMessage.status == EmailOutboxStatus.SENDING.value,
                        EmailOutboxMessage.lease_expires_at <= now,
                    )
                    .limit(100)
                )
                if db.get_bind().dialect.name == "postgresql":
                    expired_query = expired_query.with_for_update(skip_locked=True)
                else:
                    expired_query = expired_query.with_for_update()
                expired_claims = list((await db.scalars(expired_query)).all())
                for outbox in expired_claims:
                    if outbox.delivery_started_at is not None:
                        outbox.status = EmailOutboxStatus.FAILED.value
                        outbox.failed_at = now
                        outbox.last_error_code = "smtp_delivery_ambiguous"
                    elif (
                        as_utc(outbox.expires_at) <= now
                        or outbox.attempt_count >= outbox.max_attempts
                    ):
                        outbox.status = EmailOutboxStatus.FAILED.value
                        outbox.failed_at = now
                        outbox.last_error_code = "email_worker_lease_expired"
                    else:
                        cap = min(
                            self.settings.email_retry_max_seconds,
                            self.settings.email_retry_base_seconds
                            * (2 ** max(0, outbox.attempt_count - 1)),
                        )
                        outbox.status = EmailOutboxStatus.PENDING.value
                        outbox.available_at = now + timedelta(seconds=random.uniform(0, cap))
                        outbox.last_error_code = "email_worker_lease_expired"
                        outbox.delivery_started_at = None
                    self._clear_claim(outbox)
                    outbox.updated_at = now

                await db.execute(
                    delete(EmailOutboxMessage).where(
                        EmailOutboxMessage.status == EmailOutboxStatus.SENT.value,
                        EmailOutboxMessage.sent_at
                        <= now - timedelta(days=self.settings.email_sent_retention_days),
                    )
                )
                await db.execute(
                    delete(EmailOutboxMessage).where(
                        EmailOutboxMessage.status == EmailOutboxStatus.FAILED.value,
                        EmailOutboxMessage.failed_at
                        <= now - timedelta(days=self.settings.email_failed_retention_days),
                    )
                )
