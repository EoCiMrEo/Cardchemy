"""Pure current-policy private display metrics, not runtime release authority.

All inputs are supplied as externally SHA-bound bytes. The caller must establish
the independent original-PDF review, real current-source authorization, actual
display observations and one-use provider execution separately. This module
reads no files, imports no application/provider settings, and changes no v4
measurement or historical label. Unknown labels count as nonuseful.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
import json
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "private_source_display_v6"
POLICY = "related_knowledge_navigation_v6"
CONTRACT = "visual_source_id_v2"
FORMS = ("direct", "paraphrase", "followup")
SEEDS = {f"D{i:02}" for i in range(1, 7)} | {f"P{i:02}" for i in range(1, 5)} | {"H01"}
INTEGRITY = ("exact_cue", "page_association_valid", "current_authorized",
             "current_revision", "original_pdf_opened", "same_subject")
LABELS = ("Yes", "No", "Unsure")


class ScoreError(ValueError):
    """Fixed content-free input rejection."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ScoreError(code)


def _sha(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _time(value: object) -> datetime:
    require(type(value) is str and re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value) is not None,
        "freeze_time_invalid")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise ScoreError("freeze_time_invalid") from None


def _unique(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def _constant(value: str):
    raise ScoreError("json_constant_invalid")


def _bound(raw: bytes, expected: str) -> dict:
    require(type(raw) is bytes and 0 < len(raw) <= 2 * 1024 * 1024 and _sha(expected)
            and sha256(raw).hexdigest() == expected, "input_sha_invalid")
    try:
        value = json.loads(raw, object_pairs_hook=_unique, parse_constant=_constant)
    except (UnicodeError, ValueError, RecursionError):
        raise ScoreError("json_invalid") from None
    require(type(value) is dict, "object_required")
    return value


def _review_seal(receipt: dict, *, roster_sha: str, labels_sha: str,
                 trusted_review_key_sha: str, labels_time: datetime) -> None:
    require(set(receipt) == {"schema", "roster_sha256", "labels_sha256", "reviewer_id",
                            "frozen_at_utc", "reviewer_public_key_hex", "reviewer_signature_hex"}
            and receipt["schema"] == SCHEMA + "_review_receipt"
            and receipt["roster_sha256"] == roster_sha and receipt["labels_sha256"] == labels_sha
            and type(receipt["reviewer_id"]) is str
            and re.fullmatch(r"[A-Za-z0-9_/-]{1,80}", receipt["reviewer_id"]) is not None
            and _time(receipt["frozen_at_utc"]) == labels_time and _sha(trusted_review_key_sha)
            and type(receipt["reviewer_public_key_hex"]) is str
            and type(receipt["reviewer_signature_hex"]) is str,
            "review_seal_invalid")
    try:
        public_key = bytes.fromhex(receipt["reviewer_public_key_hex"])
        signature = bytes.fromhex(receipt["reviewer_signature_hex"])
        require(len(public_key) == 32 and len(signature) == 64
                and sha256(public_key).hexdigest() == trusted_review_key_sha,
                "untrusted_review_key")
        body = {key: value for key, value in receipt.items()
                if key not in ("reviewer_public_key_hex", "reviewer_signature_hex")}
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, canonical)
    except (ValueError, InvalidSignature):
        raise ScoreError("review_seal_invalid") from None


