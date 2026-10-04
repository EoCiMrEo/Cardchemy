"""Audited native Gemini text profiles used by both application roles.

The catalog is intentionally closed.  Google model metadata alone does not
describe the structured-output wire contract or thinking compatibility.  Each
entry is admitted by the offline role-by-model payload tests and the official
model, thinking, structured-output, token and pricing documentation reviewed
on 2026-09-22.  A change to a wire policy must get a new version.

https://ai.google.dev/gemini-api/docs/models
https://ai.google.dev/gemini-api/docs/thinking
https://ai.google.dev/gemini-api/docs/generate-content/structured-output
https://ai.google.dev/gemini-api/docs/generate-content/tokens
https://ai.google.dev/gemini-api/docs/pricing
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


TextRole = Literal["flashcard", "rag_answer"]
CATALOG_VERSION = "gemini-text-2026-09-22-v1"
SCHEMA_POLICY_VERSION = "gemini-inline-json-subset-v1"
_ALL_ROLES: tuple[TextRole, ...] = ("flashcard", "rag_answer")
_ALL_THINKING = frozenset({"minimal", "low", "medium", "high"})
_HIGHER_THINKING = frozenset({"low", "medium", "high"})


@dataclass(frozen=True, slots=True)
class GeminiTextCapability:
    model_id: str
    roles: tuple[TextRole, ...]
    thinking_levels: frozenset[str]
    context_window_tokens: int
    max_output_tokens: int
    schema_policy_version: str
    sampling_policy: Literal["provider_default"]
    usage_policy: Literal["candidate_plus_thought"]
    paid_input_usd_per_million: Decimal
    paid_output_usd_per_million: Decimal
    price_note: str


def _entry(
    model_id: str,
    thinking_levels: frozenset[str],
    input_price: str,
    output_price: str,
    *,
    price_note: str = "standard paid tier, reviewed 2026-09-22",
) -> GeminiTextCapability:
    return GeminiTextCapability(
        model_id=model_id,
        roles=_ALL_ROLES,
        thinking_levels=thinking_levels,
        context_window_tokens=1_048_576,
        max_output_tokens=65_536,
        schema_policy_version=SCHEMA_POLICY_VERSION,
        sampling_policy="provider_default",
        usage_policy="candidate_plus_thought",
        paid_input_usd_per_million=Decimal(input_price),
        paid_output_usd_per_million=Decimal(output_price),
        price_note=price_note,
    )


_INTRODUCTORY_PRICE = "introductory paid tier through 2026-12-31; recheck before later live use"
CATALOG: dict[str, GeminiTextCapability] = {
    entry.model_id: entry
    for entry in (
        _entry("gemini-3.5-flash-lite", _ALL_THINKING, "0.30", "2.50"),
        _entry("gemini-3.5-flash", _ALL_THINKING, "1.50", "9.00"),
        _entry("gemini-3.6-flash", _ALL_THINKING, "0.75", "3.75", price_note=_INTRODUCTORY_PRICE),
        _entry("gemini-3.7-flash", _HIGHER_THINKING, "0.75", "3.75", price_note=_INTRODUCTORY_PRICE),
        _entry("gemini-3.8-flash", _HIGHER_THINKING, "0.75", "3.75", price_note=_INTRODUCTORY_PRICE),
    )
}


class GeminiCatalogError(ValueError):
    """Nonsecret, actionable model-policy preflight failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def resolve_text_model(
    model_id: str,
    *,
    role: TextRole,
    thinking_level: str,
    context_window_tokens: int,
    max_output_tokens: int,
) -> GeminiTextCapability:
    """Reject an unsupported or incompatible selection before a remote call."""

    entry = CATALOG.get(model_id)
    if entry is None or role not in entry.roles:
        raise GeminiCatalogError(
            "ai_model_not_in_catalog",
            "Select a verified Gemini model from the configured role catalog.",
        )
    if thinking_level not in entry.thinking_levels:
        raise GeminiCatalogError(
            "ai_model_thinking_incompatible",
            "The selected Gemini model does not support the configured thinking level.",
        )
    if context_window_tokens > entry.context_window_tokens:
        raise GeminiCatalogError(
            "ai_model_context_incompatible",
            "The configured context budget exceeds the selected Gemini model limit.",
        )
    if max_output_tokens > entry.max_output_tokens:
        raise GeminiCatalogError(
            "ai_model_output_incompatible",
            "The configured output budget exceeds the selected Gemini model limit.",
        )
    return entry
