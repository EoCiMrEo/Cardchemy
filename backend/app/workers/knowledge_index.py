"""Fenced durable worker for Subject Knowledge embeddings."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import timedelta
import logging
import os
import secrets
import socket
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.chunking import estimate_tokens
from app.ai.embeddings import EmbeddingProvider, get_embedding_provider
from app.ai.providers import AIProviderError
from app.config import Settings, get_settings
from app.database import async_session_maker
from app.models.knowledge import (
    SubjectDocumentChunk,
    SubjectDocumentContentRevision,
    SubjectDocumentIndexJob,
    SubjectDocumentIndexRevision,
    embedding_space_hash,
)
from app.observability import job_context
from app.services.knowledge_lock import acquire_knowledge_write_lock
from app.services.operations import pulse_worker
from app.time_utils import as_utc, utcnow
from app.workers.shutdown import drain_active_tasks


logger = logging.getLogger(__name__)


class IndexLeaseLost(RuntimeError):
    pass


class IndexCancellationRequested(RuntimeError):
    pass


class KnowledgeIndexWorker:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session_factory: async_sessionmaker[AsyncSession] = async_session_maker,
        provider: EmbeddingProvider | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory
        # A disabled RAG installation must not require provider credentials or
        # instantiate an SDK client merely to publish healthy-disabled pulses.
        # Resolve the provider lazily when active work first needs it.
        self._provider = provider
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:12]}"
        self.space_hash = embedding_space_hash(self.settings.rag_embedding_space_identity)

    @property
    def provider(self) -> EmbeddingProvider:
        if self._provider is None:
            self._provider = get_embedding_provider(self.settings)
        return self._provider

    async def run(self, stop_event: asyncio.Event) -> None:
        if not self.settings.rag_index_available:
            try:
                while not stop_event.is_set():
                    await self._pulse("disabled")
                    try:
                        await asyncio.wait_for(stop_event.wait(), timeout=min(5, self.settings.worker_health_stale_seconds / 3))
                    except TimeoutError:
                        pass
            finally:
                await self._pulse("draining")
            return
        tasks: set[asyncio.Task[None]] = set()
        last_cleanup = 0.0
        loop = asyncio.get_running_loop()
        try:
            while not stop_event.is_set():
                await self._pulse("running")
                if loop.time() - last_cleanup >= self.settings.rag_index_cleanup_interval_seconds:
                    await self.recover_expired()
                    last_cleanup = loop.time()
                while len(tasks) < self.settings.rag_index_worker_concurrency and not stop_event.is_set():
                    claim = await self.claim_next()
                    if claim is None:
                        break
                    task = asyncio.create_task(self.process_claim(*claim), name=f"knowledge-index-{claim[0]}")
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
                if tasks:
                    await asyncio.wait(tasks, timeout=self.settings.rag_index_worker_poll_seconds, return_when=asyncio.FIRST_COMPLETED)
                    for task in tuple(tasks):
                        if task.done():
                            with suppress(Exception, asyncio.CancelledError):
                                task.result()
                else:
                    try:
                        await asyncio.wait_for(stop_event.wait(), timeout=self.settings.rag_index_worker_poll_seconds)
                    except TimeoutError:
                        pass
        finally:
            await self._pulse("draining")
            await drain_active_tasks(tasks, self.settings.worker_shutdown_grace_seconds)

    async def _pulse(self, status: str) -> None:
        await pulse_worker(self.session_factory, worker_id=self.worker_id, kind="index", status=status, stale_seconds=self.settings.worker_health_stale_seconds)

    async def claim_next(self) -> tuple[UUID, str] | None:
        async with self.session_factory() as db:
            async with db.begin():
                await acquire_knowledge_write_lock(db)
                now = utcnow()
                query = (
                    select(SubjectDocumentIndexJob)
                    .where(
                        SubjectDocumentIndexJob.status == "queued",
                        SubjectDocumentIndexJob.available_at <= now,
                    )
                    .order_by(SubjectDocumentIndexJob.available_at, SubjectDocumentIndexJob.created_at, SubjectDocumentIndexJob.id)
                    .limit(1)
                )
                query = query.with_for_update(skip_locked=True) if db.get_bind().dialect.name == "postgresql" else query.with_for_update()
                job = await db.scalar(query)
                if job is None:
                    return None
                if as_utc(job.deadline_at) <= now:
                    await self._fail_locked(db, job, "knowledge_index_failed", "Document indexing failed.")
                    return None
                revision = await db.scalar(select(SubjectDocumentIndexRevision).where(
                    SubjectDocumentIndexRevision.id == job.index_revision_id
                ).with_for_update())
                if revision is None or revision.embedding_space_hash != self.space_hash:
                    await self._fail_locked(db, job, "knowledge_index_failed", "Document indexing failed.", revision=revision)
                    return None
                token = secrets.token_hex(32)
                job.status = "running"
                job.attempt_count += 1
                job.worker_id = self.worker_id
                job.claim_token = token
                job.heartbeat_at = now
                job.lease_expires_at = min(as_utc(job.deadline_at), now + timedelta(seconds=self.settings.rag_index_lease_seconds))
                job.updated_at = now
                await db.flush()
                return job.id, token

    async def _claimed_job(self, db: AsyncSession, job_id: UUID, token: str, *, for_update: bool = False) -> SubjectDocumentIndexJob:
        query = select(SubjectDocumentIndexJob).where(SubjectDocumentIndexJob.id == job_id)
        if for_update:
            query = query.with_for_update()
        job = await db.scalar(query)
        if (
            job is None or job.status != "running" or job.worker_id != self.worker_id
            or job.claim_token != token or job.lease_expires_at is None
            or as_utc(job.lease_expires_at) <= utcnow()
        ):
            raise IndexLeaseLost()
        if job.cancellation_requested_at is not None:
            raise IndexCancellationRequested()
        return job

    async def _heartbeat(self, job_id: UUID, token: str, task: asyncio.Task[None], stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=self.settings.rag_index_heartbeat_seconds)
                return
            except TimeoutError:
                pass
            try:
                async with self.session_factory() as db:
                    async with db.begin():
                        await acquire_knowledge_write_lock(db)
                        job = await self._claimed_job(db, job_id, token, for_update=True)
                        now = utcnow()
                        job.heartbeat_at = now
                        job.lease_expires_at = min(as_utc(job.deadline_at), now + timedelta(seconds=self.settings.rag_index_lease_seconds))
                        job.updated_at = now
            except (IndexLeaseLost, IndexCancellationRequested):
                task.cancel()
                return
            except Exception:
                logger.warning("index_heartbeat_failed")

    async def process_claim(self, job_id: UUID, token: str) -> None:
        origin = None
        try:
            async with asyncio.timeout(0.25):
                async with self.session_factory() as db:
                    origin = await db.scalar(
                        select(SubjectDocumentIndexJob.request_id).where(
                            SubjectDocumentIndexJob.id == job_id
                        )
                    )
        except Exception:
            pass
        with job_context(job_id, request_id=origin):
            await self._process_claim(job_id, token)

    async def _process_claim(self, job_id: UUID, token: str) -> None:
        stop = asyncio.Event()
        task = asyncio.create_task(self._index(job_id, token))
        heartbeat = asyncio.create_task(self._heartbeat(job_id, token, task, stop))
        try:
            async with asyncio.timeout(self.settings.rag_index_job_timeout_seconds):
                await task
        except asyncio.CancelledError:
            await self._cancel(job_id, token)
        except IndexCancellationRequested:
            await self._cancel(job_id, token)
        except IndexLeaseLost:
            logger.warning("index_lease_lost")
        except (AIProviderError, ValueError):
            await self._fail(job_id, token)
        except TimeoutError:
            await self._fail(job_id, token)
        except Exception:
            logger.warning("index_internal_error")
            await self._fail(job_id, token)
        finally:
            stop.set()
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)

    async def _index(self, job_id: UUID, token: str) -> None:
        async with self.session_factory() as db:
            job = await self._claimed_job(db, job_id, token)
            revision = await db.get(SubjectDocumentIndexRevision, job.index_revision_id)
            if revision is None or revision.embedding_space_hash != self.space_hash:
                raise ValueError("Incompatible embedding space")
            chunks = list((await db.scalars(select(SubjectDocumentChunk).where(
                SubjectDocumentChunk.index_revision_id == revision.id
            ).order_by(SubjectDocumentChunk.chunk_index))).all())
        if not chunks or len(chunks) > 512:
            raise ValueError("Invalid chunk snapshot")
        estimated_total = sum(estimate_tokens(chunk.content) for chunk in chunks)
        if estimated_total > self.settings.rag_index_max_job_input_tokens:
            raise ValueError("Index token bound exceeded")
        estimated_cost = round(estimated_total * float(self.settings.rag_embedding_input_cost_per_million_usd))
        if estimated_cost > round(float(self.settings.rag_embedding_max_estimated_cost_usd) * 1_000_000):
            raise ValueError("Index cost bound exceeded")
        for offset in range(0, len(chunks), self.settings.rag_embedding_batch_size):
            batch = chunks[offset:offset + self.settings.rag_embedding_batch_size]
            await self._mark_provider_boundary(job_id, token, estimated_total, estimated_cost)
            before = self.provider.telemetry_snapshot()
            try:
                response = await self.provider.embed_documents([chunk.content for chunk in batch])
            except Exception:
                after = self.provider.telemetry_snapshot()
                await self._record_failed_attempt(
                    job_id,
                    token,
                    request_count=after.request_count - before.request_count,
                    retry_count=after.retry_count - before.retry_count,
                    waited_ms=round((after.rate_limit_wait_seconds - before.rate_limit_wait_seconds) * 1000),
                )
                raise
            after = self.provider.telemetry_snapshot()
            await self._persist_batch(
                job_id, token, batch, response.vectors,
                input_tokens=response.usage.input_tokens,
                usage_estimated=response.usage.estimated,
                request_count=after.request_count - before.request_count,
                retry_count=after.retry_count - before.retry_count,
                waited_ms=round((after.rate_limit_wait_seconds - before.rate_limit_wait_seconds) * 1000),
            )
        await self._complete(job_id, token)

    async def _mark_provider_boundary(self, job_id: UUID, token: str, estimated_tokens: int, estimated_cost: int) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                await acquire_knowledge_write_lock(db)
                job = await self._claimed_job(db, job_id, token, for_update=True)
                job.provider_call_started_at = job.provider_call_started_at or utcnow()
                job.estimated_input_tokens = max(job.estimated_input_tokens, estimated_tokens)
                job.estimated_cost_microusd = max(job.estimated_cost_microusd or 0, estimated_cost)
                job.updated_at = utcnow()
                revision = await db.scalar(select(SubjectDocumentIndexRevision).where(
                    SubjectDocumentIndexRevision.id == job.index_revision_id
                ).with_for_update())
                if revision is None:
                    raise IndexLeaseLost()
                if revision.status == "pending_index":
                    revision.status = "indexing"
                    revision.updated_at = utcnow()

    async def _persist_batch(self, job_id: UUID, token: str, chunks, vectors, *, input_tokens: int, usage_estimated: bool, request_count: int, retry_count: int, waited_ms: int) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Embedding count mismatch")
        async with self.session_factory() as db:
            async with db.begin():
                await acquire_knowledge_write_lock(db)
                job = await self._claimed_job(db, job_id, token, for_update=True)
                persisted = list((await db.scalars(select(SubjectDocumentChunk).where(
                    SubjectDocumentChunk.id.in_([chunk.id for chunk in chunks]),
                    SubjectDocumentChunk.index_revision_id == job.index_revision_id,
                ).order_by(SubjectDocumentChunk.chunk_index).with_for_update())).all())
                by_id = {chunk.id: vector for chunk, vector in zip(chunks, vectors, strict=True)}
                if len(persisted) != len(chunks):
                    raise IndexLeaseLost()
                for chunk in persisted:
                    chunk.embedding = list(by_id[chunk.id])
                job.actual_input_tokens = (job.actual_input_tokens or 0) + input_tokens
                job.provider_request_count += request_count
                job.provider_retry_count += retry_count
                job.provider_rate_limit_wait_milliseconds += max(0, waited_ms)
                actual_cost = round(input_tokens * float(self.settings.rag_embedding_input_cost_per_million_usd))
                job.actual_cost_microusd = (job.actual_cost_microusd or 0) + actual_cost
                job.usage_estimated = job.usage_estimated or usage_estimated
                job.updated_at = utcnow()
                await db.flush()

    async def _record_failed_attempt(
        self,
        job_id: UUID,
        token: str,
        *,
        request_count: int,
        retry_count: int,
        waited_ms: int,
    ) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                await acquire_knowledge_write_lock(db)
                job = await self._claimed_job(db, job_id, token, for_update=True)
                job.provider_request_count += max(0, request_count)
                job.provider_retry_count += max(0, retry_count)
                job.provider_rate_limit_wait_milliseconds += max(0, waited_ms)
                job.usage_estimated = True
                job.updated_at = utcnow()

    async def _complete(self, job_id: UUID, token: str) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                await acquire_knowledge_write_lock(db)
                job = await self._claimed_job(db, job_id, token, for_update=True)
                revision = await db.scalar(select(SubjectDocumentIndexRevision).where(
                    SubjectDocumentIndexRevision.id == job.index_revision_id
                ).with_for_update())
                content = await db.scalar(select(SubjectDocumentContentRevision).where(
                    SubjectDocumentContentRevision.id == job.content_revision_id
                ).with_for_update())
                if revision is None or content is None:
                    raise IndexLeaseLost()
                embedded = int(await db.scalar(select(func.count(SubjectDocumentChunk.id)).where(
                    SubjectDocumentChunk.index_revision_id == revision.id,
                    SubjectDocumentChunk.embedding.is_not(None),
                )) or 0)
                if embedded != revision.reserved_chunk_count:
                    raise ValueError("Incomplete embedding snapshot")
                other_contents = list((await db.scalars(select(SubjectDocumentContentRevision).where(
                    SubjectDocumentContentRevision.document_id == content.document_id,
                    SubjectDocumentContentRevision.is_active.is_(True),
                    SubjectDocumentContentRevision.id != content.id,
                ).with_for_update())).all())
                for other in other_contents:
                    other.is_active = False
                revision.status = "ready"
                # Activation is safe only in the currently active space. A new
                # space remains staged until explicit full-corpus cutover.
                from app.models.subject import Subject
                subject = await db.get(Subject, job.subject_id)
                revision.is_active = bool(subject and subject.active_embedding_space_hash == revision.embedding_space_hash)
                await db.flush()
                # The content guard requires an already-ready index, and the
                # partial unique index requires old active content to be off.
                content.status = "ready"
                content.is_active = True
                await db.flush()
                now = utcnow()
                job.status = "completed"
                job.completed_at = now
                job.heartbeat_at = now
                job.lease_expires_at = None
                job.worker_id = None
                job.claim_token = None
                job.error_code = None
                job.error_message = None
                job.updated_at = now
                await db.flush()

    async def _cancel(self, job_id: UUID, token: str) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                await acquire_knowledge_write_lock(db)
                job = await db.scalar(select(SubjectDocumentIndexJob).where(
                    SubjectDocumentIndexJob.id == job_id,
                    SubjectDocumentIndexJob.claim_token == token,
                ).with_for_update())
                if job is None or job.status != "running":
                    return
                revision = await db.get(SubjectDocumentIndexRevision, job.index_revision_id)
                now = utcnow()
                if revision is not None:
                    revision.status = "cancelled"
                    revision.error_code = "knowledge_cancelled"
                    revision.error_message = "Document processing was cancelled."
                job.status = "cancelled"
                job.completed_at = now
                job.error_code = "knowledge_cancelled"
                job.error_message = "Document processing was cancelled."
                job.lease_expires_at = None
                job.worker_id = None
                job.claim_token = None
                job.updated_at = now

    async def _fail(self, job_id: UUID, token: str) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                await acquire_knowledge_write_lock(db)
                job = await db.scalar(select(SubjectDocumentIndexJob).where(
                    SubjectDocumentIndexJob.id == job_id,
                    SubjectDocumentIndexJob.claim_token == token,
                ).with_for_update())
                if job is None or job.status != "running":
                    return
                await self._fail_locked(db, job, "knowledge_index_failed", "Document indexing failed.")

    async def _fail_locked(self, db: AsyncSession, job: SubjectDocumentIndexJob, code: str, message: str, *, revision: SubjectDocumentIndexRevision | None = None) -> None:
        revision = revision or await db.get(SubjectDocumentIndexRevision, job.index_revision_id)
        now = utcnow()
        if revision is not None:
            revision.status = "index_failed"
            revision.is_active = False
            revision.error_code = code
            revision.error_message = message
            revision.updated_at = now
        job.status = "failed"
        job.completed_at = now
        job.error_code = code
        job.error_message = message
        job.lease_expires_at = None
        job.worker_id = None
        job.claim_token = None
        job.updated_at = now

    async def recover_expired(self) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                await acquire_knowledge_write_lock(db)
                now = utcnow()
                query = select(SubjectDocumentIndexJob).where(
                    SubjectDocumentIndexJob.status == "running",
                    SubjectDocumentIndexJob.lease_expires_at <= now,
                ).limit(100)
                query = query.with_for_update(skip_locked=True) if db.get_bind().dialect.name == "postgresql" else query.with_for_update()
                for job in (await db.scalars(query)).all():
                    revision = await db.get(SubjectDocumentIndexRevision, job.index_revision_id)
                    if (
                        job.provider_call_started_at is None
                        and job.attempt_count < job.max_attempts
                        and as_utc(job.deadline_at) > now
                        and job.cancellation_requested_at is None
                    ):
                        job.status = "queued"
                        job.available_at = now + timedelta(seconds=self.settings.rag_index_retry_base_seconds)
                        job.worker_id = None
                        job.claim_token = None
                        job.heartbeat_at = None
                        job.lease_expires_at = None
                        job.updated_at = now
                    elif job.cancellation_requested_at is not None:
                        await self._fail_locked(db, job, "knowledge_cancelled", "Document processing was cancelled.", revision=revision)
                        job.status = "cancelled"
                        if revision is not None:
                            revision.status = "cancelled"
                    else:
                        await self._fail_locked(db, job, "knowledge_lease_expired", "Document processing lease expired.", revision=revision)
