"""Create an unreviewed, source-bound Ask evidence-sufficiency packet.

Default invocation imports no application and reads no database. Explicit
creation reads current owner-authorized, published Knowledge in a read-only
transaction. Fixed templates, or a separately supplied bounded literal-only
spec in owner-private OS Temp, select source windows without asking the
runtime retriever, selector or provider. Each sufficient *candidate* gets
one paired wrong-entity/same-relation control. No quality label is inferred.
Private questions, source IDs and excerpts stay in owner-private OS Temp files;
stdout contains counts/status only. Old reviewed examples are excluded by
their owner-private manifests and six historical seed page identities.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
from typing import Any, Sequence
from uuid import UUID


SCHEMA = "source_sufficiency_candidate_packet_v1"
OUTPUT_ENV = "CARDCH_LANE6_REVIEW_OUTPUT_DIR"
_RELATIONS = ("acronym_expansion", "definition", "mechanism", "measurement", "reason", "process",
              "property_limitation", "application_example")
_INSUFFICIENT_TARGET = len(_RELATIONS) * 2
_CONTENT_CAP = 480
DISCOVERY_POLICY = "complete_source_units_v2"
AUTHORED_SPEC_SCHEMA = "private_source_sufficiency_authored_v1"
_AUTHORED_SPEC_MAX_BYTES = 64_000
_AUTHORED_SPEC_MAX_CASES = 64
_AUTHORED_CASE_ID = re.compile(r"X[0-9]{2}\Z")

# Page-disjoint from six previously reviewed development examples. The
# identifiers describe the historical source pages, without importing the
# retired answer/verifier probe module or inspecting runtime search results.
_DEVELOPMENT_SEED_PAGES = (
    (22, (r"\bbleu\b", r"bilingual\s+evaluation\s+understudy")),
    (22, (r"\bbleu\b", r"n[\s-]?grams?", r"referenc")),
    (13, (r"cosine", r"angle", r"magnitud")),
    (9, (r"bag[\s-]of[\s-]words|\btf[\s-]idf\b", r"word\s+order|context")),
    (30, (r"logistic", r"sigmoid", r"probab")),
    (4, (r"topic", r"legal|medical")),
)


@dataclass(frozen=True)
class Template:
    case_id: str
    relation: str
    category: str
    question: str
    entity: str
    evidence: tuple[str, ...]
    previous_turn: str = ""
    requirements: tuple[str, ...] | None = None


# Authored pool before runtime retrieval or display evaluation. Source-page
# availability chooses one per relation/category; humans decide sufficiency.
# These questions avoid the previously reviewed T01-T12 question wording.
TEMPLATES = (
    Template("A01", "acronym_expansion", "direct", "Expand POS in the tagging material.", r"\bPOS\b", (r"part[ -]of[ -]speech",)),
    Template("A03", "acronym_expansion", "direct", "Expand NER in the entity-recognition material.", r"\bNER\b", (r"named entity recognition",)),
    Template("A02", "acronym_expansion", "followup", "What does it stand for?", r"\bRNN\b", (r"recurrent neural network",), "Where is RNN discussed?"),
    Template("A04", "acronym_expansion", "followup", "What does it stand for?", r"\bLSTM\b", (r"long short[ -]term memory",), "Where is LSTM discussed?"),
    Template("A05", "acronym_expansion", "direct", "Expand TF-IDF as written in the lecture.", r"TF[ -]?IDF", (r"term.frequency.{0,120}inverse.document.frequency",)),
    Template("A06", "acronym_expansion", "direct", "Expand NLP as written in the lecture.", r"\bNLP\b", (r"natural.language.processing",)),
    Template("A07", "acronym_expansion", "direct", "Expand LDA as written in the lecture.", r"\bLDA\b", (r"latent.dirichlet.allocation",)),
    Template("A08", "acronym_expansion", "followup", "What does it stand for?", r"\bBLEU\b", (r"bilingual.evaluation.understudy",), "Where is BLEU discussed?"),
    Template("A09", "acronym_expansion", "followup", "What does it stand for?", r"\bLDA\b", (r"latent.dirichlet.allocation",), "Where is LDA discussed?"),
    Template("A10", "acronym_expansion", "followup", "What does it stand for?", r"\bNLP\b", (r"natural.language.processing",), "Where is NLP discussed?"),
    Template("D01", "definition", "direct", "What does a language model represent?", r"language model", (r"word sequence|next word",)),
    Template("D04", "definition", "direct", "What is a corpus in language processing?", r"\bcorpus\b", (r"collection|document|text|data",)),
    Template("D02", "definition", "paraphrase", "Which kinds of named things does entity recognition pick out?", r"named entity recognition", (r"person|organization|location|entit",)),
    Template("D03", "definition", "paraphrase", "Which grammatical labels are assigned during POS tagging?", r"part[ -]of[ -]speech tagging|POS tagging", (r"noun|verb|grammatical|tag",)),
    Template("D05", "definition", "direct", "What is a word embedding?", r"word embedding", (r"vector|represent|semantic",)),
    Template("D06", "definition", "direct", "What is a topic model?", r"topic model", (r"document|theme|distribution|latent",)),
    Template("D07", "definition", "direct", "What is an n-gram?", r"n[ -]?gram", (r"sequence|consecutive|contiguous",)),
    Template("D08", "definition", "paraphrase", "Which contiguous word sequences are called n-grams?", r"n[ -]?gram", (r"sequence|consecutive|contiguous",)),
    Template("D09", "definition", "paraphrase", "What does a vector representation of a word capture?", r"word vector|word embedding", (r"semantic|meaning|represent",)),
    Template("D10", "definition", "paraphrase", "What kind of data is grouped by a topic model?", r"topic model", (r"document|corpus|text|theme",)),
    Template("M01", "mechanism", "paraphrase", "How does attention emphasize selected tokens?", r"\battention\b", (r"weight|score|focus|relevan",)),
    Template("M02", "mechanism", "paraphrase", "How does naive Bayes pick a class for text?", r"naive bayes|naïve bayes", (r"probab|bayes|class|feature",)),
    Template("M03", "mechanism", "followup", "How does it work?", r"\bRNN\b", (r"hidden|state|time|sequence",), "Where is RNN discussed?"),
    Template("M04", "mechanism", "followup", "How does it work?", r"\bCNN\b", (r"filter|convol|feature|window",), "Where is CNN discussed?"),
    Template("M05", "mechanism", "followup", "How does it work?", r"TF[ -]?IDF", (r"frequency|inverse|weight",), "Where is TF-IDF discussed?"),
    Template("M06", "mechanism", "followup", "How does it work?", r"\bLDA\b", (r"topic|distribution|document",), "Where is LDA discussed?"),
    Template("V01", "measurement", "direct", "What does perplexity measure in language modeling?", r"\bperplexity\b", (r"probab|predict|uncertain|language",)),
    Template("V02", "measurement", "direct", "What does classifier accuracy measure?", r"\baccuracy\b", (r"correct|prediction|class|total",)),
    Template("V04", "measurement", "followup", "What does it combine?", r"\bF1\b|F[ -]?score", (r"precision|recall|harmonic",), "Where is F1 discussed?"),
    Template("V03", "measurement", "followup", "What does it measure?", r"\bROUGE\b", (r"overlap|recall|referenc",), "Where is ROUGE discussed?"),
    Template("R01", "reason", "paraphrase", "Why add probability smoothing for unseen terms?", r"\bsmoothing\b", (r"unseen|zero|sparse|probab",)),
    Template("R02", "reason", "paraphrase", "Why filter frequent stop words from text?", r"stop[ -]?words?", (r"common|frequen|noise|remove|filter",)),
    Template("R03", "reason", "paraphrase", "Why give rare words more weight than common words?", r"TF[ -]?IDF|inverse document frequency", (r"rare|common|discriminat|informative",)),
    Template("R04", "reason", "paraphrase", "Why reduce words to a shared stem?", r"stemming|\bstem\b", (r"vocab|variant|normaliz|reduc",)),
    Template("R07", "reason", "paraphrase", "Why divide text into tokens before analysis?", r"tokeniz", (r"process|model|input|analy",)),
    Template("R05", "reason", "followup", "What does it help with?", r"TF[ -]?IDF", (r"rare|common|informative|discriminat|weight",), "Where is TF-IDF discussed?"),
    Template("R06", "reason", "followup", "What does it help with?", r"\bBERT\b", (r"bidirectional|context|pretrain|represent",), "Where is BERT discussed?"),
    Template("P01", "process", "direct", "How are tokens converted into input IDs?", r"token|vocab", (r"index|id|map|convert|encod",)),
    Template("P02", "process", "direct", "How does a corpus become a term-document matrix?", r"term[ -]document|document[ -]term|matrix", (r"count|frequen|vector|document",)),
    Template("P03", "process", "paraphrase", "Which merges form subword units in byte-pair encoding?", r"byte[ -]pair|\bBPE\b", (r"merge|pair|frequen|subword",)),
    Template("P04", "process", "paraphrase", "How are text features prepared for a classifier?", r"text feature|feature extraction|preprocess", (r"token|vector|class|normaliz",)),
    Template("L01", "property_limitation", "direct", "What does Bag-of-Words lose when it represents text?", r"bag[ -]of[ -]words", (r"word order|context",)),
    Template("L02", "property_limitation", "paraphrase", "What makes Euclidean distance a poor fit for sparse text vectors?", r"euclidean", (r"sparse|high[ -]dimensional",)),
    Template("L03", "property_limitation", "followup", "What limitation does it have?", r"TF[ -]?IDF", (r"word order|context",), "Where is TF-IDF discussed?"),
    Template("L04", "property_limitation", "direct", "What assumption does Naive Bayes make about features?", r"naive bayes|naïve bayes", (r"independen",)),
    Template("E01", "application_example", "direct", "Where is sentiment analysis used?", r"sentiment analysis", (r"customer feedback|product reviews|social media",)),
    Template("E02", "application_example", "paraphrase", "What practical task can machine translation help perform?", r"machine translation", (r"languages?|documents?|texts?",)),
    Template("E03", "application_example", "followup", "Where is it used?", r"\bNLP\b|natural language processing", (r"chatbots?|sentiment|translation",), "Where is NLP discussed?"),
    Template("E04", "application_example", "direct", "What is a practical use of named entity recognition?", r"named entity recognition|\bNER\b", (r"information extraction|anonymiz|medical|legal",)),
)
assert len({item.case_id for item in TEMPLATES}) == len(TEMPLATES)
_CATEGORY_PLAN = {
    "acronym_expansion": ("direct", "followup"),
    "definition": ("direct", "paraphrase"),
    "mechanism": ("paraphrase", "followup"),
    "measurement": ("direct", "followup"),
    "reason": ("paraphrase", "followup"),
    "process": ("direct", "paraphrase"),
    "property_limitation": ("direct", "paraphrase", "followup"),
    "application_example": ("direct", "paraphrase", "followup"),
}
assert all(all(sum(item.relation == relation and item.category == category
                   for item in TEMPLATES) >= 1 for category in _CATEGORY_PLAN[relation])
           for relation in _RELATIONS)


def _sha(value: str | bytes) -> str:
    return sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def _templates_sha(templates: Sequence[Template] = TEMPLATES) -> str:
    if templates is TEMPLATES:
        # Preserve the fingerprint of previously issued static packets.
        payload = {"policy": DISCOVERY_POLICY,
            "templates": [{key: value for key, value in asdict(item).items()
                           if key != "requirements"} for item in templates],
            "requirements": _REQUIREMENTS}
    else:
        payload = {"policy": DISCOVERY_POLICY, "mode": AUTHORED_SPEC_SCHEMA,
            "templates": [asdict(item) for item in templates]}
    return _sha(json.dumps(payload, sort_keys=True, separators=(",", ":")))


# Authored requirements are discovery filters, not semantic quality labels.
# Every group is required within the same body unit; broad topic mentions do
# not establish a definition, operation, metric or reason.
_REQUIREMENTS = {
    "D01": (r"\b(?:assigns?|estimates?|predicts?|represents?|models?)\b", r"probabil|next word", r"word sequence|next word"),
    "D04": (r"\b(?:is|means|refers to)\b", r"\bcollection\b", r"\b(?:texts?|documents?)\b"),
    "D02": (r"\b(?:identifies|recognizes|extracts|detects)\b", r"person|organization|location"),
    "D03": (r"\b(?:assigns?|labels?|tags?)\b", r"noun|verb|grammatical categor|grammatical label"),
    "D05": (r"\b(?:is|are|represents?|encodes?|maps?|captures?)\b", r"\bvectors?\b"),
    "D06": (r"\b(?:is|are|models?|represents?|discovers?|identifies?)\b", r"document", r"theme|topic|distribution"),
    "D07": (r"\b(?:is|are|means|refers to)\b", r"sequence", r"consecutive|contiguous"),
    "D08": (r"sequence", r"consecutive|contiguous"),
    "D09": (r"\b(?:captures?|represents?|encodes?)\b", r"semantic|meaning"),
    "D10": (r"\b(?:groups?|models?|discovers?|identifies?)\b", r"documents?", r"themes?|topics?"),
    "M01": (r"\b(?:assigns?|computes?|weights?|scores?)\b", r"weights?", r"tokens?", r"relevan|focus|importance"),
    "M02": (r"posterior|conditional|likelihood", r"probab", r"\bclass\b", r"\b(?:chooses?|selects?|predicts?|maximi[sz]es?|highest)\b"),
    "M03": (r"\b(?:updates?|carries?|passes?|maintains?)\b", r"hidden state", r"time|sequence|previous"),
    "M04": (r"\b(?:slides?|convolves?|applies?|extracts?)\b", r"filters?|convolut", r"features?|tokens?|windows?"),
    "M05": (r"multipli|product|\bTF\b.{0,80}[×*].{0,80}\bIDF\b", r"term frequency|\bTF\b", r"inverse document frequency|\bIDF\b"),
    "M06": (r"\b(?:assigns?|samples?|estimates?|models?|infers?)\b", r"topics?", r"distributions?", r"documents?"),
    "V01": (r"\b(?:measures?|quantifies?|evaluates?|is)\b", r"uncertain|predict|probab"),
    "V02": (r"correct", r"total|all predictions", r"fraction|ratio|divid|\bover\b|/"),
    "V04": (r"precision", r"recall", r"harmonic|2\s*[×*].{0,100}/"),
    "V03": (r"\b(?:measures?|compares?|evaluates?|is)\b", r"overlap|recall", r"referenc"),
    "R01": (r"unseen|zero", r"\b(?:avoids?|prevents?|handles?|addresses?|ensures?)\b", r"probab"),
    "R02": (r"\b(?:removes?|filters?|reduces?|avoids?)\b", r"noise|uninformative|little information|little meaning"),
    "R03": (r"rare|infrequen", r"common|frequen", r"more|higher|greater|increase|informative|discriminat", r"weights?|importance"),
    "R04": (r"\b(?:reduces?|normalizes?|groups?)\b", r"variants?|vocabular|inflect|forms?"),
    "R07": (r"\b(?:enables?|allows?|prepares?|needed|necessary)\b", r"models?|analysis|processing|input"),
    "R05": (r"rare|infrequen", r"common|frequen", r"more|higher|greater|increase|informative|discriminat", r"weights?|importance"),
    "R06": (r"context", r"\b(?:captures?|understands?|represents?|improves?|enables?)\b", r"bidirectional|both directions"),
    "P01": (r"\b(?:maps?|converts?|encodes?|assigns?)\b", r"tokens?", r"input IDs?|indices|index|integer IDs?", r"vocabular"),
    "P02": (r"\b(?:counts?|constructs?|builds?|converts?|represents?)\b", r"terms?|words?", r"documents?", r"counts?|frequenc"),
    "P03": (r"\b(?:merges?|merging)\b", r"frequen", r"pairs?", r"repeat|iterat"),
    "P04": (r"tokeniz|normaliz", r"vectoriz|feature extraction|extract.{0,50}features", r"\b(?:then|before|followed|pipeline|steps?)\b"),
    "L01": (r"ignore|lose|does not preserve|cannot capture", r"word order|context"),
    "L02": (r"not ideal|poor|unsuitable|sensitive", r"sparse|high[ -]dimensional", r"scale|magnitude"),
    "L03": (r"ignore|lose|does not preserve|cannot capture", r"word order|context"),
    "L04": (r"assum", r"conditional|given the class", r"independen", r"features?"),
    "E01": (r"\b(?:used|applied|applications?|examples?|analy[sz]es?|monitors?)\b", r"customer feedback|product reviews|social media"),
    "E02": (r"\b(?:used|applied|applications?|examples?|translates?|converts?)\b", r"languages?", r"documents?|texts?"),
    "E03": (r"\b(?:used|applied|applications?|examples?)\b", r"chatbots?|sentiment|translation"),
    "E04": (r"\b(?:used|applied|applications?|examples?|extracts?)\b", r"information extraction|anonymiz|medical|legal"),
}
assert all(template.relation == "acronym_expansion" or template.case_id in _REQUIREMENTS
           for template in TEMPLATES)


def _literal(value: Any, *, minimum: int = 2, maximum: int = 100) -> str:
    if (not isinstance(value, str) or not minimum <= len(value) <= maximum
        or value != value.strip() or any(char.isspace() and char != " " for char in value)
        or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ValueError("authored_spec_invalid")
    return value


def _literal_pattern(value: str) -> str:
    # Input is text, never caller-controlled regular-expression syntax.
    return r"(?<!\w)" + r"\s+".join(re.escape(part) for part in value.split(" ")) + r"(?!\w)"


def _unique_json_pairs(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("authored_spec_invalid")
        result[key] = value
    return result


def _load_authored_spec(path: Path, root: Path) -> tuple[tuple[Template, ...], str]:
    """Read a bounded literal-only spec under OS Temp, before any DB read.

    This is a discovery input, not a gold-label file. Even structurally valid
    matches remain unreviewed and cannot satisfy the quality gate by themselves.
    """

    resolved = path.resolve(strict=True)
    if (not path.is_absolute() or not resolved.is_relative_to(root) or resolved == root
        or path.is_symlink() or not resolved.is_file()
        or resolved.stat().st_size > _AUTHORED_SPEC_MAX_BYTES):
        raise ValueError("authored_spec_invalid")
    raw = resolved.read_bytes()
    if not raw or len(raw) > _AUTHORED_SPEC_MAX_BYTES:
        raise ValueError("authored_spec_invalid")
    try:
        value = json.loads(raw, object_pairs_hook=_unique_json_pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("authored_spec_invalid")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("authored_spec_invalid") from exc
    if (not isinstance(value, dict) or set(value) != {"schema", "cases"}
        or value["schema"] != AUTHORED_SPEC_SCHEMA
        or not isinstance(value["cases"], list)
        or not 1 <= len(value["cases"]) <= _AUTHORED_SPEC_MAX_CASES):
        raise ValueError("authored_spec_invalid")
    templates = []
    used = set()
    for row in value["cases"]:
        if (not isinstance(row, dict)
            or set(row) != {"case_id", "relation", "category", "question", "entity",
                           "evidence", "requirements", "previous_turn"}):
            raise ValueError("authored_spec_invalid")
        case_id = row["case_id"]
        relation, category = row["relation"], row["category"]
        if (not isinstance(case_id, str) or _AUTHORED_CASE_ID.fullmatch(case_id) is None
            or case_id in used or not isinstance(relation, str)
            or not isinstance(category, str) or relation not in _CATEGORY_PLAN
            or category not in _CATEGORY_PLAN[relation]):
            raise ValueError("authored_spec_invalid")
        used.add(case_id)
        question = _literal(row["question"], minimum=5, maximum=240)
        if not isinstance(row["previous_turn"], str):
            raise ValueError("authored_spec_invalid")
        previous = _literal(row["previous_turn"], minimum=5, maximum=240) if row["previous_turn"] else ""
        entity = _literal(row["entity"], maximum=80)
        evidence = row["evidence"]
        requirements = row["requirements"]
        if (not isinstance(evidence, list) or not 1 <= len(evidence) <= 4
            or any(not isinstance(item, str) for item in evidence)):
            raise ValueError("authored_spec_invalid")
        evidence_patterns = tuple(_literal_pattern(_literal(item)) for item in evidence)
        if relation == "acronym_expansion":
            if len(evidence_patterns) != 1 or requirements != []:
                raise ValueError("authored_spec_invalid")
            required_patterns = ()
        else:
            if (not isinstance(requirements, list) or not 2 <= len(requirements) <= 5
                or any(not isinstance(group, list) or not 1 <= len(group) <= 4
                       for group in requirements)):
                raise ValueError("authored_spec_invalid")
            required_patterns = tuple("(?:" + "|".join(
                _literal_pattern(_literal(item)) for item in group) + ")"
                for group in requirements)
        if category == "followup":
            # The current local resolver only binds a single explicit prior
            # acronym; a vague or conflicting referent cannot become gold.
            anchors = set(re.findall(r"\b[A-Z][A-Z0-9]{1,11}(?:-[A-Z0-9]{2,11})*\b", previous))
            if (not previous or len(anchors) != 1 or entity not in anchors
                or not re.search(r"\b(?:it|its|this|that|these|those|they|them)\b", question, re.I)
                or re.search(r"\b[A-Z][A-Z0-9]{1,11}(?:-[A-Z0-9]{2,11})*\b", question)):
                raise ValueError("authored_spec_invalid")
        elif previous:
            raise ValueError("authored_spec_invalid")
        templates.append(Template(case_id, relation, category, question,
            _literal_pattern(entity), evidence_patterns, previous, required_patterns))
    return tuple(templates), _sha(raw)

_BULLET = re.compile(r"^\s*(?:[•●▪\-*]|\d+[.)])\s+")
_NON_SOURCE_HEADING = re.compile(r"\b(?:recap|agenda|outline|summary|roadmap|transition|next week|coming next|review questions)\b|^next\s*:", re.I)
_CLAUSE_VERB = re.compile(r"\b(?:is|are|means|assigns?|represents?|measures?|combines?|identifies|maps?|converts?|uses?|updates?|carries?|avoids?|forms?|merges?|computes?|picks?|selects?|captures?|weights?|assumes?|ignores?|loses?)\b", re.I)
_METRICS = (r"\baccuracy\b", r"\bprecision\b", r"\brecall\b", r"\bF1\b|F[ -]?score", r"\bperplexity\b", r"\bROUGE\b", r"\bBLEU\b", r"\bcosine\b", r"\beuclidean\b")
_SUBJECTS = _METRICS + (r"naive bayes|naïve bayes", r"logistic regression", r"\bRNN\b", r"\bCNN\b",
    r"TF[ -]?IDF", r"\bLDA\b", r"\bBERT\b", r"named entity recognition|\bNER\b",
    r"POS tagging", r"language models?", r"word embeddings?", r"tokenization", r"stemming",
    r"machine translation", r"sentiment analysis", r"bag[ -]of[ -]words")


@dataclass(frozen=True)
class SourceUnit:
    start: int
    end: int
    body_start: int
    body_end: int
    heading_start: int | None = None
    heading_end: int | None = None


def _is_heading(line: str) -> bool:
    text = line.strip()
    return (0 < len(text) <= 100 and len(text.split()) <= 12
            and not _BULLET.match(text) and not _CLAUSE_VERB.search(text)
            and "=" not in text and not re.search(r"[.!?]$", text))


def _complete_units(content: str) -> tuple[SourceUnit, ...]:
    """Retain complete lines/bullets and wrapped continuations, never clip.

    A heading is context for a following body, not a body on its own. Sentence
    boundaries split only complete physical lines; offsets always refer to the
    original contiguous string. New bullets/headings never join two subjects.
    """

    lines = []
    cursor = 0
    for line in content.splitlines(keepends=True):
        start = cursor + len(line) - len(line.lstrip())
        end = cursor + len(line.rstrip())
        lines.append((start, end, content[start:end]))
        cursor += len(line)
    units = []
    heading = None
    index = 0
    while index < len(lines):
        start, end, line = lines[index]
        if not line:
            index += 1
            continue
        if _is_heading(line):
            heading = (start, end)
            index += 1
            continue
        stop = index
        # Plain lines without terminal punctuation can be PDF-wrapped
        # continuation. A fresh bullet or heading always starts another unit.
        while (stop + 1 < len(lines) and lines[stop + 1][2]
               and not re.search(r"[.!?;:]$", lines[stop][2])
               and not _BULLET.match(lines[stop + 1][2])
               and not _is_heading(lines[stop + 1][2])):
            stop += 1
        end = lines[stop][1]
        body = content[start:end]
        boundaries = [0] + [match.end() for match in re.finditer(r"(?<=[.!?])\s+(?=[A-Z])", body)] + [len(body)]
        for left, right in zip(boundaries, boundaries[1:]):
            while left < right and body[left].isspace():
                left += 1
            while left < right and body[right - 1].isspace():
                right -= 1
            if left < right:
                body_start, body_end = start + left, start + right
                units.append(SourceUnit(body_start, body_end, body_start, body_end,
                                        *(heading or (None, None))))
        index = stop + 1
    return tuple(units)


def _external_clue(body: str, entity: str, patterns: tuple[str, ...]) -> bool:
    entities = [match.span() for match in re.finditer(entity, body, re.I)]
    return all(any(not any(start < match.end() and match.start() < end for start, end in entities)
                   for match in re.finditer(pattern, body, re.I | re.S)) for pattern in patterns)


def _qualifies_unit(content: str, unit: SourceUnit, template: Template) -> tuple[int, int] | None:
    body = content[unit.body_start:unit.body_end]
    heading = (content[unit.heading_start:unit.heading_end]
               if unit.heading_start is not None else "")
    if _NON_SOURCE_HEADING.search(heading) or _NON_SOURCE_HEADING.search(body[:100]):
        return None
    explicit = re.search(template.entity, body, re.I) is not None
    owning = re.search(template.entity, heading, re.I) is not None
    if not explicit and not owning:
        return None
    contextual = ({"V04": (r"\bprecision\b", r"\brecall\b"),
                   "V03": (r"\brecall\b",), "V01": (r"language models?",),
                   "E03": (r"sentiment analysis", r"machine translation")}
                  .get(template.case_id, ()))
    if not explicit and any(re.search(pattern, body, re.I)
            and not any(re.fullmatch(alias, match.group(), re.I) for match in re.finditer(pattern, body, re.I)
                        for alias in contextual) for pattern in _SUBJECTS):
        # An owning heading does not let a differently named body's relation
        # become evidence for the heading's subject.
        return None
    start = unit.body_start if explicit else unit.heading_start
    assert start is not None
    quote = content[start:unit.body_end]
    clue_text = quote if template.relation == "acronym_expansion" else body
    if not 30 <= len(quote) <= _CONTENT_CAP or not _external_clue(
            clue_text, template.entity, template.evidence):
        return None
    if template.relation == "acronym_expansion":
        expansion = template.evidence[0]
        linked = (rf"(?:{template.entity})\s*(?:\(|=|:|[-–—]|stands for|means|expands to|is short for)\s*(?:{expansion})"
                  rf"|(?:{expansion})\s*\(\s*(?:{template.entity})\s*\)")
        if not re.search(linked, quote, re.I | re.S):
            return None
    elif not all(re.search(pattern, body, re.I | re.S) for pattern in (
            template.requirements if template.requirements is not None
            else _REQUIREMENTS[template.case_id])):
        return None
    if template.relation == "measurement":
        allowed = ((template.entity, r"\bprecision\b", r"\brecall\b") if template.case_id == "V04"
                   else (template.entity, r"\brecall\b") if template.case_id == "V03"
                   else (template.entity,))
        for metric in _METRICS:
            if re.search(metric, body, re.I) and not any(re.search(alias, match.group(), re.I)
                    for match in re.finditer(metric, body, re.I) for alias in allowed):
                return None
    return start, unit.body_end


def _source_windows(content: str, template: Template) -> tuple[tuple[int, int], ...]:
    windows = {_qualifies_unit(content, unit, template) for unit in _complete_units(content)}
    return tuple(sorted((window for window in windows if window is not None),
                        key=lambda value: (value[1] - value[0], value[0], value[1])))


def _source_window(content: str, template: Template) -> tuple[int, int] | None:
    windows = _source_windows(content, template)
    return windows[0] if windows else None


def _page_span(page: str, quote: str) -> tuple[int, int] | None:
    if not quote or len(quote) > _CONTENT_CAP:
        return None
    start = page.find(quote)
    if start >= 0:
        return (start, start + len(quote)) if page.count(quote) == 1 else None
    words = quote.split()
    matches = list(re.finditer(r"\s+".join(re.escape(word) for word in words), page))
    return (matches[0].start(), matches[0].end()) if len(matches) == 1 else None


def _source_record(chunk: Any, page: str, start: int, end: int, slot: int) -> dict:
    quote = chunk.content[start:end]
    span = _page_span(page, quote)
    if span is None or not 0 <= start < end <= len(chunk.content) or len(quote) > _CONTENT_CAP:
        raise ValueError("source_unavailable")
    return {"chunk_id": str(chunk.chunk_id), "document_id": str(chunk.document_id),
        "document_slot": slot, "document_title": chunk.document_title,
        "page_number": chunk.page_number, "content_revision_id": str(chunk.content_revision_id),
        "index_revision_id": str(chunk.index_revision_id), "corpus_revision": chunk.corpus_revision,
        "embedding_space_hash": chunk.embedding_space_hash, "chunk_sha256": _sha(chunk.content),
        "page_sha256": _sha(page), "quote_sha256": _sha(quote),
        "quote_start": start, "quote_end": end,
        "page_reference_start": span[0], "page_reference_end": span[1]}


def _source_identity(row: dict) -> tuple[str, int]:
    return row["document_id"], row["page_number"]


def discover_candidates(chunks: Sequence[Any], pages: dict, slots: dict,
                        excluded_pages: set[tuple[str, int]],
                        templates: Sequence[Template] = TEMPLATES) -> tuple[list[dict], list[dict], dict]:
    """Author-template source discovery only; no runtime rank or quality label."""

    ordered = sorted(chunks, key=lambda item: (slots.get(item.document_id, 999),
                    item.page_number, str(item.chunk_id)))
    # Enumerate all eligible exact units before assigning category slots. This
    # avoids selecting a page merely because it was the first topic mention.
    pool = []
    by_template_id = {item.case_id: item for item in templates}
    if len(by_template_id) != len(templates):
        raise ValueError("authored_spec_invalid")
    for template_index, template in enumerate(templates):
        for chunk in ordered:
            pointer = (str(chunk.document_id), chunk.page_number)
            page = pages.get(chunk.chunk_id)
            if pointer in excluded_pages or page is None or chunk.document_id not in slots:
                continue
            for bounds in _source_windows(chunk.content, template):
                if _page_span(page, chunk.content[bounds[0]:bounds[1]]) is None:
                    continue
                pool.append({"case_id": template.case_id, "relation": template.relation,
                    "category": template.category, "question": template.question,
                    "previous_turn": template.previous_turn,
                    "entity_pattern": template.entity,
                    "source": _source_record(chunk, page, *bounds, slots[chunk.document_id]),
                    "labels": {"source_fidelity": "unreviewed", "excerpt_sufficient": "unreviewed",
                               "page_useful": "unreviewed"},
                    "_order": (template_index, slots[chunk.document_id], chunk.page_number,
                               str(chunk.chunk_id), bounds[0], bounds[1])})
    positives, assignment = _assign_positive_candidates(pool)
    for row in positives:
        row.pop("_order", None)
    insufficient = []
    by_id = {str(chunk.chunk_id): chunk for chunk in ordered}
    for relation in _RELATIONS:
        controls = [row for row in positives if row["relation"] == relation]
        if not controls:
            continue
        options = []
        for target in controls:
            template = by_template_id[target["case_id"]]
            for origin in pool:
                source = origin["source"]
                if _source_identity(source) == _source_identity(target["source"]):
                    continue
                src = by_id[source["chunk_id"]]
                quote = src.content[source["quote_start"]:source["quote_end"]]
                names_target = re.search(target["entity_pattern"], quote, re.I) is not None
                if origin["relation"] == relation and not names_target:
                    kind = "wrong_entity_same_relation"
                elif (origin["relation"] != relation and names_target
                      and not _source_windows(quote, template)):
                    # Absence of an authored predicate is a candidate control,
                    # never an automatic semantic insufficiency label.
                    kind = "same_entity_other_relation"
                else:
                    continue
                options.append((kind, target, origin))
        options.sort(key=lambda item: (item[0] != "same_entity_other_relation",
                                        item[1]["case_id"], item[2]["_order"]))
        used_sources = set()
        for kind, target, origin in options:
            source = origin["source"]
            pointer = (source["chunk_id"], source["quote_start"], source["quote_end"])
            if pointer in used_sources:
                continue
            used_sources.add(pointer)
            insufficient.append({"case_id": f"I-{relation}-{len(used_sources):02d}",
                "relation": relation, "category": target["category"],
                "question": target["question"], "previous_turn": target["previous_turn"],
                "paired_positive_case_id": target["case_id"],
                "source_candidate_case_id": origin["case_id"], "control_type": kind,
                "source": source, "labels": {"source_fidelity": "unreviewed",
                    "excerpt_sufficient": "unreviewed", "page_useful": "unreviewed"}})
            if len(used_sources) == 2:
                break
    counts = {"positive_candidates": len(positives), "insufficient_pair_candidates": len(insufficient),
        "missing_positive_candidates": 12-len(positives), "missing_insufficient_pairs": _INSUFFICIENT_TARGET-len(insufficient),
        "positive_documents": len({row["source"]["document_id"] for row in positives}),
        "positive_distinct_pages": len({_source_identity(row["source"]) for row in positives}),
        "positive_by_category": {category: sum(row["category"] == category for row in positives)
                                 for category in ("direct", "paraphrase", "followup")}}
    return positives, insufficient, {"counts": counts, "assignment": assignment,
        "enumerated_candidates": len(pool),
        "candidate_pages_by_category": {category: len({_source_identity(row["source"])
            for row in pool if row["category"] == category})
            for category in ("direct", "paraphrase", "followup")},
        "candidate_pages_by_relation": {relation: len({_source_identity(row["source"])
            for row in pool if row["relation"] == relation}) for relation in _RELATIONS},
        "missing_positive_relations": [relation for relation in _RELATIONS
            if not any(row["relation"] == relation for row in positives)],
        "missing_insufficient_by_relation": {relation: max(0, 2-sum(
            row["relation"] == relation for row in insufficient)) for relation in _RELATIONS}}


def _assign_positive_candidates(pool: list[dict]) -> tuple[list[dict], dict]:
    """Bounded deterministic assignment; 4/category and ≥1/relation.

    Page/template identity is unique. The search reports its bound explicitly;
    an exhausted search never proves capacity or lowers the release gate.
    """

    categories = ("direct", "paraphrase", "followup")
    unique = {}
    for row in sorted(pool, key=lambda item: item["_order"]):
        unique.setdefault((row["case_id"], _source_identity(row["source"])), row)
    candidates = list(unique.values())
    best = []
    nodes = 0
    limit = 100_000
    complete = False

    def search(chosen: list[dict], used_pages: set, used_cases: set, counts: dict):
        nonlocal nodes, best, complete
        nodes += 1
        if nodes > limit or complete:
            return
        covered = {row["relation"] for row in chosen}
        if (len(chosen), len(covered)) > (len(best), len({row["relation"] for row in best})):
            best = list(chosen)
        if len(chosen) == 12:
            complete = len(covered) == len(_RELATIONS)
            return
        eligible = [row for row in candidates if row["case_id"] not in used_cases
                    and _source_identity(row["source"]) not in used_pages
                    and counts[row["category"]] < 4]
        active = [category for category in categories if counts[category] < 4]
        if not active:
            return
        group = min(active, key=lambda category: (sum(row["category"] == category for row in eligible),
                                                  categories.index(category)))
        options = [row for row in eligible if row["category"] == group]
        options.sort(key=lambda row: (row["relation"] in covered, row["_order"]))
        for row in options:
            next_counts = dict(counts)
            next_counts[group] += 1
            search(chosen + [row], used_pages | {_source_identity(row["source"])},
                   used_cases | {row["case_id"]}, next_counts)
            if complete or nodes > limit:
                return
        # Missing structural candidates stay missing. Skip the unavailable
        # category so the partial report still inventories the other groups.
        if not options:
            next_counts = dict(counts)
            next_counts[group] = 4
            search(chosen, used_pages, used_cases, next_counts)

    search([], set(), set(), dict.fromkeys(categories, 0))
    result = [dict(row) for row in sorted(best, key=lambda item: item["_order"])]
    return result, {"complete_category_and_relation_assignment": complete,
        "search_nodes": min(nodes, limit), "search_limit": limit,
        "search_exhausted": nodes > limit}


def _load_old_exclusions(old_gold: Path, old_alternatives: Path, root: Path) -> tuple[set[tuple[str, int]], dict]:
    def read(path: Path, version: str) -> tuple[dict, str]:
        resolved = path.resolve(strict=True)
        if (not resolved.is_relative_to(root) or resolved == root or path.is_symlink()
            or resolved.stat().st_size > 512_000):
            raise ValueError("private_input_invalid")
        raw = resolved.read_bytes()
        value = json.loads(raw)
        if value.get("version") != version:
            raise ValueError("private_input_invalid")
        return value, _sha(raw)
    gold, gold_sha = read(old_gold, "source_navigation_holdout_gold_v1")
    alternatives, alternatives_sha = read(old_alternatives, "source_gold_context_alternatives_v1")
    old_scope = gold.get("scope")
    if (alternatives.get("original_roster_sha256") != gold_sha
        or not isinstance(old_scope, dict)
        or set(old_scope) != {"corpus_revision", "embedding_space_hash"}
        or alternatives.get("scope") != old_scope):
        raise ValueError("private_input_invalid")
    excluded = {(str(UUID(item["gold_document_id"])), int(item["gold_page"])) for item in gold["cases"]}
    excluded.update((str(UUID(item["gold_document_id"])), int(item["page"]))
                    for item in alternatives["candidates"])
    return excluded, {"old_gold_sha256": gold_sha, "old_alternatives_sha256": alternatives_sha,
                      "old_review_pages_excluded": len(excluded), "old_scope": old_scope}


def _load_development_exclusions(paths: Sequence[Path], root: Path,
                                expected_scope: dict) -> tuple[set[tuple[str, int]], list[str]]:
    """Previously exposed packet pages are development, regardless of labels."""

    if not paths:
        raise ValueError("development_exclusions_required")
    excluded, digests = set(), []
    for path in paths:
        resolved = path.resolve(strict=True)
        if (not resolved.is_relative_to(root) or resolved == root or path.is_symlink()
            or resolved.stat().st_size > 512_000):
            raise ValueError("private_input_invalid")
        raw = resolved.read_bytes()
        packet = json.loads(raw)
        scope = packet.get("scope", {})
        if (packet.get("schema") != SCHEMA or packet.get("source_frozen") is not True
            or {"corpus_revision": scope.get("corpus_revision"),
                "embedding_space_hash": scope.get("space_hash")} != expected_scope):
            raise ValueError("private_input_invalid")
        for row in packet["positives"] + packet["insufficient_pairs"]:
            excluded.add((str(UUID(row["source"]["document_id"])), int(row["source"]["page_number"])))
        digests.append(_sha(raw))
    return excluded, digests


def _output_root() -> Path:
    raw = os.getenv(OUTPUT_ENV, "")
    if not raw or not Path(raw).is_absolute():
        raise ValueError("output_root_unavailable")
    root = Path(raw).resolve(strict=True)
    if root != Path(tempfile.gettempdir()).resolve(strict=True) or not root.is_dir():
        raise ValueError("output_root_unavailable")
    return root


def render(manifest: dict, chunks_by_id: dict, pages: dict) -> str:
    cards = []
    for category, rows in (("Candidate complete references", manifest["positives"]),
                           ("Candidate insufficient pairs", manifest["insufficient_pairs"])):
        cards.append("<h2>" + escape(category) + "</h2>")
        for row in rows:
            source = row["source"]
            chunk = chunks_by_id[source["chunk_id"]]
            quote = chunk.content[source["quote_start"]:source["quote_end"]]
            page = pages[chunk.chunk_id]
            pos = source["page_reference_start"]
            context = page[max(0, pos-320):min(len(page), source["page_reference_end"]+320)]
            previous = ("<p><strong>Prior user turn:</strong> " + escape(row["previous_turn"]) + "</p>"
                        if row["previous_turn"] else "")
            relation = row["relation"].replace("_", " ")
            paired = ("<p>Paired complete-candidate control: " + escape(row["paired_positive_case_id"])
                      + "; source-discovery template " + escape(row["source_candidate_case_id"])
                      + "; candidate pair type " + escape(row["control_type"])
                      + ".</p>" if "paired_positive_case_id" in row else "")
            cards.append("<section><h3>" + escape(row["case_id"]) + " · " + escape(relation)
                + "</h3><p>Knowledge: " + escape(source["document_title"])
                + " (slot " + str(source["document_slot"]) + "), PDF page "
                + str(source["page_number"]) + "</p>" + previous + "<p><strong>Question:</strong> "
                + escape(row["question"]) + "</p>" + paired + "<pre>" + escape(quote) + "</pre>"
                + "<details><summary>Canonical page context</summary><pre>" + escape(context)
                + "</pre></details><p>For this exact question and excerpt: is the entity and requested "
                + "relation covered with enough context to guide reading? Yes / No / Unsure.</p>"
                + "<p>Separately: does the original PDF page help investigate the question? "
                + "Yes / No / Unsure. Also check that the source text/identifier is correct.</p></section>")
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="referrer" content="no-referrer">'
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
        'style-src &#39;unsafe-inline&#39;; form-action &#39;none&#39;; base-uri &#39;none&#39;">'
        '<title>Private source sufficiency review</title><style>'
        'body{font:16px/1.5 system-ui;max-width:900px;margin:2rem auto;padding:1rem}'
        'section{border:1px solid #abc;padding:1rem;margin:1rem 0}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef;padding:1rem}</style>'
        '<h1>Unreviewed source-sufficiency candidates</h1>'
        '<p>Source discovery uses authored patterns, not Ask ranking. “Complete” and “insufficient” '
        'are candidate groups only; neither has an owner label. A wrong-entity pair does not mean '
        'the question has no suitable source elsewhere. Review the exact excerpt and PDF page. '
        'Report labels by case ID, without copying private text into chat.</p>'
        + "".join(cards) + "</html>")


def convert_reviewed_roster(manifest: dict, review: dict,
                            templates: Sequence[Template] = TEMPLATES) -> tuple[dict, dict]:
    """Convert only a complete owner-reviewed packet to display-probe inputs.

    The positive roster is source gold, not displayed-window proof. A separate
    control file preserves exact insufficient question/source pairs for the
    future source-qualification gate. No labels are inferred from patterns.
    """

    if (manifest.get("schema") != SCHEMA or manifest.get("source_frozen") is not True
        or manifest.get("owner_reviewed") is not False
        or manifest.get("authored_templates_sha256") != _templates_sha(templates)
        or manifest.get("authored_template_mode", "fixed_v1") != (
            "fixed_v1" if templates is TEMPLATES else AUTHORED_SPEC_SCHEMA)
        or review.get("candidate_roster_sha256") != _sha(json.dumps(manifest, sort_keys=True,
                                                                   separators=(",", ":"), ensure_ascii=False))):
        raise ValueError("review_binding_invalid")
    positives = manifest["positives"]
    insufficient = manifest["insufficient_pairs"]
    authored_by_id = {item.case_id: item for item in templates}
    if (len(authored_by_id) != len(templates) or any(
        (template := authored_by_id.get(row.get("case_id"))) is None
        or any(row.get(key) != getattr(template, attribute) for key, attribute in (
            ("relation", "relation"), ("category", "category"),
            ("question", "question"), ("previous_turn", "previous_turn"),
            ("entity_pattern", "entity"))) for row in positives)):
        raise ValueError("review_binding_invalid")
    if (len(positives) != 12 or len(insufficient) < _INSUFFICIENT_TARGET
        or len({_source_identity(row["source"]) for row in positives}) != 12
        or len({row["source"]["document_id"] for row in positives}) < 2
        or {row["relation"] for row in positives} != set(_RELATIONS)
        or any(not any(row["relation"] == relation for row in positives)
               or sum(row["relation"] == relation for row in insufficient) < 2
               for relation in _RELATIONS)
        or any(sum(row["category"] == category for row in positives) != 4
               for category in ("direct", "paraphrase", "followup"))
        or any(row["category"] == "followup" and not row["previous_turn"]
               for row in positives)):
        raise ValueError("candidate_set_incomplete")
    rows = positives + insufficient
    by_positive = {row["case_id"]: row for row in positives}
    if len({row["case_id"] for row in rows}) != len(rows):
        raise ValueError("candidate_set_incomplete")
    for row in insufficient:
        paired = by_positive.get(row.get("paired_positive_case_id"))
        if (paired is None or any(row.get(key) != paired.get(key)
            for key in ("relation", "category", "question", "previous_turn"))
            or row.get("control_type") not in ("wrong_entity_same_relation", "same_entity_other_relation")):
            raise ValueError("candidate_set_incomplete")
    for relation in _RELATIONS:
        identities = {(row["source"]["chunk_id"], row["source"]["quote_start"], row["source"]["quote_end"])
                      for row in insufficient if row["relation"] == relation}
        if len(identities) < 2:
            raise ValueError("candidate_set_incomplete")
    labels = review.get("labels")
    if not isinstance(labels, dict) or set(labels) != {row["case_id"] for row in rows}:
        raise ValueError("review_incomplete")
    for row in rows:
        decision = labels[row["case_id"]]
        if (not isinstance(decision, dict)
            or set(decision) != {"source_fidelity", "excerpt_sufficient", "page_useful"}
            or any(value not in ("Yes", "No", "Unsure") for value in decision.values())
            or decision["source_fidelity"] != "Yes"
            or (row in positives and (decision["excerpt_sufficient"] != "Yes"
                                      or decision["page_useful"] != "Yes"))
            or (row in insufficient and (decision["excerpt_sufficient"] != "No"
                                         or decision["page_useful"] == "Unsure"))):
            raise ValueError("review_incomplete")
    from evaluate_private_source_display import Case, FrozenRoster, Scope, roster_fingerprint, runtime_fingerprint
    scope_data = manifest["scope"]
    scope = Scope(UUID(scope_data["principal_id"]), UUID(scope_data["subject_id"]),
        tuple(UUID(value) for value in scope_data["document_ids"]),
        scope_data["corpus_revision"], scope_data["space_hash"])
    cases = tuple(Case(row["case_id"], row["question"], UUID(row["source"]["document_id"]),
        row["source"]["page_number"], True,
        (("user", row["previous_turn"]),) if row["previous_turn"] else ()) for row in positives)
    frozen = FrozenRoster(cases, scope, roster_fingerprint(cases, scope), runtime_fingerprint())
    positive_roster = {"schema": "source_only_display_roster_v1", "frozen": True,
        "scope": {"principal_id": str(scope.principal_id), "subject_id": str(scope.subject_id),
                  "document_ids": [str(value) for value in scope.document_ids],
                  "corpus_revision": scope.corpus_revision, "space_hash": scope.space_hash},
        "cases": [{"case_id": case.case_id, "question": case.question,
                   "gold_document_id": str(case.gold_document_id),
                   "gold_page_number": case.gold_page_number,
                   "owner_reviewed_gold": case.owner_reviewed_gold,
                   "history": [list(turn) for turn in case.history]} for case in cases],
        "roster_sha256": frozen.roster_sha256, "runtime_sha256": frozen.runtime_sha256}
    controls = {"schema": "source_sufficiency_reviewed_controls_v1",
        "frozen": True, "owner_reviewed": True,
        "runtime_sha256": frozen.runtime_sha256, "scope": positive_roster["scope"],
        "evaluator_sha256": _sha(Path(__file__).with_name("evaluate_private_source_sufficiency.py").read_bytes()),
        "source_candidate_sha256": review["candidate_roster_sha256"],
        "control_types": sorted({row["control_type"] for row in insufficient}),
        "whole_question_unsupported": False,
        "positive_groups": {category: [row["case_id"] for row in positives if row["category"] == category]
                            for category in ("direct", "paraphrase", "followup")},
        "pairs": [{"case_id": row["case_id"], "relation": row["relation"],
            "category": row["category"], "question": row["question"],
            "previous_turn": row["previous_turn"],
            "paired_positive_case_id": row["paired_positive_case_id"],
            "source_candidate_case_id": row["source_candidate_case_id"],
            "control_type": row["control_type"],
            "source": row["source"], "owner_labels": labels[row["case_id"]],
            "sufficient_source": next(positive["source"] for positive in positives
                if positive["case_id"] == row["paired_positive_case_id"]),
            "sufficient_owner_labels": labels[row["paired_positive_case_id"]]}
            for row in insufficient]}
    controls["controls_sha256"] = _sha(json.dumps(controls, sort_keys=True,
        separators=(",", ":"), ensure_ascii=False))
    return positive_roster, controls


def _seed_pages(chunks: Sequence[Any]) -> set[tuple[str, int]]:
    excluded = set()
    for page, patterns in _DEVELOPMENT_SEED_PAGES:
        matches = [chunk for chunk in chunks if chunk.page_number == page
                   and all(re.search(pattern, f"{chunk.section or ''}\n{chunk.content}", re.IGNORECASE)
                           for pattern in patterns)]
        if len(matches) != 1:
            raise ValueError("seed_identity_unavailable")
        excluded.add((str(matches[0].document_id), page))
    return excluded


async def _authorized_snapshot() -> tuple[dict, tuple[Any, ...], dict, dict]:
    """Read canonical pages behind the same published/authorized SQL scope.

    The source view enforces publication/readiness/revision. Explicit Subject,
    owner, selected-document and active-space predicates remain in both reads.
    The transaction is repeatable-read and read-only; a second snapshot must
    agree before private text is written.
    """

    from sqlalchemy import bindparam, select, text
    from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID
    from app.database import async_session_maker
    from app.models.knowledge import SubjectDocument
    from app.models.rag import RagAnswerJob, RagMessage
    from app.models.user import User, UserRole
    from app.services.knowledge_retrieval import KnowledgeRetriever
    from app.time_utils import utcnow

    chunks_sql = text("""
        SELECT eligible.id AS chunk_id, eligible.document_id,
               eligible.document_title, eligible.content_revision_id,
               eligible.index_revision_id, eligible.page_number,
               eligible.section, eligible.content, eligible.corpus_revision,
               eligible.embedding_space_hash
        FROM eligible_subject_knowledge_chunks AS eligible
        JOIN subjects AS subject ON subject.id = eligible.subject_id
        JOIN users AS principal ON principal.id = :principal_id
        WHERE eligible.subject_id = :subject_id
          AND eligible.corpus_revision = :corpus_revision
          AND eligible.embedding_space_hash = :space_hash
          AND subject.active_embedding_space_hash = eligible.embedding_space_hash
          AND (NOT :has_document_filter OR eligible.document_id = ANY(:document_ids))
          AND principal.role = 'INSTRUCTOR'
          AND subject.instructor_id = principal.id
        ORDER BY eligible.document_id, eligible.page_number,
                 eligible.chunk_index, eligible.id
        LIMIT 501
    """).bindparams(
        bindparam("principal_id", type_=PGUUID(as_uuid=True)),
        bindparam("subject_id", type_=PGUUID(as_uuid=True)),
        bindparam("document_ids", type_=ARRAY(PGUUID(as_uuid=True))),
    )
    page_sql = text("""
        SELECT eligible.id AS chunk_id, page.content AS page_content
        FROM eligible_subject_knowledge_chunks AS eligible
        JOIN subject_document_pages AS page
          ON page.content_revision_id = eligible.content_revision_id
         AND page.document_id = eligible.document_id
         AND page.subject_id = eligible.subject_id
         AND page.uploader_id = eligible.uploader_id
         AND page.page_number = eligible.page_number
        JOIN subjects AS subject ON subject.id = eligible.subject_id
        JOIN users AS principal ON principal.id = :principal_id
        WHERE eligible.id = ANY(:chunk_ids)
          AND eligible.subject_id = :subject_id
          AND eligible.corpus_revision = :corpus_revision
          AND eligible.embedding_space_hash = :space_hash
          AND subject.active_embedding_space_hash = eligible.embedding_space_hash
          AND principal.role = 'INSTRUCTOR'
          AND subject.instructor_id = principal.id
        ORDER BY eligible.id
        LIMIT 501
    """).bindparams(
        bindparam("principal_id", type_=PGUUID(as_uuid=True)),
        bindparam("subject_id", type_=PGUUID(as_uuid=True)),
        bindparam("chunk_ids", type_=ARRAY(PGUUID(as_uuid=True))),
    )
    async with async_session_maker() as db:
        await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        matching = (RagMessage.role == "user", RagMessage.content.ilike("%BLEU%"),
                    RagMessage.expires_at > utcnow())
        owner_ids = (await db.scalars(select(RagAnswerJob.user_id).join(
            RagMessage, RagMessage.id == RagAnswerJob.question_message_id)
            .where(*matching).distinct().limit(2))).all()
        if len(owner_ids) != 1:
            raise ValueError("scope_unavailable")
        job = (await db.scalars(select(RagAnswerJob).join(
            RagMessage, RagMessage.id == RagAnswerJob.question_message_id)
            .where(*matching, RagAnswerJob.user_id == owner_ids[0])
            .order_by(RagAnswerJob.created_at.desc(), RagAnswerJob.id.desc()).limit(1))).one_or_none()
        user = await db.get(User, owner_ids[0])
        if job is None or user is None or user.role != UserRole.INSTRUCTOR:
            raise ValueError("scope_unavailable")
        selected = tuple(UUID(str(value)) for value in job.document_ids)
        retriever = await KnowledgeRetriever.authorize(db, principal=user, subject_id=job.subject_id,
            query="current source sufficiency packet", document_ids=selected)
        authorized = retriever.scope
        if (authorized.corpus_revision != job.corpus_revision
            or authorized.embedding_space_hash != job.embedding_space_hash):
            raise ValueError("scope_changed")
        scope = {"principal_id": str(user.id), "subject_id": str(job.subject_id),
            "scope_job_id": str(job.id),
            "document_ids": [str(value) for value in authorized.document_ids],
            "corpus_revision": authorized.corpus_revision,
            "space_hash": authorized.embedding_space_hash}
        params = {"principal_id": user.id, "subject_id": job.subject_id,
                  "corpus_revision": authorized.corpus_revision,
                  "space_hash": authorized.embedding_space_hash,
                  "has_document_filter": bool(authorized.document_ids),
                  "document_ids": list(authorized.document_ids)}
        rows = (await db.execute(chunks_sql, params)).mappings().all()
        if not rows or len(rows) > 500:
            raise ValueError("eligible_corpus_unavailable")
        chunks = tuple(SimpleNamespace(**row) for row in rows)
        ordered_ids = (await db.scalars(select(SubjectDocument.id).where(
            SubjectDocument.subject_id == job.subject_id,
            SubjectDocument.uploader_id == user.id,
        ).order_by(SubjectDocument.updated_at.desc(), SubjectDocument.id).limit(501))).all()
        if len(ordered_ids) > 500:
            raise ValueError("document_list_unavailable")
        slots = {document_id: index for index, document_id in enumerate(ordered_ids, 1)}
        if (any(chunk.document_id not in slots for chunk in chunks)
            or (authorized.document_ids and any(chunk.document_id not in authorized.document_ids
                                                for chunk in chunks))):
            raise ValueError("scope_changed")
        page_rows = (await db.execute(page_sql, {"principal_id": user.id,
            "subject_id": job.subject_id, "corpus_revision": authorized.corpus_revision,
            "space_hash": authorized.embedding_space_hash,
            "chunk_ids": [chunk.chunk_id for chunk in chunks]})).mappings().all()
        pages = {row["chunk_id"]: row["page_content"] for row in page_rows}
        if len(pages) != len(chunks) or any(chunk.chunk_id not in pages for chunk in chunks):
            raise ValueError("canonical_page_unavailable")
        await db.rollback()
        return scope, chunks, pages, slots


async def build(old_gold: Path, old_alternatives: Path,
                development_packets: Sequence[Path],
                authored_spec: Path | None = None) -> dict:
    root = _output_root()  # Fail before any private DB read.
    templates, authored_spec_sha = (_load_authored_spec(authored_spec, root)
        if authored_spec is not None else (TEMPLATES, None))
    excluded, prior = _load_old_exclusions(old_gold, old_alternatives, root)
    development_pages, development_digests = _load_development_exclusions(
        development_packets, root, prior["old_scope"])
    excluded.update(development_pages)
    prior["exposed_candidate_packet_sha256"] = development_digests
    prior["exposed_candidate_pages_excluded"] = len(development_pages)
    from app.database import close_database
    try:
        scope, chunks, pages, slots = await _authorized_snapshot()
        if prior["old_scope"] != {"corpus_revision": scope["corpus_revision"],
                                  "embedding_space_hash": scope["space_hash"]}:
            raise ValueError("scope_changed")
        seed_pages = _seed_pages(chunks)
        excluded.update(seed_pages)
        all_pages = {(str(chunk.document_id), chunk.page_number) for chunk in chunks}
        inventory = {"eligible_chunks": len(chunks), "eligible_pages": len(all_pages),
            "reviewed_pages_excluded": prior["old_review_pages_excluded"],
            "exposed_candidate_pages_excluded": len(development_pages),
            "development_seed_pages_excluded": len(seed_pages),
            "excluded_pages_total": len(excluded),
            "candidate_pages_after_exclusions": len(all_pages - excluded)}
        positives, negatives, discovery = discover_candidates(chunks, pages, slots, excluded, templates)
        # Fresh authorized/canonical snapshot before saving any candidate text.
        current_scope, again, current_pages, _slots = await _authorized_snapshot()
        if current_scope != scope:
            raise ValueError("scope_changed")
        by_id = {str(chunk.chunk_id): chunk for chunk in again}
        for row in (*positives, *negatives):
            source = row["source"]
            chunk = by_id.get(source["chunk_id"])
            if (chunk is None or chunk.chunk_id not in current_pages
                or _sha(chunk.content) != source["chunk_sha256"]
                or _sha(current_pages[chunk.chunk_id]) != source["page_sha256"]
                or str(chunk.content_revision_id) != source["content_revision_id"]
                or str(chunk.index_revision_id) != source["index_revision_id"]):
                raise ValueError("source_changed")
        manifest = {"schema": SCHEMA, "status": "candidate_unreviewed", "source_frozen": True,
            "owner_reviewed": False, "authored_templates_sha256": _templates_sha(templates),
            "authored_template_mode": (AUTHORED_SPEC_SCHEMA if authored_spec is not None else "fixed_v1"),
            "authored_spec_sha256": authored_spec_sha,
            "discovery_policy_id": DISCOVERY_POLICY,
            "scope": scope, "excluded_development_sources": prior,
            "positives": positives, "insufficient_pairs": negatives,
            "discovery": discovery, "inventory": inventory,
            "provider_calls": 0, "database_writes": 0}
        directory = Path(tempfile.mkdtemp(prefix="cardchemy-source-sufficiency-", dir=root))
        directory.chmod(0o700)
        roster = directory / "candidate-roster.json"
        packet = directory / "review.html"
        roster.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        packet.write_text(render(manifest, {str(chunk.chunk_id): chunk for chunk in again}, current_pages),
                          encoding="utf-8")
        roster.chmod(0o600)
        packet.chmod(0o600)
        counts = discovery["counts"]
        return {"status": "unreviewed_candidate_packet_written",
            "positive_candidates": counts["positive_candidates"],
            "insufficient_pair_candidates": counts["insufficient_pair_candidates"],
            "missing_positive_candidates": counts["missing_positive_candidates"],
            "missing_insufficient_pairs": counts["missing_insufficient_pairs"],
            "positive_distinct_pages": counts["positive_distinct_pages"],
            "positive_documents": counts["positive_documents"],
            "positive_by_category": counts["positive_by_category"],
            "inventory": inventory,
            "all_labels_unreviewed": True, "provider_calls": 0,
            "database_writes": 0, "packet_directory": directory.name}
    finally:
        await close_database()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--old-holdout", type=Path)
    parser.add_argument("--old-alternatives", type=Path)
    parser.add_argument("--development-packet", type=Path, action="append", default=[])
    parser.add_argument("--authored-spec", type=Path,
        help="Literal-only private JSON under the current OS Temp directory; --create only.")
    args = parser.parse_args()
    if not args.create:
        print(json.dumps({"status": "preflight_unexecuted", "authored_templates": (
            None if args.authored_spec is not None else len(TEMPLATES)),
            "authored_input_requested": args.authored_spec is not None,
            "target_positive_cases": 12, "target_insufficient_pairs": _INSUFFICIENT_TARGET,
            "provider_calls": 0, "database_reads": 0, "database_writes": 0,
            "all_labels_unreviewed": True}, separators=(",", ":")))
        return 0
    if args.old_holdout is None or args.old_alternatives is None or not args.development_packet:
        print('{"status":"packet_unavailable","reason":"private_inputs_required","provider_calls":0}')
        return 1
    try:
        result = asyncio.run(build(args.old_holdout, args.old_alternatives,
                                   args.development_packet, args.authored_spec))
    except Exception:
        print('{"status":"packet_unavailable","reason":"source_or_output_unavailable","provider_calls":0}')
        return 1
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
