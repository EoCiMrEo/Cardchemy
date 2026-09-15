from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.models.flashcard import CardStatus, Flashcard, StudyProgress
from app.models.subject import FlashcardSet
from app.schemas.flashcard import FlashcardCreate, StudyProgressUpdate
from app.schemas.subject import FlashcardSetUpdate, SubjectCreate
from app.schemas.user import UserCreate
from app.services.flashcard import FlashcardService


def card_data(**overrides) -> dict:
    data = {
        "set_id": uuid4(),
        "front_content": "  What is two plus two?  ",
        "back_content": " four ",
        "options": ["One", "Two", "  Four  ", "Five"],
    }
    data.update(overrides)
    return data


def test_multiple_choice_card_is_trimmed_and_answer_is_canonicalized():
    card = FlashcardCreate(**card_data())
    assert card.front_content == "What is two plus two?"
    assert card.options == ["One", "Two", "Four", "Five"]
    assert card.back_content == "Four"
    assert card.card_type == "multiple_choice"


@pytest.mark.parametrize(
    "options,answer",
    [
        (["One", "Two", "Three"], "One"),
        (["One", " one ", "Three", "Four"], "One"),
        (["One", "Two", "Three", "Four"], "Five"),
        (["One", "Two", "", "Four"], "One"),
    ],
)
def test_invalid_multiple_choice_cards_are_rejected(options, answer):
    with pytest.raises(ValidationError):
        FlashcardCreate(**card_data(options=options, back_content=answer))


def test_bounds_and_nullable_time_limit_contract():
    assert SubjectCreate(name="  Biology  ").name == "Biology"
    assert UserCreate(
        email="teacher@example.com",
        password="long-enough-password",
        full_name="  Ada Lovelace  ",
    ).full_name == "Ada Lovelace"
    assert FlashcardSetUpdate(time_limit=None).time_limit is None
    for invalid in (0, 4, 3601):
        with pytest.raises(ValidationError):
            FlashcardSetUpdate(time_limit=invalid)
    with pytest.raises(ValidationError):
        SubjectCreate(name=" ")


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
        "phase2-answer-0001",
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
