"""Validated flashcard and study-progress API contracts."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from app.schemas.subject import FlashcardSetResponse


CardText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000)]
CardType = Literal["multiple_choice"]


def normalize_multiple_choice(
    front_content: str,
    back_content: str,
    options: list[str],
) -> tuple[str, str, list[str]]:
    """Normalize and validate the product's canonical multiple-choice card."""

    front = front_content.strip()
    answer = back_content.strip()
    normalized_options = [option.strip() for option in options]
    if not 1 <= len(front) <= 10_000:
        raise ValueError("front_content must contain 1 to 10000 characters")
    if not 1 <= len(answer) <= 10_000:
        raise ValueError("back_content must contain 1 to 10000 characters")
    if len(normalized_options) != 4:
        raise ValueError("multiple-choice cards must contain exactly 4 options")
    if any(not option or len(option) > 10_000 for option in normalized_options):
        raise ValueError("each option must contain 1 to 10000 characters")

    option_keys = [option.casefold() for option in normalized_options]
    if len(set(option_keys)) != 4:
        raise ValueError("options must be unique after trimming and case normalization")

    answer_key = answer.casefold()
    matches = [index for index, key in enumerate(option_keys) if key == answer_key]
    if len(matches) != 1:
        raise ValueError("back_content must match exactly one option")
    return front, normalized_options[matches[0]], normalized_options


class FlashcardCreate(BaseModel):
    model_config = {"extra": "forbid"}

    set_id: UUID
    front_content: CardText
    back_content: CardText
    options: list[CardText] = Field(min_length=4, max_length=4)
    card_type: CardType = "multiple_choice"

    @model_validator(mode="after")
    def validate_card(self) -> "FlashcardCreate":
        front, back, options = normalize_multiple_choice(
            self.front_content,
            self.back_content,
            list(self.options),
        )
        self.front_content = front
        self.back_content = back
        self.options = options
        return self


class FlashcardUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    front_content: CardText | None = None
    back_content: CardText | None = None
    options: list[CardText] | None = Field(default=None, min_length=4, max_length=4)
    card_type: CardType | None = None
    is_approved: bool | None = None

    @field_validator("options")
    @classmethod
    def normalize_options(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [option.strip() for option in value]
        if len({option.casefold() for option in normalized}) != 4:
            raise ValueError("options must be unique after trimming and case normalization")
        return normalized

    @model_validator(mode="after")
    def reject_null_fields(self) -> "FlashcardUpdate":
        for field_name in ("front_content", "back_content", "options", "card_type", "is_approved"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class FlashcardResponse(BaseModel):
    id: UUID
    set_id: UUID
    front_content: str
    back_content: str
    options: list[str]
    card_type: CardType
    confidence_score: float
    is_approved: bool
    source_chunk: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class StudyCardResponse(BaseModel):
    """Student-facing card data intentionally excludes the correct answer."""

    id: UUID
    set_id: UUID
    front_content: str
    options: list[str]
    card_type: CardType

    model_config = {"from_attributes": True}


class FlashcardGenerateRequest(BaseModel):
    subject_id: UUID
    set_title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    set_description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000)] | None = None


class FlashcardGenerateResponse(BaseModel):
    flashcard_set: FlashcardSetResponse
    flashcards: list[FlashcardResponse]
    total_generated: int
    auto_approved: int
    needs_review: int


class StudyProgressUpdate(BaseModel):
    """One answer submission; correctness and quality are derived by the server."""

    model_config = {"extra": "forbid"}

    flashcard_id: UUID
    selected_option: CardText | None = None
    selected_option_index: int | None = Field(default=None, ge=0, le=3)

    @model_validator(mode="before")
    @classmethod
    def require_one_answer_representation(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        present = [name for name in ("selected_option", "selected_option_index") if name in data]
        if len(present) != 1:
            raise ValueError("provide exactly one of selected_option or selected_option_index")
        return data


class StudyProgressResponse(BaseModel):
    id: UUID
    flashcard_id: UUID
    status: Literal["new", "learning", "review", "mastered"]
    ease_factor: float
    interval_days: int
    next_review: datetime | None
    last_reviewed: datetime | None
    correct_count: int
    incorrect_count: int

    model_config = {"from_attributes": True}


class StudyAnswerResponse(BaseModel):
    progress: StudyProgressResponse
    is_correct: bool
    quality: Literal[1, 5]
    correct_option: str
    correct_option_index: int = Field(ge=0, le=3)


class StudySessionResponse(BaseModel):
    cards: list[StudyCardResponse]
    total_due: int
    new_cards: int
    review_cards: int
    time_limit: int | None = Field(default=None, ge=5, le=3600)


class SetProgressResponse(BaseModel):
    total: int
    new: int
    learning: int
    review: int
    mastered: int
    studied: int
    correct_count: int
    completion_percentage: float = Field(ge=0, le=100)
    mastery_percentage: float = Field(ge=0, le=100)


class StudySyncResponse(BaseModel):
    synced_count: int
