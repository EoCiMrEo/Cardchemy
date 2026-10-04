"""Score independently reviewed source-navigation windows without course text.

This is a content-free scorer, not a retrieval runner or a source validator.
Its input is a local JSON file of measurements and explicit reviewer labels
from the *actual displayed windows*. The producer must prove each exact source
slice, current page link and authorization before setting those fields true.
No provider, database or network client is imported here. Incomplete cases and
unreviewed windows can never pass. The default command is a no-input preflight.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from statistics import fmean
import tempfile
from typing import Any
import unicodedata
from uuid import UUID


MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "backend/tests/fixtures/rag_eval/source_first_display_gate_v1.json"
)
_ROW_KEYS = frozenset({
    "case_id", "gold_document_key", "gold_page_key", "gold_page_rank",
    "owner_reviewed_gold", "owner_reviewed_windows", "result_kind",
    "windows", "embedding_calls", "answer_calls", "automatic_retries",
    "answer_assertion_present", "retrieval_ms",
})
_WINDOW_KEYS = frozenset({
    "page_key", "chars", "question_relevant", "exact_chunk_slice",
    "canonical_page_aligned", "opened_current_page", "current_authorized",
    "known_irrelevant_u01_pair",
})
_SOURCE_WINDOW_KEYS = _WINDOW_KEYS | {"source_kind", "exact_source_slice"}
PRIVATE_HOLDOUT_SCHEMA = "source_first_private_holdout_v1"
PRIVATE_MEASUREMENT_SCHEMA = "source_first_private_measurement_v1"
AUTHORED_DISCOVERY_POLICY = "complete_source_units_v2"
INDEPENDENT_CANDIDATE_SCHEMA = "independent_source_display_candidate_v1"
INDEPENDENT_REVIEW_SCHEMA = "independent_source_display_review_v1"
INDEPENDENT_ROSTER_SCHEMA = "independent_source_only_display_roster_v1"
INDEPENDENT_HOLDOUT_SCHEMA = "source_first_private_holdout_v2"
INDEPENDENT_MEASUREMENT_SCHEMA = "source_first_private_measurement_v2"
INDEPENDENT_DISCOVERY_POLICY = "independent_original_pdf_pages_v1"
_INDEPENDENT_ROW_KEYS = _ROW_KEYS | {
    "independently_reviewed_gold", "independently_reviewed_windows", "independent_review",
}
_GROUPS = ("direct", "paraphrase", "followup")


class InvalidObservation(ValueError):
    """Malformed or unsafe-to-score input; message intentionally content-free."""


def inspect_source_window(
    *, chunk_text: str, start_offset: int, end_offset: int, canonical_page_text: str,
    source_kind: str = "chunk",
) -> dict[str, bool | int | str]:
    """Measure offsets against their declared authoritative source.

    The returned flags contain no lecture text. This does not authorize the
    source or prove the browser opened it; those checks belong to the producer.
    The default preserves historical chunk measurement fields. Canonical-page
    mode returns the explicit source-kind fields and never labels page offsets
    as chunk offsets. Historical chunk alignment retains its normalization.
    """

    if source_kind not in ("chunk", "canonical_page"):
        raise InvalidObservation("invalid_source_kind")
    source_text = canonical_page_text if source_kind == "canonical_page" else chunk_text
    empty: dict[str, bool | int | str] = {
        "chars": 0, "exact_chunk_slice": False, "canonical_page_aligned": False,
    }
    if source_kind == "canonical_page":
        empty.update(source_kind=source_kind, exact_source_slice=False)
    valid = (type(start_offset) is int and type(end_offset) is int
             and 0 <= start_offset < end_offset <= len(source_text)
             and end_offset - start_offset <= 480)
    if not valid:
        return empty
    quote = source_text[start_offset:end_offset]
    if not quote.strip():
        return empty
    if source_kind == "canonical_page":
        return {"chars": len(quote), "source_kind": source_kind,
                "exact_source_slice": True, "exact_chunk_slice": False,
                "canonical_page_aligned": True}

    def normalize(value: str) -> str:
        return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip().casefold()

    return {
        "chars": len(quote),
        "exact_chunk_slice": True,
        "canonical_page_aligned": normalize(quote) in normalize(canonical_page_text),
    }


def manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _utc_time(value: Any) -> datetime:
    if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)", value) is None:
        raise InvalidObservation("invalid_review_provenance")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        raise InvalidObservation("invalid_review_provenance") from None


def _independent_provenance(value: Any) -> dict[str, Any]:
    """Validate an explicit attestation; discovery or rank cannot supply it."""

    if (not isinstance(value, dict) or set(value) != {
        "schema", "reviewer_kind", "reviewer_id", "independent_of_runtime_selection",
        "original_pdf_inspected", "source_fidelity_inspected",
        "excerpt_relation_and_context_inspected", "source_review_artifact_sha256",
        "source_review_frozen_at_utc", "frozen_before_runtime", "runtime_evaluated",
    } or value["schema"] != "independent_source_review_provenance_v1"
        or value["reviewer_kind"] != "independent_agent"
        or not isinstance(value["reviewer_id"], str)
        or re.fullmatch(r"[A-Za-z0-9_/-]{1,80}", value["reviewer_id"]) is None
        or not _sha256(value["source_review_artifact_sha256"])
        or any(value[key] is not True for key in (
            "independent_of_runtime_selection", "original_pdf_inspected",
            "source_fidelity_inspected", "excerpt_relation_and_context_inspected",
            "frozen_before_runtime"))
        or value["runtime_evaluated"] is not False):
        raise InvalidObservation("invalid_review_provenance")
    if _utc_time(value["source_review_frozen_at_utc"]) > datetime.now(timezone.utc):
        raise InvalidObservation("invalid_review_provenance")
    return value


def _verified_independent_artifact(candidate: dict[str, Any], raw: bytes | None,
                                   provenance: dict[str, Any]) -> None:
    """Bind original PDF labels and identities before canonical-source binding."""

    if (not isinstance(raw, bytes) or len(raw) > 512 * 1024
        or hashlib.sha256(raw).hexdigest() != provenance["source_review_artifact_sha256"]):
        raise InvalidObservation("source_review_artifact_changed")
    try:
        artifact = json.loads(raw)
        if (artifact["schema"] != "independent_source_sufficiency_frozen_v1"
            or artifact["source_origin"] != "original_local_pdf_pages"
            or artifact["frozen_at_utc"] != provenance["source_review_frozen_at_utc"]
            or artifact["runtime_evaluated"] is not False
            or artifact["owner_labels_immutable"] is not True
            or any(type(artifact[key]) is not int or artifact[key] != 0
                   for key in ("provider_calls", "database_reads", "database_writes"))
            or not isinstance(artifact["positives"], list) or len(artifact["positives"]) != 12):
            raise InvalidObservation("source_review_artifact_invalid")
        original = {row["case_id"]: row for row in artifact["positives"]}
        if len(original) != 12 or len(candidate["positives"]) != 12:
            raise InvalidObservation("source_review_artifact_invalid")
        for row in candidate["positives"]:
            source_review = original.get(row["case_id"])
            if (source_review is None or row["source_review_case_sha256"] != _digest(source_review)
                or source_review["review_authority"] != "independent_original_pdf_review"
                or source_review["labels"] not in (
                    {"source_fidelity": "Yes", "excerpt_sufficient": "Yes", "page_useful": "Yes"},
                    {"source_fidelity": "yes", "excerpt_sufficient": "yes", "page_useful": "yes"},
                )
                or any(row[key] != source_review[key] for key in ("question", "previous_turn", "category", "relation"))
                or not _sha256(source_review["source"]["quote_sha256"])
                or not isinstance(source_review["quote"], str)
                or hashlib.sha256(source_review["quote"].encode("utf-8")).hexdigest() != source_review["source"]["quote_sha256"]
                or row["reviewed_quote_sha256"] != source_review["source"]["quote_sha256"]
                or ("quote" in row and (not isinstance(row["quote"], str)
                    or hashlib.sha256(row["quote"].encode("utf-8")).hexdigest() != row["reviewed_quote_sha256"]))
                or any(row["source"][key] != source_review["source"][key]
                       for key in ("document_id", "page_number"))):
                raise InvalidObservation("source_review_identity_changed")
    except (KeyError, TypeError, ValueError, AttributeError, UnicodeError, json.JSONDecodeError) as exc:
        if isinstance(exc, InvalidObservation):
            raise
        raise InvalidObservation("source_review_artifact_invalid") from None


def _private_path(path: Path) -> Path:
    """Private registration inputs/output must remain in the OS Temp tree."""

    root = Path(tempfile.gettempdir()).resolve()
    resolved = path.resolve()
    if (resolved == root or not resolved.is_relative_to(root)
        or any(parent.is_symlink() for parent in (path, *path.parents))):
        raise InvalidObservation("invalid_private_path")
    return resolved


def _private_json(path: Path, *, max_bytes: int = 512 * 1024) -> Any:
    target = _private_path(path)
    if not target.is_file() or target.stat().st_size > max_bytes:
        raise InvalidObservation("invalid_private_input")
    return json.loads(target.read_text(encoding="utf-8"))


def _private_bytes(path: Path, *, max_bytes: int = 512 * 1024) -> bytes:
    target = _private_path(path)
    if not target.is_file() or target.stat().st_size > max_bytes:
        raise InvalidObservation("invalid_private_input")
    return target.read_bytes()


def _verified_exclusions(candidate: dict[str, Any], old_gold: bytes,
                         old_alternatives: bytes, development_packets: tuple[bytes, ...]) -> dict[str, Any]:
    """Check exact earlier packet bytes and their page IDs against new positives.

    The builder's separate pattern-derived seed exclusions have no page-ID
    roster in the candidate packet, so this cannot independently verify those.
    Actual seed/holdout disjointness is checked from measured rows later.
    """

    if not 1 <= len(development_packets) <= 16:
        raise InvalidObservation("exclusion_proof_missing")
    try:
        gold = json.loads(old_gold)
        alternatives = json.loads(old_alternatives)
        development = [json.loads(value) for value in development_packets]
        prior = candidate["excluded_development_sources"]
        old_scope = {"corpus_revision": candidate["scope"]["corpus_revision"],
                     "embedding_space_hash": candidate["scope"]["space_hash"]}
        if (gold["version"] != "source_navigation_holdout_gold_v1"
            or alternatives["version"] != "source_gold_context_alternatives_v1"
            or gold["scope"] != old_scope or alternatives["scope"] != old_scope
            or alternatives["original_roster_sha256"] != hashlib.sha256(old_gold).hexdigest()
            or prior["old_scope"] != old_scope
            or prior["old_gold_sha256"] != hashlib.sha256(old_gold).hexdigest()
            or prior["old_alternatives_sha256"] != hashlib.sha256(old_alternatives).hexdigest()
            or prior["exposed_candidate_packet_sha256"] != [
                hashlib.sha256(raw).hexdigest() for raw in development_packets]):
            raise InvalidObservation("exclusion_proof_changed")
        old_pages = {(str(UUID(row["gold_document_id"])), int(row["gold_page"]))
                     for row in gold["cases"]}
        old_pages.update((str(UUID(row["gold_document_id"])), int(row["page"]))
                         for row in alternatives["candidates"])
        development_pages: set[tuple[str, int]] = set()
        for packet in development:
            scope = packet["scope"]
            standard = (packet["schema"] == "source_sufficiency_candidate_packet_v1"
                        and packet["source_frozen"] is True)
            context = (packet["schema"] == "source_sufficiency_context_candidates_v1"
                       and packet.get("source_snapshot_verified_twice") is True
                       and packet.get("runtime_evaluated") is False)
            if (not (standard or context)
                or {"corpus_revision": scope["corpus_revision"],
                    "embedding_space_hash": scope["space_hash"]} != old_scope):
                raise InvalidObservation("exclusion_proof_changed")
            development_pages.update((str(UUID(row["source"]["document_id"])),
                                      int(row["source"]["page_number"]))
                                     for row in packet["positives"] + packet["insufficient_pairs"])
        if (prior["old_review_pages_excluded"] != len(old_pages)
            or prior["exposed_candidate_pages_excluded"] != len(development_pages)):
            raise InvalidObservation("exclusion_proof_changed")
        excluded = old_pages | development_pages
        new_pages = {(str(UUID(row["source"]["document_id"])),
                      int(row["source"]["page_number"])) for row in candidate["positives"]}
        if new_pages & excluded:
            raise InvalidObservation("old_page_reused")
        return {"verified_prior_page_count": len(excluded),
                "verified_prior_pages_sha256": _digest(sorted(excluded))}
    except (KeyError, TypeError, ValueError, AttributeError, UnicodeError, json.JSONDecodeError) as exc:
        if isinstance(exc, InvalidObservation):
            raise
        raise InvalidObservation("exclusion_proof_invalid") from None


def freeze_private_holdout(candidate: Any, review: Any, roster: Any,
                           old_gold: bytes, old_alternatives: bytes,
                           development_packets: tuple[bytes, ...], *,
                           source_review_artifact: bytes | None = None) -> dict[str, Any]:
    """Pre-register separately reviewed gold without storing lecture text.

    The candidate packet alone never supplies a Yes label. The frozen probe
    roster must identify the exact reviewed question, page and history. This
    step is completed before an actual displayed-window observation is made.
    Old private gold/alternatives and prior packet pages are independently
    checked from their bound bytes. The pattern-derived development seed pages
    have no identities in the packet, so this cannot prove their exclusion.
    """

    from evaluate_private_source_display import (
        Case, FrozenRoster, Refusal, Scope, _digest as source_key, roster_fingerprint,
        runtime_fingerprint, validate_roster,
    )

    try:
        independent = isinstance(candidate, dict) and candidate.get("schema") == INDEPENDENT_CANDIDATE_SCHEMA
        missing_review = "holdout_not_independently_reviewed" if independent else "holdout_not_owner_reviewed"
        provenance = None
        if independent:
            provenance = _independent_provenance(candidate.get("provenance"))
            if (candidate.get("discovery_policy_id") != INDEPENDENT_DISCOVERY_POLICY
                or candidate.get("runtime_evaluated") is not False
                or not isinstance(review, dict) or set(review) != {
                    "schema", "candidate_roster_sha256", "labels", "provenance"}
                or review["schema"] != INDEPENDENT_REVIEW_SCHEMA
                or review["provenance"] != provenance):
                raise InvalidObservation("invalid_review_provenance")
            _verified_independent_artifact(candidate, source_review_artifact, provenance)
        elif (not isinstance(candidate, dict)
              or candidate.get("schema") != "source_sufficiency_candidate_packet_v1"
              or candidate.get("authored_template_mode") != "private_source_sufficiency_authored_v1"
              or not _sha256(candidate.get("authored_spec_sha256"))
              or candidate.get("discovery_policy_id") != AUTHORED_DISCOVERY_POLICY
              or (isinstance(review, dict) and "provenance" in review)):
            raise InvalidObservation(missing_review)
        if (candidate["source_frozen"] is not True or candidate["owner_reviewed"] is not False
            or not isinstance(candidate["positives"], list) or len(candidate["positives"]) != 12
            or not isinstance(review, dict) or not isinstance(review["labels"], dict)
            or review["candidate_roster_sha256"] != _digest(candidate)
            or not isinstance(roster, dict) or set(roster) != {
                "schema", "frozen", "scope", "cases", "roster_sha256", "runtime_sha256"}
            or roster["schema"] != (INDEPENDENT_ROSTER_SCHEMA if independent else "source_only_display_roster_v1")
            or roster["frozen"] is not True
            or not isinstance(roster["cases"], list) or len(roster["cases"]) != 12):
            raise InvalidObservation("holdout_not_owner_reviewed")
        scope_raw = roster["scope"]
        if set(scope_raw) != set(Scope.__dataclass_fields__):
            raise InvalidObservation("invalid_private_roster")
        scope = Scope(UUID(scope_raw["principal_id"]), UUID(scope_raw["subject_id"]),
            tuple(UUID(value) for value in scope_raw["document_ids"]),
            scope_raw["corpus_revision"], scope_raw["space_hash"])
        source_scope = candidate["scope"]
        if any(source_scope[key] != scope_raw[key] for key in scope_raw):
            raise InvalidObservation("private_scope_changed")
        cases = tuple(Case(row["case_id"], row["question"], UUID(row["gold_document_id"]),
            row["gold_page_number"], row["owner_reviewed_gold"],
            tuple(tuple(turn) for turn in row["history"])) for row in roster["cases"])
        frozen = FrozenRoster(cases, scope, roster["roster_sha256"], roster["runtime_sha256"])
        if independent:
            _validate_independent_roster(roster, cases, scope)
            expected_roster_sha = _digest({"scope": scope_raw, "cases": roster["cases"]})
        else:
            validate_roster(frozen)
            expected_roster_sha = roster_fingerprint(cases, scope)
        if (frozen.roster_sha256 != expected_roster_sha
            or frozen.runtime_sha256 != runtime_fingerprint()):
            raise InvalidObservation("private_roster_changed")
        by_id = {case.case_id: case for case in cases}
        if len(by_id) != 12 or (independent and set(review["labels"]) != set(by_id)):
            raise InvalidObservation("invalid_private_roster")
        groups: dict[str, list[str]] = {group: [] for group in _GROUPS}
        gold: dict[str, dict[str, str]] = {}
        for row in candidate["positives"]:
            case_id = row["case_id"]
            if (not isinstance(case_id, str) or re.fullmatch(r"X[0-9]{2}", case_id) is None
                or case_id in gold or row["category"] not in groups
                or row["labels"] != {"source_fidelity": "unreviewed",
                                     "excerpt_sufficient": "unreviewed", "page_useful": "unreviewed"}
                or case_id in {case for values in manifest()["seed"].values() for case in values}
                or case_id in manifest()["controls"]):
                raise InvalidObservation("invalid_private_case")
            labels = review["labels"].get(case_id)
            if (not isinstance(labels, dict)
                or labels != {"source_fidelity": "Yes", "excerpt_sufficient": "Yes",
                              "page_useful": "Yes"}):
                raise InvalidObservation(missing_review)
            source = row["source"]
            case = by_id.get(case_id)
            expected_history = (("user", row["previous_turn"]),) if row["previous_turn"] else ()
            if (case is None or str(case.gold_document_id) != source["document_id"]
                or case.gold_page_number != source["page_number"]
                or case.question != row["question"]
                or case.history != expected_history):
                raise InvalidObservation("private_roster_changed")
            groups[row["category"]].append(case_id)
            gold[case_id] = {
                "gold_document_key": source_key(case.gold_document_id),
                "gold_page_key": source_key([case.gold_document_id, case.gold_page_number]),
            }
        if (set(gold) != set(by_id) or any(len(groups[group]) != 4 for group in _GROUPS)
            or len({value["gold_page_key"] for value in gold.values()}) != 12
            or len({value["gold_document_key"] for value in gold.values()}) < 2):
            raise InvalidObservation("invalid_private_roster")
        exclusion_proof = _verified_exclusions(candidate, old_gold, old_alternatives,
                                                development_packets)
        body = {"schema": INDEPENDENT_HOLDOUT_SCHEMA if independent else PRIVATE_HOLDOUT_SCHEMA,
            "frozen": True, "candidate_roster_sha256": _digest(candidate),
            "independent_review_sha256" if independent else "owner_review_sha256": _digest(review),
            "roster_sha256": frozen.roster_sha256, "runtime_sha256": frozen.runtime_sha256,
            "threshold_manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
            "scorer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "discovery_policy_id": INDEPENDENT_DISCOVERY_POLICY if independent else AUTHORED_DISCOVERY_POLICY,
            **exclusion_proof, "holdout": groups, "gold_keys": gold}
        if independent:
            body["review_provenance"] = deepcopy(provenance)
            body["registered_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        return {**body, "holdout_manifest_sha256": _digest(body)}
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, Refusal) as exc:
        if isinstance(exc, InvalidObservation):
            raise
        raise InvalidObservation("invalid_private_roster") from None


def _validate_independent_roster(roster: dict[str, Any], cases: tuple[Any, ...], scope: Any) -> None:
    """Keep independent attestations explicit rather than claiming owner review."""

    if (any(set(row) != {"case_id", "question", "gold_document_id", "gold_page_number",
                         "owner_reviewed_gold", "independently_reviewed_gold", "history"}
            or row["owner_reviewed_gold"] is not False
            or row["independently_reviewed_gold"] is not True for row in roster["cases"])
        or any(type(case.gold_page_number) is not int or not 1 <= case.gold_page_number <= 10000
               or (scope.document_ids and case.gold_document_id not in scope.document_ids)
               or not isinstance(case.question, str) or not case.question.strip()
               or "\x00" in case.question or len(case.question) > 4000
               or len(case.history) > 12
               or any(role != "user" or not isinstance(value, str) or len(value) > 1000
                      for role, value in case.history) for case in cases)
        or type(scope.corpus_revision) is not int or scope.corpus_revision < 0
        or not _sha256(scope.space_hash) or len(scope.document_ids) > 50
        or len(set(scope.document_ids)) != len(scope.document_ids)):
        raise InvalidObservation("invalid_private_roster")


def validate_private_holdout(frozen: Any) -> None:
    """A changed scorer, gate fixture, roster or registration cannot be scored."""

    from evaluate_private_source_display import runtime_fingerprint

    independent = isinstance(frozen, dict) and frozen.get("schema") == INDEPENDENT_HOLDOUT_SCHEMA
    review_key = "independent_review_sha256" if independent else "owner_review_sha256"
    expected_keys = {
        "schema", "frozen", "candidate_roster_sha256", review_key,
        "roster_sha256", "runtime_sha256", "threshold_manifest_sha256",
        "scorer_sha256", "discovery_policy_id", "verified_prior_page_count",
        "verified_prior_pages_sha256", "holdout", "gold_keys", "holdout_manifest_sha256",
    }
    if independent:
        expected_keys.update({"review_provenance", "registered_at_utc"})
    if not isinstance(frozen, dict) or set(frozen) != expected_keys:
        raise InvalidObservation("invalid_private_holdout")
    if independent:
        _independent_provenance(frozen["review_provenance"])
        if _utc_time(frozen["registered_at_utc"]) < _utc_time(frozen["review_provenance"]["source_review_frozen_at_utc"]):
            raise InvalidObservation("invalid_review_provenance")
    body = {key: value for key, value in frozen.items() if key != "holdout_manifest_sha256"}
    if (frozen["schema"] != (INDEPENDENT_HOLDOUT_SCHEMA if independent else PRIVATE_HOLDOUT_SCHEMA)
        or frozen["frozen"] is not True
        or not all(_sha256(frozen[key]) for key in (
            "candidate_roster_sha256", review_key, "roster_sha256",
            "runtime_sha256", "threshold_manifest_sha256", "scorer_sha256",
            "verified_prior_pages_sha256", "holdout_manifest_sha256"))
        or frozen["discovery_policy_id"] != (INDEPENDENT_DISCOVERY_POLICY if independent else AUTHORED_DISCOVERY_POLICY)
        or type(frozen["verified_prior_page_count"]) is not int
        or frozen["verified_prior_page_count"] < 1
        or frozen["holdout_manifest_sha256"] != _digest(body)
        or frozen["threshold_manifest_sha256"] != hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
        or frozen["scorer_sha256"] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        or frozen["runtime_sha256"] != runtime_fingerprint()):
        raise InvalidObservation("private_holdout_changed")
    groups = frozen["holdout"]
    gold = frozen["gold_keys"]
    if (not isinstance(groups, dict) or set(groups) != set(_GROUPS)
        or any(not isinstance(groups[group], list) or len(groups[group]) != 4 for group in _GROUPS)
        or not isinstance(gold, dict)):
        raise InvalidObservation("invalid_private_holdout")
    case_ids = [case_id for group in _GROUPS for case_id in groups[group]]
    if (len(set(case_ids)) != 12 or set(gold) != set(case_ids)
        or any(not isinstance(case_id, str) or re.fullmatch(r"X[0-9]{2}", case_id) is None
               for case_id in case_ids)
        or any(not isinstance(value, dict) or set(value) != {"gold_document_key", "gold_page_key"}
               or not all(_sha256(key) for key in value.values()) for value in gold.values())
        or len({value["gold_page_key"] for value in gold.values()}) != 12
        or len({value["gold_document_key"] for value in gold.values()}) < 2):
        raise InvalidObservation("invalid_private_holdout")


def score_private_holdout(measurement: Any, frozen: dict[str, Any]) -> dict[str, Any]:
    """Score only observations bound to an earlier explicit reviewed registration."""

    validate_private_holdout(frozen)
    independent = frozen["schema"] == INDEPENDENT_HOLDOUT_SCHEMA
    expected_keys = {"schema", "holdout_manifest_sha256", "roster_sha256", "runtime_sha256", "observations"}
    if independent:
        expected_keys.add("evaluated_at_utc")
    if (not isinstance(measurement, dict) or set(measurement) != expected_keys
        or measurement["schema"] != (INDEPENDENT_MEASUREMENT_SCHEMA if independent else PRIVATE_MEASUREMENT_SCHEMA)
        or any(measurement[key] != frozen[key] for key in (
            "holdout_manifest_sha256", "roster_sha256", "runtime_sha256"))
        or not isinstance(measurement["observations"], list)):
        raise InvalidObservation("measurement_not_preregistered")
    provenance = frozen.get("review_provenance")
    if independent and (_utc_time(measurement["evaluated_at_utc"])
                        <= _utc_time(frozen["registered_at_utc"])):
        raise InvalidObservation("measurement_predates_registration")
    for row in measurement["observations"]:
        if not isinstance(row, dict):
            raise InvalidObservation("invalid_row_schema")
        gold = frozen["gold_keys"].get(row.get("case_id"))
        if gold is not None and any(row.get(key) != value for key, value in gold.items()):
            raise InvalidObservation("private_gold_mismatch")
        if independent and gold is not None:
            if set(row) != _INDEPENDENT_ROW_KEYS:
                raise InvalidObservation("independent_window_review_missing")
            window_review = row["independent_review"]
            if (not isinstance(window_review, dict) or set(window_review) != {
                "reviewer_kind", "reviewer_id", "source_review_artifact_sha256", "reviewed_at_utc"}
                or any(window_review[key] != provenance[key] for key in (
                    "reviewer_kind", "reviewer_id", "source_review_artifact_sha256"))
                or _utc_time(window_review["reviewed_at_utc"]) < _utc_time(measurement["evaluated_at_utc"])):
                raise InvalidObservation("invalid_window_review_provenance")
    config = deepcopy(manifest())
    config["holdout"].update(frozen["holdout"])
    report = score(measurement["observations"], config,
                   independent_case_ids=set(frozen["gold_keys"]) if independent else frozenset())
    report["holdout_preregistration_sha256"] = frozen["holdout_manifest_sha256"]
    report["verified_prior_page_exclusions"] = frozen["verified_prior_page_count"]
    report["development_seed_exclusion_independently_verified"] = False
    return report


def _case_groups(config: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    seed = {case_id: category for category, ids in config["seed"].items() for case_id in ids}
    holdout = {case_id: category for category, ids in config["holdout"].items()
               if isinstance(ids, list) for case_id in ids}
    if len(seed) != 11 or len(holdout) != 12 or set(seed) & set(holdout):
        raise InvalidObservation("invalid_case_roster")
    return seed, holdout


def _bool(value: Any) -> bool:
    if type(value) is not bool:
        raise InvalidObservation("invalid_measurement")
    return value


def _number(value: Any) -> float:
    if type(value) not in (float, int) or not 0 <= value < 1_000_000:
        raise InvalidObservation("invalid_measurement")
    return float(value)


def _count(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= 100:
        raise InvalidObservation("invalid_measurement")
    return value


def _opaque_key(value: Any) -> str:
    # Keys are private local pseudonyms. Never include their values in output.
    if not isinstance(value, str) or not 1 <= len(value) <= 80 or any(ord(c) < 33 for c in value):
        raise InvalidObservation("invalid_measurement")
    return value


def _validate_row(row: Any, *, max_windows: int, max_chars: int,
                  independent: bool = False) -> dict[str, Any]:
    if not isinstance(row, dict) or set(row) != (_INDEPENDENT_ROW_KEYS if independent else _ROW_KEYS):
        raise InvalidObservation("invalid_row_schema")
    if independent:
        if row["owner_reviewed_gold"] is not False or row["owner_reviewed_windows"] is not False:
            raise InvalidObservation("invalid_review_authority")
        _bool(row["independently_reviewed_gold"])
        _bool(row["independently_reviewed_windows"])
    case_id = row["case_id"]
    if not isinstance(case_id, str) or not case_id.isascii() or len(case_id) > 8:
        raise InvalidObservation("invalid_case_id")
    _opaque_key(row["gold_document_key"])
    _opaque_key(row["gold_page_key"])
    rank = row["gold_page_rank"]
    if rank is not None and (type(rank) is not int or not 1 <= rank <= 5):
        raise InvalidObservation("invalid_gold_rank")
    for key in ("owner_reviewed_gold", "owner_reviewed_windows", "answer_assertion_present"):
        _bool(row[key])
    if row["result_kind"] not in ("related_knowledge", "no_match"):
        raise InvalidObservation("invalid_result_kind")
    windows = row["windows"]
    if not isinstance(windows, list) or len(windows) > max_windows:
        raise InvalidObservation("invalid_windows")
    if (row["result_kind"] == "no_match") != (len(windows) == 0):
        raise InvalidObservation("invalid_result_bundle")
    seen_pages: set[str] = set()
    for window in windows:
        if not isinstance(window, dict) or set(window) not in (_WINDOW_KEYS, _SOURCE_WINDOW_KEYS):
            raise InvalidObservation("invalid_window_schema")
        page_key = _opaque_key(window["page_key"])
        if page_key in seen_pages:
            raise InvalidObservation("duplicate_display_page")
        seen_pages.add(page_key)
        if type(window["chars"]) is not int or not 1 <= window["chars"] <= max_chars:
            raise InvalidObservation("invalid_window_length")
        for key in _WINDOW_KEYS - {"page_key", "chars"}:
            _bool(window[key])
        if set(window) == _SOURCE_WINDOW_KEYS:
            if window["source_kind"] not in ("chunk", "canonical_page"):
                raise InvalidObservation("invalid_source_kind")
            _bool(window["exact_source_slice"])
            if ((window["source_kind"] == "chunk"
                 and window["exact_source_slice"] != window["exact_chunk_slice"])
                or (window["source_kind"] == "canonical_page" and window["exact_chunk_slice"])
                or (window["source_kind"] == "canonical_page"
                    and window["exact_source_slice"] != window["canonical_page_aligned"])):
                raise InvalidObservation("inconsistent_source_slice")
    for key in ("embedding_calls", "answer_calls", "automatic_retries"):
        _count(row[key])
    _number(row["retrieval_ms"])
    return row


def score(observations: Any, config: dict[str, Any] | None = None, *,
          independent_case_ids: set[str] | frozenset[str] = frozenset()) -> dict[str, Any]:
    """Return only aggregate measurements; never emit private keys or rows."""

    config = manifest() if config is None else config
    seed, holdout = _case_groups(config)
    required = set(seed) | set(holdout) | set(config["controls"])
    limits = config["thresholds"]
    if not isinstance(observations, list):
        raise InvalidObservation("invalid_observations")
    rows: dict[str, dict[str, Any]] = {}
    for raw in observations:
        row = _validate_row(raw, max_windows=limits["displayed_windows_per_case_max"],
                            max_chars=limits["displayed_window_chars_max"],
                            independent=isinstance(raw, dict) and raw.get("case_id") in independent_case_ids)
        case_id = row["case_id"]
        if case_id not in required or case_id in rows:
            raise InvalidObservation("unexpected_or_duplicate_case")
        rows[case_id] = row
    missing = len(required - set(rows))
    def gold_reviewed(row: dict[str, Any]) -> bool:
        return row.get("independently_reviewed_gold", row["owner_reviewed_gold"])

    reviewed = all(gold_reviewed(row) and row.get("independently_reviewed_windows", row["owner_reviewed_windows"])
                   for row in rows.values())

    seed_pages = {rows[case_id]["gold_page_key"] for case_id in seed if case_id in rows}
    held_rows = [rows[case_id] for case_id in holdout if case_id in rows]
    holdout_pages = {row["gold_page_key"] for row in held_rows}
    holdout_disjoint = (len(held_rows) == len(holdout)
                        and len(holdout_pages) >= config["holdout"]["required_distinct_pages"]
                        and len({row["gold_document_key"] for row in held_rows})
                        >= config["holdout"]["minimum_distinct_documents"]
                        and not seed_pages & holdout_pages)

    def exact_slice(window: dict[str, Any]) -> bool:
        return window.get("exact_source_slice", window["exact_chunk_slice"])

    def useful(row: dict[str, Any]) -> bool:
        return any(window["question_relevant"] and exact_slice(window)
                   and window["canonical_page_aligned"] and window["opened_current_page"]
                   and window["current_authorized"] for window in row["windows"])

    def first_relevant(row: dict[str, Any]) -> bool:
        return bool(row["windows"] and row["windows"][0]["question_relevant"])

    seeded = [rows[case_id] for case_id in seed if case_id in rows]
    positives = seeded + held_rows
    windows = [window for row in rows.values() for window in row["windows"]]
    seed_hits = sum(map(useful, seeded))
    holdout_hits = sum(map(useful, held_rows))
    category_hits = {category: sum(useful(rows[case_id]) for case_id in holdout_ids
                                   if case_id in rows)
                     for category, holdout_ids in config["holdout"].items()
                     if isinstance(holdout_ids, list)}
    irrelevant = sum(not window["question_relevant"] for window in windows)
    integrity_failures = sum(not exact_slice(window)
                             or not window["canonical_page_aligned"] for window in windows)
    page_open_failures = sum(not window["opened_current_page"] for window in windows)
    exposures = sum(not window["current_authorized"] for window in windows)
    answer_assertions = sum(row["answer_assertion_present"] for row in rows.values())
    rank_rows = [row for row in positives if gold_reviewed(row)]
    page_recall = (sum(row["gold_page_rank"] is not None for row in rank_rows)
                   / len(rank_rows) if rank_rows else 0.0)
    page_mrr = (fmean(1 / row["gold_page_rank"] if row["gold_page_rank"] else 0
                      for row in rank_rows) if rank_rows else 0.0)
    u01_bad = sum(window["known_irrelevant_u01_pair"] for window in
                  rows.get("U01", {}).get("windows", []))
    # U01's owner label says its known source/claim pair is *irrelevant* to
    # the question. A safe no-match is valid; another independently relevant
    # page may also be shown. Never require the known bad pair as a hit.
    controls_pass = ("N12" in rows and useful(rows["N12"])
                     and "U01" in rows
                     and all(window["question_relevant"] for window in rows["U01"]["windows"])
                     and u01_bad <= limits["known_irrelevant_u01_windows_max"])
    request_contract = all(
        row["embedding_calls"] <= limits["embedding_calls_per_case_max"]
        and row["answer_calls"] <= limits["answer_calls_per_case_max"]
        and row["automatic_retries"] <= limits["automatic_retries_per_case_max"]
        for row in rows.values()
    )
    complete = missing == 0 and reviewed and holdout_disjoint
    relevance_pass = bool(windows) and irrelevant / len(windows) <= limits["irrelevant_window_rate_max"]
    passed = bool(
        complete and seed_hits >= limits["seed_useful_hit_at_3_min"]
        and (not limits["seed_followup_useful_required"] or useful(rows["H01"]))
        and sum(map(first_relevant, seeded)) >= limits["seed_first_window_relevant_min"]
        and holdout_hits >= limits["holdout_useful_hit_at_3_min"]
        and all(value >= limits["holdout_useful_per_category_min"]
                for value in category_hits.values())
        and sum(map(first_relevant, held_rows)) >= limits["holdout_first_window_relevant_min"]
        and relevance_pass
    )
    passed = bool(
        passed and controls_pass and request_contract
        and integrity_failures <= limits["source_integrity_failures_max"]
        and page_open_failures <= limits["page_open_failures_max"]
        and exposures <= limits["unauthorized_or_stale_exposures_max"]
        and answer_assertions <= limits["unverified_answer_assertions_max"]
    )
    return {
        "status": "measured_complete" if complete else "incomplete_unreviewed",
        "candidate_passed": passed,
        "cases_present": len(rows), "cases_required": len(required), "cases_missing": missing,
        "all_windows_owner_reviewed": all(row["owner_reviewed_gold"] and row["owner_reviewed_windows"]
                                          for row in rows.values()),
        "all_windows_reviewed": reviewed,
        "holdout_page_disjoint": holdout_disjoint,
        "seed_useful_hit_at_3": seed_hits,
        "holdout_useful_hit_at_3": holdout_hits,
        "holdout_useful_by_category": category_hits,
        "seed_first_window_relevant": sum(map(first_relevant, seeded)),
        "holdout_first_window_relevant": sum(map(first_relevant, held_rows)),
        "irrelevant_window_rate": irrelevant / len(windows) if windows else 0.0,
        "source_integrity_failures": integrity_failures,
        "page_open_failures": page_open_failures,
        "unauthorized_or_stale_exposures": exposures,
        "unverified_answer_assertions": answer_assertions,
        "known_irrelevant_u01_windows": u01_bad,
        "controls_pass": controls_pass,
        "request_contract_pass": request_contract,
        "reviewed_page_recall_at_5": page_recall,
        "reviewed_page_mrr": page_mrr,
        "retrieval_p95_ms": sorted(row["retrieval_ms"] for row in rows.values())[
            max(0, (len(rows) * 95 + 99) // 100 - 1)] if rows else 0.0,
        "embedding_calls": sum(row["embedding_calls"] for row in rows.values()),
        "answer_calls": sum(row["answer_calls"] for row in rows.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--score", type=Path, help="Content-free measured/owner-reviewed local JSON")
    parser.add_argument("--freeze-holdout", action="store_true",
        help="Pre-register a reviewed X## holdout in a new OS Temp JSON file")
    parser.add_argument("--candidate", type=Path, help="Private source candidate packet")
    parser.add_argument("--owner-review", type=Path, help="Separate private owner labels")
    parser.add_argument("--independent-review", type=Path, help="Separate private agent labels with provenance")
    parser.add_argument("--source-review-artifact", type=Path, help="Original frozen independent PDF-review artifact")
    parser.add_argument("--roster", type=Path, help="Frozen private display-probe roster")
    parser.add_argument("--old-holdout", type=Path, help="Earlier private source-gold roster")
    parser.add_argument("--old-alternatives", type=Path, help="Earlier private source alternatives")
    parser.add_argument("--development-packet", type=Path, action="append", default=[],
        help="Earlier exposed candidate packet, repeat for each bound artifact")
    parser.add_argument("--private-holdout", type=Path, help="Earlier frozen content-free registration")
    parser.add_argument("--output", type=Path, help="New OS Temp registration file")
    args = parser.parse_args()
    config = manifest()
    if args.freeze_holdout:
        try:
            if (args.score is not None or args.private_holdout is not None
                or bool(args.owner_review) == bool(args.independent_review)
                or bool(args.independent_review) != bool(args.source_review_artifact)
                or not all((args.candidate, args.owner_review or args.independent_review, args.roster, args.output,
                            args.old_holdout, args.old_alternatives))
                or not args.development_packet):
                raise InvalidObservation("invalid_private_input")
            frozen = freeze_private_holdout(
                _private_json(args.candidate), _private_json(args.owner_review or args.independent_review, max_bytes=64 * 1024),
                _private_json(args.roster, max_bytes=64 * 1024),
                _private_bytes(args.old_holdout), _private_bytes(args.old_alternatives),
                tuple(_private_bytes(path) for path in args.development_packet),
                source_review_artifact=_private_bytes(args.source_review_artifact)
                    if args.source_review_artifact else None)
            if (args.independent_review is not None) != (frozen["schema"] == INDEPENDENT_HOLDOUT_SCHEMA):
                raise InvalidObservation("invalid_review_authority")
            target = _private_path(args.output)
            with target.open("x", encoding="utf-8") as stream:
                json.dump(frozen, stream, separators=(",", ":"))
            target.chmod(0o600)
            print(json.dumps({"status": "private_holdout_frozen", "candidate_passed": False,
                "holdout_cases": 12, "holdout_manifest_sha256": frozen["holdout_manifest_sha256"],
                "verified_prior_page_exclusions": frozen["verified_prior_page_count"],
                "development_seed_exclusion_independently_verified": False,
                "provider_calls": 0, "database_reads": 0, "database_writes": 0},
                separators=(",", ":")))
            return 0
        except (OSError, UnicodeError, json.JSONDecodeError, InvalidObservation, KeyError, TypeError):
            print('{"status":"invalid_private_holdout","candidate_passed":false}')
            return 1
    if args.score is None and args.private_holdout is None:
        if any((args.candidate, args.owner_review, args.independent_review, args.source_review_artifact, args.roster, args.output,
                args.old_holdout, args.old_alternatives, args.development_packet)):
            print('{"status":"invalid_private_holdout","candidate_passed":false}')
            return 1
        seed, holdout = _case_groups(config)
        print(json.dumps({"status": config["status"], "candidate_passed": False,
                          "seed_cases": len(seed), "holdout_cases_required": len(holdout),
                          "control_cases_required": len(config["controls"]),
                          "provider_calls": 0, "database_reads": 0, "database_writes": 0},
                         separators=(",", ":")))
        return 0
    try:
        if args.score is None or any((args.candidate, args.owner_review, args.independent_review,
                                      args.source_review_artifact, args.roster, args.output,
                                      args.old_holdout, args.old_alternatives,
                                      args.development_packet)):
            raise InvalidObservation("invalid_private_input")
        if args.private_holdout is None:
            report = score(json.loads(args.score.read_text(encoding="utf-8")), config)
        else:
            # A measurement file already present before the exclusive
            # registration is not a preregistered observation. File metadata
            # is only a local ordering guard, not an authenticity signature.
            if (_private_path(args.score).stat().st_mtime_ns
                <= _private_path(args.private_holdout).stat().st_mtime_ns):
                raise InvalidObservation("measurement_predates_registration")
            report = score_private_holdout(_private_json(args.score),
                                           _private_json(args.private_holdout, max_bytes=64 * 1024))
    except (OSError, UnicodeError, json.JSONDecodeError, InvalidObservation, KeyError, TypeError):
        print('{"status":"invalid_local_observations","candidate_passed":false}')
        return 1
    print(json.dumps(report, separators=(",", ":")))
    return 0 if report["candidate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
