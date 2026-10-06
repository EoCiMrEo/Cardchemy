"""Bounded literal-subject context for current source-only navigation.

Only the strictly preceding user question can supply a unique literal subject.
The caller owns immutable admission ordering and current access rechecks. This
pure helper neither transfers a transcript nor performs provider or database I/O.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import re
from collections.abc import Sequence
import unicodedata


POLICY_ID = "literal_subject_anchor_v1"
MAX_CURRENT_CHARS = 4_000
MAX_PRECEDING_CHARS = 1_000
MAX_SUBJECT_CHARS = 160
MAX_SUBJECT_WORDS = 12
MAX_HISTORY_TURNS = 12
_PRONOUN = re.compile(r"\b(?:it|its|this|that|these|those|they|them)\b", re.I)
_EVENT_REFERENCE = re.compile(
    r"\b(?:happen(?:ed|s|ing)?|occur(?:red|s|ring)?|imply|result(?:ed|s|ing)?)\b", re.I,
)
_MULTIPLE = re.compile(r"\b(?:and|or|versus|vs|compare|comparing|contrast|between|both|either|"
                       r"each|two|several|multiple)\b|[,/&]", re.I)
_META_INSTRUCTION = re.compile(
    r"\b(?:ignore|override|disregard|instruction(?:s)?|prompt(?:s)?|password(?:s)?|secret(?:s)?|"
    r"token(?:s)?|credential(?:s)?|execute|sudo|administrator|developer|assistant)\b|"
    r"(?:https?://|www\.|[<>`{}\[\];:=\\])", re.I,
)
_ADDITIONAL_INSTRUCTION = re.compile(
    r"\b(?:then|next|afterwards|instead|now)\s+"
    r"(?:show|send|return|answer|respond|reveal|delete|forget|write|read|run)\b", re.I,
)
_GENERIC_SUBJECTS = frozenset({
    "algorithm", "algorithms", "function", "functions", "method", "methods", "model", "models",
    "metric", "metrics", "system", "systems", "topic", "topics", "thing", "things", "process",
    "mechanism", "concept", "concepts", "subject", "idea", "lecture", "lectures", "document",
    "documents", "page", "pages", "question", "questions", "notes", "material", "materials",
    "term", "terms", "name", "names", "result", "results", "answer", "answers", "information",
})
_BAD_SUBJECT_WORDS = frozenset({
    "i", "we", "you", "he", "she", "it", "its", "this", "that", "these", "those", "they",
    "them", "their", "what", "which", "why", "how", "when", "where", "who", "whose",
    "if", "unless", "because", "although", "while", "that", "please", "say", "says",
    "is", "are", "was", "were", "does", "do", "has", "have", "will", "would", "can", "could",
    "should", "must", "may", "might", "then", "next", "instead", "with", "against", "relative",
})
_RELATION_PREFIXES = frozenset({
    "purpose", "objective", "goal", "definition", "meaning", "application", "example",
    "limitation", "limitations", "property", "properties", "steps", "stages", "role",
    "difference", "relationship", "connection", "expansion", "full", "name", "result", "results",
    "cause", "main", "primary", "basic",
})
_ARTICLE = re.compile(r"(?:a|an|the)\s+", re.I)
_ENDING = r"(?:\s+please)?[?.!]?$"
_RULES = tuple(re.compile(r"^(?:please\s+)?" + frame + _ENDING, re.I) for frame in (
    r"(?:tell me about|describe|explain|define|what (?:is|are))\s+(?P<subject>.+?)",
    r"what does\s+(?P<subject>.+?)\s+(?:stand for|mean|measure|represent|do)",
    r"how (?:does|do)\s+(?P<subject>.+?)\s+(?:work|operate|learn|function)",
    r"why (?:does|do)\s+(?P<subject>.+?)\s+(?:matter|work)",
    r"(?:what (?:is|are)|describe|explain|list)\s+(?:the\s+)?(?:main\s+)?"
    r"(?:purpose|objective|goal|definition|meaning|role|application|applications|limitation|limitations|"
    r"property|properties|steps|stages)\s+(?:of|for)\s+(?P<subject>.+?)",
    r"what (?:do|does)\s+(?:(?:the|these|those|our|this)\s+)?"
    r"(?:lectures?|course(?:\s+materials?)?|notes|materials|slides)\s+"
    r"(?:say|teach|explain|cover)\s+about\s+(?P<subject>.+?)",
    r"(?:how|why) (?:is|are)\s+(?P<subject>.+?)\s+"
    r"(?:used|applied|performed|calculated|represented|explained|defined)"
    r"(?:\s+(?:for|in|to|by)\s+.+?)?",
    r"i am\s+(?:reading|studying|learning)\s+about\s+(?P<subject>.+?)",
))


@dataclass(frozen=True, slots=True)
class LiteralSubjectAnchor:
    """Local provenance; only ``subject`` could enter a approved wire."""

    subject: str = field(repr=False)
    subject_sha256: str
    current_question_sha256: str
    preceding_question_sha256: str
    preceding_history_index: int
    start_offset: int
    end_offset: int
    start_byte_offset: int
    end_byte_offset: int
    policy_id: str = POLICY_ID


@dataclass(frozen=True, slots=True)
class SubjectContextResolution:
    status: str
    reason: str
    current_question_sha256: str | None
    anchor: LiteralSubjectAnchor | None = None
    policy_id: str = POLICY_ID


def _digest(value: str) -> str | None:
    try:
        return sha256(value.encode("utf-8")).hexdigest()
    except UnicodeError:
        return None


def _safe_question(value: object, maximum: int) -> bool:
    if type(value) is not str or not 0 < len(value) <= maximum or not value.strip():
        return False
    core = value.strip().rstrip("?.!")
    return (not any(unicodedata.category(char).startswith("C") for char in value)
            and _META_INSTRUCTION.search(value) is None
            and _ADDITIONAL_INSTRUCTION.search(value) is None
            and not any(char in core for char in ".!?")
            and value.count("?") <= 1
            and ("?" not in value or value.rstrip().endswith("?"))
            and _digest(value) is not None)


def _subject_span(question: str) -> tuple[int, int] | None:
    """Conservative English question frames; no topic dictionary or model."""
    if not _safe_question(question, MAX_PRECEDING_CHARS) or _MULTIPLE.search(question):
        return None
    # No sentence/object continuation can introduce another possible referent.
    trimmed = question.strip()
    if any(char in trimmed.rstrip("?.!") for char in ".!?()'\"\u2018\u2019\u201c\u201d"):
        return None
    base = len(question) - len(question.lstrip())
    spans: set[tuple[int, int]] = set()
    for rule in _RULES:
        match = rule.fullmatch(trimmed)
        if match is None:
            continue
        start, end = match.span("subject")
        while start < end and trimmed[start].isspace():
            start += 1
        while end > start and trimmed[end - 1].isspace():
            end -= 1
        article = _ARTICLE.match(trimmed, start, end)
        if article:
            start = article.end()
        subject = trimmed[start:end]
        if not 0 < len(subject) <= MAX_SUBJECT_CHARS:
            continue
        words = subject.split()
        if not 0 < len(words) <= MAX_SUBJECT_WORDS:
            continue
        lowered = [word.casefold() for word in words]
        if (any(word in _BAD_SUBJECT_WORDS for word in lowered)
                or lowered[0] in _RELATION_PREFIXES
                or all(word in _GENERIC_SUBJECTS or word in {"of", "for", "the", "a", "an"}
                       for word in lowered)):
            continue
        if any(not word or not unicodedata.category(word[0]).startswith("L")
               or word.endswith("-") or "--" in word
               or any(not (unicodedata.category(char).startswith(("L", "N")) or char == "-")
                      for char in word) for word in words):
            continue
        literal_start, literal_end = base + start, base + end
        # A repeated name or competing grammatical span is uncertain.
        if question.count(subject) == 1:
            spans.add((literal_start, literal_end))
    return next(iter(spans)) if len(spans) == 1 else None


def _resolve_literal_subject_context(
    current_question: str,
    preceding_history: Sequence[tuple[str, str]] = (),
    *,
    raw_navigation_query: str | None,
) -> SubjectContextResolution:
    """Resolve only a literal subject from the last admission-bounded USER.

    ``raw_navigation_query`` must be the actual production raw-only result,
    not its history-expanded query. The resolver deliberately does not import
    that service or copy any previous question into a source-ID provider wire.
    """
    current_sha = _digest(current_question) if type(current_question) is str else None

    def clarify(reason: str) -> SubjectContextResolution:
        return SubjectContextResolution("needs_clarification", reason, current_sha)

    if not _safe_question(current_question, MAX_CURRENT_CHARS):
        return clarify("current_question_invalid")
    if raw_navigation_query is not None:
        if type(raw_navigation_query) is not str or raw_navigation_query != current_question.strip():
            return clarify("raw_query_invalid")
        return SubjectContextResolution("clear_current_question", "raw_question_clear", current_sha)
    if _PRONOUN.search(current_question) is None:
        return clarify("unresolved_current_question")
    if _EVENT_REFERENCE.search(current_question):
        return clarify("event_referent_unresolved")
    if type(preceding_history) not in (tuple, list) or len(preceding_history) > MAX_HISTORY_TURNS:
        return clarify("history_invalid")
    if any(type(row) not in (tuple, list) or len(row) != 2 or type(row[0]) is not str
           or row[0] not in {"user", "assistant"} or type(row[1]) is not str
           for row in preceding_history):
        return clarify("history_invalid")
    for index in range(len(preceding_history) - 1, -1, -1):
        row = preceding_history[index]
        if row[0] != "user":
            continue
        preceding = row[1]
        if not _safe_question(preceding, MAX_PRECEDING_CHARS):
            return clarify("preceding_question_invalid")
        span = _subject_span(preceding)
        if span is None:
            return clarify("subject_not_unambiguous")
        start, end = span
        subject = preceding[start:end]
        anchor = LiteralSubjectAnchor(subject, _digest(subject), current_sha, _digest(preceding), index,
            start, end, len(preceding[:start].encode("utf-8")), len(preceding[:end].encode("utf-8")))
        return SubjectContextResolution("resolved_literal_subject", "literal_subject_from_prior_user", current_sha, anchor)
    return clarify("missing_preceding_user")


def validate_subject_binding(
    current_question: str, preceding_question: str, anchor: LiteralSubjectAnchor,
) -> bool:
    """Validate exact bytes/grammar; admission message identity remains external."""
    if type(anchor) is not LiteralSubjectAnchor or anchor.policy_id != POLICY_ID:
        return False
    if (not _safe_question(current_question, MAX_CURRENT_CHARS)
            or not _safe_question(preceding_question, MAX_PRECEDING_CHARS)
            or type(anchor.preceding_history_index) is not int or anchor.preceding_history_index < 0
            or anchor.preceding_history_index >= MAX_HISTORY_TURNS
            or any(type(value) is not int for value in (anchor.start_offset, anchor.end_offset,
                anchor.start_byte_offset, anchor.end_byte_offset))):
        return False
    span = _subject_span(preceding_question)
    if span != (anchor.start_offset, anchor.end_offset):
        return False
    start, end = span
    subject = preceding_question[start:end]
    return (anchor.subject == subject and anchor.subject_sha256 == _digest(subject)
            and anchor.current_question_sha256 == _digest(current_question)
            and anchor.preceding_question_sha256 == _digest(preceding_question)
            and anchor.start_byte_offset == len(preceding_question[:start].encode("utf-8"))
            and anchor.end_byte_offset == len(preceding_question[:end].encode("utf-8")))


def validate_subject_history_binding(
    current_question: str, preceding_history: Sequence[tuple[str, str]],
    anchor: LiteralSubjectAnchor, *, raw_navigation_query: str | None,
) -> bool:
    """Revalidate the latest-user choice inside the exact admission snapshot.

    This complements the single-question byte check. The caller still owns
    the database message ID, strict admission ordering and current access.
    """
    if type(anchor) is not LiteralSubjectAnchor:
        return False
    resolved = resolve_subject_context(
        current_question, preceding_history, raw_navigation_query=raw_navigation_query,
    )
    return resolved.anchor == anchor and resolved.status == "resolved_literal_subject"


CURRENT_QUESTION_POLICY_ID = "literal_subject_anchor_v2"
_INTERROGATIVE = re.compile(r"^(?:what|which|how|why|when|where|who)\b", re.I)


def safe_current_question(question: object) -> bool:
    """Retain literal-subject bounds and other exclusions; permit lexical ignore only.

    This exception requires an interrogative task and already clear raw query.
    Imperatives and instructions/credentials/prompt keywords remain rejected.
    This text check grants no source access and selects no reference.
    """
    if _safe_question(question, MAX_CURRENT_CHARS):
        return True
    if type(question) is not str or not 0 < len(question) <= MAX_CURRENT_CHARS or not question.strip():
        return False
    if _INTERROGATIVE.match(question.strip()) is None:
        return False
    meta = tuple(_META_INSTRUCTION.finditer(question))
    if not meta or any(match.group().casefold() != "ignore" for match in meta):
        return False
    core = question.strip().rstrip("?.!")
    return (not any(unicodedata.category(char).startswith("C") for char in question)
        and _ADDITIONAL_INSTRUCTION.search(question) is None
        and not any(char in core for char in ".!?") and question.count("?") <= 1
        and ("?" not in question or question.rstrip().endswith("?"))
        and _digest(question) is not None)


def resolve_subject_context(current_question: str, preceding_history=(), *, raw_navigation_query: str | None):
    """No new history eligibility; only repair a clear CURRENT task's blacklist.

    ``raw_navigation_query`` must be the actual production raw-only result.
    The source/SQL boundary must bind and recheck that independently.
    """
    if raw_navigation_query is not None and safe_current_question(current_question):
        valid = type(raw_navigation_query) is str and raw_navigation_query == current_question.strip()
        return SubjectContextResolution(
            "clear_current_question" if valid else "needs_clarification",
            "raw_question_clear" if valid else "raw_query_invalid",
            _digest(current_question), policy_id=CURRENT_QUESTION_POLICY_ID)
    # Keep every unresolved-question / literal-subject safeguard unchanged.
    return _resolve_literal_subject_context(current_question, preceding_history,
                                      raw_navigation_query=raw_navigation_query)
