"""Private Ask AI admission, authorization, history and lifecycle service."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
import re
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import bindparam, delete, func, select, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION, ASK_SOURCE_ONLY_READ_POLICIES, Settings, get_settings
from app.models.knowledge import (
    SubjectDocument,
    SubjectDocumentChunk,
    SubjectDocumentContentRevision,
    SubjectDocumentIndexRevision,
    embedding_space_hash,
)
from app.models.rag import (
    RagAnswerJob,
    RagAnswerQuotaEvent,
    RagMessage,
    RagMessageSource,
    RagRelatedEvidence,
    RagThread,
)
from app.models.subject import Subject
from app.models.user import User
from app.schemas.rag import (
    RagAnswerJobResponse,
    RagAnswerJobListResponse,
    RagHistoryResponse,
    RagMessageResponse,
    RagQuestionCreate,
    RagRelatedExcerptResponse,
    RagRelatedPageResponse,
    RagSourceResponse,
    RagThreadResponse,
)
from app.services.generation import hash_operation_key
from app.services.knowledge_retrieval import (
    SOURCE_NAVIGATION_RETRIEVAL_POLICY, KnowledgeRetriever, KnowledgeScopeUnavailable,
    read_eligible_source_batch,
)
from app.services.subject import SubjectService
from app.services.knowledge_lock import acquire_knowledge_write_lock
from app.observability import current_request_id
from app.ai.source_navigation import navigation_query_v4
from app.services.rag_question_context_v2 import (
    QuestionContextUnavailable, capture_question_context,
    persist_question_context, rehydrate_question_context,
)
from app.time_utils import utcnow


ANSWER_ADMISSION_LOCK = 7_314_159_266
ACTIVE_ANSWER_STATUSES = ("queued", "running")


def rag_http_error(status_code: int, code: str, message: str, **headers: str) -> HTTPException:
    error = HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
        headers=headers or None,
    )
    error.safe_detail = error.detail
    return error


def question_fingerprint(thread_id: UUID, data: RagQuestionCreate) -> str:
    payload = json.dumps(
        {
            "thread_id": str(thread_id),
            "question": data.question,
            "document_ids": sorted(str(value) for value in data.document_ids),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _attempt_estimate_microusd(settings: Settings) -> int:
    """Ceiling for both possible physical requests, rounded per stage."""

    embedding_cost = int((
        Decimal(settings.rag_embedding_max_input_tokens)
        * settings.rag_embedding_input_cost_per_million_usd
    ).to_integral_value(rounding=ROUND_CEILING))
    return embedding_cost + _judge_estimate_microusd(settings)


def _judge_estimate_microusd(settings: Settings) -> int:
    # Match the worker's immutable integer price snapshots and per-stage
    # ceiling, including fractional micro-USD operator prices.
    estimate = (
        Decimal(settings.rag_source_judge_max_input_tokens)
        * _judge_price_snapshot(settings.rag_source_judge_input_cost_per_million_usd)
        + Decimal(settings.rag_source_judge_max_output_tokens)
        * _judge_price_snapshot(settings.rag_source_judge_output_cost_per_million_usd)
    ) / Decimal(1_000_000)
    return int(estimate.to_integral_value(rounding=ROUND_CEILING))


def _judge_price_snapshot(price: Decimal) -> int:
    """Store nonzero micro-USD per million tokens without rounding down."""

    return int((price * Decimal(1_000_000)).to_integral_value(rounding=ROUND_CEILING))


def locate_page_reference(page_content: str, quote: str) -> tuple[int, int] | None:
    """Locate only an exact or whitespace-equivalent source span on its page."""

    if not quote or len(quote) > 480:
        return None
    start = page_content.find(quote)
    if start >= 0:
        return start, start + len(quote)
    words = quote.split()
    if not words:
        return None
    match = re.search(r"\s+".join(re.escape(word) for word in words), page_content)
    return (match.start(), match.end()) if match is not None else None


_RELATED_PAGES_SQL = text("""
    WITH authorized_subject AS (
        SELECT subject.id, subject.corpus_revision, subject.active_embedding_space_hash
        FROM subjects AS subject
        JOIN users AS principal ON principal.id = :principal_id
        WHERE subject.id = :subject_id
          AND subject.corpus_revision = :corpus_revision
          AND subject.active_embedding_space_hash = :embedding_space_hash
          AND ((principal.role = 'INSTRUCTOR' AND subject.instructor_id = principal.id)
               OR (principal.role = 'STUDENT' AND EXISTS (
                   SELECT 1 FROM enrollments AS enrollment
                   WHERE enrollment.student_id = principal.id
                     AND enrollment.subject_id = subject.id)))
    )
    SELECT eligible.id AS chunk_id, page.content
    FROM eligible_subject_knowledge_chunks AS eligible
    JOIN authorized_subject AS scope
      ON scope.id = eligible.subject_id
     AND scope.corpus_revision = eligible.corpus_revision
     AND scope.active_embedding_space_hash = eligible.embedding_space_hash
    JOIN subject_document_pages AS page
      ON page.content_revision_id = eligible.content_revision_id
     AND page.document_id = eligible.document_id
     AND page.subject_id = eligible.subject_id
     AND page.uploader_id = eligible.uploader_id
     AND page.page_number = eligible.page_number
    WHERE eligible.id = ANY(:chunk_ids)
      AND eligible.subject_id = :subject_id
      AND eligible.corpus_revision = :corpus_revision
      AND eligible.embedding_space_hash = :embedding_space_hash
