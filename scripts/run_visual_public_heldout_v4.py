"""Inert one-use continuation for 39 untouched public heldout questions.

All twenty-one observed outcomes, including two HTTP503 failures, remain in the
sixty-question denominator. The first failed trial and twenty-four prior physical
attempts remain separate history. Preparation is keyless and cannot resume the
consumed v3 worker. A fresh exact provider envelope is required for execution.
"""
from __future__ import annotations

import argparse
import asyncio
import ctypes
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import httpx
import run_visual_public_heldout_v3 as parent_trial
import score_visual_public_heldout_v2 as scorer

previous = parent_trial.previous
calibration = parent_trial.calibration
visual = parent_trial.visual
require, canonical, digest = parent_trial.require, parent_trial.canonical, parent_trial.digest
read_bound, write_new = parent_trial.read_bound, parent_trial.write_new
PilotError, ContentError = parent_trial.PilotError, parent_trial.ContentError
cost, failure_code, progress = parent_trial.cost, parent_trial.failure_code, parent_trial.progress
MODEL, ENDPOINT, ISSUED = parent_trial.MODEL, parent_trial.ENDPOINT, parent_trial.ISSUED
REPO, INPUT_ROOT = parent_trial.REPO, parent_trial.INPUT_ROOT
INPUT_FREEZE_SHA = parent_trial.INPUT_FREEZE_SHA
QUALIFICATION_FREEZE_SHA = parent_trial.QUALIFICATION_FREEZE_SHA
MAX_INPUT, MAX_OUTPUT, MAX_RESPONSE = 32768, 4096, 65536
MAX_CALLS, CALL_SECONDS, MAX_SECONDS, INTERVAL_SECONDS = 39, 120, 9000, 30
HTTP_503_COOLDOWN_SECONDS = 120
COST_CAP_MICROUSD = 850000
LIVE_AUTHORIZED = True
AUTHORIZATION_ID = "20261002_public_visual_heldout_v4_remaining39_metric_once_pinned"
APPROVAL_REPLY = "Duyệt cho lượt provider mới, duyệt lượt 39 câu công khai Q022–Q060."
OBSERVED_GROUPS = tuple(f"Q{n:03d}" for n in range(1, 22))
PARENT_GROUPS = tuple(f"Q{n:03d}" for n in range(15, 22))
FAILED_GROUPS = ("Q013", "Q014")
NEW_GROUPS = tuple(f"Q{n:03d}" for n in range(22, 61))
PARENT_REPORT_PATH = REPO / ".agent/.verification/public-heldout-v3-terminal-20261002.json"
PARENT_REPORT_SHA = "4d06b5aaaef788395cd8d5d3c737ce23db23d5fe2d7e791e93597ef87fdfac55"
PARENT_RESULT_PATH = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-public-heldout-v3-20261002-5a9c2249/result.json")
PARENT_RESULT_SHA = "10374870ceb7d1d42f6f68b99418c4c721f229a92aaf2a37826371eb5c5bdac4"
PARENT_APPROVAL_PATH = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-heldout-approval-v3-132grhl9/approval.json")
PARENT_APPROVAL_SHA = "5a9c22496a8c1dd85b859de7e6410153c31e825d192b574a812fcdcd08718552"
PARENT_OUTPUT = PARENT_RESULT_PATH.parent
PARENT_LEDGER = REPO / ".agent/.verification/visual-public-heldout-v3-ledger"
PARENT_INPUT_TOKENS, PARENT_OUTPUT_TOKENS, PARENT_COST_MICROUSD = 47643, 10366, 40212
OLD_COST_MICROUSD = parent_trial.OLD_COST_MICROUSD + PARENT_COST_MICROUSD
OLD_UNKNOWN_ATTEMPTS = 5
OLD_PHYSICAL_ATTEMPTS = 24
CODE_PATHS = parent_trial.CODE_PATHS + (
    "scripts/score_visual_public_heldout_v2.py", "scripts/run_visual_public_heldout_v4.py",
    "scripts/launch_visual_public_heldout_v4.py")
RECEIPT_FIELDS = parent_trial.RECEIPT_FIELDS
rest_body = parent_trial.rest_body


def code_hashes() -> dict:
    return {name: digest((REPO / name).read_bytes()) for name in CODE_PATHS}


