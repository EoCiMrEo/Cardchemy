"""Fenced durable worker for private, grounded Subject Ask AI answers."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING
import logging
import os
import secrets
import socket
from typing import Any, Sequence
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.answering import (
    ABSTENTION_TEXT,
    ClaimSupportOutput,
    GroundedAnswerOutput,
    ValidatedAnswerClaim,
    render_answer_prompts,
    render_support_prompts,
    validate_grounded_answer,
    validate_support_output,
)
from app.ai.chunking import estimate_tokens
from app.ai.embeddings import EmbeddingProvider, get_embedding_provider
from app.ai.providers import AIProvider, AIProviderError, ProviderAttemptTelemetry, get_ai_provider
from app.config import Settings, get_settings
from app.database import async_session_maker
from app.models.flashcard import Enrollment
from app.models.rag import RagAnswerJob, RagMessage, RagMessageSource, RagThread
from app.models.subject import Subject
from app.models.user import AuthSession, User, UserRole
from app.observability import job_context
from app.services.knowledge_lock import acquire_knowledge_write_lock
from app.services.knowledge_retrieval import (
    EXACT_V1_POLICY,
    IncompatibleEmbeddingSpace,
    InvalidQueryEmbedding,
    KnowledgeRetriever,
    KnowledgeScopeUnavailable,
)
from app.services.operations import pulse_worker
from app.services.rag_answers import RagAnswerService
from app.time_utils import as_utc, utcnow
from app.workers.shutdown import drain_active_tasks


logger = logging.getLogger(__name__)


class AnswerLeaseLost(RuntimeError):
    pass


class AnswerCancellationRequested(RuntimeError):
    pass


class AnswerAccessRevoked(RuntimeError):
    pass


class AnswerCorpusChanged(RuntimeError):
    pass


class AnswerProfileMismatch(RuntimeError):
    pass


@dataclass(slots=True)
class _Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    request_count: int = 0
    retry_count: int = 0
    waited_ms: int = 0
    cost_microusd: int = 0
    estimated: bool = False


def _snapshot(provider: object) -> ProviderAttemptTelemetry:
    method = getattr(provider, "telemetry_snapshot", None)
    if callable(method):
        return method()
    return ProviderAttemptTelemetry(0, 0, 0.0, {})


def _attempt_delta(before: ProviderAttemptTelemetry, after: ProviderAttemptTelemetry) -> tuple[int, int, int]:
    return (
        max(0, after.request_count - before.request_count),
        max(0, after.retry_count - before.retry_count),
        max(0, round((after.rate_limit_wait_seconds - before.rate_limit_wait_seconds) * 1_000)),
    )


def _ai_cost(settings: Settings, input_tokens: int, output_tokens: int) -> int:
    value = (
        Decimal(input_tokens) * settings.rag_ai_input_cost_per_million_usd
        + Decimal(output_tokens) * settings.rag_ai_output_cost_per_million_usd
    )
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def _embedding_cost(settings: Settings, input_tokens: int) -> int:
    value = Decimal(input_tokens) * settings.rag_embedding_input_cost_per_million_usd
    return int(value.to_integral_value(rounding=ROUND_CEILING))


class RagAnswerWorker:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session_factory: async_sessionmaker[AsyncSession] = async_session_maker,
        answer_provider: AIProvider | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory
        self.answer_provider = answer_provider or get_ai_provider(self.settings, role="rag_answer")
        self.embedding_provider = embedding_provider or get_embedding_provider(self.settings)
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:12]}"
        from app.models.knowledge import embedding_space_hash
        self.space_hash = embedding_space_hash(self.settings.rag_embedding_space_identity)
        self.history_service = RagAnswerService(self.settings)

    async def run(self, stop_event: asyncio.Event) -> None:
        if not self.settings.rag_answer_available:
            try:
                while not stop_event.is_set():
                    await self._pulse("disabled")
                    try:
                        await asyncio.wait_for(
                            stop_event.wait(),
                            timeout=min(5, self.settings.worker_health_stale_seconds / 3),
                        )
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
                if loop.time() - last_cleanup >= self.settings.rag_answer_cleanup_interval_seconds:
                    await self.recover_expired()
                    last_cleanup = loop.time()
                while len(tasks) < self.settings.rag_answer_worker_concurrency and not stop_event.is_set():
                    claim = await self.claim_next()
                    if claim is None:
                        break
                    task = asyncio.create_task(self.process_claim(*claim), name=f"rag-answer-{claim[0]}")
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
                if tasks:
                    await asyncio.wait(
                        tasks,
                        timeout=self.settings.rag_answer_worker_poll_seconds,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in tuple(tasks):
                        if task.done():
                            with suppress(Exception, asyncio.CancelledError):
                                task.result()
                else:
                    try:
                        await asyncio.wait_for(
                            stop_event.wait(), timeout=self.settings.rag_answer_worker_poll_seconds
                        )
                    except TimeoutError:
                        pass
        finally:
            await self._pulse("draining")
            await drain_active_tasks(tasks, self.settings.worker_shutdown_grace_seconds)

    async def _pulse(self, status: str) -> None:
        await pulse_worker(
            self.session_factory,
            worker_id=self.worker_id,
            kind="answer",
            status=status,
            stale_seconds=self.settings.worker_health_stale_seconds,
        )

    def _profile_matches(self, job: RagAnswerJob) -> bool:
        return (
            job.ai_provider == self.settings.rag_ai_provider
            and job.ai_base_url == self.settings.rag_ai_endpoint_identity
            and job.ai_model == self.settings.rag_ai_model
            and job.embedding_space_hash == self.space_hash
            and job.retrieval_policy == EXACT_V1_POLICY.policy_id
        )

    async def claim_next(self) -> tuple[UUID, str] | None:
        async with self.session_factory() as db:
            async with db.begin():
                now = utcnow()
                query = select(RagAnswerJob).where(
                    RagAnswerJob.status == "queued",
                    RagAnswerJob.available_at <= now,
                    RagAnswerJob.attempt_count < RagAnswerJob.max_attempts,
                ).order_by(RagAnswerJob.available_at, RagAnswerJob.created_at, RagAnswerJob.id).limit(1)
                query = query.with_for_update(skip_locked=True) if db.get_bind().dialect.name == "postgresql" else query.with_for_update()
                job = await db.scalar(query)
                if job is None:
                    return None
                if as_utc(job.deadline_at) <= now:
                    await self._fail_locked(job, "rag_answer_failed", "Answer generation failed.", retryable=True)
                    return None
                if not self._profile_matches(job):
                    await self._fail_locked(job, "rag_profile_mismatch", "Ask AI configuration changed before execution.", retryable=False)
                    return None
                if not await self._session_active(db, job):
                    await self._fail_locked(job, "rag_access_revoked", "Subject access is no longer available.", retryable=False)
                    return None
                token = secrets.token_hex(32)
                job.status = "running"
                job.attempt_count += 1
                job.worker_id = self.worker_id
                job.claim_token = token
                job.heartbeat_at = now
                job.lease_expires_at = min(
                    as_utc(job.deadline_at),
                    now + timedelta(seconds=self.settings.rag_answer_lease_seconds),
                )
                job.updated_at = now
                await db.flush()
                return job.id, token

    @staticmethod
    async def _session_active(
        db: AsyncSession, job: RagAnswerJob, *, for_update: bool = False
    ) -> bool:
        query = select(AuthSession).where(
            AuthSession.id == job.auth_session_id,
            AuthSession.user_id == job.user_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > utcnow(),
        )
        if for_update:
            query = query.with_for_update()
        session = await db.scalar(query)
        return session is not None

    @staticmethod
    async def _current_principal(
        db: AsyncSession, job: RagAnswerJob, *, for_update: bool = False
    ) -> User | None:
        user_query = select(User).where(User.id == job.user_id)
        subject_query = select(Subject).where(Subject.id == job.subject_id)
        if for_update:
            user_query = user_query.with_for_update()
            subject_query = subject_query.with_for_update()
        user = await db.scalar(user_query)
        subject = await db.scalar(subject_query)
        if user is None or subject is None:
            return None
        if user.role == UserRole.INSTRUCTOR:
            return user if subject.instructor_id == user.id else None
        if user.role != UserRole.STUDENT:
            return None
        enrollment_query = select(Enrollment).where(
            Enrollment.student_id == user.id,
            Enrollment.subject_id == job.subject_id,
        )
        if for_update:
            enrollment_query = enrollment_query.with_for_update()
        return user if await db.scalar(enrollment_query) is not None else None

    async def _claimed_job(
        self, db: AsyncSession, job_id: UUID, token: str, *, for_update: bool = False
    ) -> RagAnswerJob:
        query = select(RagAnswerJob).where(RagAnswerJob.id == job_id)
        if for_update:
            query = query.with_for_update()
        job = await db.scalar(query)
        if (
            job is None
            or job.status != "running"
            or job.worker_id != self.worker_id
            or job.claim_token != token
            or job.lease_expires_at is None
            or as_utc(job.lease_expires_at) <= utcnow()
        ):
            raise AnswerLeaseLost()
        if job.cancellation_requested_at is not None:
            raise AnswerCancellationRequested()
        return job

    async def _heartbeat(
        self, job_id: UUID, token: str, task: asyncio.Task[None], stop: asyncio.Event
    ) -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=self.settings.rag_answer_heartbeat_seconds)
                return
            except TimeoutError:
                pass
            try:
                async with self.session_factory() as db:
                    async with db.begin():
                        job = await self._claimed_job(db, job_id, token, for_update=True)
                        if not await self._session_active(db, job):
                            raise AnswerAccessRevoked()
                        now = utcnow()
                        job.heartbeat_at = now
                        job.lease_expires_at = min(
                            as_utc(job.deadline_at),
                            now + timedelta(seconds=self.settings.rag_answer_lease_seconds),
                        )
                        job.updated_at = now
            except AnswerCancellationRequested:
                task.cancel()
                return
            except (AnswerLeaseLost, AnswerAccessRevoked):
                # Fencing/current-access checks around every subsequent durable
                # or external boundary decide the outcome. Do not turn lease or
                # access loss into a user-requested cancellation.
                return
            except Exception:
                logger.warning("answer_heartbeat_failed")

    async def process_claim(self, job_id: UUID, token: str) -> None:
        origin = None
        try:
            async with asyncio.timeout(0.25):
                async with self.session_factory() as db:
                    origin = await db.scalar(
                        select(RagAnswerJob.request_id).where(RagAnswerJob.id == job_id)
                    )
        except Exception:
            pass
        with job_context(job_id, request_id=origin):
            await self._process_claim(job_id, token)

    async def _process_claim(self, job_id: UUID, token: str) -> None:
        stop = asyncio.Event()
        task = asyncio.create_task(self._answer(job_id, token))
        heartbeat = asyncio.create_task(self._heartbeat(job_id, token, task, stop))
        try:
            async with asyncio.timeout(self.settings.rag_answer_job_timeout_seconds):
                await task
        except (asyncio.CancelledError, AnswerCancellationRequested):
            await self._cancel(job_id, token)
        except AnswerLeaseLost:
            logger.warning("answer_lease_lost")
        except AnswerAccessRevoked:
            await self._fail(job_id, token, "rag_access_revoked", "Subject access is no longer available.", retryable=False)
        except (AnswerCorpusChanged, KnowledgeScopeUnavailable, IncompatibleEmbeddingSpace):
            await self._fail(job_id, token, "rag_corpus_changed", "Course materials changed before the answer completed.", retryable=False)
        except AnswerProfileMismatch:
            await self._fail(job_id, token, "rag_profile_mismatch", "Ask AI configuration changed before execution.", retryable=False)
        except AIProviderError as exc:
            await self._fail(job_id, token, "rag_answer_failed", "Answer generation failed.", retryable=exc.retryable)
        except TimeoutError:
            await self._fail(job_id, token, "rag_answer_failed", "Answer generation failed.", retryable=True)
        except (InvalidQueryEmbedding, ValueError):
            await self._fail(job_id, token, "rag_answer_failed", "Answer generation failed.", retryable=False)
        except Exception:
            logger.warning("answer_internal_error")
            await self._fail(job_id, token, "rag_answer_failed", "Answer generation failed.", retryable=False)
        finally:
            stop.set()
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)

    async def _bounded_history(
        self, db: AsyncSession, job: RagAnswerJob, user: User
    ) -> tuple[tuple[str, str], ...]:
        history = await self.history_service.history(
            db,
            subject_id=job.subject_id,
            thread_id=job.thread_id,
            user=user,
            limit=min(200, self.settings.rag_answer_max_history_messages + 1),
        )
        selected: list[tuple[str, str]] = []
        used = 0
        for message in reversed(history.messages):
            if message.id == job.question_message_id or message.hidden or message.content is None:
                continue
            tokens = estimate_tokens(message.content)
            if used + tokens > self.settings.rag_answer_history_token_limit:
                continue
            selected.append((message.role, message.content))
            used += tokens
            if len(selected) == self.settings.rag_answer_max_history_messages:
                break
        return tuple(reversed(selected))

    async def _answer(self, job_id: UUID, token: str) -> None:
        async with self.session_factory() as db:
            job = await self._claimed_job(db, job_id, token)
            if not self._profile_matches(job):
                raise AnswerProfileMismatch()
            if not await self._session_active(db, job):
                raise AnswerAccessRevoked()
            user = await self._current_principal(db, job)
            question = await db.get(RagMessage, job.question_message_id)
            if user is None or question is None or question.role != "user" or question.thread_id != job.thread_id:
                raise AnswerAccessRevoked()
            try:
                document_ids = [UUID(value) for value in job.document_ids]
            except (TypeError, ValueError, AttributeError):
                raise ValueError("Invalid document selection snapshot") from None
            retriever = await KnowledgeRetriever.authorize(
                db,
                principal=user,
                subject_id=job.subject_id,
                query=question.content,
                document_ids=document_ids,
                limit=EXACT_V1_POLICY.max_results,
            )
            if retriever.scope.corpus_revision != job.corpus_revision:
                raise AnswerCorpusChanged()
            if retriever.scope.embedding_space_hash is not None and retriever.scope.embedding_space_hash != job.embedding_space_hash:
                raise AnswerCorpusChanged()
            history = await self._bounded_history(db, job, user)

        if retriever.scope.embedding_space_hash is None:
            await self._complete(job_id, token, answer=None, claims=())
            return

        await self._mark_provider_boundary(job_id, token)
        embedding_before = _snapshot(self.embedding_provider)
        embedding_response = None
        try:
            embedding_response = await self.embedding_provider.embed_query(question.content)
        finally:
            after = _snapshot(self.embedding_provider)
            requests, retries, waited = _attempt_delta(embedding_before, after)
            usage = _Usage(request_count=requests, retry_count=retries, waited_ms=waited, estimated=embedding_response is None)
            if embedding_response is not None:
                usage.input_tokens = embedding_response.usage.input_tokens
                usage.estimated = embedding_response.usage.estimated
                usage.cost_microusd = _embedding_cost(self.settings, usage.input_tokens)
            await self._persist_usage(job_id, token, usage)
        if embedding_response is None or len(embedding_response.vectors) != 1:
            raise InvalidQueryEmbedding()

        async with self.session_factory() as db:
            job = await self._claimed_job(db, job_id, token)
            user = await db.get(User, job.user_id)
            if user is None or not await self._session_active(db, job):
                raise AnswerAccessRevoked()
            retriever = await KnowledgeRetriever.authorize(
                db,
                principal=user,
                subject_id=job.subject_id,
                query=question.content,
                document_ids=[UUID(value) for value in job.document_ids],
                limit=EXACT_V1_POLICY.max_results,
            )
            if retriever.scope.corpus_revision != job.corpus_revision:
                raise AnswerCorpusChanged()
            result = await retriever.retrieve(
                embedding_response.vectors[0], embedding_space_hash=job.embedding_space_hash
            )
        await self._mark_retrieval_completed(job_id, token)
        if result.insufficient:
            await self._complete(job_id, token, answer=None, claims=())
            return

        system_prompt, user_prompt = render_answer_prompts(
            question=question.content, history=history, chunks=result.chunks
        )
        await self._check_text_budget(job_id, token, system_prompt, user_prompt, self.settings.rag_ai_max_output_tokens)
        answer_response = await self._model_call(
            job_id,
            token,
            response_model=GroundedAnswerOutput,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_output_tokens=self.settings.rag_ai_max_output_tokens,
            operation="rag_answer",
        )
        if answer_response.data.outcome == "abstain":
            await self._complete(job_id, token, answer=None, claims=())
            return
        if len(answer_response.data.answer) > self.settings.rag_answer_max_answer_chars:
            raise ValueError("Ask AI answer length bound exceeded")
        claims = validate_grounded_answer(answer_response.data, result.chunks)
        support_system, support_user = render_support_prompts(
            question=question.content,
            claims=claims,
            chunks=result.chunks,
        )
        support_limit = min(512, self.settings.rag_ai_max_output_tokens)
        await self._check_text_budget(job_id, token, support_system, support_user, support_limit)
        support_response = await self._model_call(
            job_id,
            token,
            response_model=ClaimSupportOutput,
            system_prompt=support_system,
            user_prompt=support_user,
            max_output_tokens=support_limit,
            operation="rag_support",
        )
        if not validate_support_output(support_response.data, len(claims)):
            await self._complete(
                job_id, token, answer=None, claims=(), support_rejected=True
            )
            return
        await self._complete(
            job_id, token, answer=answer_response.data.answer, claims=claims
        )

    async def _model_call(self, job_id: UUID, token: str, **kwargs: Any):
        before = _snapshot(self.answer_provider)
        response = None
        try:
            response = await self.answer_provider.generate_structured(**kwargs)
            return response
        finally:
            after = _snapshot(self.answer_provider)
            requests, retries, waited = _attempt_delta(before, after)
            usage = _Usage(request_count=requests, retry_count=retries, waited_ms=waited, estimated=response is None)
            if response is not None:
                usage.input_tokens = response.usage.input_tokens
                usage.output_tokens = response.usage.output_tokens
                usage.estimated = response.usage.estimated
                usage.cost_microusd = _ai_cost(self.settings, usage.input_tokens, usage.output_tokens)
            await self._persist_usage(job_id, token, usage)

    async def _check_text_budget(
        self, job_id: UUID, token: str, system_prompt: str, user_prompt: str, output_tokens: int
    ) -> None:
        estimated_input = estimate_tokens(f"{system_prompt}\n{user_prompt}")
        async with self.session_factory() as db:
            job = await self._claimed_job(db, job_id, token)
            if not await self._session_active(db, job):
                raise AnswerAccessRevoked()
            user = await self._current_principal(db, job)
            question = await db.get(RagMessage, job.question_message_id)
            if user is None or question is None:
                raise AnswerAccessRevoked()
            retriever = await KnowledgeRetriever.authorize(
                db,
                principal=user,
                subject_id=job.subject_id,
                query=question.content,
                document_ids=[UUID(value) for value in job.document_ids],
                limit=EXACT_V1_POLICY.max_results,
            )
            if (
                retriever.scope.corpus_revision != job.corpus_revision
                or retriever.scope.embedding_space_hash != job.embedding_space_hash
            ):
                raise AnswerCorpusChanged()
            consumed_input = job.actual_input_tokens or 0
            consumed_output = job.actual_output_tokens or 0
            if consumed_input + estimated_input > self.settings.rag_ai_max_job_input_tokens:
                raise ValueError("Ask AI input token bound exceeded")
            if consumed_output + output_tokens > self.settings.rag_ai_max_job_output_tokens:
                raise ValueError("Ask AI output token bound exceeded")
            projected_cost = (job.actual_cost_microusd or 0) + _ai_cost(
                self.settings, estimated_input, output_tokens
            )
            if projected_cost > int(self.settings.rag_ai_max_estimated_cost_usd * Decimal(1_000_000)):
                raise ValueError("Ask AI cost bound exceeded")

    async def _mark_provider_boundary(self, job_id: UUID, token: str) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                job = await self._claimed_job(db, job_id, token, for_update=True)
                if not await self._session_active(db, job):
                    raise AnswerAccessRevoked()
                user = await self._current_principal(db, job)
                question = await db.get(RagMessage, job.question_message_id)
                if user is None or question is None:
                    raise AnswerAccessRevoked()
                retriever = await KnowledgeRetriever.authorize(
                    db,
                    principal=user,
                    subject_id=job.subject_id,
                    query=question.content,
                    document_ids=[UUID(value) for value in job.document_ids],
                    limit=EXACT_V1_POLICY.max_results,
                )
                if (
                    retriever.scope.corpus_revision != job.corpus_revision
                    or retriever.scope.embedding_space_hash != job.embedding_space_hash
                ):
                    raise AnswerCorpusChanged()
                job.provider_call_started_at = job.provider_call_started_at or utcnow()
                job.updated_at = utcnow()

    async def _persist_usage(self, job_id: UUID, token: str, usage: _Usage) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                job = await self._claimed_job(db, job_id, token, for_update=True)
                job.actual_input_tokens = (job.actual_input_tokens or 0) + usage.input_tokens
                job.actual_output_tokens = (job.actual_output_tokens or 0) + usage.output_tokens
                job.provider_request_count += usage.request_count
                job.provider_retry_count += usage.retry_count
                job.provider_rate_limit_wait_milliseconds += usage.waited_ms
                job.actual_cost_microusd = (job.actual_cost_microusd or 0) + usage.cost_microusd
                job.usage_estimated = job.usage_estimated or usage.estimated
                job.updated_at = utcnow()

    async def _mark_retrieval_completed(self, job_id: UUID, token: str) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                job = await self._claimed_job(db, job_id, token, for_update=True)
                now = utcnow()
                job.retrieval_completed_at = job.retrieval_completed_at or now
                job.updated_at = now

    async def _complete(
        self,
        job_id: UUID,
        token: str,
        *,
        answer: str | None,
        claims: Sequence[ValidatedAnswerClaim],
        support_rejected: bool = False,
    ) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                await acquire_knowledge_write_lock(db)
                job = await self._claimed_job(db, job_id, token, for_update=True)
                if not self._profile_matches(job):
                    raise AnswerProfileMismatch()
                if not await self._session_active(db, job, for_update=True):
                    raise AnswerAccessRevoked()
                user = await self._current_principal(db, job, for_update=True)
                question = await db.get(RagMessage, job.question_message_id)
                thread = await db.get(RagThread, job.thread_id, with_for_update=True)
                if user is None or question is None or thread is None:
                    raise AnswerAccessRevoked()
                retriever = await KnowledgeRetriever.authorize(
                    db,
                    principal=user,
                    subject_id=job.subject_id,
                    query=question.content,
                    document_ids=[UUID(value) for value in job.document_ids],
                    limit=EXACT_V1_POLICY.max_results,
                )
                if retriever.scope.corpus_revision != job.corpus_revision:
                    raise AnswerCorpusChanged()
                current_sources = ()
                if claims:
                    if retriever.scope.embedding_space_hash != job.embedding_space_hash:
                        raise AnswerCorpusChanged()
                    current_sources = await retriever.read_current_sources(
                        [claim.source.chunk_id for claim in claims]
                    )
                    current_by_id = {source.chunk_id: source for source in current_sources}
                    if len(current_by_id) != len(claims):
                        raise AnswerCorpusChanged()
                    for claim in claims:
                        source = current_by_id.get(claim.source.chunk_id)
                        if source is None or claim.source_quote not in source.content:
                            raise AnswerCorpusChanged()
                elif retriever.scope.embedding_space_hash not in (None, job.embedding_space_hash):
                    raise AnswerCorpusChanged()

                now = utcnow()
                message = RagMessage(
                    thread_id=job.thread_id,
                    user_id=job.user_id,
                    subject_id=job.subject_id,
                    role="assistant",
                    outcome="answer" if claims else "abstained",
                    content=answer if claims else ABSTENTION_TEXT,
                    source_count=len(claims),
                    corpus_revision=job.corpus_revision,
                    embedding_space_hash=job.embedding_space_hash,
                    created_at=now,
                    expires_at=now + timedelta(days=self.settings.rag_chat_retention_days),
                )
                db.add(message)
                await db.flush()
                if claims:
                    current_by_id = {source.chunk_id: source for source in current_sources}
                    for order, claim in enumerate(claims, start=1):
                        source = current_by_id[claim.source.chunk_id]
                        db.add(RagMessageSource(
                            message_id=message.id,
                            thread_id=job.thread_id,
                            user_id=job.user_id,
                            subject_id=job.subject_id,
                            chunk_id=source.chunk_id,
                            document_id=source.document_id,
                            content_revision_id=source.content_revision_id,
                            index_revision_id=source.index_revision_id,
                            citation_order=order,
                            claim_text=claim.statement,
                            source_quote=claim.source_quote,
                            created_at=now,
                        ))
                    await db.flush()
                job.status = "completed"
                job.answer_message_id = message.id
                job.completed_at = now
                job.worker_id = None
                job.claim_token = None
                job.heartbeat_at = None
                job.lease_expires_at = None
                job.error_code = None
                job.error_message = None
                job.error_retryable = False
                if support_rejected:
                    job.support_rejection_count += 1
                job.updated_at = now
                thread.updated_at = now
                await db.flush()
        logger.info("answer_completed", extra={"job_id": job_id})

    async def _cancel(self, job_id: UUID, token: str) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                job = await db.scalar(select(RagAnswerJob).where(
                    RagAnswerJob.id == job_id,
                    RagAnswerJob.claim_token == token,
                ).with_for_update())
                if (
                    job is None
                    or job.status != "running"
                    or job.cancellation_requested_at is None
                ):
                    return
                now = utcnow()
                job.status = "cancelled"
                job.completed_at = now
                job.error_code = "rag_answer_cancelled"
                job.error_message = "Answer generation was cancelled."
                job.error_retryable = False
                job.worker_id = None
                job.claim_token = None
                job.heartbeat_at = None
                job.lease_expires_at = None
                job.updated_at = now

    async def _fail(
        self, job_id: UUID, token: str, code: str, message: str, *, retryable: bool
    ) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                job = await db.scalar(select(RagAnswerJob).where(
                    RagAnswerJob.id == job_id,
                    RagAnswerJob.claim_token == token,
                ).with_for_update())
                if job is None or job.status != "running":
                    return
                await self._fail_locked(job, code, message, retryable=retryable)

    @staticmethod
    async def _fail_locked(
        job: RagAnswerJob, code: str, message: str, *, retryable: bool
    ) -> None:
        now = utcnow()
        job.status = "failed"
        job.completed_at = now
        job.error_code = code
        job.error_message = message
        job.error_retryable = retryable
        job.worker_id = None
        job.claim_token = None
        job.heartbeat_at = None
        job.lease_expires_at = None
        job.updated_at = now

    async def recover_expired(self) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                now = utcnow()
                query = select(RagAnswerJob).where(
                    RagAnswerJob.status == "running",
                    RagAnswerJob.lease_expires_at <= now,
                ).order_by(RagAnswerJob.lease_expires_at, RagAnswerJob.id).limit(100)
                query = query.with_for_update(skip_locked=True) if db.get_bind().dialect.name == "postgresql" else query.with_for_update()
                for job in (await db.scalars(query)).all():
                    if job.cancellation_requested_at is not None:
                        await self._fail_locked(
                            job, "rag_answer_cancelled", "Answer generation was cancelled.", retryable=False
                        )
                        job.status = "cancelled"
                    elif (
                        job.provider_call_started_at is None
                        and job.attempt_count < job.max_attempts
                        and as_utc(job.deadline_at) > now
                        and await self._session_active(db, job)
                    ):
                        job.status = "queued"
                        delay = min(
                            self.settings.rag_answer_retry_base_seconds
                            * (2 ** max(0, job.attempt_count - 1)),
                            self.settings.rag_answer_retry_max_seconds,
                        )
                        job.available_at = now + timedelta(seconds=delay)
                        job.worker_id = None
                        job.claim_token = None
                        job.heartbeat_at = None
                        job.lease_expires_at = None
                        job.updated_at = now
                    else:
                        await self._fail_locked(
                            job,
                            "rag_answer_lease_expired",
                            "Answer worker lease expired.",
                            retryable=True,
                        )


__all__ = ["AnswerLeaseLost", "RagAnswerWorker"]
