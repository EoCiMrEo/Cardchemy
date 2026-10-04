"""Keyless synthetic contracts for the distinct one-shot groupwise public audit."""
from __future__ import annotations

from argparse import Namespace
from io import StringIO
import json
from pathlib import Path
import random
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import audit_reading_usefulness_groupwise as audit


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
    probabilities = [0.001] * 4
    probabilities[useful] = 0.997
    return {"count_scores": probabilities,
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


def test_fixed_train_only_card_and_count_heads_are_deterministic_and_finite():
    count_rows = [[float((number // 24) % 4)] +
                  [float(number % 3) * 0.1] * (len(audit.COUNT_FEATURE_NAMES) - 1)
                  for number in range(96)]
    count_labels = [(number // 24) % 4 for number in range(96)]
    count_model = audit.fit_count_head(count_rows, count_labels)
    assert count_model == audit.fit_count_head(count_rows, count_labels)
    probabilities = audit.score_counts(count_model, count_rows[:4])
    assert len(probabilities) == 4
    assert all(abs(sum(row) - 1.0) < 1e-12 and all(0 <= value <= 1 for value in row)
               for row in probabilities)

    card_rows = [[float(number % 2)] * len(audit.CARD_FEATURE_NAMES)
                 for number in range(384)]
    card_labels = [number % 2 == 1 for number in range(384)]
    card_model = audit.fit_card_head(card_rows, card_labels)
    assert card_model == audit.fit_card_head(card_rows, card_labels)
    assert audit.score_cards(card_model, card_rows[:2])[0] < 0.5
    assert audit.score_cards(card_model, [card_rows[3], card_rows[0]]) == pytest.approx([
        audit.score_cards(card_model, card_rows[:4])[3],
        audit.score_cards(card_model, card_rows[:4])[0]])
    with pytest.raises(audit.AuditError, match="count_head_identity"):
        audit.score_counts(card_model, count_rows[:2])
    with pytest.raises(audit.AuditError, match="classifier_identity"):
        audit.score_cards(count_model, card_rows[:2])


def test_count_train_labels_require_balanced_public_strata():
    rows = [[0.0] * len(audit.COUNT_FEATURE_NAMES) for _ in range(96)]
    with pytest.raises(audit.AuditError, match="training_count_labels"):
        audit.fit_count_head(rows, [0] * 96)
    with pytest.raises(audit.AuditError, match="training_features"):
        audit.fit_count_head([[float("nan")] + row[1:] for row in rows],
                             [number // 24 for number in range(96)])


@pytest.mark.parametrize("pattern", ("random", "duplicate", "separable", "constant"))
def test_count_head_solver_stress_on_finite_synthetic_features(pattern):
    rng = random.Random(14927)
    dimension = len(audit.COUNT_FEATURE_NAMES)
    labels = [number // 24 for number in range(96)]
    rng.shuffle(labels)
    rows = []
    for label in labels:
        if pattern == "random":
            rows.append([rng.gauss(0.0, 1.0) for _ in range(dimension)])
        elif pattern == "duplicate":
            value = rng.gauss(0.0, 1.0)
            rows.append([value] * dimension)
        elif pattern == "separable":
            rows.append([label * 100.0 + rng.gauss(0.0, 0.01)] +
                        [rng.gauss(0.0, 1.0) for _ in range(dimension - 1)])
        else:
            rows.append([0.0] * dimension)
    model = audit.fit_count_head(rows, labels)
    scored = audit.score_counts(model, rows)
    assert len(scored) == 96
    assert all(abs(sum(row) - 1.0) < 1e-12 for row in scored)


def test_group_features_permutation_invariant_and_card_head_shared():
    logits = [4.0, 4.0, -2.0, 1.0]
    card_rows = [[logit, logit - 4.0, 0.0, lexical, title, condition, 1.0, 0.2]
                 for logit, lexical, title, condition in zip(
                     logits, (0.1, 0.8, 0.2, 0.3),
                     (0.2, 0.7, 0.1, 0.4), (0.3, 0.9, 0.4, 0.2))]
    original = audit.count_features(audit.null_features(logits, card_rows))
    permutation = (2, 0, 3, 1)
    reordered = audit.count_features(audit.null_features(
        [logits[index] for index in permutation],
        [card_rows[index] for index in permutation]))
    assert original == reordered
    assert len(audit.card_features(card_rows[0])) == len(audit.CARD_FEATURE_NAMES)


def test_score_projection_ignores_labels_split_review_ids_and_candidate_order():
    groups = [_group(number) for number in range(48)]

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

    scorer = lambda pairs: [4.0 - index % 4 for index in range(len(pairs))]
    first = audit.score_only_pools(groups, scorer, Previous, "train_cal", {})
    for group in groups:
        group["original_page_usefulness_per_window"] = [False] * 4
        group["exact_cue_usefulness_per_window"] = [False] * 4
        group["independent_reviewer_ids_and_adjudication"] = [{"changed": True}] * 4
        group["question_form"] = "follow-up"
        group["id"] = "changed"
        group["split"] = "heldout"
    second = audit.score_only_pools(groups, scorer, Previous, "heldout", {})
    assert first == second
    assert set(first[0]) == {"count_features", "card_features", "candidates"}
    assert not any("useful" in candidate for candidate in first[0]["candidates"])


def test_model_call_budget_is_enforced_before_each_local_call():
    groups = [_group(number) for number in range(96)]

    class Previous:
        @staticmethod
        def pair_text(group, index):
            return group["question"], group["four_exact_candidate_windows"][index]

        @staticmethod
        def features(_group, logits):
            return [[logit, 0, 0, 0, 0, 0, 0, 0] for logit in logits]

    observed: list[int] = []

    def scorer(pairs):
        observed.append(len(pairs))
        return [float(index) for index in range(len(pairs))]

    calls: dict[str, int] = {"train_cal": 0, "heldout": 0}
    audit.score_only_pools(groups, scorer, Previous, "train_cal", calls)
    audit.score_only_pools(groups[:48], scorer, Previous, "train_cal", calls)
    assert calls == {"train_cal": 20, "heldout": 0}
    assert len(observed) == 20 and max(observed) == 30
    with pytest.raises(audit.AuditError, match="model_call_budget"):
        audit.score_only_pools(groups[:48], scorer, Previous, "train_cal", calls)
    assert len(observed) == 20
    # Distinct stage never shares a partial train/calibration batch.
    calls = {"train_cal": 20, "heldout": 0}
    audit.score_only_pools(groups[:48], scorer, Previous, "heldout", calls)
    assert calls == {"train_cal": 20, "heldout": 7}
    assert len(observed) == 27
    with pytest.raises(audit.AuditError, match="model_call_budget"):
        audit.score_only_pools(groups[:48], scorer, Previous, "heldout", calls)
    assert len(observed) == 27


def test_count_is_only_a_cap_and_never_adds_weak_filler():
    row = _row(36)
    row["count_scores"] = [0.01, 0.02, 0.03, 0.94]
    row["candidates"][0]["card_score"] = 0.95
    for candidate in row["candidates"][1:]:
        candidate["card_score"] = 0.49
    assert [candidate["index"] for candidate in audit.select(row, 0.0)[1]] == [0]
    row["candidates"][1]["card_score"] = 0.8
    row["candidates"][1]["page"] = row["candidates"][0]["page"]
    assert [candidate["index"] for candidate in audit.select(row, 0.0)[1]] == [0]
    row["count_scores"] = [0.99, 0.003, 0.003, 0.004]
    assert audit.select(row, 0.0) == ("no_match", [])
    row["candidates"][2]["card_score"] = float("nan")
    with pytest.raises(audit.AuditError, match="score_invalid"):
        audit.select(row, 0.0)


def test_perfect_calibration_and_heldout_gate_with_page_and_cue_metrics():
    groups, rows = _perfect()
    risk, metrics, frontier = audit.choose_risk(groups, rows)
    assert risk is not None and metrics is not None and frontier
    assert audit.calibration_passed(metrics)
    assert audit.heldout_passed(metrics)
    assert metrics["positive_hit_at_three"] == 36
    assert metrics["displayed_useful_cards"] == 72
    assert metrics["displayed_original_page_useful"] == 72
    assert metrics["displayed_exact_cue_useful"] == 72
    assert metrics["no_useful_displayed"] == 0
    assert metrics["count_predictions"] == {"0": 12, "1": 12, "2": 12, "3": 12}


def test_weak_no_match_cards_fail_calibration_and_frontier_has_aggregates_only():
    groups, rows = _perfect()
    for number in range(12):
        rows[number]["count_scores"] = [0.01, 0.97, 0.01, 0.01]
        rows[number]["candidates"][0]["card_score"] = 0.99
    risk, metrics, frontier = audit.choose_risk(groups, rows)
    assert risk is None and metrics is None and frontier
    assert all(set(entry) == {"risk", "no_useful_displayed", "displayed_cards",
                              "displayed_useful_cards", "displayed_precision",
                              "positive_hit_at_three"} for entry in frontier)
    assert not any("question" in str(entry) or "source_document" in str(entry)
                   for entry in frontier)


@pytest.mark.parametrize("field,value", [
    ("positive_hit_at_three", 32), ("useful_first", 30),
    ("displayed_useful_cards", 59), ("no_useful_displayed", 1),
])
def test_every_primary_heldout_gate_remains_required(field, value):
    groups, rows = _perfect()
    metrics = audit.summarize(groups, rows, 0.0)
    assert audit.heldout_passed(metrics)
    metrics[field] = value
    assert not audit.heldout_passed(metrics)


def test_form_count_strata_and_nonvacuous_precision_gates():
    groups, rows = _perfect()
    metrics = audit.summarize(groups, rows, 0.0)
    metrics["form"]["direct"]["positive_hit_at_three"] = 9
    assert not audit.heldout_passed(metrics)
    metrics = audit.summarize(groups, rows, 0.0)
    metrics["count_strata"]["2"]["exact_count"] = 9
    assert not audit.heldout_passed(metrics)
    metrics = audit.summarize(groups, rows, 0.0)
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


def test_calibration_failure_does_not_score_or_use_heldout(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "require_bounded_container", lambda: None)
    monkeypatch.setattr(audit, "require_approved_ledger", lambda: None)
    monkeypatch.setattr(audit, "APPROVED_LEDGER_ROOT", tmp_path)
    monkeypatch.setattr(audit, "verify_frozen", lambda args: {"freeze_sha256": "a" * 64})
    groups = ([_group(number, "train") for number in range(96)] +
              [_group(number, "calibration") for number in range(48)] +
              [_group(number, "heldout") for number in range(48)])
    for group in groups[144:]:
        group["original_page_usefulness_per_window"] = [object()] * 4
        group["exact_cue_usefulness_per_window"] = [object()] * 4
    validator = SimpleNamespace(MAX_FIXTURE_BYTES=100, read_json=lambda *_: ({"groups": groups}, b""))
    previous = SimpleNamespace(peak_rss=lambda: 0,
                               _model_scorer=lambda *_: (
                                   lambda pairs: [0.0] * len(pairs),
                                   lambda: {"resource_passed": True,
                                            "model_run_calls": 20, "pairs_scored": 576}, 0.1))
    monkeypatch.setattr(audit, "load_helpers", lambda *_: (validator, None, previous))
    seen: list[str] = []

    def fake_score(group_rows, _scorer, _previous, stage, calls):
        seen.append(stage)
        assert stage == "train_cal"
        calls[stage] += 13 if len(group_rows) == 96 else 7
        return [{"count_features": [0.0] * len(audit.COUNT_FEATURE_NAMES),
                 "card_features": [[0.0] * len(audit.CARD_FEATURE_NAMES)] * 4}
                for _ in group_rows]

    monkeypatch.setattr(audit, "score_only_pools", fake_score)
    monkeypatch.setattr(audit, "fit_count_head", lambda *_: {"count": True})
    monkeypatch.setattr(audit, "fit_card_head", lambda *_: {"card": True})
    monkeypatch.setattr(audit, "qualify_pools", lambda pools, *_: [_row(index)
                                                               for index in range(len(pools))])
    monkeypatch.setattr(audit, "choose_risk", lambda *_: (None, None, [{"risk": 0.0}]))
    monkeypatch.setattr(audit, "_emit", lambda *_: None)
    output = tmp_path / "output"
    output.mkdir()
    fixture = tmp_path / "fixture.json"
    fixture.write_text("{}", encoding="utf-8")
    args = Namespace(output=output, fixture=fixture, bundle=tmp_path,
                     runtime_manifest=tmp_path / "runtime.json",
                     expected_freeze_sha256="a" * 64)
    audit.write_exclusive(audit.attempt_marker_path(), {
        "procedure": audit.PROCEDURE, "freeze_sha256": "a" * 64,
        "harness_sha256": audit.digest(Path(audit.__file__)), "one_shot_attempt": True})
    audit.run_child(args)
    result = json.loads((output / "audit-result.json").read_text(encoding="utf-8"))
    assert seen == ["train_cal", "train_cal"]
    assert result["status"] == "calibration_rejected_no_heldout"
    assert result["heldout_scored"] is False and result["candidate_passed"] is False
    assert result["release_gate_passed"] is False
    assert not (output / "calibration-rule.json").exists()
    with pytest.raises(FileExistsError):
        audit.run_child(args)


def test_calibration_rule_frozen_before_one_heldout_stage_with_27_call_receipt(
    tmp_path, monkeypatch,
):
    """Fake public scores exercise the whole successful child wiring, no ONNX."""
    monkeypatch.setattr(audit, "require_bounded_container", lambda: None)
    monkeypatch.setattr(audit, "require_approved_ledger", lambda: None)
    monkeypatch.setattr(audit, "APPROVED_LEDGER_ROOT", tmp_path)
    monkeypatch.setattr(audit, "verify_frozen", lambda args: {"freeze_sha256": "a" * 64})
    groups = ([_group(number, "train") for number in range(96)] +
              [_group(number, "calibration") for number in range(48)] +
              [_group(number, "heldout") for number in range(48)])
    validator = SimpleNamespace(MAX_FIXTURE_BYTES=100, read_json=lambda *_: ({"groups": groups}, b""))
    observed_calls = {"train_cal": 0, "heldout": 0}
    observed_pairs = 0
    events = []

    def fake_score(group_rows, _scorer, _previous, stage, calls):
        nonlocal observed_pairs
        if stage == "heldout":
            assert (output / "calibration-rule.json").is_file()
            assert any(event.get("event") == "calibration_frozen" for event in events)
        stage_calls = 13 if len(group_rows) == 96 else 7
        calls[stage] += stage_calls
        observed_calls[stage] += stage_calls
        observed_pairs += len(group_rows) * 4
        return [{"count_features": [0.0] * len(audit.COUNT_FEATURE_NAMES),
                 "card_features": [[0.0] * len(audit.CARD_FEATURE_NAMES)] * 4}
                for _ in group_rows]

    def resources():
        return {"resource_passed": True,
                "model_run_calls": sum(observed_calls.values()),
                "pairs_scored": observed_pairs}

    previous = SimpleNamespace(peak_rss=lambda: 0,
                               _model_scorer=lambda *_: (
                                   lambda pairs: [0.0] * len(pairs), resources, 0.1))
    monkeypatch.setattr(audit, "load_helpers", lambda *_: (validator, None, previous))
    monkeypatch.setattr(audit, "score_only_pools", fake_score)
    monkeypatch.setattr(audit, "fit_count_head", lambda *_: {"count": True})
    monkeypatch.setattr(audit, "fit_card_head", lambda *_: {"card": True})
    monkeypatch.setattr(audit, "qualify_pools", lambda pools, *_: [_row(index)
                                                               for index in range(len(pools))])
    monkeypatch.setattr(audit, "_emit", lambda event: events.append(event))
    output = tmp_path / "output"
    output.mkdir()
    fixture = tmp_path / "fixture.json"
    fixture.write_text("{}", encoding="utf-8")
    args = Namespace(output=output, fixture=fixture, bundle=tmp_path,
                     runtime_manifest=tmp_path / "runtime.json",
                     expected_freeze_sha256="a" * 64)
    audit.write_exclusive(audit.attempt_marker_path(), {
        "procedure": audit.PROCEDURE, "freeze_sha256": "a" * 64,
        "harness_sha256": audit.digest(Path(audit.__file__)), "one_shot_attempt": True})
    audit.run_child(args)
    assert [event["event"] for event in events] == [
        "preflight_ready", "startup_ready", "calibration_frozen", "result"]
    assert observed_calls == {"train_cal": 20, "heldout": 7}
    assert observed_pairs == 768
    rule = json.loads((output / "calibration-rule.json").read_text(encoding="utf-8"))
    result = json.loads((output / "audit-result.json").read_text(encoding="utf-8"))
    assert rule["heldout_scored"] is False and rule["set_risk"] in audit.SET_RISK_GRID
    assert result["status"] == "public_passed" and result["candidate_passed"] is True
    assert result["heldout_scored"] is True and result["release_gate_passed"] is False
    assert result["resources"]["model_run_calls"] == 27
    assert result["resources"]["pairs_scored"] == 768
    assert result["rule_sha256"] == audit.digest(output / "calibration-rule.json")


def test_fixed_exclusive_ledger_cannot_be_bypassed_by_new_receipt_path(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "require_bounded_container", lambda: None)
    monkeypatch.setattr(audit, "require_approved_ledger", lambda: None)
    monkeypatch.setattr(audit, "APPROVED_LEDGER_ROOT", tmp_path)
    audit.write_exclusive(audit.attempt_marker_path(), {
        "procedure": audit.PROCEDURE, "freeze_sha256": "a" * 64,
        "harness_sha256": audit.digest(Path(audit.__file__)), "one_shot_attempt": True})
    args = Namespace(audit_start=audit.perf_counter(),
                     expected_freeze_sha256="a" * 64,
                     harness_sha256=audit.digest(Path(audit.__file__)),
                     freeze_receipt=tmp_path / "new-freeze.json",
                     output=tmp_path / "new-output")
    with pytest.raises(audit.AuditError, match="audit_attempt_consumed"):
        audit.supervise(args)
    assert not args.output.exists()


@pytest.mark.parametrize("calls,pairs,expected", [
    (20, 576, "calibration_rejected_no_heldout"),
    (19, 576, "protocol_invalid"),
    (27, 768, "protocol_invalid"),
])
def test_supervisor_rejects_invalid_stage_model_call_receipt(
    tmp_path, monkeypatch, calls, pairs, expected,
):
    monkeypatch.setattr(audit, "require_bounded_container", lambda: None)
    monkeypatch.setattr(audit, "require_approved_ledger", lambda: None)
    monkeypatch.setattr(audit, "APPROVED_LEDGER_ROOT", tmp_path)
    monkeypatch.setattr(audit, "verify_frozen", lambda args: {"freeze_sha256": "a" * 64})
    fixture = tmp_path / "fixture.json"
    fixture.write_text("{}", encoding="utf-8")
    runtime = tmp_path / "runtime.json"
    runtime.write_text("{}", encoding="utf-8")
    result_body = {"status": "calibration_rejected_no_heldout",
                   "candidate_passed": False, "heldout_scored": False,
                   "release_gate_passed": False, "provider_requests": 0,
                   "database_writes": 0,
                   "resources": {"model_run_calls": calls, "pairs_scored": pairs}}
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
            messages = [{"event": "preflight_ready"}, {"event": "startup_ready"},
                        {"event": "result", "result": result_body}]
            if expected == "calibration_rejected_no_heldout":
                audit.write_exclusive(args.output / "audit-result.json", result_body)
            self.stdout = StringIO("".join(json.dumps(message) + "\n"
                                    for message in messages))

        def poll(self):
            return 0

    monkeypatch.setattr(audit.subprocess, "Popen", FakeProcess)
    result = audit.supervise(args)
    assert result["status"] == expected
    assert result["candidate_passed"] is False


@pytest.mark.parametrize("status,rule_event,expected,heldout", [
    ("public_quality_rejected", False, "protocol_invalid", False),
    ("public_quality_rejected", True, "public_quality_rejected", True),
    ("public_passed", True, "public_passed", True),
    ("calibration_rejected_no_heldout", True, "protocol_invalid",
     "unknown_after_calibration"),
])
def test_supervisor_requires_frozen_rule_before_heldout_result(
    tmp_path, monkeypatch, status, rule_event, expected, heldout,
):
    monkeypatch.setattr(audit, "require_bounded_container", lambda: None)
    monkeypatch.setattr(audit, "require_approved_ledger", lambda: None)
    monkeypatch.setattr(audit, "APPROVED_LEDGER_ROOT", tmp_path)
    monkeypatch.setattr(audit, "verify_frozen", lambda args: {"freeze_sha256": "a" * 64})
    fixture = tmp_path / "fixture.json"
    fixture.write_text("{}", encoding="utf-8")
    runtime = tmp_path / "runtime.json"
    runtime.write_text("{}", encoding="utf-8")
    resources = ({"model_run_calls": 20, "pairs_scored": 576} if
                 status == "calibration_rejected_no_heldout" else
                 {"model_run_calls": 27, "pairs_scored": 768,
                  "resource_passed": True})
    result_body = {"status": status, "candidate_passed": status == "public_passed",
                   "heldout_scored": status != "calibration_rejected_no_heldout",
                   "release_gate_passed": False, "provider_requests": 0,
                   "database_writes": 0, "resources": resources}
    if status == "public_passed":
        groups, rows = _perfect()
        result_body["heldout"] = audit.summarize(groups, rows, 0.0)
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
                result_body["rule_sha256"] = rule_hash
                messages.append({"event": "calibration_frozen", "rule_sha256": rule_hash})
            messages.append({"event": "result", "result": result_body})
            if expected == status:
                audit.write_exclusive(args.output / "audit-result.json", result_body)
            self.stdout = StringIO("".join(json.dumps(message) + "\n"
                                    for message in messages))

        def poll(self):
            return 0

    monkeypatch.setattr(audit.subprocess, "Popen", FakeProcess)
    result = audit.supervise(args)
    assert result["status"] == expected
    assert result["heldout_scored"] == heldout
    assert result["candidate_passed"] is (expected == "public_passed")


@pytest.mark.parametrize("cpu,memory,swap,uid,readonly,accepted", [
    ("400000 100000", "2147483648", "0", 1000, True, True),
    ("500000 100000", "2147483648", "0", 1000, True, False),
    ("400000 100000", "3221225472", "0", 1000, True, False),
    ("400000 100000", "2147483648", "1", 1000, True, False),
    ("400000 100000", "2147483648", "0", 0, True, False),
    ("400000 100000", "2147483648", "0", 1000, False, False),
    ("max 100000", "2147483648", "0", 1000, True, False),
])
def test_bounded_container_requires_network_cpu_ram_swap_nonroot_readonly(
    monkeypatch, cpu, memory, swap, uid, readonly, accepted,
):
    original_is_dir = Path.is_dir
    original_iterdir = Path.iterdir
    original_read = Path.read_text
    monkeypatch.setattr(audit.os, "name", "posix")
    monkeypatch.setattr(audit.os, "getuid", lambda: uid, raising=False)
    monkeypatch.setattr(audit.os, "geteuid", lambda: uid, raising=False)
    monkeypatch.setattr(audit.os, "ST_RDONLY", 1, raising=False)
    monkeypatch.setattr(audit.os, "statvfs",
                        lambda _: SimpleNamespace(f_flag=1 if readonly else 0),
                        raising=False)
    monkeypatch.setattr(Path, "is_dir", lambda path: True if str(path) == "/sys/class/net"
                        else original_is_dir(path))
    monkeypatch.setattr(Path, "iterdir", lambda path: iter([Path("/sys/class/net/lo")])
                        if str(path) == "/sys/class/net" else original_iterdir(path))

    def read(path, *args, **kwargs):
        if str(path) == "/sys/fs/cgroup/cpu.max":
            return cpu
        if str(path) == "/sys/fs/cgroup/memory.max":
            return memory
        if str(path) == "/sys/fs/cgroup/memory.swap.max":
            return swap
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    if accepted:
        audit.require_bounded_container()
    else:
        with pytest.raises(audit.AuditError, match="container_resource_limits_required"):
            audit.require_bounded_container()
