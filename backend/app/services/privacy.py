"""Operator-mediated privacy operations; the caller owns every transaction.

No operation here deletes business data on an age/inactivity schedule. Account
deletion requires quiesced writers/workers and an explicit operator command.
Exports contain private account data and must never be written to application
logs. PostgreSQL exports require this to be the transaction's first operation.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID

from sqlalchemy import delete, exists, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.flashcard import Enrollment, Flashcard, StudyAnswerSubmission, StudyProgress
from app.models.generation import (
    GenerationJob,
    GenerationJobSource,
    GenerationQuotaEvent,
    KnowledgeUploadQuotaEvent,
)
from app.models.knowledge import (
    SubjectDocument,
    SubjectDocumentChunk,
    SubjectDocumentContentRevision,
    SubjectDocumentIndexJob,
    SubjectDocumentIndexRevision,
    SubjectDocumentPage,
)
from app.models.rag import (
    RagAnswerJob,
    RagAnswerQuotaEvent,
    RagMessage,
    RagMessageSource,
    RagThread,
)
from app.models.email import EmailOutboxMessage
from app.models.subject import FlashcardSet, Subject
from app.models.user import AuthSession, InviteLink, PasswordResetToken, RateLimitBucket, User
from app.time_utils import as_utc, utcnow
from app.services.knowledge_lock import acquire_knowledge_write_lock


class PrivacyOperationError(ValueError):
    """Fixed, content-free operator error with a machine-readable code."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _json_value(value):
    if isinstance(value, datetime):
        return as_utc(value).isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def _fields(row, fields: tuple[str, ...]) -> dict:
    return {field: _json_value(getattr(row, field)) for field in fields}


