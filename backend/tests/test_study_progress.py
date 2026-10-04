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
        "attempted_count": 1,
        "attempted_percentage": 50.0,
        "correct_count": 1,
        "ever_correct_count": 1,
        "progress_percentage": 50.0,
        "accuracy_percentage": 100.0,
        "completion_percentage": 50.0,
        "mastery_percentage": 0.0,
    }

    progress = await db.scalar(select(StudyProgress).where(StudyProgress.flashcard_id == first.id))
    assert progress is not None
    assert progress.last_reviewed.tzinfo is None  # SQLite strips tzinfo; PostgreSQL coverage verifies TIMESTAMPTZ.


async def test_wrong_only_then_correct_then_wrong_keeps_coverage_and_counts_timeout(db):
    set_id = uuid4()
    cards = [
        Flashcard(
            id=uuid4(), set_id=set_id, front_content=f"Question {index}",
            back_content="Answer", options=["Answer", "B", "C", "D"], is_approved=True,
        )
        for index in range(10)
    ]
    db.add_all([FlashcardSet(id=set_id, subject_id=uuid4(), title="Set"), *cards])
    await db.commit()
    student_id = uuid4()

    for index, card in enumerate(cards):
        await FlashcardService.update_progress(
            db, student_id, card,
            StudyProgressUpdate(flashcard_id=card.id, selected_option=None if index == 0 else "B"),
            f"wrong-only-answer-{index:04d}",
        )
    await db.commit()
    wrong_only = await FlashcardService.get_set_progress(db, student_id, set_id)
    assert (wrong_only["ever_correct_count"], wrong_only["progress_percentage"]) == (0, 0.0)
    assert (wrong_only["attempted_count"], wrong_only["attempted_percentage"]) == (10, 100.0)
    assert wrong_only["completion_percentage"] == 100.0
    assert wrong_only["accuracy_percentage"] == 0.0

    answer = await FlashcardService.update_progress(
        db, student_id, cards[0],
        StudyProgressUpdate(flashcard_id=cards[0].id, selected_option="Answer"),
        "later-correct-answer-0001",
    )
    replay = await FlashcardService.update_progress(
        db, student_id, cards[0],
        StudyProgressUpdate(flashcard_id=cards[0].id, selected_option_index=0),
        "later-correct-answer-0001",
    )
    assert replay.model_dump(mode="json") == answer.model_dump(mode="json")
    await db.commit()
    await FlashcardService.update_progress(
        db, student_id, cards[0],
        StudyProgressUpdate(flashcard_id=cards[0].id, selected_option="B"),
        "later-wrong-answer-0001",
    )
    await db.commit()
    stats = await FlashcardService.get_set_progress(db, student_id, set_id)
    assert stats["ever_correct_count"] == 1
    assert stats["progress_percentage"] == 10.0
    assert stats["correct_count"] == 1
    assert stats["accuracy_percentage"] == 8.3
    assert stats["mastery_percentage"] == 0.0

    cards[0].is_approved = False
    await db.commit()
    unapproved = await FlashcardService.get_set_progress(db, student_id, set_id)
    assert (unapproved["total"], unapproved["ever_correct_count"]) == (9, 0)
    assert unapproved["correct_count"] == 0
    assert unapproved["accuracy_percentage"] == 0.0

    cards[0].is_approved = True
    await db.commit()
    reapproved = await FlashcardService.get_set_progress(db, student_id, set_id)
    assert (reapproved["total"], reapproved["ever_correct_count"]) == (10, 1)

    db.add(Flashcard(
        id=uuid4(), set_id=set_id, front_content="Newly approved", back_content="Answer",
        options=["Answer", "B", "C", "D"], is_approved=True,
    ))
    await db.commit()
    expanded = await FlashcardService.get_set_progress(db, student_id, set_id)
    assert (expanded["total"], expanded["ever_correct_count"], expanded["new"]) == (11, 1, 1)

    await db.delete(cards[0])
    await db.commit()
    deleted = await FlashcardService.get_set_progress(db, student_id, set_id)
    assert (deleted["total"], deleted["ever_correct_count"], deleted["correct_count"]) == (10, 0, 0)


async def test_empty_set_progress_has_zero_values(db):
    set_id = uuid4()
    db.add(FlashcardSet(id=set_id, subject_id=uuid4(), title="Empty"))
    await db.commit()
    stats = await FlashcardService.get_set_progress(db, uuid4(), set_id)
    assert all(value == 0 for value in stats.values())


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
