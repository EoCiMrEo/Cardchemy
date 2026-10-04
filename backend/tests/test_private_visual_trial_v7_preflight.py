"""Keyless preflight/response/scorer boundary; exclusively synthetic source data."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest

from test_private_source_display_v7_score import fixture, freeze, observations
from tests.test_source_visual_provider import response
from tests.test_source_judgment_visual import verdict

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import prepare_private_visual_trial_v7 as trial


def pin(raw):
    return sha256(raw).hexdigest()


def synthetic(monkeypatch, *, labels_change=None):
    values = fixture(labels_change=labels_change)
    paths = set(trial.EXTRA_CODE_PATHS) | {"backend/app/ai/source_navigation.py"}
    code = {name: (trial.REPO / name).read_bytes() for name in paths}
    manifest = {"schema": "private_current_v7_runtime_manifest", "actual_policy": trial.scorer.POLICY,
        "actual_contract": trial.scorer.CONTRACT, "image_sha256": "sha256:" + "a" * 64,
        "migration_heads": ["20261002_0032"], "runtime_profile": {"ask": False, "judge": False,
            "contract": trial.scorer.CONTRACT, "output": 4096, "required_policy": trial.scorer.POLICY,
            "thinking": "high", "timeout": 120.0},
        "runtime_source_hashes": {"app/ai/source_navigation.py": pin(code["backend/app/ai/source_navigation.py"])},
        "diagnostic_sha256": pin(b"synthetic-diagnostic"),
        "scorer_sha256": pin(code["scripts/score_private_source_display_v7.py"]),
        "raw_projection_sha256": pin(code["scripts/navigation_raw_query_projection_v1.py"])}
    values["runtime_sha"] = pin(trial.canonical(manifest))
    bridge = freeze(values)
    artifacts = {"roster": trial.canonical(values["roster"]), "labels": trial.canonical(values["labels"]),
        "stage1": trial.canonical(values["stage1"]), "review_receipt": trial.canonical(values["receipt"]),
        "requests": trial.canonical(values["packet"]), "bridge": trial.canonical(bridge),
        "runtime": trial.canonical(manifest)}
    pins = {name: pin(raw) for name, raw in artifacts.items()}
    pins["trusted_review_key"] = values["key_sha"]
    monkeypatch.setattr(trial, "FROZEN_PINS", pins)
    return artifacts, code, values, bridge


def repin(monkeypatch, artifacts, name, value):
    artifacts[name] = trial.canonical(value)
    monkeypatch.setitem(trial.FROZEN_PINS, name, pin(artifacts[name]))


def test_complete_signed_preflight_binds_exact_wire_cost_and_no_authority(monkeypatch):
    artifacts, code, values, bridge = synthetic(monkeypatch)
    before = deepcopy(artifacts)
    prepared = trial.prepare(artifacts, current_code=code)
    assert artifacts == before
    assert len(prepared.cases) == 12
    for case, row in zip(prepared.cases, values["packet"]["cases"], strict=True):
        assert case.request_bytes == trial.canonical(row["request"])
        assert pin(case.request_bytes) == case.request_sha256
        assert case.body_sha256 == pin(trial.canonical({k: v for k, v in row["request"].items() if k != "model"}))
        sources = json.loads(case.sources_bytes)
        assert len(sources) == 4
        assert sources[0]["document_id"] == row["source_bindings"][0]["document_id"]
        assert sources[0]["page_key"] == values["roster"]["cases"][int(case.case_id[1:]) - 1]["candidates"][0]["page_key"]
    result = trial.report(prepared)
    assert result["candidate_count"] == 48 and result["signed_review_verified"]
    assert not result["live_authorized"] and not result["release_gate_passed"]
    assert result["provider_calls"] == result["database_reads"] == result["database_writes"] == 0
    assert result["guards"]["reserved_cost_usd"] == "0.2408448"
    assert result["guards"]["max_cost_usd"] == "0.25"
    assert result["guards"]["fresh_sql_dispatch_check_required"]
    assert "Exact cue" not in json.dumps(result) and "spectral" not in repr(prepared)
    assert sum(row["context_status"] == "resolved_literal_subject" for row in bridge["cases"]) == 2


@pytest.mark.parametrize("change", ["artifact", "signature", "code", "missing_code", "request", "row_omission"])
def test_identity_and_review_cannot_be_replaced_even_with_same_question(monkeypatch, change):
    artifacts, code, values, _ = synthetic(monkeypatch)
    if change == "artifact":
        artifacts["labels"] += b" "
    elif change == "signature":
        receipt = json.loads(artifacts["review_receipt"])
        receipt["reviewer_signature_hex"] = "00" * 64
        repin(monkeypatch, artifacts, "review_receipt", receipt)
    elif change == "code":
        code["backend/app/ai/source_navigation.py"] += b"\n# changed\n"
    elif change == "missing_code":
        code.pop("backend/app/ai/providers/source_visual_v3.py")
    else:
        packet = deepcopy(values["packet"])
        if change == "request":
            packet["cases"][0]["request"]["contents"][0]["parts"][1]["text"] += " changed"
        else:
            packet["cases"].pop()
        repin(monkeypatch, artifacts, "requests", packet)
    with pytest.raises(trial.Refusal):
        trial.prepare(artifacts, current_code=code)


@pytest.mark.parametrize("field,value", [("ask", True), ("ask", 0), ("judge", 0),
                                        ("output", 4097), ("timeout", 121), ("thinking", "low")])
def test_runtime_disabled_and_budget_profile_are_exact(monkeypatch, field, value):
    artifacts, code, _, _ = synthetic(monkeypatch)
    manifest = json.loads(artifacts["runtime"])
    manifest["runtime_profile"][field] = value
    repin(monkeypatch, artifacts, "runtime", manifest)
    with pytest.raises(trial.Refusal, match="runtime_manifest_invalid"):
        trial.prepare(artifacts, current_code=code)


def test_preflight_does_not_turn_legacy_diag_context_into_sql_grant(monkeypatch):
    artifacts, code, values, _ = synthetic(monkeypatch)
    packet = deepcopy(values["packet"])
    row = packet["cases"][8]
    row["raw_navigation_query"] = values["stage1"]["cases"][8]["question"]
    row["preceding_question"] = None
    row["admission_snapshot"].update(raw_question_clear=True, preceding=None)
    row["request"] = deepcopy(row["legacy_request"])
    repin(monkeypatch, artifacts, "requests", packet)
    with pytest.raises(trial.Refusal, match="signed_bridge_invalid"):
        trial.prepare(artifacts, current_code=code)


def test_supplied_native_response_uses_actual_adapter_counts_thinking_but_proves_no_dispatch(monkeypatch):
    artifacts, code, _, _ = synthetic(monkeypatch)
    case = trial.prepare(artifacts, current_code=code).cases[0]
    from app.ai.providers import source_visual
    monkeypatch.setattr(source_visual, "Settings", lambda *args, **kwargs: pytest.fail("Settings instantiated"))
    monkeypatch.setattr(source_visual.httpx, "AsyncClient", lambda *args, **kwargs: pytest.fail("HTTP client constructed"))
    payload = response()
    result = trial.parse_supplied_response(case, trial.canonical(payload))
    assert result["output_tokens_including_thinking"] == 600
    assert result["known_guard_cost_microusd"] == 2100
    assert result["source_only"] and result["unverified_references"]
    assert not result["physical_execution_proved"] and not result["actual_display_integrity_proved"]
    assert not result["generated_answer"] and not result["release_gate_passed"]
    assert "discarded synthetic thought" not in json.dumps(result)


@pytest.mark.parametrize("change", ["finish", "model", "input_tokens", "output_with_thinking", "invented_id", "raw_size"])
def test_partial_unbounded_or_unissued_provider_output_refuses(monkeypatch, change):
    artifacts, code, _, _ = synthetic(monkeypatch)
    case = trial.prepare(artifacts, current_code=code).cases[0]
    payload = response()
    if change == "finish":
        payload["candidates"][0]["finishReason"] = "MAX_TOKENS"
    elif change == "model":
        payload["modelVersion"] = "different-model"
    elif change == "input_tokens":
        payload["usageMetadata"].update(promptTokenCount=32769, totalTokenCount=40000)
    elif change == "output_with_thinking":
        payload["usageMetadata"].update(totalTokenCount=6097)
    elif change == "invented_id":
        answer = verdict()
        answer["pages"][0]["id"] = "S99"
        payload["candidates"][0]["content"]["parts"][1]["text"] = json.dumps(answer)
    raw = b" " * 65537 if change == "raw_size" else trial.canonical(payload)
    with pytest.raises(trial.Refusal):
        trial.parse_supplied_response(case, raw)


def test_actual_measurement_scorer_keeps_every_card_unknown_and_twelve_cases(monkeypatch):
    def make_unknown(labels):
        for row in labels["cases"][:3]:
            row["candidates"][1]["cue_useful"] = "Unsure"
    artifacts, code, values, bridge = synthetic(monkeypatch, labels_change=make_unknown)
    prepared = trial.prepare(artifacts, current_code=code)
    measured = observations(values, bridge)
    for row, source in zip(measured["cases"][:3], values["roster"]["cases"][:3], strict=True):
        row["displayed"].append(dict(source["candidates"][1], **dict.fromkeys(trial.scorer.INTEGRITY, True)))
    raw = trial.canonical(measured)
    result = trial.score_supplied_measurement(prepared, raw, measurement_sha256=pin(raw))
    assert result["displayed_cards"] == 15 and result["unknown_cards"] == 3
    assert result["displayed_usefulness"] == .8 and result["case_denominator"] == 12
    assert result["component_passed"] and not result["release_gate_passed"]
    measured["cases"].pop()
    raw = trial.canonical(measured)
    result = trial.score_supplied_measurement(prepared, raw, measurement_sha256=pin(raw))
    assert not result["component_passed"] and result["missing_cases"] == 1 and result["case_denominator"] == 12


def test_cli_default_and_execute_are_inert_without_reading_even_given_directory(monkeypatch, capsys):
    monkeypatch.setattr(trial, "preflight_directory", lambda *args: pytest.fail("input opened"))
    assert trial.main(["--directory", "missing"]) == 0
    assert trial.main(["--execute", "--directory", "missing"]) == 2
    messages = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [row["status"] for row in messages] == ["unexecuted", "live_dispatch_unimplemented"]
    assert all(row["provider_calls"] == row["database_reads"] == row["database_writes"] == 0 for row in messages)


def test_private_directory_and_generic_refusal_never_expose_content(tmp_path, monkeypatch, capsys):
    with pytest.raises(trial.Refusal, match="private_temp_required"):
        trial.preflight_directory(tmp_path / "nested")
    def fail(*args):
        raise ValueError("synthetic private cue must never print")
    monkeypatch.setattr(trial, "preflight_directory", fail)
    assert trial.main(["--preflight", "--directory", str(tmp_path)]) == 2
    assert "synthetic private" not in capsys.readouterr().out


def test_input_file_checks_original_symlink_before_read(tmp_path, monkeypatch):
    target = tmp_path / "synthetic.json"
    target.write_bytes(b"{}")
    old = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == target or old(path))
    with pytest.raises(trial.Refusal, match="input_file_invalid"):
        trial._file(target, maximum=100)


def test_input_file_portable_without_python312_windows_junction_api(tmp_path, monkeypatch):
    monkeypatch.delattr(Path, "is_junction", raising=False)
    target = tmp_path / "synthetic.json"
    target.write_bytes(b"{}")
    assert trial._file(target, maximum=100) == b"{}"
