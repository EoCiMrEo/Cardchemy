"""One approved public visual calibration, isolated from application runtime.

Default actions are keyless and networkless. External receipt SHA, immutable
public inputs, executable hashes and resource fencing precede credential access.
Only the worker can POST; every physical attempt has an exclusive durable claim.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import uuid

import httpx
import prepare_visual_page_source_input_v1 as visual
import prototype_visual_page_source_judge_v2 as prototype
import score_visual_public_calibration_v2 as scorer
import summarize_visual_semantic_control_v2 as bounds

AUTHORIZATION_ID = "20261001_public_visual_calibration_v2_once"
APPROVAL_REPLY = "call_3SiFWjYzMQI64DmJaF7V0dGC"
REPO = Path(__file__).resolve().parents[1]
INPUT_ROOT = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-semantic-summary-v2-5v5jc3li")
SUMMARY_SHA = "09b1f1abd79c6a79a3d5a50f4d5ae4d3c08dc377f9c757caeb7b552ca5c0d3b3"
VERIFICATION_PATH = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-bound-verification-v2-hkkqbnpb/verification.json")
VERIFICATION_SHA = "6dc1b51d66101072c8695777d7b448518508dd902c76e23257c947c69fe1a813"
VISUAL_ROOT = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-input-v1-vwcn8r3i")
VISUAL_FREEZE_SHA = "1079eab34382f62467757209040e40113ee4bae76082ea98c4e644bd378e5bac"
MODEL = "gemini-3.5-flash-lite"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/" + MODEL + ":generateContent"
MAX_CALLS = 67
MAX_INPUT = 32768
MAX_OUTPUT = 2048
MAX_RESPONSE = 65536
MAX_SECONDS = 5400
CALL_SECONDS = 30
INTERVAL_SECONDS = 20
COST_CAP_MICROUSD = 1050000
ISSUED = ["S01", "S02", "S03", "S04"]
PUBLIC_PDFS = {
    "lec04": "e3fc3c0aac94448415cf85f36d597ac48e5a8a1d37a69d82e18e7f3a06cae863",
    "lec05": "32ed19f52b0742af04950694280d3ae2e34096b82af825afc3835a9633b01dcb",
    "lec06": "96f014eda5663bd259a4e250dce268b24ec7263b81b211de8216ba00af963b8e",
    "lec07": "268456af4b81ec7539cf220e0da4acae286a7b3ac24e9175b397c13803f20319",
}
CODE_PATHS = (
    "scripts/run_visual_public_calibration_v2.py",
    "scripts/launch_visual_public_calibration_v2.py",
    "scripts/score_visual_public_calibration_v2.py",
    "scripts/prototype_visual_page_source_judge_v2.py",
    "scripts/prototype_visual_page_source_judge_v1.py",
    "scripts/prepare_visual_page_source_input_v1.py",
    "scripts/summarize_visual_semantic_control_v2.py",
    "scripts/prepare_visual_semantic_control_v2.py",
    "scripts/prepare_visual_source_feasibility_review_v1.py",
    "scripts/summarize_visual_source_feasibility_v1.py",
)
TRANSIENT = {"provider_timeout", "provider_network", "provider_http_408", "provider_http_429",
             "provider_http_502", "provider_http_503", "provider_http_504"}
CONTENT_FAILURES = {"provider_candidate_invalid", "provider_finish_invalid", "provider_verdict_invalid"}


class PilotError(ValueError):
    """A closed diagnostic; never a provider response or private exception."""


class ContentError(PilotError):
    def __init__(self, code: str, usage: tuple[int, int]):
        super().__init__(code)
        self.usage = usage


def require(ok: bool, code: str) -> None:
    if not ok:
        raise PilotError(code)


def canonical(value: object) -> bytes:
    return visual.canonical(value)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_bound(path: Path, sha: str, cap: int = 100000) -> dict:
    require(visual._sha(sha) and path.is_file() and not path.is_symlink(), "bound_file_invalid")
    with path.open("rb") as stream:
        raw = stream.read(cap + 1)
    require(0 < len(raw) <= cap and digest(raw) == sha, "bound_file_changed")
    try:
        value = json.loads(raw, object_pairs_hook=visual._unique,
                           parse_constant=lambda _: require(False, "nonfinite_json"))
        require(type(value) is dict and canonical(value) == raw, "canonical_object_required")
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise PilotError("bound_json_invalid") from None


def write_new(path: Path, value: object) -> None:
    with path.open("xb") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())


def ledger_dir() -> Path:
    root = REPO / ".agent/.verification/visual-public-calibration-v2-ledger"
    require(not root.parent.is_symlink() and not root.is_symlink(), "ledger_invalid")
    root.mkdir(parents=True, exist_ok=True)
    return root


def code_hashes() -> dict:
    return {name: digest((REPO / name).read_bytes()) for name in CODE_PATHS}


def guards() -> dict:
    return {"endpoint": ENDPOINT, "model": MODEL, "thinking": "HIGH", "store": False,
            "max_calls": MAX_CALLS, "retries": 0, "input_per_call": MAX_INPUT,
            "output_per_call": MAX_OUTPUT, "input_total": MAX_CALLS * MAX_INPUT,
            "output_total": MAX_CALLS * MAX_OUTPUT, "max_request_bytes": visual.MAX_REQUEST_BYTES,
            "max_response_bytes": MAX_RESPONSE, "max_verdict_bytes": 2048,
            "call_seconds": CALL_SECONDS, "total_seconds": MAX_SECONDS,
            "spacing_seconds": INTERVAL_SECONDS, "cpus": 4, "memory_bytes": 2147483648,
            "input_price_usd_per_million": "0.30", "output_price_usd_per_million": "2.50",
            "new_cost_cap_microusd": COST_CAP_MICROUSD, "heldout_permitted": False,
            "private_data_permitted": False, "ask_activation_permitted": False}


def cost(input_tokens: int, output_tokens: int) -> int:
    return int((Decimal(input_tokens) * Decimal("0.30") +
                Decimal(output_tokens) * Decimal("2.50")).to_integral_value(rounding=ROUND_CEILING))


def rest_body(wire: dict, known_images: set[str], inspected: set[str]) -> bytes:
    require(set(wire) == {"model", "store", "systemInstruction", "contents", "generationConfig"}
            and wire["model"] == MODEL and wire["store"] is False
            and wire["systemInstruction"] == {"parts": [{"text": prototype.SYSTEM}]}, "wire_identity_invalid")
    require(type(wire["contents"]) is list and len(wire["contents"]) == 1
            and set(wire["contents"][0]) == {"role", "parts"}
            and wire["contents"][0]["role"] == "user", "single_current_question_required")
    parts = wire["contents"][0]["parts"]
    require(prototype.build_request(parts, ISSUED) == wire, "wire_contract_changed")
    text_bytes = len(prototype.SYSTEM.encode()) + len(canonical(wire["generationConfig"]["responseJsonSchema"]))
    for part in parts:
        if "text" in part:
            text_bytes += len(part["text"].encode())
        else:
            try:
                raw = base64.b64decode(part["inline_data"]["data"], validate=True)
            except (ValueError, TypeError):
                raise PilotError("image_encoding_invalid") from None
            sha = digest(raw)
            require(sha in known_images, "unissued_image")
            if sha not in inspected:
                visual.inspect_png(raw)
                inspected.add(sha)
    # Conservative UTF-8 byte proxy plus 9*258 tokens/image and protocol reserve.
    # This is not a provider token count; usage is independently checked later.
    require(text_bytes + 4 * 9 * 258 + 1024 <= MAX_INPUT, "estimated_input_budget")
    # The API takes model in its URL path; strip the preparer's selector metadata.
    body = canonical({k: v for k, v in wire.items() if k != "model"})
    require(len(body) <= visual.MAX_REQUEST_BYTES, "request_byte_budget")
    return body


def admit() -> dict:
    summary = read_bound(INPUT_ROOT / "summary.json", SUMMARY_SHA)
    verification = read_bound(VERIFICATION_PATH, VERIFICATION_SHA)
    require(summary.get("inert_request_count") == 67 and summary.get("control_admitted") is True
            and summary.get("heldout_opened") is False and summary.get("provider_calls") == 0
            and summary.get("parent_visual_freeze_sha256") == VISUAL_FREEZE_SHA
            and summary.get("prototype_sha256") == digest(Path(prototype.__file__).read_bytes()),
            "complete_public_summary_required")
    expected_files = {"qualification-overlay.json", "bounds.json"} | {
        f"requests/group-{n:03d}.json" for n in range(1, 68)}
    require(set(summary["files"]) == expected_files, "complete_request_roster_required")
    overlay_document = read_bound(INPUT_ROOT / "qualification-overlay.json",
                                  summary["files"]["qualification-overlay.json"])
    require(overlay_document.get("parent_mapping_sha256") == bounds.PARENT_MAPPING_SHA,
            "parent_label_binding_invalid")
    overlay = overlay_document["pairs"]
    parent_mapping = read_bound(visual.AUDIT_ROOT / "final/complete-label-mapping.json",
                               bounds.PARENT_MAPPING_SHA, 1000000)
    source_to_review = bind_group_ids(parent_mapping["pairs"])
    require(verification.get("parent_summary_sha256") == SUMMARY_SHA
            and verification.get("bound_checker_sha256") == digest(Path(bounds.__file__).read_bytes())
            and canonical(bounds.conservative_bounds(overlay, True)) == canonical(verification["bounds"])
            and verification["bounds"]["bounded_input_can_support_thresholds"] is True,
            "conservative_gate_binding_invalid")
    freeze = read_bound(VISUAL_ROOT / "freeze.json", VISUAL_FREEZE_SHA)
    manifest = read_bound(VISUAL_ROOT / "manifest.json", freeze["manifest_sha256"], 2000000)
    require(len(manifest["images"]) == 80 and manifest.get("mock_renderer") is False
            and manifest.get("resource_limits_enforced") is True, "public_image_preparation_invalid")
    require(len(manifest["requests"]) == 66 and all(
        r["group_id"] == f"G{n:03d}" and r["input_path"] == f"inputs/group-{n:03d}.json"
        for n, r in enumerate(manifest["requests"], 1)), "source_group_ordinal_binding_invalid")
    known_images = {r["sha256"] for r in manifest["images"]}
    require(len(known_images) == 80 and {r["document_id"] for r in manifest["images"]} == set(PUBLIC_PDFS),
            "public_image_roster_invalid")
    for did, sha in PUBLIC_PDFS.items():
        pdf = visual.PUBLIC_PDF_PARENT / f"{did}.pdf"
        require(pdf.is_file() and not pdf.is_symlink() and pdf.stat().st_size <= 10485760
                and digest(pdf.read_bytes()) == sha, "public_pdf_changed")
    requests, inspected = [], set()
    for n in range(1, 68):
        name = f"requests/group-{n:03d}.json"
        wire = read_bound(INPUT_ROOT / name, summary["files"][name], visual.MAX_REQUEST_BYTES)
        body = rest_body(wire, known_images, inspected)
        gid = source_to_review[manifest["requests"][n - 1]["group_id"]] if n <= 66 else "Q067"
        requests.append({"group_id": gid, "path": name,
                         "wire_sha256": summary["files"][name], "rest_sha256": digest(body),
                         "rest_bytes": len(body)})
    expected = {r["group_id"]: ISSUED for r in requests}
    require(set(r["group_id"] for r in overlay) == set(expected) - {"Q067"}, "group_binding_invalid")
    require(scorer.ceiling(overlay, [], expected)["quality_reachable"], "input_quality_unreachable")
    return {"summary_sha256": SUMMARY_SHA, "verification_sha256": VERIFICATION_SHA,
            "visual_freeze_sha256": VISUAL_FREEZE_SHA, "requests": requests,
            "request_roster_sha256": digest(canonical(requests)), "overlay": overlay,
            "known_images": known_images, "expected_ids": expected}


def bind_group_ids(parent_pairs: list[dict]) -> dict[str, str]:
    """Keep shuffled review IDs attached to their original question slate."""
    require(type(parent_pairs) is list and len(parent_pairs) == 264, "parent_group_roster_invalid")
    mapping, pairs, slots = {}, set(), set()
    for row in parent_pairs:
        old, current, sid, pid = row["old_group_id"], row["group_id"], row["old_candidate_id"], row["pair_id"]
        require(re.fullmatch(r"G[0-9]{3}", old) is not None and re.fullmatch(r"Q[0-9]{3}", current) is not None
                and sid in ISSUED and pid not in pairs and (old, sid) not in slots,
                "parent_group_binding_invalid")
        require(old not in mapping or mapping[old] == current, "parent_group_binding_invalid")
        mapping[old] = current
        pairs.add(pid)
        slots.add((old, sid))
    require(set(mapping) == {f"G{i:03d}" for i in range(1, 67)}
            and set(mapping.values()) == {f"Q{i:03d}" for i in range(1, 67)}
            and pairs == {f"P{i:03d}" for i in range(1, 265)}, "parent_group_roster_invalid")
    return mapping


def expected_approval(admitted: dict) -> dict:
    return {"schema_version": "public_visual_calibration_v2_approval", "authorization_id": AUTHORIZATION_ID,
            "approval_reply": APPROVAL_REPLY, "guards": guards(), "code_hashes": code_hashes(),
            "summary_sha256": SUMMARY_SHA, "verification_sha256": VERIFICATION_SHA,
            "visual_freeze_sha256": VISUAL_FREEZE_SHA,
            "request_roster_sha256": admitted["request_roster_sha256"], "public_only": True}


def validate_approval(path: Path, sha: str, admitted: dict) -> None:
    require(read_bound(path, sha) == expected_approval(admitted), "approval_contract_changed")


def read_key() -> str:
    """Read only the separately selected judge key; never load application settings."""
    env = REPO / ".env"
    require(env.is_file() and not env.is_symlink() and env.stat().st_size <= 1048576,
            "source_judge_key_unavailable")
    found = []
    with env.open(encoding="utf-8-sig") as stream:
        for line in stream:
            match = re.fullmatch(r"\s*(?:export\s+)?RAG_SOURCE_JUDGE_API_KEY\s*=(.*)", line.rstrip("\r\n"))
            if match:
                raw = match[1].strip()
                if raw.startswith(("'", '"')):
                    quote, end = raw[0], raw.find(raw[0], 1)
                    require(end > 0 and (not raw[end + 1:].strip() or raw[end + 1:].strip().startswith("#")),
                            "source_judge_key_unavailable")
                    raw = raw[1:end]
                else:
                    raw = re.split(r"\s+#", raw, maxsplit=1)[0].strip()
                require(re.fullmatch(r"[!-~]{1,512}", raw) is not None, "source_judge_key_unavailable")
                found.append(raw)
    require(len(found) == 1, "source_judge_key_unavailable")
    return found[0]


def parse_response(response: httpx.Response) -> tuple[dict, tuple[int, int]]:
    if response.status_code != 200:
        code = f"provider_http_{response.status_code}"
        raise PilotError(code if code in TRANSIENT else "provider_http_permanent")
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


def failure_code(error: BaseException) -> str:
    if isinstance(error, PilotError):
        value = str(error)
        return value if re.fullmatch(r"[a-z_0-9]{1,64}", value) else "local_failure"
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return "provider_timeout"
    if isinstance(error, httpx.TransportError):
        return "provider_network"
    return "local_failure"


def progress(output: Path, value: dict) -> None:
    scratch = output / ("progress-" + uuid.uuid4().hex + ".tmp")
    write_new(scratch, value)
    os.replace(scratch, output / "progress.json")


async def run(admitted: dict, approval_sha: str, output: Path, send,
              *, ledger: Path | None = None, clock=time.monotonic, sleep=asyncio.sleep) -> dict:
    """No key/file configuration reads; transport is injected for offline contracts."""
    require(output.is_dir() and not output.is_symlink(), "output_invalid")
    ledger = ledger_dir() if ledger is None else ledger
    require(len(admitted["requests"]) == MAX_CALLS and len({r["group_id"] for r in admitted["requests"]}) == MAX_CALLS
            and {r["group_id"] for r in admitted["requests"]} == set(admitted["expected_ids"]), "physical_attempt_roster_invalid")
    start, last = clock(), None
    write_new(ledger / f"{AUTHORIZATION_ID}.run-claim.json", {
        "authorization_id": AUTHORIZATION_ID, "approval_sha256": approval_sha,
        "request_roster_sha256": admitted["request_roster_sha256"], "pid": os.getpid()})
    rows, receipts, reported_input, reported_output, known_cost, unknown = [], [], 0, 0, 0, 0
    reason, state = "complete", "complete"
    for request in admitted["requests"]:
        ceiling = scorer.ceiling(admitted["overlay"], rows, admitted["expected_ids"])
        if not ceiling["quality_reachable"]:
            reason, state = "quality_unreachable", "stopped"
            break
        if last is not None:
            await sleep(max(0, INTERVAL_SECONDS - (clock() - last)))
        require(clock() - start + CALL_SECONDS <= MAX_SECONDS, "total_time_budget")
        require((len(rows) + 1) * cost(MAX_INPUT, MAX_OUTPUT) <= COST_CAP_MICROUSD, "cost_reserve_budget")
        wire = read_bound(INPUT_ROOT / request["path"], request["wire_sha256"], visual.MAX_REQUEST_BYTES)
        body = rest_body(wire, admitted["known_images"], set(admitted["known_images"]))
        require(digest(body) == request["rest_sha256"], "request_changed")
        gid = request["group_id"]
        claim = {"authorization_id": AUTHORIZATION_ID, "group_id": gid,
                 "approval_sha256": approval_sha, "rest_sha256": request["rest_sha256"],
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
            fatal = failure not in TRANSIENT | CONTENT_FAILURES
        elapsed = int(max(0, (clock() - last) * 1000))
        if usage is None:
            unknown += 1
        else:
            reported_input += usage[0]
            reported_output += usage[1]
            known_cost += cost(*usage)
        selected = verdict["selected_ids"] if verdict else []
        rows.append({"group_id": gid, "state": "completed" if verdict else "failed", "selected_ids": selected,
                     "question_status": verdict["question_status"] if verdict else None})
        receipt = {**rows[-1], "request_sha256": request["rest_sha256"],
                   "attempt_claim_sha256": digest(canonical(claim)), "latency_ms": elapsed,
                   "reported_usage": {"input": usage[0], "output": usage[1]} if usage else None,
                   "known_cost_microusd": cost(*usage) if usage else None, "failure_code": failure,
                   "verdict": verdict}
        write_new(output / f"attempt-{gid}.json", receipt)
        receipts.append(receipt)
        score = scorer.evaluate(admitted["overlay"], rows, admitted["expected_ids"])
        progress(output, {"status": "running", "attempts": len(rows), "valid": score["metrics"]["valid_responses"],
                          "known_cost_microusd": known_cost, "unknown_cost_attempts": unknown,
                          "last_group_id": gid, "last_failure_code": failure, "provider_calls": len(rows)})
        if fatal or known_cost > COST_CAP_MICROUSD or reported_input > MAX_CALLS * MAX_INPUT or reported_output > MAX_CALLS * MAX_OUTPUT:
            reason, state = failure or "aggregate_budget_exceeded", "stopped"
            break
    final = {"schema_version": "public_visual_calibration_v2_result", "status": state, "reason": reason,
             "authorization_id": AUTHORIZATION_ID, "approval_sha256": approval_sha,
             "request_roster_sha256": admitted["request_roster_sha256"], "provider_calls": len(rows),
             "known_cost_microusd": known_cost, "unknown_cost_attempts": unknown,
             "reported_input_tokens": reported_input, "reported_output_tokens": reported_output,
             "reserved_cost_microusd": len(rows) * cost(MAX_INPUT, MAX_OUTPUT),
             "elapsed_ms": int((clock() - start) * 1000),
             "score": scorer.evaluate(admitted["overlay"], rows, admitted["expected_ids"]),
             "ceiling": scorer.ceiling(admitted["overlay"], rows, admitted["expected_ids"]),
             "receipt_hashes": {r["group_id"]: digest(canonical(r)) for r in receipts},
             "resume_permitted": False, "heldout_opened": False, "ask_enabled": False}
    write_new(output / "result.json", final)
    progress(output, {"status": state, "reason": reason, "attempts": len(rows), "provider_calls": len(rows),
                      "calibration_passed": final["score"]["calibration_passed"], "known_cost_microusd": known_cost,
                      "unknown_cost_attempts": unknown})
    return final


async def execute(admitted: dict, approval_sha: str, output: Path) -> dict:
    key = read_key()
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
        return await run(admitted, approval_sha, output, send)


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
            visual.RESOURCE_JOB_NAME = visual.validate_resource_job_name(args.resource_job)
            require(visual._inside_windows_job(), "resource_fence_required")
        else:
            require(args.resource_job is None and args.output_dir is None, "internal_arguments_forbidden")
        admitted = admit()
        if args.prepare_approval:
            require(args.approval_file is None and args.approval_sha is None, "approval_arguments_forbidden")
            root = Path(tempfile.mkdtemp(prefix="cardchemy-visual-public-approval-v2-"))
            receipt = expected_approval(admitted)
            write_new(root / "approval.json", receipt)
            print(json.dumps({"approval_file": str(root / "approval.json"), "approval_sha256": digest(canonical(receipt)),
                              "provider_calls": 0, "requests": 67}))
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
            asyncio.run(execute(admitted, args.approval_sha, output))
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
