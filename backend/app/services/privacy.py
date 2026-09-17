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
from app.models.generation import GenerationJob, GenerationJobSource, GenerationQuotaEvent
from app.models.email import EmailOutboxMessage
from app.models.subject import FlashcardSet, Subject
from app.models.user import AuthSession, InviteLink, PasswordResetToken, RateLimitBucket, User
from app.time_utils import as_utc, utcnow


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
                           ("id", "subject_id", "status", "stage", "requested_card_count",
                            "generated_card_count", "ai_provider", "ai_model", "error_code",
                            "provider_request_count", "provider_retry_count", "estimated_input_tokens",
                            "estimated_output_tokens", "actual_input_tokens", "actual_output_tokens",
                            "estimated_cost_microusd", "actual_cost_microusd", "created_at", "completed_at")),
    }


async def delete_account(db: AsyncSession, user_id: UUID) -> dict[str, int]:
    """Delete explicitly requested identity/dependents, never commit implicitly.

    The CLI must require operator acknowledgement that writers/workers have been
    stopped. Locks prevent claims/inserts racing the commit; already-running
    generation or SMTP claims cause a refusal rather than a remote side effect.
    """
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
    return {"accounts": 1, "generation_jobs": len(jobs), "email_events": len(outbox),
            "recipient_invitations": len(bound_invites)}


async def cleanup_retention(db: AsyncSession, settings: Settings, dry_run: bool = True) -> dict[str, int]:
    """Count or remove at most one configured batch per safe metadata category.

    Active windows, remote work, sources and durable study receipts are protected.
    Email-dependent reset/invite rows survive until their outbox history expires.
    This function does not replace source expiry/lease recovery in the workers.
    """
    from app.models.audit import AuditEvent
    from app.models.operations import RequestEvent, WorkerHeartbeat

    now = utcnow()
    metadata_cutoff = now - timedelta(days=settings.database_metadata_retention_days)
    job_cutoff = now - timedelta(days=settings.generation_job_retention_days)
    has_source = exists().where(GenerationJobSource.job_id == GenerationJob.id)
    has_reset_email = exists().where(EmailOutboxMessage.password_reset_token_id == PasswordResetToken.id)
    has_invite_email = exists().where(EmailOutboxMessage.invite_link_id == InviteLink.id)
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
