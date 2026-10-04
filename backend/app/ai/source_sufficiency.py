"""Conservative, local question-to-source qualification for source-only Ask.

This selector finds *candidate* lecture units that state the requested kind of
information. It does not prove semantic entailment or produce an answer. All
returned spans are exact slices of an indexed chunk or its authorized canonical
page. Section metadata is never concatenated into pretend source text.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import re
from typing import Mapping, Sequence
from uuid import UUID

from app.ai.chunking import _looks_like_heading, estimate_tokens

from app.ai.source_structure import (
    question_roles, prior_entity, structural_units, qualifies_structure,
    ambiguous_acronym, lexical_words, operation_matches,
)

from app.ai.related_evidence import (
    MAX_RELATED_EXCERPT_CHARS,
    MAX_SOURCE_FIRST_EXCERPTS,
    RelatedExcerptSelection,
)
from app.services.knowledge_retrieval import ExpandedKnowledgeNeighbor, RetrievedKnowledgeChunk


SOURCE_SELECTION_POLICY_ID = "source_relation_units_v7"
MAX_EXAMINED_CHUNKS = 30
MAX_EXAMINED_PAGES = 12
MAX_EXAMINED_TOKENS = 8_192
MAX_INITIAL_PAGES = 8
MAX_INITIAL_TOKENS = 4_096
MAX_PARTIAL_ANCHORS = 4
MAX_PARTIAL_ANCHOR_PAGES = 4
MAX_PARTIAL_ANCHOR_TOKENS = 4_096

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9-]*")
_NUMBER = re.compile(r"(?<!\w)\d+(?:\.\d+)?(?!\w)")
_ACRONYM = re.compile(r"\b[A-Z][A-Z0-9]{1,11}(?:-[A-Z0-9]{2,11})*\b")
_PRONOUN = re.compile(r"\b(?:it|its|this|that|these|those|they|them)\b", re.I)
_UNIT = re.compile(r"[^\n.!?]+(?:[.!?](?!\w)|$)")
_STOP = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "between", "by", "can",
    "do", "does", "for", "from", "how", "in", "into", "is", "it", "its",
    "of", "on", "or", "rather", "that", "the", "their", "these", "this",
    "those", "to", "two", "use", "uses", "using", "was", "what", "when",
    "which", "why", "with", "without", "would", "your", "stand", "stands",
    "full", "form", "meaning", "define", "definition", "measure", "measures",
    "metric", "function", "process", "steps", "work", "works", "explain", "follow", "follows",
    "primarily", "mainly", "chiefly", "usually", "typically", "than",
})
_TOPIC_ONLY = re.compile(r"\b(?:discussed|mentioned|introduced|covered|listed|example|topic)\b", re.I)
_RELATION_CUES = {
    "acronym": re.compile(r"\b(?:stands?\s+for|means?|short\s+for|abbreviat(?:ion|ed\s+as))\b", re.I),
    "definition": re.compile(r"\b(?:is|are|refers?\s+to|defined\s+as|means?)\b", re.I),
    "mechanism": re.compile(r"\b(?:uses?|works?\s+by|operates?\s+by|based\s+on|applies?)\b", re.I),
    "measurement": re.compile(r"\b(?:measures?|compares?|quantif(?:y|ies)|evaluates?|focus(?:es)?\s+on)\b", re.I),
    "reason": re.compile(r"\b(?:because|due\s+to|since|therefore|as\s+a\s+result)\b", re.I),
    "process": re.compile(r"\b(?:steps?|first|then|finally|followed\s+by|transforms?)\b", re.I),
}
_HEADING_LABELS = {
    "acronym": r"(?:full form|expansion|abbreviation)",
    "definition": r"(?:definition|meaning)",
    "mechanism": r"(?:mechanism|how it works)",
    "measurement": r"(?:measurement|what it measures)",
    "reason": r"(?:reason|why)",
    "process": r"(?:process|steps|stages)",
    "property": r"(?:limitations?|disadvantages?|properties)",
    "application": r"(?:applications?|examples?|use cases?)",
}
_ACRONYM_PAREN = re.compile(r"\b([A-Z][a-z]+(?:[\s-]+[A-Z]?[a-z]+){1,8})\s*\(([A-Z][A-Z0-9-]{1,15})\)")
_ACRONYM_PREFIX_PAREN = re.compile(
    r"\b([A-Z][A-Z0-9-]{1,15})\s*\(([A-Z][a-z]+(?:[\s-]+[A-Z]?[a-z]+){1,8})\)"
)
_PROPERTY_CUES = re.compile(
    r"\b(?:ignores?|discards?|loses?|lost|do(?:es)?\s+not\s+(?:preserve|retain)|fails?\s+to\s+(?:preserve|retain)|"
    r"(?:not\s+)?sensitive\s+to|(?:not\s+(?:ideal|suitable)|unsuitable)\s+for|"
    r"(?:ideal|suitable)\s+for|(?:limitations?|disadvantages?)\s+(?:is|are|include))\b", re.I,
)
_APPLICATION_CUES = re.compile(
    r"\b(?:used\s+(?:for|to|in)|applied\s+(?:to|in|for)|applications?\s+(?:include|is|are)|"
    r"examples?\s+(?:include|is|are)|use\s+cases?\s+(?:include|is|are))\b", re.I,
)
_INVERSE_APPLICATION = re.compile(
    r"\bis\s+an?\s+(?:application|example|use case)\s+of\s+([^.!?;\n]+)", re.I,
)
_EXAMPLE_ACTION = re.compile(
    r"\b(?:cluster(?:ing)?|analy[sz](?:e|es|ing|is)|organiz(?:e|es|ing)|categor(?:ize|izes|izing)|"
    r"classif(?:y|ies|ying|ication)|summari[sz](?:e|es|ing|ation)|identif(?:y|ies|ying|ication)|"
    r"extract(?:s|ing|ion)?|discover(?:s|ing|y)?|detect(?:s|ing|ion)?|recommend(?:s|ing|ation)?)\b", re.I,
)
_RELATION_SCAFFOLD = frozenset({
    "property", "properties", "limitation", "limitations", "disadvantage", "disadvantages",
    "model", "models", "means", "lost", "loss", "noted", "known", "being", "sensitive",
    "ideal", "suitable", "unsuitable", "not", "example", "examples", "application",
    "applications", "mentioned", "domain", "domains", "give", "name", "applied", "used",
    "information", "described", "material", "one", "similarity",
    "ignore", "ignores", "discard", "discards", "lose", "loses", "fail", "fails", "retain", "preserve",
})
_REASON_ACTION_TERMS = frozenset({
    "use", "uses", "remove", "removes", "apply", "applies", "work", "works",
    "cause", "causes", "produce", "produces", "help", "helps", "matter",
    "important", "emphasize", "emphasizes",
})
_INTENT_FORMS = {
    "definition": re.compile(r"\bwhich\s+(?:idea|concept)\s+does\s+(.+?)\s+describe\b", re.I),
    "application": re.compile(r"\bwhich\s+(?:task|activity)\s+can\s+(.+?)\s+support\b", re.I),
}


@dataclass(frozen=True, slots=True)
class QuestionDescriptor:
    original_question: str
    local_query: str | None
    entity: str | None
    relation: str
    qualifiers: tuple[str, ...]
    ambiguous: bool
    conditions: tuple[str, ...] = ()
    requested_action: str = ""


@dataclass(frozen=True, slots=True)
class SourceQualification:
    selections: tuple[RelatedExcerptSelection, ...]
    partial_found: bool
    partial_anchors: tuple[RetrievedKnowledgeChunk, ...]
    examined_chunks: int
    examined_pages: int
    examined_tokens: int
    status: str  # explicit_relation_candidate, partial_context, no_matching_relation, ambiguous


def _terms(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(word.group().casefold() for word in _WORD.finditer(text)
                               if word.group().casefold() not in _STOP))


def _relation(question: str) -> str:
    q = question.casefold()
    # One source relation must not stand in for a second requested relation.
    # The single-relation selector leaves coordinated interrogatives unknown.
    if re.search(r"\band\s+(?:what|which|how|why|define|explain|describe|show)\b", q):
        return "unknown"
    if re.search(r"\b(?:stand for|stands for|full form|expand|expansion of|abbreviation for)\b", q):
        return "acronym"
    if re.search(
        r"(?i:\bwhat\s+does)\s+[A-Z][A-Z0-9]{1,11}(?:-[A-Z0-9]{2,11})*\s+(?i:mean\b)",
        question,
    ):
        return "acronym"
    if (re.search(r"\b(?:applications?|use cases?|example application)\b", q)
        or re.search(r"\bwhich\s+(?:task|activity)\s+can\s+.+?\s+support\b", q)):
        return "application"
    if (re.search(r"\b(?:limitations?|disadvantages?|properties|property)\b", q)
        or re.search(r"\binformation\s+(?:does|do)\s+.+?\s+(?:ignore|discard|lose|fail\s+to\s+(?:retain|preserve))\b", q)
        or re.search(r"\bwhich\s+.+?\b(?:metric|model)\s+is\s+(?:noted|known|sensitive|unsuitable|ideal)\b", q)):
        return "property"
    if re.search(r"\b(?:why|reason|cause)\b", q):
        return "reason"
    if re.search(r"\b(?:steps|process|how to|sequence|stages)\b", q):
        return "process"
    if re.search(r"\b(?:measure|compare|similarity metric|focus on|evaluate|quantify)\b", q):
        return "measurement"
    if (re.search(r"\b(?:how does|how do|work|mechanism|function does|uses to)\b", q)
        or re.search(r"\bwhat\s+does\s+.+?\s+use\s+to\b", q)):
        return "mechanism"
    if (re.search(r"\b(?:what is|what are|define|definition|refers to|meaning of|say about)\b", q)
        or re.search(r"\bwhich\s+(?:idea|concept)\s+does\s+.+?\s+describe\b", q)):
        return "definition"
    return "unknown"


def _explicit_entity(question: str, relation: str) -> str | None:
    if relation == "property":
        loss = re.search(
            r"\binformation\s+(?:does|do)\s+(.+?)\s+(?:ignores?|discards?|loses?|fails?\s+to\s+(?:retain|preserve))\b",
            question, re.I,
        )
        if loss:
            return loss.group(1).strip()
        match = re.search(
            r"\b(?:limitations?|disadvantages?|properties|property)\s+of\s+(.+?)"
            r"(?:\s+(?:models?\s+)?(?:means?(?:\s+that)?|is|are|in|for)|\?|$)", question, re.I,
        )
        if match:
            return re.sub(r"\s+models?$", "", match.group(1).strip(), flags=re.I)
    if relation == "application":
        task = re.search(r"\bwhich\s+(?:task|activity)\s+can\s+(.+?)\s+support\b", question, re.I)
        if task:
            return task.group(1).strip()
        match = re.search(
            r"\b(?:applications?|use\s+cases?|examples?)\s+(?:of|for)\s+(.+?)"
            r"(?:\s+(?:(?:mentioned|described)\s+)?(?:for|in|to)\s+|[.?]|$)", question, re.I,
        )
        if match:
            return match.group(1).strip()
    if relation == "process":
        follows = re.search(r"\bwhat\s+steps\s+does\s+(.+?)\s+follow\b", question, re.I)
        if follows:
            return follows.group(1).strip()
        process = re.search(r"\b(?:steps|process|stages)\s+(?:in|of|for)\s+(.+?)(?:\?|$)", question, re.I)
        if process:
            return process.group(1).strip()
    if relation == "acronym":
        match = re.search(r"\bwhat\s+does\s+(.+?)\s+(?:stands?\s+for|mean)\b", question, re.I)
        if match:
            return match.group(1).strip()
    if relation == "definition":
        concept = re.search(r"\bwhich\s+(?:idea|concept)\s+does\s+(.+?)\s+describe\b", question, re.I)
        if concept:
            return concept.group(1).strip()
        explicit = re.search(r"\b(?:define|definition\s+of|meaning\s+of)\s+(.+?)(?:[?.!]|$)", question, re.I)
        if explicit:
            return explicit.group(1).strip()
        defined = re.search(r"\bwhat\s+is\s+(?:the\s+)?definition\s+of\s+(.+?)(?:\?|$)", question, re.I)
        if defined:
            return defined.group(1).strip()
        about = re.search(r"\bsay\s+about\s+(.+?)(?:\?|$)", question, re.I)
        if about:
            return about.group(1).strip()
    if relation in {"definition", "mechanism", "measurement", "reason", "process"}:
        patterns = (
            r"\bwhat\s+(?:is|are)\s+(.+?)(?:\?|$)",
            r"\bhow\s+does\s+(.+?)\s+(?:work|use|operate|produce|calculate)\b",
            r"\bwhat\s+function\s+does\s+(.+?)\s+use\b",
            r"\bwhat\s+does\s+(.+?)\s+(?:(?:primarily|mainly|chiefly|usually|typically)\s+)?(?:measure|compare|focus\s+on|evaluate|quantify)\b",
            r"\bhow\s+does\s+(.+?)\s+(?:measure|compare|focus\s+on|evaluate|quantify)\b",
            r"\bwhat\s+does\s+(.+?)\s+use\s+to\b",
            r"\bwhich\s+.+?\s+does\s+(.+?)\s+(?:compare|measure|evaluate)\b",
            r"\bwhy\s+(?:does|is|are)\s+(.+?)\s+(?:use|work|cause|matter|important)\b",
        )
        for pattern in patterns:
            match = re.search(pattern, question, re.I)
            if match:
                return match.group(1).strip()
    acronyms = set(_ACRONYM.findall(question))
    if len(acronyms) == 1:
        return next(iter(acronyms))
    return None


def describe_question(
    question: str, history: Sequence[tuple[str, str]] = (),
) -> QuestionDescriptor:
    """Keep the current relation while resolving only an unambiguous entity locally."""

    question = question.strip()
    roles = question_roles(question)
    relation = roles.relation if roles else _relation(question)
    entity = roles.entity if roles else _explicit_entity(question, relation)
    if entity and _PRONOUN.fullmatch(entity):
        entity = None
    unresolved = bool(_PRONOUN.search(question)) and entity is None
    if unresolved:
        for role, content in reversed(history[-12:]):
            if role != "user" or not content:
                continue
            entity = prior_entity(content[:1_000])
            if entity is None:
                anchors = set(_ACRONYM.findall(content[:1_000]))
                if len(anchors) == 1 and not re.search(r"\b(?:and|or|versus|vs)\b|[,/]", content, re.I):
                    entity = next(iter(anchors))
            break
    ambiguous = not question or relation == "unknown" or (unresolved and entity is None)
    local_query = None if ambiguous else (
        _PRONOUN.sub(entity, question, count=1) if unresolved and entity else question
    )
    entity_terms = set(_terms(entity or ""))
    # Remove only the matched request prefix/auxiliary verb. The same words
    # in a suffix (e.g. customer support or task scheduling) remain factual
    # qualifiers; family-wide stopwords would silently change the question.
    qualifier_text = roles.required_text if roles else question
    intent_form = _INTENT_FORMS.get(relation)
    intent_match = intent_form.search(question) if intent_form else None
    if intent_match and roles is None:
        qualifier_text = (question[:intent_match.start()] + intent_match.group(1)
                          + question[intent_match.end():])
    qualifiers = tuple(term for term in _terms(qualifier_text) if term not in entity_terms
                       and (relation not in {"property", "application"} or term not in _RELATION_SCAFFOLD))
    return QuestionDescriptor(question, local_query, entity, relation, qualifiers, ambiguous,
                              roles.conditions if roles else (), roles.action if roles else "")


def _units(content: str) -> tuple[tuple[int, int], ...]:
    units: list[tuple[int, int]] = []
    for line in re.finditer(r"[^\n]+", content):
        for unit in _UNIT.finditer(line.group()):
            start, end = line.start() + unit.start(), line.start() + unit.end()
            while start < end and content[start].isspace():
                start += 1
            while end > start and content[end - 1].isspace():
                end -= 1
            if start < end:
                units.append((start, end))
    return tuple(units)


def _heading_units(content: str, descriptor: QuestionDescriptor) -> tuple[tuple[int, int], ...]:
    """Add contiguous same-chunk title-owned relation windows."""

    if descriptor.relation not in _HEADING_LABELS:
        return ()
    lines = tuple(re.finditer(r"[^\n]+", content))
    units: list[tuple[int, int]] = []
    for index, heading in enumerate(lines):
        title = heading.group().strip().lstrip("# ").rstrip(":")
        if (not title or len(title) > 120 or re.search(r"[.!?]", title)
            or re.match(r"[-*•]", title) or len(_WORD.findall(title)) > 12
            or _PROPERTY_CUES.search(title) or _APPLICATION_CUES.search(title)):
            continue
        if descriptor.entity and not re.search(
            r"(?<!\w)" + re.escape(descriptor.entity) + r"(?!\w)", title, re.I,
        ):
            continue
        start = heading.start() + len(heading.group()) - len(heading.group().lstrip())
        for following in lines[index + 1:index + 4]:
            text = following.group().strip()
            relation_heading = bool(re.fullmatch(
                _HEADING_LABELS[descriptor.relation] + r"\s*:?", text, re.I,
            ))
            continuation = bool(re.match(r"[-*•]|\d+[.)]", text)
                                or _PROPERTY_CUES.search(text) or _APPLICATION_CUES.search(text)
                                or any(cue.search(text) for cue in _RELATION_CUES.values()))
            # A fresh title owns its own following material. Do not cross it.
            if not relation_heading and not continuation:
                break
            end = following.end()
            if end - start > MAX_RELATED_EXCERPT_CHARS:
                break
            if continuation:
                units.append((start, end))
                # Other relations need one title-owned assertion, not a bag of
                # sibling bullets whose qualifiers could combine falsely.
                # A process can show a bounded explicit sequence across steps.
                if descriptor.relation != "process":
                    break
    return tuple(units)


def _page_identity(chunk: RetrievedKnowledgeChunk) -> tuple[UUID, UUID, int]:
    return chunk.document_id, chunk.content_revision_id, chunk.page_number


def _canonical_anchor_bounds(
    chunk: RetrievedKnowledgeChunk, page: str,
) -> tuple[int, int, int | None] | None:
    """Locate literal chunk text, allowing only differences in whitespace.

    An ambiguous body cannot establish which title owns the discovery anchor.
    A section must be the current preceding canonical heading, never a matching
    label elsewhere on the page. All offsets remain against the original page.
    """

    pieces = chunk.content.split()
    if not pieces:
        return None
    matches = tuple(re.finditer(r"\s+".join(re.escape(piece) for piece in pieces), page))
    if len(matches) != 1:
        return None
    body = matches[0]
    if not chunk.section:
        return body.start(), body.end(), None
    section = " ".join(chunk.section.split())
    owner: re.Match[str] | None = None
    for line in re.finditer(r"[^\n]+", page[:body.start()]):
        text = line.group().strip()
        if " ".join(text.split()) == section or _looks_like_heading(text):
            owner = line
    if owner is None or " ".join(owner.group().split()) != section:
        return None
    owner_start = owner.start() + len(owner.group()) - len(owner.group().lstrip())
    return body.start(), body.end(), owner_start


def _canonical_units(
    chunk: RetrievedKnowledgeChunk, page: str, descriptor: QuestionDescriptor,
) -> tuple[tuple[int, int, bool], ...]:
    bounds = _canonical_anchor_bounds(chunk, page)
    if bounds is None:
        return ()
    body_start, body_end, owner_start = bounds
    direct = tuple((start, end, False) for start, end in _units(page)
                   if body_start <= start and end <= body_end)
    heading = tuple((start, end, True) for start, end in _heading_units(page, descriptor)
                    if owner_start == start and end > body_start and end <= body_end)
    return (*direct, *heading)


def _all_requested_terms(unit: str, descriptor: QuestionDescriptor) -> bool:
    required = set(descriptor.qualifiers)
    present = set(_terms(unit))
    # An explicit A-or-B domain request needs one named alternative, not both.
    alternative = re.search(r"\b([A-Za-z][A-Za-z-]*)\s+or\s+([A-Za-z][A-Za-z-]*)\b",
                            descriptor.original_question, re.I)
    if alternative and descriptor.relation == "application":
        choices = {alternative.group(1).casefold(), alternative.group(2).casefold()}
        if choices.issubset(required):
            return bool(choices & present) and (required - choices).issubset(present)
    return (bool(required) or descriptor.entity is not None) and required.issubset(present)


def _property_polarity_matches(unit: str, question: str) -> bool:
    if re.search(r"\b(?:may|might|could|unless|if)\b", unit, re.I):
        return False
    if re.search(r"\b(?:not|never)\s+(?:ignore|discard|lose|sensitive)\b", unit, re.I):
        if not re.search(r"\b(?:not|never)\s+(?:ignore|discard|lose|sensitive)\b", question, re.I):
            return False
    requested_negative = re.search(r"\b(?:not|never)\s+(ignore|discard|lose|sensitive)\b", question, re.I)
    if requested_negative and not re.search(
        r"\b(?:not|never)\s+" + re.escape(requested_negative.group(1)) + r"\b", unit, re.I,
    ):
        return False
    if re.search(r"\b(?:lost|loss|ignores?|discards?|loses?|fails?\s+to\s+(?:retain|preserve))\b", question, re.I):
        if not re.search(r"\b(?:ignores?|discards?|loses?|lost|do(?:es)?\s+not\s+(?:preserve|retain)|"
                         r"fails?\s+to\s+(?:preserve|retain))\b", unit, re.I):
            return False
    if re.search(r"\b(?:not\s+(?:ideal|suitable)|unsuitable)\b", question, re.I):
        if not re.search(r"\b(?:not\s+(?:ideal|suitable)|unsuitable)\s+for\b", unit, re.I):
            return False
    elif re.search(r"\b(?:ideal|suitable)\b", question, re.I):
        if re.search(r"\b(?:not\s+(?:ideal|suitable)|unsuitable)\b", unit, re.I):
            return False
    if re.search(r"\bsensitive\b", question, re.I):
        if not re.search(r"\bsensitive\s+to\b", unit, re.I):
            return False
    return True


def _qualifies_new_relation(unit: str, descriptor: QuestionDescriptor, *, heading_owned: bool) -> bool:
    relation = descriptor.relation
    if re.search(r"\b(?:discussed|mentioned|introduced|covered|listed)\b", unit, re.I):
        return False
    if re.search(r"[;]|\b(?:whereas|while|but|unlike|compared)\b", unit, re.I):
        return False
    # Preserve the requested sparse, high-dimensional phrase. Other comma
    # clauses can introduce a new property owner; leave them unqualified.
    if relation == "property" and re.search(r",(?!\s*high-dimensional\b)", unit, re.I):
        return False
    entity_match = (re.search(r"(?<!\w)" + re.escape(descriptor.entity) + r"(?!\w)", unit, re.I)
                    if descriptor.entity else None)
    remaining = unit[entity_match.end():] if entity_match else unit
    if re.search(r"\band\s+[A-Za-z][^,.;\n]{0,70}?\s+(?:is|are|uses?|ignores?|measures?)\b", remaining, re.I):
        return False
    pattern = _PROPERTY_CUES if relation == "property" else _APPLICATION_CUES
    if relation == "property" and descriptor.entity is None:
        if heading_owned:
            title_subject = unit.split("\n", 1)[0].strip().lstrip("# ").split(":", 1)[0].strip()
            if not _named_measurement_subject(title_subject):
                return False
        elif not any(_named_measurement_subject(unit[:cue.start()]) for cue in pattern.finditer(unit)):
            return False
    heading_example = bool(heading_owned and re.search(
        r"\b(?:applications?|examples?|use cases?)\b", "\n".join(unit.split("\n")[:2]), re.I,
    ))
    heading_limitation = bool(heading_owned and re.search(
        r"\b(?:limitations?|disadvantages?)\b", unit.split("\n", 1)[0], re.I,
    ))
    body = unit.split("\n", 1)[1] if heading_owned else unit
    if heading_owned and "\n" in body and re.fullmatch(
        r"(?:applications?|examples?|use cases?|limitations?|disadvantages?)\s*:?",
        body.split("\n", 1)[0].strip(), re.I,
    ):
        body = body.split("\n", 1)[1]
    if not _all_requested_terms(body, descriptor):
        return False
    inverse = tuple(_INVERSE_APPLICATION.finditer(body)) if relation == "application" else ()
    inverse_owned = bool(inverse and descriptor.entity and all(
        match.group(1).strip().casefold() == descriptor.entity.casefold() for match in inverse
    ))
    if inverse and not inverse_owned:
        return False
    cues = tuple(pattern.finditer(body))
    if heading_owned:
        def owned(cue: re.Match[str]) -> bool:
            prefix = body[:cue.start()].strip().lstrip("-*• ")
            # An implicit bullet predicate belongs to its title only if no
            # unrelated noun phrase occurs before it.
            return not prefix or set(_terms(prefix)).issubset(set(descriptor.qualifiers))
        bound_cues = tuple(cue for cue in cues if owned(cue))
    else:
        def explicitly_bound(cue: re.Match[str]) -> bool:
            if _entity_bound(unit, descriptor.entity, cue):
                return True
            if relation != "application" or not descriptor.entity:
                return False
            entity = re.search(r"(?<!\w)" + re.escape(descriptor.entity) + r"(?!\w)", unit, re.I)
            return bool(entity and entity.end() <= cue.start()
                        and re.fullmatch(r"\s+can\s+be\s+", unit[entity.end():cue.start()], re.I))
        bound_cues = tuple(cue for cue in cues if explicitly_bound(cue))
    if relation == "property":
        # A slide can state a limitation in a bare bullet under its owning
        # title. Admit only an explicit negative/property predicate at the
        # start of that bullet; a second named subject cannot borrow the title.
        implicit_limitation = bool(heading_limitation and re.match(
            r"\s*[-*•]?\s*(?:no\b|not\b|sensitive\s+to\b|computationally\s+expensive\b|"
            r"unable\s+to\b|fails?\s+to\b)", body, re.I,
        ))
        return bool((bound_cues or implicit_limitation)
                    and _property_polarity_matches(unit, descriptor.original_question))
    if re.search(r"\b(?:not|never|may|might|could|if|unless)\b", body, re.I):
        return False
    # A bare example bullet may inherit its Applications title, but a bullet
    # that explicitly assigns the relation to another entity cannot do so.
    implicit_example = bool(heading_example and not cues and _EXAMPLE_ACTION.match(body.strip().lstrip("-*• ")))
    return bool((bound_cues or implicit_example or inverse_owned) and _EXAMPLE_ACTION.search(body)
                and len(_terms(body)) >= 3)


def _entity_bound(unit: str, entity: str | None, cue: re.Match[str]) -> bool:
    if not entity:
        return True
    match = re.search(r"(?<!\w)" + re.escape(entity) + r"(?!\w)", unit, re.I)
    if match is None:
        return False
    # The requested entity must own the predicate, not occur after another
    # subject's relation cue or merely in a second, unrelated clause.
    between = unit[match.end():cue.start()] if match.end() <= cue.start() else ""
    # Only a short copula/adverb bridge may separate the entity from its
    # predicate. A second noun phrase or relative clause can assign the cue
    # to another entity even without sentence punctuation.
    if cue.start() < match.end() or not re.fullmatch(
        r"\s*(?:(?:is|are|primarily|mainly|chiefly|usually|typically|often|generally|directly|also)\s+)*",
        between, re.I,
    ):
        return False
    return True


def _heading_body(unit: str, relation: str) -> str:
    body = unit.split("\n", 1)[1]
    if "\n" in body and re.fullmatch(
        _HEADING_LABELS[relation] + r"\s*:?", body.split("\n", 1)[0].strip(), re.I,
    ):
        body = body.split("\n", 1)[1]
    return body


def _heading_line_owner(line: str, cue: re.Match[str], descriptor: QuestionDescriptor) -> bool:
    """A bullet predicate may inherit its title only without another subject."""

    prefix = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line[:cue.start()]).strip()
    if not prefix:
        return True
    entity = descriptor.entity
    if entity and re.fullmatch(
        re.escape(entity) + r"(?:\s+(?:is|are|primarily|mainly|usually|directly|also))*",
        prefix, re.I,
    ):
        return True
    # A reason bullet can begin with the title subject's action: the action
    # itself then precedes "because". Do not accept a new named subject.
    if descriptor.relation == "reason" and re.match(
        r"^(?:removes?|uses?|applies?|helps?|reduces?|improves?|works?|produces?)\b",
        prefix, re.I,
    ) and not re.search(r"\b(?:and|but|whereas|while)\b", prefix, re.I):
        return True
    if descriptor.relation == "process" and re.match(r"^(?:first|then)\b", prefix, re.I):
        return not re.search(r"\b(?:and|but|whereas|while)\b", prefix, re.I)
    return False


def _reason_object_before_cue(prefix: str, descriptor: QuestionDescriptor) -> bool:
    # A word from the question that appears only in a different entity's
    # because-clause does not establish the requested action's reason.
    objects = set(descriptor.qualifiers) - _REASON_ACTION_TERMS
    return not objects or objects.issubset(_terms(prefix))


def _named_measurement_subject(subject: str) -> bool:
    name = subject.strip()
    terms = set(_terms(name))
    return bool(
        (_ACRONYM.fullmatch(name) or re.search(r"\b(?:similarity|distance|metric|score)\b", name, re.I))
        and terms - {"similarity", "distance", "metric", "metrics", "score", "scores"}
        and not re.search(r"\b(?:and|or|of|versus|vs\.?)\b|[,/]", name, re.I)
    )


def _qualifies_heading_relation(unit: str, descriptor: QuestionDescriptor) -> bool:
    """Qualify a title plus its literal bullet for the six original relations."""

    relation = descriptor.relation
    title = unit.split("\n", 1)[0]
    title_subject = title.strip().lstrip("# ").split(":", 1)[0].strip()
    body = _heading_body(unit, relation)
    if not body.strip() or not _all_requested_terms(body, descriptor):
        return False
    # The subject of an implicit bullet is the title's named subject, not a
    # term merely mentioned later in an "evaluation of X" heading.
    if descriptor.entity and title_subject.casefold() != descriptor.entity.casefold():
        return False
    if relation == "measurement" and descriptor.entity is None:
        if not _named_measurement_subject(title_subject):
            return False
    if re.search(r"\b(?:not|never|may|might|could|if|unless|incorrect|false|wrong)\b", body, re.I):
        return False
    if re.search(r"[;]|\b(?:whereas|while|but|unlike|compared)\b", body, re.I):
        return False
    if _TOPIC_ONLY.search(body):
        return False
    # Every overt subject/predicate line in the displayed window must belong
    # to the title. A later sufficient bullet cannot borrow an earlier wrong
    # subject while keeping that earlier bullet in the quoted span.
    for raw_line in body.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        for pattern in _RELATION_CUES.values():
            for cue in pattern.finditer(line):
                if not _heading_line_owner(line, cue, descriptor):
                    return False
    if relation == "acronym":
        entity = descriptor.entity
        if not entity or not _ACRONYM.fullmatch(entity):
            return False
        if any(match.group(2) == entity and len(_terms(match.group(1))) >= 2
               for match in _ACRONYM_PAREN.finditer(body)):
            return True
        if any(match.group(1) == entity and len(_terms(match.group(2))) >= 2
               for match in _ACRONYM_PREFIX_PAREN.finditer(body)):
            return True
    if relation == "process":
        numbered = [re.sub(r"^\s*\d+[.)]\s*", "", line).strip()
                    for line in body.split("\n") if re.match(r"^\s*\d+[.)]", line)]
        if (len(numbered) >= 2 and all(re.match(
                r"^(?:split|lowercase|remove|normalize|tokenize|convert|replace|compute|"
                r"apply|identify|extract|select|assign|iterate|update|calculate|"
                r"generate|filter|lemmatize|stem|clean|map|encode|decode|train|predict)\b",
                item, re.I,
            ) and len(_terms(item)) >= 2 for item in numbered)):
            return True
    cues = tuple(_RELATION_CUES[relation].finditer(body))
    if relation == "process" and not re.search(
        r"\b(?:first[\s\S]{1,300}then|steps?\s+(?:are|include)|"
        r"followed\s+by|transforms?[\s\S]{1,120}into)\b", body, re.I,
    ):
        return False
    if relation == "definition" and re.search(
        r"\b(?:is|are)\s+(?:a\s+)?(?:metric|model|topic|technique|method|concept|process)\s*[.!?]?\s*$", body, re.I,
    ):
        return False
    if relation == "measurement" and re.search(r"\brather\s+than\b", descriptor.original_question, re.I):
        if not re.search(r"\b(?:rather\s+than|instead\s+of|not)\b", body, re.I):
            return False
    for cue in cues:
        line_start = body.rfind("\n", 0, cue.start()) + 1
        line_end = body.find("\n", cue.end())
        line_end = len(body) if line_end < 0 else line_end
        line = body[line_start:line_end].strip()
        local_cue = _RELATION_CUES[relation].search(line)
        if not local_cue or not _heading_line_owner(line, local_cue, descriptor):
            continue
        if relation == "reason" and not _reason_object_before_cue(
            line[:local_cue.start()], descriptor,
        ):
            continue
        tail = line[local_cue.end():]
        if relation == "acronym":
            # A description of an acronym is not its spelled-out form.
            if len(re.findall(r"\b[A-Z][a-z]+\b", tail)) < 2:
                continue
        if relation == "mechanism" and re.search(r"\b(?:function|use\s+to)\b", descriptor.original_question, re.I):
            operand = re.split(r"\b(?:to|for|by|in)\b", tail, maxsplit=1, flags=re.I)[0]
            if not set(_terms(operand)) - set(descriptor.qualifiers):
                continue
        if (len(_terms(tail)) >= (2 if relation in {"acronym", "definition", "reason"} else 1)):
            return True
    return False


def _qualifies(unit: str, descriptor: QuestionDescriptor, *, heading_owned: bool = False) -> bool:
    if len(unit) > MAX_RELATED_EXCERPT_CHARS or descriptor.ambiguous:
        return False
    # Numeric requirements are not generic relevance terms: a passage with
    # another range must never qualify by matching the surrounding words.
    required_numbers = set(_NUMBER.findall(descriptor.original_question))
    if required_numbers and not required_numbers.issubset(_NUMBER.findall(unit)):
        return False
    relation = descriptor.relation
    if relation in {"property", "application"}:
        return _qualifies_new_relation(unit, descriptor, heading_owned=heading_owned)
    if heading_owned:
        return _qualifies_heading_relation(unit, descriptor)
    if re.search(r"\b(?:not|never|may|might|could|if|unless)\b", unit, re.I):
        return False
    if _TOPIC_ONLY.search(unit) and relation != "process":
        return False
    if relation == "acronym":
        if re.search(r"\b(?:incorrect|false|wrong|erroneous|invalid)\b", unit, re.I):
            return False
        entity = descriptor.entity
        if not entity or not _ACRONYM.fullmatch(entity):
            return False
        parenthetic = any(match.group(2) == entity and len(_terms(match.group(1))) >= 2
                           for match in _ACRONYM_PAREN.finditer(unit))
        parenthetic = parenthetic or any(
            match.group(1) == entity and len(_terms(match.group(2))) >= 2
            for match in _ACRONYM_PREFIX_PAREN.finditer(unit)
        )
        if parenthetic:
            return True
        subject = re.search(r"(?<!\w)" + re.escape(entity) + r"(?!\w)", unit)
        if not subject:
            return False
        return any(
            _entity_bound(unit, entity, cue)
            and len(re.findall(r"\b[A-Z][a-z]+\b", unit[cue.end():])) >= 2
            for cue in _RELATION_CUES["acronym"].finditer(unit)
        )
    cue_pattern = _RELATION_CUES.get(relation)
    if cue_pattern is None:
        return False
    cues = tuple(cue_pattern.finditer(unit))
    if not cues:
        return False
    if relation == "reason":
        entity_match = (re.search(r"(?<!\w)" + re.escape(descriptor.entity) + r"(?!\w)", unit, re.I)
                        if descriptor.entity else None)
        if descriptor.entity and entity_match is None:
            return False
        if not any(
            (entity_match is None or (entity_match.end() <= cue.start() and not re.search(
                r"[;:]|\b(?:and|whereas|but|while|which|compared|unlike)\b",
                unit[entity_match.end():cue.start()], re.I,
            ))) and _reason_object_before_cue(unit[:cue.start()], descriptor)
            and len(_terms(unit[cue.end():])) >= 2 for cue in cues
        ):
            return False
    elif not any(_entity_bound(unit, descriptor.entity, cue) and
                 len(_terms(unit[cue.end():])) >= 1 for cue in cues):
        return False
    if relation == "definition" and re.search(
        r"\b(?:is|are)\s+(?:a\s+)?(?:metric|model|topic|technique|method|concept|process)\s*[.!?]?$",
        unit, re.I,
    ):
        return False
    if relation == "process" and not re.search(r"\b(?:first.+then|steps?\s+(?:are|include)|followed\s+by|transforms?.+into)\b", unit, re.I):
        return False
    # For an unknown entity, matching two generic words can select a passage
    # about the wrong metric. Require every requested discriminator in this
    # same exact source unit; synonyms remain an honest no-match.
    if relation == "measurement" and descriptor.entity is None:
        if not descriptor.qualifiers or not set(descriptor.qualifiers).issubset(_terms(unit)):
            return False
        if not any(_named_measurement_subject(unit[:cue.start()]) for cue in cues):
            return False
    if relation == "measurement" and re.search(r"\brather\s+than\b", descriptor.original_question, re.I):
        if not re.search(r"\b(?:rather\s+than|instead\s+of|not)\b", unit, re.I):
            return False
    if relation == "mechanism" and re.search(r"\b(?:function|use\s+to)\b", descriptor.original_question, re.I):
        if not any(
            set(_terms(re.split(r"\b(?:to|for|by|in)\b", unit[cue.end():], maxsplit=1, flags=re.I)[0]))
            - set(descriptor.qualifiers)
            for cue in cues if _entity_bound(unit, descriptor.entity, cue)
        ):
            return False
    if relation in {"measurement", "mechanism", "reason", "process"} and descriptor.qualifiers:
        matches = set(_terms(unit)) & set(descriptor.qualifiers)
        required = min(2, len(descriptor.qualifiers))
        if len(matches) < required:
            return False
    return True


def select_partial_anchors(
    descriptor: QuestionDescriptor,
    chunks: Sequence[RetrievedKnowledgeChunk],
) -> tuple[RetrievedKnowledgeChunk, ...]:
    """Reserve a small, deterministic partial-context set for local neighbors.

    Call only with a context already admitted by the local examination budget.
    This function also applies that budget when used directly.
    """

    if descriptor.ambiguous:
        return ()
    candidates: list[tuple[int, int, int, RetrievedKnowledgeChunk]] = []
    for rank, chunk in enumerate(_bounded_pool(chunks, max_chunks=MAX_EXAMINED_CHUNKS,
                                               max_pages=MAX_EXAMINED_PAGES,
                                               max_tokens=MAX_EXAMINED_TOKENS)):
        if not 0 < chunk.token_count <= MAX_PARTIAL_ANCHOR_TOKENS:
            continue
        entity_mentioned = bool(descriptor.entity and re.search(
            r"(?<!\w)" + re.escape(descriptor.entity) + r"(?!\w)",
            chunk.content + " " + (chunk.section or ""), re.I,
        ))
        qualifier_hits = len(set(_terms(chunk.content)) & set(descriptor.qualifiers))
        qualifier_context = bool(
            descriptor.entity is None and descriptor.qualifiers
            and qualifier_hits >= min(2, len(descriptor.qualifiers))
        )
        if entity_mentioned or qualifier_context:
            candidates.append((-int(entity_mentioned), -qualifier_hits, rank, chunk))
    candidates.sort(key=lambda item: item[:3])
    selected: list[RetrievedKnowledgeChunk] = []
    seen_ids: set[object] = set()
    pages: set[tuple[object, int]] = set()
    tokens = 0
    for _entity, _qualifier_hits, _rank, chunk in candidates:
        page = (chunk.document_id, chunk.page_number)
        if (chunk.chunk_id in seen_ids
            or page not in pages and len(pages) >= MAX_PARTIAL_ANCHOR_PAGES
            or tokens + chunk.token_count > MAX_PARTIAL_ANCHOR_TOKENS):
            continue
        selected.append(chunk)
        seen_ids.add(chunk.chunk_id)
        pages.add(page)
        tokens += chunk.token_count
        if len(selected) == MAX_PARTIAL_ANCHORS:
            break
    return tuple(selected)


def _metadata_rank(chunk: RetrievedKnowledgeChunk, position: int) -> tuple[int, float, int]:
    """Order retrieval hits without examining document text or section content."""

    ranks = (rank for rank in (chunk.vector_rank, chunk.lexical_rank)
             if isinstance(rank, int) and rank > 0)
    return min(ranks, default=MAX_EXAMINED_CHUNKS + position + 1), -chunk.fusion_score, position


def _bounded_pool(
    chunks: Sequence[RetrievedKnowledgeChunk], *, max_chunks: int,
    max_pages: int, max_tokens: int,
) -> tuple[RetrievedKnowledgeChunk, ...]:
    """Admit chunks by IDs, page coordinates and token counts only."""

    selected: list[RetrievedKnowledgeChunk] = []
    seen: set[object] = set()
    pages: set[tuple[object, int]] = set()
    tokens = 0
    for chunk in chunks:
        if len(selected) >= max_chunks:
            break
        page = (chunk.document_id, chunk.page_number)
        if (chunk.chunk_id in seen or chunk.token_count <= 0
            or page not in pages and len(pages) >= max_pages
            or tokens + chunk.token_count > max_tokens):
            continue
        selected.append(chunk)
        seen.add(chunk.chunk_id)
        pages.add(page)
        tokens += chunk.token_count
    return tuple(selected)


def select_initial_candidate_pool(
    chunks: Sequence[RetrievedKnowledgeChunk],
) -> tuple[RetrievedKnowledgeChunk, ...]:
    """Choose the inspected top-20 pool using retrieval metadata only.

    Lexical or vector rank can preserve a lower fused-rank hit. The reserved
    page/token capacity is left for eligible local neighbors.
    """

    ordered = sorted(enumerate(chunks[:20]), key=lambda pair: _metadata_rank(pair[1], pair[0]))
    return _bounded_pool((chunk for _position, chunk in ordered), max_chunks=20,
                         max_pages=MAX_INITIAL_PAGES, max_tokens=MAX_INITIAL_TOKENS)


def rank_sufficient_sources(
    descriptor: QuestionDescriptor,
    chunks: Sequence[RetrievedKnowledgeChunk],
    canonical_pages: Mapping[UUID, str] | None = None,
) -> SourceQualification:
    """Rank complete relation candidates before relevance; report partials.

    The ordinal score only orders source-navigation candidates. It is not a
    probability of correctness. The caller may supply eligible same-page or
    neighbor chunks; each item must still be an independently citable slice.
    """

    if descriptor.ambiguous:
        return SourceQualification((), False, (), 0, 0, 0, "ambiguous")
    pages: set[tuple[object, int]] = set()
    seen_chunks: set[object] = set()
    inspected: list[RetrievedKnowledgeChunk] = []
    examined_tokens = 0
    inspected_pages: dict[tuple[UUID, UUID, int], str] = {}
    examined = 0
    partial = False
    candidates: list[tuple[int, int, float, int, RelatedExcerptSelection]] = []
    for rank, chunk in enumerate(chunks):
        if chunk.chunk_id in seen_chunks:
            continue
        page = (chunk.document_id, chunk.page_number)
        if len(seen_chunks) >= MAX_EXAMINED_CHUNKS:
            break
        if page not in pages and len(pages) >= MAX_EXAMINED_PAGES:
            continue
        if chunk.token_count <= 0 or examined_tokens + chunk.token_count > MAX_EXAMINED_TOKENS:
            continue
        seen_chunks.add(chunk.chunk_id)
        inspected.append(chunk)
        pages.add(page)
        examined += 1
        examined_tokens += chunk.token_count
        canonical = canonical_pages.get(chunk.chunk_id) if canonical_pages is not None else None
        if not isinstance(canonical, str):
            canonical = None
        canonical_identity = _page_identity(chunk)
        if canonical is not None:
            previous = inspected_pages.get(canonical_identity)
            if previous is None:
                page_tokens = estimate_tokens(canonical)
                if not canonical or examined_tokens + page_tokens > MAX_EXAMINED_TOKENS:
                    canonical = None
                else:
                    examined_tokens += page_tokens
                    inspected_pages[canonical_identity] = canonical
            elif canonical != previous:
                canonical = None
        entity_mentioned = bool(descriptor.entity and re.search(
            r"(?<!\w)" + re.escape(descriptor.entity) + r"(?!\w)",
            chunk.content + " " + (chunk.section or ""), re.I,
        ))
        qualifier_hits = len(set(_terms(chunk.content)) & set(descriptor.qualifiers))
        partial |= entity_mentioned or (
            descriptor.entity is None and bool(descriptor.qualifiers)
            and qualifier_hits >= min(2, len(descriptor.qualifiers))
        )
        if canonical_pages is None:
            heading_units = _heading_units(chunk.content, descriptor)
            for start, end in (*_units(chunk.content), *heading_units):
                unit = chunk.content[start:end]
                if not _qualifies(unit, descriptor, heading_owned=(start, end) in heading_units):
                    continue
                partial = True
                overlap = len(set(_terms(unit)) & set(descriptor.qualifiers))
                # Complete relation is a hard precondition. These remaining
                # components only order already qualified units.
                candidates.append((overlap, -rank, chunk.fusion_score, -start,
                                   RelatedExcerptSelection(chunk, start, end)))
        if canonical is not None:
            if ambiguous_acronym(canonical, descriptor.entity):
                continue
            bounds = _canonical_anchor_bounds(chunk, canonical)
            structures = ()
            if bounds is not None:
                body_start, body_end, _owner = bounds
                structures = structural_units(canonical, body_start, body_end, descriptor.entity)
                for structure in structures:
                    if not qualifies_structure(
                        canonical, structure, relation=descriptor.relation, entity=descriptor.entity,
                        qualifiers=descriptor.qualifiers, question=descriptor.original_question,
                        conditions=descriptor.conditions, requested_action=descriptor.requested_action,
                    ):
                        continue
                    partial = True
                    unit = canonical[structure.start:structure.end]
                    overlap = len(lexical_words(unit) & set(descriptor.qualifiers))
                    candidates.append((overlap, -rank, chunk.fusion_score, -structure.start,
                                       RelatedExcerptSelection(chunk, structure.start, structure.end,
                                                               "canonical_page", canonical)))
            for start, end, heading_owned in _canonical_units(chunk, canonical, descriptor):
                unit = canonical[start:end]
                if any(structure.relation == descriptor.relation for structure in structures) and heading_owned:
                    continue
                if descriptor.requested_action and descriptor.entity and not operation_matches(unit, descriptor.entity, descriptor.requested_action):
                    continue
                if any(not re.search(r"\s+".join(re.escape(word) for word in condition.split()), unit, re.I)
                       for condition in descriptor.conditions if re.match(r"(?:when|if|unless|without|with|at)\b", condition, re.I)):
                    continue
                if descriptor.conditions or question_roles(descriptor.original_question) is not None:
                    if any(not (lexical_words(term) & lexical_words(unit)) for term in descriptor.qualifiers):
                        continue
                if not _qualifies(unit, descriptor, heading_owned=heading_owned):
                    continue
                partial = True
                overlap = len(set(_terms(unit)) & set(descriptor.qualifiers))
                candidates.append((overlap, -rank, chunk.fusion_score, -start,
                                   RelatedExcerptSelection(chunk, start, end,
                                                           "canonical_page", canonical)))
    candidates.sort(key=lambda item: (-item[0], -item[1], -item[2], -item[3]))
    selected: list[RelatedExcerptSelection] = []
    selected_pages: set[tuple[object, int]] = set()
    for _overlap, _rank, _fusion, _offset, item in candidates:
        page = (item.source.document_id, item.source.page_number)
        if page in selected_pages:
            continue
        selected.append(item)
        selected_pages.add(page)
        if len(selected) >= MAX_SOURCE_FIRST_EXCERPTS:
            break
    partial_anchors = select_partial_anchors(descriptor, inspected)
    partial = partial or bool(partial_anchors)
    status = ("explicit_relation_candidate" if selected else
              "partial_context" if partial else "no_matching_relation")
    return SourceQualification(tuple(selected), partial, partial_anchors,
                               examined, len(pages), examined_tokens, status)


async def qualify_with_neighbors(
    descriptor: QuestionDescriptor,
    chunks: Sequence[RetrievedKnowledgeChunk],
    expand: Callable[[tuple[RetrievedKnowledgeChunk, ...], int, int, int, int],
                     Awaitable[Sequence[ExpandedKnowledgeNeighbor]]],
    load_pages: Callable[[tuple[UUID, ...], int, int],
                         Awaitable[Mapping[UUID, str]]] | None = None,
) -> tuple[SourceQualification, int]:
    """Inspect one bounded initial pool and a bounded union of local neighbors."""

    initial = select_initial_candidate_pool(chunks)
    canonical_pages: dict[UUID, str] = {}
    page_cache: dict[tuple[UUID, UUID, int], str] = {}

    async def inspect_pages(admitted: Sequence[RetrievedKnowledgeChunk]) -> None:
        if load_pages is None or descriptor.ambiguous:
            return
        pending: list[RetrievedKnowledgeChunk] = []
        pending_pages: set[tuple[UUID, UUID, int]] = set()
        for chunk in admitted:
            identity = _page_identity(chunk)
            if identity in page_cache:
                canonical_pages[chunk.chunk_id] = page_cache[identity]
            elif identity not in pending_pages:
                pending.append(chunk)
                pending_pages.add(identity)
        remaining = (MAX_EXAMINED_TOKENS - sum(chunk.token_count for chunk in examined)
                     - sum(estimate_tokens(page) for page in page_cache.values()))
        remaining_pages = MAX_EXAMINED_PAGES - len(page_cache)
        if not pending or remaining <= 0 or remaining_pages <= 0:
            return
        loaded = await load_pages(tuple(chunk.chunk_id for chunk in pending),
                                  min(remaining_pages, len(pending)),
                                  remaining)
        for chunk in pending:
            page = loaded.get(chunk.chunk_id)
            if not isinstance(page, str) or not page:
                continue
            tokens = estimate_tokens(page)
            if tokens > remaining:
                continue
            page_cache[_page_identity(chunk)] = page
            remaining -= tokens
        for chunk in admitted:
            page = page_cache.get(_page_identity(chunk))
            if page is not None:
                canonical_pages[chunk.chunk_id] = page

    examined = list(initial)
    await inspect_pages(initial)
    assessment = rank_sufficient_sources(
        descriptor, initial, canonical_pages if load_pages is not None else None,
    )
    anchors = assessment.partial_anchors
    if assessment.selections or not anchors:
        return assessment, 0
    seen_ids = {chunk.chunk_id for chunk in initial}
    pages = {(chunk.document_id, chunk.page_number) for chunk in initial}
    tokens = assessment.examined_tokens
    anchor_pages = {(chunk.document_id, chunk.page_number) for chunk in anchors}
    anchor_tokens = sum(chunk.token_count for chunk in anchors)
    neighbors_seen: list[RetrievedKnowledgeChunk] = []
    anchor_ids = {chunk.chunk_id for chunk in anchors}
    last_expanded_radius = 0
    for radius in (1, 2):
        available_chunks = MAX_EXAMINED_CHUNKS - len(examined)
        available_tokens = MAX_EXAMINED_TOKENS - tokens
        if available_chunks <= 0 or available_tokens <= 0:
            break
        neighbors = await expand(
            anchors, radius, len(anchors) + available_chunks,
            len(anchor_pages) + MAX_EXAMINED_PAGES - len(pages),
            anchor_tokens + available_tokens,
        )
        last_expanded_radius = radius
        for item in neighbors:
            chunk = item.chunk
            page = (chunk.document_id, chunk.page_number)
            if (chunk.chunk_id in seen_ids or chunk.token_count <= 0
                or len(examined) >= MAX_EXAMINED_CHUNKS
                or page not in pages and len(pages) >= MAX_EXAMINED_PAGES
                or tokens + chunk.token_count > MAX_EXAMINED_TOKENS):
                continue
            examined.append(chunk)
            neighbors_seen.append(chunk)
            seen_ids.add(chunk.chunk_id)
            pages.add(page)
            tokens += chunk.token_count
        await inspect_pages(neighbors_seen)
        tokens = (sum(chunk.token_count for chunk in examined)
                  + sum(estimate_tokens(page) for page in page_cache.values()))
        # Keep the partial anchors and nearest pages before unrelated initial
        # tail, while counting every distinct initial and neighbor chunk.
        ordered = (*anchors, *neighbors_seen,
                   *(chunk for chunk in initial if chunk.chunk_id not in anchor_ids))
        assessment = rank_sufficient_sources(
            descriptor, ordered, canonical_pages if load_pages is not None else None,
        )
        if assessment.selections or not assessment.partial_found:
            return assessment, radius
    return assessment, last_expanded_radius


__all__ = [
    "SOURCE_SELECTION_POLICY_ID", "QuestionDescriptor", "SourceQualification",
    "describe_question", "rank_sufficient_sources", "select_partial_anchors",
    "select_initial_candidate_pool", "qualify_with_neighbors",
    "MAX_EXAMINED_CHUNKS", "MAX_EXAMINED_PAGES", "MAX_EXAMINED_TOKENS",
    "MAX_INITIAL_PAGES", "MAX_INITIAL_TOKENS",
    "MAX_PARTIAL_ANCHORS", "MAX_PARTIAL_ANCHOR_PAGES", "MAX_PARTIAL_ANCHOR_TOKENS",
]
