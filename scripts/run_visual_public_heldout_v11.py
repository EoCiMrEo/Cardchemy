"""Inert public successor: manual Q056 and 4 untouched cases.

No provider envelope is authorized. Prospective v4 parser; identical frozen wire.
A precise five-request approval is required. Old receipts,
labels, code and stopped results stay immutable. Preparation is keyless.
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
import public_visual_parser_equivalence_v1 as parser_equivalence

production_parser = parser_equivalence.candidate
PARSER_PROOF_SHA = "3465fa6f5d97b7d4cea26e4551776d2337232a863c814ada7c64f2dfe1a0e256"
import run_visual_public_heldout_v10 as parent_trial
import public_trial_process_identity_v5 as process_identity

previous = parent_trial.previous
calibration = parent_trial.calibration
visual = parent_trial.visual
scorer = parent_trial.scorer
require, canonical, digest = parent_trial.require, parent_trial.canonical, parent_trial.digest
write_new = parent_trial.write_new
LOCAL_METADATA_BYTES = 524288
PilotError, ContentError = parent_trial.PilotError, parent_trial.ContentError
cost, failure_code, progress = parent_trial.cost, parent_trial.failure_code, parent_trial.progress
MODEL, ENDPOINT, ISSUED = parent_trial.MODEL, parent_trial.ENDPOINT, parent_trial.ISSUED
REPO, INPUT_ROOT = parent_trial.REPO, parent_trial.INPUT_ROOT
INPUT_FREEZE_SHA = parent_trial.INPUT_FREEZE_SHA
QUALIFICATION_FREEZE_SHA = parent_trial.QUALIFICATION_FREEZE_SHA
MAX_INPUT, MAX_OUTPUT, MAX_RESPONSE = 32768, 4096, 65536
MAX_CALLS, CALL_SECONDS, MAX_SECONDS, INTERVAL_SECONDS = 5, 120, 9000, 30
HTTP_503_COOLDOWN_SECONDS = 120
COST_CAP_MICROUSD = 110000
LIVE_AUTHORIZED = True
AUTHORIZATION_ID = "20261002_public_visual_heldout_v11_manual56_remaining4_once_pinned"
APPROVAL_REPLY = "Duyệt đúng lượt 5 câu với parser mới"
OBSERVED_GROUPS = tuple(f"Q{n:03d}" for n in range(1, 57))
ACTIVE_INHERITED_GROUPS = tuple(g for g in OBSERVED_GROUPS if g != "Q056")
PARENT_GROUPS = ("Q056",)
FAILED_GROUPS = ("Q013", "Q014")
PARENT_FAILED_GROUPS = (*FAILED_GROUPS, "Q056")
MANUAL_GROUPS = ("Q056",)
NEW_GROUPS = tuple(f"Q{n:03d}" for n in range(56, 61))
PARENT_REPORT_PATH = REPO / ".agent/.verification/public-heldout-v10-terminal-20261002.json"
PARENT_REPORT_SHA = "a2921593d26c6285a71698584e37f6e21c1a803f51f533b1ffd00ae94e6836d6"
PARENT_RESULT_PATH = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-public-heldout-v10-20261002-d1a171bb/result.json")
PARENT_RESULT_SHA = "e01245c3c247baef93cb3cd1d98bad88cbb09ade02c3ce0f73ae159d4e508e65"
PARENT_APPROVAL_PATH = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-heldout-approval-v10-gbmiy7b6/approval.json")
PARENT_APPROVAL_SHA = "d1a171bb12a145fc4342907b999f236c8438121f139268b1b3017ee892a6dd07"
PARENT_OUTPUT = PARENT_RESULT_PATH.parent
PARENT_LEDGER = REPO / ".agent/.verification/visual-public-heldout-v10-ledger"
PARENT_INPUT_TOKENS, PARENT_OUTPUT_TOKENS, PARENT_COST_MICROUSD = 6898, 1371, 5497
OLD_COST_MICROUSD = parent_trial.OLD_COST_MICROUSD + PARENT_COST_MICROUSD
OLD_UNKNOWN_ATTEMPTS = 8
OLD_PHYSICAL_ATTEMPTS = 65
CODE_PATHS = parent_trial.CODE_PATHS + (
    "scripts/run_visual_public_heldout_v11.py", "scripts/launch_visual_public_heldout_v11.py",
    "scripts/public_trial_process_identity_v5.py",
    "scripts/public_visual_parser_equivalence_v1.py",
    "backend/tests/test_visual_public_heldout_v11_caller.py",
    "backend/tests/test_public_trial_process_identity_v5.py",
    "backend/tests/test_public_visual_parser_equivalence_v1.py",
    ".agent/.verification/visual-parser-v4-equivalence-20261002.json",
) + tuple(name for name in parser_equivalence.PARSER_CODE_PATHS if name != "scripts/public_visual_parser_equivalence_v1.py")
RECEIPT_FIELDS = parent_trial.RECEIPT_FIELDS | {"verdict_failure_subcode"}
rest_body = parent_trial.rest_body
read_existing, process_absent = parent_trial.read_existing, parent_trial.process_absent


def read_bound(path: Path, sha: str, cap: int = LOCAL_METADATA_BYTES) -> dict:
    # Growing immutable checkpoint metadata is local. Explicit request/image
    # caps and provider response caps remain exactly the approved envelope.
    return parent_trial.read_bound(path, sha, cap)


def code_hashes() -> dict:
    return {name: digest((REPO / name).read_bytes()) for name in CODE_PATHS}


def guards() -> dict:
    return dict(parent_trial.guards(), max_calls=MAX_CALLS,
        input_total=MAX_CALLS * MAX_INPUT, output_total=MAX_CALLS * MAX_OUTPUT,
        new_cost_cap_microusd=COST_CAP_MICROUSD, live_authorized=LIVE_AUTHORIZED,
        local_metadata_bytes=LOCAL_METADATA_BYTES,
        consumed_process_identity="public_consumed_process_identity_v5",
        inherited_evaluated_groups=56, active_inherited_outcomes=55,
        inherited_valid_responses=53, inherited_failed_groups=2,
        inherited_known_cost_microusd=OLD_COST_MICROUSD,
        prior_unknown_cost_attempts=OLD_UNKNOWN_ATTEMPTS,
        prior_physical_attempts=OLD_PHYSICAL_ATTEMPTS, manual_failed_reattempts=1,
        untouched_requests_only=False, manual_group_ids=list(MANUAL_GROUPS),
        superseded_failed_outcomes_remain_history=True,
        prospective_parser=production_parser.CONTRACT_VERSION, candidate_local_repair=True,
        mixed_historical_parser_lineage=True, historical_failures_reconstructed=False)


def ledger_dir() -> Path:
    root = REPO / ".agent/.verification/visual-public-heldout-v11-ledger"
    require(not root.is_symlink() and not root.parent.is_symlink(), "ledger_invalid")
    root.mkdir(parents=True, exist_ok=True)
    return root


def admit_checkpoint(base: dict, *, process_observer=process_absent) -> dict:
    parent_trial.validate_approval(PARENT_APPROVAL_PATH, PARENT_APPROVAL_SHA, base)
    result = read_bound(PARENT_RESULT_PATH, PARENT_RESULT_SHA)
    report = read_bound(PARENT_REPORT_PATH, PARENT_REPORT_SHA)
    require(result["schema_version"] == "public_visual_heldout_v10_result" and
        result["authorization_id"] == parent_trial.AUTHORIZATION_ID and
        result["approval_sha256"] == PARENT_APPROVAL_SHA and
        result["status"] == "stopped" and result["reason"] == "quality_unreachable" and
        result["provider_calls"] == 1 and result["evaluated_group_attempts"] == 56 and
        result["total_physical_provider_calls"] == OLD_PHYSICAL_ATTEMPTS and
        result["historical_physical_attempts"] == parent_trial.OLD_PHYSICAL_ATTEMPTS and
        result["checkpoint_binding"] == base["checkpoint"]["binding"] and
        result["inherited_receipts"] == base["checkpoint"]["receipts"] and
        result["prior_checkpoint"] == base["checkpoint"]["prior_checkpoint"] and
        result["calibration_binding"] == base["calibration_binding"] and
        result["input_freeze_sha256"] == INPUT_FREEZE_SHA and
        result["qualification_freeze_sha256"] == QUALIFICATION_FREEZE_SHA and
        result["request_roster_sha256"] == base["request_roster_sha256"] and
        result["known_cost_microusd"] == PARENT_COST_MICROUSD and
        result["combined_known_cost_microusd"] == OLD_COST_MICROUSD and
        result["reported_input_tokens"] == PARENT_INPUT_TOKENS and
        result["reported_output_tokens"] == PARENT_OUTPUT_TOKENS and
        result["unknown_cost_attempts"] == 0 and result["prior_unknown_cost_attempts"] == 8 and
        result["old_trial_remains_failed"] is True and
        result["resume_permitted"] is result["ask_enabled"] is result["private_data_sent"] is False,
        "parent_terminal_binding_changed")
    require(report["schema"] == "public_visual_heldout_v10_terminal_observation" and
        report["terminal_result_sha256"] == PARENT_RESULT_SHA and
        report["approval_sha256"] == PARENT_APPROVAL_SHA and
        report["failed_evaluated_groups"] == list(PARENT_FAILED_GROUPS) and
        report["caller_code_sha256"] == parent_trial.code_hashes() and
        report["caller_hashes_match"] is report["recorded_processes_absent"] is True,
        "parent_observation_changed")
    controls = {}
    for role in ("launch", "execute", "run"):
        claim, sha = read_existing(PARENT_LEDGER / f"{parent_trial.AUTHORIZATION_ID}.{role}-claim.json")
        require(claim["authorization_id"] == parent_trial.AUTHORIZATION_ID and
            claim["approval_sha256"] == PARENT_APPROVAL_SHA and sha == report["controls"][role]["sha256"],
            "parent_control_claim_changed")
        if role == "launch":
            require(claim["approval_file"] == str(PARENT_APPROVAL_PATH) and
                claim["output_dir"] == str(PARENT_OUTPUT) and
                claim["launcher_sha256"] == parent_trial.code_hashes()["scripts/launch_visual_public_heldout_v10.py"],
                "parent_launch_claim_changed")
        else:
            require(claim["request_roster_sha256"] == base["request_roster_sha256"] and
                claim["checkpoint_binding_sha256"] == base["checkpoint"]["binding_sha256"],
                "parent_execution_claim_changed")
        controls[role] = {"sha256": sha, "value": claim}
    resource, resource_sha = read_existing(PARENT_OUTPUT.with_name(PARENT_OUTPUT.name + ".resource-process.json"))
    complete, complete_sha = read_existing(PARENT_OUTPUT.with_name(PARENT_OUTPUT.name + ".supervisor-complete.json"))
    require(resource_sha == report["resource_receipt_sha256"] and complete_sha == report["supervisor_complete_sha256"] and
        resource["approval_sha256"] == PARENT_APPROVAL_SHA and resource["cpus"] == 4 and
        resource["memory_bytes"] == 2147483648 and resource["timeout_seconds"] == MAX_SECONDS and
        resource["kill_tree_on_close"] is True and
        complete == {"approval_sha256": PARENT_APPROVAL_SHA, "exit_code": 0, "resume_permitted": False},
        "parent_resource_claim_changed")
    pids = {resource["worker_pid"], controls["launch"]["value"]["supervisor_pid"],
        controls["execute"]["value"]["pid"], controls["run"]["value"]["pid"]}
    require(all(process_observer(pid) for pid in pids), "parent_process_still_live")
    require({p.name for p in PARENT_OUTPUT.glob("attempt-*.json")} ==
        {f"attempt-{g}.json" for g in PARENT_GROUPS} and
        {p.name for p in PARENT_LEDGER.glob(parent_trial.AUTHORIZATION_ID + "-Q*.claim.json")} ==
        {f"{parent_trial.AUTHORIZATION_ID}-{g}.claim.json" for g in PARENT_GROUPS} and
        set(result["receipt_hashes"]) == set(report["receipts"]) == set(PARENT_GROUPS), "parent_roster_changed")
    requests = {r["group_id"]: r for r in base["requests"]}
    rows = parent_trial.checkpoint_rows(base)
    receipts, bindings, starts = {}, {}, []
    total_in = total_out = total_cost = total_unknown = 0
    for gid in PARENT_GROUPS:
        hashes, request = report["receipts"][gid], requests[gid]
        require(hashes["receipt_sha256"] == result["receipt_hashes"][gid], "parent_receipt_binding_changed")
        receipt = read_bound(PARENT_OUTPUT / f"attempt-{gid}.json", hashes["receipt_sha256"])
        claim = read_bound(PARENT_LEDGER / f"{parent_trial.AUTHORIZATION_ID}-{gid}.claim.json", hashes["claim_sha256"])
        require(set(receipt) == parent_trial.RECEIPT_FIELDS and receipt["group_id"] == gid and
            receipt["request_sha256"] == request["rest_sha256"] and receipt["attempt_claim_sha256"] == hashes["claim_sha256"] and
            claim["authorization_id"] == parent_trial.AUTHORIZATION_ID and claim["group_id"] == gid and
            claim["approval_sha256"] == PARENT_APPROVAL_SHA and claim["rest_sha256"] == request["rest_sha256"] and
            claim["checkpoint_binding_sha256"] == base["checkpoint"]["binding_sha256"] and
            claim["reserved_microusd"] == cost(MAX_INPUT, MAX_OUTPUT) and
            type(claim["started_epoch_ms"]) is int and type(receipt["latency_ms"]) is int and
            0 <= receipt["latency_ms"] <= 121000, "parent_attempt_changed")
        starts.append(claim["started_epoch_ms"])
        require(receipt["verdict_failure_subcode"] == ("cue_without_useful_page" if gid == "Q056" else None), "parent_diagnostic_changed")
        require(len(starts) == 1 or starts[-1] - starts[-2] >= 30000, "parent_spacing_changed")
        usage = receipt["reported_usage"]
        require(type(usage) is dict and set(usage) == {"input", "output"} and
            type(usage["input"]) is type(usage["output"]) is int and
            0 < usage["input"] <= MAX_INPUT and 0 <= usage["output"] <= MAX_OUTPUT and
            receipt["known_cost_microusd"] == cost(usage["input"], usage["output"]), "parent_usage_changed")
        row = {k: receipt[k] for k in ("group_id", "state", "selected_ids", "question_status")}
        if gid == "Q056":
            require(receipt["state"] == "failed" and receipt["failure_code"] == "provider_verdict_invalid" and
                receipt["selected_ids"] == [] and receipt["question_status"] is receipt["verdict"] is None,
                "parent_failed_receipt_changed")
        else:
            require(receipt["state"] == "completed" and receipt["failure_code"] is None and type(receipt["verdict"]) is dict,
                "parent_valid_receipt_changed")
            verdict = receipt["verdict"]
            parsed = calibration.prototype.parse_verdict(canonical({"question_status": verdict["question_status"],
                "pages": verdict["page_verdicts"]}), ISSUED)
            require(parsed == verdict and parsed["selected_ids"] == row["selected_ids"] and
                parsed["question_status"] == row["question_status"], "parent_valid_verdict_changed")
        rows.append(row); receipts[gid] = receipt
        bindings[gid] = {**hashes, "rest_sha256": request["rest_sha256"], "wire_sha256": request["wire_sha256"]}
        if usage is not None:
            total_in += usage["input"]; total_out += usage["output"]; total_cost += receipt["known_cost_microusd"]
    rows.sort(key=lambda row: row["group_id"])
    require(tuple(r["group_id"] for r in rows) == OBSERVED_GROUPS and
        (total_in, total_out, total_cost) == (PARENT_INPUT_TOKENS, PARENT_OUTPUT_TOKENS, PARENT_COST_MICROUSD),
        "parent_aggregate_changed")
    require(total_unknown == 0, "parent_unknown_count_changed")
    old_score = scorer.evaluate(base["overlay"], rows, base["expected_ids"])
    old_ceiling = scorer.ceiling(base["overlay"], rows, base["expected_ids"])
    require(canonical(old_score) == canonical(result["score"]) and canonical(old_ceiling) == canonical(result["ceiling"]) and
        old_ceiling["unreachable_reasons"] == ["availability", "error_budget"] and
        old_score["metrics"]["valid_responses"] == 53 and old_score["metrics"]["failed_groups"] == 3,
        "parent_historical_score_changed")
    active = [r for r in rows if r["group_id"] != "Q056"]
    binding = {"parent_report_sha256": PARENT_REPORT_SHA, "parent_result_sha256": PARENT_RESULT_SHA,
        "parent_approval_sha256": PARENT_APPROVAL_SHA, "parent_authorization_id": parent_trial.AUTHORIZATION_ID,
        "parent_request_roster_sha256": base["request_roster_sha256"], "parent_checkpoint": base["checkpoint"]["binding"],
        "parent_controls": controls, "parent_resource_sha256": resource_sha, "parent_complete_sha256": complete_sha,
        "receipt_bindings": bindings, "all_observed_rows_sha256": digest(canonical(rows)),
        "rows_sha256": digest(canonical(active)), "inherited_failures": list(FAILED_GROUPS),
        "manual_failed_group_ids": list(MANUAL_GROUPS), "superseded_failed_outcomes": [r for r in rows if r["group_id"] == "Q056"],
        "parent_cooldown_until_epoch_ms": 0, "historical_physical_attempts": OLD_PHYSICAL_ATTEMPTS,
        "known_cost_microusd": OLD_COST_MICROUSD, "unknown_cost_attempts": OLD_UNKNOWN_ATTEMPTS,
        "historical_score_sha256": digest(canonical(old_score)), "historical_trial_stays_stopped": True}
    return {"binding": binding, "binding_sha256": digest(canonical(binding)), "rows": active,
        "all_observed_rows": rows, "receipts": receipts, "prior_checkpoint": base["checkpoint"]}


def checkpoint_rows(admitted: dict) -> list[dict]:
    checkpoint, binding = admitted["checkpoint"], admitted["checkpoint"]["binding"]
    require(digest(canonical(binding)) == checkpoint["binding_sha256"] and
        digest(canonical(checkpoint["rows"])) == binding["rows_sha256"] and
        digest(canonical(checkpoint["all_observed_rows"])) == binding["all_observed_rows_sha256"] and
        tuple(r["group_id"] for r in checkpoint["rows"]) == ACTIVE_INHERITED_GROUPS and
        tuple(r["group_id"] for r in checkpoint["all_observed_rows"]) == OBSERVED_GROUPS and
        [r["group_id"] for r in checkpoint["rows"] if r["state"] == "failed"] == list(FAILED_GROUPS) and
        binding["manual_failed_group_ids"] == list(MANUAL_GROUPS) and
        binding["parent_report_sha256"] == PARENT_REPORT_SHA and binding["parent_result_sha256"] == PARENT_RESULT_SHA and
        binding["parent_approval_sha256"] == PARENT_APPROVAL_SHA and
        binding["historical_trial_stays_stopped"] is True,
        "checkpoint_binding_changed")
    return [dict(row) for row in checkpoint["rows"]]


def expected_transition() -> dict:
    return {"schema": "public_visual_parser_equivalence_v1", "proof_sha256": PARSER_PROOF_SHA,
        "old_parser": "visual_source_id_v3", "new_parser": production_parser.CONTRACT_VERSION,
        "valid_equivalent": 118, "failed_preserved": 20, "historical_failed_results_credited": 0,
        "wire_unchanged": True, "candidate_local_repair": True, "mixed_historical_parser_lineage": True}


def admit_parser_transition() -> dict:
    try:
        binding = parser_equivalence.validate(parser_equivalence.PROOF_PATH, PARSER_PROOF_SHA)
    except (parser_equivalence.EquivalenceError, production_parser.VisualSourceJudgmentError):
        raise PilotError("parser_equivalence_proof_invalid") from None
    require(binding == expected_transition(), "parser_transition_changed")
    return binding


def admit() -> dict:
    current = sys.modules[__name__]
    proof = process_identity.bind_completed_scopes(current)
    def observer(pid):
        return process_identity.recorded_process_released(pid, proof["upper_bounds"])
    preserved_parent = process_identity.clone_admission_tree(parent_trial, observer)
    base = preserved_parent.admit()
    checkpoint = admit_checkpoint(base, process_observer=observer)
    requests = [r for r in base["requests"] if r["group_id"] in NEW_GROUPS]
    require(tuple(r["group_id"] for r in requests) == NEW_GROUPS and len(requests) == MAX_CALLS, "new_roster_changed")
    transition = admit_parser_transition()
    return {**base, "requests": requests, "checkpoint": checkpoint, "parser_transition": transition,
        "process_identity_binding": proof["binding"], "process_identity_binding_sha256": proof["binding_sha256"],
        "request_roster_sha256": digest(canonical(requests))}


def expected_approval(admitted: dict) -> dict:
    return {"schema_version": "public_visual_heldout_v11_approval", "authorization_id": AUTHORIZATION_ID,
        "approval_reply": APPROVAL_REPLY, "live_authorized": LIVE_AUTHORIZED, "guards": guards(),
        "code_hashes": code_hashes(), "calibration_binding": admitted["calibration_binding"],
        "parser_transition": admitted["parser_transition"],
        "input_freeze_sha256": INPUT_FREEZE_SHA, "qualification_freeze_sha256": QUALIFICATION_FREEZE_SHA,
        "request_roster_sha256": admitted["request_roster_sha256"], "public_only": True,
        "checkpoint_binding": admitted["checkpoint"]["binding"],
        "checkpoint_binding_sha256": admitted["checkpoint"]["binding_sha256"],
        "process_identity_binding": admitted["process_identity_binding"],
        "process_identity_binding_sha256": admitted["process_identity_binding_sha256"]}


def validate_approval(path: Path, sha: str, admitted: dict) -> None:
    require(read_bound(path, sha) == expected_approval(admitted), "approval_contract_changed")


VERDICT_SUBCODES = frozenset({
    "verdict_type_invalid", "verdict_oversize", "duplicate_json_key", "nonfinite_json",
    "verdict_json_invalid", "verdict_fields_invalid", "question_status_invalid", "four_verdicts_required",
    "page_verdict_fields_invalid", "page_id_invalid", "usefulness_invalid", "cue_verdict_invalid",
    "cue_without_useful_page", "verdict_roster_invalid", "clarification_qualified_page", "verdict_count_invalid",
})


def parse_response(response: httpx.Response) -> tuple[dict, tuple[int, int]]:
    if response.status_code != 200:
        code = f"provider_http_{response.status_code}"
        raise PilotError(code if code in previous.TRANSIENT else "provider_http_permanent")
    require(len(response.content) <= MAX_RESPONSE, "provider_response_oversize")
    try:
        body = json.loads(response.content, object_pairs_hook=visual._unique,
                          parse_constant=lambda _: require(False, "provider_json_invalid"))
    except (ValueError, UnicodeError, RecursionError):
        raise PilotError("provider_json_invalid") from None
    require(type(body) is dict and body.get("modelVersion") == MODEL, "provider_model_mismatch")
    usage = body.get("usageMetadata")
    require(type(usage) is dict and all(type(usage.get(k)) is int and usage[k] >= 0
            for k in ("promptTokenCount", "candidatesTokenCount"))
            and type(usage.get("thoughtsTokenCount", 0)) is int and usage.get("thoughtsTokenCount", 0) >= 0
            and usage["promptTokenCount"] > 0, "provider_usage_invalid")
    inp = usage["promptTokenCount"]
    out = usage["candidatesTokenCount"] + usage.get("thoughtsTokenCount", 0)
    total = usage.get("totalTokenCount")
    require(total is None or (type(total) is int and total >= inp + out), "provider_usage_invalid")
    out = max(out, (total - inp) if total is not None else out)
    if inp > MAX_INPUT or out > MAX_OUTPUT:
        raise ContentError("provider_token_limit_exceeded", (inp, out))
    candidates = body.get("candidates")
    if type(candidates) is not list or len(candidates) != 1 or type(candidates[0]) is not dict:
        raise ContentError("provider_candidate_invalid", (inp, out))
    candidate = candidates[0]
    content = candidate.get("content")
    if candidate.get("finishReason") != "STOP" or type(content) is not dict or type(content.get("parts")) is not list:
        raise ContentError("provider_finish_invalid", (inp, out))
    parts = content["parts"]
    if (not parts or any(type(p) is not dict or type(p.get("text")) is not str
                        or set(p) - {"text", "thought", "thoughtSignature"} for p in parts)):
        raise ContentError("provider_candidate_invalid", (inp, out))
    final = [p["text"] for p in parts if p.get("thought") is not True]
    if len(final) != 1:
        raise ContentError("provider_candidate_invalid", (inp, out))
    try:
        verdict = production_parser.parse_verdict(final[0], ISSUED)
    except production_parser.VisualSourceJudgmentError as failure:
        error = ContentError("provider_verdict_invalid", (inp, out))
        error.safe_verdict_subcode = str(failure) if str(failure) in VERDICT_SUBCODES else "verdict_schema_invalid"
        raise error from None
    return verdict, (inp, out)



async def run(admitted: dict, approval_sha: str, output: Path, send, *, ledger: Path | None = None,
              clock=time.monotonic, sleep=asyncio.sleep) -> dict:
    """Synthetic injected transport; live execution is separately fenced."""
    require(output.is_dir() and not output.is_symlink() and visual._sha(approval_sha), "output_or_approval_invalid")
    require(admitted.get("parser_transition") == expected_transition(), "parser_transition_changed")
    rows = checkpoint_rows(admitted)
    requests = admitted["requests"]
    require(len(requests) == MAX_CALLS and tuple(r["group_id"] for r in requests) == NEW_GROUPS and
        {r["group_id"] for r in requests} == set(admitted["expected_ids"]) - set(ACTIVE_INHERITED_GROUPS),
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
        last = clock(); verdict = usage = failure = verdict_subcode = None; fatal = False
        try:
            async with asyncio.timeout(CALL_SECONDS):
                response = await send(body)
            verdict, usage = parse_response(response)
        except Exception as error:
            failure = failure_code(error)
            verdict_subcode = getattr(error, 'safe_verdict_subcode', None)
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
            "known_cost_microusd": cost(*usage) if usage else None, "failure_code": failure, "verdict": verdict, "verdict_failure_subcode": verdict_subcode}
        write_new(output / f"attempt-{gid}.json", receipt); receipts.append(receipt)
        progress(output, {"status": "running", "new_provider_calls": len(receipts),
            "inherited_physical_provider_calls": OLD_PHYSICAL_ATTEMPTS, "inherited_evaluated_groups": 56,
            "evaluated_groups": len(rows), "new_known_cost_microusd": known_cost,
            "inherited_known_cost_microusd": OLD_COST_MICROUSD, "unknown_cost_attempts": unknown,
            "last_group_id": gid, "last_failure_code": failure})
        if fatal or known_cost > COST_CAP_MICROUSD or reported_input > MAX_CALLS * MAX_INPUT or reported_output > MAX_CALLS * MAX_OUTPUT:
            reason, state = failure or "aggregate_budget_exceeded", "stopped"
            break
    final_score = scorer.evaluate(admitted["overlay"], rows, admitted["expected_ids"])
    final_ceiling = scorer.ceiling(admitted["overlay"], rows, admitted["expected_ids"])
    # The last response has no next loop iteration in which to apply the
    # optimistic stop. A complete roster can still fail its quality gate.
    if state == "complete" and not final_score["heldout_passed"]:
        state, reason = "stopped", "quality_unreachable"
    final = {"schema_version": "public_visual_heldout_v11_result", "status": state, "reason": reason,
        "authorization_id": AUTHORIZATION_ID, "approval_sha256": approval_sha,
        "calibration_binding": admitted["calibration_binding"], "input_freeze_sha256": INPUT_FREEZE_SHA,
        "parser_transition": admitted["parser_transition"],
        "qualification_freeze_sha256": QUALIFICATION_FREEZE_SHA, "checkpoint_binding": admitted["checkpoint"]["binding"],
        "inherited_receipts": admitted["checkpoint"]["receipts"],
        "prior_checkpoint": admitted["checkpoint"]["prior_checkpoint"],
        "request_roster_sha256": admitted["request_roster_sha256"], "provider_calls": len(receipts),
        "evaluated_group_attempts": len(rows),
        "total_physical_provider_calls": OLD_PHYSICAL_ATTEMPTS + len(receipts), "historical_physical_attempts": OLD_PHYSICAL_ATTEMPTS,
        "known_cost_microusd": known_cost, "combined_known_cost_microusd": known_cost + OLD_COST_MICROUSD,
        "unknown_cost_attempts": unknown, "prior_unknown_cost_attempts": OLD_UNKNOWN_ATTEMPTS,
        "reported_input_tokens": reported_input, "reported_output_tokens": reported_output,
        "reserved_cost_microusd": len(receipts) * cost(MAX_INPUT, MAX_OUTPUT),
        "elapsed_ms": int((clock() - started) * 1000),
        "score": final_score, "ceiling": final_ceiling,
        "receipt_hashes": {r["group_id"]: digest(canonical(r)) for r in receipts},
        "old_trial_remains_failed": True, "resume_permitted": False, "ask_enabled": False, "private_data_sent": False}
    write_new(output / "result.json", final)
    progress(output, {"status": state, "reason": reason, "new_provider_calls": len(receipts),
        "inherited_physical_provider_calls": OLD_PHYSICAL_ATTEMPTS,
        "inherited_evaluated_groups": 56, "evaluated_groups": len(rows),
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
                "new_requests": MAX_CALLS, "inherited_outcomes": 56, "inherited_failed_groups": 2,
                "historical_physical_attempts": OLD_PHYSICAL_ATTEMPTS,
                "quality_reachable": measured["quality_reachable"], "live_authorized": LIVE_AUTHORIZED,
                "parser_transition": admitted["parser_transition"]}))
            return 0
        if args.prepare_approval:
            require(args.approval_file is None and args.approval_sha is None, "approval_arguments_forbidden")
            root = Path(tempfile.mkdtemp(prefix="cardchemy-visual-heldout-approval-v11-"))
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
