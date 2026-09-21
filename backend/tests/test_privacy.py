"""Privacy boundary tests without operator data or remote services."""

from datetime import timedelta
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, text

from app.config import Settings
from app.models.audit import AuditEvent
from app.models.email import EmailOutboxMessage
from app.models.flashcard import StudyAnswerSubmission, StudyProgress
from app.models.generation import GenerationJob, GenerationJobSource, GenerationQuotaEvent
from app.models.knowledge import (
    SubjectDocument,
    SubjectDocumentContentRevision,
    SubjectDocumentPage,
)
from app.models.operations import RequestEvent, WorkerHeartbeat
from app.models.rag import RagAnswerJob, RagAnswerQuotaEvent, RagMessage, RagThread
from app.models.subject import Subject
from app.models.user import AuthSession, InviteLink, PasswordResetToken, RateLimitBucket, User
from app.services.privacy import PrivacyOperationError, cleanup_retention, delete_account, export_account
from app.services.generation import GenerationJobService, hash_operation_key
from app.services.subject import SubjectService
from app.time_utils import utcnow
from tests.support.privacy_fixtures import (
    addressed_invite, invitation_email, job_for, retention_settings, seed_private_course,
    seed_rag_job,
)


async def test_export_excludes_other_people_secrets_and_unexpected_receipt_json(db):
    course = await seed_private_course(db)
    db.add(job_for(course))
    await db.commit()
    owner_export = await export_account(db, course.owner.id)
    rendered = json.dumps(owner_export)
    for private in (course.student.email, course.other.email, course.other.full_name,
                    "DO_NOT_EXPORT_PASSWORD", "idempotency_key_hash", "request_fingerprint"):
        assert private not in rendered
    assert len(owner_export["cards"]) == 1
    assert owner_export["progress"] == []
    assert owner_export["enrollments"] == []
    assert len(owner_export["jobs"]) == 1

    student_export = await export_account(db, course.student.id)
    assert student_export["subjects"] == student_export["sets"] == student_export["cards"] == []
    assert len(student_export["progress"]) == len(student_export["answer_receipts"]) == 1
    assert "DO_NOT_EXPORT_RAW_JSON" not in json.dumps(student_export)


async def test_export_includes_only_the_principals_own_rag_conversations(db):
    course = await seed_private_course(db)
    owner_chat = await seed_rag_job(db, course, user=course.owner)
    other_chat = await seed_rag_job(db, course, user=course.other)
    owner_question = owner_chat.question.content
    other_question = other_chat.question.content
    owner_thread_id = owner_chat.thread.id
    other_id = course.other.id
    await db.commit()

    exported = await export_account(db, course.owner.id)
    rendered = json.dumps(exported)
    assert len(exported["rag_threads"]) == len(exported["rag_messages"]) == 1
    assert len(exported["rag_answer_jobs"]) == 1
    assert owner_question in rendered
    assert other_question not in rendered
    assert exported["rag_threads"][0]["id"] == str(owner_thread_id)

    await db.rollback()
    other_export = await export_account(db, other_id)
    other_rendered = json.dumps(other_export)
    assert other_question in other_rendered
    assert owner_question not in other_rendered


async def test_export_includes_owned_knowledge_without_internal_hashes(db):
    course = await seed_private_course(db)
    content_text = "Private durable lecture text."
    content_bytes = len(content_text.encode("utf-8"))
    source_hash = "9" * 64
    document = SubjectDocument(
        subject_id=course.subject.id,
        uploader_id=course.owner.id,
        title="Private lecture",
        source_pdf_name="lecture.pdf",
        source_sha256=source_hash,
    )
    db.add(document)
    await db.flush()
    revision = SubjectDocumentContentRevision(
        document_id=document.id,
        subject_id=course.subject.id,
        uploader_id=course.owner.id,
        revision_no=1,
        source_sha256=source_hash,
        extraction_version="pypdf_bounded_v1",
        status="ready",
        is_active=True,
        reserved_page_count=1,
        reserved_page_chars=len(content_text),
        reserved_page_bytes=content_bytes,
        actual_page_count=1,
        actual_page_chars=len(content_text),
        actual_page_bytes=content_bytes,
    )
    db.add(revision)
    await db.flush()
    db.add(
        SubjectDocumentPage(
            content_revision_id=revision.id,
            document_id=document.id,
            subject_id=course.subject.id,
            uploader_id=course.owner.id,
            page_number=1,
            content=content_text,
        )
    )
    await db.flush()

    exported = await export_account(db, course.owner.id)
    assert exported["knowledge_documents"][0]["title"] == "Private lecture"
    assert exported["knowledge_pages"][0]["content"] == content_text
    rendered = json.dumps(exported)
    assert source_hash not in rendered
    assert "source_sha256" not in rendered
    assert "embedding_space_hash" not in rendered
    assert "embedding_base_url" not in rendered


