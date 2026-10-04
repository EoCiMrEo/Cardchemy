"""Bounded, provider-free navigation to related published lecture pages.

The returned previews are exact source slices for browsing. Relevance scores
never certify that the source answers the question. Every source is reauthorized
by the caller before its reference is persisted or opened.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
import re
from uuid import UUID

from app.ai.chunking import estimate_tokens
from app.ai.related_evidence import RelatedExcerptSelection, _best_window
from app.ai.source_structure import prior_entity
from app.services.knowledge_retrieval import ExpandedKnowledgeNeighbor, RetrievedKnowledgeChunk


SOURCE_NAVIGATION_POLICY_ID = "source_navigation_v9"
MAX_NAVIGATION_CHUNKS = 30
MAX_NAVIGATION_PAGES = 12
MAX_NAVIGATION_TOKENS = 8_192
MAX_INITIAL_PAGES = 8
MAX_INITIAL_TOKENS = 4_096
MAX_NAVIGATION_ANCHORS = 4
_WORD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.I)
_REFERENT = re.compile(r"\b(?:it|its|this|that|these|those|they|them)\b", re.I)
_ACRONYM = re.compile(r"\b[A-Z][A-Z0-9]{1,11}(?:-[A-Z0-9]{2,11})*\b")
_STOP = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "could",
    "do", "does", "for", "from", "how", "i", "in", "is", "it", "its",
    "of", "on", "or", "the", "their", "them", "these", "they", "this",
    "those", "that", "to", "was", "what", "when", "where", "which", "who",
    "why", "with", "would", "you", "your", "stand", "stands", "explain",
    "define", "definition", "mean", "means", "work", "works", "please",
    "about", "tell", "me", "more", "course", "lecture", "lectures",
    "material", "materials", "knowledge", "say", "says", "help", "understand",
})


def navigation_terms(text: str) -> frozenset[str]:
    return frozenset(match.group().casefold() for match in _WORD.finditer(text)
                     if match.group().casefold() not in _STOP)


def navigation_query(question: str, history: Sequence[tuple[str, str]] = ()) -> str | None:
    """Resolve a referent locally without imposing a question-relation taxonomy.

    The expanded query is used only by local search. The provider receives only
    the original current question. An unresolved follow-up asks for specificity
    instead of borrowing an arbitrary earlier topic.
    """

    question = question.strip()
    if not question:
        return None
    referent = _REFERENT.search(question)
    if referent is None:
        return question if navigation_terms(question) else None
    # An acronym after the pronoun can be the comparison target, not its
    # antecedent: "How does it compare to ROUGE?" still needs the prior BLEU.
    # Only a single acronym before the first pronoun is an explicit same-turn
    # antecedent; otherwise resolve from the bounded previous user turn.
    antecedents = {_match.group() for _match in _ACRONYM.finditer(question)
                   if _match.start() < referent.start()}
    if len(antecedents) == 1:
        return question if navigation_terms(question) else None
    if len(antecedents) > 1:
        return None
    same_turn = re.fullmatch(
        r"(?:what is|define|explain|describe)\s+(?P<entity>.+?)\s+and\s+how\s+(?:does\s+)?it\b.+",
        question, re.I,
    )
    if same_turn is not None:
        entity = same_turn["entity"].strip()
        if (len(entity) <= 160 and navigation_terms(entity)
            and not re.search(r"\b(?:and|or|versus|vs)\b|[,/]", entity, re.I)):
            return question
    for role, content in reversed(history[-12:]):
        if role != "user" or not content:
            continue
        bounded = content[:1_000]
        entity = prior_entity(bounded)
        if entity is None:
            acronyms = set(_ACRONYM.findall(bounded))
            if len(acronyms) == 1 and not re.search(r"\band\b|\bor\b|[,/]", bounded, re.I):
                entity = next(iter(acronyms))
        if entity is None:
            return None
        return f"{entity} {question}" if navigation_terms(entity) else None
    return None


_MULTIPLE_PRIOR_TOPICS = re.compile(
    r"\b(?:two|both|either|several|multiple|compare|comparing|versus|vs)\b", re.I,
)
_CURRENT_DOCUMENT_DEMONSTRATIVE = re.compile(
    r"\b(?:this|these|that|those)\s+(?:[a-z0-9-]+\s+){0,2}"
    r"(?:slide|slides|lecture|lectures|document|documents|notes|page|pages)\b",
    re.I,
)
_NAMED_FIRST_CLAUSE = re.compile(
    r"\b(?:a|an|the)\s+([a-z0-9-]+(?:\s+[a-z0-9-]+){0,3})\b", re.I,
)


def navigation_query_v4(
    question: str, history: Sequence[tuple[str, str]] = (),
) -> str | None:
    """Build a local-only retrieval query for the prospective source judge.

    The v3 resolver remains immutable. A named topic before a possessive
    referent is explicit in the current question. Otherwise one bounded prior
    user turn may guide *local* search when it has a distinctive topic and does
    not explicitly discuss multiple subjects. Neither the prior text nor this
    expanded query belongs in the source-judge request.
    """

    resolved = navigation_query(question, history)
    if resolved is not None:
        return resolved
    current = question.strip()
    referent = _REFERENT.search(current)
    if referent is None:
        return None
    # "These slides" and "this lecture" name the current published material;
    # they do not stand for a missing subject from an earlier chat turn. Keep
    # an actual topic in the same question mandatory, so "What do these slides
    # say?" still asks for clarification.
    if (referent.group().casefold() in {"this", "these", "that", "those"}
        and _CURRENT_DOCUMENT_DEMONSTRATIVE.match(current, referent.start())
        and len(navigation_terms(current)) >= 3):
        return current
    before = navigation_terms(current[:referent.start()])
    if referent.group().casefold() in {"its", "their", "they", "them"} and len(before) >= 2:
        return current
    # A single named subject in the first clause is a same-turn antecedent
    # for a later "it". A bare first-person pronoun or comparison target is
    # not enough to manufacture an antecedent.
    first_clause = current[:referent.start()].split(",", 1)[0]
    named = _NAMED_FIRST_CLAUSE.findall(first_clause)
    if (referent.group().casefold() == "it" and len(named) == 1
        and len(navigation_terms(named[0])) >= 2
        and not _MULTIPLE_PRIOR_TOPICS.search(first_clause)):
        return current
    for role, content in reversed(history[-12:]):
        if role != "user":
            continue
        prior = content[:1_000].strip()
        if not prior or _MULTIPLE_PRIOR_TOPICS.search(prior):
            return None
        terms = navigation_terms(prior)
        if len(terms) < 2 or not any(len(term) >= 8 for term in terms):
            return None
        return f"{prior} {current}" if len(prior) + len(current) + 1 <= 4_000 else None
    return None


@dataclass(frozen=True, slots=True)
class NavigationSelection:
    selections: tuple[RelatedExcerptSelection, ...]
    examined_chunks: int
    examined_pages: int
    examined_tokens: int
    status: str


def _page(chunk: RetrievedKnowledgeChunk) -> tuple[UUID, UUID, int]:
    return chunk.document_id, chunk.content_revision_id, chunk.page_number


def _bounded_initial(chunks: Sequence[RetrievedKnowledgeChunk]) -> tuple[RetrievedKnowledgeChunk, ...]:
    selected: list[RetrievedKnowledgeChunk] = []
    pages: set[tuple[UUID, UUID, int]] = set()
    seen: set[UUID] = set()
    tokens = 0
    for chunk in chunks[:20]:
        identity = _page(chunk)
        if (chunk.chunk_id in seen or chunk.token_count <= 0
            or tokens + chunk.token_count > MAX_INITIAL_TOKENS
            or identity not in pages and len(pages) >= MAX_INITIAL_PAGES):
            continue
        selected.append(chunk)
        seen.add(chunk.chunk_id)
        pages.add(identity)
        tokens += chunk.token_count
    return tuple(selected)


def _preview(
    query: str, chunk: RetrievedKnowledgeChunk, canonical: str | None,
) -> tuple[float, RelatedExcerptSelection] | None:
    content = canonical if canonical is not None else chunk.content
    terms = navigation_terms(query)
    bounds = _best_window(content, terms)
    if bounds is None:
        return None
    start, end = bounds
    hits = len(navigation_terms(content[start:end]) & terms)
    title_hits = len(navigation_terms(chunk.section or "") & terms)
    # Both search channels are relevance signals, never evidence sufficiency.
    # Neighbor pages retain unset search ranks; a concrete text match can still
    # promote a definition page above its introductory anchor.
    score = hits / max(1, len(terms)) + min(title_hits, 3) * 0.05
    score += min(1.0, max(0.0, chunk.fusion_score) * 30)
    # A search rank by itself is never a navigation match. This minimum topic
    # overlap rejects unrelated vector neighbors; it does not certify an answer.
    if not hits:
        return None
    return score, RelatedExcerptSelection(
        chunk, start, end, "canonical_page" if canonical is not None else "chunk", canonical,
    )


async def select_navigation_pages(
    query: str,
    chunks: Sequence[RetrievedKnowledgeChunk],
    expand: Callable[[tuple[RetrievedKnowledgeChunk, ...], int, int, int, int],
                     Awaitable[Sequence[ExpandedKnowledgeNeighbor]]],
    load_pages: Callable[[tuple[UUID, ...], int, int], Awaitable[Mapping[UUID, str]]],
) -> tuple[NavigationSelection, int]:
    """Inspect related anchors and ±2 pages before selecting three previews.

    A plausible initial match never short-circuits neighbor inspection. Initial
    and neighboring chunks plus inspected canonical pages share one cumulative
    token budget. Missing canonical pages use their exact eligible chunk preview.
    """

    initial = _bounded_initial(chunks)
    if not initial:
        return NavigationSelection((), 0, 0, 0, "no_candidate"), 0
    terms = navigation_terms(query)
    ranked = sorted(enumerate(initial), key=lambda item: (
        -len(navigation_terms(item[1].content + " " + (item[1].section or "")) & terms),
        -item[1].fusion_score, item[0],
    ))
    anchors: list[RetrievedKnowledgeChunk] = []
    anchor_pages: set[tuple[UUID, UUID, int]] = set()
    for _rank, chunk in ranked:
        if _page(chunk) in anchor_pages:
            continue
        anchors.append(chunk)
        anchor_pages.add(_page(chunk))
        if len(anchors) == MAX_NAVIGATION_ANCHORS:
            break
    examined = list(initial)
    seen = {chunk.chunk_id for chunk in initial}
    pages = {_page(chunk) for chunk in initial}
    tokens = sum(chunk.token_count for chunk in initial)
    # Read canonical anchor pages before neighbors can consume the remaining
    # budget. Include every initial chunk on an anchor page so contradictory
    # copies cannot be hidden by the page-level anchor deduplication.
    accepted_pages: dict[tuple[UUID, UUID, int], str] = {}
    conflicting_pages: set[tuple[UUID, UUID, int]] = set()

    def accept_pages(
        source_chunks: Sequence[RetrievedKnowledgeChunk], copies: Mapping[UUID, str],
    ) -> None:
        nonlocal tokens
        for source_chunk in source_chunks:
            canonical = copies.get(source_chunk.chunk_id)
            if not isinstance(canonical, str) or not canonical.strip():
                continue
            identity = _page(source_chunk)
            if identity in conflicting_pages:
                continue
            existing = accepted_pages.get(identity)
            if existing is not None:
                if existing != canonical:
                    conflicting_pages.add(identity)
                    del accepted_pages[identity]
                continue
            page_tokens = estimate_tokens(canonical)
            if tokens + page_tokens <= MAX_NAVIGATION_TOKENS:
                accepted_pages[identity] = canonical
                tokens += page_tokens

    anchor_scoped = tuple(chunk for anchor in anchors for chunk in initial
                          if _page(chunk) == _page(anchor))
    available = MAX_NAVIGATION_TOKENS - tokens
    if available > 0:
        accept_pages(anchor_scoped, await load_pages(
            tuple(chunk.chunk_id for chunk in anchor_scoped), len(anchor_pages), available,
        ))

    available = MAX_NAVIGATION_TOKENS - tokens
    anchor_tokens = sum(chunk.token_count for chunk in anchors)
    neighbors = (await expand(
        tuple(anchors), 2, len(anchors) + MAX_NAVIGATION_CHUNKS - len(initial),
        len(anchor_pages) + MAX_NAVIGATION_PAGES - len(pages), anchor_tokens + available,
    ) if available > 0 else ())
    for neighbor in neighbors:
        chunk = neighbor.chunk
        identity = _page(chunk)
        if (chunk.chunk_id in seen or chunk.token_count <= 0
            or len(examined) >= MAX_NAVIGATION_CHUNKS
            or identity not in pages and len(pages) >= MAX_NAVIGATION_PAGES
            or tokens + chunk.token_count > MAX_NAVIGATION_TOKENS):
            continue
        examined.append(chunk)
        seen.add(chunk.chunk_id)
        pages.add(identity)
        tokens += chunk.token_count
    remaining = MAX_NAVIGATION_TOKENS - tokens
    pending = tuple(chunk for chunk in examined
                    if _page(chunk) not in accepted_pages and _page(chunk) not in conflicting_pages)
    pending_pages = len({_page(chunk) for chunk in pending})
    if remaining > 0 and pending_pages:
        accept_pages(pending, await load_pages(
            tuple(chunk.chunk_id for chunk in pending),
            min(MAX_NAVIGATION_PAGES - len(accepted_pages), pending_pages), remaining,
        ))
    # A loader is a trusted service boundary, but count/validate returned source
    # pages again before using them. Contradictory copies are never cited.
    candidates: list[tuple[float, int, RelatedExcerptSelection]] = []
    for rank, chunk in enumerate(examined):
        canonical = accepted_pages.get(_page(chunk))
        result = _preview(query, chunk, canonical)
        if result is not None:
            score, selection = result
            candidates.append((-score, rank, selection))
    candidates.sort(key=lambda item: (item[0], item[1]))
    selected: list[RelatedExcerptSelection] = []
    selected_pages: set[tuple[UUID, UUID, int]] = set()
    for _score, _rank, selection in candidates:
        identity = _page(selection.source)
        if identity in selected_pages or identity in conflicting_pages:
            continue
        selected_pages.add(identity)
        selected.append(selection)
        if len(selected) == 3:
            break
    return NavigationSelection(tuple(selected), len(examined), len(pages), tokens,
                               "related_pages" if selected else "no_candidate"), 2
