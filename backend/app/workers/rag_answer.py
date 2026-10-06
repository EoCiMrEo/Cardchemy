"""Fenced durable worker for private, source-only Subject Knowledge search."""

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
from typing import Any, Protocol, Sequence
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.chunking import estimate_tokens
from app.ai.embeddings import EmbeddingProvider, get_embedding_provider
from app.ai.providers import (
    AIProviderError,
    ProviderAttemptScope,
    provider_attempt_scope,
)
from app.ai.related_evidence import RelatedExcerptSelection
from app.ai.related_evidence import _best_window
from app.ai import source_judgment_visual as visual_contract
from app.ai.providers.source_visual import GeminiVisualSourceJudge, VisualJudgeResponse as _JudgeResponse
from app.ai.source_navigation import (
    SOURCE_NAVIGATION_POLICY_ID, navigation_terms,
)
from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION, Settings, get_settings
from app.database import async_session_maker
from app.models.flashcard import Enrollment
from app.models.rag import (
    RagAnswerJob, RagAnswerStageAttempt, RagMessage,
    RagRelatedEvidence, RagThread,
)
from app.models.subject import Subject
from app.models.user import AuthSession, User, UserRole
from app.observability import job_context
from app.services.knowledge_lock import acquire_knowledge_write_lock
from app.services.knowledge_retrieval import (
    EXACT_V1_POLICY,
    SOURCE_NAVIGATION_RETRIEVAL_POLICY,
    IncompatibleEmbeddingSpace,
    InvalidQueryEmbedding,
    KnowledgeRetriever,
    KnowledgeScopeUnavailable,
    KnowledgeSourceUnavailable,
    RetrievedKnowledgeChunk,
)
from app.services.operations import pulse_worker
from app.services.rag_answers import RagAnswerService
from app.services.rag_question_context import (
    HydratedQuestionContext, QuestionContextUnavailable, rehydrate_question_context,
)
from app.services.source_visual_preparation import (
    PdfSourceBinding, check_pdf_bindings,
)
from app.services.source_visual_preparation import prepare_visual_sources
from app.time_utils import as_utc, utcnow
from app.workers.shutdown import drain_active_tasks


logger = logging.getLogger(__name__)

_SAFE_PROVIDER_CATEGORIES = frozenset({
    "ai_provider_not_configured", "invalid_ai_output", "ai_provider_timeout",
    "ai_provider_unavailable", "ai_provider_invalid_request",
    "ai_provider_authentication_failed", "ai_provider_access_denied",
    "ai_model_unavailable", "ai_provider_rate_limited",
    "ai_provider_rejected_request", "ai_provider_request_token_limit",
    "ai_model_output_incompatible", "ai_model_schema_incompatible",
    "invalid_embedding_output", "embedding_provider_timeout",
    "embedding_provider_unavailable", "embedding_provider_invalid_request",
    "embedding_provider_authentication_failed", "embedding_provider_access_denied",
    "embedding_model_unavailable", "embedding_provider_rate_limited",
    "embedding_provider_rejected_request", "embedding_provider_request_token_limit",
})
_SAFE_FAILURE_REASONS = frozenset({
    "transport_timeout", "transport_protocol", "transport_network",
    "http_invalid_request", "http_authentication", "http_access_denied",
    "http_model_missing", "http_rate_limited", "http_server_error",
    "http_transient", "http_rejected", "sdk_unclassified",
    "output_empty", "output_blocked", "output_unfinished", "json_invalid",
    "schema_invalid", "citation_invalid", "answer_too_long",
    "retrieval_failed", "retrieval_timeout", "local_support_unavailable",
    "local_support_timeout", "rag_access_revoked", "rag_corpus_changed",
    "internal_failure",
})
_LEXICAL_FALLBACK_CATEGORIES = frozenset({
    "embedding_provider_timeout", "embedding_provider_unavailable", "embedding_provider_rate_limited",
})
_VISUAL_SOURCE_JUDGE_POLICY = "related_knowledge_navigation_v8"
_SOURCE_JUDGE_ENDPOINT = "https://generativelanguage.googleapis.com"
_MAX_SOURCE_CANDIDATES = 4


def _safe_provider_category(code: str) -> str:
    return code if code in _SAFE_PROVIDER_CATEGORIES else "internal_failure"


def _safe_failure_reason(value: str | None) -> str | None:
    return value if value in _SAFE_FAILURE_REASONS else "internal_failure" if value else None


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


class AnswerQuestionContextChanged(RuntimeError):
    """Content-free failure for an unavailable immutable question binding."""


@dataclass(slots=True)
class _Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    request_count: int = 0
    retry_count: int = 0
    waited_ms: int = 0
    cost_microusd: int = 0
    estimated: bool = False
    has_usage: bool = False


@dataclass(frozen=True, slots=True)
class _CandidatePool:
    selections: tuple[RelatedExcerptSelection, ...]
    examined_chunks: int
    examined_pages: int
    examined_tokens: int


class _SourceJudge(Protocol):
    async def judge(self, wire: dict[str, Any]) -> _JudgeResponse: ...


def _attempt_usage(
    scope: ProviderAttemptScope,
    provider: object,
    operation: str,
) -> tuple[int, int, int]:
    """Read one invocation's counters without using shared cumulative deltas.

    Shipped providers mark each physical request in the context-local scope.
    Simple injected test providers do not have that instrumentation, so their
    one high-level invocation is counted once without consulting shared state.
    """

    telemetry = scope.snapshot()
    if telemetry.request_count == 0 and not callable(getattr(provider, "attempt_scope", None)):
        scope.record_request(operation, retry=False, waited_seconds=0.0)
        telemetry = scope.snapshot()
    return (
        telemetry.request_count,
        telemetry.retry_count,
        max(0, round(telemetry.rate_limit_wait_seconds * 1_000)),
    )


def _embedding_cost(settings: Settings, input_tokens: int) -> int:
    value = Decimal(input_tokens) * settings.rag_embedding_input_cost_per_million_usd
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def _judge_cost(
    input_tokens: int, output_tokens: int, *,
    input_price: int,
    output_price: int,
) -> int:
    value = (
        Decimal(input_tokens) * input_price
        + Decimal(output_tokens) * output_price
    ) / Decimal(1_000_000)
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def _judge_price_snapshot(price: Decimal) -> int:
    return int((price * Decimal(1_000_000)).to_integral_value(rounding=ROUND_CEILING))


def _strict_tokens(value: object) -> bool:
    return type(value) is int and value >= 0


