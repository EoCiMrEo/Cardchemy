"""Private Ask AI admission, authorization, history and lifecycle service."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chunking import estimate_tokens
from app.config import Settings, get_settings
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
    RagSourceResponse,
    RagThreadResponse,
)
from app.services.generation import hash_operation_key
from app.services.knowledge_retrieval import EXACT_V1_POLICY, KnowledgeRetriever, KnowledgeScopeUnavailable
from app.services.subject import SubjectService
from app.observability import current_request_id
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


def _cost_microusd(settings: Settings, input_tokens: int, output_tokens: int) -> int:
    total = (
        Decimal(input_tokens) * settings.rag_ai_input_cost_per_million_usd
        + Decimal(output_tokens) * settings.rag_ai_output_cost_per_million_usd
    )
    return int(total.to_integral_value(rounding=ROUND_CEILING))


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
        if not self.settings.rag_answer_available:
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
        """Reserve future assistant rows represented by active answer jobs.

        The admission advisory lock serializes these counts with enqueue/retry.
        Each queued/running job already owns its question row and reserves one
        not-yet-written assistant row. This prevents concurrent admissions from
        exceeding durable thread, user, or deployment storage limits at commit.
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
        )) or 0)
        user_reservations = int(await db.scalar(select(func.count(RagAnswerJob.id)).where(
            RagAnswerJob.user_id == user_id,
            RagAnswerJob.status.in_(ACTIVE_ANSWER_STATUSES),
        )) or 0)
        deployment_reservations = int(await db.scalar(select(func.count(RagAnswerJob.id)).where(
            RagAnswerJob.status.in_(ACTIVE_ANSWER_STATUSES),
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
            new_messages=2,
        )

        try:
            retriever = await KnowledgeRetriever.authorize(
                db,
                principal=user,
                subject_id=subject_id,
                query=data.question,
                document_ids=data.document_ids,
                limit=EXACT_V1_POLICY.max_results,
            )
        except KnowledgeScopeUnavailable:
            raise rag_http_error(status.HTTP_409_CONFLICT, "rag_knowledge_unavailable", "Current course materials are unavailable for this request.") from None

        now = utcnow()
        auth_session_id = getattr(user, "_auth_session_id", None)
        if not isinstance(auth_session_id, UUID):
            raise rag_http_error(status.HTTP_401_UNAUTHORIZED, "authentication_required", "Could not validate credentials")
        expires_at = now + timedelta(days=self.settings.rag_chat_retention_days)
        question = RagMessage(
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
        db.add(question)
        await db.flush()
        configured_space = embedding_space_hash(self.settings.rag_embedding_space_identity)
        space_hash = retriever.scope.embedding_space_hash or configured_space
        estimated_input = min(
            self.settings.rag_ai_max_job_input_tokens,
            estimate_tokens(data.question)
            + self.settings.rag_answer_history_token_limit
            + EXACT_V1_POLICY.context_token_limit
            + 1_024,
        )
        estimated_output = min(
            self.settings.rag_ai_max_job_output_tokens,
            self.settings.rag_ai_max_output_tokens * 2,
        )
        estimated_cost = _cost_microusd(self.settings, estimated_input, estimated_output)
        if estimated_cost > int(self.settings.rag_ai_max_estimated_cost_usd * Decimal(1_000_000)):
            raise rag_http_error(status.HTTP_409_CONFLICT, "rag_answer_cost_limit", "The Ask AI request exceeds the configured cost limit.")
        job = RagAnswerJob(
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
            retrieval_policy=EXACT_V1_POLICY.policy_id,
            embedding_space_hash=space_hash,
            ai_provider=self.settings.rag_ai_provider,
            ai_base_url=self.settings.rag_ai_endpoint_identity,
            ai_model=self.settings.rag_ai_model,
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
        return RagAnswerJobListResponse(
            jobs=[self.job_response(job) for job in jobs]
        )

    async def cancel(
        self, db: AsyncSession, *, subject_id: UUID, thread_id: UUID, job_id: UUID, user: User
    ) -> RagAnswerJob:
        await self._lock_admission(db)
        job = await self.owned_job(
            db, subject_id=subject_id, thread_id=thread_id, job_id=job_id, user=user, for_update=True
        )
        now = utcnow()
        if job.status == "queued":
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
        if job.status != "failed" or not job.error_retryable:
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
            or (current_space is not None and current_space != job.embedding_space_hash)
            or configured_space != job.embedding_space_hash
            or self.settings.rag_ai_provider != job.ai_provider
            or self.settings.rag_ai_endpoint_identity != job.ai_base_url
            or self.settings.rag_ai_model != job.ai_model
        ):
            raise rag_http_error(status.HTTP_409_CONFLICT, "rag_answer_snapshot_changed", "Ask AI configuration or course materials changed; submit a new question.")
        await self._check_job_capacity(db, user.id)
        await self._check_message_capacity(
            db,
            user_id=user.id,
            thread_id=thread_id,
            new_messages=1,
        )
        now = utcnow()
        db.add(RagAnswerQuotaEvent(
            user_id=user.id,
            job_id=job.id,
            operation_key_hash=retry_key_hash,
            job_units=1,
            created_at=now,
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
        job.completed_at = None
        job.error_code = None
        job.error_message = None
        job.error_retryable = False
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

    def job_response(self, job: RagAnswerJob) -> RagAnswerJobResponse:
        return RagAnswerJobResponse(
            id=job.id,
            thread_id=job.thread_id,
            subject_id=job.subject_id,
            question_message_id=job.question_message_id,
            answer_message_id=job.answer_message_id,
            status=job.status,
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
            actual_cost_microusd=job.actual_cost_microusd,
            usage_estimated=job.usage_estimated,
            support_rejection_count=job.support_rejection_count,
            error_code=job.error_code,
            error_message=job.error_message,
            cancellation_requested_at=job.cancellation_requested_at,
            created_at=job.created_at,
            completed_at=job.completed_at,
            updated_at=job.updated_at,
            can_cancel=job.status in ACTIVE_ANSWER_STATUSES and job.cancellation_requested_at is None,
            can_retry=(
                job.status == "failed"
                and job.error_retryable
                and job.manual_retry_count < self.settings.rag_answer_max_manual_retries
            ),
        )


__all__ = ["RagAnswerService", "rag_http_error"]
