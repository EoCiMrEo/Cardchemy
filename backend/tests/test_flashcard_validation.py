from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.flashcard import FlashcardCreate
from app.schemas.subject import FlashcardSetUpdate, SubjectCreate
from app.schemas.user import UserCreate


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


