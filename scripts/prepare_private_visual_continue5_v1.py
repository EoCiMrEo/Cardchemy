"""Inert exact T08–T12 continuation; full signed twelve-case inputs survive.

The seven successful outcomes are checkpointed, never supplied to transport.
Their current access/PDF/context must be rechecked before combined credit.
Old claims, HTTP 503 and all eight physical attempts remain immutable.
"""
from __future__ import annotations
from dataclasses import replace
from decimal import Decimal
import json
from types import FunctionType
import prepare_private_visual_trial_v8 as base

for _name, _value in vars(base).items():
    if not _name.startswith("__") and (not isinstance(_value, FunctionType) or _value.__module__ != base.__name__):
        globals()[_name] = _value
SCHEMA = "private_visual_continue5_v1_preflight"
LIVE_AUTHORIZED = False
CASE_IDS = tuple(f"T{i:02}" for i in range(8, 13))
RETAINED_IDS = tuple(f"T{i:02}" for i in range(1, 8))
MAX_CALLS, MAX_COST_USD = 5, Decimal("0.11")
PARENT_STAGE_SHA = "d3a1c43820f98abb6d1327a5d617b881cd7ca1acb15701a63e923a36efc70e2c"
PARENT_APPROVAL_SHA = "f2532ac78ab8e497077ad311e7a1dc125046cf1714086c7554eb9e9aed178b91"
PARENT_OUTPUT_PINS_SHA = "1524aafd9618a0f982d6924c632bcb97889274511c2fc1fdab79c0250b189b36"
CODE_PATHS = (
    "scripts/prepare_private_visual_continue5_v1.py", "scripts/run_private_visual_continue5_v1.py",
    "scripts/launch_private_visual_continue5_v1.py", "backend/scripts/execute_private_visual_continue5_v1.py",
    "backend/scripts/private_visual_continue5_entry_v1.py", "backend/scripts/rehearse_private_visual_continue5_v1.py")

def _shared(function):
    value = FunctionType(function.__code__, globals(), function.__name__, function.__defaults__, function.__closure__)
    value.__kwdefaults__ = function.__kwdefaults__
    return value

for _name in ("require", "canonical", "digest", "_bound", "_file", "_code_path", "guards", "report", "parse_supplied_response"):
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
    require(summary["schema"] == "private_visual_trial_v8_execution" and summary["status"] == "stopped"
        and summary["synthetic_interfaces"] is False and summary["provider_calls"] == 8
        and summary["completed_cases"] == 7 and summary["case_denominator"] == 12
        and summary["known_guard_cost_microusd"] == 38077 and summary["usage_unknown_attempts"] == 1
        and tuple(row["case_id"] for row in summary["cases"]) == RETAINED_IDS
        and all(summary[name] == 0 for name in ("embedding_calls", "answer_calls", "verifier_calls",
            "automatic_retries", "database_writes")), "parent_terminal_invalid")
    for frozen, observed in zip(full.cases[:7], summary["cases"], strict=True):
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
    failed = json.loads(records["T08-result.json"])
    require(failed["case_id"] == "T08" and failed["status"] == "stopped"
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
    projected = replace(full, cases=full.cases[7:], code_sha256=tuple(sorted(code.items())))
    require(tuple(case.case_id for case in projected.cases) == CASE_IDS, "projection_invalid")
    return full, projected

def checkpoint_report(prepared):
    value = report(prepared)
    value.update(parent_stage_sha256=PARENT_STAGE_SHA, parent_output_pins_sha256=PARENT_OUTPUT_PINS_SHA,
        preserved_cases=list(RETAINED_IDS), preserved_physical_attempts=8,
        preserved_known_guard_cost_microusd=38077, preserved_unknown_attempts=1,
        new_cases=list(CASE_IDS), full_quality_denominator=12, fresh_retained_guard_required=True)
    return value
