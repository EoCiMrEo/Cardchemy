"""Synthetic, keyless contracts for the frozen public reading-usefulness audit."""
from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path
import sys
from time import perf_counter
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import audit_reading_usefulness as audit


FORMS = ("direct", "paraphrase", "follow-up")


def _row(number: int, available: int) -> dict:
    candidates = []
    for index in range(4):
        useful = index < available
        candidates.append({"index": index, "page": index + 1,
                           "source_document_sha256": "a" * 64,
                           "page_useful": useful, "cue_useful": useful,
                           "useful": useful,
                           "score": 0.95 - index * 0.01 if useful else 0.05 - index * 0.01,
                           "logit": 5.0 - index if useful else -5.0 - index})
    return {"id": f"g{number}", "form": FORMS[number % 3],
            "relation": "definition", "candidates": candidates}


def _perfect_rows() -> list[dict]:
    # Four of each useful-count stratum in each form, giving 12 positive
    # direct, paraphrase and follow-up groups.
    return [_row(number, number // 12) for number in range(48)]


def _group(number: int, split: str) -> dict:
    return {"id": f"{split}-{number}", "split": split,
            "question": "What condition defines the process?",
            "prior_question_context_if_followup": None,
            "question_form": "direct", "relation_family": "definition",
            "source_document_sha256": "a" * 64,
            "four_exact_candidate_windows": [
                f"Condition {index}: process is defined here." for index in range(4)],
            "page_number_and_text_offsets_for_each_window": [
                {"page_number": index + 1} for index in range(4)],
            "original_page_usefulness_per_window": [False] * 4,
            "exact_cue_usefulness_per_window": [False] * 4}


def test_fixed_features_include_only_displayed_cue_and_local_context():
    group = _group(0, "train")
    group["question"] = "When does the process begin?"
    group["four_exact_candidate_windows"][0] = "When active: process begins here."
    group["question_form"] = "follow-up"
    group["prior_question_context_if_followup"] = "What is the process?"
    first = audit.pair_text(group, 0)
    assert first == ("Previous question: What is the process?\n"
                     "Current question: When does the process begin?",
                     "When active: process begins here.")
    features = audit.features(group, [4.0, 3.0, 2.0, 1.0])
    assert len(features) == 4
    assert all(len(row) == len(audit.FEATURE_NAMES) for row in features)
    assert features[0][1] == 0.0
    assert features[1][1] == -1.0
    assert features[0][5] > 0.0
    assert features[0][7] <= 1.0


def test_train_only_logistic_fit_is_deterministic_and_finite():
    rows = []
    labels = []
    for index in range(384):
        positive = index % 4 == 0
        rows.append([2.0 if positive else -2.0, 0.0, 1.0,
                     float(positive), float(positive), 0.0, 1.0, 0.5])
        labels.append(positive)
    first = audit.fit_classifier(rows, labels)
    second = audit.fit_classifier(rows, labels)
    assert first == second
    scores = audit.classifier_scores(first, [rows[0], rows[1]])
    assert 0.0 < scores[1] < scores[0] < 1.0
    assert first["feature_names"] == list(audit.FEATURE_NAMES)


def test_calibration_chooses_one_threshold_and_never_fills():
    rows = _perfect_rows()
    threshold, metrics = audit.choose_threshold(rows)
    assert 0.05 < threshold < 0.93
    assert metrics["displayed_useful_cards"] == 72
    assert metrics["positive_hit_at_three"] == 36
    assert metrics["no_useful_displayed"] == 0
    heldout = audit.summarize(rows, threshold, include_grades=True)
    assert audit.heldout_passed(heldout)
    assert heldout["displayed_precision"] == 1.0
    assert len(heldout["displayed_card_grades"]) == 72
    assert all(row["displayed_card_useful"] for row in
               heldout["displayed_card_grades"])


def test_calibration_rejects_when_negative_requires_positive_suppression():
    rows = _perfect_rows()
    rows[0]["candidates"][0]["score"] = 0.99
    with pytest.raises(audit.AuditError, match="calibration_gate_rejected"):
        audit.choose_threshold(rows)


def test_distinct_page_deduplication_and_page_vs_cue_failure_grade():
    row = _row(0, 0)
    row["candidates"][0].update(score=0.9, page_useful=True,
                                 cue_useful=False, useful=False)
    row["candidates"][1].update(score=0.8, page=1)
    row["candidates"][2].update(score=0.7, page_useful=False,
                                 cue_useful=False, useful=False)
    assert [candidate["index"] for candidate in
            audit.displayed(row["candidates"], 0.5)] == [0, 2]
    metrics = audit.summarize([row], 0.5, include_grades=True)
    assert metrics["false_primary"][0]["mechanism"] == "exact_cue_not_useful"
    assert metrics["displayed_original_page_useful"] == 1
    assert metrics["displayed_exact_cue_useful"] == 0
    assert metrics["displayed_page_useful_cue_weak"] == 1
    assert [grade["original_page_number"] for grade in
            metrics["displayed_card_grades"]] == [1, 3]


@pytest.mark.parametrize("field,value", [
    ("positive_hit_at_three", 32), ("useful_first", 30),
    ("displayed_useful_cards", 59), ("no_useful_displayed", 1),
])
def test_every_primary_heldout_gate_is_mandatory(field, value):
    threshold, _metrics = audit.choose_threshold(_perfect_rows())
    metrics = audit.summarize(_perfect_rows(), threshold, include_grades=True)
    assert audit.heldout_passed(metrics)
    metrics[field] = value
    assert not audit.heldout_passed(metrics)


def test_per_form_and_exact_cardinality_gates_are_mandatory():
    threshold, _metrics = audit.choose_threshold(_perfect_rows())
    metrics = audit.summarize(_perfect_rows(), threshold, include_grades=True)
    metrics["form"]["direct"]["positive_hit_at_three"] = 9
    assert not audit.heldout_passed(metrics)
    metrics = audit.summarize(_perfect_rows(), threshold, include_grades=True)
    metrics["count_strata"]["2"]["exact_count"] = 9
    assert not audit.heldout_passed(metrics)


def test_missing_external_freeze_pin_stops_before_any_child(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(audit, "run_child", lambda args: calls.append(args))
    argv = ["--corpus", "unused", "--fixture", "unused", "--bundle", "unused",
            "--runtime-manifest", "unused", "--freeze-receipt", "unused",
            "--expected-freeze-sha256", "bad-pin", "--output", "unused",
            "--execute-approved"]
    assert audit.main(argv) == 1
    assert calls == []
    assert json.loads(capsys.readouterr().out)["candidate_passed"] is False


def test_calibration_failure_does_not_open_heldout(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "require_bounded_container", lambda: None)
    monkeypatch.setattr(audit, "require_approved_ledger", lambda: None)
    monkeypatch.setattr(audit, "APPROVED_LEDGER_ROOT", tmp_path)
    groups = ([_group(i, "train") for i in range(96)] +
              [_group(i, "calibration") for i in range(48)] +
              [_group(i, "heldout") for i in range(48)])
    monkeypatch.setattr(audit, "verify_frozen", lambda args: {"freeze_sha256": "a" * 64})
    real_read_json = audit.fixture_admission.read_json
    monkeypatch.setattr(audit.fixture_admission, "read_json",
                        lambda path, limit: (({"groups": groups}, b"") if
                                             path.name == "fixture.json" else
                                             real_read_json(path, limit)))
    monkeypatch.setattr(audit, "peak_rss", lambda: 100)
    monkeypatch.setattr(audit, "fit_classifier", lambda rows, labels: {"synthetic": True})
    scored_splits = []

    def fake_rows(split_groups, model, scorer):
        scored_splits.append(split_groups[0]["split"])
        return _perfect_rows()

    monkeypatch.setattr(audit, "scored_rows", fake_rows)
    monkeypatch.setattr(audit, "choose_threshold",
                        lambda rows: (_ for _ in ()).throw(
                            audit.AuditError("calibration_gate_rejected")))
    scorer_calls = []

    def scorer(pairs):
        scorer_calls.append(len(pairs))
        return [0.0] * len(pairs)

    monkeypatch.setattr(audit, "_model_scorer",
                        lambda bundle, start, baseline: (
                            scorer, lambda: {"resource_passed": True}, 0.1))
    args = Namespace(corpus=tmp_path, fixture=tmp_path / "fixture.json",
                     bundle=tmp_path, runtime_manifest=tmp_path / "runtime.json",
                     freeze_receipt=tmp_path / "freeze.json",
                     expected_freeze_sha256="a" * 64, output=tmp_path)
    audit.write_exclusive(audit.attempt_marker_path(), {
        "procedure": audit.PROCEDURE, "freeze_sha256": "a" * 64,
        "harness_sha256": audit.digest(Path(audit.__file__)),
        "one_shot_attempt": True})
    audit.run_child(args)
    assert audit.child_claim_path().is_file()
    assert scored_splits == ["calibration"]
    assert sum(scorer_calls) == 384
    result = json.loads((tmp_path / "audit-result.json").read_text(encoding="utf-8"))
    assert result["status"] == "calibration_rejected_no_heldout"
    assert result["heldout_scored"] is False
    assert not (tmp_path / "calibration-rule.json").exists()


def test_child_claim_is_exclusive_after_first_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "require_bounded_container", lambda: None)
    monkeypatch.setattr(audit, "require_approved_ledger", lambda: None)
    monkeypatch.setattr(audit, "APPROVED_LEDGER_ROOT", tmp_path)
    args = Namespace(freeze_receipt=tmp_path / "freeze.json",
                     expected_freeze_sha256="a" * 64,
                     output=tmp_path, fixture=tmp_path / "fixture.json")
    monkeypatch.setattr(audit, "verify_frozen", lambda args: {"freeze_sha256": "a" * 64})
    marker = audit.attempt_marker_path()
    audit.write_exclusive(marker, {
        "procedure": audit.PROCEDURE, "freeze_sha256": "a" * 64,
        "harness_sha256": audit.digest(Path(audit.__file__)),
        "one_shot_attempt": True})
    # A missing fixture fails after the claim, consuming this single attempt.
    with pytest.raises(audit.fixture_admission.FixtureError, match="file_missing_or_symlink"):
        audit.run_child(args)
    assert audit.child_claim_path().is_file()
    with pytest.raises(FileExistsError):
        audit.run_child(args)


def test_second_receipt_name_cannot_open_another_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "require_bounded_container", lambda: None)
    monkeypatch.setattr(audit, "require_approved_ledger", lambda: None)
    monkeypatch.setattr(audit, "APPROVED_LEDGER_ROOT", tmp_path)
    first_receipt = tmp_path / "freeze-first.json"
    second_receipt = tmp_path / "freeze-copied.json"
    audit.write_exclusive(audit.attempt_marker_path(), {
        "procedure": audit.PROCEDURE, "freeze_sha256": "a" * 64,
        "harness_sha256": audit.digest(Path(audit.__file__)),
        "one_shot_attempt": True,
    })
    assert first_receipt != second_receipt
    args = Namespace(
        audit_start=audit.perf_counter(), freeze_receipt=second_receipt,
        expected_freeze_sha256="a" * 64,
        output=tmp_path / "fresh-output",
    )
    with pytest.raises(audit.AuditError, match="audit_attempt_consumed"):
        audit.supervise(args)
    assert not args.output.exists()


@pytest.mark.parametrize("cpu,memory,accepted", [
    ("400000 100000", "2147483648", True),
    ("500000 100000", "2147483648", False),
    ("400000 100000", "3221225472", False),
    ("max 100000", "2147483648", False),
])
def test_bounded_container_requires_cpu_and_memory_cgroup_limits(
    monkeypatch, cpu, memory, accepted,
):
    monkeypatch.setattr(audit, "require_networkless_linux", lambda: None)
    original = Path.read_text

    def read(path, *args, **kwargs):
        if str(path).replace("\\", "/").endswith("/cpu.max"):
            return cpu
        if str(path).replace("\\", "/").endswith("/memory.max"):
            return memory
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    if accepted:
        audit.require_bounded_container()
    else:
        with pytest.raises(audit.AuditError, match="container_resource_limits_required"):
            audit.require_bounded_container()


def test_overlong_pair_rejected_before_model_run(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text('{"pad_token_id":0}', encoding="utf-8")
    runs = []

    class FakeTokenizer:
        @classmethod
        def from_file(cls, path):
            return cls()

        def no_truncation(self):
            pass

        def no_padding(self):
            pass

        def encode(self, question, cue, *, add_special_tokens):
            return SimpleNamespace(ids=[1] * 257, attention_mask=[1] * 257,
                                   type_ids=[0] * 257)

    class FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        def get_inputs(self):
            return [SimpleNamespace(name="input_ids"),
                    SimpleNamespace(name="attention_mask")]

        def get_outputs(self):
            return [SimpleNamespace(name="logits")]

        def run(self, *args):
            runs.append(args)
            raise AssertionError("model must not run")

    fake_ort = SimpleNamespace(SessionOptions=lambda: SimpleNamespace(),
                               ExecutionMode=SimpleNamespace(ORT_SEQUENTIAL=0),
                               InferenceSession=FakeSession)
    monkeypatch.setitem(sys.modules, "tokenizers",
                        SimpleNamespace(Tokenizer=FakeTokenizer))
    monkeypatch.setitem(sys.modules, "onnxruntime", fake_ort)
    monkeypatch.setattr(audit, "peak_rss", lambda: 100)
    monkeypatch.setattr(audit, "require_networkless_linux", lambda: None)
    score, _resources, _startup = audit._model_scorer(tmp_path, perf_counter(), 100)
    with pytest.raises(audit.AuditError, match="complete_input_budget"):
        score([("question", "cue")])
    assert runs == []
