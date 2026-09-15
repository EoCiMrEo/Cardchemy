"""PostgreSQL-only proof for the Phase 2 schema and transaction contract."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.flashcard import Enrollment, Flashcard, StudyProgress
from app.models.subject import FlashcardSet, Subject
from app.models.user import AuthSession, InviteLink, PasswordResetToken, User, UserRole
from app.schemas.flashcard import StudyProgressUpdate
from app.services.auth import AuthService
from app.services.flashcard import FlashcardService
from app.time_utils import utcnow


pytestmark = pytest.mark.postgres


@pytest_asyncio.fixture
async def pg_session_factory():
    database_url = os.getenv("POSTGRES_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL is not configured")
    engine = create_async_engine(database_url, pool_size=8, max_overflow=0)
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != "20260914_0003":
            pytest.fail(f"PostgreSQL test database is at Alembic revision {revision!r}")
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


@dataclass(frozen=True)
class SeededCourse:
    owner_id: UUID
    student_id: UUID
    subject_id: UUID
    set_id: UUID
    card_ids: tuple[UUID, ...]


async def seed_course(
    factory: async_sessionmaker[AsyncSession],
    *,
    card_count: int = 1,
    published: bool = False,
) -> SeededCourse:
    nonce = uuid4().hex
    owner = User(
        email=f"owner-{nonce}@example.test",
        hashed_password="not-a-real-password-hash",
        full_name="Owner",
        role=UserRole.INSTRUCTOR,
    )
    student = User(
        email=f"student-{nonce}@example.test",
        hashed_password="not-a-real-password-hash",
        full_name="Student",
        role=UserRole.STUDENT,
    )
    subject = Subject(name="Integrity", description="PostgreSQL proof", instructor=owner)
    flashcard_set = FlashcardSet(subject=subject, title="Phase 2", is_published=False)
    cards = [
        Flashcard(
            flashcard_set=flashcard_set,
            front_content=f"Question {index}",
            back_content="Canonical Answer",
            options=["Canonical Answer", "Distractor B", "Distractor C", f"Distractor {index} D"],
            card_type="multiple_choice",
            quality_score=0.75,
            is_approved=True,
        )
        for index in range(card_count)
    ]
    enrollment = Enrollment(student=student, subject=subject)

    async with factory() as session:
        async with session.begin():
            session.add_all([owner, student, subject, flashcard_set, enrollment, *cards])
            await session.flush()
            if published:
                flashcard_set.is_published = True
                await session.flush()

    return SeededCourse(
        owner_id=owner.id,
        student_id=student.id,
        subject_id=subject.id,
        set_id=flashcard_set.id,
        card_ids=tuple(card.id for card in cards),
    )


async def assert_rejected(factory: async_sessionmaker[AsyncSession], instance: object) -> None:
    async with factory() as session:
        session.add(instance)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


async def test_concurrent_same_student_invitation_replay_is_idempotent(pg_session_factory):
    nonce = uuid4().hex
    owner = User(
        email=f"invite-owner-{nonce}@example.test",
        hashed_password="not-a-real-password-hash",
        role=UserRole.INSTRUCTOR,
    )
    student = User(
        email=f"invite-student-{nonce}@example.test",
        hashed_password="not-a-real-password-hash",
        role=UserRole.STUDENT,
    )
    subject = Subject(name="Invitation locking", instructor=owner)
    async with pg_session_factory() as session:
        async with session.begin():
            session.add_all([owner, student, subject])
            await session.flush()
            _, token = await AuthService.create_invitation(
                session,
                owner.id,
                subject.id,
                24,
            )
            student_id = student.id
            subject_id = subject.id

    async def accept_once() -> UUID:
        async with pg_session_factory() as session:
            async with session.begin():
                actor = await session.get(User, student_id)
                assert actor is not None
                invite = await AuthService.consume_invitation(session, token, actor)
                return invite.id

    first, second = await asyncio.gather(accept_once(), accept_once())
    assert first == second
    async with pg_session_factory() as session:
        enrollment_count = await session.scalar(
            select(func.count(Enrollment.id)).where(
                Enrollment.student_id == student_id,
                Enrollment.subject_id == subject_id,
            )
        )
    assert enrollment_count == 1


async def test_migration_installs_timestamptz_constraints_and_indexes(pg_session_factory):
    async with pg_session_factory() as session:
        timestamp_columns = set(
            (await session.execute(text(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND data_type = 'timestamp with time zone'
                """
            ))).all()
        )
        expected_timestamp_columns = {
            ("users", "created_at"),
            ("study_progress", "next_review"),
            ("study_progress", "last_reviewed"),
            ("invite_links", "expires_at"),
            ("auth_sessions", "expires_at"),
        }
        assert expected_timestamp_columns <= timestamp_columns

        indexes = set(
            (await session.scalars(text(
                "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"
            ))).all()
        )
        assert {
            "uq_users_email_normalized",
            "ix_flashcards_approved_due_source",
            "ix_study_progress_student_due",
            "ix_invite_links_subject_id",
        } <= indexes


