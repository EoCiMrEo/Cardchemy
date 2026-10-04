"""Synthetic exact-checkpoint, projection and one-use continuation controls."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
import sys
from uuid import uuid4
import pytest
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / "scripts"),
    str(Path(__file__).resolve().parents[1] / "scripts")]
import prepare_private_visual_continue5_v1 as prep
import run_private_visual_continue5_v1 as custody
import launch_private_visual_continue5_v1 as host
import execute_private_visual_continue5_v1 as executor
from test_private_visual_trial_v8_preflight import synthetic
from test_private_visual_trial_v8_caller import synthetic_bound
from test_execute_private_visual_trial_v8 import ControllerHarness
from test_private_source_display_v8_score import NOW

def pin(raw): return sha256(raw).hexdigest()

def inputs(monkeypatch):
    artifacts, code, _, _ = synthetic(monkeypatch)
    full = prep.base.prepare(artifacts, current_code=code)
    for name in prep.CODE_PATHS: code[name] = (prep.REPO / name).read_bytes()
    parent = prep.canonical({"code": {name: pin(raw) for name, raw in code.items()}})
    approval = b"invented old authority"
    records, observed = {}, []
    for frozen in full.cases[:7]:
        cid = frozen.case_id
        records[cid + "-dispatch-guard.json"] = prep.canonical({"invented": "dispatch", "id": cid})
        records[cid + "-selected-guard.json"] = prep.canonical({"invented": "selected", "id": cid})
        row = {"case_id": cid, "request_sha256": frozen.request_sha256,
            "admission_sha256": frozen.admission_sha256, "selected_ids": ["S01"],
            "selected_guard_sha256": pin(records[cid + "-selected-guard.json"]),
            "dispatch_guard_sha256": pin(records[cid + "-dispatch-guard.json"]),
            "backend_association_verified": True, "unverified_references": True}
        observed.append(row)
        records[cid + "-result.json"] = prep.canonical({**row, "status": "completed",
            "physical_attempted": True, "synthetic_attempted": False, "http_status": 200,
            "body_sha256": frozen.body_sha256})
    records["T08-result.json"] = prep.canonical({"case_id": "T08", "status": "stopped",
        "http_status": 503, "physical_attempted": True, "usage_cost_unknown": True})
    records["summary.json"] = prep.canonical({"schema": "private_visual_trial_v8_execution",
        "status": "stopped", "synthetic_interfaces": False, "provider_calls": 8,
        "completed_cases": 7, "case_denominator": 12, "known_guard_cost_microusd": 38077,
        "usage_unknown_attempts": 1, "cases": observed, "embedding_calls": 0, "answer_calls": 0,
        "verifier_calls": 0, "automatic_retries": 0, "database_writes": 0})
    monkeypatch.setattr(prep, "PARENT_STAGE_SHA", pin(parent))
    monkeypatch.setattr(prep, "PARENT_APPROVAL_SHA", pin(approval))
    monkeypatch.setattr(prep, "PARENT_OUTPUT_PINS_SHA", pin(prep.canonical({n: pin(r) for n, r in records.items()})))
    return artifacts, code, parent, approval, records

def test_exact_five_projection_retains_full_signed_artifacts_and_seven_outcomes(monkeypatch):
    artifacts, code, parent, approval, records = inputs(monkeypatch)
    saved = deepcopy((artifacts, records)); constants = prep.base.CASE_IDS, prep.base.MAX_CALLS, prep.base.MAX_COST_USD
    full, projected = prep.prepare(artifacts, current_code=code, manifest_raw=parent, approval_raw=approval, records=records)
    assert len(full.cases) == 12 and [c.case_id for c in projected.cases] == list(prep.CASE_IDS)
    assert projected.cases == full.cases[7:] and projected.artifacts == full.artifacts
    assert dict(projected.artifacts) == artifacts and (artifacts, records) == saved
    assert (prep.base.CASE_IDS, prep.base.MAX_CALLS, prep.base.MAX_COST_USD) == constants
    report = prep.checkpoint_report(projected)
    assert report["guards"]["max_calls"] == 5 and report["guards"]["max_cost_usd"] == "0.11"
    assert report["preserved_physical_attempts"] == 8 and report["full_quality_denominator"] == 12
    assert report["guards"]["reserved_cost_usd"] == "0.100352"
    assert report["provider_calls"] == 0 and report["live_authorized"] is False

@pytest.mark.parametrize("mutation", ["parent", "approval", "missing", "selection", "request", "failure", "code", "summary"])
def test_changed_checkpoint_or_old_attempt_cannot_be_reused(monkeypatch, mutation):
    artifacts, code, parent, approval, records = inputs(monkeypatch)
    if mutation == "parent": parent += b" "
    elif mutation == "approval": approval += b" "
    elif mutation == "missing": records.pop("T01-result.json")
    elif mutation == "code": code["backend/app/ai/source_navigation.py"] += b" "
    else:
        name = "T08-result.json" if mutation == "failure" else "summary.json" if mutation == "summary" else "T01-result.json"
        row = json.loads(records[name])
        if mutation == "selection": row["selected_ids"] = ["S02"]
        elif mutation == "request": row["request_sha256"] = "0" * 64
        elif mutation == "failure": row["http_status"] = 200
        else: row["provider_calls"] = 7
        records[name] = prep.canonical(row)
        # Even a separately repinned checkpoint cannot forge semantic credit.
        monkeypatch.setattr(prep, "PARENT_OUTPUT_PINS_SHA", pin(prep.canonical({n: pin(r) for n, r in records.items()})))
    with pytest.raises((prep.Refusal, KeyError)):
        prep.prepare(artifacts, current_code=code, manifest_raw=parent, approval_raw=approval, records=records)

def harness(monkeypatch):
    full, whole = synthetic_bound(monkeypatch)
    code = dict(whole.pins[0].code_sha256)
    for name in prep.CODE_PATHS: code[name] = pin((prep.REPO / name).read_bytes())
    projected = replace(full, cases=full.cases[7:], code_sha256=tuple(sorted({**dict(full.code_sha256),
        **{n: code[n] for n in prep.CODE_PATHS}}.items())))
    bound = replace(whole, cases=whole.cases[7:], pins=tuple(replace(p, code_sha256=code) for p in whole.pins[7:]))
    return ControllerHarness(projected, bound), full, whole

@pytest.mark.asyncio
async def test_seven_fresh_rechecks_precede_only_five_new_calls_and_no_browser_claim(monkeypatch, tmp_path):
    h, full, whole = harness(monkeypatch)
    monkeypatch.setattr(executor, "LIVE_AUTHORIZED", True)
    async def recheck(*args, **kwargs):
        h.events.append((None, "retained_recheck"))
        return [{"case_id": cid, "browser_page_open_observed": False, "provider_replayed": False}
            for cid in prep.RETAINED_IDS]
    monkeypatch.setattr(executor.rehearsal, "recheck_retained", recheck)
    raw = executor.approval_payload(h.prepared, h.bound, trial_id=uuid4(), authorization_id="synthetic_five_only",
        approved_at=NOW, expires_at=NOW + timedelta(hours=1))
    r = await executor.execute_private_continue5(h.prepared, h.bound, retained_context=(full, whole, {}),
        settings=object(), api_key="synthetic-opaque-key", approval_bytes=raw, approval_sha256=pin(raw),
        ledger=executor.TrialLedger(tmp_path), interfaces=h.controller_interfaces())
    assert r["status"] == "completed" and r["completed_cases"] == r["synthetic_transport_calls"] == 5
    assert r["provider_calls"] == 0 and r["preserved_completed_cases"] == 7
    assert [row["case_id"] for row in r["cases"]] == list(prep.CASE_IDS)
    assert h.events[0][1] == "retained_recheck" and r["historical_provider_calls"] == 8
    assert not r["browser_page_open_observed"] and not r["release_gate_passed"]
    assert len(list(tmp_path.glob("T*-intent.json"))) == 5
    with pytest.raises((executor.ExecutionError, host.LaunchError)):
        await executor.execute_private_continue5(h.prepared, h.bound, retained_context=(full, whole, {}),
            settings=object(), api_key="synthetic-opaque-key", approval_bytes=raw, approval_sha256=pin(raw),
            ledger=executor.TrialLedger(tmp_path), interfaces=h.controller_interfaces())

@pytest.mark.asyncio
async def test_retained_source_guard_failure_prevents_any_new_http_or_credit(monkeypatch, tmp_path):
    h, full, whole = harness(monkeypatch)
    monkeypatch.setattr(executor, "LIVE_AUTHORIZED", True)
    async def deny(*args, **kwargs): raise executor.guard.DispatchGuardError("source_changed")
    monkeypatch.setattr(executor.rehearsal, "recheck_retained", deny)
    raw = executor.approval_payload(h.prepared, h.bound, trial_id=uuid4(), authorization_id="synthetic_five_only",
        approved_at=NOW, expires_at=NOW + timedelta(hours=1))
    with pytest.raises(executor.guard.DispatchGuardError):
        await executor.execute_private_continue5(h.prepared, h.bound, retained_context=(full, whole, {}),
            settings=object(), api_key="synthetic-opaque-key", approval_bytes=raw, approval_sha256=pin(raw),
            ledger=executor.TrialLedger(tmp_path), interfaces=h.controller_interfaces())
    assert h.keys == [] and not (tmp_path / "claim.json").exists()
