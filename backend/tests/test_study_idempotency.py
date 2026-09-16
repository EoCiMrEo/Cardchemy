from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.flashcard import Flashcard, StudyAnswerSubmission, StudyProgress
from app.models.subject import FlashcardSet
from app.schemas.flashcard import StudyProgressUpdate
from app.services.flashcard import FlashcardService


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


