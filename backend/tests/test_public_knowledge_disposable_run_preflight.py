"""The independent freeze must be checked before a disposable paid run."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts import preflight_public_knowledge_disposable_run as run_preflight


def _write(path: Path, value: dict) -> str:
    path.write_text(json.dumps(value), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _freeze(tmp_path: Path, monkeypatch):
    roster_sha = "a" * 64
    monkeypatch.setattr(run_preflight, "HOLDOUT", ("holdout-v2.json", roster_sha))
    cases = []
    labels = []
    for index in range(12):
        group = ("direct", "paraphrase", "follow_up")[index % 3]
        case_id = f"T{index + 1:02d}"
        window = f"A useful detail from page {index + 1}."
        source_hash = ("b" if index % 2 else "c") * 64
        cases.append({
            "id": case_id, "group": group, "document_sha256": source_hash,
            "gold_physical_page": index + 1,
            "gold_window_exact_extracted_text": window,
        })
        labels.append({
            "id": case_id, "group": group, "document_sha256": source_hash,
            "physical_page": index + 1,
            "exact_window_sha256": hashlib.sha256(window.encode()).hexdigest(),
            "source_identity": "Yes", "exact_app_extracted_substring": "Yes",
            "excerpt_relation_and_conditions": "Yes", "visual_page_useful": "Yes",
            "followup_referent": "Yes" if group == "follow_up" else "N/A",
        })
    label_document = {
        "schema": run_preflight.LABEL_SCHEMA, "packet_sha256": roster_sha,
        "selector_outputs_inspected": False, "provider_requests": 0,
        "database_writes": 0, "cases": labels,
    }
    receipt = {
        "selector_results_seen": False, "question_labels_frozen": False,
        "provider_requests": 0, "database_writes": 0,
        "runtime_hashes": {
            name: hashlib.sha256((run_preflight.ROOT / name).read_bytes()).hexdigest()
            for name in run_preflight.RUNTIME_PATHS
        },
    }
    label_path = tmp_path / "labels.json"
    receipt_path = tmp_path / "receipt.json"
    monkeypatch.setattr(run_preflight, "LABELS", (label_path.name, _write(label_path, label_document)))
    monkeypatch.setattr(run_preflight, "PRELABEL", (receipt_path.name, _write(receipt_path, receipt)))
    return cases, label_path, receipt_path, label_document, receipt


def test_independent_labels_and_runtime_freeze_match(tmp_path, monkeypatch):
    cases, *_ = _freeze(tmp_path, monkeypatch)
    run_preflight.check_freeze(tmp_path, cases)


def test_refuses_changed_label_bytes(tmp_path, monkeypatch):
    cases, label_path, *_ = _freeze(tmp_path, monkeypatch)
    label_path.write_bytes(label_path.read_bytes() + b" ")
    with pytest.raises(run_preflight.Refusal, match="frozen_artifact_changed"):
        run_preflight.check_freeze(tmp_path, cases)


def test_refuses_label_for_different_window(tmp_path, monkeypatch):
    cases, label_path, _, labels, _ = _freeze(tmp_path, monkeypatch)
    labels["cases"][0]["exact_window_sha256"] = "0" * 64
    monkeypatch.setattr(run_preflight, "LABELS", (label_path.name, _write(label_path, labels)))
    with pytest.raises(run_preflight.Refusal, match="freeze_invalid"):
        run_preflight.check_freeze(tmp_path, cases)


def test_refuses_selector_output_inspection_before_labels(tmp_path, monkeypatch):
    cases, _, receipt_path, _, receipt = _freeze(tmp_path, monkeypatch)
    receipt["selector_results_seen"] = True
    monkeypatch.setattr(run_preflight, "PRELABEL", (receipt_path.name, _write(receipt_path, receipt)))
    with pytest.raises(run_preflight.Refusal, match="freeze_invalid"):
        run_preflight.check_freeze(tmp_path, cases)


def test_refuses_runtime_drift(tmp_path, monkeypatch):
    cases, _, receipt_path, _, receipt = _freeze(tmp_path, monkeypatch)
    name = next(iter(run_preflight.RUNTIME_PATHS))
    receipt["runtime_hashes"][name] = "0" * 64
    monkeypatch.setattr(run_preflight, "PRELABEL", (receipt_path.name, _write(receipt_path, receipt)))
    with pytest.raises(run_preflight.Refusal, match="runtime_changed_since_freeze"):
        run_preflight.check_freeze(tmp_path, cases)
