"""Deployed-database proof for operator privacy cascades/snapshots/locks."""

from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text

from app.config import Settings
from app.models.audit import AuditEvent
from app.models.email import EmailOutboxMessage
from app.models.flashcard import Enrollment, Flashcard, StudyAnswerSubmission, StudyProgress
from app.models.generation import GenerationJob, GenerationJobSource, GenerationQuotaEvent
from app.models.rag import RagAnswerJob, RagAnswerQuotaEvent, RagMessage, RagThread
from app.models.subject import FlashcardSet, Subject
from app.models.user import AuthSession, InviteLink, PasswordResetToken, User
from app.services.privacy import PrivacyOperationError, cleanup_retention, delete_account, export_account
from app.services.generation import GenerationJobService, hash_operation_key
from app.services.subject import SubjectService
from app.time_utils import utcnow
from tests.support.privacy_fixtures import (
    addressed_invite, invitation_email, job_for, retention_settings, seed_private_course,
    seed_rag_job,
)


pytestmark = pytest.mark.postgres


async def test_account_export_uses_readonly_repeatable_snapshot(postgres_session_factory):
    async with postgres_session_factory() as db:
        async with db.begin():
            course = await seed_private_course(db)
            owner_id, subject_id = course.owner.id, course.subject.id
    async with postgres_session_factory() as snapshot:
        exported = await export_account(snapshot, owner_id)
        assert exported["subjects"][0]["name"] == "Authored course"
        assert await snapshot.scalar(text("SHOW transaction_isolation")) == "repeatable read"
        assert await snapshot.scalar(text("SHOW transaction_read_only")) == "on"
        async with postgres_session_factory() as writer:
            async with writer.begin():
                subject = await writer.get(Subject, subject_id)
                subject.name = "Concurrent updated course"
        assert await snapshot.scalar(select(Subject.name).where(Subject.id == subject_id)) == "Authored course"


async def test_account_export_never_includes_another_students_rag_chat(postgres_session_factory):
    async with postgres_session_factory() as db:
        async with db.begin():
            course = await seed_private_course(db)
            own = await seed_rag_job(db, course, user=course.student)
            other = await seed_rag_job(db, course, user=course.other)
            student_id = course.student.id
            own_thread_id = own.thread.id
            own_question = own.question.content
            other_question = other.question.content
    async with postgres_session_factory() as db:
        exported = await export_account(db, student_id)
        assert [row["id"] for row in exported["rag_threads"]] == [str(own_thread_id)]
        assert [row["content"] for row in exported["rag_messages"]] == [own_question]
        assert other_question not in str(exported)


async def test_student_deletion_removes_all_address_copies_without_resurrecting_invite(postgres_session_factory):
    async with postgres_session_factory() as db:
        async with db.begin():
            course = await seed_private_course(db)
            invite = addressed_invite(course)
            unused = addressed_invite(course, consumed=False)
            db.add_all([invite, unused])
            await db.flush()
            messages = [invitation_email(invite), invitation_email(unused)]
            db.add_all(messages)
            await db.flush()
            user_id, owner_id, other_id = course.student.id, course.owner.id, course.other.id
            subject_id, invite_id, unused_id = course.subject.id, invite.id, unused.id
            used_at = invite.used_at
            message_ids = [message.id for message in messages]
    async with postgres_session_factory() as db:
        async with db.begin():
            await delete_account(db, user_id)
    async with postgres_session_factory() as db:
        assert await db.get(User, user_id) is None
        assert await db.get(User, owner_id) is not None and await db.get(User, other_id) is not None
        assert await db.get(Subject, subject_id) is not None
        remaining = await db.get(InviteLink, invite_id)
        assert remaining.used_by is None and remaining.used_at == used_at
        assert remaining.recipient_email is None
        assert await db.get(InviteLink, unused_id) is None
        assert not (await db.scalars(select(EmailOutboxMessage).where(EmailOutboxMessage.id.in_(message_ids)))).all()
        for model in (Enrollment, StudyProgress, StudyAnswerSubmission):
            assert await db.scalar(select(model.id).where(model.student_id == user_id)) is None
        assert await db.scalar(select(AuditEvent.id).where(AuditEvent.action == "account.deleted", AuditEvent.target_id == user_id)) is not None


