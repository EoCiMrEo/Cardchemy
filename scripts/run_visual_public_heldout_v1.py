"""Separate one-use public heldout; keyless preparation never authorizes dispatch.

The fixed calibration result must pass, and the complete blind input review and
all source bytes must be bound before credentials are read. No private corpus,
database, embedding, download, model training or Ask activation exists here.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import httpx
import run_visual_public_calibration_v5 as calibration
import review_visual_public_heldout_v1 as review
import score_visual_public_heldout_v1 as scorer

previous = calibration.previous
visual = calibration.visual
require, canonical, digest = calibration.require, calibration.canonical, calibration.digest
read_bound, write_new = calibration.read_bound, calibration.write_new
PilotError, ContentError = calibration.PilotError, calibration.ContentError
cost, failure_code, progress = calibration.cost, calibration.failure_code, calibration.progress
MODEL, ENDPOINT, ISSUED = calibration.MODEL, calibration.ENDPOINT, calibration.ISSUED
MAX_INPUT, MAX_OUTPUT, MAX_RESPONSE = 32768, 4096, 65536
MAX_CALLS, CALL_SECONDS, MAX_SECONDS, INTERVAL_SECONDS = 60, 60, 5400, 20
COST_CAP_MICROUSD = 1250000
LIVE_AUTHORIZED = True
AUTHORIZATION_ID = "20261001_public_visual_heldout_v1_once"
APPROVAL_REPLY = "20261002_user_approved_exact_sixty_public_heldout_envelope"
REPO = Path(__file__).resolve().parents[1]
INPUT_ROOT = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-heldout-input-v2-ftym4wam")
INPUT_FREEZE_SHA = "321bce11c7e882e0c7b9e56ffcc24296459217183b17fec87910c43e45ee68cd"
REVIEW_ROOT = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-heldout-review-v1-kguf6t5m")
QUALIFICATION_FREEZE_SHA = "24179f108fbd2ab9ab35c91cec09030acbb6eb3438eba72e643b20364beedfc9"
CALIBRATION_RESULT_PATH = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-public-calibration-v5-20261001-71c88d0a/result.json")
CALIBRATION_RESULT_SHA = "ab7de74a34811bc2c8bdef2abbd634a7d751b59540f2b0232008fbdedefddb4e"
CALIBRATION_APPROVAL_PATH = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-public-approval-v5-pfm6zro6/approval.json")
CALIBRATION_APPROVAL_SHA = "71c88d0a613a4b7c0865e0fb2b14dd8f6eb9edf0175e87fad79664630555e48b"
CODE_PATHS = calibration.CODE_PATHS + (
    "scripts/prepare_visual_public_heldout_v2.py", "scripts/review_visual_public_heldout_v1.py",
    "scripts/score_visual_public_heldout_v1.py", "scripts/run_visual_public_heldout_v1.py",
    "scripts/launch_visual_public_heldout_v1.py",
    "backend/app/ai/source_judgment_visual_v2.py",
    "backend/app/services/knowledge_pdf_renderer.py",
    "backend/app/services/source_visual_preparation.py",
)


def code_hashes() -> dict:
    return {name: digest((REPO / name).read_bytes()) for name in CODE_PATHS}


def guards() -> dict:
    return dict(previous.guards(), max_calls=MAX_CALLS, input_total=MAX_CALLS * MAX_INPUT,
                output_total=MAX_CALLS * MAX_OUTPUT, output_per_call=MAX_OUTPUT,
                call_seconds=CALL_SECONDS, total_seconds=MAX_SECONDS,
                new_cost_cap_microusd=COST_CAP_MICROUSD, heldout_permitted=True,
                live_authorized=LIVE_AUTHORIZED, maximum_failed_groups=2,
                minimum_valid_responses=58, minimum_positive_hits=40,
                minimum_per_form_hits=14, minimum_valid_empty_no_match=10,
                minimum_displayed_usefulness_percent=80, selected_unknown_permitted=False)


def ledger_dir() -> Path:
    root = REPO / ".agent/.verification/visual-public-heldout-v1-ledger"
    require(not root.parent.is_symlink() and not root.is_symlink(), "ledger_invalid")
    root.mkdir(parents=True, exist_ok=True)
    return root


def rest_body(wire: dict, known_images: set[str], inspected: set[str]) -> bytes:
    # Reuse the exact frozen prompt/schema/parser, changing only its recorded
    # output allowance to the already calibrated 4096-token successor.
    require(type(wire) is dict and type(wire.get("generationConfig")) is dict and
            wire["generationConfig"].get("maxOutputTokens") == MAX_OUTPUT,
            "heldout_output_contract_invalid")
    parent = copy.deepcopy(wire)
    parent["generationConfig"]["maxOutputTokens"] = 2048
    body = calibration.rest_body(parent, known_images, inspected)
    require(len(body) <= visual.MAX_REQUEST_BYTES, "request_byte_budget")
    return body


def admit_calibration() -> dict:
    admitted = calibration.admit()
    calibration.validate_approval(CALIBRATION_APPROVAL_PATH, CALIBRATION_APPROVAL_SHA, admitted)
    result = read_bound(CALIBRATION_RESULT_PATH, CALIBRATION_RESULT_SHA, 1000000)
    require(result.get("schema_version") == "public_visual_calibration_v5_result" and
            result.get("status") == "complete" and result.get("reason") == "complete" and
            result.get("authorization_id") == calibration.AUTHORIZATION_ID and
            result.get("approval_sha256") == CALIBRATION_APPROVAL_SHA and
            result.get("provider_calls") == 47 and result.get("total_provider_calls") == 67 and
            result.get("request_roster_sha256") == admitted["request_roster_sha256"] and
            result.get("checkpoint_binding") == admitted["checkpoint"]["binding"] and
            result.get("inherited_receipts") == admitted["checkpoint"]["receipts"] and
            result.get("heldout_opened") is False and result.get("ask_enabled") is False,
            "calibration_terminal_binding")
    rows = calibration._checkpoint_rows(admitted)
    for request in admitted["requests"]:
        gid = request["group_id"]
        if gid in calibration.OLD_GROUPS:
            continue
        receipt = read_bound(CALIBRATION_RESULT_PATH.parent / f"attempt-{gid}.json",
                             result["receipt_hashes"][gid])
        require(receipt["request_sha256"] == request["rest_sha256"], "calibration_request_changed")
        rows.append({k: receipt[k] for k in ("group_id", "state", "selected_ids", "question_status")})
    measured = calibration.scorer.evaluate(admitted["overlay"], rows, admitted["expected_ids"])
    require(canonical(measured) == canonical(result["score"]) and measured["calibration_passed"] is True,
            "calibration_quality_gate_required")
    return {"result_sha256": CALIBRATION_RESULT_SHA, "approval_sha256": CALIBRATION_APPROVAL_SHA,
            "score_sha256": digest(canonical(measured)), "public_only": True}


def bind_qualification(packet: dict, hidden: dict, bound: dict, final_review: dict) -> list[dict]:
    indexed = review.validate_review(final_review, packet,
        digest(canonical(packet)), "root-blind")
    labels = review.input_.read_json(review.input_.PACKET_ROOT / "heldout/labels.json",
                                   review.input_.LABEL_SHA)
    old = {r["group_id"]: r for r in labels["groups"]}
    parents = {r["pair_id"]: r for r in bound["mapping"]}
    overlay = []
    for entry in hidden["pairs"]:
        source = parents[entry["pair_id"]]
        group = old[source["old_group_id"]]
        historical = next(r for r in group["candidates"] if r["id"] == entry["candidate_id"])
        useful = "Yes" if historical["page_useful"] and historical["cue_useful"] else "No"
        current = indexed[entry["review_id"]]
        values = [current[field] for field in review.FIELDS]
        qualification = "No" if "No" in values else ("Unsure" if "Unsure" in values else "Yes")
        if useful == "No" and qualification != "No":
            qualification = "Unsure"  # disagreement never upgrades old No.
        overlay.append({"pair_id": entry["pair_id"], "group_id": entry["group_id"],
                        "candidate_id": entry["candidate_id"], "form": group["form"],
                        "historical_joint_usefulness": useful, "qualification": qualification,
                        "review_id": entry["review_id"]})
    return sorted(overlay, key=lambda r: r["pair_id"])


def admit() -> dict:
    calibration_binding = admit_calibration()
    manifest, bound, _ = review.validate_frozen_input(INPUT_ROOT, INPUT_FREEZE_SHA)
    packet, hidden = review.project_review(INPUT_ROOT, INPUT_FREEZE_SHA)
    frozen = read_bound(REVIEW_ROOT / "qualification-freeze.json", QUALIFICATION_FREEZE_SHA)
    require(frozen.get("schema_version") == "visual_public_heldout_qualification_v1" and
            frozen.get("source_visual_freeze_sha256") == INPUT_FREEZE_SHA and
            frozen.get("historical_labels_sha256") == review.input_.LABEL_SHA and
            frozen.get("candidate_pairs") == 240 and frozen.get("images_visually_inspected") == 86 and
            frozen.get("provider_calls") == 0 and frozen.get("model_quality_pass") is False and
            frozen.get("historical_labels_changed") is False,
            "complete_blind_qualification_required")
    require(digest(canonical(packet)) == frozen["packet_sha256"] and
            read_bound(REVIEW_ROOT / "packet.json", frozen["packet_sha256"], 2000000) == packet,
            "review_packet_changed")
    final_review = read_bound(REVIEW_ROOT / "root-review-final.json", frozen["review_sha256"], 1000000)
    overlay = bind_qualification(packet, hidden, bound, final_review)
    raw_overlay = (REVIEW_ROOT / "qualification-overlay.json").read_bytes()
    require(len(raw_overlay) <= 1000000 and digest(raw_overlay) == frozen["overlay_sha256"] and
            canonical(overlay) == raw_overlay, "qualification_overlay_changed")
    known_images = {r["sha256"] for r in manifest["images"]}
    requests = []
    inspected = set()
    for r in manifest["requests"]:
        wire = read_bound(INPUT_ROOT / r["wire_path"], r["wire_sha256"], visual.MAX_REQUEST_BYTES)
        body = rest_body(wire, known_images, inspected)
        requests.append({"group_id": r["group_id"], "path": r["wire_path"],
                         "wire_sha256": r["wire_sha256"], "rest_sha256": digest(body),
                         "rest_bytes": len(body)})
    require(len(requests) == MAX_CALLS and len({r["group_id"] for r in requests}) == MAX_CALLS,
            "complete_physical_attempt_roster")
    expected = {r["group_id"]: ISSUED for r in requests}
    require(scorer.ceiling(overlay, [], expected)["quality_reachable"], "heldout_input_unreachable")
    return {"calibration_binding": calibration_binding, "input_freeze_sha256": INPUT_FREEZE_SHA,
            "qualification_freeze_sha256": QUALIFICATION_FREEZE_SHA,
            "requests": requests, "request_roster_sha256": digest(canonical(requests)),
            "overlay": overlay, "known_images": known_images, "expected_ids": expected}


def expected_approval(admitted: dict) -> dict:
    return {"schema_version": "public_visual_heldout_v1_approval", "authorization_id": AUTHORIZATION_ID,
            "approval_reply": APPROVAL_REPLY, "live_authorized": LIVE_AUTHORIZED, "guards": guards(),
            "code_hashes": code_hashes(), "calibration_binding": admitted["calibration_binding"],
            "input_freeze_sha256": INPUT_FREEZE_SHA, "qualification_freeze_sha256": QUALIFICATION_FREEZE_SHA,
            "request_roster_sha256": admitted["request_roster_sha256"], "public_only": True}


def validate_approval(path: Path, sha: str, admitted: dict) -> None:
    require(read_bound(path, sha) == expected_approval(admitted), "approval_contract_changed")


async def run(admitted: dict, approval_sha: str, output: Path, send, *,
              ledger: Path | None = None, clock=time.monotonic, sleep=asyncio.sleep) -> dict:
    """Inject a transport for offline tests; never implies live authorization."""
    require(output.is_dir() and not output.is_symlink() and visual._sha(approval_sha), "output_or_approval_invalid")
    requests = admitted["requests"]
    require(len(requests) == MAX_CALLS and {r["group_id"] for r in requests} == set(admitted["expected_ids"]),
            "physical_attempt_roster_invalid")
    ledger = ledger_dir() if ledger is None else ledger
    require(ledger.is_dir() and not ledger.is_symlink(), "ledger_invalid")
    write_new(ledger / f"{AUTHORIZATION_ID}.run-claim.json", {
        "authorization_id": AUTHORIZATION_ID, "approval_sha256": approval_sha,
        "request_roster_sha256": admitted["request_roster_sha256"], "pid": os.getpid()})
    rows, receipts = [], []
    reported_input = reported_output = known_cost = unknown = 0
    started, last = clock(), None
    reason, state = "complete", "complete"
    for request in requests:
        if not scorer.ceiling(admitted["overlay"], rows, admitted["expected_ids"])["quality_reachable"]:
            reason, state = "quality_unreachable", "stopped"
            break
        if last is not None:
            await sleep(max(0, INTERVAL_SECONDS - (clock() - last)))
        require(clock() - started + CALL_SECONDS <= MAX_SECONDS, "total_time_budget")
        require((len(receipts) + 1) * cost(MAX_INPUT, MAX_OUTPUT) <= COST_CAP_MICROUSD, "cost_reserve_budget")
        wire = read_bound(INPUT_ROOT / request["path"], request["wire_sha256"], visual.MAX_REQUEST_BYTES)
        body = rest_body(wire, admitted["known_images"], set())
        require(digest(body) == request["rest_sha256"], "request_changed")
        gid = request["group_id"]
        claim = {"authorization_id": AUTHORIZATION_ID, "group_id": gid,
                 "approval_sha256": approval_sha, "rest_sha256": request["rest_sha256"],
                 "started_epoch_ms": int(time.time() * 1000), "reserved_microusd": cost(MAX_INPUT, MAX_OUTPUT)}
        write_new(ledger / f"{AUTHORIZATION_ID}-{gid}.claim.json", claim)
        last = clock()
        verdict = usage = failure = None
        fatal = False
        try:
            async with asyncio.timeout(CALL_SECONDS):
                response = await send(body)
            verdict, usage = calibration.parse_response(response)
        except Exception as error:
            failure = failure_code(error)
            usage = error.usage if isinstance(error, ContentError) else None
            fatal = failure not in previous.TRANSIENT | previous.CONTENT_FAILURES
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
        receipt = {**row, "request_sha256": request["rest_sha256"],
                   "attempt_claim_sha256": digest(canonical(claim)),
                   "latency_ms": int(max(0, (clock() - last) * 1000)),
                   "reported_usage": {"input": usage[0], "output": usage[1]} if usage else None,
                   "known_cost_microusd": cost(*usage) if usage else None,
                   "failure_code": failure, "verdict": verdict}
        write_new(output / f"attempt-{gid}.json", receipt)
        receipts.append(receipt)
        progress(output, {"status": "running", "provider_calls": len(receipts),
                          "known_cost_microusd": known_cost, "unknown_cost_attempts": unknown,
                          "last_group_id": gid, "last_failure_code": failure})
        if fatal or known_cost > COST_CAP_MICROUSD or reported_input > MAX_CALLS * MAX_INPUT or reported_output > MAX_CALLS * MAX_OUTPUT:
            reason, state = failure or "aggregate_budget_exceeded", "stopped"
            break
    final = {"schema_version": "public_visual_heldout_v1_result", "status": state, "reason": reason,
             "authorization_id": AUTHORIZATION_ID, "approval_sha256": approval_sha,
             "calibration_binding": admitted["calibration_binding"],
             "input_freeze_sha256": INPUT_FREEZE_SHA, "qualification_freeze_sha256": QUALIFICATION_FREEZE_SHA,
             "request_roster_sha256": admitted["request_roster_sha256"],
             "provider_calls": len(receipts), "known_cost_microusd": known_cost,
             "unknown_cost_attempts": unknown, "reported_input_tokens": reported_input,
             "reported_output_tokens": reported_output, "reserved_cost_microusd": len(receipts) * cost(MAX_INPUT, MAX_OUTPUT),
             "elapsed_ms": int((clock() - started) * 1000),
             "score": scorer.evaluate(admitted["overlay"], rows, admitted["expected_ids"]),
             "ceiling": scorer.ceiling(admitted["overlay"], rows, admitted["expected_ids"]),
             "receipt_hashes": {r["group_id"]: digest(canonical(r)) for r in receipts},
             "resume_permitted": False, "ask_enabled": False, "private_data_sent": False}
    write_new(output / "result.json", final)
    progress(output, {"status": state, "reason": reason, "provider_calls": len(receipts),
                      "heldout_passed": final["score"]["heldout_passed"], "known_cost_microusd": known_cost,
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
            root = Path(tempfile.mkdtemp(prefix="cardchemy-visual-heldout-approval-v1-"))
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
