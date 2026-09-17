"""Authored private-record fixtures shared by offline and disposable DB tests."""

from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.models.email import EmailOutboxMessage
from app.models.flashcard import Enrollment, Flashcard, StudyAnswerSubmission, StudyProgress
from app.models.generation import GenerationJob
from app.models.subject import FlashcardSet, Subject
from app.models.user import InviteLink, User, UserRole
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