async def test_missing_accounts_return_fixed_content_free_errors(db):
    for operation in (export_account, delete_account):
        with pytest.raises(PrivacyOperationError) as error:
            await operation(db, uuid4())
        assert error.value.code == "account_not_found"
        assert str(error.value) == "Account was not found."


async def test_delete_refuses_running_generation_without_mutating_account(db):
    course = await seed_private_course(db)
    job = job_for(course, status="running")
    db.add(job)
    await db.commit()
    with pytest.raises(PrivacyOperationError, match="Stop and drain") as error:
        await delete_account(db, course.owner.id)
    assert error.value.code == "account_work_active"
    assert await db.get(User, course.owner.id) is not None
    assert await db.get(GenerationJob, job.id) is not None


async def test_delete_refuses_running_answer_without_mutating_account(db):
    course = await seed_private_course(db)
    rag = await seed_rag_job(db, course, status="running")
    await db.commit()
    with pytest.raises(PrivacyOperationError, match="Stop and drain") as error:
        await delete_account(db, course.student.id)
    assert error.value.code == "account_work_active"
    assert await db.get(User, course.student.id) is not None
    assert await db.get(RagAnswerJob, rag.job.id) is not None


async def test_subject_delete_refuses_running_answer_claim(db):
    course = await seed_private_course(db)
    rag = await seed_rag_job(db, course, status="running")
    await db.commit()
    with pytest.raises(HTTPException) as error:
        await SubjectService.delete_subject(db, course.subject)
    assert getattr(error.value, "detail", {})["code"] == "subject_work_active"
    assert await db.get(Subject, course.subject.id) is not None
    assert await db.get(RagAnswerJob, rag.job.id) is not None


async def test_subject_delete_cascades_queued_answer_without_resurrection(db):
    await db.execute(text("PRAGMA foreign_keys=ON"))
    course = await seed_private_course(db)
    rag = await seed_rag_job(db, course, status="queued")
    subject_id = course.subject.id
    thread_id = rag.thread.id
    job_id = rag.job.id
    owner_id = course.owner.id
    student_id = course.student.id
    await db.commit()

    await SubjectService.delete_subject(db, course.subject)
    await db.commit()
    db.expire_all()
    assert await db.get(Subject, subject_id) is None
    assert await db.get(RagThread, thread_id) is None
    assert await db.get(RagAnswerJob, job_id) is None
    assert await db.get(User, owner_id) is not None
    assert await db.get(User, student_id) is not None


async def test_delete_refuses_related_smtp_claim_without_removing_recipient(db):
    course = await seed_private_course(db)
    invite = addressed_invite(course)
    db.add(invite)
    await db.flush()
    db.add(invitation_email(invite, status="sending"))
    await db.commit()
    with pytest.raises(PrivacyOperationError) as error:
        await delete_account(db, course.student.id)
    assert error.value.code == "account_email_active"
    assert invite.recipient_email == course.student.email


async def test_delete_student_preserves_consumption_and_other_course_records(db):
    await db.execute(text("PRAGMA foreign_keys=ON"))
    course = await seed_private_course(db)
    consumed = addressed_invite(course)
    unused = addressed_invite(course, consumed=False)
    db.add_all([consumed, unused])
    await db.flush()
    db.add_all([invitation_email(consumed), invitation_email(unused)])
    await db.commit()
    ids = SimpleNamespace(student=course.student.id, subject=course.subject.id,
                          consumed=consumed.id, unused=unused.id, other=course.other.id)
    original_used_at = consumed.used_at
    result = await delete_account(db, ids.student)
    assert result["email_events"] == 2
    await db.commit()
    db.expire_all()
    assert await db.get(User, ids.student) is None
    assert await db.get(Subject, ids.subject) is not None
    assert await db.get(User, ids.other) is not None
    remaining = await db.get(InviteLink, ids.consumed)
    assert remaining.used_by is None and remaining.used_at is not None
    assert remaining.recipient_email is None
    assert remaining.used_at.replace(tzinfo=original_used_at.tzinfo) == original_used_at
    assert await db.get(InviteLink, ids.unused) is None
    assert await db.scalar(select(func.count()).select_from(EmailOutboxMessage)) == 0
    assert await db.scalar(select(func.count()).select_from(StudyProgress)) == 1
    assert await db.scalar(select(func.count()).select_from(StudyAnswerSubmission)) == 0


