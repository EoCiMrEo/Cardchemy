"""Keyless, content-free contracts for the v4 original-PDF release scorer."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from uuid import UUID

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/score_source_judgment_display_v4.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("score_source_judgment_display_v4", SCRIPT)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)
_TEST_SIGNER = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
_TEST_PUBKEY = _TEST_SIGNER.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)
_TEST_PUB_SHA = hashlib.sha256(_TEST_PUBKEY).hexdigest()


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _sign(receipt):
    receipt["reviewer_public_key_hex"] = _TEST_PUBKEY.hex()
    body = {key: value for key, value in receipt.items()
            if key not in ("reviewer_public_key_hex", "reviewer_signature_hex")}
    receipt["reviewer_signature_hex"] = _TEST_SIGNER.sign(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hex()


def _inputs(component="exposed_seed"):
    seed = ([f"D{i:02}" for i in range(1, 7)]
            + [f"P{i:02}" for i in range(1, 5)] + ["H01"])
    holdout = [f"T{i:02}" for i in range(1, 13)]
    ids = (holdout if component == "private_holdout" else
           seed + ["N12", "U01", "C01"])
    cases = []
    reviews = []
    measurements = []
    for index, case_id in enumerate(ids):
        if case_id in seed:
            cohort = "seed"
            form = ("followup" if case_id == "H01" else
                    "paraphrase" if case_id.startswith("P") else "direct")
        elif case_id in holdout:
            cohort = "holdout"
            form = _FORMS[(index - len(seed)) // 4]
        else:
            cohort = "control"
            form = "direct"
        positive = case_id not in {"U01", "C01"}
        candidates = [{"id": f"C{slot}",
                       "page_key": hashlib.sha256(f"{case_id}-page-{slot}".encode()).hexdigest(),
                       "cue_sha256": hashlib.sha256(f"{case_id}-cue-{slot}".encode()).hexdigest()}
                      for slot in range(1, 5)]
        cases.append({"case_id": case_id, "cohort": cohort, "form": form,
                      "gold_page_key": candidates[0]["page_key"] if positive else None,
                      "candidates": candidates})
        reviews.append({"case_id": case_id, "candidates": [
            {**candidate, "page_useful": "Yes" if positive and slot == 0 else "No",
             "cue_useful": "Yes" if positive and slot == 0 else "No"}
            for slot, candidate in enumerate(candidates)]})
        selected = ([{**candidates[0],
                     "exact_cue": True, "page_association_valid": True,
                     "current_authorized": True, "current_revision": True,
                     "original_pdf_opened": True, "same_subject": True}] if positive else [])
        measurements.append({"case_id": case_id,
                             "result_kind": "related_knowledge" if positive else "no_match",
                             "embedding_calls": 1, "source_judgment_calls": 1,
                             "answer_calls": 0, "verifier_calls": 0,
                             "automatic_retries": 0,
                             "answer_assertion_present": False,
                             "displayed": selected})
    roster = {"schema": gate.SCHEMA + "_roster", "policy": gate.POLICY,
              "component": component,
              "runtime_build_sha256": "a" * 64,
              "stage1_roster_sha256": "b" * 64 if component == "private_holdout" else "c" * 64,
              "frozen_at_utc": "2026-09-29T00:00:00Z", "cases": cases}
    labels = {"schema": gate.SCHEMA + "_labels",
              "component": component,
              "roster_sha256": _digest(roster),
              "reviewer_kind": "independent_reviewer", "reviewer_id": "reviewer1",
              "independent_of_runtime_selection": True,
              "original_pdf_inspected": True,
              "frozen_at_utc": "2026-09-29T00:01:00Z",
              "runtime_evaluated": False, "cases": reviews}
    receipt = {"schema": gate.SCHEMA + "_freeze_receipt",
               "component": component,
               "stage1_roster_sha256": roster["stage1_roster_sha256"],
               "roster_sha256": _digest(roster), "labels_sha256": _digest(labels),
               "runtime_build_sha256": "a" * 64,
               "frozen_at_utc": "2026-09-29T00:02:00Z",
               "approved_release_gate": "adr024_original_pdf_v1",
               "reviewer_id": "reviewer1"}
    _sign(receipt)
    measurement = {"schema": gate.SCHEMA + "_measurement", "policy": gate.POLICY,
                   "component": component,
                   "stage1_roster_sha256": roster["stage1_roster_sha256"],
                   "roster_sha256": _digest(roster), "labels_sha256": _digest(labels),
                   "runtime_build_sha256": "a" * 64,
                   "measured_at_utc": "2026-09-29T00:03:00Z",
                   "cases": measurements}
    return roster, labels, receipt, measurement


_FORMS = ("direct", "paraphrase", "followup")


def _score(inputs):
    roster, labels, receipt, measurement = inputs
    return gate.score(roster, labels, receipt, measurement,
                      roster_sha256=_digest(roster), labels_sha256=_digest(labels),
                      trusted_review_key_sha256=_TEST_PUB_SHA)


def _bundle(inputs):
    return (*inputs, _digest(inputs[0]), _digest(inputs[1]), _TEST_PUB_SHA)


def _bridge_material(inputs):
    """Pure synthetic current-page snapshot bound to the private holdout slate."""
    import bridge_private_source_gold_v4 as bridge

    roster, labels, receipt, measurement = inputs
    stage_cases = []
    pages = []
    slates = []
    documents = {}
    for slot in (1, 2, 3):
        documents[slot] = {
            "document_id": str(UUID(int=slot)),
            "content_revision_id": str(UUID(int=slot + 10)),
            "index_revision_id": str(UUID(int=slot + 20)),
            "original_pdf_sha256": hashlib.sha256(f"pdf-{slot}".encode()).hexdigest(),
            "original_pdf_page_count": 48,
        }
    for index, (case, review, observed) in enumerate(zip(
        roster["cases"], labels["cases"], measurement["cases"], strict=True
    )):
        slot = index % 3 + 1
        document = documents[slot]
        issued = []
        slate = []
        for number in range(4):
            page_number = index * 4 + number + 1
            page_text = f"Synthetic page {page_number}: method {index + 1} has a result."
            page_key = bridge._digest([document["document_id"], page_number])
            identity = {
                "id": f"C{number + 1}", "page_key": page_key,
                "cue_sha256": hashlib.sha256(page_text.encode()).hexdigest(),
            }
            issued.append(identity)
            slate.append({
                "runtime_id": f"S{number + 1:02}",
                "document_id": document["document_id"],
                "page_number": page_number,
                "start_offset": 0, "end_offset": len(page_text),
            })
            pages.append({
                **document, "page_number": page_number, "page_text": page_text,
                "corpus_revision": 7, "embedding_space_hash": "e" * 64,
                "current_authorized": True, "published": True, "index_ready": True,
            })
        case["gold_page_key"] = issued[0]["page_key"]
        case["candidates"] = issued
        for number, review_candidate in enumerate(review["candidates"]):
            review_candidate.update(issued[number])
        for shown in observed["displayed"]:
            shown.update(issued[int(shown["id"][1:]) - 1])
        slates.append({"case_id": case["case_id"], "candidates": slate})
        gold = pages[index * 4]
        stage_cases.append({
            "case_id": case["case_id"], "form": case["form"],
            "question": f"How does synthetic method {index + 1} work?",
            "previous_turn": "Which method?" if case["form"] == "followup" else "",
            "document_slot": slot, "page_number": gold["page_number"],
            "page_useful": "Yes",
            "page_sha256": hashlib.sha256(gold["page_text"].encode()).hexdigest(),
            "page_key": issued[0]["page_key"], **document,
        })
    stage1 = {
        "schema": bridge.SCHEMA, "authored_input_sha256": "a" * 64,
        "reviewer_kind": "agent_self_review",
        "review_method": "authenticated_original_pdf_browser",
        "candidate_selection_seen": False,
        "frozen_at_utc": "2026-09-28T23:59:00Z",
        "scope": {"corpus_revision": 7, "embedding_space_hash": "e" * 64},
        "cases": stage_cases,
    }
    stage1_bytes = json.dumps(stage1, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=False).encode()
    roster["stage1_roster_sha256"] = hashlib.sha256(stage1_bytes).hexdigest()
    roster_sha = _digest(roster)
    labels["roster_sha256"] = roster_sha
    labels_sha = _digest(labels)
    receipt["stage1_roster_sha256"] = roster["stage1_roster_sha256"]
    receipt["roster_sha256"] = roster_sha
    receipt["labels_sha256"] = labels_sha
    _sign(receipt)
    measurement["stage1_roster_sha256"] = roster["stage1_roster_sha256"]
    measurement["roster_sha256"] = roster_sha
    measurement["labels_sha256"] = labels_sha
    return {
        "stage1_bytes": stage1_bytes,
        "stage1_sha256": roster["stage1_roster_sha256"],
        "roster_bytes": json.dumps(roster, sort_keys=True).encode(),
        "labels_bytes": json.dumps(labels, sort_keys=True).encode(),
        "authorized_pages": pages,
        "slates": slates,
    }


def _release(exposed, holdout, bridge_material):
    return gate.score_release(_bundle(exposed), _bundle(holdout),
                              holdout_bridge=bridge_material)


def _release_cli_args(tmp_path, exposed, holdout, bridge_material):
    args = [str(SCRIPT), "--release-execute"]
    files = {}
    for prefix, inputs in (("", exposed), ("holdout-", holdout)):
        for name, value in zip(("roster", "labels", "receipt", "measurement"),
                               inputs, strict=True):
            raw = json.dumps(value, sort_keys=True).encode()
            path = tmp_path / f"{prefix}{name}.json"
            path.write_bytes(raw)
            files[f"{prefix}{name}"] = path
            args.extend((f"--{prefix}{name}", str(path),
                         f"--{prefix}{name}-sha256", hashlib.sha256(raw).hexdigest()))
        args.extend((f"--{prefix}trusted-review-key-sha256", _TEST_PUB_SHA))
    for name, value in (
        ("stage1-gold", bridge_material["stage1_bytes"]),
        ("authorized-pages", bridge_material["authorized_pages"]),
        ("slates", bridge_material["slates"]),
    ):
        raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True).encode()
        path = tmp_path / f"holdout-{name}.json"
        path.write_bytes(raw)
        files[f"holdout-{name}"] = path
        args.extend((f"--holdout-{name}", str(path),
                     f"--holdout-{name}-sha256", hashlib.sha256(raw).hexdigest()))
    return args, files


def test_all_reviewed_cues_and_original_pages_pass_only_aggregate_gate():
    result = _score(_inputs())
    assert result["component_passed"]
    assert not result["release_gate_passed"]
    assert result["seed_useful_hit_at_3"] == 11
    assert result["holdout_useful_hit_at_3"] == 0
    assert result["displayed_cards"] == result["displayed_useful_cue_and_page"] == 12
    assert result["no_match_controls"] == 2
    assert "D01" not in json.dumps(result)


def test_only_combined_independently_frozen_components_can_pass_release():
    exposed, holdout = _inputs(), _inputs("private_holdout")
    bridge_material = _bridge_material(holdout)
    assert _score(holdout)["component_passed"]
    assert not _score(holdout)["release_gate_passed"]
    result = _release(exposed, holdout, bridge_material)
    assert result["display_quality_gate_passed"]
    assert result["gold_bridge_admitted"]
    assert not result["release_gate_passed"]
    assert result["exposed_seed_useful_hit_at_3"] == 11
    assert result["private_holdout_useful_hit_at_3"] == 12
    assert result["displayed_cards"] == result["displayed_useful_cue_and_page"] == 24
    assert result["top_one_useful"] == result["top_one_displayed_cases"] == 24
    assert result["positive_top_one_useful"] == result["positive_cases"] == 24
    assert result["no_match_controls"] == result["correct_no_match_results"] == 2


def test_combined_gate_counts_weak_cards_in_both_splits():
    exposed, holdout = _inputs(), _inputs("private_holdout")
    bridge_material = _bridge_material(holdout)
    for case_id in ("D01", "T01", "T02"):
        inputs = exposed if case_id.startswith("D") else holdout
        case = next(row for row in inputs[0]["cases"] if row["case_id"] == case_id)
        row = next(row for row in inputs[3]["cases"] if row["case_id"] == case_id)
        row["displayed"].append({**case["candidates"][1],
                                 **{key: True for key in gate._REQUIRED_INTEGRITY}})
    result = _release(exposed, holdout, bridge_material)
    assert result["displayed_cards"] == 27
    assert result["displayed_useful_cue_and_page"] == 24
    assert result["displayed_useful_fraction"] == 24 / 27
    assert not result["display_quality_gate_passed"]


def test_strong_exposed_split_cannot_hide_weak_independent_holdout_cards():
    exposed, holdout = _inputs(), _inputs("private_holdout")
    bridge_material = _bridge_material(holdout)
    for case_id in ("T01", "T02"):
        case = next(row for row in holdout[0]["cases"] if row["case_id"] == case_id)
        row = next(row for row in holdout[3]["cases"] if row["case_id"] == case_id)
        row["displayed"].append({**case["candidates"][1],
                                 **{key: True for key in gate._REQUIRED_INTEGRITY}})
    result = _release(exposed, holdout, bridge_material)
    assert result["private_holdout_useful_hit_at_3"] == 12
    assert result["private_holdout_displayed_cards"] == 14
    assert result["private_holdout_displayed_useful"] == 12
    assert not result["private_holdout_display_usefulness_gate_passed"]
    assert result["displayed_useful_fraction"] == 24 / 26  # Global ratio alone exceeds 90%.
    assert not result["display_quality_gate_passed"]


def test_release_rejects_reused_stage_one_or_page_identity():
    exposed, holdout = _inputs(), _inputs("private_holdout")
    bridge_material = _bridge_material(holdout)
    holdout[0]["stage1_roster_sha256"] = exposed[0]["stage1_roster_sha256"]
    with pytest.raises(gate.InvalidObservation, match="incompatible_release_components"):
        _release(exposed, holdout, bridge_material)
    exposed, holdout = _inputs(), _inputs("private_holdout")
    bridge_material = _bridge_material(holdout)
    holdout[0]["cases"][0]["gold_page_key"] = (
        exposed[0]["cases"][0]["gold_page_key"])
    holdout[1]["roster_sha256"] = _digest(holdout[0])
    holdout[2]["roster_sha256"] = holdout[3]["roster_sha256"] = _digest(holdout[0])
    holdout[2]["labels_sha256"] = holdout[3]["labels_sha256"] = _digest(holdout[1])
    _sign(holdout[2])
    with pytest.raises(gate.InvalidObservation, match="holdout_gold_page_reused"):
        _release(exposed, holdout, bridge_material)


@pytest.mark.parametrize("changed", ["page_useful", "cue_useful"])
def test_unsure_on_displayed_card_counts_as_nonuseful(changed):
    roster, labels, receipt, measurement = _inputs()
    for case_id in ("D01", "D02", "D03"):
        row = next(row for row in labels["cases"] if row["case_id"] == case_id)
        row["candidates"][0][changed] = "Unsure"
    labels["roster_sha256"] = _digest(roster)
    receipt["labels_sha256"] = measurement["labels_sha256"] = _digest(labels)
    _sign(receipt)
    result = _score((roster, labels, receipt, measurement))
    assert result["displayed_unsure_counted_nonuseful"] == 3
    assert result["displayed_useful_fraction"] < 0.9
    assert not result["release_gate_passed"]


def test_every_displayed_card_counts_in_denominator_including_weak_second_cards():
    roster, labels, receipt, measurement = _inputs()
    for case_id in ("D01", "D02", "D03"):
        case = next(row for row in roster["cases"] if row["case_id"] == case_id)
        row = next(row for row in measurement["cases"] if row["case_id"] == case_id)
        row["displayed"].append({**case["candidates"][1],
                                 "exact_cue": True, "page_association_valid": True,
                                 "current_authorized": True, "current_revision": True,
                                 "original_pdf_opened": True, "same_subject": True})
    result = _score((roster, labels, receipt, measurement))
    assert result["seed_useful_hit_at_3"] == 11
    assert result["displayed_cards"] == 15
    assert result["displayed_useful_fraction"] == 12 / 15
    assert result["component_passed"]  # Independent holdout and combined ratio are later gates.


def test_top_one_reports_first_displayed_card_and_positive_question_denominator():
    inputs = list(_inputs())
    case = next(row for row in inputs[0]["cases"] if row["case_id"] == "D01")
    shown = next(row for row in inputs[3]["cases"] if row["case_id"] == "D01")["displayed"]
    integrity = {key: True for key in gate._REQUIRED_INTEGRITY}
    shown.insert(0, {**case["candidates"][1], **integrity})
    result = _score(tuple(inputs))
    assert result["seed_useful_hit_at_3"] == 11  # The useful second card still counts at three.
    assert result["top_one_useful"] == 11
    assert result["top_one_displayed_cases"] == 12
    assert result["positive_top_one_useful"] == 11
    assert result["positive_cases"] == 12


def test_release_refuses_missing_or_changed_private_gold_bridge():
    exposed, holdout = _inputs(), _inputs("private_holdout")
    bridge_material = _bridge_material(holdout)
    with pytest.raises(gate.InvalidObservation, match="missing_gold_bridge"):
        gate.score_release(_bundle(exposed), _bundle(holdout))
    wrong = deepcopy(bridge_material)
    wrong["slates"][0]["candidates"][0]["end_offset"] = 5
    with pytest.raises(gate.InvalidObservation, match="gold_bridge_admission_failed"):
        _release(exposed, holdout, wrong)
    wrong = deepcopy(bridge_material)
    wrong["authorized_pages"][0]["current_authorized"] = False
    with pytest.raises(gate.InvalidObservation, match="gold_bridge_admission_failed"):
        _release(exposed, holdout, wrong)


def test_release_requires_four_issued_pages_per_private_question():
    exposed, holdout = _inputs(), _inputs("private_holdout")
    bridge_material = _bridge_material(holdout)
    holdout[0]["cases"][0]["candidates"].pop()
    holdout[1]["cases"][0]["candidates"].pop()
    bridge_material["slates"][0]["candidates"].pop()
    holdout[1]["roster_sha256"] = _digest(holdout[0])
    holdout[2]["roster_sha256"] = holdout[3]["roster_sha256"] = _digest(holdout[0])
    holdout[2]["labels_sha256"] = holdout[3]["labels_sha256"] = _digest(holdout[1])
    _sign(holdout[2])
    bridge_material["roster_bytes"] = json.dumps(holdout[0], sort_keys=True).encode()
    bridge_material["labels_bytes"] = json.dumps(holdout[1], sort_keys=True).encode()
    with pytest.raises(gate.InvalidObservation, match="incomplete_gold_bridge_slate"):
        _release(exposed, holdout, bridge_material)


def test_no_match_display_and_provider_failure_fail_separately():
    inputs = list(_inputs())
    measurement = inputs[-1]
    control = next(row for row in measurement["cases"] if row["case_id"] == "U01")
    candidate = next(row for row in inputs[0]["cases"] if row["case_id"] == "U01")["candidates"][0]
    control["result_kind"] = "related_knowledge"
    control["displayed"] = [{**candidate, **{key: True for key in gate._REQUIRED_INTEGRITY}}]
    result = _score(tuple(inputs))
    assert result["negative_displayed"] == 1
    assert not result["component_passed"]

    control["displayed"] = []
    control["result_kind"] = "provider_unavailable"
    result = _score(tuple(inputs))
    assert result["provider_unavailable"] == 1
    assert not result["component_passed"]


def test_missing_independent_candidate_label_fails_closed():
    inputs = list(_inputs())
    inputs[1]["cases"][0]["candidates"].pop()
    inputs[2]["labels_sha256"] = inputs[3]["labels_sha256"] = _digest(inputs[1])
    _sign(inputs[2])
    with pytest.raises(gate.InvalidObservation, match="missing_candidate_review"):
        _score(tuple(inputs))


def test_measurement_cannot_select_unissued_or_duplicate_card():
    inputs = list(_inputs())
    first = inputs[3]["cases"][0]["displayed"]
    first[0]["cue_sha256"] = "f" * 64
    with pytest.raises(gate.InvalidObservation, match="display_not_issued"):
        _score(tuple(inputs))
    first[0]["cue_sha256"] = inputs[0]["cases"][0]["candidates"][0]["cue_sha256"]
    first.append(deepcopy(first[0]))
    with pytest.raises(gate.InvalidObservation, match="display_not_issued"):
        _score(tuple(inputs))


def test_counters_and_original_pdf_open_are_gate_conditions():
    inputs = list(_inputs())
    row = inputs[3]["cases"][0]
    row["source_judgment_calls"] = 2
    assert not _score(tuple(inputs))["component_passed"]
    row["source_judgment_calls"] = 1
    row["displayed"][0]["original_pdf_opened"] = False
    result = _score(tuple(inputs))
    assert result["display_integrity_failures"] == 1
    assert not result["component_passed"]


def test_freeze_and_runtime_identity_must_match():
    inputs = list(_inputs())
    inputs[2]["labels_sha256"] = "f" * 64
    with pytest.raises(gate.InvalidObservation, match="invalid_freeze_receipt"):
        _score(tuple(inputs))
    inputs = list(_inputs())
    inputs[3]["runtime_build_sha256"] = "f" * 64
    with pytest.raises(gate.InvalidObservation, match="measurement_not_frozen"):
        _score(tuple(inputs))


def test_external_review_key_and_signature_are_required():
    inputs = _inputs()
    with pytest.raises(gate.InvalidObservation, match="untrusted_review_signature"):
        gate.score(*inputs, roster_sha256=_digest(inputs[0]),
                   labels_sha256=_digest(inputs[1]),
                   trusted_review_key_sha256="b" * 64)
    inputs[2]["reviewer_signature_hex"] = "0" * 128
    with pytest.raises(gate.InvalidObservation, match="untrusted_review_signature"):
        _score(inputs)


def test_cli_default_is_preflight_only(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])
    assert gate.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "preflight_only"
    assert result["release_gate_passed"] is False


def test_cli_combines_only_exact_temp_artifacts(monkeypatch, capsys, tmp_path):
    exposed, holdout = _inputs(), _inputs("private_holdout")
    bridge_material = _bridge_material(holdout)
    args, _ = _release_cli_args(tmp_path, exposed, holdout, bridge_material)
    monkeypatch.setattr(sys, "argv", args)
    assert gate.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["display_quality_gate_passed"]
    assert result["gold_bridge_admitted"]
    assert not result["release_gate_passed"]


@pytest.mark.parametrize("name,duplicate_key", [
    ("roster", "schema"), ("labels", "schema"),
    ("receipt", "schema"), ("measurement", "schema"),
    ("holdout-roster", "schema"), ("holdout-labels", "schema"),
    ("holdout-receipt", "schema"), ("holdout-measurement", "schema"),
    ("holdout-stage1-gold", "schema"),
    ("holdout-authorized-pages", "document_id"),
    ("holdout-slates", "case_id"),
])
def test_cli_rejects_duplicate_keys_in_every_frozen_json_input(
    monkeypatch, capsys, tmp_path, name, duplicate_key
):
    exposed, holdout = _inputs(), _inputs("private_holdout")
    bridge_material = _bridge_material(holdout)
    args, files = _release_cli_args(tmp_path, exposed, holdout, bridge_material)
    path = files[name]
    original = path.read_bytes()
    if name in ("holdout-authorized-pages", "holdout-slates"):
        corrupted = original.replace(b"[{", f'[{{"{duplicate_key}":"duplicate",'.encode(), 1)
    else:
        corrupted = f'{{"{duplicate_key}":"duplicate",'.encode() + original[1:]
    path.write_bytes(corrupted)
    sha_option = f"--{name}-sha256"
    args[args.index(sha_option) + 1] = hashlib.sha256(corrupted).hexdigest()
    monkeypatch.setattr(sys, "argv", args)
    assert gate.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "invalid_observation"
    assert not result["release_gate_passed"]