def guards() -> dict:
    inherited = parent_trial.guards()
    inherited.pop("inherited_calls", None)
    return dict(inherited, max_calls=MAX_CALLS,
        input_total=MAX_CALLS * MAX_INPUT, output_total=MAX_CALLS * MAX_OUTPUT,
        new_cost_cap_microusd=COST_CAP_MICROUSD, live_authorized=LIVE_AUTHORIZED,
        inherited_evaluated_groups=21, inherited_valid_responses=19, inherited_failed_groups=2,
        inherited_known_cost_microusd=OLD_COST_MICROUSD,
        prior_unknown_cost_attempts=OLD_UNKNOWN_ATTEMPTS,
        prior_physical_attempts=OLD_PHYSICAL_ATTEMPTS, manual_failed_reattempts=0,
        inherited_outcomes_include_failures=True, untouched_requests_only=True, selected_unknown_permitted=True,
        uncertain_review_usefulness_credit=0, historical_trial_remains_failed=True,
        scorer_contract=scorer.SCHEMA_VERSION, source_id_validation="strict_issued_ids")


def ledger_dir() -> Path:
    root = REPO / ".agent/.verification/visual-public-heldout-v4-ledger"
    require(not root.is_symlink() and not root.parent.is_symlink(), "ledger_invalid")
    root.mkdir(parents=True, exist_ok=True)
    return root


def process_absent(pid: int) -> bool:
    """Recheck only recorded workers; never infer death from a stale receipt."""
    require(os.name == "nt" and type(pid) is int and pid > 0, "process_observation_unavailable")
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    kernel.OpenProcess.restype = w.HANDLE
    kernel.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    ctypes.set_last_error(0)
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        require(ctypes.get_last_error() == 87, "process_observation_unavailable")
        return True
    try:
        code = w.DWORD()
        require(bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))), "process_observation_unavailable")
        return code.value != 259
    finally:
        kernel.CloseHandle(handle)


def read_existing(path: Path, limit: int = 1000000) -> tuple[dict, str]:
    require(path.is_file() and not path.is_symlink(), "parent_artifact_missing")
    raw = path.read_bytes()
    require(0 < len(raw) <= limit, "parent_artifact_size")
    sha = digest(raw)
    return read_bound(path, sha, limit), sha