async def test_database_rejects_invalid_bounds_and_flashcards(pg_session_factory):
    course = await seed_course(pg_session_factory)
    now = utcnow()

    await assert_rejected(
        pg_session_factory,
        Subject(name=" ", instructor_id=course.owner_id),
    )
    await assert_rejected(
        pg_session_factory,
        FlashcardSet(subject_id=course.subject_id, title="Too fast", time_limit=4),
    )
    await assert_rejected(
        pg_session_factory,
        FlashcardSet(subject_id=course.subject_id, title=" "),
    )
    await assert_rejected(
        pg_session_factory,
        InviteLink(
            code=uuid4().hex[:20],
            instructor_id=course.owner_id,
            subject_id=course.subject_id,
            created_at=now,
            expires_at=now + timedelta(minutes=59),
        ),
    )
    await assert_rejected(
        pg_session_factory,
        InviteLink(
            code=uuid4().hex[:20],
            instructor_id=course.owner_id,
            subject_id=course.subject_id,
            created_at=now,
            expires_at=now + timedelta(hours=721),
        ),
    )
    await assert_rejected(
        pg_session_factory,
        Flashcard(
            set_id=course.set_id,
            front_content=" ",
            back_content="A",
            options=["A", "B", "C", "D"],
            card_type="multiple_choice",
            quality_score=0.5,
        ),
    )
    await assert_rejected(
        pg_session_factory,
        Flashcard(
            set_id=course.set_id,
            front_content="Duplicate options",
            back_content="Alpha",
            options=["Alpha", " alpha ", "Beta", "Gamma"],
            card_type="multiple_choice",
            quality_score=0.5,
        ),
    )
    await assert_rejected(
        pg_session_factory,
        Flashcard(
            set_id=course.set_id,
            front_content="Missing answer",
            back_content="Not present",
            options=["A", "B", "C", "D"],
            card_type="multiple_choice",
            quality_score=0.5,
        ),
    )
    await assert_rejected(
        pg_session_factory,
        Flashcard(
            set_id=course.set_id,
            front_content="Bad confidence",
            back_content="A",
            options=["A", "B", "C", "D"],
            card_type="multiple_choice",
            quality_score=1.01,
        ),
    )


async def test_publish_trigger_preserves_at_least_one_approved_card(pg_session_factory):
    course = await seed_course(pg_session_factory, card_count=0)

    async with pg_session_factory() as session:
        flashcard_set = await session.get(FlashcardSet, course.set_id)
        flashcard_set.is_published = True
        with pytest.raises(IntegrityError, match="approved card"):
            await session.commit()
        await session.rollback()

    async with pg_session_factory() as session:
        async with session.begin():
            flashcard_set = await session.get(FlashcardSet, course.set_id)
            card = Flashcard(
                set_id=course.set_id,
                front_content="Publishable question",
                back_content="A",
                options=["A", "B", "C", "D"],
                card_type="multiple_choice",
                quality_score=1,
                is_approved=True,
            )
            session.add(card)
            await session.flush()
            flashcard_set.is_published = True
            await session.flush()
            card_id = card.id

    async with pg_session_factory() as session:
        card = await session.get(Flashcard, card_id)
        await session.delete(card)
        with pytest.raises(IntegrityError, match="final approved card"):
            await session.commit()
        await session.rollback()

    async with pg_session_factory() as session:
        async with session.begin():
            flashcard_set = await session.get(FlashcardSet, course.set_id)
            flashcard_set.is_published = False
            await session.flush()
            card = await session.get(Flashcard, card_id)
            await session.delete(card)


