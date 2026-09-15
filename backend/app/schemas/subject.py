"""Validated request and response schemas for subjects and flashcard sets."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator


BoundedName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
BoundedDescription = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000)]


def _blank_to_none(value: object) -> object:
    if not isinstance(value, str):
        return value
    normalized = value.strip()
    return normalized or None


class SubjectCreate(BaseModel):
    model_config = {"extra": "forbid"}

    name: BoundedName
    description: BoundedDescription | None = None

    _normalize_description = field_validator("description", mode="before")(_blank_to_none)


class SubjectUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    name: BoundedName | None = None
    description: BoundedDescription | None = None

    _normalize_description = field_validator("description", mode="before")(_blank_to_none)

    @model_validator(mode="after")
    def reject_null_name(self) -> "SubjectUpdate":
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        return self


class SubjectResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    instructor_id: UUID
    created_at: datetime
    flashcard_set_count: int = 0
    student_count: int = 0

    model_config = {"from_attributes": True}


class FlashcardSetCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    title: BoundedName
    description: BoundedDescription | None = None

    _normalize_description = field_validator("description", mode="before")(_blank_to_none)


class FlashcardSetCreate(FlashcardSetCreateRequest):
    """Internal create contract after the route supplies its subject ID."""

    subject_id: UUID


class FlashcardSetUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    title: BoundedName | None = None
    description: BoundedDescription | None = None
    is_published: bool | None = None
    time_limit: int | None = Field(default=None, ge=5, le=3600)

    _normalize_description = field_validator("description", mode="before")(_blank_to_none)

    @model_validator(mode="after")
    def reject_null_non_nullable_fields(self) -> "FlashcardSetUpdate":
        for field_name in ("title", "is_published"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class FlashcardSetResponse(BaseModel):
    id: UUID
    subject_id: UUID
    title: str
    description: str | None
    source_pdf_name: str | None
    generation_job_id: UUID | None
    is_published: bool
    time_limit: int | None
    created_at: datetime
    flashcard_count: int = 0
    approved_count: int = 0

    model_config = {"from_attributes": True}
