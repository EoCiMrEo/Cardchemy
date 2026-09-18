"""Deterministic grounding, quality checks, and near-duplicate rejection."""

from __future__ import annotations

from difflib import SequenceMatcher
import re
import unicodedata

from app.ai.contracts import DocumentChunk, GeneratedCardCandidate, ValidatedCard


_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")
_QUESTION_PREFIX = re.compile(
    r"^(?:what\s+is|what\s+are|define|explain|describe|which\s+of\s+the\s+following)\b[\s:—-]*",
    re.IGNORECASE,
)

REJECTION_CATEGORIES = (
    "unknown_source", "chunk_quota", "quote_not_contiguous", "answer_not_in_quote",
    "unclear_question", "option_matches_question", "near_duplicate",
)


def normalize_evidence(value: str) -> str:
    """Normalize only for comparison; persisted evidence remains verbatim."""

    return _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", value)).strip().casefold()


def _duplicate_key(value: str) -> tuple[str, set[str]]:
    normalized = normalize_evidence(value)
    normalized = _QUESTION_PREFIX.sub("", normalized)
    normalized = _NON_WORD.sub(" ", normalized)
    normalized = _WHITESPACE.sub(" ", normalized).strip()
    return normalized, set(normalized.split())


def duplicate_similarity(left: ValidatedCard, right: ValidatedCard) -> float:
    left_front, left_tokens = _duplicate_key(left.front_content)
    right_front, right_tokens = _duplicate_key(right.front_content)
    union = left_tokens | right_tokens
    jaccard = len(left_tokens & right_tokens) / len(union) if union else 1.0
    character = SequenceMatcher(None, left_front, right_front).ratio()
    answer = SequenceMatcher(
        None,
        normalize_evidence(left.back_content),
        normalize_evidence(right.back_content),
    ).ratio()
    front_similarity = max(character, jaccard)
    return (front_similarity * 0.75) + (answer * 0.25)


def validate_grounded_candidate(
    candidate: GeneratedCardCandidate,
    chunks_by_id: dict[str, DocumentChunk],
) -> ValidatedCard | None:
    """Return the canonical card only when every deterministic check succeeds."""

    return inspect_grounded_candidate(candidate, chunks_by_id)[0]


def inspect_grounded_candidate(
    candidate: GeneratedCardCandidate,
    chunks_by_id: dict[str, DocumentChunk],
) -> tuple[ValidatedCard | None, str | None]:
    """Return a card or a closed rejection code, never candidate content."""

    chunk = chunks_by_id.get(candidate.source_chunk_id)
    if chunk is None:
        return None, "unknown_source"
    quote = normalize_evidence(candidate.source_quote)
    source = normalize_evidence(chunk.text)
    answer = normalize_evidence(candidate.back)
    if not quote or quote not in source:
        return None, "quote_not_contiguous"
    if not answer or answer not in quote:
        return None, "answer_not_in_quote"

    # The strict candidate contract already proves four unique options and one
    # exact answer. This second pass checks clarity and meaningful distractors.
    question = normalize_evidence(candidate.front)
    if len(question) < 5 or question == answer:
        return None, "unclear_question"
    if any(normalize_evidence(option) == question for option in candidate.options):
        return None, "option_matches_question"

    quote_coverage = min(1.0, len(answer) / max(1, len(quote)))
    quality = round(min(1.0, 0.75 + quote_coverage * 0.25), 4)
    return ValidatedCard(
        front_content=candidate.front,
        back_content=candidate.back,
        options=candidate.options,
        quality_score=quality,
        source_snippet=candidate.source_quote,
        source_page=chunk.page_number,
        source_section=chunk.section,
    ), None


def append_if_distinct(
    accepted: list[ValidatedCard],
    candidate: ValidatedCard,
    *,
    threshold: float,
) -> bool:
    if any(duplicate_similarity(existing, candidate) >= threshold for existing in accepted):
        return False
    accepted.append(candidate)
    return True