async def test_instructor_deletion_cascades_sources_results_and_auth_but_retains_redacted_audit(postgres_session_factory):
    async with postgres_session_factory() as db:
        async with db.begin():
            course = await seed_private_course(db)
            job = job_for(course)
            db.add(job)
            await db.flush()
            db.add(GenerationJobSource(job_id=job.id, payload=b"encrypted-fixture" * 3,
                                       nonce=b"0123456789ab", expires_at=utcnow() + timedelta(hours=1)))
            course.card_set.generation_job_id = job.id
            auth = AuthSession(user_id=course.owner.id, refresh_jti_hash=uuid4().hex * 2,
                               expires_at=utcnow() + timedelta(days=1))
            reset = PasswordResetToken(user_id=course.owner.id, expires_at=utcnow() + timedelta(minutes=30))
            audit = AuditEvent(action="card.approved", actor_kind="user", actor_id=course.owner.id,
                               target_type="card", target_id=course.card.id)
            db.add_all([auth, reset, audit])
            await db.flush()
            owner_id, student_id, job_id, subject_id = course.owner.id, course.student.id, job.id, course.subject.id
            set_id, card_id, auth_id, reset_id, audit_id = course.card_set.id, course.card.id, auth.id, reset.id, audit.id
    async with postgres_session_factory() as db:
        async with db.begin():
            await delete_account(db, owner_id)
    async with postgres_session_factory() as db:
        for model, identity in ((User, owner_id), (GenerationJob, job_id), (GenerationJobSource, job_id),
                                (Subject, subject_id), (FlashcardSet, set_id), (Flashcard, card_id),
                                (AuthSession, auth_id), (PasswordResetToken, reset_id)):
            assert await db.get(model, identity) is None
        assert await db.get(User, student_id) is not None
        assert (await db.get(AuditEvent, audit_id)).actor_id is None


async def test_retention_skips_locked_terminal_job_and_keeps_content_and_current_quota(postgres_session_factory):
    async with postgres_session_factory() as db:
        async with db.begin():
            course = await seed_private_course(db)
            job = job_for(course, status="completed", age_days=4000)
            db.add(job)
            await db.flush()
            course.card_set.generation_job_id = job.id
            quota = GenerationQuotaEvent(user_id=course.owner.id, job_id=job.id,
                                         operation_key_hash=uuid4().hex * 2, card_units=1)
            db.add(quota)
            await db.flush()
            job_id, set_id, quota_id = job.id, course.card_set.id, quota.id
    async with postgres_session_factory() as lock:
        async with lock.begin():
            await lock.scalar(select(GenerationJob.id).where(GenerationJob.id == job_id).with_for_update())
            async with postgres_session_factory() as cleaner:
                async with cleaner.begin():
                    await cleanup_retention(cleaner, retention_settings(), dry_run=False)
            assert await lock.get(GenerationJob, job_id) is not None
    async with postgres_session_factory() as cleaner:
        async with cleaner.begin():
            await cleanup_retention(cleaner, retention_settings(), dry_run=False)
    async with postgres_session_factory() as db:
        assert await db.get(GenerationJob, job_id) is None
        assert (await db.get(FlashcardSet, set_id)).generation_job_id is None
        assert (await db.get(GenerationQuotaEvent, quota_id)).job_id is None


async def test_deletion_refuses_a_claim_that_has_started(postgres_session_factory):
    async with postgres_session_factory() as db:
        async with db.begin():
            course = await seed_private_course(db)
            job = job_for(course, status="running")
            db.add(job)
            owner_id = course.owner.id
    async with postgres_session_factory() as db:
        with pytest.raises(PrivacyOperationError) as error:
            async with db.begin():
                await delete_account(db, owner_id)
        assert error.value.code == "account_work_active"
        assert await db.get(User, owner_id) is not None


async def test_account_and_subject_deletion_refuse_running_answer_claim(postgres_session_factory):
    async with postgres_session_factory() as db:
        async with db.begin():
            course = await seed_private_course(db)
            rag = await seed_rag_job(db, course, status="running")
            student_id = course.student.id
            subject_id = course.subject.id
            job_id = rag.job.id

    async with postgres_session_factory() as db:
        with pytest.raises(PrivacyOperationError) as account_error:
            async with db.begin():
                await delete_account(db, student_id)
        assert account_error.value.code == "account_work_active"

    async with postgres_session_factory() as db:
        with pytest.raises(HTTPException) as subject_error:
            async with db.begin():
                subject = await db.get(Subject, subject_id)
                await SubjectService.delete_subject(db, subject)
        assert subject_error.value.detail["code"] == "subject_work_active"

    async with postgres_session_factory() as db:
        assert await db.get(User, student_id) is not None
        assert await db.get(Subject, subject_id) is not None
        assert await db.get(RagAnswerJob, job_id) is not None


