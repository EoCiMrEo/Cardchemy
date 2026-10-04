"""Inert exact T08–T12 continuation; full signed fourteen-case inputs survive.

The four successful outcomes are checkpointed, never supplied to transport.
Their current access/PDF/context must be rechecked before combined credit.
Old claims, HTTP 503 and all five physical attempts remain immutable.
"""
from __future__ import annotations
from dataclasses import replace
from decimal import Decimal
import json
from types import FunctionType
import prepare_private_seed_visual_trial_v1 as original

for _name, _value in vars(original).items():
    if not _name.startswith("__") and (not isinstance(_value, FunctionType) or _value.__module__ != original.__name__):
        globals()[_name] = _value
base = original
SCHEMA = "private_seed_continue10_v1_preflight"
LIVE_AUTHORIZED = False
CASE_IDS = base.CASE_IDS[4:]
RETAINED_IDS = base.CASE_IDS[:4]
MAX_CALLS, MAX_COST_USD = 10, Decimal("0.21")
MAX_TOTAL_SECONDS = 2400
PARENT_STAGE_SHA = "7652938130b53fd2d52c729f5234a449f3c9467fb8a5a1bbe19a38204f48a6af"
PARENT_APPROVAL_SHA = "c59a657dedc614c0c30a73acba7d679eb1b5c278f6430f48268fec4254ff320c"
PARENT_OUTPUT_PINS_SHA = "a1153362b3aa9934b33a6470130f50de091f97ca70011adf0121ba6bf94cc00b"
CODE_PATHS = (
    "scripts/prepare_private_seed_continue10_v1.py", "scripts/run_private_seed_continue10_v1.py",
    "scripts/launch_private_seed_continue10_v1.py", "backend/scripts/execute_private_seed_continue10_v1.py",
    "backend/scripts/private_seed_continue10_entry_v1.py", "backend/scripts/rehearse_private_seed_continue10_v1.py",
    "scripts/prepare_private_visual_continue5_v1.py", "scripts/run_private_visual_continue5_v1.py",
    "scripts/launch_private_visual_continue5_v1.py", "backend/scripts/execute_private_visual_continue5_v1.py",
    "backend/scripts/private_visual_continue5_entry_v1.py", "backend/scripts/rehearse_private_visual_continue5_v1.py")

def _shared(function):
    value = FunctionType(function.__code__, globals(), function.__name__, function.__defaults__, function.__closure__)
    value.__kwdefaults__ = function.__kwdefaults__
    return value

for _name in ("require", "canonical", "digest", "_bound", "_file", "_code_path", "guards", "parse_supplied_response"):
    globals()[_name] = _shared(getattr(base, _name))

def checkpoint(manifest_raw, approval_raw, records, full, current_code):
    require(type(records) is dict and digest(manifest_raw) == PARENT_STAGE_SHA
        and digest(approval_raw) == PARENT_APPROVAL_SHA, "parent_identity_invalid")
    require(digest(canonical({name: digest(raw) for name, raw in records.items()})) == PARENT_OUTPUT_PINS_SHA,
        "parent_receipts_changed")
    manifest = json.loads(manifest_raw)
    require(type(manifest["code"]) is dict and set(manifest["code"]) <= set(current_code)
        and all(digest(current_code[name]) == pin for name, pin in manifest["code"].items()), "parent_code_changed")
    summary = json.loads(records["summary.json"])
    require(summary["schema"] == "private_seed_visual_trial_v1_execution" and summary["status"] == "stopped"
        and summary["synthetic_interfaces"] is False and summary["provider_calls"] == 5
        and summary["completed_cases"] == 4 and summary["case_denominator"] == 14
        and summary["known_guard_cost_microusd"] == 20310 and summary["usage_unknown_attempts"] == 1
        and tuple(row["case_id"] for row in summary["cases"]) == RETAINED_IDS
        and all(summary[name] == 0 for name in ("embedding_calls", "answer_calls", "verifier_calls",
            "automatic_retries", "database_writes")), "parent_terminal_invalid")
    for frozen, observed in zip(full.cases[:4], summary["cases"], strict=True):
        cid = frozen.case_id
        result = json.loads(records[cid + "-result.json"])
        require(result["status"] == "completed" and result["physical_attempted"] is True
            and result["synthetic_attempted"] is False and result["http_status"] == 200
            and result["request_sha256"] == observed["request_sha256"] == frozen.request_sha256
            and result["body_sha256"] == frozen.body_sha256
            and result["admission_sha256"] == observed["admission_sha256"] == frozen.admission_sha256
            and result["selected_ids"] == observed["selected_ids"]
            and result["selected_guard_sha256"] == digest(records[cid + "-selected-guard.json"])
            and result["dispatch_guard_sha256"] == digest(records[cid + "-dispatch-guard.json"])
            and observed["backend_association_verified"] is True and observed["unverified_references"] is True,
            "parent_success_binding_invalid")
    failed = json.loads(records["D05-result.json"])
    require(failed["case_id"] == "D05" and failed["status"] == "stopped"
        and failed["http_status"] == 503 and failed["physical_attempted"] is True
        and failed["usage_cost_unknown"] is True, "parent_failure_changed")
    return summary


def prepare(artifacts, *, current_code, manifest_raw, approval_raw, records):
    runtime = json.loads(artifacts["runtime"])
    paths = {"backend/" + name for name in runtime["runtime_source_hashes"]} | set(base.EXTRA_CODE_PATHS)
    require(paths | set(CODE_PATHS) <= set(current_code), "runtime_code_incomplete")
    full = base.prepare(artifacts, current_code={name: current_code[name] for name in paths})
    checkpoint(manifest_raw, approval_raw, records, full, current_code)
    code = dict(full.code_sha256)
    code.update({name: digest(current_code[name]) for name in CODE_PATHS})
    projected = replace(full, cases=full.cases[4:], code_sha256=tuple(sorted(code.items())))
    require(tuple(case.case_id for case in projected.cases) == CASE_IDS, "projection_invalid")
    return full, projected

def report(prepared):
    require(type(prepared) is PreparedTrial and tuple(c.case_id for c in prepared.cases) == CASE_IDS,
        "prepared_invalid")
    identities = [{"case_id": c.case_id, "request_sha256": c.request_sha256, "body_sha256": c.body_sha256,
        "admission_sha256": c.admission_sha256, "sources_sha256": digest(c.sources_bytes)} for c in prepared.cases]
    identity = digest(canonical({"parent": PARENT_STAGE_SHA, "receipts": PARENT_OUTPUT_PINS_SHA,
        "scope_sha256": prepared.scope_sha256, "code": dict(prepared.code_sha256), "guards": guards(), "cases": identities}))
    return {"schema": SCHEMA, "status": "preflight_passed", "preflight_identity_sha256": identity,
        "case_count": MAX_CALLS, "candidate_count": 34, "full_quality_denominator": 14,
        "preserved_cases": list(RETAINED_IDS), "preserved_physical_attempts": 5,
        "preserved_known_guard_cost_microusd": 20310, "preserved_unknown_attempts": 1,
        "parent_stage_sha256": PARENT_STAGE_SHA, "parent_output_pins_sha256": PARENT_OUTPUT_PINS_SHA,
        "runtime_code_sha256": dict(prepared.code_sha256), "guards": guards(),
        "estimated_total_input_tokens": sum(c.estimated_input_tokens for c in prepared.cases),
        "live_authorized": False, "provider_calls": 0, "database_reads": 0, "database_writes": 0,
        "independent_review_sha_verified": True, "signed_review_verified": False,
        "fresh_retained_guard_required": True, "release_gate_passed": False}
checkpoint_report = report
