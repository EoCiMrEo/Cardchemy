"""Offline v4 release scorer for independently reviewed original-PDF links.

Inputs live in OS Temp. Freeze a candidate roster and independent page/cue
labels before a runtime measurement; then bind exact bytes through a separate
receipt. This module makes no database, browser, network or provider call and
prints aggregate counts only. It cannot itself prove that a reviewer saw the
PDF, that the producer measured the actual UI, or that an external receipt was
frozen at the claimed time; those are separate release evidence obligations.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import tempfile
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


SCHEMA = "source_judgment_display_v4"
POLICY = "related_knowledge_navigation_v4"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_CASE = re.compile(r"[A-Z][0-9]{2}\Z")
_FORMS = ("direct", "paraphrase", "followup")
_GOOD = "Yes"
_LABELS = ("Yes", "No", "Unsure")
_REQUIRED_INTEGRITY = (
    "exact_cue", "page_association_valid", "current_authorized",
    "current_revision", "original_pdf_opened", "same_subject",
)


class InvalidObservation(ValueError):
    """Unsafe or unscorable input. Error codes contain no source content."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise InvalidObservation(code)


def _sha(value: Any) -> bool:
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def _utc(value: Any) -> datetime:
    _require(isinstance(value, str) and re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value
    ) is not None, "invalid_freeze_time")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise InvalidObservation("invalid_freeze_time") from None


def _candidate(value: Any) -> tuple[str, str, str]:
    _require(isinstance(value, dict) and set(value) == {
        "id", "page_key", "cue_sha256"
    }, "invalid_candidate")
    _require(isinstance(value["id"], str) and re.fullmatch(r"C[1-4]", value["id"]) is not None
             and _sha(value["page_key"]) and _sha(value["cue_sha256"]),
             "invalid_candidate")
    return value["id"], value["page_key"], value["cue_sha256"]


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        _require(key not in value, "duplicate_json_key")
        value[key] = item
    return value


def _parse_frozen_json(raw: bytes) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=_unique_object)
    except (UnicodeError, ValueError):
        raise InvalidObservation("invalid_frozen_json") from None


def _roster(raw: Any) -> dict[str, dict[str, Any]]:
    _require(isinstance(raw, dict) and set(raw) == {
        "schema", "policy", "component", "runtime_build_sha256", "frozen_at_utc",
        "stage1_roster_sha256", "cases"
    } and raw["schema"] == SCHEMA + "_roster"
        and raw["policy"] == POLICY
        and raw["component"] in ("private_holdout", "exposed_seed")
        and _sha(raw["runtime_build_sha256"])
        and _sha(raw["stage1_roster_sha256"]),
        "invalid_roster")
    _utc(raw["frozen_at_utc"])
    _require(isinstance(raw["cases"], list), "invalid_roster")
    cases: dict[str, dict[str, Any]] = {}
    for case in raw["cases"]:
        _require(isinstance(case, dict) and set(case) == {
            "case_id", "cohort", "form", "gold_page_key", "candidates"
        } and isinstance(case["case_id"], str)
            and _CASE.fullmatch(case["case_id"]) is not None
            and case["case_id"] not in cases
            and case["cohort"] in ("seed", "holdout", "control")
            and case["form"] in _FORMS
            and (case["gold_page_key"] is None or _sha(case["gold_page_key"]))
            and isinstance(case["candidates"], list)
            and len(case["candidates"]) <= 4, "invalid_roster_case")
        keys = [_candidate(item) for item in case["candidates"]]
        _require(len(set(keys)) == len(keys)
                 and len({key[0] for key in keys}) == len(keys)
                 and len({key[1] for key in keys}) == len(keys),
                 "duplicate_candidate")
        cases[case["case_id"]] = case
    if raw["component"] == "private_holdout":
        _require(set(cases) == {f"T{i:02}" for i in range(1, 13)}
                 and all(case["cohort"] == "holdout"
                         and case["gold_page_key"] is not None
                         for case in cases.values())
                 and all(sum(case["form"] == form for case in cases.values()) == 4
                         for form in _FORMS), "invalid_case_roster")
    else:
        seeds = {f"D{i:02}" for i in range(1, 7)} | {
            f"P{i:02}" for i in range(1, 5)} | {"H01"}
        _require({case_id for case_id, case in cases.items()
                  if case["cohort"] == "seed"} == seeds
                 and all(cases[case_id]["gold_page_key"] is not None
                         for case_id in seeds)
                 and all(case["cohort"] != "holdout" for case in cases.values())
                 and cases.get("N12", {}).get("cohort") == "control"
                 and cases["N12"]["gold_page_key"] is not None
                 and cases.get("U01", {}).get("cohort") == "control"
                 and sum(case["cohort"] == "control"
                         and case["gold_page_key"] is None
                         for case in cases.values()) >= 2,
                 "invalid_case_roster")
    return cases