async def test_subject_deletion_cascades_queued_answer_without_resurrection_on_postgres(
    postgres_session_factory,
):
    async with postgres_session_factory() as db:
        async with db.begin():
            course = await seed_private_course(db)
            rag = await seed_rag_job(db, course, status="queued")
            subject_id = course.subject.id
            owner_id = course.owner.id
            student_id = course.student.id
            thread_id = rag.thread.id
            job_id = rag.job.id

    async with postgres_session_factory() as db:
        async with db.begin():
            subject = await db.get(Subject, subject_id)
            await SubjectService.delete_subject(db, subject)

    async with postgres_session_factory() as db:
        assert await db.get(Subject, subject_id) is None
        assert await db.get(RagThread, thread_id) is None
        assert await db.get(RagAnswerJob, job_id) is None
        assert await db.get(User, owner_id) is not None
        assert await db.get(User, student_id) is not None


async def test_rag_retention_cascades_in_safe_order_on_postgres(postgres_session_factory):
    async with postgres_session_factory() as db:
        async with db.begin():
            course = await seed_private_course(db)
            rag = await seed_rag_job(db, course, status="completed", expired=True)
            quota = RagAnswerQuotaEvent(
                user_id=course.student.id,
                job_id=rag.job.id,
                operation_key_hash=uuid4().hex * 2,
                created_at=utcnow() - timedelta(days=120),
            )
            db.add(quota)
            await db.flush()
            ids = (rag.thread.id, rag.question.id, rag.answer.id, rag.job.id, quota.id)

    async with postgres_session_factory() as db:
        async with db.begin():
            applied = await cleanup_retention(db, retention_settings(), dry_run=False)
        assert applied["rag_question_messages"] == 1
        assert applied["rag_assistant_messages"] == 1
        assert applied["rag_threads"] == 1
        assert applied["rag_answer_quota_events"] == 1

    async with postgres_session_factory() as db:
        for model, identity in (
            (RagThread, ids[0]),
            (RagMessage, ids[1]),
            (RagMessage, ids[2]),
            (RagAnswerJob, ids[3]),
            (RagAnswerQuotaEvent, ids[4]),
        ):
            assert await db.get(model, identity) is None


async def test_manual_retry_receipt_survives_shorter_metadata_than_source_retention(postgres_session_factory):
    key = f"retained-manual-retry-{uuid4().hex}"
    now = utcnow()
    async with postgres_session_factory() as db:
        async with db.begin():
            course = await seed_private_course(db)
            job = job_for(course, age_days=2)
            job.error_retryable = True
            job.manual_retry_count = 1
            db.add(job)
            await db.flush()
            charge = GenerationQuotaEvent(user_id=course.owner.id, job_id=job.id,
                                          operation_key_hash=hash_operation_key(key), card_units=1,
                                          created_at=now - timedelta(days=2))
            db.add_all([charge, GenerationJobSource(job_id=job.id, payload=b"encrypted-fixture" * 3,
                                                    nonce=b"0123456789ab", expires_at=now + timedelta(days=7))])
            await db.flush()
            job_id, owner_id, charge_id = job.id, course.owner.id, charge.id
    async with postgres_session_factory() as cleaner:
        async with cleaner.begin():
            await cleanup_retention(cleaner, retention_settings(database_metadata_retention_days=1), dry_run=False)
    service = GenerationJobService(Settings(_env_file=None, flashcard_ai_provider_enabled=True,
                                            generation_source_retry_retention_hours=168,
                                            database_metadata_retention_days=1))
    async with postgres_session_factory() as db:
        async with db.begin():
            assert await db.get(GenerationQuotaEvent, charge_id) is not None
            replayed = await service.retry(db, job_id=job_id, user_id=owner_id, idempotency_key=key)
            assert replayed.status == "failed" and replayed.manual_retry_count == 1
            assert (await db.scalars(select(GenerationQuotaEvent.id).where(
                GenerationQuotaEvent.user_id == owner_id,
                GenerationQuotaEvent.operation_key_hash == hash_operation_key(key),
            ))).all() == [charge_id]