async def test_account_and_subject_graph_cascades_preserve_invite_history(pg_session_factory):
    course = await seed_course(pg_session_factory, published=True)
    nonce = uuid4().hex
    consumer = User(
        email=f"consumer-{nonce}@example.test",
        hashed_password="not-a-real-password-hash",
        role=UserRole.STUDENT,
    )
    now = utcnow()

    async with pg_session_factory() as session:
        async with session.begin():
            session.add(consumer)
            await session.flush()
            invite = InviteLink(
                code=nonce[:20],
                instructor_id=course.owner_id,
                subject_id=course.subject_id,
                created_at=now,
                expires_at=now + timedelta(hours=24),
                used_by=consumer.id,
                used_at=now,
            )
            progress = StudyProgress(
                student_id=course.student_id,
                flashcard_id=course.card_ids[0],
                status="learning",
                interval_days=1,
                last_reviewed=now,
                next_review=now + timedelta(days=1),
            )
            auth_session = AuthSession(
                user_id=course.owner_id,
                refresh_jti_hash="a" * 64,
                expires_at=now + timedelta(days=1),
            )
            reset_token = PasswordResetToken(
                user_id=course.owner_id,
                expires_at=now + timedelta(hours=1),
            )
            session.add_all([invite, progress, auth_session, reset_token])
            await session.flush()
            invite_id = invite.id
            auth_session_id = auth_session.id
            reset_token_id = reset_token.id

    async with pg_session_factory() as session:
        async with session.begin():
            await session.execute(delete(User).where(User.id == consumer.id))
        invite_row = await session.get(InviteLink, invite_id)
        assert invite_row is not None
        assert invite_row.used_by is None
        assert invite_row.used_at == now

    async with pg_session_factory() as session:
        async with session.begin():
            await session.execute(delete(User).where(User.id == course.owner_id))
        for model, identity in (
            (Subject, course.subject_id),
            (FlashcardSet, course.set_id),
            (Flashcard, course.card_ids[0]),
            (InviteLink, invite_id),
            (AuthSession, auth_session_id),
            (PasswordResetToken, reset_token_id),
        ):
            assert await session.get(model, identity) is None
        assert await session.scalar(
            select(func.count(Enrollment.id)).where(Enrollment.subject_id == course.subject_id)
        ) == 0
        assert await session.scalar(
            select(func.count(StudyProgress.id)).where(
                StudyProgress.flashcard_id == course.card_ids[0]
            )
        ) == 0


async def test_direct_subject_delete_cascades_all_subject_dependents(pg_session_factory):
    course = await seed_course(pg_session_factory, published=True)
    now = utcnow()
    async with pg_session_factory() as session:
        async with session.begin():
            invite = InviteLink(
                code=uuid4().hex[:20],
                instructor_id=course.owner_id,
                subject_id=course.subject_id,
                created_at=now,
                expires_at=now + timedelta(hours=24),
            )
            progress = StudyProgress(
                student_id=course.student_id,
                flashcard_id=course.card_ids[0],
                status="learning",
                interval_days=1,
                last_reviewed=now,
                next_review=now + timedelta(days=1),
            )
            session.add_all([invite, progress])
            await session.flush()
            invite_id = invite.id

    async with pg_session_factory() as session:
        async with session.begin():
            await session.execute(delete(Subject).where(Subject.id == course.subject_id))
        assert await session.get(User, course.owner_id) is not None
        assert await session.get(User, course.student_id) is not None
        assert await session.get(FlashcardSet, course.set_id) is None
        assert await session.get(Flashcard, course.card_ids[0]) is None
        assert await session.get(InviteLink, invite_id) is None
        assert await session.scalar(
            select(func.count(Enrollment.id)).where(Enrollment.subject_id == course.subject_id)
        ) == 0
        assert await session.scalar(
            select(func.count(StudyProgress.id)).where(
                StudyProgress.flashcard_id == course.card_ids[0]
            )
        ) == 0


