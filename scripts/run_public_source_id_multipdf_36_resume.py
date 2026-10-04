"""Checkpointed, public-only Gemini 3.6 source-ID pilot (never application Ask).

The previous calibration stopped after three accepted groups and an HTTP 503.
This runner verifies that immutable ledger, then starts at group four under a
*new* exact approval. Only an explicit HTTP 503 may be retried, once, inside
this process. A stopped process can never be resumed under the same approval.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable
import json
import os
from pathlib import Path
import re
import sys
from tempfile import gettempdir
import time

import httpx

from evaluate_source_id_multipdf_36 import (
    MODEL, PACKET_SHA256, SCHEMA, THINKING, _fingerprint, _responses,
    digest, prepare, score, write_exclusive,
)
from finalize_public_source_id_multipdf import LABEL_SCHEMA, read_pinned
from prepare_public_source_id_multipdf import canonical_bytes
from run_public_source_id_multipdf_36 import (
    ENDPOINT, PilotFailure, _canonical_json, _cost_microusd,
    _failure_code, _http_call, _load_public_requests,
    _parse_provider_response, _probe_writable_directory, _rest_body,
    ensure,
)

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
from app.ai.source_judgment import parse_source_id_output  # noqa: E402


AUTHORIZATION_ID = "lane6-public-36-resume-20260929-b599f494d4774a198a6a294f92944dd9"
APPROVAL_SCHEMA = "cardchemy_public_source_id_36_resume_approval_v1"
RESUME_SCHEMA = "cardchemy_public_source_id_36_resume_v1"
MAX_NEW_CALLS = 186
MAX_NEW_INPUT_TOKENS = 1_523_712
MAX_NEW_OUTPUT_TOKENS = 190_464
MAX_NEW_COST_MICROUSD = 3_720_000
MAX_INPUT_PER_CALL = 8_192
MAX_OUTPUT_PER_CALL = 1_024
MAX_CALL_SECONDS = 30
MAX_TOTAL_SECONDS = 150 * 60
MIN_START_INTERVAL_SECONDS = 20
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_OLD_CALIBRATION_SHA256 = {
    "call-01.claim": "9fe21776ccd9a5846928b684cc52f8d974bc171c07e9d68f894152ca1fc9aaad",
    "call-02.claim": "81376ec884dcd232962ee8d4d8e34d545504dbe570e3c506613495cfbf360853",
    "call-03.claim": "09c0ba3ca6ab234cad98fc775a29368d5960663e69d47ce5937d56bd284ae07b",
    "call-04.claim": "86ba92b1a0712beaa6022f51a74b9241b36de277761677171ce5644352d90d1b",
    "live-failure.json": "40aea66d3c615b18d3e6b28b72de7014617aba712c8aa2e1fe3b7e33c9bab5a6",
    "live-run.claim": "4674b829798617a6df58aadd734e55296bd62bf5e6f9db2299a689d6a5b443a9",
    "operator-approval.json": "d4b25625ed5d838c9acefd1b5c00845b7a4787f9413fd3db02455b68cddfbc86",
    "prepare-receipt.json": "c3faba72e7ddd50bfabcb76eab7e0ffec43310d1028c5412f6595e022bf1a5c8",
    "requests.json": "c0d9ae5d3889e0988e29bde63adfa8a5e2bd84b75d27f7f8fda36a77e553ec2a",
    "response-ids.jsonl": "18d7d35db83c1efc527343d60c04d0d288ae43fab9f301b02d17d84d43a7ec5d",
    "usage-receipts.jsonl": "3b6f04eb2039e495c77de85076efa142a2d805b2b812389d4f5a4607fb930d10",
}
_OLD_RUNNER_SHA256 = "bbbde897408389ec7c75676d9c82230633e8b0572d3c8e70c9603989646e4802"
_OLD_EVALUATOR_SHA256 = "dc328cb76c88dc2d050c7006e2f05158c93d34f32ce7f3f588bbfb46a4148d08"
_OLD_KNOWN_COST_MICROUSD = 7_823
_MAX_RESERVATION_PER_CALL = 19_968


def _strict_lines(path: Path, *, max_bytes: int, max_lines: int) -> list[dict]:
    ensure(path.is_file() and not path.is_symlink() and
           path.stat().st_size <= max_bytes, "checkpoint_lines_invalid")
    raw = path.read_bytes()
    ensure(raw.endswith(b"\n") and b"\r" not in raw,
           "checkpoint_lines_invalid")
    lines = raw.splitlines(keepends=True)
    ensure(0 < len(lines) <= max_lines, "checkpoint_lines_invalid")
    items = []
    for line in lines:
        ensure(len(line) <= 4_096, "checkpoint_line_oversize")
        try:
            value = json.loads(line)
        except (ValueError, UnicodeError) as exc:
            raise PilotFailure("checkpoint_lines_invalid") from exc
        ensure(type(value) is dict and canonical_bytes(value) == line,
               "checkpoint_lines_invalid")
        items.append(value)
    return items


def _old_code_hashes() -> dict[str, str]:
    here = Path(__file__).resolve().parent
    hashes = {
        "old_runner_sha256": digest((here / "run_public_source_id_multipdf_36.py").read_bytes()),
        "old_evaluator_sha256": digest((here / "evaluate_source_id_multipdf_36.py").read_bytes()),
    }
    ensure(hashes["old_runner_sha256"] == _OLD_RUNNER_SHA256 and
           hashes["old_evaluator_sha256"] == _OLD_EVALUATOR_SHA256,
           "old_code_changed")
    return hashes


def validate_prior(prior_dir: Path, packet_dir: Path, labels_path: Path,
                   labels_sha: str, freeze_sha: str) -> tuple[dict, dict, dict]:
    """Read-only validation; never expose or score the three selected IDs."""
    ensure(prior_dir.is_dir() and not prior_dir.is_symlink() and
           labels_path.is_file() and not labels_path.is_symlink() and
           digest(labels_path.read_bytes()) == labels_sha and
           _HEX64.fullmatch(labels_sha) and _HEX64.fullmatch(freeze_sha),
           "checkpoint_input_invalid")
    old_code = _old_code_hashes()
    for name, expected in _OLD_CALIBRATION_SHA256.items():
        path = prior_dir / name
        ensure(path.is_file() and not path.is_symlink() and
               digest(path.read_bytes()) == expected,
               "checkpoint_file_changed")
    prepared, receipt = _load_public_requests(
        prior_dir, _OLD_CALIBRATION_SHA256["prepare-receipt.json"], packet_dir)
    ensure(prepared["split"] == "calibration" and
           receipt["labels_sha256"] == labels_sha and
           receipt["freeze_receipt_sha256"] == freeze_sha and
           receipt["callable_count"] == 48 and
           receipt["clarification_count"] == 0 and
           prepared["fingerprint"] == _fingerprint(PACKET_SHA256, labels_sha, freeze_sha),
           "checkpoint_contract_mismatch")
    approval = _canonical_json(prior_dir / "operator-approval.json", 4_096)
    ensure(approval.get("operator_approved") is True and
           approval.get("authorization_id") ==
           "lane6-public-36-eight-pdf-20260929-ff03e1f99d40410189f1f554b90a578c" and
           approval.get("requests_sha256") == receipt["requests_sha256"] and
           approval.get("fingerprint") == receipt["fingerprint"],
           "checkpoint_approval_mismatch")
    failure = _canonical_json(prior_dir / "live-failure.json", 4_096)
    ensure(failure.get("status") == "stopped_no_retry" and
           failure.get("reason") == "provider_http_error" and
           failure.get("http_status") == 503 and
           type(failure.get("attempts")) is int and failure["attempts"] == 4 and
           failure.get("failed_attempt_cost_unknown") is True and
           failure.get("known_cost_microusd") == _OLD_KNOWN_COST_MICROUSD,
           "checkpoint_failure_mismatch")
    run_claim = _canonical_json(prior_dir / "live-run.claim", 4_096)
    ensure(run_claim.get("split") == "calibration" and
           run_claim.get("fingerprint") == receipt["fingerprint"] and
           run_claim.get("requests_sha256") == receipt["requests_sha256"],
           "checkpoint_run_claim_mismatch")
    rows = prepared["requests"]
    response_lines = _strict_lines(prior_dir / "response-ids.jsonl",
                                   max_bytes=16_384, max_lines=3)
    usage_lines = _strict_lines(prior_dir / "usage-receipts.jsonl",
                                max_bytes=16_384, max_lines=3)
    ensure(len(response_lines) == len(usage_lines) == 3,
           "checkpoint_prefix_invalid")
    total_cost = 0
    for index, row in enumerate(rows[:4]):
        claim = _canonical_json(prior_dir / f"call-{index + 1:02d}.claim", 4_096)
        ensure(row["status"] == "callable" and
               claim.get("group_id") == row["group_id"] and
               claim.get("wire_sha256") == row["wire_sha256"],
               "checkpoint_claim_mismatch")
        if index == 3:
            continue
        accepted = response_lines[index]
        usage = usage_lines[index]
        ensure(set(accepted) == {"group_id", "wire_sha256", "raw_json"} and
               accepted["group_id"] == row["group_id"] and
               accepted["wire_sha256"] == row["wire_sha256"] and
               type(accepted["raw_json"]) is str and
               len(accepted["raw_json"].encode("utf-8")) <= 4_096,
               "checkpoint_response_mismatch")
        issued = [item["id"] for item in row["wire"]["user_payload"]["candidates"]]
        try:
            parse_source_id_output(accepted["raw_json"], issued)
        except Exception as exc:
            raise PilotFailure("checkpoint_response_mismatch") from exc
        ensure(set(usage) == {"group_id", "finish_reason", "input_tokens",
                              "output_tokens", "cost_microusd"} and
               usage["group_id"] == row["group_id"] and
               usage["finish_reason"] == "STOP" and
               type(usage["input_tokens"]) is int and
               type(usage["output_tokens"]) is int and
               0 <= usage["input_tokens"] <= MAX_INPUT_PER_CALL and
               0 <= usage["output_tokens"] <= MAX_OUTPUT_PER_CALL and
               usage["cost_microusd"] == _cost_microusd(
                   usage["input_tokens"], usage["output_tokens"]),
               "checkpoint_usage_mismatch")
        total_cost += usage["cost_microusd"]
    ensure(total_cost == _OLD_KNOWN_COST_MICROUSD,
           "checkpoint_cost_mismatch")
    checkpoint = {"schema": RESUME_SCHEMA + "_prior_checkpoint",
                  "source_packet_sha256": PACKET_SHA256,
                  "labels_sha256": labels_sha,
                  "freeze_receipt_sha256": freeze_sha,
                  "fingerprint": receipt["fingerprint"],
                  "prior_accepted_groups": 3,
                  "prior_failed_http_status": 503,
                  "prior_known_cost_microusd": _OLD_KNOWN_COST_MICROUSD,
                  "prior_files_sha256": _OLD_CALIBRATION_SHA256,
                  **old_code}
    return prepared, receipt, checkpoint


def _approval_claim_path(approval_sha: str) -> Path:
    ensure(type(approval_sha) is str and _HEX64.fullmatch(approval_sha),
           "approval_hash_required")
    directory = Path(gettempdir()).resolve() / "cardchemy-source-id-36-resume-ledger"
    directory.mkdir(mode=0o700 if os.name != "nt" else 0o777, exist_ok=True)
    ensure(directory.is_dir() and not directory.is_symlink(),
           "approval_ledger_unavailable")
    return directory / f"approval-{approval_sha}.claim"


def approval_template(checkpoint: dict) -> dict:
    """Return the exact canonical receipt fields for a separate operator approval."""
    return {
        "schema": APPROVAL_SCHEMA,
        "authorization_id": AUTHORIZATION_ID,
        "operator_approved": True,
        "prior_checkpoint_sha256": digest(canonical_bytes(checkpoint)),
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "old_runner_sha256": _OLD_RUNNER_SHA256,
        "old_evaluator_sha256": _OLD_EVALUATOR_SHA256,
        "source_packet_sha256": PACKET_SHA256,
        "labels_sha256": checkpoint["labels_sha256"],
        "freeze_receipt_sha256": checkpoint["freeze_receipt_sha256"],
        "fingerprint": checkpoint["fingerprint"],
        "endpoint": ENDPOINT, "model": MODEL, "thinking": THINKING,
        "store": False, "split_sequence": ["calibration", "heldout_if_passed"],
        "max_new_physical_calls": MAX_NEW_CALLS,
        "max_new_input_tokens": MAX_NEW_INPUT_TOKENS,
        "max_new_output_tokens": MAX_NEW_OUTPUT_TOKENS,
        "max_new_cost_microusd": MAX_NEW_COST_MICROUSD,
        "max_input_tokens_per_call": MAX_INPUT_PER_CALL,
        "max_output_tokens_per_call": MAX_OUTPUT_PER_CALL,
        "max_call_seconds": MAX_CALL_SECONDS,
        "max_total_seconds": MAX_TOTAL_SECONDS,
        "min_start_interval_seconds": MIN_START_INTERVAL_SECONDS,
        "max_http_503_retries_per_group": 1,
        "input_price_usd_per_million": "1.50",
        "output_price_usd_per_million": "7.50",
        "prior_known_cost_microusd": _OLD_KNOWN_COST_MICROUSD,
        "prior_failed_cost_unknown": True,
    }


def validate_approval(path: Path, approval_sha: str, checkpoint: dict) -> dict:
    ensure(AUTHORIZATION_ID != "PENDING_SEPARATE_OPERATOR_APPROVAL",
           "separate_operator_approval_required")
    approval = _canonical_json(path, 8_192)
    expected = approval_template(checkpoint)
    ensure(type(approval_sha) is str and _HEX64.fullmatch(approval_sha) and
           digest(path.read_bytes()) == approval_sha and approval == expected,
           "approval_envelope_mismatch")
    return approval


def _append_sync(path: Path, value: dict) -> None:
    with path.open("ab") as stream:
        stream.write(canonical_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())


def _pinned_prior_receipts(prior_dir: Path) -> tuple[bytes, bytes]:
    """Read exact immutable bytes once; these are the bytes copied to output."""
    originals = []
    for name in ("response-ids.jsonl", "usage-receipts.jsonl"):
        path = prior_dir / name
        ensure(path.is_file() and not path.is_symlink() and
               path.stat().st_size <= 16_384, "checkpoint_file_changed")
        raw = path.read_bytes()
        ensure(digest(raw) == _OLD_CALIBRATION_SHA256[name],
               "checkpoint_file_changed")
        originals.append(raw)
    return originals[0], originals[1]


class _PilotState:
    def __init__(self, *, clock: Callable[[], float], wall_clock: Callable[[], float],
                 sleeper: Callable[[float], Awaitable[None]], output: Path):
        self.clock = clock
        self.wall_clock = wall_clock
        self.sleeper = sleeper
        self.output = output
        self.started = clock()
        self.last_start: float | None = None
        self.last_503_received: float | None = None
        self.calls = 0
        self.input_reserved = 0
        self.output_reserved = 0
        self.cost_reserved_microusd = 0
        self.known_cost_microusd = 0
        self.observed_input_tokens = 0
        self.observed_output_tokens = 0
        self.successes = 0
        self.http_503_first_attempts = 0
        self.failed_cost_unknown = False

    def _remaining(self) -> float:
        remaining = MAX_TOTAL_SECONDS - (self.clock() - self.started)
        ensure(remaining > 0, "total_time_budget")
        return remaining

    async def spacing(self) -> None:
        deadline = self.clock()
        if self.last_start is not None:
            deadline = max(deadline, self.last_start + MIN_START_INTERVAL_SECONDS)
        if self.last_503_received is not None:
            deadline = max(deadline,
                           self.last_503_received + MIN_START_INTERVAL_SECONDS)
        pause = deadline - self.clock()
        if pause > 0:
            await self.sleeper(pause)
        self._remaining()

    def reserve(self, row: dict, *, split: str, attempt_in_group: int) -> float:
        self._remaining()
        ensure(self.calls < MAX_NEW_CALLS and
               self.input_reserved + MAX_INPUT_PER_CALL <= MAX_NEW_INPUT_TOKENS and
               self.output_reserved + MAX_OUTPUT_PER_CALL <= MAX_NEW_OUTPUT_TOKENS and
               self.cost_reserved_microusd + _MAX_RESERVATION_PER_CALL <=
               MAX_NEW_COST_MICROUSD, "physical_budget")
        number = self.calls + 1
        write_exclusive(self.output / f"call-{number:03d}.claim", {
            "schema": RESUME_SCHEMA + "_physical_claim",
            "number": number, "split": split, "group_id": row["group_id"],
            "wire_sha256": row["wire_sha256"],
            "attempt_in_group": attempt_in_group,
            "reserved_input_tokens": MAX_INPUT_PER_CALL,
            "reserved_output_tokens": MAX_OUTPUT_PER_CALL,
            "reserved_cost_microusd": _MAX_RESERVATION_PER_CALL,
            "started_unix_ms": int(self.wall_clock() * 1_000),
        })
        self.calls = number
        self.input_reserved += MAX_INPUT_PER_CALL
        self.output_reserved += MAX_OUTPUT_PER_CALL
        self.cost_reserved_microusd += _MAX_RESERVATION_PER_CALL
        self.last_start = self.clock()
        return self.last_start

    def summary(self) -> dict:
        return {"new_physical_calls": self.calls,
                "new_accepted_groups": self.successes,
                "new_input_tokens_reserved": self.input_reserved,
                "new_output_tokens_reserved": self.output_reserved,
                "new_cost_reserved_microusd": self.cost_reserved_microusd,
                "new_known_cost_microusd": self.known_cost_microusd,
                "new_observed_input_tokens": self.observed_input_tokens,
                "new_observed_output_tokens": self.observed_output_tokens,
                "new_failed_call_cost_unknown": self.failed_cost_unknown,
                "http_503_first_attempts": self.http_503_first_attempts}


async def _run_split(prepared: dict, rows: list[dict], state: _PilotState,
                     transport: Callable[[dict], Awaitable[httpx.Response]],
                     response_path: Path, usage_path: Path) -> None:
    """Append accepted rows only. Any unresolved physical claim stops the run."""
    split = prepared["split"]
    for row in rows:
        ensure(row["status"] == "callable", "callable_row_required")
        _rest_body(row["wire"])
        issued = [item["id"] for item in row["wire"]["user_payload"]["candidates"]]
        for attempt_in_group in (1, 2):
            await state.spacing()
            claim_started = state.reserve(row, split=split,
                                          attempt_in_group=attempt_in_group)
            response = await asyncio.wait_for(
                transport(row["wire"]),
                timeout=min(MAX_CALL_SECONDS, state._remaining()),
            )
            if response.status_code == 503:
                state.last_503_received = state.clock()
                state.failed_cost_unknown = True
                if attempt_in_group == 1:
                    state.http_503_first_attempts += 1
                _append_sync(state.output / "physical-outcomes.jsonl", {
                    "number": state.calls, "split": split,
                    "group_id": row["group_id"],
                    "attempt_in_group": attempt_in_group,
                    "http_status": 503, "accepted": False,
                    "cost_receipt_missing": True,
                    "elapsed_ms": max(0, int((state.clock() - claim_started) * 1_000)),
                })
                if attempt_in_group == 1:
                    continue
                raise PilotFailure("provider_http_503_second")
            raw_json, input_tokens, output_tokens = _parse_provider_response(
                response, issued)
            state.known_cost_microusd += _cost_microusd(input_tokens, output_tokens)
            state.observed_input_tokens += input_tokens
            state.observed_output_tokens += output_tokens
            accepted = {"group_id": row["group_id"],
                        "wire_sha256": row["wire_sha256"],
                        "raw_json": raw_json}
            usage = {"group_id": row["group_id"], "finish_reason": "STOP",
                     "input_tokens": input_tokens,
                     "output_tokens": output_tokens,
                     "cost_microusd": _cost_microusd(input_tokens, output_tokens)}
            _append_sync(response_path, accepted)
            _append_sync(usage_path, usage)
            _append_sync(state.output / "physical-outcomes.jsonl", {
                "number": state.calls, "split": split,
                "group_id": row["group_id"],
                "attempt_in_group": attempt_in_group,
                "http_status": 200, "accepted": True,
                "cost_receipt_missing": False,
                "elapsed_ms": max(0, int((state.clock() - claim_started) * 1_000)),
            })
            state.successes += 1
            break


def _score_complete_split(prepared: dict, labels_path: Path, labels_sha: str,
                          freeze_sha: str, response_path: Path,
                          checkpoint_sha: str, output: Path) -> dict:
    _validate_accepted_split(prepared, response_path,
                             response_path.parent / "usage-receipts.jsonl")
    ensure(digest(labels_path.read_bytes()) == labels_sha,
           "labels_changed")
    labels = read_pinned(labels_path, labels_sha, 100_000)
    ensure(labels.get("schema") == LABEL_SCHEMA and
           labels.get("packet_sha256") == PACKET_SHA256 and
           len(labels.get("groups", [])) == 96,
           "labels_contract_mismatch")
    responses = _responses(response_path, prepared["requests"])
    expected = [row["group_id"] for row in prepared["requests"]
                if row["status"] == "callable"]
    ensure(len(expected) == len(responses) == 48 and
           set(expected) == set(responses), "split_incomplete")
    metrics = score(prepared, labels, responses)
    result = {"schema": SCHEMA, "split": prepared["split"],
              "fingerprint": prepared["fingerprint"],
              "source_packet_sha256": PACKET_SHA256,
              "labels_sha256": labels_sha,
              "freeze_receipt_sha256": freeze_sha,
              "requests_sha256": digest(canonical_bytes(prepared)),
              "responses_sha256": digest(response_path.read_bytes()),
              "prior_checkpoint_sha256": checkpoint_sha,
              "public_passed": metrics["public_passed"],
              "release_gate_passed": False,
              "metrics": metrics}
    write_exclusive(output / f"{prepared['split']}-score.json", result)
    return result


def _validate_accepted_split(prepared: dict, response_path: Path,
                             usage_path: Path) -> None:
    """Refuse an incomplete or torn response/usage pair before any score gate."""
    rows = [row for row in prepared["requests"] if row["status"] == "callable"]
    response_lines = _strict_lines(response_path, max_bytes=256_000,
                                   max_lines=48)
    usage_lines = _strict_lines(usage_path, max_bytes=64_000,
                                max_lines=48)
    ensure(len(rows) == len(response_lines) == len(usage_lines),
           "accepted_pair_incomplete")
    for row, response, usage in zip(rows, response_lines, usage_lines,
                                    strict=True):
        ensure(set(response) == {"group_id", "wire_sha256", "raw_json"} and
               response["group_id"] == row["group_id"] and
               response["wire_sha256"] == row["wire_sha256"] and
               type(response["raw_json"]) is str and
               set(usage) == {"group_id", "finish_reason", "input_tokens",
                              "output_tokens", "cost_microusd"} and
               usage["group_id"] == row["group_id"] and
               usage["finish_reason"] == "STOP" and
               type(usage["input_tokens"]) is int and
               type(usage["output_tokens"]) is int and
               0 <= usage["input_tokens"] <= MAX_INPUT_PER_CALL and
               0 <= usage["output_tokens"] <= MAX_OUTPUT_PER_CALL and
               type(usage["cost_microusd"]) is int and
               usage["cost_microusd"] == _cost_microusd(
                   usage["input_tokens"], usage["output_tokens"]),
               "accepted_pair_invalid")
        issued = [item["id"] for item in row["wire"]["user_payload"]["candidates"]]
        try:
            parse_source_id_output(response["raw_json"], issued)
        except Exception as exc:
            raise PilotFailure("accepted_pair_invalid") from exc


async def run_pilot(prior_dir: Path, packet_dir: Path, labels_path: Path,
                    labels_sha: str, freeze_sha: str, approval: dict,
                    approval_sha: str, output: Path,
                    transport: Callable[[dict], Awaitable[httpx.Response]],
                    *, clock: Callable[[], float] = time.monotonic,
                    wall_clock: Callable[[], float] = time.time,
                    sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
                    prevalidated: tuple[dict, dict, dict] | None = None) -> dict:
    prepared, _receipt, checkpoint = (prevalidated if prevalidated is not None else
                                      validate_prior(prior_dir, packet_dir,
                                                     labels_path, labels_sha, freeze_sha))
    resolved_output = output.resolve()
    resolved_prior = prior_dir.resolve()
    ensure(output.is_absolute() and not output.exists() and
           output.parent.is_dir() and not output.parent.is_symlink() and
           Path(gettempdir()).resolve() in resolved_output.parents and
           resolved_output != resolved_prior and
           resolved_prior not in resolved_output.parents,
           "os_temp_output_required")
    prior_response_bytes, prior_usage_bytes = _pinned_prior_receipts(prior_dir)
    checkpoint_sha = digest(canonical_bytes(checkpoint))
    ensure(approval["prior_checkpoint_sha256"] == checkpoint_sha and
           approval["authorization_id"] == AUTHORIZATION_ID,
           "run_approval_mismatch")
    claim_path = _approval_claim_path(approval_sha)
    ensure(not claim_path.exists() and not claim_path.is_symlink(),
           "approval_claim_consumed")
    output.mkdir(mode=0o700 if os.name != "nt" else 0o777)
    write_exclusive(claim_path, {"schema": RESUME_SCHEMA + "_approval_claim",
                                 "authorization_id": AUTHORIZATION_ID,
                                 "prior_checkpoint_sha256": checkpoint_sha,
                                 "output_name": output.name})
    write_exclusive(output / "run.claim", {"approval_sha256": approval_sha,
                                           "prior_checkpoint_sha256": checkpoint_sha})
    write_exclusive(output / "prior-checkpoint.json", checkpoint)
    calibration_dir = output / "calibration"
    calibration_dir.mkdir()
    response_path = calibration_dir / "response-ids.jsonl"
    usage_path = calibration_dir / "usage-receipts.jsonl"
    # Copy, never move or rewrite, the three already accepted public receipts.
    with response_path.open("xb") as stream:
        stream.write(prior_response_bytes)
        stream.flush()
        os.fsync(stream.fileno())
    with usage_path.open("xb") as stream:
        stream.write(prior_usage_bytes)
        stream.flush()
        os.fsync(stream.fileno())
    with (output / "physical-outcomes.jsonl").open("xb"):
        pass
    state = _PilotState(clock=clock, wall_clock=wall_clock,
                        sleeper=sleeper, output=output)
    calibration_passed = False
    heldout_opened = False
    try:
        await _run_split(prepared, prepared["requests"][3:], state, transport,
                         response_path, usage_path)
        cal_score = _score_complete_split(prepared, labels_path, labels_sha,
                                          freeze_sha, response_path,
                                          checkpoint_sha, output)
        if not cal_score["public_passed"]:
            result = {"status": "calibration_gate_failed",
                      "calibration_passed": False, "heldout_opened": False,
                      "calibration_score_sha256": digest(canonical_bytes(cal_score)),
                      **state.summary()}
            write_exclusive(output / "pilot-result.json", result)
            return result
        calibration_passed = True
        # Recompute the calibration score from the actual accepted prefix
        # immediately before releasing the independently frozen heldout.
        score_check = score(prepared,
                            read_pinned(labels_path, labels_sha, 100_000),
                            _responses(response_path, prepared["requests"]))
        _validate_accepted_split(prepared, response_path, usage_path)
        ensure(score_check == cal_score["metrics"] and
               digest((output / "calibration-score.json").read_bytes()) ==
               digest(canonical_bytes(cal_score)), "calibration_gate_changed")
        heldout_dir = output / "heldout"
        prepare(packet_dir, labels_path, labels_sha, freeze_sha, "heldout",
                heldout_dir, output / "calibration-score.json",
                digest(canonical_bytes(cal_score)))
        heldout_opened = True
        heldout, _heldout_receipt = _load_public_requests(
            heldout_dir, digest((heldout_dir / "prepare-receipt.json").read_bytes()),
            packet_dir)
        heldout_response = heldout_dir / "response-ids.jsonl"
        heldout_usage = heldout_dir / "usage-receipts.jsonl"
        with heldout_response.open("xb"):
            pass
        with heldout_usage.open("xb"):
            pass
        await _run_split(heldout, heldout["requests"], state, transport,
                         heldout_response, heldout_usage)
        heldout_score = _score_complete_split(heldout, labels_path, labels_sha,
                                              freeze_sha, heldout_response,
                                              checkpoint_sha, output)
        result = {"status": "public_pilot_complete",
                  "calibration_passed": True,
                  "heldout_opened": True,
                  "heldout_passed": heldout_score["public_passed"],
                  "calibration_score_sha256": digest(canonical_bytes(cal_score)),
                  "heldout_score_sha256": digest(canonical_bytes(heldout_score)),
                  "release_gate_passed": False, **state.summary()}
        write_exclusive(output / "pilot-result.json", result)
        return result
    except (Exception, asyncio.CancelledError) as exc:
        code = _failure_code(exc)
        if isinstance(exc, PilotFailure) and str(exc) == "provider_http_503_second":
            code = "provider_http_503_second"
        http_status = None
        if code.startswith("provider_http_") and code != "provider_http_503_second":
            maybe_status = code.removeprefix("provider_http_")
            if maybe_status.isdecimal():
                http_status = int(maybe_status)
            code = "provider_http_error"
        elif code == "provider_http_503_second":
            http_status = 503
        if state.calls > state.successes:
            state.failed_cost_unknown = True
        result = {"status": "stopped_no_replay", "reason": code,
                  "calibration_passed": calibration_passed,
                  "heldout_opened": heldout_opened,
                  "release_gate_passed": False, **state.summary()}
        if http_status is not None:
            result["http_status"] = http_status
        write_exclusive(output / "pilot-failure.json", result)
        return result


def _admit(args: argparse.Namespace) -> tuple[dict, dict, dict, dict]:
    temp = Path(gettempdir()).resolve()
    for path in (args.prior_dir, args.packet_dir, args.labels,
                 args.approval_receipt, args.output.parent):
        ensure(path.is_absolute() and temp in path.resolve().parents and
               not path.is_symlink(), "os_temp_input_required")
    resolved_output = args.output.resolve()
    resolved_prior = args.prior_dir.resolve()
    ensure(args.output.is_absolute() and temp in resolved_output.parents and
           not args.output.exists() and resolved_output != resolved_prior and
           resolved_prior not in resolved_output.parents,
           "os_temp_output_required")
    prepared, receipt, checkpoint = validate_prior(
        args.prior_dir, args.packet_dir, args.labels,
        args.labels_sha256, args.freeze_receipt_sha256)
    approval = validate_approval(args.approval_receipt,
                                 args.approval_sha256, checkpoint)
    _probe_writable_directory(args.output.parent)
    claim_path = _approval_claim_path(args.approval_sha256)
    _probe_writable_directory(claim_path.parent)
    ensure(not claim_path.exists() and not claim_path.is_symlink(),
           "approval_claim_consumed")
    return prepared, receipt, checkpoint, approval


async def _live_cli(args: argparse.Namespace,
                    admitted: tuple[dict, dict, dict, dict]) -> dict:
    # All packet/hash/approval/ACL checks complete before reading a credential.
    from app.config import Settings
    api_key = Settings().rag_ai_api_key_value
    ensure(bool(api_key), "provider_key_unavailable")
    async with httpx.AsyncClient(timeout=MAX_CALL_SECONDS,
                                 follow_redirects=False) as client:
        return await run_pilot(
            args.prior_dir, args.packet_dir, args.labels,
            args.labels_sha256, args.freeze_receipt_sha256,
            admitted[3], args.approval_sha256, args.output,
            lambda wire: _http_call(client, api_key, wire),
            prevalidated=admitted[:3],
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior-dir", type=Path, required=True)
    parser.add_argument("--packet-dir", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--labels-sha256", required=True)
    parser.add_argument("--freeze-receipt-sha256", required=True)
    parser.add_argument("--approval-receipt", type=Path, required=True)
    parser.add_argument("--approval-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    try:
        admitted = _admit(args)
        if args.preflight_only:
            result = {"status": "preflight_passed", "new_calls": 0,
                      "remaining_calibration_groups": 45,
                      "conditional_heldout_groups": 48,
                      "prior_checkpoint_sha256": digest(canonical_bytes(admitted[2]))}
        else:
            result = asyncio.run(_live_cli(args, admitted))
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] in {
            "preflight_passed", "calibration_gate_failed", "public_pilot_complete"
        } else 2
    except (PilotFailure, OSError, ValueError, KeyError, TypeError) as exc:
        code = str(exc) if isinstance(exc, PilotFailure) else type(exc).__name__
        print(json.dumps({"status": "pilot_rejected", "reason": code,
                          "new_calls": 0}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
