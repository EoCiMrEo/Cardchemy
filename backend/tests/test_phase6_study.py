from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.main import app
from app.models.flashcard import Enrollment, Flashcard, StudyAnswerSubmission, StudyProgress
from app.models.subject import FlashcardSet, Subject
from app.models.user import User, UserRole
from app.routers.study import get_study_session
from app.schemas.flashcard import StudyProgressUpdate
from app.services.flashcard import FlashcardService
from app.time_utils import utcnow


def make_card(set_id, *, answer: str = "Correct", approved: bool = True) -> Flashcard:
    return Flashcard(
        id=uuid4(),
        set_id=set_id,
        front_content=f"Question {uuid4()}",
        back_content=answer,
        options=[answer, "Distractor B", "Distractor C", "Distractor D"],
        is_approved=approved,
    )


async def test_answer_idempotency_replays_exact_response_and_rejects_key_reuse(db):
    set_id = uuid4()
    card = make_card(set_id)
    db.add(FlashcardSet(id=set_id, subject_id=uuid4(), title="Idempotency"))
    db.add(card)
    await db.commit()

    student_id = uuid4()
    key = "study-answer-idempotency-0001"
    first = await FlashcardService.update_progress(
        db,
        student_id,
        card,
        StudyProgressUpdate(flashcard_id=card.id, selected_option=" correct "),
        key,
    )
    await db.commit()

    replay = await FlashcardService.update_progress(
        db,
        student_id,
        card,
        StudyProgressUpdate(flashcard_id=card.id, selected_option_index=0),
        key,
    )
    await db.commit()

    assert replay == first
    progress = await db.scalar(
        select(StudyProgress).where(
            StudyProgress.student_id == student_id,
            StudyProgress.flashcard_id == card.id,
        )
    )
    assert progress is not None
    assert progress.correct_count == 1
    assert progress.incorrect_count == 0
    assert await db.scalar(
        select(func.count(StudyAnswerSubmission.id)).where(
            StudyAnswerSubmission.student_id == student_id,
        )
    ) == 1

    with pytest.raises(HTTPException) as reused:
        await FlashcardService.update_progress(
            db,
            student_id,
            card,
            StudyProgressUpdate(flashcard_id=card.id, selected_option_index=1),
            key,
        )
    assert reused.value.status_code == 409
    assert reused.value.detail["code"] == "idempotency_key_reused"
    await db.rollback()


async def test_answer_idempotency_key_is_bounded_visible_ascii(db):
    set_id = uuid4()
    card = make_card(set_id)
    db.add_all([FlashcardSet(id=set_id, subject_id=uuid4(), title="Keys"), card])
    await db.commit()

    for invalid_key in ("short", "contains a space", "x" * 129, "unicode-☃-key"):
        with pytest.raises(HTTPException) as invalid:
            await FlashcardService.update_progress(
                db,
                uuid4(),
                card,
                StudyProgressUpdate(flashcard_id=card.id, selected_option_index=0),
                invalid_key,
            )
        assert invalid.value.status_code == 422
        assert invalid.value.detail["code"] == "invalid_idempotency_key"
        await db.rollback()


async def test_answer_idempotency_keys_are_scoped_to_each_student(db):
    set_id = uuid4()
    card = make_card(set_id)
    db.add_all([FlashcardSet(id=set_id, subject_id=uuid4(), title="Key scope"), card])
    await db.commit()

    shared_key = "same-client-key-different-students"
    for student_id in (uuid4(), uuid4()):
        answer = await FlashcardService.update_progress(
            db,
            student_id,
            card,
            StudyProgressUpdate(flashcard_id=card.id, selected_option_index=0),
            shared_key,
        )
        assert answer.is_correct is True
        await db.commit()

    assert await db.scalar(select(func.count(StudyAnswerSubmission.id))) == 2
    assert await db.scalar(select(func.count(StudyProgress.id))) == 2


async def test_review_all_returns_future_cards_in_least_recently_reviewed_order(db):
    set_id = uuid4()
    flashcard_set = FlashcardSet(id=set_id, subject_id=uuid4(), title="Review")
    older = make_card(set_id, answer="Older")
    newer = make_card(set_id, answer="Newer")
    draft = make_card(set_id, answer="Draft", approved=False)
    student_id = uuid4()
    now = utcnow()
    db.add_all(
        [
            flashcard_set,
            older,
            newer,
            draft,
            StudyProgress(
                student_id=student_id,
                flashcard_id=older.id,
                status="learning",
                interval_days=1,
                next_review=now + timedelta(days=1),
                last_reviewed=now - timedelta(days=2),
            ),
            StudyProgress(
                student_id=student_id,
                flashcard_id=newer.id,
                status="learning",
                interval_days=1,
                next_review=now + timedelta(days=1),
                last_reviewed=now - timedelta(days=1),
            ),
        ]
    )
    await db.commit()

    assert await FlashcardService.get_due_cards(db, student_id, set_id) == []
    review_cards = await FlashcardService.get_review_cards(db, student_id, set_id)
    assert [card.id for card in review_cards] == [older.id, newer.id]
    assert [card.id for card in await FlashcardService.get_review_cards(db, student_id, set_id, 1)] == [older.id]


async def test_review_all_router_starts_a_completed_authorized_session(db):
    owner = User(
        id=uuid4(),
        email="phase6-owner@example.test",
        hashed_password="not-a-password",
        role=UserRole.INSTRUCTOR,
    )
    student = User(
        id=uuid4(),
        email="phase6-student@example.test",
        hashed_password="not-a-password",
        role=UserRole.STUDENT,
    )
    subject = Subject(id=uuid4(), name="Review course", instructor_id=owner.id)
    flashcard_set = FlashcardSet(
        id=uuid4(),
        subject_id=subject.id,
        title="Completed set",
        is_published=True,
    )
    card = make_card(flashcard_set.id)
    now = utcnow()
    db.add_all(
        [
            owner,
            student,
            subject,
            flashcard_set,
            card,
            Enrollment(student_id=student.id, subject_id=subject.id),
            StudyProgress(
                student_id=student.id,
                flashcard_id=card.id,
                status="learning",
                interval_days=1,
                next_review=now + timedelta(days=1),
                last_reviewed=now,
            ),
        ]
    )
    await db.commit()

    due = await get_study_session(
        flashcard_set.id,
        limit=20,
        mode="due",
        user=student,
        db=db,
    )
    review = await get_study_session(
        flashcard_set.id,
        limit=20,
        mode="review_all",
        user=student,
        db=db,
    )
    assert due.cards == []
    assert [returned.id for returned in review.cards] == [card.id]


def test_study_openapi_requires_idempotency_and_has_no_offline_sync_contract():
    schema = app.openapi()
    progress_operation = schema["paths"]["/study/progress"]["post"]
    idempotency = next(
        parameter
        for parameter in progress_operation["parameters"]
        if parameter["name"] == "Idempotency-Key"
    )
    assert idempotency["in"] == "header"
    assert idempotency["required"] is True
    assert idempotency["schema"]["minLength"] == 8
    assert idempotency["schema"]["maxLength"] == 128
    assert "/study/sync" not in schema["paths"]

    session_parameters = schema["paths"]["/study/sets/{set_id}/session"]["get"]["parameters"]
    mode = next(parameter for parameter in session_parameters if parameter["name"] == "mode")
    assert mode["schema"]["enum"] == ["due", "review_all"]