def admit_checkpoint(base: dict) -> dict:
    """Bind the stopped parent unchanged before applying a prospective metric."""
    parent_trial.validate_approval(PARENT_APPROVAL_PATH, PARENT_APPROVAL_SHA, base)
    result = read_bound(PARENT_RESULT_PATH, PARENT_RESULT_SHA, 1000000)
    report = read_bound(PARENT_REPORT_PATH, PARENT_REPORT_SHA, 1000000)
    require(result.get("schema_version") == "public_visual_heldout_v3_result" and
        result.get("authorization_id") == parent_trial.AUTHORIZATION_ID and
        result.get("approval_sha256") == PARENT_APPROVAL_SHA and
        result.get("status") == "stopped" and result.get("reason") == "quality_unreachable" and
        result.get("provider_calls") == 7 and result.get("evaluated_group_attempts") == 21 and
        result.get("total_physical_provider_calls") == 24 and result.get("historical_physical_attempts") == 17 and
        result.get("request_roster_sha256") == base["request_roster_sha256"] and
        result.get("checkpoint_binding") == base["checkpoint"]["binding"] and
        result.get("inherited_receipts") == base["checkpoint"]["receipts"] and
        result.get("first_trial_valid_receipts") == base["checkpoint"]["prior_receipts"] and
        result.get("calibration_binding") == base["calibration_binding"] and
        result.get("input_freeze_sha256") == INPUT_FREEZE_SHA and
        result.get("qualification_freeze_sha256") == QUALIFICATION_FREEZE_SHA and
        result.get("known_cost_microusd") == PARENT_COST_MICROUSD and
        result.get("combined_known_cost_microusd") == OLD_COST_MICROUSD and
        result.get("unknown_cost_attempts") == 0 and result.get("prior_unknown_cost_attempts") == 5 and
        result.get("reported_input_tokens") == PARENT_INPUT_TOKENS and
        result.get("reported_output_tokens") == PARENT_OUTPUT_TOKENS and
        result.get("old_trial_remains_failed") is True and
        result.get("resume_permitted") is result.get("ask_enabled") is result.get("private_data_sent") is False,
        "parent_terminal_binding_changed")
    require(report.get("schema") == "public_visual_heldout_v3_terminal_observation" and
        report.get("approval_sha256") == PARENT_APPROVAL_SHA and
        report.get("terminal_result_sha256") == PARENT_RESULT_SHA and
        report.get("provider_calls") == report.get("new_valid_responses") == 7 and
        report.get("new_failures") == report.get("new_unknown_cost_attempts") == report.get("selected_unissued_ids") == 0 and
        report.get("evaluated_groups") == 21 and report.get("all_historical_physical_attempts") == 24 and
        report.get("untouched_questions") == 39 and report.get("new_known_cost_microusd") == PARENT_COST_MICROUSD and
        report.get("new_input_tokens") == PARENT_INPUT_TOKENS and report.get("new_output_tokens") == PARENT_OUTPUT_TOKENS and
        report.get("prior_unknown_cost_attempts") == 5 and report.get("all_displayed_cards") == 32 and
        report.get("useful_displayed_cards") == 31 and report.get("zero_credit_unsure_cards") == 1 and
        report.get("terminal_reason") == "unknown_displayed_zero" and
        report.get("parent_checkpoint_binding_sha256") == base["checkpoint"]["binding_sha256"] and
        report.get("request_roster_sha256") == base["request_roster_sha256"] and
        report.get("caller_code_sha256") == parent_trial.code_hashes() and
        report.get("old_trial_stays_stopped") is True and
        report.get("resume_permitted") is report.get("release_passed") is False,
        "parent_observation_changed")
    require({p.name for p in PARENT_OUTPUT.glob("attempt-*.json")} ==
        {f"attempt-{g}.json" for g in PARENT_GROUPS} and
        {p.name for p in PARENT_LEDGER.glob(parent_trial.AUTHORIZATION_ID + "-Q*.claim.json")} ==
        {f"{parent_trial.AUTHORIZATION_ID}-{g}.claim.json" for g in PARENT_GROUPS} and
        set(report["receipts"]) == set(result["receipt_hashes"]) == set(PARENT_GROUPS),
        "parent_physical_attempt_roster_changed")
    controls = {}
    for role in ("launch", "execute", "run"):
        value, sha = read_existing(PARENT_LEDGER / f"{parent_trial.AUTHORIZATION_ID}.{role}-claim.json")
        require(value.get("authorization_id") == parent_trial.AUTHORIZATION_ID and
            value.get("approval_sha256") == PARENT_APPROVAL_SHA, "parent_control_claim_changed")
        if role == "launch":
            require(value.get("approval_file") == str(PARENT_APPROVAL_PATH) and
                value.get("output_dir") == str(PARENT_OUTPUT) and
                value.get("launcher_sha256") == parent_trial.code_hashes()["scripts/launch_visual_public_heldout_v3.py"],
                "parent_launch_claim_changed")
        else:
            require(value.get("request_roster_sha256") == base["request_roster_sha256"] and
                value.get("checkpoint_binding_sha256") == base["checkpoint"]["binding_sha256"],
                "parent_execution_claim_changed")
        controls[role] = {"sha256": sha, "value": value}
    resource, resource_sha = read_existing(PARENT_OUTPUT.with_name(PARENT_OUTPUT.name + ".resource-process.json"))
    complete, complete_sha = read_existing(PARENT_OUTPUT.with_name(PARENT_OUTPUT.name + ".supervisor-complete.json"))
    require(resource.get("approval_sha256") == PARENT_APPROVAL_SHA and resource.get("cpus") == 4 and
        resource.get("memory_bytes") == 2147483648 and resource.get("timeout_seconds") == 9000 and
        resource.get("kill_tree_on_close") is True and complete == {
            "approval_sha256": PARENT_APPROVAL_SHA, "exit_code": 0, "resume_permitted": False},
        "parent_resource_claim_changed")
    pids = {resource["worker_pid"], controls["launch"]["value"]["supervisor_pid"],
            controls["execute"]["value"]["pid"], controls["run"]["value"]["pid"]}
    require(all(process_absent(pid) for pid in pids), "parent_process_still_live")
    requests = {r["group_id"]: r for r in base["requests"]}
    rows = parent_trial.checkpoint_rows(base)
    receipts, bindings = {}, {}
    total_in = total_out = total_cost = 0
    starts = []
    for gid in PARENT_GROUPS:
        request = requests[gid]
        hashes = report["receipts"][gid]
        require(hashes["receipt_sha256"] == result["receipt_hashes"][gid], "parent_receipt_binding_changed")
        receipt = read_bound(PARENT_OUTPUT / f"attempt-{gid}.json", hashes["receipt_sha256"])
        claim = read_bound(PARENT_LEDGER / f"{parent_trial.AUTHORIZATION_ID}-{gid}.claim.json", hashes["claim_sha256"])
        require(set(receipt) == RECEIPT_FIELDS and receipt["group_id"] == gid and
            receipt["request_sha256"] == request["rest_sha256"] and
            receipt["attempt_claim_sha256"] == hashes["claim_sha256"] and
            claim.get("authorization_id") == parent_trial.AUTHORIZATION_ID and claim.get("group_id") == gid and
            claim.get("approval_sha256") == PARENT_APPROVAL_SHA and
            claim.get("rest_sha256") == request["rest_sha256"] and
            claim.get("checkpoint_binding_sha256") == base["checkpoint"]["binding_sha256"] and
            claim.get("reserved_microusd") == cost(MAX_INPUT, MAX_OUTPUT) and
            type(claim.get("started_epoch_ms")) is int and type(receipt["latency_ms"]) is int and
            0 <= receipt["latency_ms"] <= 121000, "parent_attempt_changed")
        start = claim["started_epoch_ms"]
        require(not starts or start - starts[-1] >= 30000, "parent_spacing_changed")
        starts.append(start)
        require(receipt["state"] == "completed" and receipt["failure_code"] is None and
            type(receipt["verdict"]) is dict, "parent_valid_receipt_changed")
        row = {k: receipt[k] for k in ("group_id", "state", "selected_ids", "question_status")}
        verdict = receipt["verdict"]
        parsed = calibration.prototype.parse_verdict(canonical({"question_status": verdict["question_status"],
            "pages": verdict["page_verdicts"]}), ISSUED)
        require(parsed == verdict and parsed["selected_ids"] == row["selected_ids"] and
            parsed["question_status"] == row["question_status"], "parent_valid_verdict_changed")
        usage = receipt["reported_usage"]
        require(type(usage) is dict and set(usage) == {"input", "output"} and
            type(usage["input"]) is type(usage["output"]) is int and
            0 < usage["input"] <= MAX_INPUT and 0 <= usage["output"] <= MAX_OUTPUT and
            receipt["known_cost_microusd"] == cost(usage["input"], usage["output"]), "parent_usage_changed")
        total_in += usage["input"]; total_out += usage["output"]; total_cost += receipt["known_cost_microusd"]
        rows.append(row)
        receipts[gid] = receipt
        bindings[gid] = {**hashes, "rest_sha256": request["rest_sha256"], "wire_sha256": request["wire_sha256"]}
    rows.sort(key=lambda row: row["group_id"])
    require(tuple(row["group_id"] for row in rows) == OBSERVED_GROUPS and
        (total_in, total_out, total_cost) == (PARENT_INPUT_TOKENS, PARENT_OUTPUT_TOKENS, PARENT_COST_MICROUSD),
        "parent_aggregate_changed")
    old_score = parent_trial.scorer.evaluate(base["overlay"], rows, base["expected_ids"])
    old_ceiling = parent_trial.scorer.ceiling(base["overlay"], rows, base["expected_ids"])
    require(canonical(old_score) == canonical(result["score"]) and
        canonical(old_ceiling) == canonical(result["ceiling"]) and
        old_ceiling["unreachable_reasons"] == ["unknown_displayed_zero"] and
        old_score["metrics"]["valid_responses"] == 19 and old_score["metrics"]["failed_groups"] == 2 and
        old_score["metrics"]["unknown_displayed_cards"] == 1 and
        old_score["metrics"]["all_displayed_cards"] == 32 and old_score["metrics"]["useful_displayed_cards"] == 31,
        "parent_historical_score_changed")
    binding = {"parent_report_sha256": PARENT_REPORT_SHA, "parent_result_sha256": PARENT_RESULT_SHA,
        "parent_approval_sha256": PARENT_APPROVAL_SHA, "parent_authorization_id": parent_trial.AUTHORIZATION_ID,
        "parent_request_roster_sha256": base["request_roster_sha256"], "prior_checkpoint": base["checkpoint"]["binding"],
        "parent_controls": controls, "parent_resource_sha256": resource_sha, "parent_complete_sha256": complete_sha,
        "receipt_bindings": bindings, "inherited_groups": list(OBSERVED_GROUPS), "inherited_failures": list(FAILED_GROUPS),
        "rows_sha256": digest(canonical(rows)), "parent_cooldown_until_epoch_ms": 0,
        "prior_physical_attempts": OLD_PHYSICAL_ATTEMPTS, "known_cost_microusd": OLD_COST_MICROUSD,
        "unknown_cost_attempts": OLD_UNKNOWN_ATTEMPTS,
        "historical_score_sha256": digest(canonical(old_score)), "historical_trial_stays_stopped": True,
        "prospective_scorer_contract": scorer.SCHEMA_VERSION, "review_unknown_credit": 0}
    return {"binding": binding, "binding_sha256": digest(canonical(binding)), "rows": rows,
            "receipts": receipts, "prior_checkpoint": base["checkpoint"]}