async def export_account(db: AsyncSession, user_id: UUID) -> dict:
    """Export only the account's own records from one PostgreSQL snapshot.

    Start with a fresh session/transaction: PostgreSQL rejects setting isolation
    after an earlier query. The caller releases the read-only transaction.
    """
    if db.get_bind().dialect.name == "postgresql":
        await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
    user = await db.get(User, user_id)
    if user is None:
        raise PrivacyOperationError("account_not_found", "Account was not found.")

    owned_subjects = select(Subject.id).where(Subject.instructor_id == user_id)
    owned_sets = select(FlashcardSet.id).where(FlashcardSet.subject_id.in_(owned_subjects))
    owned_documents = select(SubjectDocument.id).where(SubjectDocument.uploader_id == user_id)
    owned_indexes = select(SubjectDocumentIndexRevision.id).where(
        SubjectDocumentIndexRevision.uploader_id == user_id
    )
    owned_rag_messages = select(RagMessage.id).where(RagMessage.user_id == user_id)

    async def rows(model, condition, fields: tuple[str, ...]) -> list[dict]:
        records = await db.scalars(select(model).where(condition).order_by(model.id))
        return [_fields(row, fields) for row in records]

    progress_fields = (
        "id", "flashcard_id", "status", "ease_factor", "interval_days", "next_review",
        "last_reviewed", "correct_count", "incorrect_count",
    )
    receipt_rows = await db.scalars(
        select(StudyAnswerSubmission).where(StudyAnswerSubmission.student_id == user_id)
        .order_by(StudyAnswerSubmission.id)
    )
    receipts = []
    for row in receipt_rows:
        # Do not blindly export arbitrary persisted JSON or key/fingerprint hashes.
        response = row.response_payload or {}
        receipts.append({
            **_fields(row, ("id", "flashcard_id", "created_at")),
            "answer": {key: response[key] for key in (
                "is_correct", "quality", "correct_option", "correct_option_index",
            ) if key in response},
        })

    return {
        "format_version": 1,
        "exported_at": utcnow().isoformat(),
        "profile": _fields(user, ("id", "email", "full_name", "role", "created_at")),
        "enrollments": await rows(Enrollment, Enrollment.student_id == user_id,
                                  ("id", "subject_id", "enrolled_at")),
        "progress": await rows(StudyProgress, StudyProgress.student_id == user_id, progress_fields),
        "answer_receipts": receipts,
        "subjects": await rows(Subject, Subject.instructor_id == user_id,
                               ("id", "name", "description", "created_at")),
        "sets": await rows(FlashcardSet, FlashcardSet.subject_id.in_(owned_subjects),
                           ("id", "subject_id", "title", "description", "source_pdf_name",
                            "generation_job_id", "is_published", "time_limit", "created_at")),
        "cards": await rows(Flashcard, Flashcard.set_id.in_(owned_sets),
                            ("id", "set_id", "front_content", "back_content", "options",
                             "card_type", "quality_score", "is_approved", "source_snippet",
                             "source_page", "source_section", "created_at")),
        "jobs": await rows(GenerationJob, GenerationJob.user_id == user_id,
                           ("id", "subject_id", "job_kind", "document_id",
                            "knowledge_content_revision_id", "knowledge_capture_status",
                            "knowledge_capture_error_code", "status", "stage", "requested_card_count",
                            "generated_card_count", "ai_provider", "ai_model", "error_code",
                            "provider_request_count", "provider_retry_count", "estimated_input_tokens",
                            "estimated_output_tokens", "actual_input_tokens", "actual_output_tokens",
                            "estimated_cost_microusd", "actual_cost_microusd", "created_at", "completed_at")),
        "knowledge_documents": await rows(
            SubjectDocument,
            SubjectDocument.uploader_id == user_id,
            ("id", "subject_id", "title", "source_pdf_name", "created_at", "updated_at"),
        ),
        "knowledge_content_revisions": await rows(
            SubjectDocumentContentRevision,
            SubjectDocumentContentRevision.uploader_id == user_id,
            ("id", "document_id", "subject_id", "revision_no", "extraction_version",
             "status", "is_active", "reviewed_at", "published_at",
             "created_at", "updated_at"),
        ),
        "knowledge_pages": await rows(
            SubjectDocumentPage,
            SubjectDocumentPage.document_id.in_(owned_documents),
            ("id", "content_revision_id", "document_id", "subject_id", "page_number", "content"),
        ),
        "knowledge_index_revisions": await rows(
            SubjectDocumentIndexRevision,
            SubjectDocumentIndexRevision.uploader_id == user_id,
            ("id", "content_revision_id", "document_id", "subject_id", "revision_no",
             "chunker_version", "embedding_provider", "embedding_model",
             "embedding_space_revision", "embedding_format_version", "embedding_dimensions",
             "embedding_representation", "embedding_metric", "document_task_mode",
             "query_task_mode", "status",
             "is_active", "created_at", "updated_at"),
        ),
        # Embedding vectors are derived provider output and intentionally omitted;
        # server-derived source text/provenance remains part of the user's export.
        "knowledge_chunks": await rows(
            SubjectDocumentChunk,
            SubjectDocumentChunk.index_revision_id.in_(owned_indexes),
            ("id", "index_revision_id", "content_revision_id", "document_id", "subject_id",
             "chunk_index", "local_chunk_id", "page_number", "section", "content", "token_count",
            ),
        ),
        "knowledge_index_jobs": await rows(
            SubjectDocumentIndexJob,
            SubjectDocumentIndexJob.uploader_id == user_id,
            ("id", "index_revision_id", "content_revision_id", "document_id", "subject_id",
             "status", "attempt_count", "max_attempts", "error_code", "estimated_input_tokens",
             "actual_input_tokens", "provider_request_count", "provider_retry_count",
             "estimated_cost_microusd", "actual_cost_microusd", "created_at", "completed_at"),
        ),
        # Conversation export is principal-owned even for instructors: access
        # to a Subject never grants access to another user's private chat.
        "rag_threads": await rows(
            RagThread,
            RagThread.user_id == user_id,
            ("id", "subject_id", "created_at", "updated_at"),
        ),
        "rag_messages": await rows(
            RagMessage,
            RagMessage.user_id == user_id,
            ("id", "thread_id", "subject_id", "role", "outcome", "content",
             "source_count", "corpus_revision", "created_at",
             "expires_at"),
        ),
        "rag_message_sources": await rows(
            RagMessageSource,
            RagMessageSource.message_id.in_(owned_rag_messages),
            ("id", "message_id", "thread_id", "subject_id", "chunk_id", "document_id",
             "content_revision_id", "index_revision_id", "citation_order", "claim_text",
             "source_quote", "created_at"),
        ),
        "rag_answer_jobs": await rows(
            RagAnswerJob,
            RagAnswerJob.user_id == user_id,
            ("id", "thread_id", "question_message_id", "answer_message_id", "subject_id",
             "status", "document_ids", "corpus_revision", "retrieval_policy",
             "ai_provider", "ai_model", "attempt_count",
             "manual_retry_count", "max_attempts", "estimated_input_tokens",
             "estimated_output_tokens", "actual_input_tokens", "actual_output_tokens",
             "provider_request_count", "provider_retry_count",
             "provider_rate_limit_wait_milliseconds", "estimated_cost_microusd",
             "actual_cost_microusd", "usage_estimated", "support_rejection_count",
             "error_code", "created_at", "completed_at"),
        ),
    }


