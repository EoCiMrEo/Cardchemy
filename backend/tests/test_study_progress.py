from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.models.flashcard import CardStatus, Flashcard, StudyProgress
from app.models.subject import FlashcardSet
from app.schemas.flashcard import StudyProgressUpdate
from app.services.flashcard import FlashcardService


def test_progress_rejects_client_supplied_correctness_and_quality():
    with pytest.raises(ValidationError):
        StudyProgressUpdate(flashcard_id=uuid4(), is_correct=True, quality=5)
    with pytest.raises(ValidationError):
        StudyProgressUpdate(
            flashcard_id=uuid4(),
            selected_option="Answer",
            selected_option_index=0,
        )


async def test_server_derives_correctness_and_progress_percentages(db):
    set_id = uuid4()
    first = Flashcard(
        id=uuid4(),
        set_id=set_id,
        front_content="Question one",
        back_content="Answer",
        options=["Answer", "B", "C", "D"],
        is_approved=True,
    )
    second = Flashcard(
        id=uuid4(),
        set_id=set_id,
        front_content="Question two",
        back_content="Correct",
        options=["A", "B", "C", "Correct"],
        is_approved=True,
    )
    db.add_all([FlashcardSet(id=set_id, subject_id=uuid4(), title="Set"), first, second])
    # SQLite unit tests do not enforce foreign keys, so the parent subject is not needed here.
    await db.commit()

    student_id = uuid4()
    answer = await FlashcardService.update_progress(
        db,
        student_id,
        first,
        StudyProgressUpdate(flashcard_id=first.id, selected_option=" answer "),
        "study-progress-answer-0001",
    )
    await db.commit()
    assert answer.is_correct is True
    assert answer.quality == 5
    assert answer.correct_option == "Answer"
    assert answer.progress.status == CardStatus.LEARNING.value

    stats = await FlashcardService.get_set_progress(db, student_id, set_id)
    assert stats == {
        "total": 2,
        "new": 1,
        "learning": 1,
        "review": 0,
        "mastered": 0,
        "studied": 1,
        "correct_count": 1,
        "completion_percentage": 50.0,
        "mastery_percentage": 0.0,
    }

    progress = await db.scalar(select(StudyProgress).where(StudyProgress.flashcard_id == first.id))
    assert progress is not None
    assert progress.last_reviewed.tzinfo is None  # SQLite strips tzinfo; PostgreSQL coverage verifies TIMESTAMPTZ.


async def test_due_cards_are_limited_and_deterministic(db):
    set_id = uuid4()
    flashcard_set = FlashcardSet(id=set_id, subject_id=uuid4(), title="Set")
    cards = [
        Flashcard(
            id=uuid4(),
            set_id=set_id,
            front_content=f"Question {index}",
            back_content="A",
            options=["A", "B", "C", "D"],
            is_approved=True,
        )
        for index in range(3)
    ]
    db.add_all([flashcard_set, *cards])
    await db.commit()
    first_run = await FlashcardService.get_due_cards(db, uuid4(), set_id, limit=2)
    second_run = await FlashcardService.get_due_cards(db, uuid4(), set_id, limit=2)
    assert len(first_run) == 2
    assert [card.id for card in first_run] == [card.id for card in second_run]