def checkpoint_rows(admitted: dict) -> list[dict]:
    checkpoint = admitted["checkpoint"]; binding = checkpoint["binding"]
    require(digest(canonical(binding)) == checkpoint["binding_sha256"] and
        digest(canonical(checkpoint["rows"])) == binding["rows_sha256"] and
        tuple(row["group_id"] for row in checkpoint["rows"]) == OBSERVED_GROUPS and
        set(checkpoint["receipts"]) == set(PARENT_GROUPS) and
        binding["parent_report_sha256"] == PARENT_REPORT_SHA and
        binding["parent_result_sha256"] == PARENT_RESULT_SHA and
        binding["parent_approval_sha256"] == PARENT_APPROVAL_SHA and
        binding["inherited_failures"] == list(FAILED_GROUPS) and
        [row["group_id"] for row in checkpoint["rows"] if row["state"] == "failed"] == list(FAILED_GROUPS) and
        binding["prospective_scorer_contract"] == scorer.SCHEMA_VERSION and
        binding["review_unknown_credit"] == 0 and binding["historical_trial_stays_stopped"] is True,
        "checkpoint_binding_changed")
    measured = scorer.evaluate(admitted["overlay"], checkpoint["rows"], admitted["expected_ids"])
    require(measured["metrics"]["unknown_displayed_cards"] == 1, "inherited_uncertainty_changed")
    return [dict(row) for row in checkpoint["rows"]]