async def delete_account(db: AsyncSession, user_id: UUID) -> dict[str, int]:
    """Delete explicitly requested identity/dependents, never commit implicitly.

    The CLI must require operator acknowledgement that writers/workers have been
    stopped. Locks prevent claims/inserts racing the commit; already-running
    generation or SMTP claims cause a refusal rather than a remote side effect.
    """
    await acquire_knowledge_write_lock(db)
    user = await db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise PrivacyOperationError("account_not_found", "Account was not found.")
    subject_ids = select(Subject.id).where(Subject.instructor_id == user_id)
    jobs = list((await db.scalars(
        select(GenerationJob).where(or_(GenerationJob.user_id == user_id,
                                       GenerationJob.subject_id.in_(subject_ids)))
        .order_by(GenerationJob.id).with_for_update()
    )).all())
    if any(job.status == "running" for job in jobs):
        raise PrivacyOperationError("account_work_active", "Stop and drain account generation work before deletion.")
    index_jobs = list((await db.scalars(
        select(SubjectDocumentIndexJob).where(or_(
            SubjectDocumentIndexJob.uploader_id == user_id,
            SubjectDocumentIndexJob.subject_id.in_(subject_ids),
        )).order_by(SubjectDocumentIndexJob.id).with_for_update()
    )).all())
    if any(job.status == "running" for job in index_jobs):
        raise PrivacyOperationError(
            "account_work_active", "Stop and drain account Knowledge indexing before deletion."
        )
    answer_jobs = list((await db.scalars(
        select(RagAnswerJob).where(or_(
            RagAnswerJob.user_id == user_id,
            RagAnswerJob.subject_id.in_(subject_ids),
        )).order_by(RagAnswerJob.id).with_for_update()
    )).all())
    if any(job.status == "running" for job in answer_jobs):
        raise PrivacyOperationError(
            "account_work_active", "Stop and drain account Ask AI work before deletion."
        )

    email = user.email.strip().lower()
    invite_ids = select(InviteLink.id).where(InviteLink.instructor_id == user_id)
    reset_ids = select(PasswordResetToken.id).where(PasswordResetToken.user_id == user_id)
    outbox_condition = or_(
        EmailOutboxMessage.recipient_email == email,
        EmailOutboxMessage.invite_link_id.in_(invite_ids),
        EmailOutboxMessage.password_reset_token_id.in_(reset_ids),
    )
    outbox = list((await db.scalars(
        select(EmailOutboxMessage).where(outbox_condition)
        .order_by(EmailOutboxMessage.id).with_for_update()
    )).all())
    if any(message.status == "sending" for message in outbox):
        raise PrivacyOperationError("account_email_active", "Stop and drain related email delivery before deletion.")

    # Remove recipient copies owned by a different instructor as well. An unused
    # addressed invitation must be removed, never converted into a public invite.
    # Used invitations retain used_at so account deletion cannot resurrect them.
    bound_invites = list((await db.scalars(
        select(InviteLink).where(InviteLink.recipient_email == email)
        .order_by(InviteLink.id).with_for_update()
    )).all())
    for invite in bound_invites:
        invite.recipient_email = None
        if invite.used_at is None:
            # Preserve the database's 1-hour minimum lifetime constraint. Remove
            # an unused invite instead of rewriting expiry or unbinding its token.
            await db.delete(invite)
    await db.execute(delete(EmailOutboxMessage).where(outbox_condition))
    await db.execute(delete(User).where(User.id == user_id))
    from app.models.audit import AuditAction
    from app.services.audit import AuditService
    AuditService.record(db, action=AuditAction.ACCOUNT_DELETED, actor_kind="operator",
                        target_type="account", target_id=user_id, affected_count=1)
    await db.flush()
    return {"accounts": 1, "generation_jobs": len(jobs), "knowledge_index_jobs": len(index_jobs),
            "rag_answer_jobs": len(answer_jobs), "email_events": len(outbox),
            "recipient_invitations": len(bound_invites)}


