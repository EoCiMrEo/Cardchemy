"""Deployed PostgreSQL audit integrity, role triggers and deletion behavior."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, update

from app.models.audit import AuditAction, AuditEvent
from app.models.flashcard import Flashcard
from app.models.subject import FlashcardSet, Subject
from app.models.user import User, UserRole
from app.routers.flashcards import update_flashcard
from app.schemas.flashcard import FlashcardUpdate
from app.services.audit import AuditService

pytestmark = pytest.mark.postgres


async def test_role_updates_are_audited_atomically_including_direct_sql(postgres_session_factory):
    account_id = uuid4()
    async with postgres_session_factory() as db:
        try:
            db.add(User(id=account_id, email=f"audit-role-{account_id.hex}@example.test", hashed_password="unused", role=UserRole.STUDENT))
            await db.commit()
            await db.execute(update(User).where(User.id == account_id).values(role=UserRole.INSTRUCTOR))
            event = await db.scalar(select(AuditEvent).where(AuditEvent.target_id == account_id))
            assert event.action == "account.role_changed"
            assert event.actor_kind == "operator_database"
            assert event.actor_id is None
            assert (event.role_before, event.role_after) == ("student", "instructor")
            await db.rollback()
            assert await db.scalar(select(AuditEvent.id).where(AuditEvent.target_id == account_id)) is None
            await db.execute(update(User).where(User.id == account_id).values(role=UserRole.INSTRUCTOR))
            await db.commit()
            await db.execute(update(User).where(User.id == account_id).values(role=UserRole.INSTRUCTOR))
            await db.commit()
            records = list((await db.scalars(select(AuditEvent).where(AuditEvent.target_id == account_id))).all())
            assert len(records) == 1
        finally:
            await db.rollback()
            await db.execute(delete(User).where(User.id == account_id))
            await db.execute(delete(AuditEvent).where(AuditEvent.target_id == account_id))
            await db.commit()


async def test_concurrent_card_approval_records_one_actual_transition(postgres_session_factory):
    actor_id, subject_id, set_id, card_id = uuid4(), uuid4(), uuid4(), uuid4()
    async with postgres_session_factory() as db:
        db.add_all([
            User(id=actor_id, email=f"audit-race-{actor_id.hex}@example.test", hashed_password="unused", role=UserRole.INSTRUCTOR),
            Subject(id=subject_id, name="Audit concurrency", instructor_id=actor_id),
            FlashcardSet(id=set_id, subject_id=subject_id, title="Review", is_published=False),
            Flashcard(id=card_id, set_id=set_id, front_content="Q", back_content="A", options=["A", "B", "C", "D"], card_type="multiple_choice", is_approved=False),
        ])
        await db.commit()

    async def approve():
        async with postgres_session_factory() as db:
            actor = await db.get(User, actor_id)
            await update_flashcard(card_id, FlashcardUpdate(is_approved=True), actor, db)

    try:
        await asyncio.wait_for(asyncio.gather(approve(), approve()), timeout=10)
        async with postgres_session_factory() as db:
            records = list((await db.scalars(select(AuditEvent).where(AuditEvent.target_id == card_id))).all())
            assert len(records) == 1
            assert records[0].action == "card.approved"
            assert records[0].state_before is False and records[0].state_after is True
    finally:
        async with postgres_session_factory() as db:
            await db.execute(delete(User).where(User.id == actor_id))
            await db.execute(delete(AuditEvent).where(AuditEvent.target_id == card_id))
            await db.commit()


async def test_actor_deletion_nulls_identity_preserving_opaque_resource_audit(postgres_session_factory):
    actor_id, target_id = uuid4(), uuid4()
    async with postgres_session_factory() as db:
        try:
            db.add(User(id=actor_id, email=f"audit-delete-{actor_id.hex}@example.test", hashed_password="unused", role=UserRole.INSTRUCTOR))
            await db.flush()
            event = AuditService.record(db, action=AuditAction.CARD_APPROVED, actor_id=actor_id, target_type="card", target_id=target_id)
            await db.commit()
            event_id = event.id
            await db.execute(delete(User).where(User.id == actor_id))
            await db.commit()
            db.expire_all()
            surviving = await db.get(AuditEvent, event_id)
            assert surviving.actor_id is None
            assert surviving.target_id == target_id
            assert surviving.action == "card.approved"
        finally:
            await db.rollback()
            await db.execute(delete(User).where(User.id == actor_id))
            await db.execute(delete(AuditEvent).where(AuditEvent.target_id == target_id))
            await db.commit()
