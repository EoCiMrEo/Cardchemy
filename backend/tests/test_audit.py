"""Privileged audit records share domain commits and accept no free-form data."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.audit import AuditAction, AuditEvent
from app.models.flashcard import Flashcard
from app.models.subject import FlashcardSet, Subject
from app.models.user import InviteLink, User, UserRole
from app.routers import flashcards, subjects
from app.schemas.flashcard import FlashcardCreateRequest, FlashcardUpdate
from app.schemas.subject import FlashcardSetUpdate
from app.schemas.user import UserCreate
from app.services.audit import AuditService
from app.services.auth import AuthService


async def seed(db):
    owner = User(id=uuid4(), email="audit-owner@example.test", hashed_password="unused", role=UserRole.INSTRUCTOR)
    other = User(id=uuid4(), email="audit-other@example.test", hashed_password="unused", role=UserRole.INSTRUCTOR)
    subject = Subject(id=uuid4(), name="Private lecture title", instructor_id=owner.id)
    fset = FlashcardSet(id=uuid4(), subject_id=subject.id, title="Private set title", is_published=False)
    card = Flashcard(
        id=uuid4(), set_id=fset.id, front_content="Private question", back_content="Answer",
        options=["Answer", "B", "C", "D"], card_type="multiple_choice", is_approved=False,
    )
    db.add_all([owner, other, subject, fset, card])
    await db.commit()
    return owner, other, subject, fset, card


async def events(db):
    return list((await db.scalars(select(AuditEvent).order_by(AuditEvent.created_at, AuditEvent.id))).all())


async def test_invitation_and_audit_rollback_together(db):
    owner, _, subject, _, _ = await seed(db)
    invite, _ = await AuthService.create_invitation(db, owner.id, subject.id, 24, "private-recipient@example.test")
    invite_id = invite.id
    await db.flush()
    event = (await events(db))[0]
    assert event.action == AuditAction.INVITATION_CREATED.value
    assert event.target_id == invite_id
    assert event.actor_id == owner.id
    await db.rollback()
    assert await db.get(InviteLink, invite_id) is None
    assert await events(db) == []


async def test_instructor_provisioning_is_audited_but_student_signup_is_not_privileged(db):
    owner = await AuthService.create_user(
        db, UserCreate(email="operator-created@example.com", password="private password"), UserRole.INSTRUCTOR,
    )
    await db.commit()
    event = (await events(db))[0]
    assert (event.action, event.actor_kind, event.actor_id) == ("account.instructor_provisioned", "operator", None)
    assert event.target_id == owner.id
    assert event.role_after == "instructor"
    await AuthService.create_user(
        db, UserCreate(email="student@example.com", password="private password"), UserRole.STUDENT,
    )
    await db.commit()
    assert len(await events(db)) == 1


async def test_manual_approval_and_transitions_exclude_card_contents_and_noops(db):
    owner, _, subject, fset, _ = await seed(db)
    card = await flashcards.create_flashcard(
        fset.id, FlashcardCreateRequest(front_content="Private manual question", back_content="A", options=["A", "B", "C", "D"]), owner, db,
    )
    await flashcards.update_flashcard(card.id, FlashcardUpdate(is_approved=True), owner, db)
    await flashcards.update_flashcard(card.id, FlashcardUpdate(is_approved=False), owner, db)
    await flashcards.update_flashcard(card.id, FlashcardUpdate(is_approved=True), owner, db)
    audit = await events(db)
    assert [event.action for event in audit] == ["card.approved", "card.unapproved", "card.approved"]
    assert all(event.actor_id == owner.id and event.subject_id == subject.id for event in audit)
    assert [(event.state_before, event.state_after) for event in audit] == [(False, True), (True, False), (False, True)]
    assert all(event.target_id == card.id for event in audit)
    fields = set(AuditEvent.__table__.columns.keys())
    assert fields == {
        "id", "action", "actor_kind", "actor_id", "target_type", "target_id", "subject_id", "request_id",
        "state_before", "state_after", "affected_count", "role_before", "role_after", "created_at",
    }


async def test_bulk_approval_and_publication_only_record_changes(db):
    owner, _, subject, fset, _ = await seed(db)
    assert (await flashcards.approve_all_flashcards(fset.id, owner, db))["approved_count"] == 1
    assert (await flashcards.approve_all_flashcards(fset.id, owner, db))["approved_count"] == 0
    await subjects.update_flashcard_set(subject.id, fset.id, FlashcardSetUpdate(is_published=True), owner, db)
    await subjects.update_flashcard_set(subject.id, fset.id, FlashcardSetUpdate(is_published=True), owner, db)
    await subjects.update_flashcard_set(subject.id, fset.id, FlashcardSetUpdate(is_published=False), owner, db)
    audit = await events(db)
    assert [event.action for event in audit] == ["cards.approved", "set.published", "set.unpublished"]
    assert audit[0].affected_count == 1
    assert audit[1].state_before is False and audit[1].state_after is True
    assert audit[2].state_before is True and audit[2].state_after is False


async def test_denied_or_invalid_privileged_mutations_leave_no_audit(db):
    owner, other, subject, fset, card = await seed(db)
    with pytest.raises(HTTPException) as denied:
        await flashcards.update_flashcard(card.id, FlashcardUpdate(is_approved=True), other, db)
    assert denied.value.status_code == 403
    with pytest.raises(HTTPException) as unpublished:
        await subjects.update_flashcard_set(subject.id, fset.id, FlashcardSetUpdate(is_published=True), owner, db)
    assert unpublished.value.status_code == 409
    assert await events(db) == []


async def test_audit_failure_rolls_back_approved_card(db, monkeypatch):
    owner, _, _, fset, _ = await seed(db)
    set_id = fset.id
    initial = await db.scalar(select(func.count(Flashcard.id)))

    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(AuditService, "record", fail)
    with pytest.raises(RuntimeError):
        await flashcards.create_flashcard(
            set_id, FlashcardCreateRequest(front_content="Q", back_content="A", options=["A", "B", "C", "D"]), owner, db,
        )
    await db.rollback()
    assert await db.scalar(select(func.count(Flashcard.id))) == initial
    assert await events(db) == []


async def test_audit_correlates_server_request_and_rejects_untrusted_metadata(db, monkeypatch):
    import app.observability

    request_id = uuid4()
    monkeypatch.setattr(app.observability, "current_request_id", lambda: request_id)
    event = AuditService.record(db, action=AuditAction.ACCOUNT_DELETED, actor_kind="operator", target_type="account", target_id=uuid4())
    assert event.request_id == request_id
    with pytest.raises(ValueError):
        AuditService.record(db, action="private document", target_type="account", target_id=uuid4())
    with pytest.raises(ValueError):
        AuditService.record(db, action=AuditAction.ACCOUNT_ROLE_CHANGED, target_type="account", target_id=uuid4(), role_after="private provider response")
    with pytest.raises(TypeError):
        AuditService.record(db, action=AuditAction.INVITATION_CREATED, target_type="invitation", target_id=uuid4(), recipient_email="private@example.test")
