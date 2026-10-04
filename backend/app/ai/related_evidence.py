"""Bounded exact-source windows for unverified, related Knowledge previews.

Selection is deterministic and provider-free. It ranks windows for browsing
only; lexical overlap never certifies that a passage answers a question.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence

from app.services.knowledge_retrieval import RetrievedKnowledgeChunk


MAX_RELATED_EXCERPTS = 2
MAX_SOURCE_FIRST_EXCERPTS = 3
MAX_RELATED_EXCERPT_CHARS = 480
_WINDOW_TARGET_CHARS = 420
_TERM = re.compile(r"[a-z0-9]{3,}", re.IGNORECASE)
_ACRONYM = re.compile(r"\b[A-Z][A-Z0-9]{1,11}(?:-[A-Z0-9]{2,11})*\b")
_REFERENT = re.compile(r"\b(?:it|its|this|that|these|those|they|them)\b", re.IGNORECASE)
_STOP = frozenset({
    "about", "against", "and", "are", "can", "does", "for", "from", "how",
    "into", "not", "the", "their", "this", "that", "what", "when", "where",
    "which", "while", "with", "would", "your",
})
_SOURCE_FIRST_STOP = _STOP | frozenset({
    "any", "between", "could", "did", "example", "examples", "have", "has",
    "many", "mean", "means", "much", "one", "primarily", "show", "shows",
    "stand", "stands", "thing", "things", "two", "use", "uses", "using",
})


@dataclass(frozen=True, slots=True)
class RelatedExcerptSelection:
    source: RetrievedKnowledgeChunk
    start_offset: int
    end_offset: int
    source_kind: str = "chunk"
    page_content: str | None = None

    @property
    def quote(self) -> str:
        if self.source_kind == "canonical_page":
            if self.page_content is None:
                raise ValueError("Canonical page source is unavailable.")
            return self.page_content[self.start_offset:self.end_offset]
        if self.source_kind != "chunk":
            raise ValueError("Unknown excerpt source kind.")
        return self.source.content[self.start_offset:self.end_offset]


def _query_terms(question: str) -> frozenset[str]:
    return frozenset(
        match.group(0).casefold() for match in _TERM.finditer(question)
        if match.group(0).casefold() not in _STOP
    )


def local_followup_query(
    question: str, history: Sequence[tuple[str, str]] = (),
) -> str | None:
    """Resolve a short referent locally to one explicit prior user acronym.

    Only the current question is sent for embedding. This bounded query is for
    local lexical retrieval/window ranking and never leaves the worker.
    Unknown or multiple possible referents return ``None`` instead of guessing.
    """

    if (
        not _REFERENT.search(question)
        or _ACRONYM.search(question)
        or len(_source_first_terms(question)) >= 2
    ):
        return question
    for role, content in reversed(history[-12:]):
        if role != "user" or not content:
            continue
        anchors = set(_ACRONYM.findall(content[:1_000]))
        if len(anchors) == 1:
            return next(iter(anchors))
        return None
    return None


def _source_first_terms(question: str) -> frozenset[str]:
    return frozenset(
        match.group(0).casefold() for match in _TERM.finditer(question)
        if match.group(0).casefold() not in _SOURCE_FIRST_STOP
    )


def _trim_bounds(content: str, start: int, end: int) -> tuple[int, int]:
    while start < end and content[start].isspace():
        start += 1
    while end > start and content[end - 1].isspace():
        end -= 1
    return start, end


def _window_bounds(content: str, anchor: int) -> tuple[int, int]:
    """Choose an exact slice near an anchor without exceeding the DB cap."""

    start = max(0, anchor - 80)
    if start:
        previous = max(content.rfind("\n", max(0, start - 80), start),
                       content.rfind(". ", max(0, start - 80), start))
        if previous >= 0:
            start = previous + (1 if content[previous] == "\n" else 2)
    end = min(len(content), start + _WINDOW_TARGET_CHARS)
    if end < len(content):
        trailing = content.find("\n", max(start + 80, end - 80),
                                min(len(content), start + MAX_RELATED_EXCERPT_CHARS))
        if trailing >= 0:
            end = trailing
        else:
            split = content.rfind(" ", max(start + 80, end - 60), end)
            if split > start:
                end = split
    return _trim_bounds(content, start, end)


def _best_window(content: str, terms: frozenset[str]) -> tuple[int, int] | None:
    if not content.strip():
        return None
    anchors = [0]
    if terms:
        for match in _TERM.finditer(content):
            if match.group(0).casefold() in terms:
                anchors.append(match.start())
                if len(anchors) >= 65:
                    break
    scored: list[tuple[int, int, int, int]] = []
    for anchor in anchors:
        start, end = _window_bounds(content, anchor)
        if not start < end or end - start > MAX_RELATED_EXCERPT_CHARS:
            continue
        present = {match.group(0).casefold() for match in _TERM.finditer(content[start:end])}
        score = len(present & terms)
        # Prefer distinct question terms, then the earliest exact source span.
        scored.append((-score, start, end, anchor))
    if not scored:
        return None
    _score, start, end, _anchor = min(scored)
    return start, end


def select_related_excerpts(
    question: str,
    chunks: Sequence[RetrievedKnowledgeChunk],
) -> tuple[RelatedExcerptSelection, ...]:
    """Return up to two exact windows from distinct ranked source pages."""

    terms = _query_terms(question)
    selected: list[RelatedExcerptSelection] = []
    seen_pages: set[tuple[object, int]] = set()
    for chunk in chunks[:5]:
        page = (chunk.document_id, chunk.page_number)
        if page in seen_pages:
            continue
        bounds = _best_window(chunk.content, terms)
        if bounds is None:
            continue
        start, end = bounds
        selected.append(RelatedExcerptSelection(chunk, start, end))
        seen_pages.add(page)
        if len(selected) == MAX_RELATED_EXCERPTS:
            break
    return tuple(selected)


def select_source_first_excerpts(
    question: str,
    chunks: Sequence[RetrievedKnowledgeChunk],
    *,
    history: Sequence[tuple[str, str]] = (),
) -> tuple[RelatedExcerptSelection, ...]:
    """Select at most three source-exact windows for browsing, not an answer.

    Requiring a small amount of question-term coverage prevents a completely
    unrelated top-five page from becoming a positive result. This is a
    conservative candidate rule; private displayed-window review still gates
    its use in the application.
    """

    local_query = local_followup_query(question, history)
    if local_query is None:
        return ()
    terms = _source_first_terms(local_query)
    if not terms:
        return ()
    minimum_hits = 1 if len(terms) == 1 else 2
    candidates: list[tuple[int, int, RelatedExcerptSelection]] = []
    seen_pages: set[tuple[object, int]] = set()
    for rank, chunk in enumerate(chunks[:5]):
        page = (chunk.document_id, chunk.page_number)
        if page in seen_pages:
            continue
        bounds = _best_window(chunk.content, terms)
        if bounds is None:
            continue
        start, end = bounds
        quote_terms = {match.group(0).casefold() for match in _TERM.finditer(chunk.content[start:end])}
        hits = len(quote_terms & terms)
        if hits < minimum_hits:
            continue
        candidates.append((-hits, rank, RelatedExcerptSelection(chunk, start, end)))
        seen_pages.add(page)
    candidates.sort(key=lambda item: (item[0], item[1]))
    return tuple(item[2] for item in candidates[:MAX_SOURCE_FIRST_EXCERPTS])


__all__ = [
    "MAX_RELATED_EXCERPTS", "MAX_SOURCE_FIRST_EXCERPTS", "MAX_RELATED_EXCERPT_CHARS",
    "RelatedExcerptSelection", "local_followup_query", "select_related_excerpts",
    "select_source_first_excerpts",
]