async def cleanup_retention(db: AsyncSession, settings: Settings, dry_run: bool = True) -> dict[str, int]:
    """Count or remove at most one configured batch per safe metadata category.

    Active windows, remote work, sources and durable study receipts are protected.
    Email-dependent reset/invite rows survive until their outbox history expires.
    This function does not replace source expiry/lease recovery in the workers.
    """
    from app.models.audit import AuditEvent
    from app.models.operations import RequestEvent, WorkerHeartbeat

    if not dry_run:
        # Old generation history can be linked to durable Knowledge. Admission
        # precedes its FOR UPDATE rows, preserving document-delete lock order.
        await acquire_knowledge_write_lock(db)

    now = utcnow()
    metadata_cutoff = now - timedelta(days=settings.database_metadata_retention_days)
    job_cutoff = now - timedelta(days=settings.generation_job_retention_days)
    has_source = exists().where(GenerationJobSource.job_id == GenerationJob.id)
    has_reset_email = exists().where(EmailOutboxMessage.password_reset_token_id == PasswordResetToken.id)
    has_invite_email = exists().where(EmailOutboxMessage.invite_link_id == InviteLink.id)
    has_answer_job = exists().where(RagAnswerJob.answer_message_id == RagMessage.id)
    has_rag_message = exists().where(RagMessage.thread_id == RagThread.id)
    # Some narrow unit-test settings objects predate Ask AI. Runtime Settings
    # always supplies this field; the fallback preserves the approved G2 value.
    rag_cutoff = now - timedelta(days=getattr(settings, "rag_chat_retention_days", 90))
    categories = (
        ("request_events", RequestEvent, RequestEvent.created_at < now - timedelta(days=settings.request_retention_days), RequestEvent.id),
        ("audit_events", AuditEvent, AuditEvent.created_at < now - timedelta(days=settings.audit_retention_days), AuditEvent.id),
        ("worker_heartbeats", WorkerHeartbeat, WorkerHeartbeat.last_seen_at < now - timedelta(hours=24), WorkerHeartbeat.worker_id),
        ("generation_jobs", GenerationJob, (GenerationJob.status.in_(("completed", "failed", "cancelled"))) & (GenerationJob.completed_at < job_cutoff) & ~has_source, GenerationJob.id),
        ("rate_limit_buckets", RateLimitBucket, RateLimitBucket.updated_at < metadata_cutoff, RateLimitBucket.id),
        # Quota operation keys also back manual-retry idempotency. A receipt
        # must survive for as long as its linked job, including long source
        # retention or queue waits. Job deletion detaches charges with SET NULL.
        ("generation_quota_events", GenerationQuotaEvent,
         (GenerationQuotaEvent.created_at < metadata_cutoff) & GenerationQuotaEvent.job_id.is_(None),
         GenerationQuotaEvent.id),
        ("knowledge_upload_quota_events", KnowledgeUploadQuotaEvent,
         (KnowledgeUploadQuotaEvent.created_at < metadata_cutoff) & KnowledgeUploadQuotaEvent.job_id.is_(None),
         KnowledgeUploadQuotaEvent.id),
        # Questions are deleted first so their ON DELETE CASCADE removes the
        # durable job. Assistant rows referenced by a surviving job are held
        # until that question/job can be safely removed.
        ("rag_question_messages", RagMessage,
         (RagMessage.expires_at < now) & (RagMessage.role == "user"), RagMessage.id),
        ("rag_assistant_messages", RagMessage,
         (RagMessage.expires_at < now) & (RagMessage.role == "assistant") & ~has_answer_job,
         RagMessage.id),
        ("rag_threads", RagThread,
         (RagThread.updated_at < rag_cutoff) & ~has_rag_message, RagThread.id),
        # Quota receipts remain idempotency/rate-limit evidence while their job
        # exists; job deletion detaches the event with SET NULL.
        ("rag_answer_quota_events", RagAnswerQuotaEvent,
         (RagAnswerQuotaEvent.created_at < metadata_cutoff) & RagAnswerQuotaEvent.job_id.is_(None),
         RagAnswerQuotaEvent.id),
        ("auth_sessions", AuthSession, AuthSession.expires_at < metadata_cutoff, AuthSession.id),
        ("password_reset_tokens", PasswordResetToken, (PasswordResetToken.expires_at < metadata_cutoff) & ~has_reset_email, PasswordResetToken.id),
        ("invite_links", InviteLink, (InviteLink.expires_at < metadata_cutoff) & ~has_invite_email, InviteLink.id),
    )
    age_columns = {
        "request_events": RequestEvent.created_at,
        "audit_events": AuditEvent.created_at,
        "worker_heartbeats": WorkerHeartbeat.last_seen_at,
        "generation_jobs": GenerationJob.completed_at,
        "rate_limit_buckets": RateLimitBucket.updated_at,
        "generation_quota_events": GenerationQuotaEvent.created_at,
        "knowledge_upload_quota_events": KnowledgeUploadQuotaEvent.created_at,
        "rag_question_messages": RagMessage.expires_at,
        "rag_assistant_messages": RagMessage.expires_at,
        "rag_threads": RagThread.updated_at,
        "rag_answer_quota_events": RagAnswerQuotaEvent.created_at,
        "auth_sessions": AuthSession.expires_at,
        "password_reset_tokens": PasswordResetToken.expires_at,
        "invite_links": InviteLink.expires_at,
    }
    counts = {}
    for name, model, condition, primary_key in categories:
        query = (select(primary_key).where(condition).order_by(age_columns[name], primary_key)
                 .limit(settings.retention_batch_size))
        if not dry_run:
            query = query.with_for_update(skip_locked=db.get_bind().dialect.name == "postgresql")
        keys = list((await db.scalars(query)).all())
        counts[name] = len(keys)
        if not dry_run and keys:
            await db.execute(delete(model).where(primary_key.in_(keys), condition))
    if not dry_run:
        await db.flush()
    return counts
