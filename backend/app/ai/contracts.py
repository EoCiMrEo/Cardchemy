"""Strict contracts shared by extraction, providers, validation, and persistence."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
CardFront = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)
]
CardBack = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4_000)
]
CardOption = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4_000)
]
SourceQuote = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000)
]


class StrictModel(BaseModel):
    """Reject undeclared/coerced provider data instead of silently accepting it."""

    model_config = ConfigDict(extra="forbid", strict=True)


class ExtractedPage(StrictModel):
    """One PDF page, including empty pages so page numbering never shifts."""

    page_number: int = Field(ge=1)
    text: str = Field(max_length=10_000_000)


class ExtractedDocument(StrictModel):
    """Page-preserving PDF extraction result."""

    pages: list[ExtractedPage] = Field(min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def require_contiguous_page_numbers(self) -> "ExtractedDocument":
        expected = list(range(1, len(self.pages) + 1))
        actual = [page.page_number for page in self.pages]
        if actual != expected:
            raise ValueError("extracted pages must be ordered and numbered contiguously")
        return self

    @property
    def text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text).strip()

    def __str__(self) -> str:
        return self.text

    def __eq__(self, other: object) -> bool:
        # Preserve the old extraction assertion contract while callers migrate
        # to the structured page representation.
        if isinstance(other, str):
            return self.text == other
        return super().__eq__(other)


class DocumentChunk(StrictModel):
    """A token-bounded chunk whose provenance is assigned by the server."""

    chunk_id: Annotated[str, StringConstraints(pattern=r"^chunk-[0-9]{4}-p[0-9]+$")]
    text: NonEmptyText
    page_number: int = Field(ge=1)
    section: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None
    token_count: int = Field(ge=1)


class GeneratedCardCandidate(StrictModel):
    """Provider output. It deliberately contains no model confidence score."""

    front: CardFront
    back: CardBack
    options: list[CardOption] = Field(min_length=4, max_length=4)
    source_chunk_id: Annotated[
        str, StringConstraints(pattern=r"^chunk-[0-9]{4}-p[0-9]+$")
    ]
    source_quote: SourceQuote

    @field_validator("options")
    @classmethod
    def require_unique_options(cls, options: list[str]) -> list[str]:
        keys = [option.casefold() for option in options]
        if len(set(keys)) != 4:
            raise ValueError("options must be unique after case normalization")
        return options

    @model_validator(mode="after")
    def require_exactly_one_answer(self) -> "GeneratedCardCandidate":
        answer = self.back.casefold()
        if sum(option.casefold() == answer for option in self.options) != 1:
            raise ValueError("back must match exactly one option")
        return self


class CandidateBatch(StrictModel):
    cards: list[GeneratedCardCandidate] = Field(max_length=500)


class SummaryOutput(StrictModel):
    """One map/reduce summary with traceable source chunk identifiers."""

    summary: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000)
    ]
    source_chunk_ids: list[
        Annotated[str, StringConstraints(pattern=r"^chunk-[0-9]{4}-p[0-9]+$")]
    ] = Field(min_length=1, max_length=500)

    @field_validator("source_chunk_ids")
    @classmethod
    def unique_source_ids(cls, source_ids: list[str]) -> list[str]:
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("source_chunk_ids must be unique")
        return source_ids


class ValidatedCard(StrictModel):
    """Server-grounded representation returned to the durable worker."""

    front_content: CardFront
    back_content: CardBack
    options: list[CardOption] = Field(min_length=4, max_length=4)
    card_type: Literal["multiple_choice"] = "multiple_choice"
    quality_score: float = Field(ge=0, le=1)
    source_snippet: SourceQuote
    source_page: int = Field(ge=1)
    source_section: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=255)
    ] | None = None


class EvaluationMetrics(StrictModel):
    requested_cards: int = Field(ge=1)
    generated_cards: int = Field(ge=0)
    rejected_cards: int = Field(ge=0)
    schema_valid_rate: float = Field(ge=0, le=1)
    grounded_rate: float = Field(ge=0, le=1)
    duplicate_rate: float = Field(ge=0, le=1)