def _labels(raw: Any, cases: dict[str, dict[str, Any]], roster_sha: str,
            roster_time: datetime) -> dict[tuple[str, str], dict[str, str]]:
    _require(isinstance(raw, dict) and set(raw) == {
        "schema", "component", "roster_sha256", "reviewer_kind", "reviewer_id",
        "independent_of_runtime_selection", "original_pdf_inspected",
        "frozen_at_utc", "runtime_evaluated", "cases"
    } and raw["schema"] == SCHEMA + "_labels"
        and raw["component"] in ("private_holdout", "exposed_seed")
        and raw["roster_sha256"] == roster_sha
        and raw["reviewer_kind"] == "independent_reviewer"
        and isinstance(raw["reviewer_id"], str)
        and re.fullmatch(r"[A-Za-z0-9_/-]{1,80}", raw["reviewer_id"]) is not None
        and raw["independent_of_runtime_selection"] is True
        and raw["original_pdf_inspected"] is True
        and raw["runtime_evaluated"] is False
        and isinstance(raw["cases"], list)
        and _utc(raw["frozen_at_utc"]) > roster_time,
        "invalid_independent_review")
    labels: dict[tuple[str, str], dict[str, str]] = {}
    seen_cases: set[str] = set()
    for row in raw["cases"]:
        _require(isinstance(row, dict) and set(row) == {"case_id", "candidates"}
                 and row["case_id"] in cases and row["case_id"] not in seen_cases
                 and isinstance(row["candidates"], list), "invalid_review_case")
        case_id = row["case_id"]
        seen_cases.add(case_id)
        expected = {candidate["id"]: _candidate(candidate)
                    for candidate in cases[case_id]["candidates"]}
        _require(len(row["candidates"]) == len(expected), "missing_candidate_review")
        for candidate in row["candidates"]:
            _require(isinstance(candidate, dict) and set(candidate) == {
                "id", "page_key", "cue_sha256", "page_useful", "cue_useful"
            }, "invalid_candidate_review")
            identity = _candidate({key: candidate[key] for key in (
                "id", "page_key", "cue_sha256")})
            _require(expected.get(candidate["id"]) == identity
                     and (case_id, candidate["id"]) not in labels
                     and candidate["page_useful"] in _LABELS
                     and candidate["cue_useful"] in _LABELS,
                     "review_identity_mismatch")
            labels[(case_id, candidate["id"])] = candidate
    _require(seen_cases == set(cases), "missing_case_review")
    return labels


