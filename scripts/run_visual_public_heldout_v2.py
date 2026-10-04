"""Inert transport-only successor for the consumed public-heldout trial.

Three validated results are retained; 54 untouched questions and three manual
fresh attempts form 57 new calls. The old v1 trial remains failed and immutable.
A precise fresh provider envelope is required before any credential access.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import httpx
import run_visual_public_heldout_v1 as previous_trial

previous=previous_trial.previous
calibration=previous_trial.calibration
visual=previous_trial.visual
scorer=previous_trial.scorer
require,canonical,digest=previous_trial.require,previous_trial.canonical,previous_trial.digest
read_bound,write_new=previous_trial.read_bound,previous_trial.write_new
PilotError,ContentError=previous_trial.PilotError,previous_trial.ContentError
cost,failure_code,progress=previous_trial.cost,previous_trial.failure_code,previous_trial.progress
MODEL,ENDPOINT,ISSUED=previous_trial.MODEL,previous_trial.ENDPOINT,previous_trial.ISSUED
REPO,INPUT_ROOT=previous_trial.REPO,previous_trial.INPUT_ROOT
INPUT_FREEZE_SHA=previous_trial.INPUT_FREEZE_SHA
QUALIFICATION_FREEZE_SHA=previous_trial.QUALIFICATION_FREEZE_SHA
MAX_INPUT,MAX_OUTPUT,MAX_RESPONSE=32768,4096,65536
MAX_CALLS,CALL_SECONDS,MAX_SECONDS,INTERVAL_SECONDS=57,120,9000,30
HTTP_503_COOLDOWN_SECONDS=120
COST_CAP_MICROUSD=1250000
LIVE_AUTHORIZED=True
AUTHORIZATION_ID="20261002_public_visual_heldout_v2_transport_once_pinned"
APPROVAL_REPLY="20261002_user_approved_exact_57_public_transport_successor_envelope"
OLD_SUCCESS_GROUPS=("Q001","Q002","Q005")
OLD_FAILED_GROUPS=("Q003","Q004","Q006")
OLD_FAILURE_CODES={"Q003":"provider_timeout","Q004":"provider_http_503","Q006":"provider_timeout"}
OLD_INPUT_TOKENS,OLD_OUTPUT_TOKENS,OLD_COST_MICROUSD=20450,3323,14444
OLD_APPROVAL_PATH=Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-heldout-approval-v1-9zina88l/approval.json")
OLD_APPROVAL_SHA="f12dcf219569b0571d3dbe50591c75f08e1a04018aec6350617bc6fa04372396"
OLD_RESULT_PATH=Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-public-heldout-v1-20261002-f12dcf21/result.json")
OLD_RESULT_SHA="41dd9c287206046c6bdc7ca7c3e247405b674400ab57f1aeb7232915c1f82095"
OLD_LEDGER=REPO/".agent/.verification/visual-public-heldout-v1-ledger"
CODE_PATHS=previous_trial.CODE_PATHS+(
    "scripts/run_visual_public_heldout_v2.py","scripts/launch_visual_public_heldout_v2.py")
RECEIPT_FIELDS={"group_id","state","selected_ids","question_status","request_sha256",
    "attempt_claim_sha256","latency_ms","reported_usage","known_cost_microusd","failure_code","verdict"}
rest_body=previous_trial.rest_body


def code_hashes():
    return {name:digest((REPO/name).read_bytes()) for name in CODE_PATHS}


def guards():
    return dict(previous_trial.guards(),max_calls=MAX_CALLS,
        input_total=MAX_CALLS*MAX_INPUT,output_total=MAX_CALLS*MAX_OUTPUT,
        call_seconds=CALL_SECONDS,total_seconds=MAX_SECONDS,spacing_seconds=INTERVAL_SECONDS,
        http_503_cooldown_seconds=HTTP_503_COOLDOWN_SECONDS,
        new_cost_cap_microusd=COST_CAP_MICROUSD,live_authorized=LIVE_AUTHORIZED,
        inherited_calls=3,total_group_denominator=60,manual_failed_reattempts=3,
        inherited_known_cost_microusd=OLD_COST_MICROUSD,prior_unknown_cost_attempts=3,
        prior_physical_attempts=6,automatic_same_question_retries=0)


def ledger_dir():
    root=REPO/".agent/.verification/visual-public-heldout-v2-ledger"
    require(not root.parent.is_symlink() and not root.is_symlink(),"ledger_invalid")
    root.mkdir(parents=True,exist_ok=True)
    return root

def admit_checkpoint(base: dict) -> dict:
    """Bind all six old physical attempts; retain only three valid results."""
    previous_trial.validate_approval(OLD_APPROVAL_PATH, OLD_APPROVAL_SHA, base)
    result = read_bound(OLD_RESULT_PATH, OLD_RESULT_SHA, 1000000)
    require(result.get("schema_version") == "public_visual_heldout_v1_result" and
        result.get("authorization_id") == previous_trial.AUTHORIZATION_ID and
        result.get("approval_sha256") == OLD_APPROVAL_SHA and result.get("status") == "stopped" and
        result.get("reason") == "quality_unreachable" and result.get("provider_calls") == 6 and
        result.get("request_roster_sha256") == base["request_roster_sha256"] and
        result.get("calibration_binding") == base["calibration_binding"] and
        result.get("input_freeze_sha256") == INPUT_FREEZE_SHA and
        result.get("qualification_freeze_sha256") == QUALIFICATION_FREEZE_SHA and
        result.get("known_cost_microusd") == OLD_COST_MICROUSD and
        result.get("unknown_cost_attempts") == 3 and
        result.get("reported_input_tokens") == OLD_INPUT_TOKENS and
        result.get("reported_output_tokens") == OLD_OUTPUT_TOKENS and
        result.get("resume_permitted") is result.get("ask_enabled") is
        result.get("private_data_sent") is False, "parent_result_changed")
    ordered = base["requests"][:6]
    require([r["group_id"] for r in ordered] == [f"Q{n:03d}" for n in range(1, 7)],
        "parent_request_order_changed")
    old_ids = {r["group_id"] for r in ordered}
    require(set(result["receipt_hashes"]) == old_ids and
        {p.name for p in OLD_RESULT_PATH.parent.glob("attempt-*.json")} ==
            {f"attempt-{gid}.json" for gid in old_ids} and
        {p.name for p in OLD_LEDGER.glob(previous_trial.AUTHORIZATION_ID + "-Q*.claim.json")} ==
            {f"{previous_trial.AUTHORIZATION_ID}-{gid}.claim.json" for gid in old_ids},
        "parent_physical_attempt_roster_changed")
    run_path = OLD_LEDGER / (previous_trial.AUTHORIZATION_ID + ".run-claim.json")
    require(run_path.is_file() and not run_path.is_symlink(), "parent_run_claim_missing")
    run_raw = run_path.read_bytes()
    run_claim = read_bound(run_path, digest(run_raw))
    require(run_claim.get("authorization_id") == previous_trial.AUTHORIZATION_ID and
        run_claim.get("approval_sha256") == OLD_APPROVAL_SHA and
        run_claim.get("request_roster_sha256") == base["request_roster_sha256"], "parent_run_claim_changed")
    rows, all_rows, receipts, bindings, failures, starts = [], [], {}, {}, {}, []
    total_in = total_out = total_cost = 0
    for request in ordered:
        gid = request["group_id"]
        receipt = read_bound(OLD_RESULT_PATH.parent / f"attempt-{gid}.json", result["receipt_hashes"][gid])
        claim = read_bound(OLD_LEDGER / f"{previous_trial.AUTHORIZATION_ID}-{gid}.claim.json",
            receipt["attempt_claim_sha256"])
        require(set(receipt) == RECEIPT_FIELDS and receipt["group_id"] == gid and
            receipt["request_sha256"] == request["rest_sha256"] and
            claim.get("authorization_id") == previous_trial.AUTHORIZATION_ID and
            claim.get("group_id") == gid and claim.get("approval_sha256") == OLD_APPROVAL_SHA and
            claim.get("rest_sha256") == request["rest_sha256"] and
            claim.get("reserved_microusd") == cost(MAX_INPUT, MAX_OUTPUT) and
            type(claim.get("started_epoch_ms")) is int and
            type(receipt["latency_ms"]) is int and 0 <= receipt["latency_ms"] <= 61000,
            "parent_attempt_changed")
        starts.append(claim["started_epoch_ms"])
        row = {k: receipt[k] for k in ("group_id", "state", "selected_ids", "question_status")}
        all_rows.append(row)
        binding = {"receipt_sha256": result["receipt_hashes"][gid],
            "claim_sha256": receipt["attempt_claim_sha256"], "wire_sha256": request["wire_sha256"],
            "rest_sha256": request["rest_sha256"]}
        if gid in OLD_FAILED_GROUPS:
            require(receipt["state"] == "failed" and receipt["failure_code"] == OLD_FAILURE_CODES[gid]
                and receipt["selected_ids"] == [] and receipt["question_status"] is None and
                receipt["verdict"] is None and receipt["reported_usage"] is None and
                receipt["known_cost_microusd"] is None, "parent_failure_changed")
            failures[gid] = {**binding, "failure_code": receipt["failure_code"], "cost_unknown": True}
            continue
        require(gid in OLD_SUCCESS_GROUPS and receipt["state"] == "completed" and
            receipt["failure_code"] is None and type(receipt["verdict"]) is dict,
            "parent_valid_receipt_changed")
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
        rows.append(row); receipts[gid] = receipt; bindings[gid] = binding
    require(all(b - a >= 20000 for a, b in zip(starts, starts[1:])) and
        (total_in, total_out, total_cost) == (OLD_INPUT_TOKENS, OLD_OUTPUT_TOKENS, OLD_COST_MICROUSD),
        "parent_aggregate_changed")
    require(canonical(result["score"]) == canonical(scorer.evaluate(base["overlay"], all_rows, base["expected_ids"])) and
        canonical(result["ceiling"]) == canonical(scorer.ceiling(base["overlay"], all_rows, base["expected_ids"])) and
        result["score"]["heldout_passed"] is False, "parent_failed_score_changed")
    require(set(receipts) == set(OLD_SUCCESS_GROUPS) and len(rows) == 3, "parent_success_roster_changed")
    binding = {"old_authorization_id": previous_trial.AUTHORIZATION_ID, "old_result_sha256": OLD_RESULT_SHA,
        "old_approval_sha256": OLD_APPROVAL_SHA, "old_run_claim_sha256": digest(run_raw),
        "original_request_roster_sha256": base["request_roster_sha256"],
        "receipt_bindings": bindings, "inherited_groups": list(OLD_SUCCESS_GROUPS),
        "prior_failed_attempts": failures, "inherited_known_cost_microusd": OLD_COST_MICROUSD,
        "inherited_input_tokens": OLD_INPUT_TOKENS, "inherited_output_tokens": OLD_OUTPUT_TOKENS,
        "prior_physical_attempts": 6, "rows_sha256": digest(canonical(rows))}
    return {"binding": binding, "binding_sha256": digest(canonical(binding)), "rows": rows, "receipts": receipts}


def checkpoint_rows(admitted: dict) -> list[dict]:
    checkpoint = admitted["checkpoint"]; binding = checkpoint["binding"]
    require(digest(canonical(binding)) == checkpoint["binding_sha256"] and
        digest(canonical(checkpoint["rows"])) == binding["rows_sha256"] and
        set(checkpoint["receipts"]) == set(OLD_SUCCESS_GROUPS) and len(checkpoint["rows"]) == 3 and
        {r["group_id"] for r in checkpoint["rows"]} == set(OLD_SUCCESS_GROUPS) and
        binding["old_result_sha256"] == OLD_RESULT_SHA and binding["old_approval_sha256"] == OLD_APPROVAL_SHA and
        set(binding["prior_failed_attempts"]) == set(OLD_FAILED_GROUPS), "checkpoint_binding_changed")
    return [dict(row) for row in checkpoint["rows"]]


def admit() -> dict:
    base = previous_trial.admit()
    checkpoint = admit_checkpoint(base)
    requests = [r for r in base["requests"] if r["group_id"] not in OLD_SUCCESS_GROUPS]
    require(len(requests) == MAX_CALLS and len({r["group_id"] for r in requests}) == MAX_CALLS and
        set(OLD_FAILED_GROUPS) <= {r["group_id"] for r in requests}, "new_physical_attempt_roster_changed")
    return {**base, "original_requests": base["requests"], "requests": requests, "checkpoint": checkpoint,
        "original_request_roster_sha256": base["request_roster_sha256"],
        "request_roster_sha256": digest(canonical(requests))}


def expected_approval(admitted: dict) -> dict:
    return {"schema_version": "public_visual_heldout_v2_approval", "authorization_id": AUTHORIZATION_ID,
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
    require(len(requests) == MAX_CALLS and len({r["group_id"] for r in requests}) == MAX_CALLS and
        {r["group_id"] for r in requests} == set(admitted["expected_ids"]) - set(OLD_SUCCESS_GROUPS),
        "physical_attempt_roster_invalid")
    ledger = ledger_dir() if ledger is None else ledger
    require(ledger.is_dir() and not ledger.is_symlink(), "ledger_invalid")
    write_new(ledger / f"{AUTHORIZATION_ID}.run-claim.json", {"authorization_id": AUTHORIZATION_ID,
        "approval_sha256": approval_sha, "request_roster_sha256": admitted["request_roster_sha256"],
        "checkpoint_binding_sha256": admitted["checkpoint"]["binding_sha256"], "pid": os.getpid()})
    receipts = []; reported_input = reported_output = known_cost = unknown = 0
    started, last, cooldown_until = clock(), None, None
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
        progress(output, {"status": "running", "new_provider_calls": len(receipts), "inherited_provider_calls": 3,
            "evaluated_groups": len(rows), "new_known_cost_microusd": known_cost,
            "inherited_known_cost_microusd": OLD_COST_MICROUSD, "unknown_cost_attempts": unknown,
            "last_group_id": gid, "last_failure_code": failure})
        if fatal or known_cost > COST_CAP_MICROUSD or reported_input > MAX_CALLS * MAX_INPUT or reported_output > MAX_CALLS * MAX_OUTPUT:
            reason, state = failure or "aggregate_budget_exceeded", "stopped"
            break
    final = {"schema_version": "public_visual_heldout_v2_result", "status": state, "reason": reason,
        "authorization_id": AUTHORIZATION_ID, "approval_sha256": approval_sha,
        "calibration_binding": admitted["calibration_binding"], "input_freeze_sha256": INPUT_FREEZE_SHA,
        "qualification_freeze_sha256": QUALIFICATION_FREEZE_SHA, "checkpoint_binding": admitted["checkpoint"]["binding"],
        "inherited_receipts": admitted["checkpoint"]["receipts"],
        "request_roster_sha256": admitted["request_roster_sha256"], "provider_calls": len(receipts),
        "evaluated_group_attempts": 3 + len(receipts),
        "total_physical_provider_calls": 6 + len(receipts), "historical_physical_attempts": 6,
        "known_cost_microusd": known_cost, "combined_known_cost_microusd": known_cost + OLD_COST_MICROUSD,
        "unknown_cost_attempts": unknown, "prior_unknown_cost_attempts": 3,
        "reported_input_tokens": reported_input, "reported_output_tokens": reported_output,
        "reserved_cost_microusd": len(receipts) * cost(MAX_INPUT, MAX_OUTPUT),
        "elapsed_ms": int((clock() - started) * 1000),
        "score": scorer.evaluate(admitted["overlay"], rows, admitted["expected_ids"]),
        "ceiling": scorer.ceiling(admitted["overlay"], rows, admitted["expected_ids"]),
        "receipt_hashes": {r["group_id"]: digest(canonical(r)) for r in receipts},
        "old_trial_remains_failed": True, "resume_permitted": False, "ask_enabled": False, "private_data_sent": False}
    write_new(output / "result.json", final)
    progress(output, {"status": state, "reason": reason, "new_provider_calls": len(receipts),
        "inherited_provider_calls": 3, "evaluated_groups": len(rows),
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
        if args.prepare_approval:
            require(args.approval_file is None and args.approval_sha is None, "approval_arguments_forbidden")
            root = Path(tempfile.mkdtemp(prefix="cardchemy-visual-heldout-approval-v2-"))
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