async def test_account_deletion_rolls_back_with_its_recipient_cleanup(db):
    await db.execute(text("PRAGMA foreign_keys=ON"))
    course = await seed_private_course(db)
    invite = addressed_invite(course)
    db.add(invite)
    await db.commit()
    account_id, invite_id, email = course.student.id, invite.id, course.student.email
    await delete_account(db, account_id)
    await db.rollback()
    assert await db.get(User, account_id) is not None
    assert (await db.get(InviteLink, invite_id)).recipient_email == email


async def test_retention_dry_run_and_apply_preserve_sources_active_data_and_windows(db):
    await db.execute(text("PRAGMA foreign_keys=ON"))
    course = await seed_private_course(db)
    now = utcnow()
    old = now - timedelta(days=120)
    eligible = job_for(course, status="completed")
    with_source = job_for(course)
    active = job_for(course, status="queued")
    recent = job_for(course, age_days=1)
    db.add_all([eligible, with_source, active, recent])
    await db.flush()
    db.add(GenerationJobSource(job_id=with_source.id, payload=b"encrypted-fixture" * 3,
                               nonce=b"0123456789ab", expires_at=now + timedelta(hours=1)))
    db.add_all([
        GenerationQuotaEvent(user_id=course.owner.id, job_id=eligible.id,
                             operation_key_hash="f" * 64, card_units=1, created_at=now),
        GenerationQuotaEvent(user_id=course.owner.id, operation_key_hash="0" * 64,
                             card_units=1, created_at=old),
        RateLimitBucket(scope="login", key_hash="1" * 64, window_started_at=now, updated_at=now),
        RateLimitBucket(scope="login", key_hash="2" * 64, window_started_at=old, updated_at=old),
        AuthSession(user_id=course.student.id, refresh_jti_hash="3" * 64, expires_at=old),
        AuthSession(user_id=course.student.id, refresh_jti_hash="4" * 64, expires_at=now + timedelta(days=1)),
        RequestEvent(id=uuid4(), route="/study/{id}", method="POST", status_code=200,
                     latency_milliseconds=10, created_at=old),
        WorkerHeartbeat(worker_id="old", kind="generation", status="running", last_seen_at=old),
        WorkerHeartbeat(worker_id="new", kind="email", status="running", last_seen_at=now),
        AuditEvent(action="card.approved", actor_kind="user", actor_id=course.owner.id,
                   target_type="card", target_id=course.card.id, created_at=old),
    ])
    retained_set = course.card_set
    retained_set.generation_job_id = eligible.id
    await db.commit()
    eligible_id, source_job_id, active_id, recent_id = eligible.id, with_source.id, active.id, recent.id
    set_id = retained_set.id
    counts = await cleanup_retention(db, retention_settings())
    assert counts["generation_jobs"] == counts["generation_quota_events"] == counts["rate_limit_buckets"] == 1
    assert counts["request_events"] == counts["audit_events"] == counts["worker_heartbeats"] == 1
    assert await db.get(GenerationJob, eligible_id) is not None
    await db.rollback()
    applied = await cleanup_retention(db, retention_settings(), dry_run=False)
    assert applied == counts
    await db.commit()
    db.expire_all()
    assert await db.get(GenerationJob, eligible_id) is None
    for identity in (source_job_id, active_id, recent_id):
        assert await db.get(GenerationJob, identity) is not None
    from app.models.subject import FlashcardSet
    assert (await db.get(FlashcardSet, set_id)).generation_job_id is None
    assert await db.scalar(select(func.count()).select_from(GenerationQuotaEvent)) == 1
    assert await db.scalar(select(func.count()).select_from(RateLimitBucket)) == 1
    assert await db.scalar(select(func.count()).select_from(StudyProgress)) == 2
    assert await db.scalar(select(func.count()).select_from(StudyAnswerSubmission)) == 1