""").bindparams(
    bindparam("principal_id", type_=PGUUID(as_uuid=True)),
    bindparam("subject_id", type_=PGUUID(as_uuid=True)),
    bindparam("chunk_ids", type_=ARRAY(PGUUID(as_uuid=True))),
)


async def _read_related_pages(
    db: AsyncSession, *, principal_id: UUID, subject_id: UUID,
    corpus_revision: int, embedding_space_hash: str, chunk_ids: list[UUID],
) -> dict[UUID, str]:
    """Read current pages only for authorized eligible anchors and job scope."""

    if not chunk_ids:
        return {}
    result = await db.execute(_RELATED_PAGES_SQL, {
        "principal_id": principal_id, "subject_id": subject_id,
        "corpus_revision": corpus_revision,
        "embedding_space_hash": embedding_space_hash,
        "chunk_ids": chunk_ids,
    })
    return {row["chunk_id"]: row["content"] for row in result.mappings().all()}


class RagAnswerService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def _lock_admission(self, db: AsyncSession) -> None:
        if db.get_bind().dialect.name == "postgresql":
            await db.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"),
                {"lock_id": ANSWER_ADMISSION_LOCK},
            )

    @staticmethod
    def _day_start() -> datetime:
        now = utcnow()
        return datetime.combine(now.date(), time.min, tzinfo=timezone.utc)

    async def _owned_thread(
        self,
        db: AsyncSession,
        *,
        subject_id: UUID,
        thread_id: UUID,
        user: User,
        for_update: bool = False,
    ) -> RagThread:
        await SubjectService.check_subject_access(db, subject_id, user)
        query = select(RagThread).where(
            RagThread.id == thread_id,
            RagThread.user_id == user.id,
            RagThread.subject_id == subject_id,
        )
        if for_update:
            query = query.with_for_update()
        thread = await db.scalar(query)
        if thread is None:
            raise rag_http_error(status.HTTP_404_NOT_FOUND, "rag_thread_not_found", "Ask AI thread not found.")
        return thread

    async def create_thread(self, db: AsyncSession, *, subject_id: UUID, user: User) -> RagThread:
        await SubjectService.check_subject_access(db, subject_id, user)
        if not self.settings.rag_enabled:
            raise rag_http_error(status.HTTP_503_SERVICE_UNAVAILABLE, "rag_disabled", "Ask AI is not enabled.")
        if not self.settings.rag_source_only_available:
            raise rag_http_error(status.HTTP_503_SERVICE_UNAVAILABLE, "rag_ask_disabled", "Ask AI is temporarily unavailable.")
        await self._lock_admission(db)
        user_count = int(await db.scalar(select(func.count(RagThread.id)).where(
            RagThread.user_id == user.id,
        )) or 0)
        deployment_count = int(await db.scalar(select(func.count(RagThread.id))) or 0)
        if user_count >= self.settings.rag_answer_max_threads_per_user:
            raise rag_http_error(status.HTTP_429_TOO_MANY_REQUESTS, "rag_thread_limit", "Your Ask AI thread limit has been reached.")
        if deployment_count >= self.settings.rag_answer_max_threads_deployment:
            raise rag_http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "rag_deployment_thread_limit",
                "Ask AI conversation storage is temporarily at capacity.",
                **{"Retry-After": "60"},
            )
        now = utcnow()
        thread = RagThread(user_id=user.id, subject_id=subject_id, created_at=now, updated_at=now)
        db.add(thread)
        await db.flush()
        return thread

    async def list_threads(
        self, db: AsyncSession, *, subject_id: UUID, user: User, limit: int
    ) -> list[RagThread]:
        await SubjectService.check_subject_access(db, subject_id, user)
        return list((await db.scalars(select(RagThread).where(
            RagThread.user_id == user.id,
            RagThread.subject_id == subject_id,
        ).order_by(RagThread.updated_at.desc(), RagThread.id).limit(limit))).all())

    async def delete_thread(
        self, db: AsyncSession, *, subject_id: UUID, thread_id: UUID, user: User
    ) -> None:
        await self._lock_admission(db)
        thread = await self._owned_thread(
            db, subject_id=subject_id, thread_id=thread_id, user=user, for_update=True
        )
        await db.delete(thread)
        await db.flush()

    async def _check_job_capacity(self, db: AsyncSession, user_id: UUID) -> None:
        if not self.settings.rag_source_only_available:
            raise rag_http_error(status.HTTP_503_SERVICE_UNAVAILABLE, "rag_answer_unavailable", "Ask AI is temporarily unavailable.")
        user_active = int(await db.scalar(select(func.count(RagAnswerJob.id)).where(
            RagAnswerJob.user_id == user_id,
            RagAnswerJob.status.in_(ACTIVE_ANSWER_STATUSES),
        )) or 0)
        deployment_active = int(await db.scalar(select(func.count(RagAnswerJob.id)).where(
            RagAnswerJob.status.in_(ACTIVE_ANSWER_STATUSES),
        )) or 0)
        queued = int(await db.scalar(select(func.count(RagAnswerJob.id)).where(
            RagAnswerJob.status == "queued",
        )) or 0)
        if user_active >= self.settings.rag_answer_max_active_jobs_per_user:
            raise rag_http_error(status.HTTP_429_TOO_MANY_REQUESTS, "rag_user_active_limit", "Finish or cancel your active Ask AI job first.", **{"Retry-After": "30"})
        if deployment_active >= self.settings.rag_answer_max_active_jobs_deployment:
            raise rag_http_error(status.HTTP_503_SERVICE_UNAVAILABLE, "rag_deployment_active_limit", "Ask AI is temporarily at capacity.", **{"Retry-After": "30"})
        if queued >= self.settings.rag_answer_max_queued_jobs_deployment:
            raise rag_http_error(status.HTTP_503_SERVICE_UNAVAILABLE, "rag_answer_queue_full", "The Ask AI queue is full.", **{"Retry-After": "30"})
        start = self._day_start()
        user_daily = int(await db.scalar(select(func.coalesce(func.sum(RagAnswerQuotaEvent.job_units), 0)).where(
            RagAnswerQuotaEvent.user_id == user_id,
            RagAnswerQuotaEvent.created_at >= start,
        )) or 0)
        deployment_daily = int(await db.scalar(select(func.coalesce(func.sum(RagAnswerQuotaEvent.job_units), 0)).where(
            RagAnswerQuotaEvent.created_at >= start,
        )) or 0)
        if user_daily >= self.settings.rag_answer_daily_jobs_per_user:
            raise rag_http_error(status.HTTP_429_TOO_MANY_REQUESTS, "rag_user_daily_limit", "Your daily Ask AI limit has been reached.")
        if deployment_daily >= self.settings.rag_answer_daily_jobs_deployment:
            raise rag_http_error(status.HTTP_503_SERVICE_UNAVAILABLE, "rag_deployment_daily_limit", "The deployment daily Ask AI limit has been reached.")

    async def _check_message_capacity(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        thread_id: UUID,
        new_messages: int,
    ) -> None:
        """Reserve future assistant rows only for historical active answer jobs.

        The admission advisory lock serializes these counts with enqueue/retry.
        Source-only jobs never create an assistant row. Historical active jobs
        still reserve one until they are fenced at cutover.
        """

        thread_messages = int(await db.scalar(select(func.count(RagMessage.id)).where(
            RagMessage.thread_id == thread_id,
        )) or 0)
        user_messages = int(await db.scalar(select(func.count(RagMessage.id)).where(
            RagMessage.user_id == user_id,
        )) or 0)
        deployment_messages = int(await db.scalar(select(func.count(RagMessage.id))) or 0)
        thread_reservations = int(await db.scalar(select(func.count(RagAnswerJob.id)).where(
            RagAnswerJob.thread_id == thread_id,
            RagAnswerJob.status.in_(ACTIVE_ANSWER_STATUSES),
            RagAnswerJob.answer_policy_version.not_in(ASK_SOURCE_ONLY_READ_POLICIES),
        )) or 0)
        user_reservations = int(await db.scalar(select(func.count(RagAnswerJob.id)).where(
            RagAnswerJob.user_id == user_id,
            RagAnswerJob.status.in_(ACTIVE_ANSWER_STATUSES),
            RagAnswerJob.answer_policy_version.not_in(ASK_SOURCE_ONLY_READ_POLICIES),
        )) or 0)
        deployment_reservations = int(await db.scalar(select(func.count(RagAnswerJob.id)).where(
            RagAnswerJob.status.in_(ACTIVE_ANSWER_STATUSES),
            RagAnswerJob.answer_policy_version.not_in(ASK_SOURCE_ONLY_READ_POLICIES),
        )) or 0)
        if (
            thread_messages + thread_reservations + new_messages
            > self.settings.rag_answer_max_messages_per_thread
        ):
            raise rag_http_error(
                status.HTTP_409_CONFLICT,
                "rag_thread_message_limit",
                "This Ask AI thread has reached its message limit.",
            )
        if (
            user_messages + user_reservations + new_messages
            > self.settings.rag_answer_max_messages_per_user
        ):
            raise rag_http_error(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "rag_message_storage_limit",
                "Your Ask AI message storage limit has been reached.",
            )
        if (
            deployment_messages + deployment_reservations + new_messages
            > self.settings.rag_answer_max_messages_deployment
        ):
            raise rag_http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "rag_deployment_message_storage_limit",
                "Ask AI message storage is temporarily at capacity.",
                **{"Retry-After": "60"},
            )

    async def enqueue(
        self,
        db: AsyncSession,
        *,
        subject_id: UUID,
        thread_id: UUID,
        user: User,
        data: RagQuestionCreate,
        idempotency_key: str,
    ) -> RagAnswerJob:
        key_hash = hash_operation_key(idempotency_key)
        fingerprint = question_fingerprint(thread_id, data)
        if len(data.question) > self.settings.rag_answer_max_question_chars:
            raise rag_http_error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "rag_question_too_long",
                "The Ask AI question exceeds the configured length limit.",
            )
        await SubjectService.check_subject_access(db, subject_id, user)
        if not self.settings.rag_source_only_available:
            raise rag_http_error(status.HTTP_503_SERVICE_UNAVAILABLE, "rag_ask_disabled", "Ask AI is temporarily unavailable.")
        await self._lock_admission(db)
        existing = await db.scalar(select(RagAnswerJob).where(
            RagAnswerJob.user_id == user.id,
            RagAnswerJob.operation_key_hash == key_hash,
        ))
        if existing is not None:
            if existing.thread_id != thread_id or existing.subject_id != subject_id or existing.request_fingerprint != fingerprint:
                raise rag_http_error(status.HTTP_409_CONFLICT, "idempotency_key_reused", "This Idempotency-Key was already used for another operation.")
            return existing

        thread = await self._owned_thread(
            db, subject_id=subject_id, thread_id=thread_id, user=user, for_update=True
        )
        await self._check_job_capacity(db, user.id)
        await self._check_message_capacity(
            db,
            user_id=user.id,
            thread_id=thread.id,
            new_messages=1,
        )

        try:
            retriever = await KnowledgeRetriever.authorize(
                db,
                principal=user,
                subject_id=subject_id,
                query=data.question,
                document_ids=data.document_ids,
                limit=SOURCE_NAVIGATION_RETRIEVAL_POLICY.max_results,
                policy=SOURCE_NAVIGATION_RETRIEVAL_POLICY,
            )
        except KnowledgeScopeUnavailable:
            raise rag_http_error(status.HTTP_409_CONFLICT, "rag_knowledge_unavailable", "Current course materials are unavailable for this request.") from None

        configured_space = embedding_space_hash(self.settings.rag_embedding_space_identity)
        if retriever.scope.embedding_space_hash != configured_space:
            raise rag_http_error(
                status.HTTP_409_CONFLICT,
                "rag_embedding_space_mismatch",
                "Current course materials are not indexed for the active Ask AI profile.",
            )

        now = utcnow()
        auth_session_id = getattr(user, "_auth_session_id", None)
        if not isinstance(auth_session_id, UUID):
            raise rag_http_error(status.HTTP_401_UNAUTHORIZED, "authentication_required", "Could not validate credentials")
        expires_at = now + timedelta(days=self.settings.rag_chat_retention_days)
        question = RagMessage(
            id=uuid4(),
            thread_id=thread.id,
            user_id=user.id,
            subject_id=subject_id,
            role="user",
            outcome=None,
            content=data.question,
            source_count=0,
            created_at=now,
            expires_at=expires_at,
        )
        try:
            captured_context = await capture_question_context(
                db, current=question, thread=thread,
                corpus_revision=retriever.scope.corpus_revision,
                embedding_space_hash=configured_space, captured_at=now,
                raw_navigation_query=navigation_query_v4(data.question, ()),
            )
        except QuestionContextUnavailable:
            raise rag_http_error(
                status.HTTP_409_CONFLICT, "rag_question_context_changed",
                "The question context changed or expired. Start a new search.",
            ) from None
        db.add(question)
        await db.flush()
        space_hash = configured_space
        embedding_input = self.settings.rag_embedding_max_input_tokens
        estimated_input = embedding_input + self.settings.rag_source_judge_max_input_tokens
        estimated_output = self.settings.rag_source_judge_max_output_tokens
        estimated_cost = _attempt_estimate_microusd(self.settings)
        embedding_cost = int((Decimal(embedding_input) *
                              self.settings.rag_embedding_input_cost_per_million_usd
                              ).to_integral_value(rounding=ROUND_CEILING))
        if embedding_cost > int(self.settings.rag_embedding_max_estimated_cost_usd * Decimal(1_000_000)):
            raise rag_http_error(status.HTTP_409_CONFLICT, "rag_embedding_cost_limit", "The Ask AI request exceeds the configured cost limit.")
        if _judge_estimate_microusd(self.settings) > int(
            self.settings.rag_source_judge_max_estimated_cost_usd * Decimal(1_000_000)
        ):
            raise rag_http_error(status.HTTP_409_CONFLICT, "rag_source_judge_cost_limit", "The Ask AI request exceeds the configured cost limit.")
        job = RagAnswerJob(
            id=uuid4(),
            thread_id=thread.id,
            question_message_id=question.id,
            auth_session_id=auth_session_id,
            user_id=user.id,
            subject_id=subject_id,
            request_id=current_request_id(),
            status="queued",
            operation_key_hash=key_hash,
            request_fingerprint=fingerprint,
            document_ids=[str(value) for value in sorted(data.document_ids, key=str)],
            corpus_revision=retriever.scope.corpus_revision,
            retrieval_policy=SOURCE_NAVIGATION_RETRIEVAL_POLICY.policy_id,
            embedding_space_hash=space_hash,
            embedding_provider=self.settings.rag_embedding_provider,
            embedding_base_url=self.settings.rag_embedding_endpoint_identity,
            embedding_model=self.settings.rag_embedding_model,
            source_judge_provider=self.settings.rag_source_judge_provider,
            source_judge_base_url=self.settings.rag_source_judge_endpoint_identity,
            source_judge_model=self.settings.rag_source_judge_model,
            source_judge_contract_version=self.settings.rag_source_judge_contract_version,
            source_judge_input_price_microusd_per_million=_judge_price_snapshot(
                self.settings.rag_source_judge_input_cost_per_million_usd),
            source_judge_output_price_microusd_per_million=_judge_price_snapshot(
                self.settings.rag_source_judge_output_cost_per_million_usd),
            source_judge_max_input_tokens=self.settings.rag_source_judge_max_input_tokens,
            source_judge_max_output_tokens=self.settings.rag_source_judge_max_output_tokens,
            source_judge_thinking_level=self.settings.rag_source_judge_thinking_level,
            source_judge_timeout_seconds=self.settings.rag_source_judge_provider_timeout_seconds,
            ai_provider=None,
            ai_base_url=None,
            ai_model=None,
            ai_catalog_version=None,
            ai_schema_policy_version=None,
            answer_policy_version=ASK_REQUIRED_RELEASE_POLICY_VERSION,
            support_policy_version=None,
            max_attempts=self.settings.rag_answer_max_attempts,
            available_at=now,
            deadline_at=now + timedelta(seconds=self.settings.rag_answer_job_timeout_seconds),
            estimated_input_tokens=estimated_input,
            estimated_output_tokens=estimated_output,
            estimated_cost_microusd=estimated_cost,
            created_at=now,
            updated_at=now,
        )
        db.add(job)
        await persist_question_context(db, job=job, captured=captured_context)
        # Flush the parent before the metadata-only binding's scoped FK. Both
        # remain in the caller-owned transaction; its deferred admission guard
        # requires the binding at commit.
        await db.flush([job])
        await db.flush()
        db.add(RagAnswerQuotaEvent(
            user_id=user.id,
            job_id=job.id,
            operation_key_hash=key_hash,
            job_units=1,
            created_at=now,
        ))
        thread.updated_at = now
        await db.flush()
        return job

    async def owned_job(
        self,
        db: AsyncSession,
        *,
        subject_id: UUID,
        thread_id: UUID,
        job_id: UUID,
        user: User,
        for_update: bool = False,
    ) -> RagAnswerJob:
        await self._owned_thread(db, subject_id=subject_id, thread_id=thread_id, user=user)
        query = select(RagAnswerJob).where(
            RagAnswerJob.id == job_id,
            RagAnswerJob.thread_id == thread_id,
            RagAnswerJob.user_id == user.id,
            RagAnswerJob.subject_id == subject_id,
        )
        if for_update:
            query = query.with_for_update()
        job = await db.scalar(query)
        if job is None:
            raise rag_http_error(status.HTTP_404_NOT_FOUND, "rag_answer_job_not_found", "Ask AI job not found.")
        return job

    async def list_jobs(
        self,
        db: AsyncSession,
        *,
        subject_id: UUID,
        thread_id: UUID,
        user: User,
        limit: int,
    ) -> RagAnswerJobListResponse:
        await self._owned_thread(
            db, subject_id=subject_id, thread_id=thread_id, user=user
        )
        jobs = list(
            (
                await db.scalars(
                    select(RagAnswerJob)
                    .where(
                        RagAnswerJob.thread_id == thread_id,
                        RagAnswerJob.user_id == user.id,
                        RagAnswerJob.subject_id == subject_id,
                    )
                    .order_by(RagAnswerJob.created_at.desc(), RagAnswerJob.id.desc())
                    .limit(limit)
                )
            ).all()
        )
        related = await self._related_excerpts_for_jobs(
            db, jobs=jobs, user=user, subject_id=subject_id,
        )
        return RagAnswerJobListResponse(
            jobs=[self.job_response(job, related_excerpts=related.get(job.id, [])) for job in jobs]
        )

    async def job_response_with_related(
        self,
        db: AsyncSession,
        *,
        job: RagAnswerJob,
        user: User,
    ) -> RagAnswerJobResponse:
        related = await self._related_excerpts_for_jobs(
            db, jobs=[job], user=user, subject_id=job.subject_id,
        )
        return self.job_response(job, related_excerpts=related.get(job.id, []))

    async def related_page(
        self, db: AsyncSession, *, subject_id: UUID, thread_id: UUID,
        job_id: UUID, excerpt_order: int, user: User,
    ) -> RagRelatedPageResponse:
        """Open one current canonical page after reauthorizing the whole bundle."""

        await acquire_knowledge_write_lock(db)
        job = await self.owned_job(
            db, subject_id=subject_id, thread_id=thread_id, job_id=job_id, user=user,
        )
        if (
            job.status != "completed" or job.result_kind != "related_knowledge"
            or job.answer_policy_version not in ASK_SOURCE_ONLY_READ_POLICIES
        ):
            raise rag_http_error(status.HTTP_404_NOT_FOUND, "rag_related_page_unavailable", "Current Knowledge page is unavailable.")
        bundles = await self._related_excerpts_for_jobs(
            db, jobs=[job], user=user, subject_id=subject_id,
        )
        excerpts = bundles.get(job.id)
        if excerpts is None or not 1 <= excerpt_order <= len(excerpts):
            raise rag_http_error(status.HTTP_404_NOT_FOUND, "rag_related_page_unavailable", "Current Knowledge page is unavailable.")
        excerpt = excerpts[excerpt_order - 1]
        row = await db.get(RagRelatedEvidence, (job.id, excerpt_order))
        if row is None:
            raise rag_http_error(status.HTTP_404_NOT_FOUND, "rag_related_page_unavailable", "Current Knowledge page is unavailable.")
        page_content = (await _read_related_pages(
            db, principal_id=user.id, subject_id=subject_id,
            corpus_revision=job.corpus_revision,
            embedding_space_hash=job.embedding_space_hash,
            chunk_ids=[row.chunk_id],
        )).get(row.chunk_id)
        if page_content is None:
            raise rag_http_error(status.HTTP_404_NOT_FOUND, "rag_related_page_unavailable", "Current Knowledge page is unavailable.")
        if row.source_kind == "canonical_page":
            span = (row.start_offset, row.end_offset)
            if page_content[span[0]:span[1]] != excerpt.source_quote:
                raise rag_http_error(status.HTTP_404_NOT_FOUND, "rag_related_page_unavailable", "Current Knowledge page is unavailable.")
        elif row.source_kind == "chunk":
            span = locate_page_reference(page_content, excerpt.source_quote)
        else:
            raise rag_http_error(status.HTTP_404_NOT_FOUND, "rag_related_page_unavailable", "Current Knowledge page is unavailable.")
        return RagRelatedPageResponse(
            document_title=excerpt.document_title,
            page_number=excerpt.page_number,
            section=excerpt.section,
            source_quote=excerpt.source_quote,
            page_content=page_content,
            reference_start=span[0] if span is not None else None,
            reference_end=span[1] if span is not None else None,
        )

    async def _related_excerpts_for_jobs(
        self,
        db: AsyncSession,
        *,
        jobs: list[RagAnswerJob],
        user: User,
        subject_id: UUID,
    ) -> dict[UUID, list[RagRelatedExcerptResponse]]:
        """Batch-read current exact source slices; any drift hides the bundle."""

        now = utcnow()
        completed_ids = [
            job.answer_message_id for job in jobs
            if job.status == "completed" and job.answer_message_id is not None
        ]
        abstained_ids: set[UUID] = set()
        if completed_ids:
            abstained_ids = set((await db.scalars(select(RagMessage.id).where(
                RagMessage.id.in_(completed_ids),
                RagMessage.user_id == user.id,
                RagMessage.subject_id == subject_id,
                RagMessage.role == "assistant",
                RagMessage.outcome == "abstained",
                RagMessage.expires_at > now,
            ))).all())
        eligible_jobs = {
            job.id: job for job in jobs
            if job.user_id == user.id and job.subject_id == subject_id
            and (
                (job.status == "completed" and getattr(job, "answer_policy_version", None) in ASK_SOURCE_ONLY_READ_POLICIES
                 and getattr(job, "result_kind", None) == "related_knowledge" and job.answer_message_id is None)
                or
                (job.status == "failed" and job.error_code == "rag_answer_failed")
                or (job.status == "completed" and job.answer_message_id in abstained_ids)
            )
        }
        if not eligible_jobs:
            return {}
        rows = list((await db.scalars(select(RagRelatedEvidence).where(
            RagRelatedEvidence.job_id.in_(eligible_jobs),
            RagRelatedEvidence.user_id == user.id,
            RagRelatedEvidence.subject_id == subject_id,
            RagRelatedEvidence.expires_at > now,
        ).order_by(
            RagRelatedEvidence.job_id, RagRelatedEvidence.excerpt_order,
        ))).all())
        if not rows:
            return {}
        chunk_ids = list({row.chunk_id for row in rows})
        current_sources = {}
        for start in range(0, len(chunk_ids), 100):
            current_sources.update(await read_eligible_source_batch(
                db, principal_id=user.id, subject_id=subject_id,
                chunk_ids=chunk_ids[start:start + 100],
            ))
        by_job: dict[UUID, list[RagRelatedEvidence]] = {}
        for row in rows:
            by_job.setdefault(row.job_id, []).append(row)
        valid_jobs: dict[UUID, list[RagRelatedEvidence]] = {}
        page_groups: dict[tuple[int, str], set[UUID]] = {}
        for job_id, refs in by_job.items():
            job = eligible_jobs[job_id]
            size = refs[0].bundle_size
            if (
                size not in (1, 2, 3) or len(refs) != size
                or [row.excerpt_order for row in refs] != list(range(1, size + 1))
                or any(row.bundle_size != size for row in refs)
                or any(row.manual_retry_number != job.manual_retry_count for row in refs)
            ):
                continue
            valid_jobs[job_id] = refs
            page_groups.setdefault(
                (job.corpus_revision, job.embedding_space_hash), set(),
            ).update(
                row.chunk_id for row in refs
                if row.source_kind == "canonical_page" and row.chunk_id in current_sources
            )
        current_pages: dict[tuple[int, str], dict[UUID, str]] = {}
        for (corpus_revision, space_hash), ids in page_groups.items():
            pages: dict[UUID, str] = {}
            ordered_ids = sorted(ids, key=str)
            for start in range(0, len(ordered_ids), 100):
                pages.update(await _read_related_pages(
                    db, principal_id=user.id, subject_id=subject_id,
                    corpus_revision=corpus_revision,
                    embedding_space_hash=space_hash,
                    chunk_ids=ordered_ids[start:start + 100],
                ))
            current_pages[(corpus_revision, space_hash)] = pages
        response: dict[UUID, list[RagRelatedExcerptResponse]] = {}
        for job_id, refs in valid_jobs.items():
            job = eligible_jobs[job_id]
            size = refs[0].bundle_size
            job_pages = current_pages.get((job.corpus_revision, job.embedding_space_hash), {})
            document_scope = set(job.document_ids)
            excerpts: list[RagRelatedExcerptResponse] = []
            for row in refs:
                source = current_sources.get(row.chunk_id)
                source_kind = row.source_kind
                page_content = job_pages.get(row.chunk_id)
                source_content = (
                    page_content if source_kind == "canonical_page"
                    else source.content if source_kind == "chunk" and source is not None
                    else None
                )
                if (
                    source is None
                    or (source_kind == "canonical_page" and page_content is None)
                    or source_content is None
                    or row.expires_at <= now
                    or row.thread_id != job.thread_id
                    or row.subject_id != job.subject_id
                    or row.user_id != job.user_id
                    or source.document_id != row.document_id
                    or source.content_revision_id != row.content_revision_id
                    or source.index_revision_id != row.index_revision_id
                    or source.corpus_revision != job.corpus_revision
                    or source.embedding_space_hash != job.embedding_space_hash
                    or document_scope and str(source.document_id) not in document_scope
                    or not 0 <= row.start_offset < row.end_offset <= len(source_content)
                    or row.end_offset - row.start_offset > 480
                ):
                    excerpts = []
                    break
                quote = source_content[row.start_offset:row.end_offset]
                if not quote.strip():
                    excerpts = []
                    break
                excerpts.append(RagRelatedExcerptResponse(
                    excerpt_order=row.excerpt_order,
                    document_title=source.document_title,
                    page_number=source.page_number,
                    section=source.section,
                    source_quote=quote,
                ))
            if len(excerpts) == size:
                response[job_id] = excerpts
        return response

    async def cancel(
        self, db: AsyncSession, *, subject_id: UUID, thread_id: UUID, job_id: UUID, user: User
    ) -> RagAnswerJob:
        await self._lock_admission(db)
        job = await self.owned_job(
            db, subject_id=subject_id, thread_id=thread_id, job_id=job_id, user=user, for_update=True
        )
        now = utcnow()
        if job.status == "queued":
            await db.execute(delete(RagRelatedEvidence).where(
                RagRelatedEvidence.job_id == job.id,
            ))
            job.status = "cancelled"
            job.cancellation_requested_at = now
            job.completed_at = now
            job.error_code = "rag_answer_cancelled"
            job.error_message = "Answer generation was cancelled."
            job.error_retryable = False
        elif job.status == "running" and job.cancellation_requested_at is None:
            job.cancellation_requested_at = now
        job.updated_at = now
        await db.flush()
        return job

    async def retry(
        self,
        db: AsyncSession,
        *,
        subject_id: UUID,
        thread_id: UUID,
        job_id: UUID,
        user: User,
        idempotency_key: str,
    ) -> RagAnswerJob:
        retry_key_hash = hash_operation_key(idempotency_key)
        await SubjectService.check_subject_access(db, subject_id, user)
        if not self.settings.rag_source_only_available:
            raise rag_http_error(status.HTTP_503_SERVICE_UNAVAILABLE, "rag_ask_disabled", "Ask AI is temporarily unavailable.")
        await self._lock_admission(db)
        existing = await db.scalar(select(RagAnswerQuotaEvent).where(
            RagAnswerQuotaEvent.user_id == user.id,
            RagAnswerQuotaEvent.operation_key_hash == retry_key_hash,
        ))
        if existing is not None:
            if existing.job_id != job_id:
                raise rag_http_error(status.HTTP_409_CONFLICT, "idempotency_key_reused", "This Idempotency-Key was already used for another operation.")
            return await self.owned_job(
                db, subject_id=subject_id, thread_id=thread_id, job_id=job_id, user=user
            )
        job = await self.owned_job(
            db, subject_id=subject_id, thread_id=thread_id, job_id=job_id, user=user, for_update=True
        )
        if job.status != "failed" or not job.error_retryable or job.answer_policy_version != ASK_REQUIRED_RELEASE_POLICY_VERSION:
            raise rag_http_error(status.HTTP_409_CONFLICT, "rag_answer_not_retryable", "This Ask AI job can no longer be retried.")
        if job.manual_retry_count >= self.settings.rag_answer_max_manual_retries:
            raise rag_http_error(status.HTTP_409_CONFLICT, "rag_answer_retry_limit", "This Ask AI job reached its manual retry limit.")
        auth_session_id = getattr(user, "_auth_session_id", None)
        if not isinstance(auth_session_id, UUID):
            raise rag_http_error(status.HTTP_401_UNAUTHORIZED, "authentication_required", "Could not validate credentials")
        subject = await db.get(Subject, subject_id)
        configured_space = embedding_space_hash(self.settings.rag_embedding_space_identity)
        current_space = subject.active_embedding_space_hash if subject else None
        if (
            subject is None
            or subject.corpus_revision != job.corpus_revision
            or current_space != job.embedding_space_hash
            or configured_space != job.embedding_space_hash
            or self.settings.rag_embedding_provider != job.embedding_provider
            or self.settings.rag_embedding_endpoint_identity != job.embedding_base_url
            or self.settings.rag_embedding_model != job.embedding_model
            or job.answer_policy_version != ASK_REQUIRED_RELEASE_POLICY_VERSION
            or job.retrieval_policy != SOURCE_NAVIGATION_RETRIEVAL_POLICY.policy_id
            or self.settings.rag_source_judge_provider != job.source_judge_provider
            or self.settings.rag_source_judge_endpoint_identity != job.source_judge_base_url
            or self.settings.rag_source_judge_model != job.source_judge_model
            or self.settings.rag_source_judge_contract_version != job.source_judge_contract_version
            or _judge_price_snapshot(self.settings.rag_source_judge_input_cost_per_million_usd)
            != job.source_judge_input_price_microusd_per_million
            or _judge_price_snapshot(self.settings.rag_source_judge_output_cost_per_million_usd)
            != job.source_judge_output_price_microusd_per_million
            or self.settings.rag_source_judge_max_input_tokens != job.source_judge_max_input_tokens
            or self.settings.rag_source_judge_max_output_tokens != job.source_judge_max_output_tokens
            or self.settings.rag_source_judge_thinking_level != job.source_judge_thinking_level
            or self.settings.rag_source_judge_provider_timeout_seconds != job.source_judge_timeout_seconds
        ):
            raise rag_http_error(status.HTTP_409_CONFLICT, "rag_answer_snapshot_changed", "Ask AI configuration or course materials changed; submit a new question.")
        await self._check_job_capacity(db, user.id)
        await self._check_message_capacity(
            db,
            user_id=user.id,
            thread_id=thread_id,
            new_messages=0,
        )
        now = utcnow()
        try:
            await rehydrate_question_context(db, job=job, checked_at=now)
        except QuestionContextUnavailable:
            raise rag_http_error(
                status.HTTP_409_CONFLICT, "rag_question_context_changed",
                "The question context changed or expired. Start a new search.",
            ) from None
        db.add(RagAnswerQuotaEvent(
            user_id=user.id,
            job_id=job.id,
            operation_key_hash=retry_key_hash,
            job_units=1,
            created_at=now,
        ))
        await db.execute(delete(RagRelatedEvidence).where(
            RagRelatedEvidence.job_id == job.id,
        ))
        job.status = "queued"
        job.auth_session_id = auth_session_id
        job.attempt_count = 0
        job.manual_retry_count += 1
        job.available_at = now
        job.deadline_at = now + timedelta(seconds=self.settings.rag_answer_job_timeout_seconds)
        job.worker_id = None
        job.claim_token = None
        job.heartbeat_at = None
        job.lease_expires_at = None
        job.cancellation_requested_at = None
        job.provider_call_started_at = None
        job.retrieval_completed_at = None
        job.attempt_cost_microusd = 0
        job.attempt_cost_unknown = False
        job.execution_uncertain = False
        job.completed_at = None
        job.error_code = None
        job.error_message = None
        job.error_retryable = False
        job.failed_stage = None
        job.provider_error_category = None
        job.failure_reason = None
        job.updated_at = now
        await db.flush()
        return job

    async def _eligible_source_rows(
        self, db: AsyncSession, message_ids: list[UUID]
    ) -> dict[UUID, list[RagSourceResponse]]:
        if not message_ids:
            return {}
        rows = (await db.execute(
            select(
                RagMessageSource.message_id,
                RagMessageSource.citation_order,
                RagMessageSource.chunk_id,
                RagMessageSource.document_id,
                SubjectDocument.title,
                RagMessageSource.content_revision_id,
                RagMessageSource.index_revision_id,
                SubjectDocumentChunk.page_number,
                SubjectDocumentChunk.section,
                RagMessageSource.claim_text,
                RagMessageSource.source_quote,
            )
            .join(RagMessage, RagMessage.id == RagMessageSource.message_id)
            .join(SubjectDocumentChunk, SubjectDocumentChunk.id == RagMessageSource.chunk_id)
            .join(SubjectDocument, SubjectDocument.id == RagMessageSource.document_id)
            .join(SubjectDocumentContentRevision, SubjectDocumentContentRevision.id == RagMessageSource.content_revision_id)
            .join(SubjectDocumentIndexRevision, SubjectDocumentIndexRevision.id == RagMessageSource.index_revision_id)
            .join(Subject, Subject.id == RagMessage.subject_id)
            .where(
                RagMessageSource.message_id.in_(message_ids),
                SubjectDocumentContentRevision.is_active.is_(True),
                SubjectDocumentContentRevision.status == "ready",
                SubjectDocumentContentRevision.published_at.is_not(None),
                SubjectDocumentContentRevision.reviewed_at.is_not(None),
                SubjectDocumentContentRevision.reviewed_by_id == SubjectDocument.uploader_id,
                SubjectDocumentIndexRevision.is_active.is_(True),
                SubjectDocumentIndexRevision.status == "ready",
                SubjectDocumentChunk.embedding.is_not(None),
                SubjectDocumentChunk.embedding_space_hash == Subject.active_embedding_space_hash,
                SubjectDocumentChunk.embedding_space_hash == RagMessage.embedding_space_hash,
                Subject.corpus_revision == RagMessage.corpus_revision,
            )
            .order_by(RagMessageSource.message_id, RagMessageSource.citation_order)
        )).all()
        result: dict[UUID, list[RagSourceResponse]] = {}
        for row in rows:
            result.setdefault(row[0], []).append(RagSourceResponse(
                citation_order=row[1], chunk_id=row[2], document_id=row[3], document_title=row[4],
                content_revision_id=row[5], index_revision_id=row[6], page_number=row[7],
                section=row[8], claim_text=row[9], source_quote=row[10],
            ))
        return result

    async def history(
        self,
        db: AsyncSession,
        *,
        subject_id: UUID,
        thread_id: UUID,
        user: User,
        limit: int,
    ) -> RagHistoryResponse:
        thread = await self._owned_thread(db, subject_id=subject_id, thread_id=thread_id, user=user)
        now = utcnow()
        descending = list((await db.scalars(select(RagMessage).where(
            RagMessage.thread_id == thread_id,
            RagMessage.expires_at > now,
        ).order_by(RagMessage.created_at.desc(), RagMessage.id.desc()).limit(limit))).all())
        messages = list(reversed(descending))
        sources = await self._eligible_source_rows(
            db, [message.id for message in messages if message.role == "assistant" and message.outcome == "answer"]
        )
        payload: list[RagMessageResponse] = []
        for message in messages:
            current_sources = sources.get(message.id, [])
            hidden = message.role == "assistant" and message.outcome == "answer" and len(current_sources) != message.source_count
            payload.append(RagMessageResponse(
                id=message.id,
                role=message.role,
                outcome=message.outcome,
                abstention_kind=message.abstention_kind,
                content=None if hidden else message.content,
                hidden=hidden,
                sources=[] if hidden else current_sources,
                created_at=message.created_at,
                expires_at=message.expires_at,
            ))
        return RagHistoryResponse(thread=self.thread_response(thread), messages=payload)

    async def message_sources(
        self,
        db: AsyncSession,
        *,
        subject_id: UUID,
        thread_id: UUID,
        message_id: UUID,
        user: User,
    ) -> list[RagSourceResponse]:
        await self._owned_thread(db, subject_id=subject_id, thread_id=thread_id, user=user)
        message = await db.scalar(select(RagMessage).where(
            RagMessage.id == message_id,
            RagMessage.thread_id == thread_id,
            RagMessage.user_id == user.id,
            RagMessage.subject_id == subject_id,
            RagMessage.role == "assistant",
            RagMessage.expires_at > utcnow(),
        ))
        if message is None:
            raise rag_http_error(status.HTTP_404_NOT_FOUND, "rag_message_not_found", "Ask AI message not found.")
        sources = (await self._eligible_source_rows(db, [message.id])).get(message.id, [])
        if message.outcome != "answer" or len(sources) != message.source_count:
            raise rag_http_error(status.HTTP_404_NOT_FOUND, "rag_sources_unavailable", "Current answer sources are unavailable.")
        return sources

    @staticmethod
    def thread_response(thread: RagThread) -> RagThreadResponse:
        return RagThreadResponse(
            id=thread.id,
            subject_id=thread.subject_id,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
        )

    def job_response(
        self,
        job: RagAnswerJob,
        *,
        related_excerpts: list[RagRelatedExcerptResponse] | None = None,
    ) -> RagAnswerJobResponse:
        failure_kind = None
        if job.status == "failed" and job.error_code == "rag_answer_failed":
            category = job.provider_error_category
            reason = job.failure_reason
            if category == "invalid_ai_output" or category == "invalid_embedding_output":
                failure_kind = "invalid_output"
            elif category == "local_support_unavailable":
                failure_kind = "support_unavailable"
            elif category in {
                "ai_provider_timeout", "embedding_provider_timeout",
                "ai_provider_rate_limited", "embedding_provider_rate_limited",
                "ai_provider_unavailable", "embedding_provider_unavailable",
            } or reason in {
                "transport_timeout", "transport_protocol", "transport_network",
                "http_rate_limited", "http_server_error", "http_transient",
            }:
                failure_kind = "provider_temporarily_unavailable"
            elif category in {
                "ai_provider_invalid_request", "ai_provider_authentication_failed",
                "ai_provider_access_denied", "ai_model_unavailable",
                "ai_provider_rejected_request", "ai_provider_request_token_limit",
                "ai_model_output_incompatible", "ai_model_schema_incompatible",
                "embedding_provider_invalid_request",
                "embedding_provider_authentication_failed", "embedding_provider_access_denied",
                "embedding_model_unavailable", "embedding_provider_rejected_request",
                "embedding_provider_request_token_limit",
            }:
                failure_kind = "provider_rejected"
            else:
                failure_kind = "internal_failure"
        return RagAnswerJobResponse(
            id=job.id,
            thread_id=job.thread_id,
            subject_id=job.subject_id,
            question_message_id=job.question_message_id,
            answer_message_id=job.answer_message_id,
            status=job.status,
            ask_policy=job.answer_policy_version,
            result_kind=job.result_kind,
            search_mode=(
                "lexical_fallback"
                if job.status == "completed" and job.retrieval_completed_at is not None
                and job.answer_policy_version in (
                    "related_knowledge_navigation_v3", "related_knowledge_navigation_v4",
                    "related_knowledge_navigation_v5", "related_knowledge_navigation_v6",
                    "related_knowledge_navigation_v7", ASK_REQUIRED_RELEASE_POLICY_VERSION)
                and job.failed_stage == "query_embedding" and job.provider_error_category in {
                    "embedding_provider_timeout", "embedding_provider_unavailable", "embedding_provider_rate_limited",
                }
                else "hybrid" if job.status == "completed" and job.retrieval_completed_at is not None
                and job.answer_policy_version in ASK_SOURCE_ONLY_READ_POLICIES
                else "not_searched"
            ),
            embedding_provider=job.embedding_provider,
            embedding_model=job.embedding_model,
            source_judge_provider=job.source_judge_provider,
            source_judge_model=job.source_judge_model,
            ai_provider=job.ai_provider,
            ai_model=job.ai_model,
            retrieval_policy=job.retrieval_policy,
            attempt_count=job.attempt_count,
            manual_retry_count=job.manual_retry_count,
            max_attempts=job.max_attempts,
            estimated_input_tokens=job.estimated_input_tokens,
            estimated_output_tokens=job.estimated_output_tokens,
            actual_input_tokens=job.actual_input_tokens,
            actual_output_tokens=job.actual_output_tokens,
            provider_request_count=job.provider_request_count,
            provider_retry_count=job.provider_retry_count,
            provider_rate_limit_wait_milliseconds=job.provider_rate_limit_wait_milliseconds,
            estimated_cost_microusd=job.estimated_cost_microusd,
            actual_cost_microusd=(
                None if job.attempt_cost_unknown
                or (job.answer_policy_version in ASK_SOURCE_ONLY_READ_POLICIES
                    and job.usage_estimated)
                else job.actual_cost_microusd
            ),
            estimated_additional_cost_microusd=(
                job.estimated_cost_microusd
                if job.answer_policy_version == ASK_REQUIRED_RELEASE_POLICY_VERSION
                and self.settings.rag_related_pricing_configured
                else None
            ),
            previous_attempt_cost_microusd=(
                job.attempt_cost_microusd
                if job.status == "failed"
                and job.answer_policy_version == ASK_REQUIRED_RELEASE_POLICY_VERSION
                and not job.attempt_cost_unknown
                and self.settings.rag_related_pricing_configured
                else None
            ),
            usage_estimated=job.usage_estimated,
            support_rejection_count=job.support_rejection_count,
            error_code=job.error_code,
            error_message=(
                "Knowledge search failed. Please try again."
                if job.answer_policy_version in ASK_SOURCE_ONLY_READ_POLICIES
                and job.status == "failed" and job.error_code == "rag_answer_failed"
                else "Knowledge search was cancelled."
                if job.answer_policy_version in ASK_SOURCE_ONLY_READ_POLICIES
                and job.status == "cancelled"
                else job.error_message
            ),
            failure_kind=failure_kind,
            cancellation_requested_at=job.cancellation_requested_at,
            created_at=job.created_at,
            completed_at=job.completed_at,
            updated_at=job.updated_at,
            can_cancel=job.status in ACTIVE_ANSWER_STATUSES and job.cancellation_requested_at is None,
            can_retry=(
                self.settings.rag_source_only_available
                and
                job.status == "failed"
                and job.error_retryable
                and job.answer_policy_version == ASK_REQUIRED_RELEASE_POLICY_VERSION
                and job.retrieval_policy == SOURCE_NAVIGATION_RETRIEVAL_POLICY.policy_id
                and job.manual_retry_count < self.settings.rag_answer_max_manual_retries
            ),
            related_excerpts=related_excerpts or [],
        )


__all__ = ["RagAnswerService", "rag_http_error"]