def admit() -> dict:
    base = parent_trial.admit()
    checkpoint = admit_checkpoint(base)
    requests = [r for r in base["requests"] if r["group_id"] in NEW_GROUPS]
    require(tuple(r["group_id"] for r in requests) == NEW_GROUPS and len(requests) == MAX_CALLS,
        "untouched_physical_attempt_roster_changed")
    return {**base, "requests": requests, "checkpoint": checkpoint,
        "original_request_roster_sha256": base["original_request_roster_sha256"],
        "request_roster_sha256": digest(canonical(requests))}


def expected_approval(admitted: dict) -> dict:
    return {"schema_version": "public_visual_heldout_v4_approval", "authorization_id": AUTHORIZATION_ID,
        "approval_reply": APPROVAL_REPLY, "live_authorized": LIVE_AUTHORIZED, "guards": guards(),
        "code_hashes": code_hashes(), "calibration_binding": admitted["calibration_binding"],
        "input_freeze_sha256": INPUT_FREEZE_SHA, "qualification_freeze_sha256": QUALIFICATION_FREEZE_SHA,
        "request_roster_sha256": admitted["request_roster_sha256"], "public_only": True,
        "checkpoint_binding": admitted["checkpoint"]["binding"],
        "checkpoint_binding_sha256": admitted["checkpoint"]["binding_sha256"]}


def validate_approval(path: Path, sha: str, admitted: dict) -> None:
    require(read_bound(path, sha) == expected_approval(admitted), "approval_contract_changed")


