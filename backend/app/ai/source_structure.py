"""Explicit question roles and literal lecture structure for source navigation.

This is a bounded grammar, not an entailment model. It recognizes authored
labels, ownership and connected explanations; unsupported prose stays a miss.
All source coordinates refer to the unchanged canonical page.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


_WORD = re.compile(r"[A-Za-z][A-Za-z0-9-]*")
_PRONOUN = re.compile(r"(?:it|its|this|that|these|those|they|them)", re.I)
_ARTICLE = re.compile(r"^(?:a|an|the)\s+", re.I)
_ACTION = (
    r"work|operate|use|apply|add|hold|block|open|close|produce|calculate|sort|release|detect|turn|convert|"
    r"prevent|require|need|remove|reduce|increase|decrease|keep|hold|create|"
    r"generate|transform|map|encode|decode|learn|represent|predict|classify|"
    r"identify|extract|assign|update|combine|select|split|filter|compare|measure"
)
_FINITE_ACTION = rf"(?:{_ACTION})(?:s|es)?"
_LABELS = {
    "acronym": r"(?:full form|expansion|abbreviation)",
    "definition": r"(?:definition|meaning)",
    "mechanism": r"(?:mechanism|how it works|operation|rule)",
    "measurement": r"(?:measurement|what it measures|interpretation)",
    "reason": r"(?:reason|why|cause|consequence)",
    "process": r"(?:process|steps|stages|sequence)",
    "property": r"(?:limitation|limitations|disadvantage|disadvantages|property|properties)",
    "application": r"(?:application|applications|example|examples|use case|use cases)",
}
_EXPLANATORY_LABEL = re.compile(
    r"^(?:input|output|rule|operation|example|interpretation|cause|consequence|"
    r"result|objective|takeaway)\s*:", re.I,
)
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")
_IMPERATIVE = re.compile(
    r"^(?:place|fold|seal|turn|press|open|add|close|write|attach|record|insert|"
    r"connect|read|wait|move|lift|push|pull|set|check|repeat|sort|divide|count|"
    r"split|lowercase|remove|normalize|tokenize|convert|replace|compute|apply|"
    r"identify|extract|select|assign|iterate|update|calculate|generate|filter|"
    r"lemmatize|stem|clean|map|encode|decode|train|predict)\b", re.I,
)
_PREDICATE = re.compile(
    r"\b(?:is|are|has|have|uses?|measures?|compares?|ignores?|discards?|"
    r"requires?|adds?|removes?|produces?|generates?|detects?|prevents?|"
    r"represents?|defines?|applies?|stands?|means?)\b", re.I,
)
_CONNECTOR = re.compile(
    r"\b(?:because|so that|therefore|due to|as a result|through which|"
    r"leaving|to obtain|by|each|routes?|pulls?|lifts?|strikes?|adds?)\b", re.I,
)
_BAD_SOURCE = re.compile(r"\b(?:incorrect|false|wrong|erroneous|invalid|may|might|could)\b", re.I)
_TOPIC_ONLY = re.compile(r"\b(?:discussed|mentioned|introduced|consult|handbook)\b|\bcovered\s+(?:in|by)\b", re.I)
_ACRONYM = r"[A-Z][A-Z0-9]{1,11}(?:-[A-Z0-9]{2,11})*"
_EXPANSION = r"[A-Z][A-Za-z-]+(?:[ \t]+[A-Za-z][A-Za-z-]+){0,8}"
_ALIAS_AFTER = re.compile(rf"\b(?P<short>{_ACRONYM})\s*\((?P<long>{_EXPANSION})\)")
_ALIAS_BEFORE = re.compile(rf"(?P<long>{_EXPANSION})\s*\((?P<short>{_ACRONYM})\)")


@dataclass(frozen=True, slots=True)
class QuestionRoles:
    entity: str | None
    relation: str
    object_text: str = ""
    domain: str = ""
    conditions: tuple[str, ...] = ()
    required_text: str = ""
    action: str = ""


@dataclass(frozen=True, slots=True)
class SourceAlias:
    short: str
    long: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class StructuralUnit:
    start: int
    end: int
    body_start: int
    relation: str
    owner: str
    aliases: tuple[SourceAlias, ...] = ()


def _entity(value: str) -> str:
    return _ARTICLE.sub("", value.strip().rstrip(".?! ")).strip()


def question_roles(question: str) -> QuestionRoles | None:
    """Parse explicit supported constructions without removing factual suffixes."""

    q = question.strip().rstrip(".?! ")
    if re.search(r"\band\s+(?:what|which|how|why|define|explain|describe|show)\b", q, re.I):
        return None
    domain = ""
    prefix = re.match(r"^(?:In|For|At)\s+(.+?),\s*(.+)$", q, re.I)
    if prefix:
        domain, q = _entity(prefix[1]), prefix[2]
    q = re.sub(r"^(?:explain|describe)\s+(?=(?:how|why|what)\b)", "", q, flags=re.I)
    # Each rule captures the requested owner separately from objects/conditions.
    rules = (
        ("acronym", r"(?:expand|give the expansion of)\s+(?P<entity>.+)"),
        ("acronym", r"what does\s+(?P<entity>.+?)\s+stand for"),
        ("process", r"how is\s+(?P<entity>.+?)\s+performed"),
        ("process", r"(?:what are|list)\s+(?:the\s+)?(?:all\s+)?(?:(?P<count>\d+)\s+)?steps\s+(?:of|for|in)\s+(?P<entity>.+?)(?:\s+in order)?"),
        ("property", r"what\s+(?:limitation|disadvantage|property|properties)\s+does\s+(?P<entity>.+?)\s+have(?P<tail>.*)"),
        ("application", r"(?:give|name)\s+(?:an?\s+)?(?:example\s+)?application\s+of\s+(?P<entity>.+?)(?P<tail>\s+(?:in|for)\s+.*|$)"),
        ("application", r"what is\s+(?:an?\s+)?application\s+of\s+(?P<entity>.+?)(?P<tail>\s+(?:in|for)\s+.*|$)"),
        ("application", r"where\s+(?:is|are)\s+(?P<entity>.+?)\s+used(?P<tail>.*)"),
        ("measurement", r"what does\s+(?P<entity>.+?)\s+(?:(?:primarily|mainly|chiefly)\s+)?(?:measure|compare|evaluate|quantify|focus on)(?P<tail>.*)"),
        ("measurement", r"what\s+(?:does\s+)?(?:a\s+)?(?P<scalar>high|low|higher|lower)\s+(?P<entity>.+?)\s+(?:indicates|indicate|means|mean)(?P<tail>.*)"),
        ("measurement", r"how\s+(?:does|do)\s+(?P<entity>.+?)\s+(?:measure|compare|evaluate|quantify)(?P<tail>\s.*|$)"),
        ("mechanism", rf"how\s+(?:does|do)\s+(?P<entity>.+?)\s+(?P<action>{_FINITE_ACTION})(?P<tail>\s.*|$)"),
        ("mechanism", rf"how\s+(?P<entity>.+?)\s+(?P<action>{_FINITE_ACTION})(?P<tail>\s.*|$)"),
        ("reason", rf"why\s+(?:does|do)\s+(?P<entity>.+?)\s+(?P<action>{_FINITE_ACTION})(?P<tail>\s.*|$)"),
        ("reason", rf"why\s+(?P<entity>.+?)\s+(?P<action>{_FINITE_ACTION})(?P<tail>\s.*|$)"),
        ("definition", r"define\s+(?P<entity>.+)"),
        ("definition", r"what\s+(?:is|are)\s+(?P<entity>.+)"),
    )
    for relation, pattern in rules:
        m = re.fullmatch(pattern, q, re.I)
        if not m:
            continue
        values = m.groupdict()
        owner = _entity(values["entity"])
        # Let the maintained grammar handle nested relation noun questions.
        if relation == "definition" and re.match(
            r"(?:definition|meaning|application|example|limitation|property|steps)\b", owner, re.I,
        ):
            return None
        tail = (values.get("tail") or "").strip()
        tail = re.sub(r"\s+in order$", "", tail, flags=re.I)
        scalar = values.get("scalar") or ""
        conditions = tuple(m.group().strip() for m in re.finditer(
            r"\b(?:when|if|unless|without|with|at|in)\b.+?(?=\s+(?:and when|and if)\b|$)", tail, re.I,
        ))
        return QuestionRoles(owner, relation, tail, domain, conditions,
                             " ".join(part for part in (domain, tail, scalar) if part), values.get("action") or "")
    return None


def prior_entity(question: str) -> str | None:
    """Resolve a single explicit noun phrase from one bounded prior user turn."""

    roles = question_roles(question)
    value = roles.entity if roles else None
    if value is None:
        m = re.fullmatch(r"(?:tell me about|describe|explain)\s+(.+?)[.?!]*", question.strip(), re.I)
        value = _entity(m[1]) if m else None
    if value and (re.search(r"\b(?:and|or|versus|vs)\b|[,/]", value, re.I)
                  or _PRONOUN.fullmatch(value) or len(value) > 160):
        return None
    return value


def source_aliases(page: str) -> tuple[SourceAlias, ...]:
    """Keep only single-valued, source-attested abbreviation pairs with offsets."""

    pairs: list[SourceAlias] = []
    for pattern in (_ALIAS_AFTER, _ALIAS_BEFORE):
        for m in pattern.finditer(page):
            long = m["long"].strip()
            pairs.append(SourceAlias(m["short"], long, m.start(), m.end()))
    expansions: dict[str, set[str]] = {}
    for pair in pairs:
        expansions.setdefault(pair.short, set()).add(pair.long.casefold())
    return tuple(pair for pair in pairs if len(expansions[pair.short]) == 1)


def ambiguous_acronym(page: str, entity: str | None) -> bool:
    if not entity or not re.fullmatch(_ACRONYM, entity):
        return False
    expansions = {m["long"].casefold() for pattern in (_ALIAS_AFTER, _ALIAS_BEFORE)
                  for m in pattern.finditer(page) if m["short"] == entity}
    return len(expansions) > 1


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split()).strip(" #:.?!")


def _owner_matches(title: str, entity: str | None, aliases: tuple[SourceAlias, ...]) -> bool:
    if not entity:
        return False
    names = {_normalize(entity)}
    for pair in aliases:
        if _normalize(entity) in {_normalize(pair.short), _normalize(pair.long)}:
            names.update((_normalize(pair.short), _normalize(pair.long)))
    title = _normalize(title)
    if title in names:
        return True
    for pair in aliases:
        if _normalize(pair.short) in names and title in {
            _normalize(f"{pair.short} ({pair.long})"), _normalize(f"{pair.long} ({pair.short})"),
        }:
            return True
    for label in _LABELS.values():
        for name in names:
            if (re.fullmatch(re.escape(name) + r"\s*:\s*" + label, title, re.I)
                or re.fullmatch(label + r"\s+of\s+" + re.escape(name), title, re.I)):
                return True
    return False


def relation_label(text: str) -> str | None:
    """Recognize a short authored label, including an explicit domain suffix."""

    text = text.strip().lstrip("# ")
    head = text.split(":", 1)[0].strip()
    if len(head.split()) > 12:
        return None
    for relation, label in _LABELS.items():
        if (re.fullmatch(label + r"(?:\s+(?:in|for|at|with|without|of)\s+.+)?", head, re.I)
            or re.fullmatch(r"[A-Za-z0-9 -]+\s+" + label, head, re.I)):
            return relation
    return None


def _topic_heading(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped and len(stripped) <= 160 and len(stripped.split()) <= 14
                and not _BULLET.match(stripped) and not re.search(r"[.!?;:]", stripped)
                and not relation_label(stripped) and not _PREDICATE.search(stripped)
                and not re.match(r"\d+[ -]", stripped))


def structural_units(page: str, body_start: int, body_end: int, entity: str | None,
                     max_chars: int = 480) -> tuple[StructuralUnit, ...]:
    """Build contiguous owner-plus-structure windows intersecting an anchor.

    No material is concatenated. A new topic ends ownership; a label may own
    one paragraph/list item, or an explicitly connected sequence/example block.
    """

    aliases = source_aliases(page)
    lines = tuple(re.finditer(r"[^\n]+", page))
    result: list[StructuralUnit] = []
    # Parenthetical names belong to their own item; a neighboring list item
    # cannot supply an expansion. Include an immediately preceding domain
    # heading as literal context, never concatenate it.
    for pair in aliases:
        if pair.short != entity or pair.end <= body_start or pair.start >= body_end:
            continue
        for index, line in enumerate(lines):
            if line.start() <= pair.start < line.end():
                start = line.start()
                if index and _topic_heading(lines[index - 1].group()):
                    start = lines[index - 1].start()
                if line.end() - start <= max_chars:
                    result.append(StructuralUnit(start, line.end(), line.start(), "acronym", entity, aliases))
                break
    for i, line in enumerate(lines):
        title = line.group().strip()
        if not _owner_matches(title, entity, aliases):
            continue
        start = line.start() + len(line.group()) - len(line.group().lstrip())
        relation = relation_label(title.split(":", 1)[-1]) if ":" in title else None
        body = line.end() + 1
        for item in lines[i + 1:]:
            text = item.group().strip()
            if _topic_heading(text):
                break
            label = relation_label(text)
            if label and not _BULLET.match(text):
                relation = relation if label == "application" and relation in {"mechanism", "measurement", "reason"} else label
                body = item.start() if ":" in text else item.end() + 1
            end = item.end()
            if end - start > max_chars:
                break
            if end <= body_start or start >= body_end or not relation or end <= body:
                continue
            result.append(StructuralUnit(start, end, body, relation, title, aliases))
        # An explicitly ordered action list carries the process relation itself.
        following: list[re.Match[str]] = []
        for item in lines[i + 1:]:
            text = item.group().strip()
            if _topic_heading(text):
                break
            if relation_label(text):
                continue
            if not re.match(r"\s*\d+[.)]", text):
                break
            following.append(item)
        if len(following) >= 2:
            end = following[-1].end()
            if end - start <= max_chars and end > body_start and start < body_end:
                result.append(StructuralUnit(start, end, following[0].start(), "process", title, aliases))
    return tuple(result)


def lexical_words(text: str) -> set[str]:
    """Conservative inflection matching; no semantic synonym substitution."""

    words: set[str] = set()
    for match in _WORD.finditer(text):
        word = match.group().casefold()
        words.add(word)
        if len(word) > 5 and word.endswith("ing"):
            words.add(word[:-3])
        elif len(word) > 4 and word.endswith("ies"):
            words.add(word[:-3] + "y")
        elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            words.add(word[:-1])
    return words


def _substantive(text: str) -> bool:
    text = _BULLET.sub("", text).strip()
    return bool(len(_WORD.findall(text)) >= 3
                and not re.search(r"\b(?:for|to|of|with|and|or|by|into|carrying|using)\s*$", text, re.I)
                and not _TOPIC_ONLY.search(text))


def _overt_other_owner(body: str, entity: str) -> bool:
    """Reject independent named subjects; pronouns/parts and action objects remain local."""

    names = set(_WORD.findall(entity.casefold()))
    for raw in body.splitlines():
        line = _BULLET.sub("", raw).strip()
        line = _EXPLANATORY_LABEL.sub("", line).strip()
        cue = _PREDICATE.search(line)
        if not cue or cue.start() == 0:
            continue
        prefix = line[:cue.start()].strip()
        if re.search(r"\b(?:when|if|because|so|that|which|while)\b", prefix, re.I):
            continue
        if re.match(r"^(?:it|its|this|that|these|those)\b", prefix, re.I):
            continue
        clean_prefix = re.sub(r"^(?:the|a|an)\s+", "", prefix, flags=re.I)
        if not lexical_words(clean_prefix) & names and clean_prefix[:1].isupper():
            return True
    return False


def qualifies_structure(page: str, unit: StructuralUnit, *, relation: str,
                        entity: str | None, qualifiers: tuple[str, ...],
                        question: str, conditions: tuple[str, ...] = (), requested_action: str = "") -> bool:
    """Require the requested explicit relation, complete body and matched context."""

    if not entity or unit.relation != relation:
        return False
    quote, body = page[unit.start:unit.end], page[unit.body_start:unit.end].strip()
    if not body or _BAD_SOURCE.search(body) or _TOPIC_ONLY.search(body):
        return False
    if requested_action and not operation_matches(body, entity, requested_action):
        return False
    if _overt_other_owner(body, entity):
        return False
    words = lexical_words(quote)
    if any(not (lexical_words(term) & words) for term in qualifiers):
        return False
    if not set(re.findall(r"\d+(?:\.\d+)?", question)).issubset(re.findall(r"\d+(?:\.\d+)?", quote)):
        return False
    for condition in conditions:
        # Preserve polarity/condition as authored, ignoring only determiners.
        required = [w for w in _WORD.findall(condition.casefold()) if w not in {"a", "an", "the", "its", "in", "at", "of", "for"}]
        if any(not lexical_words(w) & words for w in required):
            return False
        condition_pattern = r"\s+".join(re.escape(w) for w in condition.casefold().split())
        if re.match(r"(?:when|if|unless|without|with|at)\b", condition, re.I) and not re.search(condition_pattern, quote, re.I):
            return False
    if re.search(r"\b(?:not|never|without)\b", body, re.I) and relation not in {"property", "reason"}:
        if not re.search(r"\b(?:not|never|without)\b", question, re.I):
            return False
    if relation == "acronym":
        return any(pair.start >= unit.start and pair.end <= unit.end
                   and pair.short == entity for pair in unit.aliases)
    if relation == "definition":
        clean = _BULLET.sub("", body).strip()
        return bool(_substantive(clean) and re.match(r"^(?:a|an|the|is|are)\b|^[A-Za-z]+ing\b", clean, re.I)
                    and len(_WORD.findall(clean)) >= 5)
    if relation == "process":
        steps = re.findall(r"^\s*(\d+)[.)]\s*([^\n]*)", body, re.M)
        if len(steps) < 2 or [int(n) for n, _ in steps] != list(range(1, len(steps) + 1)):
            return False
        if re.match(r"\s*\n\s*\d+[.)]", page[unit.end:]):
            return False
        requested = re.search(r"\b(?:all\s+)?(\d+)\s+steps\b", question, re.I)
        return bool((not requested or len(steps) == int(requested[1]))
                    and all(_IMPERATIVE.match(item) and _substantive(item) for _, item in steps))
    if relation == "mechanism":
        return bool(_substantive(body) and _CONNECTOR.search(body)
                    and len(_WORD.findall(body)) >= 8)
    if relation == "reason":
        return bool(_substantive(body) and re.search(
            r"\b(?:because|so that|therefore|due to|as a result|consequence)\b", quote, re.I,
        ) and len(_WORD.findall(body)) >= 7)
    if relation == "measurement":
        if re.search(r"\binterpretation\b", quote, re.I):
            return bool(_substantive(body) and re.search(r"\b(?:indicates?|means?|represents?|corresponds? to)\b", body, re.I))
        return _substantive(body)
    if relation == "property":
        return _substantive(body)
    if relation == "application":
        clean = _BULLET.sub("", body).strip()
        return bool(_substantive(clean) and re.match(r"^[A-Za-z]+ing\b", clean, re.I))
    return False


def operation_matches(body: str, entity: str, requested_action: str) -> bool:
    """Reject an overt owner predicate assigning a conflicting operation.

    Owning relation labels and connected examples may state their operation
    structurally without repeating the question's verb. This is not a synonym
    or entailment inference; an overt contradictory action is never ignored.
    """
    if requested_action.casefold() in {"work", "works", "operate", "operates"}:
        return True
    requested = lexical_words(requested_action)
    for raw in body.splitlines():
        line = _BULLET.sub("", raw).strip()
        match = re.match(r"(?:" + re.escape(entity) + r"\s+)?(?P<action>" + _FINITE_ACTION + r")\b", line, re.I)
        if match and not lexical_words(match["action"]) & requested:
            return False
    return True
