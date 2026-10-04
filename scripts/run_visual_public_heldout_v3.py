"""Inert one-use continuation for 46 untouched public heldout questions.

All fourteen observed outcomes, including two HTTP503 failures, remain in the
sixty-question denominator. The first failed trial and seventeen prior physical
attempts remain separate history. Preparation is keyless and cannot resume the
consumed v2 worker. A fresh exact provider envelope is required for execution.
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
import run_visual_public_heldout_v2 as parent_trial

previous = parent_trial.previous
calibration = parent_trial.calibration
visual = parent_trial.visual
scorer = parent_trial.scorer
require, canonical, digest = parent_trial.require, parent_trial.canonical, parent_trial.digest
read_bound, write_new = parent_trial.read_bound, parent_trial.write_new
PilotError, ContentError = parent_trial.PilotError, parent_trial.ContentError
cost, failure_code, progress = parent_trial.cost, parent_trial.failure_code, parent_trial.progress
MODEL, ENDPOINT, ISSUED = parent_trial.MODEL, parent_trial.ENDPOINT, parent_trial.ISSUED
REPO, INPUT_ROOT = parent_trial.REPO, parent_trial.INPUT_ROOT
INPUT_FREEZE_SHA = parent_trial.INPUT_FREEZE_SHA
QUALIFICATION_FREEZE_SHA = parent_trial.QUALIFICATION_FREEZE_SHA
MAX_INPUT, MAX_OUTPUT, MAX_RESPONSE = 32768, 4096, 65536
MAX_CALLS, CALL_SECONDS, MAX_SECONDS, INTERVAL_SECONDS = 46, 120, 9000, 30
HTTP_503_COOLDOWN_SECONDS = 120
COST_CAP_MICROUSD = 1000000
LIVE_AUTHORIZED = True
AUTHORIZATION_ID = "20261002_public_visual_heldout_v3_remaining46_once_pinned"
APPROVAL_REPLY = "Duyệt đúng lượt 46 câu công khai"
OBSERVED_GROUPS = tuple(f"Q{n:03d}" for n in range(1, 15))
PARENT_GROUPS = tuple(g for g in OBSERVED_GROUPS if g not in parent_trial.OLD_SUCCESS_GROUPS)
FAILED_GROUPS = ("Q013", "Q014")
NEW_GROUPS = tuple(f"Q{n:03d}" for n in range(15, 61))
PARENT_REPORT_PATH = REPO / ".agent/.verification/public-heldout-v2-interrupted-20261002.json"
PARENT_REPORT_SHA = "59f6147432ad4f562cb73f4faaf317fa3e9de44d92f15cac104d4f5324c95615"
PARENT_APPROVAL_PATH = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-heldout-approval-v2-0tm1pwc6/approval.json")
PARENT_APPROVAL_SHA = "35b47bb9bc6e08d103bc806ddf1bd4a19835be7ba85c43c254c5de82d4981488"
PARENT_OUTPUT = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-public-heldout-v2-20261002-35b47bb9")
PARENT_LEDGER = REPO / ".agent/.verification/visual-public-heldout-v2-ledger"
PARENT_INPUT_TOKENS, PARENT_OUTPUT_TOKENS, PARENT_COST_MICROUSD = 61580, 15813, 58010
OLD_COST_MICROUSD = parent_trial.OLD_COST_MICROUSD + PARENT_COST_MICROUSD
OLD_UNKNOWN_ATTEMPTS = 5
OLD_PHYSICAL_ATTEMPTS = 17
CODE_PATHS = parent_trial.CODE_PATHS + (
    "scripts/run_visual_public_heldout_v3.py", "scripts/launch_visual_public_heldout_v3.py")
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
        inherited_evaluated_groups=14, inherited_valid_responses=12, inherited_failed_groups=2,
        inherited_known_cost_microusd=OLD_COST_MICROUSD,
        prior_unknown_cost_attempts=OLD_UNKNOWN_ATTEMPTS,
        prior_physical_attempts=OLD_PHYSICAL_ATTEMPTS, manual_failed_reattempts=0,
        inherited_outcomes_include_failures=True, untouched_requests_only=True)


def ledger_dir() -> Path:
    root = REPO / ".agent/.verification/visual-public-heldout-v3-ledger"
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
    """Verify every observed request/receipt and all consumed trial bindings."""
    parent_trial.validate_approval(PARENT_APPROVAL_PATH, PARENT_APPROVAL_SHA, base)
    report = read_bound(PARENT_REPORT_PATH, PARENT_REPORT_SHA, 1000000)
    require(report.get("schema") == "public_visual_heldout_v2_interrupted_observation" and
        report.get("status") == "interrupted_processes_absent" and
        report.get("approval_sha256") == PARENT_APPROVAL_SHA and
        report.get("request_roster_sha256") == base["request_roster_sha256"] and
        report.get("checkpoint_binding_sha256") == base["checkpoint"]["binding_sha256"] and
        report.get("caller_code_sha256") == parent_trial.code_hashes() and
        report.get("new_physical_claims") == report.get("new_receipts") == 11 and
        report.get("valid_new_responses") == 9 and report.get("evaluated_groups") == 14 and
        report.get("all_physical_attempts") == 17 and
        report.get("in_flight_claims_without_receipt") == 0 and
        report.get("new_known_cost_microusd") == PARENT_COST_MICROUSD and
        report.get("inherited_known_cost_microusd") == parent_trial.OLD_COST_MICROUSD and
        report.get("new_reported_input_tokens") == PARENT_INPUT_TOKENS and
        report.get("new_reported_output_tokens") == PARENT_OUTPUT_TOKENS and
        report.get("new_unknown_cost_attempts") == 2 and report.get("prior_unknown_cost_attempts") == 3 and
        report.get("failures") == {g: "provider_http_503" for g in FAILED_GROUPS} and
        report.get("resume_permitted") is report.get("provider_restarted") is
        report.get("ask_enabled") is report.get("private_data_sent") is report.get("release_passed") is False,
        "parent_observation_changed")
    require(not (PARENT_OUTPUT / "result.json").exists(), "parent_terminal_state_changed")
    require({p.name for p in PARENT_OUTPUT.glob("attempt-*.json")} ==
        {f"attempt-{g}.json" for g in PARENT_GROUPS} and
        {p.name for p in PARENT_LEDGER.glob(parent_trial.AUTHORIZATION_ID + "-Q*.claim.json")} ==
        {f"{parent_trial.AUTHORIZATION_ID}-{g}.claim.json" for g in PARENT_GROUPS} and
        set(report["receipts"]) == set(PARENT_GROUPS), "parent_physical_attempt_roster_changed")
    controls = {}
    for role in ("launch", "execute", "run"):
        value, sha = read_existing(PARENT_LEDGER / f"{parent_trial.AUTHORIZATION_ID}.{role}-claim.json")
        require(value.get("authorization_id") == parent_trial.AUTHORIZATION_ID and
            value.get("approval_sha256") == PARENT_APPROVAL_SHA, "parent_control_claim_changed")
        if role == "launch":
            require(value.get("approval_file") == str(PARENT_APPROVAL_PATH) and
                value.get("output_dir") == str(PARENT_OUTPUT) and
                value.get("launcher_sha256") == parent_trial.code_hashes()["scripts/launch_visual_public_heldout_v2.py"],
                "parent_launch_claim_changed")
        else:
            require(value.get("request_roster_sha256") == base["request_roster_sha256"] and
                value.get("checkpoint_binding_sha256") == base["checkpoint"]["binding_sha256"],
                "parent_execution_claim_changed")
        controls[role] = {"sha256": sha, "value": value}
    resource, resource_sha = read_existing(PARENT_OUTPUT.with_name(PARENT_OUTPUT.name + ".resource-process.json"))
    launch, launch_sha = read_existing(PARENT_OUTPUT.with_name(PARENT_OUTPUT.name + ".launch-process.json"))
    require(resource.get("approval_sha256") == launch.get("approval_sha256") == PARENT_APPROVAL_SHA and
        resource.get("cpus") == 4 and resource.get("memory_bytes") == 2147483648 and
        resource.get("timeout_seconds") == 9000 and resource.get("kill_tree_on_close") is True and
        launch.get("output_dir") == str(PARENT_OUTPUT), "parent_resource_claim_changed")
    pids = {resource["worker_pid"], launch["supervisor_pid"], controls["execute"]["value"]["pid"],
            controls["run"]["value"]["pid"]}
    require(all(process_absent(pid) for pid in pids), "parent_process_still_live")
    requests = {r["group_id"]: r for r in base["requests"]}
    rows = parent_trial.checkpoint_rows(base)
    receipts, bindings = {}, {}
    total_in = total_out = total_cost = 0
    starts, cooldown_after = [], None
    for gid in PARENT_GROUPS:
        request = requests[gid]
        hashes = report["receipts"][gid]
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
        require(cooldown_after is None or start >= cooldown_after, "parent_cooldown_changed")
        starts.append(start)
        row = {k: receipt[k] for k in ("group_id", "state", "selected_ids", "question_status")}
        if gid in FAILED_GROUPS:
            require(receipt["state"] == "failed" and receipt["failure_code"] == "provider_http_503" and
                receipt["selected_ids"] == [] and receipt["question_status"] is None and
                receipt["verdict"] is receipt["reported_usage"] is receipt["known_cost_microusd"] is None,
                "parent_failure_changed")
            cooldown_after = start + receipt["latency_ms"] + HTTP_503_COOLDOWN_SECONDS * 1000
        else:
            require(receipt["state"] == "completed" and receipt["failure_code"] is None and
                type(receipt["verdict"]) is dict, "parent_valid_receipt_changed")
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
    rows.sort(key=lambda r: r["group_id"])
    require(tuple(r["group_id"] for r in rows) == OBSERVED_GROUPS and
        (total_in, total_out, total_cost) == (PARENT_INPUT_TOKENS, PARENT_OUTPUT_TOKENS, PARENT_COST_MICROUSD),
        "parent_aggregate_changed")
    score, ceiling = scorer.evaluate(base["overlay"], rows, base["expected_ids"]), scorer.ceiling(base["overlay"], rows, base["expected_ids"])
    require(canonical(score) == canonical(report["partial_score"]) and
        canonical(ceiling) == canonical(report["ceiling"]) and ceiling["quality_reachable"] is True and
        score["metrics"]["valid_responses"] == 12 and score["metrics"]["failed_groups"] == 2,
        "parent_partial_score_changed")
    binding = {"parent_report_sha256": PARENT_REPORT_SHA, "parent_approval_sha256": PARENT_APPROVAL_SHA,
        "parent_authorization_id": parent_trial.AUTHORIZATION_ID, "parent_request_roster_sha256": base["request_roster_sha256"],
        "prior_checkpoint": base["checkpoint"]["binding"], "parent_controls": controls,
        "parent_resource_sha256": resource_sha, "parent_launch_sha256": launch_sha,
        "receipt_bindings": bindings, "inherited_groups": list(OBSERVED_GROUPS),
        "inherited_failures": list(FAILED_GROUPS), "rows_sha256": digest(canonical(rows)),
        "parent_cooldown_until_epoch_ms": cooldown_after,
        "prior_physical_attempts": OLD_PHYSICAL_ATTEMPTS, "known_cost_microusd": OLD_COST_MICROUSD,
        "unknown_cost_attempts": OLD_UNKNOWN_ATTEMPTS}
    return {"binding": binding, "binding_sha256": digest(canonical(binding)), "rows": rows,
            "receipts": receipts, "prior_receipts": base["checkpoint"]["receipts"]}


def checkpoint_rows(admitted: dict) -> list[dict]:
    checkpoint = admitted["checkpoint"]; binding = checkpoint["binding"]
    require(digest(canonical(binding)) == checkpoint["binding_sha256"] and
        digest(canonical(checkpoint["rows"])) == binding["rows_sha256"] and
        tuple(r["group_id"] for r in checkpoint["rows"]) == OBSERVED_GROUPS and
        set(checkpoint["receipts"]) == set(PARENT_GROUPS) and
        set(checkpoint["prior_receipts"]) == set(parent_trial.OLD_SUCCESS_GROUPS) and
        binding["parent_report_sha256"] == PARENT_REPORT_SHA and
        binding["parent_approval_sha256"] == PARENT_APPROVAL_SHA and
        binding["inherited_failures"] == list(FAILED_GROUPS) and
        [r["group_id"] for r in checkpoint["rows"] if r["state"] == "failed"] == list(FAILED_GROUPS),
        "checkpoint_binding_changed")
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
    return {"schema_version": "public_visual_heldout_v3_approval", "authorization_id": AUTHORIZATION_ID,
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
            "inherited_physical_provider_calls": OLD_PHYSICAL_ATTEMPTS, "inherited_evaluated_groups": 14,
            "evaluated_groups": len(rows), "new_known_cost_microusd": known_cost,
            "inherited_known_cost_microusd": OLD_COST_MICROUSD, "unknown_cost_attempts": unknown,
            "last_group_id": gid, "last_failure_code": failure})
        if fatal or known_cost > COST_CAP_MICROUSD or reported_input > MAX_CALLS * MAX_INPUT or reported_output > MAX_CALLS * MAX_OUTPUT:
            reason, state = failure or "aggregate_budget_exceeded", "stopped"
            break
    final = {"schema_version": "public_visual_heldout_v3_result", "status": state, "reason": reason,
        "authorization_id": AUTHORIZATION_ID, "approval_sha256": approval_sha,
        "calibration_binding": admitted["calibration_binding"], "input_freeze_sha256": INPUT_FREEZE_SHA,
        "qualification_freeze_sha256": QUALIFICATION_FREEZE_SHA, "checkpoint_binding": admitted["checkpoint"]["binding"],
        "inherited_receipts": admitted["checkpoint"]["receipts"],
        "first_trial_valid_receipts": admitted["checkpoint"]["prior_receipts"],
        "request_roster_sha256": admitted["request_roster_sha256"], "provider_calls": len(receipts),
        "evaluated_group_attempts": 14 + len(receipts),
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
        "inherited_evaluated_groups": 14, "evaluated_groups": len(rows),
        "heldout_passed": final["score"]["heldout_passed"], "new_known_cost_microusd": known_cost,
        "inherited_known_cost_microusd": OLD_COST_MICROUSD, "unknown_cost_attempts": unknown})
    return final


async def execute(admitted: dict, approval_sha: str, output: Path, *, approval_file: Path | None = None) -> dict:
    require(LIVE_AUTHORIZED is True, "precise_provider_envelope_not_authorized")
    require(visual._inside_windows_job(), "resource_fence_required")
    require(approval_file is not None, "external_approval_required")
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
                "new_requests": MAX_CALLS, "inherited_outcomes": 14, "inherited_failed_groups": 2,
                "historical_physical_attempts": OLD_PHYSICAL_ATTEMPTS,
                "quality_reachable": measured["quality_reachable"], "live_authorized": LIVE_AUTHORIZED}))
            return 0
        if args.prepare_approval:
            require(args.approval_file is None and args.approval_sha is None, "approval_arguments_forbidden")
            root = Path(tempfile.mkdtemp(prefix="cardchemy-visual-heldout-approval-v3-"))
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