async def _source_candidate_pool(
    query: str, chunks: Sequence[RetrievedKnowledgeChunk], retriever: KnowledgeRetriever,
) -> _CandidatePool:
    """Bounded current canonical pages, before any local final-page selection."""
    initial = tuple(chunks[:SOURCE_NAVIGATION_RETRIEVAL_POLICY.max_results])
    if not initial:
        return _CandidatePool((), 0, 0, 0)
    anchors: list[RetrievedKnowledgeChunk] = []
    anchor_pages: set[tuple[UUID, int]] = set()
    for chunk in initial:
        page = (chunk.document_id, chunk.page_number)
        if page not in anchor_pages:
            anchors.append(chunk)
            anchor_pages.add(page)
        if len(anchors) == 4:
            break
    neighbors = await retriever.expand_source_neighbors(
        tuple(anchors), radius=2, max_chunks=30, max_pages=12, max_tokens=8_192,
    )
    by_page: dict[tuple[UUID, int], RetrievedKnowledgeChunk] = {}
    for chunk in (*anchors, *(neighbor.chunk for neighbor in neighbors), *initial):
        if chunk.token_count <= 0:
            continue
        by_page.setdefault((chunk.document_id, chunk.page_number), chunk)
        if len(by_page) == 12:
            break
    if not by_page:
        return _CandidatePool((), 0, 0, 0)
    selected = tuple(by_page.values())
    current = await retriever.read_current_sources(tuple(chunk.chunk_id for chunk in selected))
    current_by_id = {source.chunk_id: source for source in current}
    if len(current_by_id) != len(selected) or any(
        current_by_id[chunk.chunk_id].document_id != chunk.document_id
        or current_by_id[chunk.chunk_id].content_revision_id != chunk.content_revision_id
        or current_by_id[chunk.chunk_id].index_revision_id != chunk.index_revision_id
        or current_by_id[chunk.chunk_id].page_number != chunk.page_number
        or current_by_id[chunk.chunk_id].content != chunk.content
        or current_by_id[chunk.chunk_id].embedding_space_hash != chunk.embedding_space_hash
        or current_by_id[chunk.chunk_id].corpus_revision != chunk.corpus_revision
        for chunk in selected
    ):
        raise KnowledgeSourceUnavailable()
    pages = await retriever.read_current_source_pages(
        tuple(chunk.chunk_id for chunk in selected), max_pages=12, max_tokens=8_192,
    )
    # The page reader omits stale, unauthorized, or over-budget pages. None
    # of those cases is evidence that there is no useful published source.
    if len(pages) != len(selected) or any(
        not isinstance(pages.get(chunk.chunk_id), str)
        or not pages[chunk.chunk_id].strip()
        for chunk in selected
    ):
        raise KnowledgeSourceUnavailable()
    terms = navigation_terms(query)
    ranked: list[tuple[int, float, int, RelatedExcerptSelection]] = []
    for index, chunk in enumerate(selected):
        page = pages.get(chunk.chunk_id)
        if not isinstance(page, str) or not page.strip():
            continue
        bounds = _best_window(page, terms)
        if bounds is None:
            continue
        start, end = bounds
        if end - start > 480:
            continue
        cue_hits = len(navigation_terms(page[start:end]) & terms)
        ranked.append((
            -cue_hits, -max(0.0, chunk.fusion_score), index,
            RelatedExcerptSelection(chunk, start, end, "canonical_page", page),
        ))
    ranked.sort(key=lambda item: item[:3])
    return _CandidatePool(
        tuple(item[3] for item in ranked[:_MAX_SOURCE_CANDIDATES]),
        examined_chunks=len(selected),
        examined_pages=len(pages),
        examined_tokens=sum(estimate_tokens(page) for page in pages.values()),
    )


