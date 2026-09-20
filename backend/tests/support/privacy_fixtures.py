"""Authored private-record fixtures shared by offline and disposable DB tests."""

from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.models.email import EmailOutboxMessage
from app.models.flashcard import Enrollment, Flashcard, StudyAnswerSubmission, StudyProgress
from app.models.generation import GenerationJob
from app.models.rag import RagAnswerJob, RagMessage, RagThread
from app.models.subject import FlashcardSet, Subject
from app.models.user import AuthSession, InviteLink, User, UserRole
from app.time_utils import utcnow


def retention_settings(**overrides):
    values = dict(request_retention_days=7, generation_job_retention_days=30,
                  database_metadata_retention_days=30, audit_retention_days=90,
                  retention_batch_size=500)
    return SimpleNamespace(**(values | overrides))


async def seed_private_course(db):
    nonce = uuid4().hex
    owner = User(email=f"owner-{nonce}@example.test", role=UserRole.INSTRUCTOR,
                 full_name="Authored owner", hashed_password="DO_NOT_EXPORT_PASSWORD")
    student = User(email=f"student-{nonce}@example.test", role=UserRole.STUDENT,
                   full_name="Authored student", hashed_password="DO_NOT_EXPORT_PASSWORD")
    other = User(email=f"other-{nonce}@example.test", role=UserRole.STUDENT,
                 full_name="OTHER_PRIVATE_NAME", hashed_password="DO_NOT_EXPORT_PASSWORD")
    db.add_all([owner, student, other])
    await db.flush()
    subject = Subject(name="Authored course", instructor_id=owner.id)
    db.add(subject)
    await db.flush()
    card_set = FlashcardSet(subject_id=subject.id, title="Authored set")
    db.add(card_set)
    await db.flush()
    card = Flashcard(set_id=card_set.id, front_content="Authored fact?", back_content="A",
                     options=["A", "B", "C", "D"], is_approved=True)
    db.add(card)
    await db.flush()
    db.add_all([
        Enrollment(student_id=student.id, subject_id=subject.id),
        Enrollment(student_id=other.id, subject_id=subject.id),
        StudyProgress(student_id=student.id, flashcard_id=card.id),
        StudyProgress(student_id=other.id, flashcard_id=card.id),
        StudyAnswerSubmission(student_id=student.id, flashcard_id=card.id,
                              idempotency_key_hash="a" * 64, request_fingerprint="b" * 64,
                              response_payload={"is_correct": True, "quality": 5,
                                                "correct_option": "A", "correct_option_index": 0,
                                                "unexpected": "DO_NOT_EXPORT_RAW_JSON"}),
    ])
    await db.flush()
    return SimpleNamespace(owner=owner, student=student, other=other, subject=subject,
                           card_set=card_set, card=card)


async def seed_rag_job(db, course, *, user=None, status="queued", expired=False):
    """Create a content-bounded private conversation and optional active job."""
    principal = user or course.student
    now = utcnow()
    created_at = now - timedelta(days=100) if expired else now
    expires_at = now - timedelta(days=10) if expired else now + timedelta(days=90)
    auth = AuthSession(
        user_id=principal.id,
        refresh_jti_hash=uuid4().hex * 2,
        created_at=created_at,
        last_used_at=created_at,
        expires_at=now + timedelta(days=1),
    )
    thread = RagThread(
        user_id=principal.id,
        subject_id=course.subject.id,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add_all([auth, thread])
    await db.flush()
    question = RagMessage(
        thread_id=thread.id,
        user_id=principal.id,
        subject_id=course.subject.id,
        role="user",
        content=f"private-question-{uuid4().hex}",
        created_at=created_at,
        expires_at=expires_at,
    )
    db.add(question)
    await db.flush()
    answer = None
    if status == "completed":
        answer = RagMessage(
            thread_id=thread.id,
            user_id=principal.id,
            subject_id=course.subject.id,
            role="assistant",
            outcome="abstained",
            content="The available course materials do not support an answer.",
            source_count=0,
            corpus_revision=course.subject.corpus_revision,
            embedding_space_hash="e" * 64,
            created_at=created_at + timedelta(seconds=1),
            expires_at=expires_at,
        )
        db.add(answer)
        await db.flush()
    values = dict(
        thread_id=thread.id,
        question_message_id=question.id,
        auth_session_id=auth.id,
        user_id=principal.id,
        subject_id=course.subject.id,
        status="queued",
        operation_key_hash=uuid4().hex * 2,
        request_fingerprint=uuid4().hex * 2,
        document_ids=[],
        corpus_revision=course.subject.corpus_revision,
        retrieval_policy="hybrid_exact_v1",
        embedding_space_hash="e" * 64,
        ai_provider="test",
        ai_base_url="https://provider.invalid/v1",
        ai_model="test-model",
        available_at=created_at,
        deadline_at=created_at + timedelta(minutes=10),
        created_at=created_at,
        updated_at=created_at,
    )
    job = RagAnswerJob(**values)
    db.add(job)
    await db.flush()
    if status in {"running", "completed"}:
        # PostgreSQL intentionally permits only queued inserts. Reproduce the
        # real durable state machine so this shared fixture exercises its guard
        # instead of bypassing it on SQLite.
        job.status = "running"
        job.attempt_count = 1
        job.worker_id = "answer-test-worker"
        job.claim_token = "f" * 64
        job.heartbeat_at = created_at
        job.lease_expires_at = created_at + timedelta(minutes=1)
        await db.flush()
    if status == "completed":
        job.status = "completed"
        job.answer_message_id = answer.id
        job.completed_at = created_at + timedelta(minutes=1)
        job.worker_id = None
        job.claim_token = None
        job.heartbeat_at = None
        job.lease_expires_at = None
        await db.flush()
    return SimpleNamespace(
        auth=auth,
        thread=thread,
        question=question,
        answer=answer,
        job=job,
        principal=principal,
    )


def job_for(course, *, status="failed", age_days=40):
    now = utcnow()
    values = dict(user_id=course.owner.id, subject_id=course.subject.id,
                  idempotency_key_hash=uuid4().hex * 2, request_fingerprint="c" * 64,
                  status=status, set_title="Authored job", requested_card_count=1,
                  source_pdf_name="authored.pdf", progress=100 if status != "running" else 20,
                  created_at=now - timedelta(days=age_days),
                  completed_at=now - timedelta(days=age_days) if status in ("completed", "failed", "cancelled") else None,
                  generated_card_count=1 if status == "completed" else None)
    if status == "running":
        values.update(worker_id="fixture-worker", claim_token="d" * 64,
                      lease_expires_at=now + timedelta(minutes=2))
    return GenerationJob(**values)


def addressed_invite(course, *, consumed=True):
    now = utcnow()
    return InviteLink(code=uuid4().hex[:20], instructor_id=course.owner.id,
                      subject_id=course.subject.id, created_at=now,
                      expires_at=now + timedelta(hours=24),
                      used_at=now if consumed else None,
                      used_by=course.student.id if consumed else None,
                      recipient_email=course.student.email)


def invitation_email(invite, *, status="pending"):
    now = utcnow()
    values = dict(message_type="student_invitation", recipient_email=invite.recipient_email,
                  message_id=f"fixture-{uuid4().hex}@example.test", idempotency_key_hash=uuid4().hex * 2,
                  status=status, available_at=now, expires_at=now + timedelta(hours=2),
                  invite_link_id=invite.id)
    if status == "sending":
        values.update(worker_id="fixture-email", claim_token="e" * 64,
                      claimed_at=now, lease_expires_at=now + timedelta(minutes=2))
    return EmailOutboxMessage(**values)