def _roster(value: dict) -> dict:
    require(set(value) == {"schema", "policy", "contract", "component", "runtime_sha256",
                           "stage1_sha256", "frozen_at_utc", "cases"}
            and value["schema"] == SCHEMA + "_roster" and value["policy"] == POLICY
            and value["contract"] == CONTRACT and _sha(value["runtime_sha256"])
            and _sha(value["stage1_sha256"])
            and value["component"] in ("private_holdout", "exposed_seed")
            and type(value["cases"]) is list, "roster_invalid")
    _time(value["frozen_at_utc"])
    rows = {}
    for row in value["cases"]:
        require(type(row) is dict and set(row) == {
            "case_id", "form", "gold_page_key", "require_empty", "request_sha256", "candidates"}
            and type(row["case_id"]) is str and re.fullmatch(r"[A-Z][0-9]{2}", row["case_id"])
            and row["case_id"] not in rows and type(row["form"]) is str and row["form"] in (*FORMS, "control")
            and (row["gold_page_key"] is None or _sha(row["gold_page_key"]))
            and type(row["require_empty"]) is bool
            and type(row["candidates"]) is list and len(row["candidates"]) <= 4
            and (_sha(row["request_sha256"]) if row["candidates"] else row["request_sha256"] is None),
            "roster_case_invalid")
        page_keys = set()
        for ordinal, candidate in enumerate(row["candidates"], 1):
            require(type(candidate) is dict and set(candidate) == {
                "id", "page_key", "cue_sha256", "pdf_sha256"}
                and type(candidate["id"]) is str and candidate["id"] == f"S{ordinal:02}"
                and all(_sha(candidate[key]) for key in ("page_key", "cue_sha256", "pdf_sha256"))
                and candidate["page_key"] not in page_keys, "candidate_invalid")
            page_keys.add(candidate["page_key"])
        rows[row["case_id"]] = row
    if value["component"] == "private_holdout":
        require(set(rows) == {f"T{i:02}" for i in range(1, 13)}
                and Counter(row["form"] for row in rows.values()) == Counter({form: 4 for form in FORMS})
                and all(row["gold_page_key"] is not None and not row["require_empty"] for row in rows.values())
                and len({row["gold_page_key"] for row in rows.values()}) == 12,
                "holdout_roster_invalid")
    else:
        require(SEEDS <= set(rows) and all(rows[key]["gold_page_key"] is not None
                and not rows[key]["require_empty"] for key in SEEDS)
                and "N12" in rows and rows["N12"]["gold_page_key"] is not None
                and not rows["N12"]["require_empty"] and "U01" in rows
                and rows["U01"]["require_empty"]
                and all(row["form"] == "control" for key, row in rows.items() if key not in SEEDS)
                and sum(row["require_empty"] for row in rows.values()) >= 2,
                "seed_roster_invalid")
    return rows