def score(roster: Any, labels: Any, receipt: Any, measurement: Any, *,
          roster_sha256: str, labels_sha256: str,
          trusted_review_key_sha256: str) -> dict[str, Any]:
    """Score exact v4 display observations; never return source IDs or content."""

    _require(_sha(roster_sha256) and _sha(labels_sha256)
             and _sha(trusted_review_key_sha256), "invalid_binding")
    cases = _roster(roster)
    reviewed = _labels(labels, cases, roster_sha256, _utc(roster["frozen_at_utc"]))
    _require(isinstance(receipt, dict) and set(receipt) == {
        "schema", "component", "stage1_roster_sha256", "roster_sha256",
        "labels_sha256", "runtime_build_sha256",
        "frozen_at_utc", "approved_release_gate", "reviewer_id",
        "reviewer_public_key_hex", "reviewer_signature_hex"
    } and receipt["schema"] == SCHEMA + "_freeze_receipt"
        and receipt["component"] == labels["component"] == roster["component"]
        and receipt["stage1_roster_sha256"] == roster["stage1_roster_sha256"]
        and receipt["roster_sha256"] == roster_sha256
        and receipt["labels_sha256"] == labels_sha256
        and receipt["runtime_build_sha256"] == roster["runtime_build_sha256"]
        and receipt["approved_release_gate"] == "adr024_original_pdf_v1"
        and receipt["reviewer_id"] == labels["reviewer_id"]
        and _utc(receipt["frozen_at_utc"]) > _utc(labels["frozen_at_utc"]),
        "invalid_freeze_receipt")
    try:
        public_key = bytes.fromhex(receipt["reviewer_public_key_hex"])
        signature = bytes.fromhex(receipt["reviewer_signature_hex"])
        _require(len(public_key) == 32 and len(signature) == 64
                 and hashlib.sha256(public_key).hexdigest()
                 == trusted_review_key_sha256, "untrusted_review_signature")
        signed_body = {key: value for key, value in receipt.items()
                       if key not in ("reviewer_public_key_hex", "reviewer_signature_hex")}
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature, json.dumps(signed_body, sort_keys=True,
                                  separators=(",", ":")).encode("utf-8"))
    except (ValueError, TypeError, InvalidSignature):
        raise InvalidObservation("untrusted_review_signature") from None
    _require(isinstance(measurement, dict) and set(measurement) == {
        "schema", "policy", "component", "stage1_roster_sha256",
        "roster_sha256", "labels_sha256",
        "runtime_build_sha256", "measured_at_utc", "cases"
    } and measurement["schema"] == SCHEMA + "_measurement"
        and measurement["policy"] == POLICY
        and measurement["component"] == roster["component"]
        and measurement["stage1_roster_sha256"] == roster["stage1_roster_sha256"]
        and measurement["roster_sha256"] == roster_sha256
        and measurement["labels_sha256"] == labels_sha256
        and measurement["runtime_build_sha256"] == roster["runtime_build_sha256"]
        and _utc(measurement["measured_at_utc"]) > _utc(receipt["frozen_at_utc"])
        and isinstance(measurement["cases"], list),
        "measurement_not_frozen")
    by_id: dict[str, dict[str, Any]] = {}
    for row in measurement["cases"]:
        _require(isinstance(row, dict) and set(row) == {
            "case_id", "result_kind", "embedding_calls", "source_judgment_calls",
            "answer_calls", "verifier_calls", "automatic_retries",
            "answer_assertion_present", "displayed"
        } and row["case_id"] in cases and row["case_id"] not in by_id
            and row["result_kind"] in (
                "related_knowledge", "no_match", "clarification", "provider_unavailable"
            ) and isinstance(row["displayed"], list)
            and len(row["displayed"]) <= 3
            and type(row["answer_assertion_present"]) is bool
            and all(type(row[key]) is int and 0 <= row[key] <= 3 for key in (
                "embedding_calls", "source_judgment_calls", "answer_calls",
                "verifier_calls", "automatic_retries")), "invalid_measurement_case")
        _require((row["result_kind"] == "related_knowledge") == bool(row["displayed"]),
                 "invalid_result_bundle")
        by_id[row["case_id"]] = row
    _require(set(by_id) == set(cases), "missing_measurement_case")

    counts: Counter[str] = Counter()
    holdout_form: dict[str, Counter[str]] = {form: Counter() for form in _FORMS}
    seed_hits = holdout_hits = 0
    safe = True
    for case_id, case in cases.items():
        row = by_id[case_id]
        issued = {item["id"]: _candidate(item) for item in case["candidates"]}
        shown_ids: set[str] = set()
        case_useful = False
        control_weak = False
        for display_index, displayed in enumerate(row["displayed"]):
            _require(isinstance(displayed, dict) and set(displayed) == {
                "id", "page_key", "cue_sha256", *_REQUIRED_INTEGRITY
            }, "invalid_displayed_card")
            identity = _candidate({key: displayed[key] for key in (
                "id", "page_key", "cue_sha256")})
            _require(issued.get(displayed["id"]) == identity
                     and displayed["id"] not in shown_ids,
                     "display_not_issued")
            shown_ids.add(displayed["id"])
            _require(all(type(displayed[key]) is bool for key in _REQUIRED_INTEGRITY),
                     "invalid_display_integrity")
            valid_source = all(displayed[key] for key in _REQUIRED_INTEGRITY)
            label = reviewed[(case_id, displayed["id"])]
            page_useful = label["page_useful"] == _GOOD
            cue_useful = label["cue_useful"] == _GOOD
            useful = page_useful and cue_useful and valid_source
            counts["displayed_cards"] += 1
            counts["displayed_useful_original_pages"] += page_useful and valid_source
            counts["displayed_useful_cue_and_page"] += useful
            counts["displayed_unsure"] += (
                label["page_useful"] == "Unsure" or label["cue_useful"] == "Unsure"
            )
            counts["display_integrity_failures"] += not valid_source
            counts["fabricated_or_wrong_page"] += not (
                displayed["exact_cue"] and displayed["page_association_valid"]
                and displayed["original_pdf_opened"])
            counts["unauthorized_stale_or_cross_subject"] += not (
                displayed["current_authorized"] and displayed["current_revision"]
                and displayed["same_subject"])
            case_useful |= useful
            control_weak |= not useful
            if display_index == 0:
                counts["top_one_displayed_cases"] += 1
                counts["top_one_useful"] += useful
                if case["gold_page_key"] is not None:
                    counts["positive_top_one_useful"] += useful
        counts["cases"] += 1
        counts["embedding_calls"] += row["embedding_calls"]
        counts["source_judgment_calls"] += row["source_judgment_calls"]
        counts["answer_calls"] += row["answer_calls"]
        counts["verifier_calls"] += row["verifier_calls"]
        counts["automatic_retries"] += row["automatic_retries"]
        counts["answer_assertions"] += row["answer_assertion_present"]
        counts["provider_unavailable"] += row["result_kind"] == "provider_unavailable"
        budget_ok = (row["embedding_calls"] <= 1
                     and row["source_judgment_calls"] <= 1
                     and (row["result_kind"] != "related_knowledge"
                          or row["source_judgment_calls"] == 1)
                     and row["answer_calls"] == row["verifier_calls"]
                     == row["automatic_retries"] == 0
                     and not row["answer_assertion_present"])
        safe &= budget_ok
        counts["policy_budget_violations"] += not budget_ok
        if case["cohort"] == "seed":
            seed_hits += case_useful
        elif case["cohort"] == "holdout":
            holdout_hits += case_useful
            holdout_form[case["form"]]["cases"] += 1
            holdout_form[case["form"]]["useful_hit_at_3"] += case_useful
        else:
            counts["control_cases"] += 1
            counts["control_weak_displayed"] += control_weak
            if case["gold_page_key"] is None:
                counts["no_match_controls"] += 1
                counts["false_no_match_displays"] += bool(row["displayed"])
                counts["invalid_no_match_results"] += row["result_kind"] != "no_match"
                counts["correct_no_match_results"] += row["result_kind"] == "no_match"
            elif case_id == "N12":
                counts["n12_useful_hit"] += case_useful
        if case["gold_page_key"] is not None:
            counts["positive_cases"] += 1
            counts["positive_hit_at_3"] += case_useful
        else:
            counts["negative_cases"] += 1
            counts["negative_displayed"] += bool(row["displayed"])

    shown = counts["displayed_cards"]
    useful = counts["displayed_useful_cue_and_page"]
    displayed_usefulness_ok = bool(shown and useful * 10 >= shown * 9)
    common = bool(shown and counts["false_no_match_displays"] == 0
                  and counts["invalid_no_match_results"] == 0
                  and counts["negative_displayed"] == 0
                  and counts["display_integrity_failures"] == 0
                  and counts["provider_unavailable"] == 0 and safe)
    if roster["component"] == "private_holdout":
        passed = bool(common and holdout_hits >= 10
                      and displayed_usefulness_ok
                      and all(group["useful_hit_at_3"] >= 3
                              for group in holdout_form.values()))
    else:
        passed = bool(common and seed_hits >= 10
                      and counts["n12_useful_hit"] == 1
                      and counts["control_weak_displayed"] == 0)
    return {
        "schema": SCHEMA + "_aggregate", "component": roster["component"],
        "component_passed": passed, "release_gate_passed": False,
        "cases": counts["cases"], "seed_useful_hit_at_3": seed_hits,
        "holdout_useful_hit_at_3": holdout_hits,
        "holdout_by_form": {form: dict(holdout_form[form]) for form in _FORMS},
        "top_one_useful": counts["top_one_useful"],
        "top_one_displayed_cases": counts["top_one_displayed_cases"],
        "positive_top_one_useful": counts["positive_top_one_useful"],
        "positive_cases": counts["positive_cases"],
        "displayed_cards": shown,
        "displayed_useful_cue_and_page": useful,
        "displayed_useful_original_pages": counts["displayed_useful_original_pages"],
        "displayed_unsure_counted_nonuseful": counts["displayed_unsure"],
        "displayed_useful_fraction": useful / shown if shown else 0.0,
        "display_usefulness_gate_passed": displayed_usefulness_ok,
        "no_match_controls": counts["no_match_controls"],
        "correct_no_match_results": counts["correct_no_match_results"],
        "control_weak_displayed": counts["control_weak_displayed"],
        "negative_displayed": counts["negative_displayed"],
        "invalid_no_match_results": counts["invalid_no_match_results"],
        "display_integrity_failures": counts["display_integrity_failures"],
        "fabricated_or_wrong_page": counts["fabricated_or_wrong_page"],
        "unauthorized_stale_or_cross_subject": counts["unauthorized_stale_or_cross_subject"],
        "policy_budget_violations": counts["policy_budget_violations"],
        "provider_unavailable": counts["provider_unavailable"],
        "embedding_calls": counts["embedding_calls"],
        "source_judgment_calls": counts["source_judgment_calls"],
        "answer_calls": counts["answer_calls"],
        "verifier_calls": counts["verifier_calls"],
        "automatic_retries": counts["automatic_retries"],
        "answer_assertions": counts["answer_assertions"],
        "policy_max_calls_per_case": {
            "embedding": 1, "source_judgment": 1,
            "answer": 0, "verifier": 0, "automatic_retry": 0,
        },
    }


