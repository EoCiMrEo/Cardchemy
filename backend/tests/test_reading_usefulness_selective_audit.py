"""Keyless synthetic contracts for the one-shot selective public audit."""
from __future__ import annotations

from argparse import Namespace
from collections import Counter
from io import StringIO
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import audit_reading_usefulness_selective as audit


FORMS = ("direct", "paraphrase", "follow-up")


def _group(number: int, split: str = "calibration") -> dict:
    useful = (number // 12) % 4
    return {"split": split, "question_form": FORMS[number % 3],
            "question": "When does the process begin?",
            "prior_question_context_if_followup": None,
            "source_document_sha256": "a" * 64,
            "four_exact_candidate_windows": [
                f"Process condition {index} is described here." for index in range(4)],
            "page_number_and_text_offsets_for_each_window": [
                {"page_number": index + 1} for index in range(4)],
            "original_page_usefulness_per_window": [index < useful for index in range(4)],
            "exact_cue_usefulness_per_window": [index < useful for index in range(4)],
            "independent_reviewer_ids_and_adjudication": [{"secret": "ignore"}] * 4,
            "id": f"hidden-{number}"}


def _row(number: int) -> dict:
    useful = (number // 12) % 4
    return {"null_score": 0.05 if useful == 0 else 0.95,
            "candidates": [
                {"index": index, "page": index + 1,
                 "source_document_sha256": "a" * 64,
                 "logit": 5.0 - index if index < useful else -5.0 - index,
                 "card_score": 0.95 - index * 0.01 if index < useful
                               else 0.05 - index * 0.01}
                for index in range(4)]}


def _perfect() -> tuple[list[dict], list[dict]]:
    return ([_group(number) for number in range(48)],
            [_row(number) for number in range(48)])


def test_two_distinct_train_only_logistic_fits_are_deterministic():
    null_rows = [[float(index % 2)] * len(audit.NULL_FEATURE_NAMES)
                 for index in range(96)]
    null_labels = [index % 2 == 1 for index in range(96)]
    card_rows = [[float(index % 2)] * len(audit.CARD_FEATURE_NAMES)
                 for index in range(384)]
    card_labels = [index % 2 == 1 for index in range(384)]
    null_model = audit.fit_classifier(null_rows, null_labels,
                                      audit.NULL_FEATURE_NAMES, 96, "null")
    card_model = audit.fit_classifier(card_rows, card_labels,
                                      audit.CARD_FEATURE_NAMES, 384, "card")
    assert null_model == audit.fit_classifier(null_rows, null_labels,
                                              audit.NULL_FEATURE_NAMES, 96, "null")
    assert null_model["kind"] == "null" and card_model["kind"] == "card"
    assert null_model["feature_names"] != card_model["feature_names"]
    assert audit.classifier_scores(null_model, null_rows[:2],
                                   audit.NULL_FEATURE_NAMES, "null")[0] < 0.5
    with pytest.raises(audit.AuditError, match="classifier_identity"):
        audit.classifier_scores(null_model, null_rows[:2],
                                audit.NULL_FEATURE_NAMES, "card")


def test_score_projection_ignores_labels_review_ids_and_strata():
    group = _group(12)

    class Previous:
        @staticmethod
        def pair_text(item, index):
            assert set(item) == {"question", "prior_question_context_if_followup",
                                 "four_exact_candidate_windows"}
            return item["question"], item["four_exact_candidate_windows"][index]

        @staticmethod
        def features(item, logits):
            assert set(item) == {"question", "prior_question_context_if_followup",
                                 "four_exact_candidate_windows"}
            return [[logit, 0.0, 1.0, 0.25, 0.1, 0.5, 1.0, 0.4]
                    for logit in logits]

    scorer = lambda pairs: [4.0 - index for index in range(len(pairs))]
    first = audit.score_only_pools([group], scorer, Previous)
    group["original_page_usefulness_per_window"] = [False] * 4
    group["exact_cue_usefulness_per_window"] = [False] * 4
    group["independent_reviewer_ids_and_adjudication"] = [{"secret": "changed"}] * 4
    group["question_form"] = "follow-up"
    group["id"] = "changed"
    second = audit.score_only_pools([group], scorer, Previous)
    assert first == second
    assert set(first[0]) == {"null_features", "card_features", "candidates"}
    assert not any("useful" in candidate for candidate in first[0]["candidates"])


def test_null_no_match_card_none_and_three_distinct_pages():
    row = _row(36)
    row["candidates"][1]["page"] = row["candidates"][0]["page"]
    assert audit.select(row, 0.96, 0.5) == ("no_match", [])
    assert audit.select(row, 0.9, 0.99) == ("null_positive_card_none", [])
    assert [candidate["index"] for candidate in audit.select(row, 0.95, 0.95)[1]] == [0]
    state, selected = audit.select(row, 0.9, 0.5)
    assert state == "qualified"
    assert [item["index"] for item in selected] == [0, 2]
    row["candidates"][1]["page"] = 2
    assert len(audit.select(row, 0.9, 0.0)[1]) == 3
    with pytest.raises(audit.AuditError, match="threshold_or_score_invalid"):
        audit.select({**row, "null_score": float("nan")}, 0.9, 0.5)
    row["candidates"][0]["card_score"] = float("nan")
    with pytest.raises(audit.AuditError, match="score_invalid"):
        audit.select(row, 0.96, 0.5)


def test_all_four_confusion_cells_and_effective_display_cap():
    counts = Counter()
    for predicted, actual in ((True, True), (True, False),
                              (False, True), (False, False)):
        audit._confusion(predicted, actual, counts)
    assert counts == {"tp": 1, "fp": 1, "fn": 1, "tn": 1}
    group = _group(36)
    row = _row(36)
    row["candidates"][3]["card_score"] = 0.9
    metrics = audit.summarize([group], [row], 0.9, 0.0)
    assert metrics["card_confusion"]["fp"] == 1
    assert metrics["effective_card_confusion"]["fp"] == 0
    row["candidates"][1]["page"] = row["candidates"][0]["page"]
    metrics = audit.summarize([group], [row], 0.9, 0.0)
    assert metrics["effective_card_confusion"]["tp"] == 2


def test_fixed_threshold_grid_chooses_one_pair_and_exact_old_gate():
    groups, rows = _perfect()
    null_threshold, card_threshold, metrics, attempts = audit.choose_thresholds(groups, rows)
    assert 0.05 < null_threshold < 0.95
    assert 0.05 < card_threshold < 0.93
    assert attempts > 0
    assert metrics["displayed_useful_cards"] == 72
    assert metrics["displayed_cards"] == 72
    assert metrics["positive_hit_at_three"] == 36
    assert metrics["no_useful_displayed"] == 0
    assert metrics["null_confusion"] == {"tp": 36, "tn": 12, "fp": 0, "fn": 0}
    assert audit.heldout_passed(metrics)
    assert "group_id" not in json.dumps(metrics)


def test_positive_no_match_and_null_positive_without_card_are_distinct():
    group = _group(12)
    row = _row(12)
    no_match = audit.summarize([group], [row], 0.96, 0.5)
    assert no_match["positive_no_match_errors"] == 1
    assert no_match["outcome_states"] == {"no_match": 1}
    no_card = audit.summarize([group], [row], 0.9, 0.99)
    assert no_card["positive_no_qualified_card_errors"] == 1
    assert no_card["outcome_states"] == {"null_positive_card_none": 1}


def test_calibration_rejects_inseparable_null_and_card_scores():
    groups, rows = _perfect()
    for row in rows:
        row["null_score"] = 0.5
        for candidate in row["candidates"]:
            candidate["card_score"] = 0.5
    with pytest.raises(audit.AuditError, match="calibration_gate_rejected"):
        audit.choose_thresholds(groups, rows)


@pytest.mark.parametrize("field,value", [
    ("positive_hit_at_three", 32), ("useful_first", 30),
    ("displayed_useful_cards", 59), ("no_useful_displayed", 1),
])
def test_every_primary_heldout_gate_remains_required(field, value):
    groups, rows = _perfect()
    metrics = audit.summarize(groups, rows, 0.5, 0.5)
    assert audit.heldout_passed(metrics)
    metrics[field] = value
    assert not audit.heldout_passed(metrics)


def test_form_count_strata_and_nonvacuous_precision_gates():
    groups, rows = _perfect()
    metrics = audit.summarize(groups, rows, 0.5, 0.5)
    metrics["form"]["direct"]["positive_hit_at_three"] = 9
    assert not audit.heldout_passed(metrics)
    metrics = audit.summarize(groups, rows, 0.5, 0.5)
    metrics["count_strata"]["2"]["exact_count"] = 9
    assert not audit.heldout_passed(metrics)
    metrics = audit.summarize(groups, rows, 0.5, 0.5)
    metrics["displayed_cards"] = 0
    assert not audit.calibration_passed(metrics)
    assert not audit.heldout_passed(metrics)


def test_helper_manifest_hash_checked_before_import(tmp_path, monkeypatch):
    manifest = {"schema": audit.RUNTIME_SCHEMA,
                "helper_sha256": {name: "0" * 64 for name in audit.HELPER_NAMES}}
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    imports = []
    monkeypatch.setattr(audit.importlib, "import_module", lambda name: imports.append(name))
    with pytest.raises(audit.AuditError, match="helper_hash_mismatch"):
        audit.load_helpers(path)
    assert imports == []


def test_missing_external_freeze_pin_stops_before_scoring(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(audit, "supervise", lambda args: calls.append(args))
    argv = ["--corpus", "unused", "--fixture", "unused", "--bundle", "unused",
            "--runtime-manifest", "unused", "--freeze-receipt", "unused",
            "--expected-freeze-sha256", "bad-pin", "--output", "unused",
            "--execute-approved"]
    assert audit.main(argv) == 1
    assert calls == []
    assert json.loads(capsys.readouterr().out)["candidate_passed"] is False


def test_default_preflight_is_no_score_even_with_valid_freeze(monkeypatch, capsys):
    monkeypatch.setattr(audit, "verify_frozen", lambda args: {"freeze_sha256": "a" * 64})
    monkeypatch.setattr(audit, "supervise", lambda args: pytest.fail("must not score"))
    argv = ["--corpus", "unused", "--fixture", "unused", "--bundle", "unused",
            "--runtime-manifest", "unused", "--freeze-receipt", "unused",
            "--expected-freeze-sha256", "a" * 64]
    assert audit.main(argv) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "frozen_preflight_no_scoring"
    assert result["model_inferences"] == 0


def test_calibration_rejection_never_scores_heldout_and_consumes_child_claim(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(audit, "require_bounded_container", lambda: None)
    monkeypatch.setattr(audit, "require_approved_ledger", lambda: None)
    monkeypatch.setattr(audit, "APPROVED_LEDGER_ROOT", tmp_path)
    groups = ([_group(index, "train") for index in range(96)] +
              [_group(index, "calibration") for index in range(48)] +
              [_group(index, "heldout") for index in range(48)])
    validator = SimpleNamespace(read_json=lambda path, limit: ({"groups": groups}, b""),
                                MAX_FIXTURE_BYTES=4 * 1024 * 1024)
    prior = SimpleNamespace(peak_rss=lambda: 100,
                            _model_scorer=lambda bundle, start, baseline: (
                                lambda pairs: [0.0] * len(pairs),
                                lambda: {"resource_passed": True}, 0.01))
    monkeypatch.setattr(audit, "verify_frozen", lambda args: {"freeze_sha256": "a" * 64})
    monkeypatch.setattr(audit, "load_helpers", lambda path: (validator, None, prior))
    seen = []
    monkeypatch.setattr(audit, "score_only_pools", lambda split, scorer, previous:
                        seen.append(split[0]["split"]) or
                        [{"null_features": [0.0] * len(audit.NULL_FEATURE_NAMES),
                          "card_features": [[0.0] * len(audit.CARD_FEATURE_NAMES)] * 4}
                         for _ in split])
    monkeypatch.setattr(audit, "fit_classifier", lambda *args: {"kind": args[-1]})
    monkeypatch.setattr(audit, "qualify_pools", lambda pools, null, card: _perfect()[1])
    monkeypatch.setattr(audit, "choose_thresholds", lambda groups, rows:
                        (_ for _ in ()).throw(audit.AuditError("calibration_gate_rejected")))
    output = tmp_path / "output"
    output.mkdir()
    args = Namespace(corpus=tmp_path, fixture=tmp_path / "fixture.json",
                     bundle=tmp_path, runtime_manifest=tmp_path / "runtime.json",
                     freeze_receipt=tmp_path / "freeze.json",
                     expected_freeze_sha256="a" * 64, output=output)
    audit.write_exclusive(audit.attempt_marker_path(), {
        "procedure": audit.PROCEDURE, "freeze_sha256": "a" * 64,
        "harness_sha256": audit.digest(Path(audit.__file__)), "one_shot_attempt": True})
    audit.run_child(args)
    assert seen == ["train", "calibration"]
    assert audit.child_claim_path().is_file()
    result = json.loads((output / "audit-result.json").read_text(encoding="utf-8"))
    assert result["status"] == "calibration_rejected_no_heldout"
    assert result["heldout_scored"] is False
    assert "displayed_cards" not in result["calibration"]
    assert not (output / "calibration-rule.json").exists()
    with pytest.raises(FileExistsError):
        audit.run_child(args)


def test_other_receipt_name_cannot_bypass_fixed_attempt_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "require_bounded_container", lambda: None)
    monkeypatch.setattr(audit, "require_approved_ledger", lambda: None)
    monkeypatch.setattr(audit, "APPROVED_LEDGER_ROOT", tmp_path)
    audit.write_exclusive(audit.attempt_marker_path(), {
        "procedure": audit.PROCEDURE, "freeze_sha256": "a" * 64,
        "harness_sha256": audit.digest(Path(audit.__file__)), "one_shot_attempt": True})
    args = Namespace(audit_start=audit.perf_counter(),
                     expected_freeze_sha256="a" * 64,
                     harness_sha256=audit.digest(Path(audit.__file__)),
                     freeze_receipt=tmp_path / "new-freeze-name.json",
                     output=tmp_path / "new-output")
    with pytest.raises(audit.AuditError, match="audit_attempt_consumed"):
        audit.supervise(args)
    assert not args.output.exists()


@pytest.mark.parametrize("result_status,rule_event,expected_status,heldout", [
    ("public_passed", False, "protocol_invalid", False),
    ("calibration_rejected_no_heldout", True, "protocol_invalid",
     "unknown_after_calibration"),
    ("calibration_rejected_no_heldout", False,
     "calibration_rejected_no_heldout", False),
])
def test_supervisor_enforces_rule_event_before_heldout_result(
    tmp_path, monkeypatch, result_status, rule_event, expected_status, heldout,
):
    monkeypatch.setattr(audit, "require_bounded_container", lambda: None)
    monkeypatch.setattr(audit, "require_approved_ledger", lambda: None)
    monkeypatch.setattr(audit, "APPROVED_LEDGER_ROOT", tmp_path)
    monkeypatch.setattr(audit, "verify_frozen", lambda args: {"freeze_sha256": "a" * 64})
    fixture = tmp_path / "fixture.json"
    fixture.write_text("{}", encoding="utf-8")
    runtime = tmp_path / "runtime.json"
    runtime.write_text("{}", encoding="utf-8")
    result_body = {"status": result_status,
                   "candidate_passed": result_status == "public_passed",
                   "heldout_scored": result_status == "public_passed",
                   "release_gate_passed": False,
                   "provider_requests": 0, "database_writes": 0}
    args = Namespace(audit_start=audit.perf_counter(), corpus=tmp_path,
                     fixture=fixture, bundle=tmp_path, runtime_manifest=runtime,
                     freeze_receipt=tmp_path / "freeze.json",
                     expected_freeze_sha256="a" * 64, output=tmp_path / "output",
                     harness_sha256=audit.digest(Path(audit.__file__)),
                     fixture_sha256=audit.digest(fixture),
                     runtime_sha256=audit.digest(runtime))

    class FakeProcess:
        returncode = 0

        def __init__(self, *_args, **_kwargs):
            messages = [{"event": "preflight_ready"}, {"event": "startup_ready"}]
            if rule_event:
                rule_hash = audit.write_exclusive(args.output / "calibration-rule.json",
                                                  {"synthetic": True})
                messages.append({"event": "calibration_frozen", "rule_sha256": rule_hash})
            messages.append({"event": "result", "result": result_body})
            if expected_status == result_status:
                audit.write_exclusive(args.output / "audit-result.json", result_body)
            self.stdout = StringIO("".join(json.dumps(message) + "\n"
                                    for message in messages))

        def poll(self):
            return 0

    monkeypatch.setattr(audit.subprocess, "Popen", FakeProcess)
    result = audit.supervise(args)
    assert result["status"] == expected_status
    assert result["heldout_scored"] == heldout


@pytest.mark.parametrize("cpu,memory,accepted", [
    ("400000 100000", "2147483648", True),
    ("500000 100000", "2147483648", False),
    ("400000 100000", "3221225472", False),
    ("max 100000", "2147483648", False),
])
def test_bounded_container_requires_network_cpu_and_ram(monkeypatch, cpu, memory, accepted):
    original_is_dir = Path.is_dir
    original_iterdir = Path.iterdir
    original_read = Path.read_text
    monkeypatch.setattr(audit.os, "name", "posix")
    monkeypatch.setattr(Path, "is_dir", lambda path: True if str(path) == "/sys/class/net"
                        else original_is_dir(path))
    monkeypatch.setattr(Path, "iterdir", lambda path: iter([Path("/sys/class/net/lo")])
                        if str(path) == "/sys/class/net" else original_iterdir(path))

    def read(path, *args, **kwargs):
        if str(path) == "/sys/fs/cgroup/cpu.max":
            return cpu
        if str(path) == "/sys/fs/cgroup/memory.max":
            return memory
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    if accepted:
        audit.require_bounded_container()
    else:
        with pytest.raises(audit.AuditError, match="container_resource_limits_required"):
            audit.require_bounded_container()
