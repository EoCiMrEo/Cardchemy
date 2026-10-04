"""Unshipped, source-extractive Ask support experiment.

This candidate deliberately recognizes only an explicit acronym expansion.
The active Ask worker never selects it. A finite grammar is safer than treating
the current small NLI model's low confidence or a missing QA span as proof of a
relation. It is not a general semantic-support replacement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Literal, Sequence

from app.ai.answering import ValidatedAnswerClaim, normalize_text
from app.ai.local_support import NliScorer, QaScorer
from app.services.knowledge_retrieval import RetrievedKnowledgeChunk


EXTRACTIVE_SUPPORT_CANDIDATE_VERSION = "local_extractive_acronym_candidate_v1"

CandidateReason = Literal[
    "supported",
    "invalid_source",
    "unsupported_question",
    "unsupported_source_relation",
    "claim_mismatch",
    "local_semantic_rejected",
    "local_check_unavailable",
    "conflicting_expansion",
    "ambiguous_expansion",
]

_ACRONYM = r"[A-Z][A-Z0-9-]{1,23}"
_EXPANSION = r"[A-Za-z]+(?:[ -]+[A-Za-z]+){0,11}"
_DIRECT_QUESTION = re.compile(
    rf"^what does (?P<subject>{_ACRONYM}) stand for\s*\?$",
    re.IGNORECASE,
)
_SOURCE_PATTERNS = (
    re.compile(rf"^(?P<subject>{_ACRONYM})\s*\((?P<expansion>{_EXPANSION})\)\.?$"),
    re.compile(rf"^(?P<subject>{_ACRONYM})\s*:\s*(?P<expansion>{_EXPANSION})\.?$"),
    re.compile(
        rf"^(?P<subject>{_ACRONYM})\s+(?:stands for|is short for|means)\s+"
        rf"(?P<expansion>{_EXPANSION})\.?$",
        re.IGNORECASE,
    ),
)
_CLAIM_PATTERN = re.compile(
    rf"^(?P<subject>{_ACRONYM})\s+(?:stands for|is short for|means)\s+"
    rf"(?P<expansion>{_EXPANSION})\.?$",
    re.IGNORECASE,
)
_BULLET = re.compile(r"^(?:[-*•]\s*|\d+[.)]\s*)")
_EXPANSION_CUE = re.compile(
    r"\b(?:stands? for|short for|means|abbreviation|acronym|expands? to|full form)\b",
    re.IGNORECASE,
)
_ANAPHORIC_EXPANSION = re.compile(r"\b(?:it|this|that)\s+(?:stands? for|means)\b", re.IGNORECASE)
_UNSAFE_MODIFIER = re.compile(r"\b(?:not|never|false|incorrect|obsolete|formerly|allegedly|possibly)\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class CandidateVerdict:
    accepted: bool
    reason_code: CandidateReason
    # Derived from an exact source relation. Never place it in diagnostic logs.
    answer: str | None = field(default=None, repr=False)


def _clean_line(value: str) -> str:
    return _BULLET.sub("", value.strip(), count=1).strip()


def _expansion(value: str) -> tuple[str, str] | None:
    line = _clean_line(value)
    if not line or "\n" in line or "\r" in line or _UNSAFE_MODIFIER.search(line):
        return None
    for pattern in _SOURCE_PATTERNS:
        match = pattern.fullmatch(line)
        if match is not None:
            expansion = match.group("expansion").rstrip(". ").strip()
            if not 2 <= len(expansion.split()) <= 12:
                return None
            return match.group("subject"), expansion
    return None


def evaluate_acronym_candidate(
    *,
    question: str,
    claim: ValidatedAnswerClaim,
    chunks: Sequence[RetrievedKnowledgeChunk],
    nli: NliScorer,
    qa: QaScorer,
) -> CandidateVerdict:
    """Prove only an explicit acronym expansion from one exact cited line.

    All selected source chunks are scanned for an explicit conflicting expansion.
    An unresolved same-subject expansion or anaphora abstains. Other measured
    properties of that subject are different propositions and do not veto it.
    The caller still owns authorization, current-revision reads and citation
    persistence; this pure experiment never performs I/O or provider calls.
    """

    if len(question) > 4000 or len(claim.statement) > 4000 or len(chunks) > 5:
        return CandidateVerdict(False, "invalid_source")
    sources = [source for source in chunks if source.chunk_id == claim.source.chunk_id]
    if (
        len(sources) != 1
        or sources[0] != claim.source
        or not claim.source_quote
        or len(claim.source_quote) > 950
        or claim.source_quote not in claim.source.content
        or sum(
            line.strip() == claim.source_quote.strip()
            for line in claim.source.content.splitlines()
        ) != 1
        or len({source.chunk_id for source in chunks}) != len(chunks)
    ):
        return CandidateVerdict(False, "invalid_source")

    question_match = _DIRECT_QUESTION.fullmatch(" ".join(question.split()))
    if question_match is None or question_match.group("subject") != question_match.group("subject").upper():
        return CandidateVerdict(False, "unsupported_question")
    subject = question_match.group("subject").casefold()

    source_fact = _expansion(claim.source_quote)
    if source_fact is None or source_fact[0].casefold() != subject:
        return CandidateVerdict(False, "unsupported_source_relation")

    claim_match = _CLAIM_PATTERN.fullmatch(" ".join(claim.statement.split()))
    if (
        claim_match is None
        or claim_match.group("subject").casefold() != subject
        or normalize_text(claim_match.group("expansion").rstrip(". "))
        != normalize_text(source_fact[1])
    ):
        return CandidateVerdict(False, "claim_mismatch")

    # Parenthetical notation alone can be a gloss, not an expansion. Keep the
    # independent local NLI and question-answering gates even for this strict
    # source grammar. Exact expansion matching additionally rejects a wrong
    # object when a small NLI model gives it an erroneously high score.
    try:
        entailment = nli.score(claim.source_quote, claim.statement)
        answer_span = qa.answer(question, claim.source_quote)
    except Exception:
        return CandidateVerdict(False, "local_check_unavailable")
    if (
        entailment.entailment < 0.80
        or entailment.entailment <= max(entailment.contradiction, entailment.neutral)
        or not answer_span
        or not normalize_text(answer_span)
        or normalize_text(answer_span) not in normalize_text(claim.statement)
        or normalize_text(answer_span) not in normalize_text(claim.source_quote)
    ):
        return CandidateVerdict(False, "local_semantic_rejected")

    for chunk in chunks:
        for raw_line in chunk.content.splitlines():
            line = _clean_line(raw_line)
            if not line:
                continue
            parsed = _expansion(line)
            if parsed is not None and parsed[0].casefold() == subject:
                if normalize_text(parsed[1]) != normalize_text(source_fact[1]):
                    return CandidateVerdict(False, "conflicting_expansion")
                continue
            if _ANAPHORIC_EXPANSION.search(line):
                return CandidateVerdict(False, "ambiguous_expansion")
            if (
                re.search(rf"(?<!\w){re.escape(subject)}(?!\w)", line, re.IGNORECASE)
                and _EXPANSION_CUE.search(line)
            ):
                return CandidateVerdict(False, "ambiguous_expansion")

    return CandidateVerdict(
        True,
        "supported",
        f"{source_fact[0]} stands for {source_fact[1]}.",
    )


__all__ = [
    "CandidateVerdict",
    "EXTRACTIVE_SUPPORT_CANDIDATE_VERSION",
    "evaluate_acronym_candidate",
]