def score_release(exposed: tuple[Any, Any, Any, Any, str, str, str],
                  holdout: tuple[Any, Any, Any, Any, str, str, str], *,
                  holdout_bridge: dict[str, Any] | None = None) -> dict[str, Any]:
    """Join signed freezes and exact gold-to-slate admission before release scoring.

    The supplied authorized-page snapshot still needs independent provenance
    from a read-only current-principal/Subject transaction. This pure scorer
    cannot establish that provenance or open the runtime release gate.
    """

    exposed_roster, *rest = exposed
    holdout_roster, *held_rest = holdout
    _require(isinstance(exposed_roster, dict) and isinstance(holdout_roster, dict)
             and exposed_roster.get("component") == "exposed_seed"
             and holdout_roster.get("component") == "private_holdout"
             and exposed_roster.get("runtime_build_sha256")
             == holdout_roster.get("runtime_build_sha256")
             and exposed_roster.get("stage1_roster_sha256")
             != holdout_roster.get("stage1_roster_sha256"),
             "incompatible_release_components")
    exposed_cases = _roster(exposed_roster)
    holdout_cases = _roster(holdout_roster)
    exposed_gold = {case["gold_page_key"] for case in exposed_cases.values()
                    if case["gold_page_key"] is not None}
    holdout_gold = {case["gold_page_key"] for case in holdout_cases.values()}
    _require(not exposed_gold & holdout_gold, "holdout_gold_page_reused")
    _require(all(len(case["candidates"]) == 4 for case in holdout_cases.values()),
             "incomplete_gold_bridge_slate")
    _require(isinstance(holdout_bridge, dict) and set(holdout_bridge) == {
        "stage1_bytes", "stage1_sha256", "roster_bytes", "labels_bytes",
        "authorized_pages", "slates"
    }, "missing_gold_bridge")
    _require(type(holdout_bridge["roster_bytes"]) is bytes
             and type(holdout_bridge["labels_bytes"]) is bytes
             and hashlib.sha256(holdout_bridge["roster_bytes"]).hexdigest()
             == held_rest[3]
             and hashlib.sha256(holdout_bridge["labels_bytes"]).hexdigest()
             == held_rest[4]
             and _parse_frozen_json(holdout_bridge["roster_bytes"])
             == holdout_roster
             and _parse_frozen_json(holdout_bridge["labels_bytes"])
             == held_rest[0], "gold_bridge_input_changed")
    from bridge_private_source_gold_v4 import InvalidBridge, validate_bridge
    try:
        bridge = validate_bridge(
            stage1_bytes=holdout_bridge["stage1_bytes"],
            stage1_sha256=holdout_bridge["stage1_sha256"],
            roster_bytes=holdout_bridge["roster_bytes"],
            roster_sha256=held_rest[3],
            labels_bytes=holdout_bridge["labels_bytes"],
            labels_sha256=held_rest[4],
            authorized_pages=holdout_bridge["authorized_pages"],
            slates=holdout_bridge["slates"],
        )
    except InvalidBridge:
        raise InvalidObservation("gold_bridge_admission_failed") from None
    _require(bridge["gold_pages_bound"] == 12
             and bridge["candidates_bound"]
             == sum(len(case["candidates"]) for case in holdout_roster["cases"]),
             "gold_bridge_admission_failed")
    exposed_result = score(exposed_roster, *rest[:3],
                           roster_sha256=rest[3], labels_sha256=rest[4],
                           trusted_review_key_sha256=rest[5])
    holdout_result = score(holdout_roster, *held_rest[:3],
                           roster_sha256=held_rest[3],
                           labels_sha256=held_rest[4],
                           trusted_review_key_sha256=held_rest[5])
    shown = exposed_result["displayed_cards"] + holdout_result["displayed_cards"]
    useful = (exposed_result["displayed_useful_cue_and_page"]
              + holdout_result["displayed_useful_cue_and_page"])
    return {
        "schema": SCHEMA + "_release_aggregate",
        "display_quality_gate_passed": bool(exposed_result["component_passed"]
                                            and holdout_result["component_passed"]
                                            and shown > 0 and useful * 10 >= shown * 9),
        "release_gate_passed": False,
        "gold_bridge_admitted": True,
        "exposed_seed_useful_hit_at_3": exposed_result["seed_useful_hit_at_3"],
        "private_holdout_useful_hit_at_3": holdout_result["holdout_useful_hit_at_3"],
        "top_one_useful": (exposed_result["top_one_useful"]
                           + holdout_result["top_one_useful"]),
        "top_one_displayed_cases": (exposed_result["top_one_displayed_cases"]
                                    + holdout_result["top_one_displayed_cases"]),
        "positive_top_one_useful": (exposed_result["positive_top_one_useful"]
                                    + holdout_result["positive_top_one_useful"]),
        "positive_cases": (exposed_result["positive_cases"]
                           + holdout_result["positive_cases"]),
        "private_holdout_by_form": holdout_result["holdout_by_form"],
        "private_holdout_displayed_cards": holdout_result["displayed_cards"],
        "private_holdout_displayed_useful": holdout_result["displayed_useful_cue_and_page"],
        "private_holdout_display_usefulness_gate_passed": (
            holdout_result["display_usefulness_gate_passed"]),
        "displayed_cards": shown,
        "displayed_useful_cue_and_page": useful,
        "displayed_useful_fraction": useful / shown if shown else 0.0,
        "no_match_controls": exposed_result["no_match_controls"],
        "correct_no_match_results": exposed_result["correct_no_match_results"],
        "fabricated_or_wrong_page": (
            exposed_result["fabricated_or_wrong_page"]
            + holdout_result["fabricated_or_wrong_page"]),
        "unauthorized_stale_or_cross_subject": (
            exposed_result["unauthorized_stale_or_cross_subject"]
            + holdout_result["unauthorized_stale_or_cross_subject"]),
        "provider_calls": {
            "embedding": exposed_result["embedding_calls"] + holdout_result["embedding_calls"],
            "source_judgment": (exposed_result["source_judgment_calls"]
                                + holdout_result["source_judgment_calls"]),
            "answer": exposed_result["answer_calls"] + holdout_result["answer_calls"],
            "verifier": exposed_result["verifier_calls"] + holdout_result["verifier_calls"],
        },
    }


