"""Typed compatibility state for the provider-neutral generation pipeline."""

from typing import TypedDict

class Flashcard(TypedDict):
    front_content: str
    back_content: str
    options: list[str]
    card_type: str
    quality_score: float
    source_snippet: str
    source_page: int
    source_section: str | None

class AgentState(TypedDict):
    pdf_document: object
    pdf_text: str
    target_count: int
    final_cards: list[Flashcard]
    rejected_card_count: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    actual_input_tokens: int
    actual_output_tokens: int
    estimated_cost_microusd: int | None
    actual_cost_microusd: int | None
    usage_estimated: bool