async def test_rag_retention_deletes_question_job_then_answer_thread_and_detached_quota(db):
    await db.execute(text("PRAGMA foreign_keys=ON"))
    course = await seed_private_course(db)
    rag = await seed_rag_job(db, course, status="completed", expired=True)
    quota = RagAnswerQuotaEvent(
        user_id=course.student.id,
        job_id=rag.job.id,
        operation_key_hash=uuid4().hex * 2,
        created_at=utcnow() - timedelta(days=120),
    )
    db.add(quota)
    await db.commit()
    ids = SimpleNamespace(
        thread=rag.thread.id,
        question=rag.question.id,
        answer=rag.answer.id,
        job=rag.job.id,
        quota=quota.id,
    )

    dry_run = await cleanup_retention(db, retention_settings())
    assert dry_run["rag_question_messages"] == 1
    assert dry_run["rag_assistant_messages"] == 0
    assert dry_run["rag_threads"] == 0
    assert dry_run["rag_answer_quota_events"] == 0
    await db.rollback()

    applied = await cleanup_retention(db, retention_settings(), dry_run=False)
    assert applied["rag_question_messages"] == 1
    assert applied["rag_assistant_messages"] == 1
    assert applied["rag_threads"] == 1
    assert applied["rag_answer_quota_events"] == 1
    await db.commit()
    for model, identity in (
        (RagMessage, ids.question),
        (RagMessage, ids.answer),
        (RagAnswerJob, ids.job),
        (RagThread, ids.thread),
        (RagAnswerQuotaEvent, ids.quota),
    ):
        assert await db.get(model, identity) is None


async def test_retention_is_bounded_and_keeps_reset_invite_email_dependencies(db):
    course = await seed_private_course(db)
    now = utcnow()
    old = now - timedelta(days=120)
    reset = PasswordResetToken(user_id=course.student.id, created_at=old,
                                expires_at=old + timedelta(hours=1))
    invite = InviteLink(code=uuid4().hex[:20], instructor_id=course.owner.id,
                        subject_id=course.subject.id, recipient_email=course.student.email,
                        created_at=old, expires_at=old + timedelta(hours=24),
                        used_at=old, used_by=course.student.id)
    db.add_all([reset, invite])
    await db.flush()
    # Even terminal outbox history is retained until the email worker removes it.
    db.add(invitation_email(invite, status="pending"))
    db.add(EmailOutboxMessage(message_type="password_reset", recipient_email=course.student.email,
                             message_id=f"{uuid4().hex}@example.test", idempotency_key_hash="5" * 64,
                             expires_at=now + timedelta(hours=1), password_reset_token_id=reset.id))
    for index in range(3):
        db.add(RequestEvent(id=uuid4(), route="/health/live", method="GET", status_code=200,
                            latency_milliseconds=index, created_at=old))
    await db.commit()
    counts = await cleanup_retention(db, retention_settings(retention_batch_size=2), dry_run=False)
    assert counts["request_events"] == 2
    assert counts["password_reset_tokens"] == counts["invite_links"] == 0
    await db.commit()
    assert await db.scalar(select(func.count()).select_from(RequestEvent)) == 1


async def test_short_metadata_grace_cannot_forget_a_retained_manual_retry_receipt(db):
    course = await seed_private_course(db)
    now = utcnow()
    job = job_for(course, age_days=2)
    job.error_retryable = True
    job.manual_retry_count = 1
    db.add(job)
    await db.flush()
    key = f"retained-manual-retry-{uuid4().hex}"
    charge = GenerationQuotaEvent(user_id=course.owner.id, job_id=job.id,
                                  operation_key_hash=hash_operation_key(key), card_units=1,
                                  created_at=now - timedelta(days=2))
    db.add_all([charge, GenerationJobSource(job_id=job.id, payload=b"encrypted-fixture" * 3,
                                            nonce=b"0123456789ab", expires_at=now + timedelta(days=7))])
    await db.commit()
    job_id, owner_id, charge_id = job.id, course.owner.id, charge.id
    counts = await cleanup_retention(db, retention_settings(database_metadata_retention_days=1), dry_run=False)
    assert counts["generation_quota_events"] == 0
    await db.commit()
    db.expire_all()
    assert await db.get(GenerationQuotaEvent, charge_id) is not None
    service = GenerationJobService(Settings(_env_file=None, flashcard_ai_provider_enabled=True,
                                            generation_source_retry_retention_hours=168,
                                            database_metadata_retention_days=1))
    replayed = await service.retry(db, job_id=job_id, user_id=owner_id, idempotency_key=key)
    assert replayed.status == "failed" and replayed.manual_retry_count == 1
    assert await db.scalar(select(func.count()).select_from(GenerationQuotaEvent)) == 1