def _temp_bytes(path: Path, expected_sha: str, *, max_bytes: int = 512 * 1024) -> bytes:
    _require(_sha(expected_sha), "invalid_external_digest")
    root = Path(tempfile.gettempdir()).resolve()
    resolved = path.resolve()
    _require(resolved != root and resolved.is_relative_to(root)
             and not path.is_symlink()
             and not any(parent.is_symlink() for parent in path.parents)
             and resolved.is_file() and 0 < resolved.stat().st_size <= max_bytes,
             "invalid_private_path")
    raw = resolved.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == expected_sha,
             "input_digest_changed")
    return raw


def _temp_json(path: Path, expected_sha: str, *,
               max_bytes: int = 512 * 1024) -> tuple[bytes, Any]:
    raw = _temp_bytes(path, expected_sha, max_bytes=max_bytes)
    return raw, _parse_frozen_json(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--release-execute", action="store_true")
    for name in ("roster", "labels", "receipt", "measurement"):
        parser.add_argument(f"--{name}", type=Path)
        parser.add_argument(f"--{name}-sha256")
        parser.add_argument(f"--holdout-{name}", type=Path)
        parser.add_argument(f"--holdout-{name}-sha256")
    for name in ("stage1-gold", "authorized-pages", "slates"):
        parser.add_argument(f"--holdout-{name}", type=Path)
        parser.add_argument(f"--holdout-{name}-sha256")
    parser.add_argument("--trusted-review-key-sha256")
    parser.add_argument("--holdout-trusted-review-key-sha256")
    args = parser.parse_args()
    if not args.execute and not args.release_execute:
        print(json.dumps({"schema": SCHEMA, "status": "preflight_only",
                          "release_gate_passed": False}))
        return 0
    try:
        def bundle(prefix: str) -> tuple[tuple[Any, ...], dict[str, bytes]]:
            values = []
            raw_inputs = {}
            for name in ("roster", "labels", "receipt", "measurement"):
                path = getattr(args, prefix + name)
                _require(isinstance(path, Path), "missing_private_input")
                raw, parsed = _temp_json(
                    path, getattr(args, prefix + name + "_sha256"))
                raw_inputs[name] = raw
                values.append(parsed)
            return ((*values, getattr(args, prefix + "roster_sha256"),
                     getattr(args, prefix + "labels_sha256"),
                     getattr(args, prefix + "trusted_review_key_sha256")),
                    raw_inputs)

        primary, _ = bundle("")
        if args.release_execute:
            _require(not args.execute, "ambiguous_execution_mode")
            holdout, holdout_raw = bundle("holdout_")
            stage1_path = args.holdout_stage1_gold
            pages_path = args.holdout_authorized_pages
            slates_path = args.holdout_slates
            _require(all(isinstance(path, Path) for path in (
                stage1_path, pages_path, slates_path)), "missing_gold_bridge")
            stage1_raw, _ = _temp_json(stage1_path, args.holdout_stage1_gold_sha256)
            _, pages = _temp_json(pages_path, args.holdout_authorized_pages_sha256,
                                  max_bytes=8 * 1024 * 1024)
            _, slates = _temp_json(slates_path, args.holdout_slates_sha256)
            result = score_release(primary, holdout, holdout_bridge={
                "stage1_bytes": stage1_raw,
                "stage1_sha256": args.holdout_stage1_gold_sha256,
                "roster_bytes": holdout_raw["roster"],
                "labels_bytes": holdout_raw["labels"],
                "authorized_pages": pages,
                "slates": slates,
            })
        else:
            roster, labels, receipt, measurement, roster_sha, labels_sha, key_sha = primary
            result = score(roster, labels, receipt, measurement,
                           roster_sha256=roster_sha,
                           labels_sha256=labels_sha,
                           trusted_review_key_sha256=key_sha)
    except (InvalidObservation, ValueError, TypeError, KeyError, OSError,
            json.JSONDecodeError):
        print(json.dumps({"schema": SCHEMA, "status": "invalid_observation",
                          "release_gate_passed": False}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("display_quality_gate_passed") or result.get("component_passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