async def test_duplicate_enrollment_constraint_is_race_safe(pg_session_factory):
    course = await seed_course(pg_session_factory)
    nonce = uuid4().hex
    racing_student = User(
        email=f"racer-{nonce}@example.test",
        hashed_password="not-a-real-password-hash",
        role=UserRole.STUDENT,
    )
    async with pg_session_factory() as session:
        async with session.begin():
            session.add(racing_student)
            await session.flush()
            racing_student_id = racing_student.id

    async def enroll() -> str:
        async with pg_session_factory() as session:
            session.add(Enrollment(student_id=racing_student_id, subject_id=course.subject_id))
            try:
                await session.commit()
                return "created"
            except IntegrityError:
                await session.rollback()
                return "conflict"

    assert sorted(await asyncio.gather(enroll(), enroll())) == ["conflict", "created"]
    async with pg_session_factory() as session:
        count = await session.scalar(
            select(func.count(Enrollment.id)).where(
                Enrollment.student_id == racing_student_id,
                Enrollment.subject_id == course.subject_id,
            )
        )
        assert count == 1


async def test_concurrent_progress_updates_are_lossless(pg_session_factory):
    course = await seed_course(pg_session_factory, published=True)
    ready = asyncio.Event()
    arrived = 0
    arrival_lock = asyncio.Lock()

    async def answer_once() -> None:
        nonlocal arrived
        async with pg_session_factory() as session:
            card = await session.get(Flashcard, course.card_ids[0])
            async with arrival_lock:
                arrived += 1
                if arrived == 2:
                    ready.set()
            await ready.wait()
            await FlashcardService.update_progress(
                session,
                course.student_id,
                card,
                StudyProgressUpdate(
                    flashcard_id=card.id,
                    selected_option="canonical answer",
                ),
            )
            await session.commit()

    await asyncio.gather(answer_once(), answer_once())
    async with pg_session_factory() as session:
        rows = list(
            (await session.scalars(select(StudyProgress).where(
                StudyProgress.student_id == course.student_id,
                StudyProgress.flashcard_id == course.card_ids[0],
            ))).all()
        )
        assert len(rows) == 1
        assert rows[0].correct_count == 2
        assert rows[0].incorrect_count == 0


async def test_failed_generation_and_progress_batches_leave_no_partial_records(pg_session_factory):
    course = await seed_course(pg_session_factory, card_count=2, published=True)
    orphan_title = f"rollback-{uuid4().hex}"

    async with pg_session_factory() as session:
        with pytest.raises(ValueError):
            async with session.begin():
                generated_set = FlashcardSet(subject_id=course.subject_id, title=orphan_title)
                session.add(generated_set)
                await session.flush()
                await FlashcardService.create_flashcards_bulk(
                    session,
                    [
                        {
                            "front_content": "Valid",
                            "back_content": "A",
                            "options": ["A", "B", "C", "D"],
                        },
                        {
                            "front_content": "Invalid",
                            "back_content": "missing",
                            "options": ["A", "B", "C", "D"],
                        },
                    ],
                    generated_set.id,
                )
        assert await session.scalar(
            select(func.count(FlashcardSet.id)).where(FlashcardSet.title == orphan_title)
        ) == 0

    updates = [
        StudyProgressUpdate(
            flashcard_id=course.card_ids[0],
            selected_option="Canonical Answer",
        ),
        StudyProgressUpdate(
            flashcard_id=course.card_ids[1],
            selected_option="not-an-option",
        ),
    ]
    async with pg_session_factory() as session:
        with pytest.raises(HTTPException):
            async with session.begin():
                cards = await FlashcardService.get_studyable_cards(
                    session,
                    course.student_id,
                    (update.flashcard_id for update in updates),
                )
                for update in updates:
                    await FlashcardService.update_progress(
                        session,
                        course.student_id,
                        cards[update.flashcard_id],
                        update,
                    )
        assert await session.scalar(
            select(func.count(StudyProgress.id)).where(
                StudyProgress.student_id == course.student_id,
                StudyProgress.flashcard_id.in_(course.card_ids),
            )
        ) == 0
