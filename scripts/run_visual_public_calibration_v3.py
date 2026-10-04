"""Inert successor caller with SHA-bound admission of four consumed v2 attempts.

Only an injected transport can run offline contracts. Live entry points remain
disabled until a fresh precise provider envelope is approved and frozen.
Historical receipts/claims are read-only and never grant another dispatch.
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
import run_visual_public_calibration_v2 as previous
import score_visual_public_calibration_v3 as scorer

visual, prototype = previous.visual, previous.prototype
PilotError, ContentError = previous.PilotError, previous.ContentError
require, canonical, digest = previous.require, previous.canonical, previous.digest
read_bound, write_new = previous.read_bound, previous.write_new
rest_body, parse_response, cost = previous.rest_body, previous.parse_response, previous.cost
failure_code, progress = previous.failure_code, previous.progress
REPO, INPUT_ROOT = previous.REPO, previous.INPUT_ROOT
ISSUED, MODEL, ENDPOINT = previous.ISSUED, previous.MODEL, previous.ENDPOINT
MAX_INPUT, MAX_OUTPUT, MAX_RESPONSE = previous.MAX_INPUT, previous.MAX_OUTPUT, previous.MAX_RESPONSE
CALL_SECONDS, MAX_SECONDS, INTERVAL_SECONDS = 30, 5400, 20
MAX_CALLS, COST_CAP_MICROUSD = 63, 950000
LIVE_AUTHORIZED = True
AUTHORIZATION_ID = "20261001_public_visual_calibration_v3_checkpoint_once"
APPROVAL_REPLY = "call_JhHkP71DY6BVPWwf2pr5oRay"
OLD_GROUPS = ("Q013", "Q017", "Q027", "Q036")
OLD_COST_MICROUSD, OLD_INPUT_TOKENS, OLD_OUTPUT_TOKENS = 20718, 26427, 5115
OLD_APPROVAL_PATH = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-public-approval-v2-85kba5ak/approval.json")
OLD_APPROVAL_SHA = "828a9a8518fc60500439b72c0d8c4cea0e71927ba4e95f1085f263a08c10cb68"
OLD_RESULT_PATH = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-public-calibration-v2-20261001-r2-828a9a85/result.json")
OLD_RESULT_SHA = "9999931f1e087060ccef20eb02241625788ec07b98fc56880d383dcaaa646360"
OLD_RUN_CLAIM_SHA = "b349834217faa359e6c76d2b32d710baea315e47d97a1d44dfc01ce8baf9e2f6"
OLD_LEDGER = REPO / ".agent/.verification/visual-public-calibration-v2-ledger"
CODE_PATHS = previous.CODE_PATHS + (
    "scripts/run_visual_public_calibration_v3.py", "scripts/score_visual_public_calibration_v3.py",
    "scripts/launch_visual_public_calibration_v3.py",
)
RECEIPT_FIELDS = {"group_id", "state", "selected_ids", "question_status", "request_sha256",
                  "attempt_claim_sha256", "latency_ms", "reported_usage", "known_cost_microusd",
                  "failure_code", "verdict"}


def code_hashes() -> dict:
    return {name: digest((REPO / name).read_bytes()) for name in CODE_PATHS}


def guards() -> dict:
    return dict(previous.guards(), max_calls=MAX_CALLS, input_total=MAX_CALLS * MAX_INPUT,
                output_total=MAX_CALLS * MAX_OUTPUT, new_cost_cap_microusd=COST_CAP_MICROUSD,
                live_authorized=LIVE_AUTHORIZED, inherited_calls=4, total_group_denominator=67,
                inherited_known_cost_microusd=OLD_COST_MICROUSD,
                minimum_displayed_usefulness_percent=scorer.MIN_DISPLAYED_USEFULNESS_PERCENT)


def ledger_dir() -> Path:
    root = REPO / ".agent/.verification/visual-public-calibration-v3-ledger"
    require(not root.parent.is_symlink() and not root.is_symlink(), "ledger_invalid")
    root.mkdir(parents=True, exist_ok=True)
    return root


def validate_old_receipt(receipt: dict, claim: dict, request: dict) -> dict:
    """Reparse a closed stored verdict; no raw response or source text is copied."""
    require(type(receipt) is dict and set(receipt) == RECEIPT_FIELDS and
            receipt["group_id"] == request["group_id"] in OLD_GROUPS and
            receipt["state"] == "completed" and receipt["failure_code"] is None and
            type(receipt["latency_ms"]) is int and 0 <= receipt["latency_ms"] <= CALL_SECONDS * 1000 and
            receipt["request_sha256"] == request["rest_sha256"] and
            receipt["attempt_claim_sha256"] == digest(canonical(claim)), "checkpoint_receipt_invalid")
    require(type(claim) is dict and set(claim) == {"authorization_id", "group_id", "approval_sha256",
            "rest_sha256", "started_epoch_ms", "reserved_microusd"} and
            claim["authorization_id"] == previous.AUTHORIZATION_ID and
            claim["group_id"] == request["group_id"] and claim["approval_sha256"] == OLD_APPROVAL_SHA and
            claim["rest_sha256"] == request["rest_sha256"] and
            type(claim["started_epoch_ms"]) is int and claim["started_epoch_ms"] > 0 and
            type(claim["reserved_microusd"]) is int and claim["reserved_microusd"] == cost(MAX_INPUT, MAX_OUTPUT),
            "checkpoint_claim_invalid")
    usage = receipt["reported_usage"]
    require(type(usage) is dict and set(usage) == {"input", "output"} and
            type(usage["input"]) is int and 0 < usage["input"] <= MAX_INPUT and
            type(usage["output"]) is int and 0 <= usage["output"] <= MAX_OUTPUT and
            type(receipt["known_cost_microusd"]) is int and
            receipt["known_cost_microusd"] == cost(usage["input"], usage["output"]), "checkpoint_usage_invalid")
    verdict = receipt["verdict"]
    require(type(verdict) is dict and set(verdict) == {"schema_version", "question_status", "page_verdicts",
            "selected_ids", "unverified_references", "generated_answer"}, "checkpoint_verdict_invalid")
    try:
        parsed = prototype.parse_verdict(canonical({"question_status": verdict["question_status"],
                                                   "pages": verdict["page_verdicts"]}), ISSUED)
    except (ValueError, TypeError, KeyError):
        raise PilotError("checkpoint_verdict_invalid") from None
    require(canonical(parsed) == canonical(verdict) and receipt["selected_ids"] == parsed["selected_ids"] and
            receipt["question_status"] == parsed["question_status"] == "clear", "checkpoint_verdict_changed")
    return {key: receipt[key] for key in ("group_id", "state", "selected_ids", "question_status")}


def admit_checkpoint(admitted: dict) -> dict:
    """Only fixed old paths and externally pinned result/approval may be read."""
    previous.validate_approval(OLD_APPROVAL_PATH, OLD_APPROVAL_SHA, admitted)
    run_claim = read_bound(OLD_LEDGER / f"{previous.AUTHORIZATION_ID}.run-claim.json", OLD_RUN_CLAIM_SHA)
    require(set(run_claim) == {"authorization_id", "approval_sha256", "request_roster_sha256", "pid"} and
            run_claim["authorization_id"] == previous.AUTHORIZATION_ID and
            run_claim["approval_sha256"] == OLD_APPROVAL_SHA and
            run_claim["request_roster_sha256"] == admitted["request_roster_sha256"] and
            type(run_claim["pid"]) is int and run_claim["pid"] > 0, "checkpoint_run_claim_invalid")
    result = read_bound(OLD_RESULT_PATH, OLD_RESULT_SHA, 1000000)
    require(set(result) == {"schema_version", "status", "reason", "authorization_id", "approval_sha256",
            "request_roster_sha256", "provider_calls", "known_cost_microusd", "unknown_cost_attempts",
            "reported_input_tokens", "reported_output_tokens", "reserved_cost_microusd", "elapsed_ms",
            "score", "ceiling", "receipt_hashes", "resume_permitted", "heldout_opened", "ask_enabled"} and
            result["schema_version"] == "public_visual_calibration_v2_result" and
            result["status"] == "stopped" and result["reason"] == "quality_unreachable" and
            result["authorization_id"] == previous.AUTHORIZATION_ID and result["approval_sha256"] == OLD_APPROVAL_SHA and
            result["request_roster_sha256"] == admitted["request_roster_sha256"] and
            type(result["provider_calls"]) is int and result["provider_calls"] == 4 and
            type(result["unknown_cost_attempts"]) is int and result["unknown_cost_attempts"] == 0 and result["resume_permitted"] is False and
            result["heldout_opened"] is result["ask_enabled"] is False and
            set(result["receipt_hashes"]) == set(OLD_GROUPS), "checkpoint_result_invalid")
    require(not OLD_LEDGER.is_symlink() and not OLD_RESULT_PATH.parent.is_symlink() and
            {p.name for p in OLD_LEDGER.glob(previous.AUTHORIZATION_ID + "-Q*.claim.json")} ==
            {previous.AUTHORIZATION_ID + "-" + gid + ".claim.json" for gid in OLD_GROUPS} and
            {p.name for p in OLD_RESULT_PATH.parent.glob("attempt-*.json")} ==
            {"attempt-" + gid + ".json" for gid in OLD_GROUPS}, "checkpoint_physical_roster_invalid")
    require(len(admitted["requests"]) == 67 and len({r["group_id"] for r in admitted["requests"]}) == 67 and
            {r["group_id"] for r in admitted["requests"]} == set(admitted["expected_ids"]) and
            {r["group_id"] for r in admitted["requests"][:4]} == set(OLD_GROUPS), "checkpoint_original_roster_invalid")
    requests = {r["group_id"]: r for r in admitted["requests"]}
    rows, receipts, bindings, starts = [], {}, {}, {}
    for gid in OLD_GROUPS:
        request = requests[gid]
        wire = read_bound(INPUT_ROOT / request["path"], request["wire_sha256"], visual.MAX_REQUEST_BYTES)
        body = rest_body(wire, admitted["known_images"], set())
        require(digest(body) == request["rest_sha256"] and len(body) == request["rest_bytes"],
                "checkpoint_source_wire_changed")
        receipt = read_bound(OLD_RESULT_PATH.parent / f"attempt-{gid}.json", result["receipt_hashes"][gid])
        claim = read_bound(OLD_LEDGER / f"{previous.AUTHORIZATION_ID}-{gid}.claim.json", receipt["attempt_claim_sha256"])
        rows.append(validate_old_receipt(receipt, claim, request))
        receipts[gid] = receipt
        starts[gid] = claim["started_epoch_ms"]
        bindings[gid] = {"receipt_sha256": result["receipt_hashes"][gid],
                         "claim_sha256": receipt["attempt_claim_sha256"],
                         "wire_sha256": request["wire_sha256"], "rest_sha256": request["rest_sha256"]}
    dispatch_starts = [starts[r["group_id"]] for r in admitted["requests"][:4]]
    require(all(b - a >= INTERVAL_SECONDS * 1000 for a, b in zip(dispatch_starts, dispatch_starts[1:])), "checkpoint_spacing_invalid")
    require(result["known_cost_microusd"] == sum(r["known_cost_microusd"] for r in receipts.values()) == OLD_COST_MICROUSD and
            result["reported_input_tokens"] == sum(r["reported_usage"]["input"] for r in receipts.values()) == OLD_INPUT_TOKENS and
            result["reported_output_tokens"] == sum(r["reported_usage"]["output"] for r in receipts.values()) == OLD_OUTPUT_TOKENS and
            result["reserved_cost_microusd"] == 4 * cost(MAX_INPUT, MAX_OUTPUT) and
            type(result["elapsed_ms"]) is int and 0 <= result["elapsed_ms"] <= MAX_SECONDS * 1000 and
            canonical(result["score"]) == canonical(previous.scorer.evaluate(admitted["overlay"], rows, admitted["expected_ids"])) and
            canonical(result["ceiling"]) == canonical(previous.scorer.ceiling(admitted["overlay"], rows, admitted["expected_ids"])),
            "checkpoint_totals_or_score_changed")
    binding = {"old_authorization_id": previous.AUTHORIZATION_ID, "old_approval_sha256": OLD_APPROVAL_SHA,
               "old_result_sha256": OLD_RESULT_SHA, "old_run_claim_sha256": OLD_RUN_CLAIM_SHA,
               "request_roster_sha256": admitted["request_roster_sha256"],
               "receipt_bindings": bindings, "inherited_groups": list(OLD_GROUPS),
               "inherited_known_cost_microusd": OLD_COST_MICROUSD,
               "inherited_input_tokens": OLD_INPUT_TOKENS, "inherited_output_tokens": OLD_OUTPUT_TOKENS,
               "rows_sha256": digest(canonical(rows))}
    return {"binding": binding, "binding_sha256": digest(canonical(binding)), "rows": rows, "receipts": receipts}


def _checkpoint_rows(admitted: dict) -> list[dict]:
    checkpoint = admitted["checkpoint"]
    binding_fields = {"old_authorization_id", "old_approval_sha256", "old_result_sha256", "old_run_claim_sha256",
                      "request_roster_sha256", "receipt_bindings", "inherited_groups", "inherited_known_cost_microusd",
                      "inherited_input_tokens", "inherited_output_tokens", "rows_sha256"}
    require(type(checkpoint) is dict and set(checkpoint) == {"binding", "binding_sha256", "rows", "receipts"} and
            type(checkpoint["binding"]) is dict and set(checkpoint["binding"]) == binding_fields and
            digest(canonical(checkpoint["binding"])) == checkpoint["binding_sha256"] and
            checkpoint["binding"]["rows_sha256"] == digest(canonical(checkpoint["rows"])) and
            checkpoint["binding"]["old_result_sha256"] == OLD_RESULT_SHA and
            checkpoint["binding"]["old_approval_sha256"] == OLD_APPROVAL_SHA and
            checkpoint["binding"]["old_authorization_id"] == previous.AUTHORIZATION_ID and
            checkpoint["binding"]["old_run_claim_sha256"] == OLD_RUN_CLAIM_SHA and
            checkpoint["binding"]["request_roster_sha256"] == admitted["request_roster_sha256"] and
            checkpoint["binding"]["inherited_groups"] == list(OLD_GROUPS) and
            checkpoint["binding"]["inherited_known_cost_microusd"] == OLD_COST_MICROUSD and
            checkpoint["binding"]["inherited_input_tokens"] == OLD_INPUT_TOKENS and
            checkpoint["binding"]["inherited_output_tokens"] == OLD_OUTPUT_TOKENS and
            type(checkpoint["binding"]["receipt_bindings"]) is dict and
            set(checkpoint["binding"]["receipt_bindings"]) == set(OLD_GROUPS) and
            type(checkpoint["receipts"]) is dict and
            set(checkpoint["receipts"]) == set(OLD_GROUPS) and
            type(checkpoint["rows"]) is list and len(checkpoint["rows"]) == 4 and
            [r["group_id"] for r in checkpoint["rows"]] == list(OLD_GROUPS) and
            all(r["state"] == "completed" and r["question_status"] == "clear" for r in checkpoint["rows"]),
            "checkpoint_admission_changed")
    for row in checkpoint["rows"]:
        gid = row["group_id"]
        receipt, bound = checkpoint["receipts"][gid], checkpoint["binding"]["receipt_bindings"][gid]
        require(type(bound) is dict and set(bound) == {"receipt_sha256", "claim_sha256", "wire_sha256", "rest_sha256"} and
                all(visual._sha(value) for value in bound.values()) and
                type(receipt) is dict and set(receipt) == RECEIPT_FIELDS and
                bound["receipt_sha256"] == digest(canonical(receipt)) and
                bound["claim_sha256"] == receipt["attempt_claim_sha256"] and
                bound["rest_sha256"] == receipt["request_sha256"] and
                canonical(row) == canonical({key: receipt[key] for key in
                    ("group_id", "state", "selected_ids", "question_status")}), "checkpoint_receipt_binding_changed")
        matches = [r for r in admitted["requests"] if r["group_id"] == gid]
        require(len(matches) == 1 and matches[0]["wire_sha256"] == bound["wire_sha256"] and
                matches[0]["rest_sha256"] == bound["rest_sha256"], "checkpoint_request_binding_changed")
    scorer.evaluate(admitted["overlay"], checkpoint["rows"], admitted["expected_ids"])
    return [dict(row, selected_ids=list(row["selected_ids"])) for row in checkpoint["rows"]]


def admit() -> dict:
    admitted = previous.admit()
    admitted["checkpoint"] = admit_checkpoint(admitted)
    require(scorer.ceiling(admitted["overlay"], _checkpoint_rows(admitted), admitted["expected_ids"])["quality_reachable"],
            "checkpoint_quality_unreachable")
    return admitted


def expected_approval(admitted: dict) -> dict:
    _checkpoint_rows(admitted)
    return {"schema_version": "public_visual_calibration_v3_approval", "authorization_id": AUTHORIZATION_ID,
            "approval_reply": APPROVAL_REPLY, "live_authorized": LIVE_AUTHORIZED, "guards": guards(),
            "code_hashes": code_hashes(), "summary_sha256": previous.SUMMARY_SHA,
            "verification_sha256": previous.VERIFICATION_SHA, "visual_freeze_sha256": previous.VISUAL_FREEZE_SHA,
            "request_roster_sha256": admitted["request_roster_sha256"],
            "checkpoint_binding": admitted["checkpoint"]["binding"],
            "checkpoint_binding_sha256": admitted["checkpoint"]["binding_sha256"], "public_only": True}


def validate_approval(path: Path, sha: str, admitted: dict) -> None:
    require(read_bound(path, sha) == expected_approval(admitted), "approval_contract_changed")


async def run(admitted: dict, approval_sha: str, output: Path, send,
              *, ledger: Path | None = None, clock=time.monotonic, sleep=asyncio.sleep) -> dict:
    """Injected transport for synthetic tests; live entry points are separately fenced."""
    require(output.is_dir() and not output.is_symlink() and visual._sha(approval_sha), "output_or_approval_invalid")
    rows = _checkpoint_rows(admitted)
    requests = admitted["requests"]
    require(len(requests) == 67 and len({r["group_id"] for r in requests}) == 67 and
            {r["group_id"] for r in requests} == set(admitted["expected_ids"]), "physical_attempt_roster_invalid")
    remaining = [r for r in requests if r["group_id"] not in OLD_GROUPS]
    require(len(remaining) == MAX_CALLS, "inherited_group_resend_forbidden")
    ledger = ledger_dir() if ledger is None else ledger
    require(ledger.is_dir() and not ledger.is_symlink(), "ledger_invalid")
    start, last = clock(), None
    write_new(ledger / f"{AUTHORIZATION_ID}.run-claim.json", {
        "authorization_id": AUTHORIZATION_ID, "approval_sha256": approval_sha,
        "request_roster_sha256": admitted["request_roster_sha256"],
        "checkpoint_binding_sha256": admitted["checkpoint"]["binding_sha256"], "pid": os.getpid()})
    receipts, reported_input, reported_output, known_cost, unknown = [], 0, 0, 0, 0
    reason, state = "complete", "complete"
    for request in remaining:
        if not scorer.ceiling(admitted["overlay"], rows, admitted["expected_ids"])["quality_reachable"]:
            reason, state = "quality_unreachable", "stopped"
            break
        if last is not None:
            await sleep(max(0, INTERVAL_SECONDS - (clock() - last)))
        require(clock() - start + CALL_SECONDS <= MAX_SECONDS, "total_time_budget")
        require((len(receipts) + 1) * cost(MAX_INPUT, MAX_OUTPUT) <= COST_CAP_MICROUSD, "cost_reserve_budget")
        wire = read_bound(INPUT_ROOT / request["path"], request["wire_sha256"], visual.MAX_REQUEST_BYTES)
        body = rest_body(wire, admitted["known_images"], set())
        require(digest(body) == request["rest_sha256"], "request_changed")
        gid = request["group_id"]
        require(gid not in OLD_GROUPS, "inherited_group_resend_forbidden")
        claim = {"authorization_id": AUTHORIZATION_ID, "group_id": gid,
                 "approval_sha256": approval_sha, "rest_sha256": request["rest_sha256"],
                 "checkpoint_binding_sha256": admitted["checkpoint"]["binding_sha256"],
                 "started_epoch_ms": int(time.time() * 1000), "reserved_microusd": cost(MAX_INPUT, MAX_OUTPUT)}
        write_new(ledger / f"{AUTHORIZATION_ID}-{gid}.claim.json", claim)
        verdict, usage, failure, fatal = None, None, None, False
        last = clock()
        try:
            async with asyncio.timeout(CALL_SECONDS):
                response = await send(body)
            verdict, usage = parse_response(response)
        except Exception as error:
            failure = failure_code(error)
            usage = error.usage if isinstance(error, ContentError) else None
            fatal = failure not in previous.TRANSIENT | previous.CONTENT_FAILURES
        elapsed = int(max(0, (clock() - last) * 1000))
        if usage is None:
            unknown += 1
        else:
            reported_input += usage[0]
            reported_output += usage[1]
            known_cost += cost(*usage)
        row = {"group_id": gid, "state": "completed" if verdict else "failed",
               "selected_ids": verdict["selected_ids"] if verdict else [],
               "question_status": verdict["question_status"] if verdict else None}
        rows.append(row)
        receipt = {**row, "request_sha256": request["rest_sha256"], "attempt_claim_sha256": digest(canonical(claim)),
                   "latency_ms": elapsed, "reported_usage": {"input": usage[0], "output": usage[1]} if usage else None,
                   "known_cost_microusd": cost(*usage) if usage else None, "failure_code": failure, "verdict": verdict}
        write_new(output / f"attempt-{gid}.json", receipt)
        receipts.append(receipt)
        progress(output, {"status": "running", "new_provider_calls": len(receipts), "evaluated_groups": len(rows),
                          "inherited_provider_calls": 4, "known_cost_microusd": known_cost,
                          "inherited_known_cost_microusd": OLD_COST_MICROUSD, "unknown_cost_attempts": unknown,
                          "last_group_id": gid, "last_failure_code": failure})
        if fatal or known_cost > COST_CAP_MICROUSD or reported_input > MAX_CALLS * MAX_INPUT or reported_output > MAX_CALLS * MAX_OUTPUT:
            reason, state = failure or "aggregate_budget_exceeded", "stopped"
            break
    final = {"schema_version": "public_visual_calibration_v3_result", "status": state, "reason": reason,
             "authorization_id": AUTHORIZATION_ID, "approval_sha256": approval_sha,
             "request_roster_sha256": admitted["request_roster_sha256"],
             "checkpoint_binding": admitted["checkpoint"]["binding"],
             "checkpoint_binding_sha256": admitted["checkpoint"]["binding_sha256"],
             "inherited_receipts": admitted["checkpoint"]["receipts"], "inherited_provider_calls": 4,
             "provider_calls": len(receipts), "total_provider_calls": 4 + len(receipts),
             "known_cost_microusd": known_cost, "inherited_known_cost_microusd": OLD_COST_MICROUSD,
             "combined_known_cost_microusd": OLD_COST_MICROUSD + known_cost, "unknown_cost_attempts": unknown,
             "reported_input_tokens": reported_input, "reported_output_tokens": reported_output,
             "inherited_input_tokens": OLD_INPUT_TOKENS, "inherited_output_tokens": OLD_OUTPUT_TOKENS,
             "reserved_cost_microusd": len(receipts) * cost(MAX_INPUT, MAX_OUTPUT),
             "elapsed_ms": int((clock() - start) * 1000),
             "score": scorer.evaluate(admitted["overlay"], rows, admitted["expected_ids"]),
             "ceiling": scorer.ceiling(admitted["overlay"], rows, admitted["expected_ids"]),
             "receipt_hashes": {r["group_id"]: digest(canonical(r)) for r in receipts},
             "resume_permitted": False, "heldout_opened": False, "ask_enabled": False}
    write_new(output / "result.json", final)
    progress(output, {"status": state, "reason": reason, "new_provider_calls": len(receipts),
                      "evaluated_groups": len(rows), "calibration_passed": final["score"]["calibration_passed"],
                      "known_cost_microusd": known_cost, "inherited_known_cost_microusd": OLD_COST_MICROUSD,
                      "unknown_cost_attempts": unknown})
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
        "checkpoint_binding_sha256": fresh["checkpoint"]["binding_sha256"],
        "request_roster_sha256": fresh["request_roster_sha256"], "pid": os.getpid()})
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
                return httpx.Response(response.status_code, content=bytes(raw))
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
            root = Path(tempfile.mkdtemp(prefix="cardchemy-visual-public-approval-v3-"))
            receipt = expected_approval(admitted)
            write_new(root / "approval.json", receipt)
            print(json.dumps({"approval_file": str(root / "approval.json"), "approval_sha256": digest(canonical(receipt)),
                              "provider_calls": 0, "inherited_calls": 4, "new_requests": MAX_CALLS,
                              "live_authorized": LIVE_AUTHORIZED}))
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