def score(roster_bytes: bytes, labels_bytes: bytes, measurement_bytes: bytes, *,
          roster_sha256: str, labels_sha256: str, measurement_sha256: str,
          review_receipt_bytes: bytes, review_receipt_sha256: str,
          trusted_review_key_sha256: str) -> dict:
    """Evaluate every frozen case/card; missing or failed cases cannot disappear."""
    roster = _bound(roster_bytes, roster_sha256)
    labels = _bound(labels_bytes, labels_sha256)
    measured = _bound(measurement_bytes, measurement_sha256)
    receipt = _bound(review_receipt_bytes, review_receipt_sha256)
    cases = _roster(roster)
    require(set(labels) == {"schema", "roster_sha256", "frozen_at_utc",
                           "independent_of_runtime_selection", "original_pdf_inspected",
                           "runtime_evaluated", "cases"}
            and labels["schema"] == SCHEMA + "_labels" and labels["roster_sha256"] == roster_sha256
            and labels["independent_of_runtime_selection"] is True
            and labels["original_pdf_inspected"] is True and labels["runtime_evaluated"] is False
            and _time(labels["frozen_at_utc"]) > _time(roster["frozen_at_utc"])
            and type(labels["cases"]) is list, "review_invalid")
    reviewed, seen = {}, set()
    for row in labels["cases"]:
        require(type(row) is dict and set(row) == {"case_id", "candidates"}
                and type(row["case_id"]) is str and row["case_id"] in cases and row["case_id"] not in seen
                and type(row["candidates"]) is list, "review_case_invalid")
        cid = row["case_id"]
        expected = {candidate["id"]: candidate for candidate in cases[cid]["candidates"]}
        seen.add(cid)
        require(len(row["candidates"]) == len(expected), "incomplete_candidate_review")
        for candidate in row["candidates"]:
            require(type(candidate) is dict and set(candidate) == {
                "id", "page_key", "cue_sha256", "pdf_sha256", "page_useful", "cue_useful"}
                and type(candidate["id"]) is str and candidate["id"] in expected and (cid, candidate["id"]) not in reviewed
                and {key: candidate[key] for key in expected[candidate["id"]]} == expected[candidate["id"]]
                and candidate["page_useful"] in LABELS and candidate["cue_useful"] in LABELS,
                "review_identity_invalid")
            reviewed[(cid, candidate["id"])] = candidate
    require(seen == set(cases), "incomplete_case_review")
    _review_seal(receipt, roster_sha=roster_sha256, labels_sha=labels_sha256,
                 trusted_review_key_sha=trusted_review_key_sha256,
                 labels_time=_time(labels["frozen_at_utc"]))
    require(set(measured) == {"schema", "policy", "contract", "runtime_sha256",
                             "roster_sha256", "labels_sha256", "executed_at_utc", "cases"}
            and measured["schema"] == SCHEMA + "_measurement" and measured["policy"] == POLICY
            and measured["contract"] == CONTRACT and measured["runtime_sha256"] == roster["runtime_sha256"]
            and measured["roster_sha256"] == roster_sha256 and measured["labels_sha256"] == labels_sha256
            and _time(measured["executed_at_utc"]) > _time(labels["frozen_at_utc"])
            and type(measured["cases"]) is list, "measurement_binding_invalid")
    calls = ("embedding_calls", "source_judgment_calls", "answer_calls", "verifier_calls", "automatic_retries")
    count, hits, observed = Counter(), Counter(), set()
    for row in measured["cases"]:
        require(type(row) is dict and set(row) == {"case_id", "state", "answer_assertion_present", "displayed", *calls}
                and type(row["case_id"]) is str and row["case_id"] in cases and row["case_id"] not in observed
                and type(row["state"]) is str and row["state"] in ("related_knowledge", "no_match", "clarification_needed", "provider_unavailable")
                and type(row["displayed"]) is list and len(row["displayed"]) <= 3
                and type(row["answer_assertion_present"]) is bool
                and all(type(row[key]) is int and row[key] >= 0 for key in calls)
                and (bool(row["displayed"]) == (row["state"] == "related_knowledge")),
                "measurement_case_invalid")
        cid = row["case_id"]
        observed.add(cid)
        count["provider_unavailable"] += row["state"] == "provider_unavailable"
        count["policy_violations"] += not (
            row["embedding_calls"] <= 1 and row["source_judgment_calls"] <= 1
            and (not row["displayed"] or row["source_judgment_calls"] == 1)
            and row["answer_calls"] == row["verifier_calls"] == row["automatic_retries"] == 0
            and row["answer_assertion_present"] is False)
        for key in calls:
            count[key] += row[key]
        displayed_ids, useful_case = set(), False
        for item in row["displayed"]:
            require(type(item) is dict and set(item) == {"id", "page_key", "cue_sha256", "pdf_sha256", *INTEGRITY}
                    and type(item["id"]) is str and item["id"] not in displayed_ids and (cid, item["id"]) in reviewed
                    and all(type(item[key]) is bool for key in INTEGRITY), "display_invalid")
            label = reviewed[(cid, item["id"])]
            require(all(item[key] == label[key] for key in ("id", "page_key", "cue_sha256", "pdf_sha256")),
                    "display_identity_invalid")
            displayed_ids.add(item["id"])
            integrity = all(item[key] for key in INTEGRITY)
            useful = integrity and label["page_useful"] == label["cue_useful"] == "Yes"
            count["displayed_cards"] += 1
            count["useful_cards"] += useful
            count["unknown_cards"] += "Unsure" in (label["page_useful"], label["cue_useful"])
            count["integrity_failures"] += not integrity
            useful_case |= useful
        count["useful_hit_at_3"] += useful_case
        if cases[cid]["form"] in FORMS:
            hits[cases[cid]["form"]] += useful_case
        if cid in SEEDS:
            count["seed_hits"] += useful_case
        if cid == "N12":
            count["n12_hit"] += useful_case
        if cases[cid]["require_empty"]:
            count["control_failures"] += row["state"] != "no_match" or bool(row["displayed"])
    shown = count["displayed_cards"]
    gates = {"complete": observed == set(cases), "availability": count["provider_unavailable"] == 0,
             "policy_budget": count["policy_violations"] == 0, "source_integrity": count["integrity_failures"] == 0,
             "all_displayed_usefulness": shown > 0 and 5 * count["useful_cards"] >= 4 * shown,
             "negative_controls": count["control_failures"] == 0}
    if roster["component"] == "private_holdout":
        gates.update(positive_hits=count["useful_hit_at_3"] >= 10,
                     per_form_hits=all(hits[form] >= 3 for form in FORMS))
    else:
        gates.update(positive_hits=count["seed_hits"] >= 10, n12_control=count["n12_hit"] == 1)
    return {"schema": SCHEMA + "_aggregate", "component": roster["component"],
            "component_passed": all(gates.values()), "release_gate_passed": False, "gates": gates,
            "case_denominator": len(cases), "observed_cases": len(observed), "missing_cases": len(cases) - len(observed),
            "useful_hit_at_3": count["useful_hit_at_3"], "hits_by_form": {form: hits[form] for form in FORMS},
            "displayed_cards": shown, "useful_cards": count["useful_cards"], "unknown_cards": count["unknown_cards"],
            "displayed_usefulness": count["useful_cards"] / shown if shown else 0,
            "minimum_displayed_usefulness_percent": 80,
            "integrity_failures": count["integrity_failures"], "policy_violations": count["policy_violations"],
            "provider_unavailable": count["provider_unavailable"], "control_failures": count["control_failures"],
            "physical_calls": {key: count[key] for key in calls}}