class RagAnswerWorker:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session_factory: async_sessionmaker[AsyncSession] = async_session_maker,
        embedding_provider: EmbeddingProvider | None = None,
        source_judge: _SourceJudge | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory
        # RAG ships disabled. Keep that path credential-free and avoid creating
        # remote SDK clients until an enabled worker actually performs work.
        self._embedding_provider = embedding_provider
        self._source_judge = source_judge
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:12]}"
        from app.models.knowledge import embedding_space_hash
        self.space_hash = embedding_space_hash(self.settings.rag_embedding_space_identity)
        self.history_service = RagAnswerService(self.settings)

    @property
    def embedding_provider(self) -> EmbeddingProvider:
        if self._embedding_provider is None:
            one_call = self.settings.model_copy(update={"rag_embedding_provider_max_retries": 0})
            self._embedding_provider = get_embedding_provider(one_call)
        return self._embedding_provider

    @property
    def source_judge(self) -> _SourceJudge:
        if self._source_judge is None:
            self._source_judge = GeminiVisualSourceJudge(self.settings)
        return self._source_judge

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
        common = (
            job.result_kind is None
            and job.embedding_provider == self.settings.rag_embedding_provider
            and job.embedding_base_url == self.settings.rag_embedding_endpoint_identity
            and job.embedding_model == self.settings.rag_embedding_model
            and job.ai_provider is None
            and job.ai_base_url is None
            and job.ai_model is None
            and job.ai_catalog_version is None
            and job.ai_schema_policy_version is None
            and job.support_policy_version is None
            and job.embedding_space_hash == self.space_hash
            and job.retrieval_policy == SOURCE_NAVIGATION_RETRIEVAL_POLICY.policy_id
        )
        if not common:
            return False
        if job.answer_policy_version == _VISUAL_SOURCE_JUDGE_POLICY:
            return (
                ASK_REQUIRED_RELEASE_POLICY_VERSION == _VISUAL_SOURCE_JUDGE_POLICY
                and self.settings.rag_answer_available
                and self.settings.rag_source_judge_provider_enabled is True
                and job.source_judge_provider == self.settings.rag_source_judge_provider == "gemini"
                and job.source_judge_base_url == self.settings.rag_source_judge_endpoint_identity == _SOURCE_JUDGE_ENDPOINT
                and job.source_judge_model == self.settings.rag_source_judge_model == visual_contract.MODEL
                and job.source_judge_contract_version == self.settings.rag_source_judge_contract_version == visual_contract.CONTRACT_VERSION
                and job.source_judge_thinking_level == self.settings.rag_source_judge_thinking_level == "high"
                and job.source_judge_timeout_seconds == self.settings.rag_source_judge_provider_timeout_seconds
                and 0 < job.source_judge_timeout_seconds <= visual_contract.PROVIDER_TIMEOUT_SECONDS
                and job.source_context_policy_version == visual_contract.ADMISSION_SCHEMA
                and isinstance(job.source_context_admission_sha256, str)
                and len(job.source_context_admission_sha256) == 64
                and all(char in "0123456789abcdef" for char in job.source_context_admission_sha256)
                and job.source_judge_input_price_microusd_per_million == _judge_price_snapshot(
                    self.settings.rag_source_judge_input_cost_per_million_usd)
                and job.source_judge_input_price_microusd_per_million >= 300_000
                and job.source_judge_output_price_microusd_per_million == _judge_price_snapshot(
                    self.settings.rag_source_judge_output_cost_per_million_usd)
                and job.source_judge_output_price_microusd_per_million >= 2_500_000
                and job.source_judge_max_input_tokens == self.settings.rag_source_judge_max_input_tokens == visual_contract.MAX_INPUT_TOKENS
                and job.source_judge_max_output_tokens == self.settings.rag_source_judge_max_output_tokens == visual_contract.MAX_OUTPUT_TOKENS
                and self.settings.rag_source_judge_provider_max_retries == 0
            )
        return False

    async def claim_next(self) -> tuple[UUID, str] | None:
        if not self.settings.rag_answer_available:
            return None
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
        task = asyncio.create_task(self._source_first(job_id, token))
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
        except (AnswerCorpusChanged, KnowledgeScopeUnavailable,
                KnowledgeSourceUnavailable, IncompatibleEmbeddingSpace):
            await self._fail(job_id, token, "rag_corpus_changed", "Course materials changed before the answer completed.", retryable=False)
        except AnswerProfileMismatch:
            await self._fail(job_id, token, "rag_profile_mismatch", "Ask AI configuration changed before execution.", retryable=False)
        except AnswerQuestionContextChanged:
            await self._fail(job_id, token, "rag_question_context_changed", "The question context changed or expired. Start a new search.", retryable=False)
        except AIProviderError as exc:
            await self._fail(job_id, token, "rag_answer_failed", "Answer generation failed.", retryable=exc.retryable)
        except TimeoutError:
            await self._fail(
                job_id, token, "rag_answer_failed", "Answer generation failed.",
                retryable=True, timed_out=True,
            )
        except (InvalidQueryEmbedding, ValueError):
            await self._fail(job_id, token, "rag_answer_failed", "Answer generation failed.", retryable=False)
        except Exception:
            logger.warning("answer_internal_error")
            await self._fail(job_id, token, "rag_answer_failed", "Answer generation failed.", retryable=False)
        finally:
            stop.set()
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)


    async def _question_context(
        self, db: AsyncSession, job: RagAnswerJob, *,
        expected: HydratedQuestionContext | None = None,
    ) -> HydratedQuestionContext:
        try:
            hydrated = await rehydrate_question_context(db, job=job, checked_at=utcnow())
            if expected is not None and (
                hydrated.snapshot != expected.snapshot or hydrated.binding != expected.binding
                or hydrated.question != expected.question or hydrated.local_query != expected.local_query
            ):
                raise QuestionContextUnavailable()
            return hydrated
        except QuestionContextUnavailable:
            raise AnswerQuestionContextChanged() from None

    async def _source_first(self, job_id: UUID, token: str) -> None:
        async with self.session_factory() as db:
            job = await self._claimed_job(db, job_id, token)
            if not self._profile_matches(job):
                raise AnswerProfileMismatch()
            if not await self._session_active(db, job):
                raise AnswerAccessRevoked()
            user = await self._current_principal(db, job)
            question = await db.get(RagMessage, job.question_message_id)
            if (
                user is None or question is None or question.role != "user"
                or question.thread_id != job.thread_id
            ):
                raise AnswerAccessRevoked()
            try:
                document_ids = [UUID(value) for value in job.document_ids]
            except (TypeError, ValueError, AttributeError):
                raise ValueError("Invalid document selection snapshot") from None
            retriever = await KnowledgeRetriever.authorize(
                db, principal=user, subject_id=job.subject_id,
                query=question.content, document_ids=document_ids,
                limit=SOURCE_NAVIGATION_RETRIEVAL_POLICY.max_results,
                policy=SOURCE_NAVIGATION_RETRIEVAL_POLICY,
            )
            if retriever.scope.corpus_revision != job.corpus_revision:
                raise AnswerCorpusChanged()
            if retriever.scope.embedding_space_hash not in (None, job.embedding_space_hash):
                raise AnswerCorpusChanged()
            context = await self._question_context(db, job)
            if context.question != question.content:
                raise AnswerQuestionContextChanged()
            local_query = None if context.needs_clarification else context.local_query

        # An unresolved referent is not sent to the provider or guessed from
        # unrelated vector matches. It is a terminal, source-free no_match.
        if local_query is None or retriever.scope.embedding_space_hash is None:
            logger.info("knowledge_source_selection", extra={
                "selection_policy": SOURCE_NAVIGATION_POLICY_ID,
                "selection_status": "clarification_needed" if local_query is None else "no_active_space",
                "anchor_chunks": 0, "examined_chunks": 0, "neighbor_radius": 0,
            })
            await self._complete_source(
                job_id, token, selections=(),
                clarification_needed=local_query is None,
            )
            return

        await self._mark_provider_boundary(job_id, token)
        embedding_stage_id = await self._begin_stage(job_id, token, "query_embedding", remote=True)
        embedding_response = None
        embedding_error: str | None = None
        embedding_reason: str | None = None
        embedding_uncertain = False
        async with provider_attempt_scope(self.embedding_provider) as attempt_scope:
            try:
                # Never send history, snippets, or locally expanded query terms.
                embedding_response = await self.embedding_provider.embed_query(question.content)
            except AIProviderError as exc:
                embedding_error = _safe_provider_category(exc.code)
                embedding_reason = _safe_failure_reason(exc.reason_code)
                embedding_uncertain = exc.code in {
                    "embedding_provider_timeout", "embedding_provider_unavailable",
                }
                if embedding_error not in _LEXICAL_FALLBACK_CATEGORIES:
                    raise
            except TimeoutError:
                embedding_error = "embedding_provider_timeout"
                embedding_reason = "transport_timeout"
                embedding_uncertain = True
                # The remote attempt is finished and will not be replayed.
                # Continue with local lexical search while preserving unknown
                # cost/execution telemetry from the timed-out request.
            except BaseException:
                embedding_error = "internal_failure"
                embedding_uncertain = True
                raise
            finally:
                requests, retries, waited = _attempt_usage(
                    attempt_scope, self.embedding_provider, "embedding_query"
                )
                usage = _Usage(
                    request_count=requests, retry_count=retries, waited_ms=waited,
                    estimated=embedding_response is None,
                )
                if embedding_response is not None:
                    usage.input_tokens = embedding_response.usage.input_tokens
                    usage.estimated = embedding_response.usage.estimated
                    usage.has_usage = True
                    usage.cost_microusd = _embedding_cost(self.settings, usage.input_tokens)
                await self._finish_stage(
                    job_id, token, embedding_stage_id, usage, embedding_error,
                    embedding_uncertain, failure_reason=embedding_reason,
                )
        if embedding_response is not None and len(embedding_response.vectors) != 1:
            raise InvalidQueryEmbedding()
        if embedding_response is None and embedding_error not in _LEXICAL_FALLBACK_CATEGORIES:
            raise InvalidQueryEmbedding()
        if (usage.request_count > 1 or usage.retry_count != 0
            or embedding_response is not None and usage.request_count != 1):
            raise AnswerProfileMismatch()

        retrieval_stage_id = await self._begin_stage(job_id, token, "retrieval", remote=False)
        retrieval_error: str | None = None
        retrieval_reason: str | None = None
        result = None
        selections: tuple[RelatedExcerptSelection, ...] = ()
        selection_status = "no_candidate"
        selection_examined = 0
        selection_pages = 0
        selection_tokens = 0
        neighbor_radius = 0
        try:
            async with self.session_factory() as db:
                job = await self._claimed_job(db, job_id, token)
                user = await self._current_principal(db, job)
                if user is None or not await self._session_active(db, job):
                    raise AnswerAccessRevoked()
                retriever = await KnowledgeRetriever.authorize(
                    db, principal=user, subject_id=job.subject_id,
                    query=local_query, document_ids=[UUID(value) for value in job.document_ids],
                    limit=SOURCE_NAVIGATION_RETRIEVAL_POLICY.max_results,
                    policy=SOURCE_NAVIGATION_RETRIEVAL_POLICY,
                )
                if (
                    retriever.scope.corpus_revision != job.corpus_revision
                    or retriever.scope.embedding_space_hash != job.embedding_space_hash
                ):
                    raise AnswerCorpusChanged()
                result = (await retriever.retrieve(
                    embedding_response.vectors[0], embedding_space_hash=job.embedding_space_hash,
                ) if embedding_response is not None else await retriever.retrieve_lexical())
                if not result.insufficient:
                    pool = await _source_candidate_pool(local_query, result.chunks, retriever)
                    selections = pool.selections
                    selection_status = "candidate_pool" if selections else "no_candidate"
                    selection_examined = pool.examined_chunks
                    selection_pages = pool.examined_pages
                    selection_tokens = pool.examined_tokens
                    neighbor_radius = 2
        except AnswerAccessRevoked:
            retrieval_error = "rag_access_revoked"
            raise
        except (AnswerCorpusChanged, KnowledgeScopeUnavailable, IncompatibleEmbeddingSpace):
            retrieval_error = "rag_corpus_changed"
            raise
        except TimeoutError:
            retrieval_error = "retrieval_failed"
            retrieval_reason = "retrieval_timeout"
            raise
        except BaseException:
            retrieval_error = "retrieval_failed"
            raise
        finally:
            ranks = None if result is None else [
                {
                    "vector_rank": chunk.vector_rank
                    if isinstance(chunk.vector_rank, int) and 1 <= chunk.vector_rank <= 20 else None,
                    "lexical_rank": chunk.lexical_rank
                    if isinstance(chunk.lexical_rank, int) and 1 <= chunk.lexical_rank <= 20 else None,
                }
                for chunk in result.chunks[:SOURCE_NAVIGATION_RETRIEVAL_POLICY.max_results]
            ]
            await self._finish_stage(
                job_id, token, retrieval_stage_id, _Usage(), retrieval_error, False,
                failure_reason=retrieval_reason or retrieval_error,
                retrieval_ranks=ranks,
            )
        first_stage_ids = () if result is None else tuple(chunk.chunk_id for chunk in result.chunks)
        logger.info("knowledge_source_selection", extra={
            "selection_policy": SOURCE_NAVIGATION_POLICY_ID,
            "selection_status": selection_status,
            "anchor_chunks": 0 if result is None else len(result.chunks),
            "examined_chunks": selection_examined,
            "examined_pages": selection_pages,
            "examined_tokens": selection_tokens,
            "neighbor_radius": neighbor_radius,
            "selected_chunks": len(selections),
            "selected_neighbor_chunks": sum(item.source.chunk_id not in first_stage_ids for item in selections),
            "selected_beyond_top5": sum(item.source.chunk_id in first_stage_ids[5:] for item in selections),
        })
        pdf_bindings: tuple[PdfSourceBinding, ...] = ()
        clarification_needed = False
        if selections:
            selections, clarification_needed, pdf_bindings = await self._judge_visual_sources(
                job_id, token, question.content, selections,
            )
        await self._complete_source(job_id, token, selections=selections,
                                    clarification_needed=clarification_needed, pdf_bindings=pdf_bindings)

    async def _mark_provider_boundary(self, job_id: UUID, token: str) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                job = await self._claimed_job(db, job_id, token, for_update=True)
                if not self._profile_matches(job):
                    raise AnswerProfileMismatch()
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
                    limit=SOURCE_NAVIGATION_RETRIEVAL_POLICY.max_results,
                    policy=SOURCE_NAVIGATION_RETRIEVAL_POLICY,
                )
                if (
                    retriever.scope.corpus_revision != job.corpus_revision
                    or retriever.scope.embedding_space_hash != job.embedding_space_hash
                ):
                    raise AnswerCorpusChanged()
                if job.answer_policy_version == _VISUAL_SOURCE_JUDGE_POLICY:
                    context = await self._question_context(db, job)
                    if context.needs_clarification:
                        raise AnswerQuestionContextChanged()
                job.provider_call_started_at = job.provider_call_started_at or utcnow()
                job.updated_at = utcnow()

    async def _begin_stage(
        self, job_id: UUID, token: str, stage: str, *, remote: bool,
        judge_selections: Sequence[RelatedExcerptSelection] = (),
        judge_pdf_bindings: Sequence[PdfSourceBinding] = (),
        judge_question_context: HydratedQuestionContext | None = None,
    ) -> UUID:
        async with self.session_factory() as db:
            async with db.begin():
                job = await self._claimed_job(db, job_id, token, for_update=True)
                if (not self._profile_matches(job)
                    or stage not in {"query_embedding", "retrieval", "source_judgment"}
                    or stage == "source_judgment" and job.answer_policy_version != _VISUAL_SOURCE_JUDGE_POLICY):
                    raise AnswerProfileMismatch()
                if stage == "query_embedding":
                    if job.answer_policy_version == _VISUAL_SOURCE_JUDGE_POLICY:
                        context = await self._question_context(db, job)
                        if context.needs_clarification:
                            raise AnswerQuestionContextChanged()
                    prior_embedding = await db.scalar(
                        select(RagAnswerStageAttempt).where(
                            RagAnswerStageAttempt.job_id == job.id,
                            RagAnswerStageAttempt.manual_retry_number == job.manual_retry_count,
                            RagAnswerStageAttempt.stage == "query_embedding",
                        ).limit(1)
                    )
                    if prior_embedding is not None:
                        raise AnswerProfileMismatch()
                elif stage == "retrieval":
                    prior_embedding = await db.scalar(
                        select(RagAnswerStageAttempt).where(
                            RagAnswerStageAttempt.job_id == job.id,
                            RagAnswerStageAttempt.manual_retry_number == job.manual_retry_count,
                            RagAnswerStageAttempt.stage == "query_embedding",
                            RagAnswerStageAttempt.completed_at.is_not(None),
                            RagAnswerStageAttempt.physical_request_count <= 1,
                            RagAnswerStageAttempt.retry_count == 0,
                        )
                    )
                    if (prior_embedding is None or not (
                        (prior_embedding.error_category is None
                         and prior_embedding.physical_request_count == 1)
                        or prior_embedding.error_category in _LEXICAL_FALLBACK_CATEGORIES
                    )):
                        raise AnswerProfileMismatch()
                else:
                    prior = await db.scalar(select(RagAnswerStageAttempt).where(
                        RagAnswerStageAttempt.job_id == job.id,
                        RagAnswerStageAttempt.manual_retry_number == job.manual_retry_count,
                        RagAnswerStageAttempt.stage == "source_judgment",
                    ).limit(1))
                    retrieval = await db.scalar(select(RagAnswerStageAttempt).where(
                        RagAnswerStageAttempt.job_id == job.id,
                        RagAnswerStageAttempt.manual_retry_number == job.manual_retry_count,
                        RagAnswerStageAttempt.stage == "retrieval",
                        RagAnswerStageAttempt.completed_at.is_not(None),
                        RagAnswerStageAttempt.error_category.is_(None),
                    ).limit(1))
                    if (prior is not None or retrieval is None
                        or not 1 <= len(judge_selections) <= _MAX_SOURCE_CANDIDATES
                        or job.estimated_cost_microusd is None
                        or job.attempt_cost_microusd + _judge_cost(
                            job.source_judge_max_input_tokens,
                            job.source_judge_max_output_tokens,
                            input_price=job.source_judge_input_price_microusd_per_million,
                            output_price=job.source_judge_output_price_microusd_per_million,
                        ) > job.estimated_cost_microusd):
                        raise AnswerProfileMismatch()
                    await self._validate_judge_inputs(
                        db, job, judge_selections, judge_pdf_bindings, judge_question_context,
                    )
                row = RagAnswerStageAttempt(
                    job_id=job.id,
                    manual_retry_number=job.manual_retry_count,
                    worker_attempt_number=job.attempt_count,
                    stage=stage,
                    answer_policy_version=job.answer_policy_version,
                    execution_uncertain=remote,
                )
                db.add(row)
                await db.flush()
                return row.id

    async def _validate_judge_inputs(
        self, db: AsyncSession, job: RagAnswerJob,
        selections: Sequence[RelatedExcerptSelection], pdf_bindings: Sequence[PdfSourceBinding],
        expected_context: HydratedQuestionContext | None,
    ) -> None:
        if not await self._session_active(db, job):
            raise AnswerAccessRevoked()
        user = await self._current_principal(db, job)
        question = await db.get(RagMessage, job.question_message_id)
        if user is None or question is None:
            raise AnswerAccessRevoked()
        retriever = await KnowledgeRetriever.authorize(
            db, principal=user, subject_id=job.subject_id, query=question.content,
            document_ids=[UUID(value) for value in job.document_ids],
            limit=SOURCE_NAVIGATION_RETRIEVAL_POLICY.max_results,
            policy=SOURCE_NAVIGATION_RETRIEVAL_POLICY,
        )
        if (retriever.scope.corpus_revision != job.corpus_revision
            or retriever.scope.embedding_space_hash != job.embedding_space_hash):
            raise AnswerCorpusChanged()
        current = await retriever.read_current_sources(tuple(item.source.chunk_id for item in selections))
        by_id = {source.chunk_id: source for source in current}
        pages = await retriever.read_current_source_pages(
            tuple(by_id), max_pages=_MAX_SOURCE_CANDIDATES, max_tokens=8_192,
        )
        if len(by_id) != len(selections) or len(pages) != len(selections):
            raise AnswerCorpusChanged()
        for item in selections:
            source = by_id.get(item.source.chunk_id)
            if (source is None or item.source_kind != "canonical_page"
                or source.content != item.source.content or source.section != item.source.section
                or source.document_id != item.source.document_id
                or source.content_revision_id != item.source.content_revision_id
                or source.index_revision_id != item.source.index_revision_id
                or source.page_number != item.source.page_number
                or source.embedding_space_hash != job.embedding_space_hash
                or source.corpus_revision != job.corpus_revision
                or pages.get(item.source.chunk_id) != item.page_content
                or item.page_content is None or item.start_offset < 0
                or item.end_offset <= item.start_offset or item.end_offset - item.start_offset > 480
                or item.end_offset > len(item.page_content)
                or item.page_content[item.start_offset:item.end_offset] != item.quote):
                raise AnswerCorpusChanged()
        if job.answer_policy_version == _VISUAL_SOURCE_JUDGE_POLICY:
            bindings = {binding.content_revision_id: binding for binding in pdf_bindings}
            if (len(bindings) != len(pdf_bindings) or not bindings
                or set(bindings) != {item.source.content_revision_id for item in selections}
                or any(binding.subject_id != job.subject_id for binding in bindings.values())
                or any(bindings[item.source.content_revision_id].document_id != item.source.document_id
                       or item.source.page_number > bindings[item.source.content_revision_id].page_count
                       for item in selections)):
                raise AnswerCorpusChanged()
            await check_pdf_bindings(db, tuple(bindings.values()))
            if expected_context is None:
                raise AnswerQuestionContextChanged()
            context = await self._question_context(db, job, expected=expected_context)
            if context.question != question.content or context.needs_clarification:
                raise AnswerQuestionContextChanged()

    async def _recheck_visual_dispatch(
        self, job_id: UUID, token: str, candidates: Sequence[RelatedExcerptSelection],
        pdf_bindings: Sequence[PdfSourceBinding], context: HydratedQuestionContext,
    ) -> None:
        """Fresh access/context fence after quota wait, immediately before HTTP."""
        async with self.session_factory() as db:
            async with db.begin():
                job = await self._claimed_job(db, job_id, token, for_update=True)
                if not self._profile_matches(job) or job.answer_policy_version != _VISUAL_SOURCE_JUDGE_POLICY:
                    raise AnswerProfileMismatch()
                await self._validate_judge_inputs(db, job, candidates, pdf_bindings, context)

    async def _judge_visual_sources(
        self, job_id: UUID, token: str, question: str,
        candidates: Sequence[RelatedExcerptSelection],
    ) -> tuple[tuple[RelatedExcerptSelection, ...], bool, tuple[PdfSourceBinding, ...]]:
        """Render authenticated current PDFs, then fence one issued-ID dispatch."""
        async with self.session_factory() as db:
            job = await self._claimed_job(db, job_id, token)
            if not self._profile_matches(job) or job.answer_policy_version != _VISUAL_SOURCE_JUDGE_POLICY:
                raise AnswerProfileMismatch()
            if not await self._session_active(db, job):
                raise AnswerAccessRevoked()
            user = await self._current_principal(db, job)
            message = await db.get(RagMessage, job.question_message_id)
            if user is None or message is None or message.content != question:
                raise AnswerAccessRevoked()
            retriever = await KnowledgeRetriever.authorize(
                db, principal=user, subject_id=job.subject_id, query=question,
                document_ids=[UUID(value) for value in job.document_ids],
                limit=SOURCE_NAVIGATION_RETRIEVAL_POLICY.max_results,
                policy=SOURCE_NAVIGATION_RETRIEVAL_POLICY,
            )
            if (retriever.scope.corpus_revision != job.corpus_revision
                or retriever.scope.embedding_space_hash != job.embedding_space_hash):
                raise AnswerCorpusChanged()
            context = await self._question_context(db, job)
            if context.question != question or context.needs_clarification:
                raise AnswerQuestionContextChanged()
            prepared = await prepare_visual_sources(
                db, settings=self.settings, retriever=retriever, subject_id=job.subject_id,
                question=question, selections=candidates,
                snapshot=context.snapshot, checked_at=utcnow(),
                raw_navigation_query=context.raw_navigation_query,
                preceding_question=context.preceding_question, anchor=context.binding.anchor,
            )
        stage_id = await self._begin_stage(
            job_id, token, "source_judgment", remote=True,
            judge_selections=candidates, judge_pdf_bindings=prepared.bindings,
            judge_question_context=context,
        )
        issued = [f"S{index:02d}" for index in range(1, len(candidates) + 1)]
        response, verdict, category, reason, finish = None, None, None, None, None
        async with provider_attempt_scope(self.source_judge) as scope:
            try:
                async def before_dispatch() -> None:
                    await self._recheck_visual_dispatch(
                        job_id, token, candidates, prepared.bindings, context,
                    )

                call = (self.source_judge.judge(prepared.request, before_dispatch=before_dispatch)
                        if isinstance(self.source_judge, GeminiVisualSourceJudge)
                        else self.source_judge.judge(prepared.request))
                response = await asyncio.wait_for(
                    call,
                    timeout=self.settings.rag_source_judge_provider_timeout_seconds,
                )
                finish = response.finish_reason
                visual_contract.validate_usage(response.input_tokens, response.candidate_tokens,
                                               thinking_tokens=response.thinking_tokens)
                if finish != "STOP":
                    raise visual_contract.VisualSourceJudgmentError("output_unfinished")
                verdict = visual_contract.parse_verdict(response.raw_json, issued)
            except AIProviderError as error:
                category, reason = _safe_provider_category(error.code), _safe_failure_reason(error.reason_code)
                raise
            except TimeoutError:
                category, reason = "ai_provider_timeout", "transport_timeout"
                raise
            except visual_contract.VisualSourceJudgmentError as error:
                category = "invalid_ai_output"
                reason = "output_unfinished" if str(error) == "output_unfinished" else "schema_invalid"
                raise
            except (AnswerQuestionContextChanged, AnswerAccessRevoked, AnswerCorpusChanged,
                    AnswerLeaseLost, AnswerCancellationRequested, AnswerProfileMismatch):
                category, reason = "rag_dispatch_revoked", "rag_access_revoked"
                raise
            except BaseException:
                category, reason = "ai_provider_unavailable", "sdk_unclassified"
                raise
            finally:
                requests, retries, waited = _attempt_usage(scope, self.source_judge, "source_judgment")
                known = (response is not None and _strict_tokens(response.input_tokens)
                         and _strict_tokens(response.candidate_tokens) and _strict_tokens(response.thinking_tokens))
                usage = _Usage(request_count=requests, retry_count=retries, waited_ms=waited,
                               estimated=not known, has_usage=known)
                if known:
                    usage.input_tokens = response.input_tokens
                    usage.output_tokens = response.candidate_tokens + response.thinking_tokens
                    usage.cost_microusd = _judge_cost(
                        usage.input_tokens, usage.output_tokens,
                        input_price=_judge_price_snapshot(self.settings.rag_source_judge_input_cost_per_million_usd),
                        output_price=_judge_price_snapshot(self.settings.rag_source_judge_output_cost_per_million_usd),
                    )
                await self._finish_stage(job_id, token, stage_id, usage, category,
                                         uncertain=category is not None and requests > 0,
                                         failure_reason=reason, finish_reason=finish)
        if requests != 1 or retries != 0 or verdict is None:
            raise AnswerProfileMismatch()
        by_id = dict(zip(issued, candidates))
        return (tuple(by_id[sid] for sid in verdict["selected_ids"]),
                verdict["question_status"] == "needs_clarification", prepared.bindings)


    async def _finish_stage(
        self,
        job_id: UUID,
        token: str,
        stage_id: UUID,
        usage: _Usage,
        category: str | None,
        uncertain: bool,
        *,
        failure_reason: str | None = None,
        retrieval_ranks: list[dict[str, int | None]] | None = None,
        finish_reason: str | None = None,
    ) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                job = await self._claimed_job(db, job_id, token, for_update=True)
                row = await db.get(RagAnswerStageAttempt, stage_id, with_for_update=True)
                if row is None or row.job_id != job_id or row.completed_at is not None:
                    raise AnswerLeaseLost()
                now = utcnow()
                row.completed_at = now
                row.elapsed_milliseconds = max(0, round((now - as_utc(row.started_at)).total_seconds() * 1_000))
                row.physical_request_count = usage.request_count
                row.retry_count = usage.retry_count
                row.rate_limit_wait_milliseconds = usage.waited_ms
                row.error_category = category
                row.failure_reason = _safe_failure_reason(failure_reason)
                row.provider_finish_reason = finish_reason if finish_reason in {
                    "STOP", "MAX_TOKENS", "SAFETY", "RECITATION", "OTHER",
                    "BLOCKLIST", "PROHIBITED_CONTENT", "SPII",
                } else None
                if getattr(usage, "has_usage", False):
                    row.input_tokens = usage.input_tokens
                    row.output_tokens = usage.output_tokens
                    row.usage_estimated = usage.estimated
                if row.stage == "retrieval" and retrieval_ranks is not None:
                    row.retrieval_ranks = retrieval_ranks[:EXACT_V1_POLICY.max_results]
                row.execution_uncertain = uncertain
                job.actual_input_tokens = (job.actual_input_tokens or 0) + usage.input_tokens
                job.actual_output_tokens = (job.actual_output_tokens or 0) + usage.output_tokens
                job.provider_request_count += usage.request_count
                job.provider_retry_count += usage.retry_count
                job.provider_rate_limit_wait_milliseconds += usage.waited_ms
                job.actual_cost_microusd = (job.actual_cost_microusd or 0) + usage.cost_microusd
                job.attempt_cost_microusd += usage.cost_microusd
                job.attempt_cost_unknown = job.attempt_cost_unknown or (
                    usage.request_count > 0 and usage.estimated
                ) or uncertain
                job.usage_estimated = job.usage_estimated or usage.estimated
                if category is not None:
                    job.failed_stage = row.stage
                    job.provider_error_category = category
                    job.failure_reason = row.failure_reason
                job.execution_uncertain = job.execution_uncertain or uncertain
                job.updated_at = now

    async def _complete_source(
        self, job_id: UUID, token: str, *,
        selections: Sequence[RelatedExcerptSelection],
        clarification_needed: bool = False,
        pdf_bindings: Sequence[PdfSourceBinding] = (),
    ) -> None:
        """Commit a source-only terminal result and its exact references atomically."""

        if len(selections) > 3:
            raise ValueError("Too many related Knowledge references")
        if clarification_needed and selections:
            raise ValueError("Clarification cannot include related Knowledge references")
        async with self.session_factory() as db:
            async with db.begin():
                await acquire_knowledge_write_lock(db)
                job = await self._claimed_job(db, job_id, token, for_update=True)
                if not self._profile_matches(job):
                    raise AnswerProfileMismatch()
                if clarification_needed and job.answer_policy_version != _VISUAL_SOURCE_JUDGE_POLICY:
                    raise AnswerProfileMismatch()
                if not await self._session_active(db, job, for_update=True):
                    raise AnswerAccessRevoked()
                user = await self._current_principal(db, job, for_update=True)
                question = await db.get(RagMessage, job.question_message_id)
                thread = await db.get(RagThread, job.thread_id, with_for_update=True)
                if (
                    user is None or question is None or thread is None
                    or question.role != "user" or question.thread_id != job.thread_id
                ):
                    raise AnswerAccessRevoked()
                now = utcnow()
                if as_utc(question.expires_at) <= now:
                    raise AnswerAccessRevoked()
                retriever = await KnowledgeRetriever.authorize(
                    db, principal=user, subject_id=job.subject_id,
                    query=question.content,
                    document_ids=[UUID(value) for value in job.document_ids],
                    limit=SOURCE_NAVIGATION_RETRIEVAL_POLICY.max_results,
                    policy=SOURCE_NAVIGATION_RETRIEVAL_POLICY,
                )
                if (
                    retriever.scope.corpus_revision != job.corpus_revision
                    or retriever.scope.embedding_space_hash not in (None, job.embedding_space_hash)
                ):
                    raise AnswerCorpusChanged()
                if selections and retriever.scope.embedding_space_hash != job.embedding_space_hash:
                    raise AnswerCorpusChanged()
                if job.answer_policy_version == _VISUAL_SOURCE_JUDGE_POLICY:
                    context = await self._question_context(db, job)
                    if context.question != question.content or context.needs_clarification and not clarification_needed:
                        raise AnswerQuestionContextChanged()
                    bindings = {item.content_revision_id: item for item in pdf_bindings}
                    if (len(bindings) != len(pdf_bindings)
                        or any(item.subject_id != job.subject_id for item in bindings.values())
                        or any(selection.source.content_revision_id not in bindings
                               or bindings[selection.source.content_revision_id].document_id != selection.source.document_id
                               for selection in selections)):
                        raise AnswerCorpusChanged()
                    await check_pdf_bindings(db, tuple(bindings.values()))
                current_sources = (
                    await retriever.read_current_sources(
                        [selection.source.chunk_id for selection in selections]
                    ) if selections else ()
                )
                current_by_id = {source.chunk_id: source for source in current_sources}
                if len(current_by_id) != len(selections):
                    raise AnswerCorpusChanged()
                page_anchor_ids = tuple(selection.source.chunk_id for selection in selections
                                        if selection.source_kind == "canonical_page")
                current_pages = (await retriever.read_current_source_pages(
                    page_anchor_ids, max_pages=3, max_tokens=8_192,
                ) if page_anchor_ids else {})
                if len(current_pages) != len(page_anchor_ids):
                    raise AnswerCorpusChanged()
                seen_pages: set[tuple[UUID, int]] = set()
                for selection in selections:
                    source = current_by_id.get(selection.source.chunk_id)
                    page = (selection.source.document_id, selection.source.page_number)
                    if selection.source_kind == "canonical_page":
                        authoritative_content = current_pages.get(selection.source.chunk_id)
                        if (authoritative_content is None
                            or authoritative_content != selection.page_content
                            or source is None
                            or source.content != selection.source.content
                            or source.section != selection.source.section):
                            raise AnswerCorpusChanged()
                    elif selection.source_kind == "chunk":
                        authoritative_content = source.content if source else ""
                    else:
                        raise AnswerCorpusChanged()
                    if (
                        source is None or page in seen_pages
                        or source.document_id != selection.source.document_id
                        or source.content_revision_id != selection.source.content_revision_id
                        or source.index_revision_id != selection.source.index_revision_id
                        or source.embedding_space_hash != job.embedding_space_hash
                        or source.corpus_revision != job.corpus_revision
                        or source.page_number != selection.source.page_number
                        or selection.start_offset < 0
                        or selection.end_offset <= selection.start_offset
                        or selection.end_offset - selection.start_offset > 480
                        or selection.end_offset > len(authoritative_content)
                        or authoritative_content[selection.start_offset:selection.end_offset] != selection.quote
                    ):
                        raise AnswerCorpusChanged()
                    seen_pages.add(page)

                # A locally ambiguous question can finish before any query
                # embedding or retrieval. Preserve NULL in that case: the
                # database's retrieval-timing guard requires a provider
                # boundary before a retrieval completion timestamp.
                if job.provider_call_started_at is not None:
                    job.retrieval_completed_at = job.retrieval_completed_at or now
                elif selections:
                    raise AnswerProfileMismatch()
                job.updated_at = now
                await db.flush()
                await db.execute(delete(RagRelatedEvidence).where(
                    RagRelatedEvidence.job_id == job.id,
                ))
                for order, selection in enumerate(selections, start=1):
                    source = current_by_id[selection.source.chunk_id]
                    db.add(RagRelatedEvidence(
                        job_id=job.id, excerpt_order=order,
                        thread_id=job.thread_id, user_id=job.user_id,
                        subject_id=job.subject_id, chunk_id=source.chunk_id,
                        document_id=source.document_id,
                        content_revision_id=source.content_revision_id,
                        index_revision_id=source.index_revision_id,
                        source_kind=selection.source_kind,
                        start_offset=selection.start_offset,
                        end_offset=selection.end_offset,
                        manual_retry_number=job.manual_retry_count,
                        bundle_size=len(selections),
                        created_at=now, expires_at=question.expires_at,
                    ))
                # The guard permits INSERT only while this claim is running.
                # Flush all refs before the terminal state in the same DB tx.
                await db.flush()
                job.status = "completed"
                job.result_kind = (
                    "clarification_needed" if clarification_needed
                    else "related_knowledge" if selections else "no_match"
                )
                job.answer_message_id = None
                job.completed_at = now
                job.worker_id = None
                job.claim_token = None
                job.heartbeat_at = None
                job.lease_expires_at = None
                job.error_code = None
                job.error_message = None
                job.error_retryable = False
                job.updated_at = now
                thread.updated_at = now
                await db.flush()
        logger.info("knowledge_search_completed", extra={"job_id": job_id})

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
                if job.failed_stage is None:
                    job.failed_stage = await db.scalar(
                        select(RagAnswerStageAttempt.stage)
                        .where(RagAnswerStageAttempt.job_id == job_id)
                        .order_by(
                            RagAnswerStageAttempt.started_at.desc(),
                            RagAnswerStageAttempt.id.desc(),
                        )
                        .limit(1)
                    ) or "preflight"
                unfinished_remote = await db.scalar(
                    select(RagAnswerStageAttempt.id).where(
                        RagAnswerStageAttempt.job_id == job_id,
                        RagAnswerStageAttempt.manual_retry_number == job.manual_retry_count,
                        RagAnswerStageAttempt.stage.in_(("query_embedding", "answer", "source_judgment")),
                        RagAnswerStageAttempt.completed_at.is_(None),
                    ).limit(1)
                )
                if unfinished_remote is not None:
                    job.execution_uncertain = True
                    job.attempt_cost_unknown = True
                job.provider_error_category = (
                    job.provider_error_category or "rag_answer_cancelled"
                )
                await db.execute(delete(RagRelatedEvidence).where(
                    RagRelatedEvidence.job_id == job.id,
                ))
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
        self, job_id: UUID, token: str, code: str, message: str, *,
        retryable: bool, timed_out: bool = False,
    ) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                job = await db.scalar(select(RagAnswerJob).where(
                    RagAnswerJob.id == job_id,
                    RagAnswerJob.claim_token == token,
                ).with_for_update())
                if job is None or job.status != "running":
                    return
                if job.failed_stage is None:
                    job.failed_stage = await db.scalar(
                        select(RagAnswerStageAttempt.stage)
                        .where(RagAnswerStageAttempt.job_id == job_id)
                        .order_by(RagAnswerStageAttempt.started_at.desc(), RagAnswerStageAttempt.id.desc())
                        .limit(1)
                    ) or "preflight"
                unfinished_remote = await db.scalar(
                    select(RagAnswerStageAttempt.id).where(
                        RagAnswerStageAttempt.job_id == job_id,
                        RagAnswerStageAttempt.manual_retry_number == job.manual_retry_count,
                        RagAnswerStageAttempt.stage.in_(("query_embedding", "answer", "source_judgment")),
                        RagAnswerStageAttempt.completed_at.is_(None),
                    ).limit(1)
                )
                if unfinished_remote is not None:
                    job.execution_uncertain = True
                    job.attempt_cost_unknown = True
                if timed_out and job.failed_stage == "local_support":
                    job.provider_error_category = "local_support_unavailable"
                    job.failure_reason = "local_support_timeout"
                elif timed_out and job.failed_stage == "retrieval":
                    job.provider_error_category = "retrieval_failed"
                    job.failure_reason = "retrieval_timeout"
                elif timed_out and job.failed_stage in {"query_embedding", "answer", "source_judgment"}:
                    job.provider_error_category = (
                        "embedding_provider_timeout"
                        if job.failed_stage == "query_embedding" else "ai_provider_timeout"
                    )
                    job.failure_reason = "transport_timeout"
                    job.execution_uncertain = True
                    job.attempt_cost_unknown = True
                elif job.provider_error_category is None:
                    if code == "rag_answer_failed" and job.failed_stage == "local_support":
                        job.provider_error_category = "local_support_unavailable"
                        job.failure_reason = "local_support_timeout" if retryable else "local_support_unavailable"
                    elif code == "rag_answer_failed" and job.failed_stage == "retrieval":
                        job.provider_error_category = "retrieval_failed"
                        job.failure_reason = "retrieval_timeout" if retryable else "retrieval_failed"
                    else:
                        job.provider_error_category = (
                            "timeout" if code == "rag_answer_failed" and job.execution_uncertain
                            else "internal_failure" if code == "rag_answer_failed"
                            else code
                        )
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
        job.failed_stage = job.failed_stage or "preflight"
        job.provider_error_category = job.provider_error_category or code
        job.attempt_cost_unknown = job.attempt_cost_unknown or job.execution_uncertain
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
                        await db.execute(delete(RagRelatedEvidence).where(
                            RagRelatedEvidence.job_id == job.id,
                        ))
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
                        job.execution_uncertain = job.execution_uncertain or job.provider_call_started_at is not None
                        job.failed_stage = job.failed_stage or "worker_lease"
                        await self._fail_locked(
                            job,
                            "rag_answer_lease_expired",
                            "Answer worker lease expired.",
                            retryable=True,
                        )


__all__ = ["AnswerLeaseLost", "RagAnswerWorker"]