async def run(admitted: dict, approval_sha: str, output: Path, send, *, ledger: Path | None = None,
              clock=time.monotonic, sleep=asyncio.sleep) -> dict:
    """Synthetic injected transport; live execution is separately fenced."""
    require(output.is_dir() and not output.is_symlink() and visual._sha(approval_sha), "output_or_approval_invalid")
    rows = checkpoint_rows(admitted)
    requests = admitted["requests"]
    require(len(requests) == MAX_CALLS and tuple(r["group_id"] for r in requests) == NEW_GROUPS and
        {r["group_id"] for r in requests} == set(admitted["expected_ids"]) - set(OBSERVED_GROUPS),
        "physical_attempt_roster_invalid")
    ledger = ledger_dir() if ledger is None else ledger
    require(ledger.is_dir() and not ledger.is_symlink(), "ledger_invalid")
    write_new(ledger / f"{AUTHORIZATION_ID}.run-claim.json", {"authorization_id": AUTHORIZATION_ID,
        "approval_sha256": approval_sha, "request_roster_sha256": admitted["request_roster_sha256"],
        "checkpoint_binding_sha256": admitted["checkpoint"]["binding_sha256"], "pid": os.getpid()})
    receipts = []; reported_input = reported_output = known_cost = unknown = 0
    started, last, cooldown_until = clock(), None, None
    parent_wait = max(0, (admitted["checkpoint"]["binding"]["parent_cooldown_until_epoch_ms"]
                         - int(time.time() * 1000)) / 1000)
    if parent_wait:
        await sleep(parent_wait)
    reason, state = "complete", "complete"
    for request in requests:
        if not scorer.ceiling(admitted["overlay"], rows, admitted["expected_ids"])["quality_reachable"]:
            reason, state = "quality_unreachable", "stopped"
            break
        wait = max(0, (last + INTERVAL_SECONDS - clock()) if last is not None else 0,
                   (cooldown_until - clock()) if cooldown_until is not None else 0)
        if wait:
            await sleep(wait)
        require(clock() - started + CALL_SECONDS <= MAX_SECONDS, "total_time_budget")
        require((len(receipts) + 1) * cost(MAX_INPUT, MAX_OUTPUT) <= COST_CAP_MICROUSD, "cost_reserve_budget")
        wire = read_bound(INPUT_ROOT / request["path"], request["wire_sha256"], visual.MAX_REQUEST_BYTES)
        body = rest_body(wire, admitted["known_images"], set())
        require(digest(body) == request["rest_sha256"], "request_changed")
        gid = request["group_id"]
        claim = {"authorization_id": AUTHORIZATION_ID, "group_id": gid, "approval_sha256": approval_sha,
            "rest_sha256": request["rest_sha256"], "checkpoint_binding_sha256": admitted["checkpoint"]["binding_sha256"],
            "started_epoch_ms": int(time.time() * 1000), "reserved_microusd": cost(MAX_INPUT, MAX_OUTPUT)}
        write_new(ledger / f"{AUTHORIZATION_ID}-{gid}.claim.json", claim)
        last = clock(); verdict = usage = failure = None; fatal = False
        try:
            async with asyncio.timeout(CALL_SECONDS):
                response = await send(body)
            verdict, usage = calibration.parse_response(response)
        except Exception as error:
            failure = failure_code(error)
            usage = error.usage if isinstance(error, ContentError) else None
            fatal = failure not in previous.TRANSIENT | previous.CONTENT_FAILURES
        if failure == "provider_http_503":
            cooldown_until = clock() + HTTP_503_COOLDOWN_SECONDS
        if usage is None:
            unknown += 1
        else:
            reported_input += usage[0]; reported_output += usage[1]; known_cost += cost(*usage)
        row = {"group_id": gid, "state": "completed" if verdict else "failed",
            "selected_ids": verdict["selected_ids"] if verdict else [],
            "question_status": verdict["question_status"] if verdict else None}
        rows.append(row)
        receipt = {**row, "request_sha256": request["rest_sha256"], "attempt_claim_sha256": digest(canonical(claim)),
            "latency_ms": int(max(0, (clock() - last) * 1000)),
            "reported_usage": {"input": usage[0], "output": usage[1]} if usage else None,
            "known_cost_microusd": cost(*usage) if usage else None, "failure_code": failure, "verdict": verdict}
        write_new(output / f"attempt-{gid}.json", receipt); receipts.append(receipt)
        progress(output, {"status": "running", "new_provider_calls": len(receipts),
            "inherited_physical_provider_calls": OLD_PHYSICAL_ATTEMPTS, "inherited_evaluated_groups": 21,
            "evaluated_groups": len(rows), "new_known_cost_microusd": known_cost,
            "inherited_known_cost_microusd": OLD_COST_MICROUSD, "unknown_cost_attempts": unknown,
            "last_group_id": gid, "last_failure_code": failure})
        if fatal or known_cost > COST_CAP_MICROUSD or reported_input > MAX_CALLS * MAX_INPUT or reported_output > MAX_CALLS * MAX_OUTPUT:
            reason, state = failure or "aggregate_budget_exceeded", "stopped"
            break
    final = {"schema_version": "public_visual_heldout_v4_result", "status": state, "reason": reason,
        "authorization_id": AUTHORIZATION_ID, "approval_sha256": approval_sha,
        "calibration_binding": admitted["calibration_binding"], "input_freeze_sha256": INPUT_FREEZE_SHA,
        "qualification_freeze_sha256": QUALIFICATION_FREEZE_SHA, "checkpoint_binding": admitted["checkpoint"]["binding"],
        "inherited_receipts": admitted["checkpoint"]["receipts"],
        "prior_checkpoint": admitted["checkpoint"]["prior_checkpoint"],
        "request_roster_sha256": admitted["request_roster_sha256"], "provider_calls": len(receipts),
        "evaluated_group_attempts": 21 + len(receipts),
        "total_physical_provider_calls": OLD_PHYSICAL_ATTEMPTS + len(receipts), "historical_physical_attempts": OLD_PHYSICAL_ATTEMPTS,
        "known_cost_microusd": known_cost, "combined_known_cost_microusd": known_cost + OLD_COST_MICROUSD,
        "unknown_cost_attempts": unknown, "prior_unknown_cost_attempts": OLD_UNKNOWN_ATTEMPTS,
        "reported_input_tokens": reported_input, "reported_output_tokens": reported_output,
        "reserved_cost_microusd": len(receipts) * cost(MAX_INPUT, MAX_OUTPUT),
        "elapsed_ms": int((clock() - started) * 1000),
        "score": scorer.evaluate(admitted["overlay"], rows, admitted["expected_ids"]),
        "ceiling": scorer.ceiling(admitted["overlay"], rows, admitted["expected_ids"]),
        "receipt_hashes": {r["group_id"]: digest(canonical(r)) for r in receipts},
        "old_trial_remains_failed": True, "resume_permitted": False, "ask_enabled": False, "private_data_sent": False}
    write_new(output / "result.json", final)
    progress(output, {"status": state, "reason": reason, "new_provider_calls": len(receipts),
        "inherited_physical_provider_calls": OLD_PHYSICAL_ATTEMPTS,
        "inherited_evaluated_groups": 21, "evaluated_groups": len(rows),
        "heldout_passed": final["score"]["heldout_passed"], "new_known_cost_microusd": known_cost,
        "inherited_known_cost_microusd": OLD_COST_MICROUSD, "unknown_cost_attempts": unknown})
    return final


