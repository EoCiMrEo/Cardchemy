"""Offline 4,096-output successor; twenty valid receipts retained, all old failures preserved.

Injected transports serve offline contracts. Live entry points require the
precise one-use provider approval, frozen inputs and exclusive durable claims.
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
import run_visual_public_calibration_v4 as checkpoint_previous
import score_visual_public_calibration_v5 as scorer

visual, prototype = previous.visual, previous.prototype
PilotError, ContentError = previous.PilotError, previous.ContentError
require, canonical, digest = previous.require, previous.canonical, previous.digest
read_bound, write_new = previous.read_bound, previous.write_new
cost = previous.cost
failure_code, progress = previous.failure_code, previous.progress
REPO, INPUT_ROOT = previous.REPO, previous.INPUT_ROOT
ISSUED, MODEL, ENDPOINT = previous.ISSUED, previous.MODEL, previous.ENDPOINT
MAX_INPUT, MAX_OUTPUT, MAX_RESPONSE = previous.MAX_INPUT, 4096, previous.MAX_RESPONSE
CALL_SECONDS, MAX_SECONDS, INTERVAL_SECONDS = 60, 5400, 20
MAX_CALLS, COST_CAP_MICROUSD = 47, 950000
LIVE_AUTHORIZED = True
AUTHORIZATION_ID = "20261001_public_visual_calibration_v5_completion_once"
APPROVAL_REPLY = "20261001_user_explicit_exact_47_public_question_continuation"
OLD_GROUPS = ("Q013", "Q017", "Q027", "Q036", "Q001", "Q019", "Q020", "Q022", "Q032", "Q034", "Q049", "Q051", "Q052", "Q053", "Q059", "Q060", "Q062", "Q065", "Q066", "Q006")
OLD_COST_MICROUSD, OLD_INPUT_TOKENS, OLD_OUTPUT_TOKENS = 130870, 152725, 34017
OLD_APPROVAL_PATH = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-public-approval-v4-xi3n2plp/approval.json")
OLD_APPROVAL_SHA = "6fdd878e41dd04f56275377c9cc68868d0d98b6be534619bbb657ec2ccd75aed"
OLD_RESULT_PATH = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-public-calibration-v4-20261001-6fdd878e/result.json")
OLD_RESULT_SHA = "18e5053cbf38e6ef0b25c1048a3d4eb680ca83dd3498c143dd7c566ee865d2a8"
OLD_FAILED_GROUPS = ("Q003", "Q007", "Q014")
OLD_LEDGER = REPO / ".agent/.verification/visual-public-calibration-v4-ledger"
CODE_PATHS = checkpoint_previous.CODE_PATHS + (
    "scripts/run_visual_public_calibration_v5.py", "scripts/launch_visual_public_calibration_v5.py",
    "scripts/score_visual_public_calibration_v5.py",
)
RECEIPT_FIELDS = {"group_id", "state", "selected_ids", "question_status", "request_sha256",
                  "attempt_claim_sha256", "latency_ms", "reported_usage", "known_cost_microusd",
                  "failure_code", "verdict"}


def code_hashes() -> dict:
    return {name: digest((REPO / name).read_bytes()) for name in CODE_PATHS}


def guards() -> dict:
    return dict(previous.guards(), max_calls=MAX_CALLS, input_total=MAX_CALLS * MAX_INPUT,
                output_total=MAX_CALLS * MAX_OUTPUT, new_cost_cap_microusd=COST_CAP_MICROUSD,
                live_authorized=LIVE_AUTHORIZED, call_seconds=CALL_SECONDS, inherited_calls=20, total_group_denominator=67,
                inherited_known_cost_microusd=OLD_COST_MICROUSD,
                prior_unknown_cost_attempts=3, manual_unfinished_reattempts=3, prior_known_failed_attempts=3, output_per_call=MAX_OUTPUT, minimum_valid_empty_no_match=10,
                minimum_displayed_usefulness_percent=scorer.MIN_DISPLAYED_USEFULNESS_PERCENT)


def ledger_dir() -> Path:
    root = REPO / ".agent/.verification/visual-public-calibration-v5-ledger"
    require(not root.parent.is_symlink() and not root.is_symlink(), "ledger_invalid")
    root.mkdir(parents=True, exist_ok=True)
    return root


def rest_body(wire: dict, known_images: set[str], inspected: set[str]) -> bytes:
    body = json.loads(previous.rest_body(wire, known_images, inspected))
    require(body["generationConfig"]["maxOutputTokens"] == 2048, "parent_output_contract_changed")
    body["generationConfig"]["maxOutputTokens"] = MAX_OUTPUT
    raw = canonical(body)
    require(len(raw) <= visual.MAX_REQUEST_BYTES, "request_byte_budget")
    return raw


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
        verdict = prototype.parse_verdict(final[0], ISSUED)
    except prototype.previous.VisualVerdictError:
        raise ContentError("provider_verdict_invalid", (inp, out)) from None
    return verdict, (inp, out)



def admit_checkpoint(base: dict) -> dict:
    checkpoint_previous.validate_approval(OLD_APPROVAL_PATH, OLD_APPROVAL_SHA, base)
    result = read_bound(OLD_RESULT_PATH, OLD_RESULT_SHA, 1000000)
    require(result["schema_version"] == "public_visual_calibration_v4_result" and
            result["status"] == "stopped" and result["reason"] == "quality_unreachable" and
            result["authorization_id"] == checkpoint_previous.AUTHORIZATION_ID and
            result["approval_sha256"] == OLD_APPROVAL_SHA and
            result["request_roster_sha256"] == base["request_roster_sha256"] and
            result["checkpoint_binding"] == base["checkpoint"]["binding"] and
            result["inherited_receipts"] == base["checkpoint"]["receipts"] and
            result["provider_calls"] == 18 and result["known_cost_microusd"] == 106457 and
            result["combined_known_cost_microusd"] == OLD_COST_MICROUSD and
            result["reported_input_tokens"] == 119390 and result["reported_output_tokens"] == 28253 and
            result["unknown_cost_attempts"] == 0 and result["resume_permitted"] is
            result["heldout_opened"] is result["ask_enabled"] is False, "parent_result_changed")
    run_claim = OLD_LEDGER / (checkpoint_previous.AUTHORIZATION_ID + ".run-claim.json")
    require(run_claim.is_file() and not run_claim.is_symlink(), "parent_run_claim_missing")
    raw_claim = run_claim.read_bytes()
    claim_run = json.loads(raw_claim, object_pairs_hook=visual._unique)
    require(claim_run["approval_sha256"] == OLD_APPROVAL_SHA and
            claim_run["checkpoint_binding_sha256"] == base["checkpoint"]["binding_sha256"] and
            claim_run["request_roster_sha256"] == base["request_roster_sha256"], "parent_run_claim_changed")
    remaining = [r for r in base["requests"] if r["group_id"] not in checkpoint_previous.OLD_GROUPS]
    ordered = remaining[:18]
    new_ids = {r["group_id"] for r in ordered}
    require(set(result["receipt_hashes"]) == new_ids and
            {p.name for p in OLD_RESULT_PATH.parent.glob("attempt-*.json")} ==
            {"attempt-" + gid + ".json" for gid in new_ids} and
            {p.name for p in OLD_LEDGER.glob(checkpoint_previous.AUTHORIZATION_ID + "-Q*.claim.json")} ==
            {checkpoint_previous.AUTHORIZATION_ID + "-" + gid + ".claim.json" for gid in new_ids},
            "parent_attempt_roster_changed")
    historical = checkpoint_previous._checkpoint_rows(base)
    rows, receipts = list(historical), dict(base["checkpoint"]["receipts"])
    bindings = dict(base["checkpoint"]["binding"]["receipt_bindings"])
    failures = dict(base["checkpoint"]["binding"]["prior_failed_attempts"])
    total_in, total_out, total_cost, starts = 0, 0, 0, []
    for request in ordered:
        gid = request["group_id"]
        receipt = read_bound(OLD_RESULT_PATH.parent / f"attempt-{gid}.json", result["receipt_hashes"][gid])
        claim = read_bound(OLD_LEDGER / f"{checkpoint_previous.AUTHORIZATION_ID}-{gid}.claim.json",
                           receipt["attempt_claim_sha256"])
        require(set(receipt) == RECEIPT_FIELDS and receipt["group_id"] == gid and
                receipt["request_sha256"] == request["rest_sha256"] and
                claim["authorization_id"] == checkpoint_previous.AUTHORIZATION_ID and
                claim["approval_sha256"] == OLD_APPROVAL_SHA and claim["group_id"] == gid and
                claim["rest_sha256"] == request["rest_sha256"] and
                claim["checkpoint_binding_sha256"] == base["checkpoint"]["binding_sha256"] and
                type(claim["started_epoch_ms"]) is int and type(receipt["latency_ms"]) is int and
                0 <= receipt["latency_ms"] <= 61000, "parent_attempt_changed")
        starts.append(claim["started_epoch_ms"])
        usage = receipt["reported_usage"]
        require(type(usage) is dict and set(usage) == {"input", "output"} and
                type(usage["input"]) is type(usage["output"]) is int and
                0 < usage["input"] <= MAX_INPUT and 0 <= usage["output"] <= 2048 and
                receipt["known_cost_microusd"] == cost(usage["input"], usage["output"]), "parent_usage_changed")
        total_in += usage["input"]
        total_out += usage["output"]
        total_cost += receipt["known_cost_microusd"]
        row = {k: receipt[k] for k in ("group_id", "state", "selected_ids", "question_status")}
        historical.append(row)
        bound = {"receipt_sha256": result["receipt_hashes"][gid],
                 "claim_sha256": receipt["attempt_claim_sha256"],
                 "wire_sha256": request["wire_sha256"], "rest_sha256": request["rest_sha256"]}
        if gid in OLD_FAILED_GROUPS:
            require(receipt["state"] == "failed" and receipt["failure_code"] == "provider_finish_invalid" and
                    receipt["question_status"] is receipt["verdict"] is None and receipt["selected_ids"] == [],
                    "parent_failure_changed")
            failures[gid] = {**bound, "failure_code": "provider_finish_invalid", "cost_unknown": False,
                             "known_cost_microusd": receipt["known_cost_microusd"]}
        else:
            verdict = receipt["verdict"]
            require(receipt["state"] == "completed" and receipt["failure_code"] is None and type(verdict) is dict,
                    "parent_valid_receipt_changed")
            parsed = prototype.parse_verdict(canonical({"question_status": verdict["question_status"],
                                                        "pages": verdict["page_verdicts"]}), ISSUED)
            require(parsed == verdict and row["selected_ids"] == parsed["selected_ids"] and
                    row["question_status"] == parsed["question_status"], "parent_valid_verdict_changed")
            rows.append(row)
            receipts[gid], bindings[gid] = receipt, bound
    require(all(b-a >= 20000 for a,b in zip(starts, starts[1:])) and
            (total_in, total_out, total_cost) == (119390, 28253, 106457), "parent_aggregate_changed")
    require(canonical(result["score"]) == canonical(checkpoint_previous.scorer.evaluate(base["overlay"], historical, base["expected_ids"])) and
            canonical(result["ceiling"]) == canonical(checkpoint_previous.scorer.ceiling(base["overlay"], historical, base["expected_ids"])),
            "parent_score_changed")
    require(set(r["group_id"] for r in rows) == set(OLD_GROUPS) and len(rows) == 20, "parent_success_roster_changed")
    binding = {"old_authorization_id": checkpoint_previous.AUTHORIZATION_ID,
               "old_approval_sha256": OLD_APPROVAL_SHA, "old_result_sha256": OLD_RESULT_SHA,
               "old_run_claim_sha256": digest(raw_claim), "base_checkpoint_sha256": base["checkpoint"]["binding_sha256"],
               "receipt_bindings": bindings, "inherited_groups": [r["group_id"] for r in rows],
               "prior_failed_attempts": failures, "inherited_known_cost_microusd": OLD_COST_MICROUSD,
               "inherited_input_tokens": OLD_INPUT_TOKENS, "inherited_output_tokens": OLD_OUTPUT_TOKENS,
               "rows_sha256": digest(canonical(rows)), "original_request_roster_sha256": base["request_roster_sha256"]}
    return {"binding": binding, "binding_sha256": digest(canonical(binding)), "rows": rows, "receipts": receipts}


def _checkpoint_rows(admitted: dict) -> list[dict]:
    checkpoint = admitted["checkpoint"]
    binding = checkpoint["binding"]
    require(digest(canonical(binding)) == checkpoint["binding_sha256"] and
            digest(canonical(checkpoint["rows"])) == binding["rows_sha256"] and
            binding["old_result_sha256"] == OLD_RESULT_SHA and binding["old_approval_sha256"] == OLD_APPROVAL_SHA and
            binding["old_authorization_id"] == checkpoint_previous.AUTHORIZATION_ID and
            binding["inherited_known_cost_microusd"] == OLD_COST_MICROUSD and
            binding["inherited_input_tokens"] == OLD_INPUT_TOKENS and binding["inherited_output_tokens"] == OLD_OUTPUT_TOKENS and
            set(binding["inherited_groups"]) == set(OLD_GROUPS) and len(binding["inherited_groups"]) == 20 and
            set(binding["prior_failed_attempts"]) == set(OLD_FAILED_GROUPS) | {"Q019", "Q032", "Q053"} and
            len(checkpoint["rows"]) == 20 and {r["group_id"] for r in checkpoint["rows"]} == set(OLD_GROUPS) and
            set(checkpoint["receipts"]) == set(binding["receipt_bindings"]) == set(OLD_GROUPS),
            "checkpoint_admission_changed")
    for gid, failure in binding["prior_failed_attempts"].items():
        require(all(visual._sha(failure[k]) for k in ("receipt_sha256", "claim_sha256", "wire_sha256", "rest_sha256")) and
                ((gid in OLD_FAILED_GROUPS and failure["failure_code"] == "provider_finish_invalid" and
                  failure["cost_unknown"] is False and type(failure["known_cost_microusd"]) is int) or
                 (gid not in OLD_FAILED_GROUPS and failure["failure_code"] == "provider_timeout" and failure["cost_unknown"] is True)),
                "prior_failure_record_changed")
    for row in checkpoint["rows"]:
        gid = row["group_id"]
        receipt, bound = checkpoint["receipts"][gid], binding["receipt_bindings"][gid]
        require(row["state"] == "completed" and bound["receipt_sha256"] == digest(canonical(receipt)) and
                bound["claim_sha256"] == receipt["attempt_claim_sha256"] and bound["rest_sha256"] == receipt["request_sha256"] and
                row == {k: receipt[k] for k in ("group_id", "state", "selected_ids", "question_status")},
                "checkpoint_receipt_binding_changed")
        original = next(r for r in admitted["original_requests"] if r["group_id"] == gid)
        require(original["wire_sha256"] == bound["wire_sha256"] and original["rest_sha256"] == bound["rest_sha256"],
                "checkpoint_request_binding_changed")
    scorer.evaluate(admitted["overlay"], checkpoint["rows"], admitted["expected_ids"])
    return [dict(row, selected_ids=list(row["selected_ids"])) for row in checkpoint["rows"]]


def admit() -> dict:
    base = checkpoint_previous.admit()
    checkpoint = admit_checkpoint(base)
    requests = []
    for request in base["requests"]:
        wire = read_bound(INPUT_ROOT / request["path"], request["wire_sha256"], visual.MAX_REQUEST_BYTES)
        body = rest_body(wire, base["known_images"], set())
        requests.append(dict(request, rest_sha256=digest(body), rest_bytes=len(body)))
    admitted = dict(base, checkpoint=checkpoint, original_requests=base["requests"], requests=requests,
                    request_roster_sha256=digest(canonical(requests)))
    require(scorer.ceiling(admitted["overlay"], _checkpoint_rows(admitted), admitted["expected_ids"])["quality_reachable"],
            "checkpoint_quality_unreachable")
    return admitted


def expected_approval(admitted: dict) -> dict:
    _checkpoint_rows(admitted)
    return {"schema_version": "public_visual_calibration_v5_approval", "authorization_id": AUTHORIZATION_ID,
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
                          "inherited_provider_calls": 20, "known_cost_microusd": known_cost,
                          "inherited_known_cost_microusd": OLD_COST_MICROUSD, "unknown_cost_attempts": unknown,
                          "last_group_id": gid, "last_failure_code": failure})
        if fatal or known_cost > COST_CAP_MICROUSD or reported_input > MAX_CALLS * MAX_INPUT or reported_output > MAX_CALLS * MAX_OUTPUT:
            reason, state = failure or "aggregate_budget_exceeded", "stopped"
            break
    final = {"schema_version": "public_visual_calibration_v5_result", "status": state, "reason": reason,
             "authorization_id": AUTHORIZATION_ID, "approval_sha256": approval_sha,
             "request_roster_sha256": admitted["request_roster_sha256"],
             "checkpoint_binding": admitted["checkpoint"]["binding"],
             "checkpoint_binding_sha256": admitted["checkpoint"]["binding_sha256"],
             "inherited_receipts": admitted["checkpoint"]["receipts"], "inherited_provider_calls": 20,
             "provider_calls": len(receipts), "total_provider_calls": 20 + len(receipts),
             "physical_attempt_history_count": 26 + len(receipts),
             "known_cost_microusd": known_cost, "inherited_known_cost_microusd": OLD_COST_MICROUSD,
             "combined_known_cost_microusd": OLD_COST_MICROUSD + known_cost, "unknown_cost_attempts": unknown,
             "prior_unknown_cost_attempts": 3, "prior_failed_attempts": admitted["checkpoint"]["binding"]["prior_failed_attempts"],
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
            root = Path(tempfile.mkdtemp(prefix="cardchemy-visual-public-approval-v5-"))
            receipt = expected_approval(admitted)
            write_new(root / "approval.json", receipt)
            print(json.dumps({"approval_file": str(root / "approval.json"), "approval_sha256": digest(canonical(receipt)),
                              "provider_calls": 0, "inherited_calls": 20, "new_requests": MAX_CALLS,
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
