"""Unshipped, local-only follow-up query candidate for a future Ask policy.

The active v3/v9 navigation policy is immutable. Keep this resolver detached
from its worker until a separately versioned policy is approved and measured.
It never sees source text or calls an embedding provider.
"""

from __future__ import annotations

from collections.abc import Sequence
import re

from app.ai.source_navigation import navigation_terms
from app.ai.source_structure import prior_entity, question_roles
from app.services.knowledge_retrieval import bounded_lexical_query


_OWNER_PRONOUNS = frozenset({"it", "this", "that"})
_AMBIGUOUS_OWNER = re.compile(r"^(?:it|its|their|these|those|they|them|this|that)\b", re.I)
_ELLIPTICAL_POSSESSIVE = re.compile(
    r"^(?:(?:and|but)\s+)?(?:what\s+(?:about|are|is)\s+)?its\s+"
    r"(?:limitations?|properties|applications?|examples?|definition|meaning|"
    r"mechanism|process|steps?|measurements?)\s*[?.!]*$",
    re.I,
)
_COMPETING_TOPIC = re.compile(
    r"\b(?:and|or|versus|vs|compare|compared|contrast|between|alongside|"
    r"against|with|relative|plus|including|except)\b"
    r"|[,/()]",
    re.I,
)
_EVENT_REFERENCE = re.compile(
    r"\b(?:happen(?:ed|s|ing)?|occur(?:red|s|ring)?|imply|result(?:ed|s|ing)?)\b",
    re.I,
)
_PRIOR_TOPIC = re.compile(r"^[A-Za-z][A-Za-z0-9' -]*$")
_ACRONYM = re.compile(r"\b[A-Z][A-Z0-9]{1,11}\b")
_GENERIC_EVENT_NOUN = re.compile(
    r"(?:the\s+)?(?:result|outcome|event|situation|thing|answer|question|process)",
    re.I,
)
_SAME_TURN_OWNER = re.compile(
    r"^(?:what\s+is|define|explain|describe)\s+(?P<owner>.+?)\s+and\s+"
    r"how\s+(?:does\s+)?it\b.+$",
    re.I,
)


def _bounded_local_query(query: str) -> str | None:
    if (len(query) > 4_000 or not navigation_terms(query)
        or len(bounded_lexical_query(query, 13).split()) > 12):
        return None
    return query


def _single_prior_topic(history: Sequence[tuple[str, str]]) -> str | None:
    """Accept one explicit owner from the immediately preceding user turn."""

    for role, content in reversed(history[-12:]):
        if role != "user":
            continue
        if not isinstance(content, str):
            return None
        prior = content.strip()
        if not prior or len(prior) > 1_000:
            return None
        core = prior.rstrip("?.! ")
        # Multiple clauses, a comparison or a coordinated noun phrase can
        # introduce another topic; never select one by position or recency.
        if (not core or re.search(r"[?!.;:\r\n]", core)
            or _COMPETING_TOPIC.search(core)):
            return None
        roles = question_roles(prior)
        if roles is not None:
            if (roles.domain or roles.conditions or roles.object_text
                or roles.required_text or roles.action not in ("", "work", "works")):
                return None
            entity = roles.entity
        else:
            entity = prior_entity(prior)
            if entity is None:
                return None
        if (not entity or len(entity) > 80 or len(entity.split()) > 3
            or not _PRIOR_TOPIC.fullmatch(entity)
            or _AMBIGUOUS_OWNER.search(entity)
            or _EVENT_REFERENCE.search(entity)
            or _GENERIC_EVENT_NOUN.fullmatch(entity)
            or len(set(_ACRONYM.findall(entity))) > 1):
            return None
        return entity
    return None


def candidate_navigation_query(
    question: str, history: Sequence[tuple[str, str]] = (),
) -> str | None:
    """Propose a bounded local query without changing the current provider input.

    A named current owner wins. Only a bare owner pronoun in a parsed question,
    or an explicitly possessed elliptical relation, may inherit a single
    topic from the latest prior user turn. All other discourse references ask
    for clarification. The worker must still send only ``question`` to the
    embedding provider when this candidate is eventually integrated.
    """

    current = question.strip()
    if not current or len(current) > 4_000:
        return None
    same_turn = _SAME_TURN_OWNER.fullmatch(current)
    if same_turn is not None:
        owner = same_turn["owner"].strip()
        if (len(owner) <= 80 and _PRIOR_TOPIC.fullmatch(owner)
            and not _COMPETING_TOPIC.search(owner)
            and not _AMBIGUOUS_OWNER.search(owner)):
            return _bounded_local_query(current)
        return None
    roles = question_roles(current)
    if roles is not None and roles.entity:
        owner = roles.entity.casefold()
        if owner in _OWNER_PRONOUNS:
            # Bare "it" in an event question is not a topic antecedent.
            if _EVENT_REFERENCE.search(current):
                return None
        elif _AMBIGUOUS_OWNER.search(roles.entity):
            if not _ELLIPTICAL_POSSESSIVE.fullmatch(current):
                return None
        else:
            return _bounded_local_query(current)
    elif not _ELLIPTICAL_POSSESSIVE.fullmatch(current):
        # An unparsed pronoun can refer to a whole event/answer, not a
        # syntactic topic slot. Explicit independent questions remain valid.
        if (re.search(r"\b(?:it|its|this|that|these|those|they|them)\b", current, re.I)
            or _EVENT_REFERENCE.search(current)):
            return None
        return _bounded_local_query(current)

    topic = _single_prior_topic(history)
    if topic is None:
        return None
    expanded = f"{topic} {current}"
    return _bounded_local_query(expanded)