def resource_worker_pid_matches(recorded_pid: object) -> bool:
    """Named Job membership must pass before accepting a direct venv parent."""
    return type(recorded_pid) is int and recorded_pid > 0 and (
        recorded_pid == os.getpid() or (os.name == "nt" and recorded_pid == os.getppid()))


async def execute(admitted: dict, approval_sha: str, output: Path, *, approval_file: Path | None = None) -> dict:
    require(LIVE_AUTHORIZED is True, "precise_provider_envelope_not_authorized")
    require(visual._inside_windows_job(), "resource_fence_required")
    require(approval_file is not None, "external_approval_required")
    resource, _ = read_existing(output.with_name(output.name + ".resource-process.json"))
    require(resource_worker_pid_matches(resource.get("worker_pid")) and
        resource.get("resource_job") == visual.RESOURCE_JOB_NAME and
        resource.get("approval_sha256") == approval_sha and resource.get("cpus") == 4 and
        resource.get("memory_bytes") == 2147483648 and resource.get("timeout_seconds") == MAX_SECONDS and
        resource.get("kill_tree_on_close") is True, "resource_receipt_invalid")
    fresh = admit()
    require(admitted == fresh, "admission_changed")
    validate_approval(approval_file, approval_sha, fresh)
    write_new(ledger_dir() / f"{AUTHORIZATION_ID}.execute-claim.json", {
        "authorization_id": AUTHORIZATION_ID, "approval_sha256": approval_sha,
        "request_roster_sha256": fresh["request_roster_sha256"],
        "checkpoint_binding_sha256": fresh["checkpoint"]["binding_sha256"], "pid": os.getpid()})
    key = previous.read_key()
    async with httpx.AsyncClient(follow_redirects=False, trust_env=False,
                                 transport=httpx.AsyncHTTPTransport(retries=0), timeout=CALL_SECONDS) as client:
        async def send(body: bytes) -> httpx.Response:
            async with client.stream("POST", ENDPOINT, content=body,
                    headers={"x-goog-api-key": key, "Content-Type": "application/json", "Accept-Encoding": "identity"}) as response:
                if response.status_code != 200:
                    return httpx.Response(response.status_code, content=b"")
                raw = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=2048):
                    raw.extend(chunk)
                    require(len(raw) <= MAX_RESPONSE, "provider_response_oversize")
                return httpx.Response(200, content=bytes(raw))
        return await run(fresh, approval_sha, output, send)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare-approval", action="store_true")
    modes.add_argument("--preflight-inputs", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--worker", action="store_true")
    parser.add_argument("--approval-file", type=Path)
    parser.add_argument("--approval-sha")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--resource-job")
    args = parser.parse_args()
    try:
        if args.worker:
            require(LIVE_AUTHORIZED is True, "precise_provider_envelope_not_authorized")
            visual.RESOURCE_JOB_NAME = visual.validate_resource_job_name(args.resource_job)
            require(visual._inside_windows_job(), "resource_fence_required")
        else:
            require(args.resource_job is None and args.output_dir is None, "internal_arguments_forbidden")
        admitted = admit()
        if args.preflight_inputs:
            require(args.approval_file is None and args.approval_sha is None, "approval_arguments_forbidden")
            measured = scorer.ceiling(admitted["overlay"], checkpoint_rows(admitted), admitted["expected_ids"])
            print(json.dumps({"status": "inputs_preflight_passed", "provider_calls": 0,
                "new_requests": MAX_CALLS, "inherited_outcomes": 21, "inherited_failed_groups": 2,
                "historical_physical_attempts": OLD_PHYSICAL_ATTEMPTS,
                "quality_reachable": measured["quality_reachable"], "live_authorized": LIVE_AUTHORIZED}))
            return 0
        if args.prepare_approval:
            require(args.approval_file is None and args.approval_sha is None, "approval_arguments_forbidden")
            root = Path(tempfile.mkdtemp(prefix="cardchemy-visual-heldout-approval-v4-"))
            receipt = expected_approval(admitted)
            write_new(root / "approval.json", receipt)
            print(json.dumps({"approval_file": str(root / "approval.json"), "approval_sha256": digest(canonical(receipt)),
                              "provider_calls": 0, "new_requests": MAX_CALLS, "live_authorized": LIVE_AUTHORIZED}))
            return 0
        require(args.approval_file is not None and args.approval_sha is not None, "external_approval_required")
        validate_approval(args.approval_file, args.approval_sha, admitted)
        if args.preflight:
            print(json.dumps({"status": "preflight_passed", "provider_calls": 0}))
            return 0
        output = args.output_dir
        require(output is not None and output.is_absolute() and not output.exists() and not output.is_symlink()
                and output.resolve().parent == Path(tempfile.gettempdir()).resolve(), "fresh_temp_output_required")
        output.mkdir()
        try:
            asyncio.run(execute(admitted, args.approval_sha, output, approval_file=args.approval_file))
        except Exception as error:
            write_new(output / "worker-failure.json", {"status": "stopped", "reason": failure_code(error),
                      "resume_permitted": False, "cost_may_be_unknown": True})
            return 2
        return 0
    except Exception as error:
        print(json.dumps({"status": "pilot_rejected", "reason": failure_code(error)}))
        return 2

if __name__ == "__main__":
    sys.exit(main())
