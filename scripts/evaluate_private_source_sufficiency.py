"""Owner-reviewed exact-window source-pair audit; default is entirely offline.

This diagnostic never retrieves, embeds, generates an answer, verifies an
answer, mutates a database or enables Ask. A passing pair audit is not a release
gate: retrieval/display/page-route and access gates remain independent.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Callable, Protocol
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "source_sufficiency_reviewed_controls_v1"
RELATIONS = {
    "acronym_expansion": "acronym", "definition": "definition",
    "mechanism": "mechanism", "measurement": "measurement", "reason": "reason",
    "process": "process", "property_limitation": "property", "application_example": "application",
}
CONTROL_TYPES = frozenset({"wrong_entity_same_relation", "same_entity_other_relation"})
SAFE_FAILURES = frozenset({"inputs_invalid", "controls_not_reviewed", "runtime_changed",
    "scope_changed", "source_changed", "page_unavailable", "database_target_invalid", "audit_failed"})


class Refusal(RuntimeError):
    """Only a fixed safe code may cross the CLI boundary."""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=str).encode()).hexdigest()


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def runtime_fingerprint() -> str:
    from evaluate_private_source_display import runtime_fingerprint as fingerprint
    return fingerprint()


def evaluator_fingerprint() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


@dataclass(frozen=True)
class Scope:
    principal_id: UUID
    subject_id: UUID
    document_ids: tuple[UUID, ...]
    corpus_revision: int
    space_hash: str


@dataclass(frozen=True)
class ReviewedControls:
    scope: Scope
    pairs: tuple[dict, ...]
    runtime_sha256: str
    evaluator_sha256: str
    controls_sha256: str


def _hex(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _integer(value: Any, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _labels(value: Any, *, sufficient: bool) -> bool:
    return (isinstance(value, dict) and set(value) == {"source_fidelity", "excerpt_sufficient", "page_useful"}
        and value["source_fidelity"] == "Yes"
        and value["excerpt_sufficient"] == ("Yes" if sufficient else "No")
        and value["page_useful"] in (("Yes",) if sufficient else ("Yes", "No")))


def _validate_source(source: Any, scope: Scope) -> None:
    if not isinstance(source, dict):
        raise Refusal("inputs_invalid")
    try:
        for field in ("chunk_id", "document_id", "content_revision_id", "index_revision_id"):
            UUID(source[field])
        if scope.document_ids and UUID(source["document_id"]) not in scope.document_ids:
            raise ValueError
        if (source["corpus_revision"] != scope.corpus_revision
            or source["embedding_space_hash"] != scope.space_hash
            or not _integer(source["page_number"], 1, 100)
            or not all(_hex(source[field]) for field in ("chunk_sha256", "page_sha256", "quote_sha256"))
            or not _integer(source["quote_start"], 0, 500_000)
            or not _integer(source["quote_end"], source["quote_start"] + 1, source["quote_start"] + 480)
            or not _integer(source["page_reference_start"], 0, 500_000)
            or not _integer(source["page_reference_end"], source["page_reference_start"] + 1, 500_000)
            or not isinstance(source["document_title"], str)):
            raise ValueError
    except (KeyError, TypeError, ValueError, AttributeError):
        raise Refusal("inputs_invalid") from None


def _bind_candidate_manifest(raw: dict, candidate: Any) -> None:
    if (not isinstance(candidate, dict)
        or candidate.get("schema") != "source_sufficiency_candidate_packet_v1"
        or candidate.get("source_frozen") is not True
        or candidate.get("discovery_policy_id") != "complete_source_units_v2"
        or digest(candidate) != raw["source_candidate_sha256"]):
        raise Refusal("inputs_invalid")
    scope_keys = ("principal_id", "subject_id", "document_ids", "corpus_revision", "space_hash")
    if any(candidate["scope"].get(key) != raw["scope"].get(key) for key in scope_keys):
        raise Refusal("scope_changed")
    positives = candidate["positives"]
    negatives = candidate["insufficient_pairs"]
    if not isinstance(positives, list) or not isinstance(negatives, list):
        raise Refusal("inputs_invalid")
    by_positive = {row["case_id"]: row for row in positives}
    by_negative = {row["case_id"]: row for row in negatives}
    if len(by_positive) != len(positives) or len(by_negative) != len(negatives):
        raise Refusal("inputs_invalid")
    for pair in raw["pairs"]:
        original = by_negative.get(pair["case_id"])
        positive = by_positive.get(pair["paired_positive_case_id"])
        if original is None or positive is None:
            raise Refusal("inputs_invalid")
        fields = ("case_id", "relation", "category", "question", "previous_turn", "paired_positive_case_id",
            "source_candidate_case_id", "control_type", "source")
        if any(original.get(key) != pair.get(key) for key in fields):
            raise Refusal("inputs_invalid")
        if (any(positive.get(key) != pair.get(key) for key in ("relation", "category", "question", "previous_turn"))
            or positive.get("source") != pair["sufficient_source"]):
            raise Refusal("inputs_invalid")
    expected_groups = {category: [row["case_id"] for row in positives if row["category"] == category]
        for category in ("direct", "paraphrase", "followup")}
    if expected_groups != raw["positive_groups"]:
        raise Refusal("inputs_invalid")


def parse_controls(raw: Any, *, candidate_manifest: Any) -> ReviewedControls:
    """Validate all review and fingerprint guards before any DB is constructed."""
    try:
        if (not isinstance(raw, dict) or raw.get("schema") != SCHEMA
            or raw.get("frozen") is not True or raw.get("owner_reviewed") is not True
            or raw.get("whole_question_unsupported") is not False):
            raise Refusal("controls_not_reviewed")
        canonical = {key: value for key, value in raw.items() if key != "controls_sha256"}
        if not _hex(raw.get("controls_sha256")) or digest(canonical) != raw["controls_sha256"]:
            raise Refusal("inputs_invalid")
        if raw.get("runtime_sha256") != runtime_fingerprint():
            raise Refusal("runtime_changed")
        if raw.get("evaluator_sha256") != evaluator_fingerprint():
            raise Refusal("runtime_changed")
        if not _hex(raw.get("source_candidate_sha256")):
            raise Refusal("inputs_invalid")
        scope_raw = raw["scope"]
        documents = tuple(UUID(value) for value in scope_raw["document_ids"])
        scope = Scope(UUID(scope_raw["principal_id"]), UUID(scope_raw["subject_id"]), documents,
            scope_raw["corpus_revision"], scope_raw["space_hash"])
        if (len(documents) > 50 or len(set(documents)) != len(documents)
            or not _integer(scope.corpus_revision, 0, 2**63-1) or not _hex(scope.space_hash)):
            raise Refusal("inputs_invalid")
        pairs = raw["pairs"]
        if not isinstance(pairs, list) or not 16 <= len(pairs) <= 64:
            raise Refusal("controls_not_reviewed")
        counts = dict.fromkeys(RELATIONS, 0)
        ids, used_types = set(), set()
        negative_windows = set()
        groups = raw["positive_groups"]
        if (not isinstance(groups, dict) or set(groups) != {"direct", "paraphrase", "followup"}
            or any(not isinstance(values, list) or any(not isinstance(value, str) for value in values)
                for values in groups.values())):
            raise Refusal("inputs_invalid")
        sufficient_bindings = {}
        for pair in pairs:
            if (not isinstance(pair, dict) or pair["relation"] not in RELATIONS
                or pair["category"] not in {"direct", "paraphrase", "followup"}
                or pair["control_type"] not in CONTROL_TYPES
                or not isinstance(pair["case_id"], str) or not 1 <= len(pair["case_id"]) <= 100
                or pair["case_id"] in ids
                or not isinstance(pair["question"], str) or not 1 <= len(pair["question"].strip()) <= 4000
                or "\x00" in pair["question"]
                or not isinstance(pair.get("previous_turn", ""), str)
                or len(pair.get("previous_turn", "")) > 4000
                or "\x00" in pair.get("previous_turn", "")
                or not isinstance(pair["paired_positive_case_id"], str)
                or not isinstance(pair["source_candidate_case_id"], str)):
                raise Refusal("inputs_invalid")
            if (not _labels(pair["owner_labels"], sufficient=False)
                or not _labels(pair["sufficient_owner_labels"], sufficient=True)):
                raise Refusal("controls_not_reviewed")
            _validate_source(pair["source"], scope)
            _validate_source(pair["sufficient_source"], scope)
            if pair["source"] == pair["sufficient_source"]:
                raise Refusal("inputs_invalid")
            # A sufficient ID cannot silently bind to different evidence/questions.
            binding = digest({key: pair[key] for key in ("relation", "category", "question", "sufficient_source")}
                | {"previous_turn": pair.get("previous_turn", "")})
            positive = pair["paired_positive_case_id"]
            if positive not in groups[pair["category"]]:
                raise Refusal("inputs_invalid")
            if positive in sufficient_bindings and sufficient_bindings[positive] != binding:
                raise Refusal("inputs_invalid")
            negative = (pair["relation"], pair["source"]["chunk_id"],
                pair["source"]["quote_start"], pair["source"]["quote_end"])
            if negative in negative_windows:
                raise Refusal("inputs_invalid")
            negative_windows.add(negative)
            sufficient_bindings[positive] = binding
            ids.add(pair["case_id"])
            used_types.add(pair["control_type"])
            counts[pair["relation"]] += 1
        if any(count < 2 for count in counts.values()) or sorted(used_types) != raw["control_types"]:
            raise Refusal("controls_not_reviewed")
        _bind_candidate_manifest(raw, candidate_manifest)
        return ReviewedControls(scope, tuple(pairs), raw["runtime_sha256"],
            raw["evaluator_sha256"], raw["controls_sha256"])
    except Refusal:
        raise
    except (KeyError, TypeError, ValueError, AttributeError):
        raise Refusal("inputs_invalid") from None


class Reader(Protocol):
    async def current(self, sources: tuple[dict, ...]) -> dict[UUID, tuple[Any, str]]: ...


def validate_current(source: dict, current: tuple[Any, str]) -> str:
    chunk, page = current
    try:
        for key in ("chunk_id", "document_id", "content_revision_id", "index_revision_id"):
            if getattr(chunk, key) != UUID(source[key]):
                raise Refusal("source_changed")
        for key in ("page_number", "corpus_revision", "embedding_space_hash", "document_title"):
            if getattr(chunk, key) != source[key]:
                raise Refusal("source_changed")
        quote = chunk.content[source["quote_start"]:source["quote_end"]]
        page_quote = page[source["page_reference_start"]:source["page_reference_end"]]
        if (_sha(chunk.content) != source["chunk_sha256"] or _sha(page) != source["page_sha256"]
            or len(quote) != source["quote_end"] - source["quote_start"]
            or _sha(quote) != source["quote_sha256"]
            or not page_quote or " ".join(quote.split()) != " ".join(page_quote.split())):
            raise Refusal("source_changed")
        return quote
    except Refusal:
        raise
    except (KeyError, TypeError, ValueError, AttributeError):
        raise Refusal("source_changed") from None


def _qualifies(pair: dict, source: Any, quote: str, *, sufficient: bool = False) -> bool | None:
    from app.ai.chunking import estimate_tokens
    from app.ai.source_sufficiency import describe_question, rank_sufficient_sources
    from app.services.knowledge_retrieval import RetrievedKnowledgeChunk
    history = (("user", pair["previous_turn"]),) if pair.get("previous_turn") else ()
    descriptor = describe_question(pair["question"], history)
    if descriptor.ambiguous or descriptor.relation != RELATIONS[pair["relation"]] or not descriptor.local_query:
        return None
    # Only the reviewed span is visible to the selector, without page/section hints.
    window = RetrievedKnowledgeChunk(source.chunk_id, source.document_id, source.document_title,
        source.content_revision_id, source.index_revision_id, source.page_number, None, quote,
        estimate_tokens(quote), source.embedding_space_hash, source.corpus_revision,
        None, None, None, None, 0.0)
    result = rank_sufficient_sources(descriptor, (window,))
    if result.status == "ambiguous":
        return None
    if any(selection.source.chunk_id != source.chunk_id
        or not 0 <= selection.start_offset < selection.end_offset <= len(quote)
        or selection.quote != quote[selection.start_offset:selection.end_offset]
        for selection in result.selections):
        return None
    # Review of a larger positive window does not label a cropped subspan.
    # For an insufficient window, *any* qualified subspan is a false-primary.
    if sufficient and result.selections and not any(
        selection.start_offset == 0 and selection.end_offset == len(quote)
        for selection in result.selections
    ):
        return None
    return bool(result.selections)


async def evaluate(controls: ReviewedControls, reader: Reader,
                   qualifier: Callable = _qualifies) -> dict:
    if (controls.runtime_sha256 != runtime_fingerprint()
        or controls.evaluator_sha256 != evaluator_fingerprint()):
        raise Refusal("runtime_changed")
    sources = tuple(source for pair in controls.pairs for source in (pair["source"], pair["sufficient_source"]))
    current = await reader.current(sources)
    totals = {relation: {"reviewed_pairs": 0, "negative_qualified": 0,
        "sufficient_control_qualified": 0, "unknown": 0} for relation in RELATIONS}
    for pair in controls.pairs:
        values = []
        for position, source in enumerate((pair["source"], pair["sufficient_source"])):
            row = current.get(UUID(source["chunk_id"]))
            if row is None:
                raise Refusal("source_changed")
            quote = validate_current(source, row)
            value = qualifier(pair, row[0], quote, sufficient=position == 1)
            if value is not None and type(value) is not bool:
                value = None
            values.append(value)
        item = totals[pair["relation"]]
        item["reviewed_pairs"] += 1
        item["negative_qualified"] += int(values[0] is True)
        item["sufficient_control_qualified"] += int(values[1] is True)
        item["unknown"] += int(None in values)
    # A second independently authorized snapshot rejects source/scope drift.
    again = await reader.current(sources)
    for source in sources:
        row = again.get(UUID(source["chunk_id"]))
        if row is None:
            raise Refusal("source_changed")
        validate_current(source, row)
    if (controls.runtime_sha256 != runtime_fingerprint()
        or controls.evaluator_sha256 != evaluator_fingerprint()):
        raise Refusal("runtime_changed")
    passed = all(item["negative_qualified"] == 0 and item["unknown"] == 0
        and item["sufficient_control_qualified"] == item["reviewed_pairs"] for item in totals.values())
    return {"schema": "source_sufficiency_pair_audit_v1", "status": "evaluated",
        "runtime_sha256": controls.runtime_sha256, "evaluator_sha256": controls.evaluator_sha256,
        "relations": totals, "source_pair_gate_passed": passed, "release_gate_passed": False,
        "provider_requests": 0, "answer_calls": 0, "verifier_calls": 0, "database_writes": 0,
        "whole_question_unsupported": False}


class ReadOnlyPostgresReader:
    def __init__(self, session_factory: Callable, scope: Scope):
        self.session_factory, self.scope = session_factory, scope

    async def current(self, sources):
        from sqlalchemy import select, text, tuple_
        from types import SimpleNamespace
        from app.models.knowledge import SubjectDocumentPage
        from app.models.subject import Subject
        from app.models.user import User, UserRole
        from app.services.knowledge_retrieval import KnowledgeRetriever, SOURCE_SUFFICIENCY_RETRIEVAL_POLICY
        async with self.session_factory() as db:
            if db.get_bind().dialect.name != "postgresql":
                raise Refusal("database_target_invalid")
            await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            await db.execute(text("SET LOCAL statement_timeout = '15000ms'"))
            owner = await db.scalar(select(User.id).join(Subject, Subject.instructor_id == User.id).where(
                User.id == self.scope.principal_id, User.role == UserRole.INSTRUCTOR,
                Subject.id == self.scope.subject_id))
            if owner is None:
                raise Refusal("scope_changed")
            bound = await KnowledgeRetriever.authorize(db, principal=SimpleNamespace(id=owner),
                subject_id=self.scope.subject_id, query="source evidence audit",
                document_ids=self.scope.document_ids, limit=20, policy=SOURCE_SUFFICIENCY_RETRIEVAL_POLICY)
            if (bound.scope.corpus_revision != self.scope.corpus_revision
                or bound.scope.embedding_space_hash != self.scope.space_hash
                or tuple(bound.scope.document_ids) != self.scope.document_ids):
                raise Refusal("scope_changed")
            ids = list(dict.fromkeys(UUID(source["chunk_id"]) for source in sources))
            chunks = []
            for offset in range(0, len(ids), 20):
                chunks.extend(await bound.read_current_sources(ids[offset:offset+20]))
            if len(chunks) != len(ids):
                raise Refusal("source_changed")
            keys = {(chunk.document_id, chunk.content_revision_id, chunk.page_number) for chunk in chunks}
            pages = (await db.scalars(select(SubjectDocumentPage).where(
                SubjectDocumentPage.subject_id == self.scope.subject_id,
                SubjectDocumentPage.uploader_id == self.scope.principal_id,
                tuple_(SubjectDocumentPage.document_id, SubjectDocumentPage.content_revision_id,
                    SubjectDocumentPage.page_number).in_(keys)))).all()
            by_page = {(page.document_id, page.content_revision_id, page.page_number): page.content for page in pages}
            if any(key not in by_page for key in keys):
                raise Refusal("page_unavailable")
            result = {chunk.chunk_id: (chunk, by_page[(chunk.document_id, chunk.content_revision_id,
                chunk.page_number)]) for chunk in chunks}
            await db.rollback()
            return result


def _private_json(path: Path) -> Any:
    resolved = path.resolve()
    if not resolved.is_relative_to(Path(tempfile.gettempdir()).resolve()) or not resolved.is_file():
        raise Refusal("inputs_invalid")
    if resolved.stat().st_size > 512 * 1024:
        raise Refusal("inputs_invalid")
    try:
        return json.loads(resolved.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError, OSError):
        raise Refusal("inputs_invalid") from None


def explicit_reader(profile: Any, scope: Scope):
    """Fresh process, explicit local DB only, no operator Settings/.env access."""
    from sqlalchemy.engine import make_url
    if (not isinstance(profile, dict) or set(profile) != {"database_url"}
        or "app.database" in sys.modules):
        raise Refusal("database_target_invalid")
    try:
        parsed = make_url(profile["database_url"])
        local = (parsed.host or "").lower() in {"localhost", "127.0.0.1", "::1"}
        container_local = Path("/.dockerenv").is_file() and parsed.host == "db"
        if parsed.drivername != "postgresql+asyncpg" or not parsed.database or not (local or container_local):
            raise ValueError
    except (TypeError, ValueError):
        raise Refusal("database_target_invalid") from None
    from app import config
    settings = config.Settings(_env_file=None, environment="test", database_url=profile["database_url"],
        secret_key="private-read-only-probe-unused-secret-key-1234567890",
        generation_source_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        rag_enabled=False, rag_ask_enabled=False)
    config.get_settings = lambda: settings
    from app.database import async_session_maker, engine
    return ReadOnlyPostgresReader(async_session_maker, scope), engine.dispose


async def _execute(args):
    controls = parse_controls(_private_json(Path(args.controls)),
        candidate_manifest=_private_json(Path(args.candidate_manifest)))
    profile = _private_json(Path(args.profile))
    sys.path.insert(0, str(ROOT / "backend"))
    reader, close = explicit_reader(profile, controls.scope)
    try:
        return await asyncio.wait_for(evaluate(controls, reader), timeout=120)
    finally:
        await close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--controls")
    parser.add_argument("--profile")
    parser.add_argument("--candidate-manifest")
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({"status": "preflight_only", "requires_frozen_owner_review": True,
            "minimum_pairs": 16, "minimum_per_relation": 2, "relation_families": 8,
            "provider_requests": 0, "database_reads": 0, "database_writes": 0,
            "source_pair_gate_passed": False, "release_gate_passed": False}, sort_keys=True))
        return 0
    try:
        if not args.controls or not args.profile or not args.candidate_manifest:
            raise Refusal("inputs_invalid")
        result = asyncio.run(_execute(args))
        print(json.dumps(result, sort_keys=True))
        return 0 if result["source_pair_gate_passed"] else 1
    except Exception as exc:
        code = str(exc) if isinstance(exc, Refusal) and str(exc) in SAFE_FAILURES else "audit_failed"
        print(json.dumps({"status": "refused", "reason": code,
            "source_pair_gate_passed": False, "release_gate_passed": False}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
