"""Inert keyless preflight for twelve frozen private visual-v5 cases.

Preparation validates the signed before-outcome source review, exact v8 wire,
runtime/code identities and bounded request costs. It does not read credentials,
call a provider/database, create Ask jobs or enable Ask. Supplied HTTP bytes can
be parsed with the actual v3 adapter/contract and supplied display observations
can be scored; those pure operations do not establish execution or authorization.

Before live work a separately authorized host dispatcher must enforce an OS
resource/deadline fence, isolate the judge credential, claim a durable one-use
ledger and obtain fresh read-only SQL/PDF/context guards AFTER each quota wait.
The old diagnostic/bridge is evidence identity, never a current source grant.
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_CEILING
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.ai import source_judgment_visual_v5 as contract
import navigation_raw_query_projection_v1 as raw_projection
import score_private_source_display_v8 as scorer

SCHEMA = "private_visual_trial_v8_preflight"
LIVE_AUTHORIZED = False
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/" + contract.MODEL + ":generateContent"
MAX_CALLS = 12
MAX_CALL_SECONDS = 120
MIN_CALL_INTERVAL_SECONDS = 30
MAX_STARTUP_SECONDS = 30
MAX_TOTAL_SECONDS = 1800
MAX_CPU = 4
MAX_MEMORY_BYTES = 2 * 1024 * 1024 * 1024
MAX_INPUT_TOKENS = 32_768
MAX_OUTPUT_TOKENS = 4_096
MAX_COST_USD = Decimal("0.25")
INPUT_PRICE_USD_PER_MILLION = Decimal("0.30")
OUTPUT_PRICE_USD_PER_MILLION = Decimal("2.50")
MAX_HTTP_RESPONSE_BYTES = 64 * 1024
CASE_IDS = tuple(f"T{i:02}" for i in range(1, 13))
ARTIFACT_NAMES = ("roster", "labels", "stage1", "review_receipt", "requests", "bridge", "runtime")
FILES = {"roster": "roster.json", "labels": "labels.json", "stage1": "stage1-gold.json",
    "review_receipt": "review-receipt.json", "requests": "request-packet-reviewed-v3.json",
    "bridge": "bridge.json", "runtime": "runtime-manifest-v3.json"}
FROZEN_PINS = {"roster": "a067cf5fbfb589f4afd52ad71db7693c3affd11da1a74ecfafac58ec930e8e07",
    "labels": "fa721e2dd48edfafa9dbfcc27c4e051216ab038a8861887e04684c863e70778e",
    "stage1": "53f0947bc3f01c488e28edb3f941bf13e51f8c85fdf7d3e8c8788ca976ab2477",
    "review_receipt": "4f2a3b5cc0455a996a5815daafb852ce9309d78929c1fa05c92848acd642e7f4",
    "trusted_review_key": "2fc3a8810822f2dcd915872df4310955fba398efab4d79bd232e00a9ec7df3e3",
    # Exact matching v8 artifacts; the signed source review predates outcomes.
    "requests": "d9c0a1b13271d25ca89c99935ffa1e4c3ce3de5364e7e165cd8368e7a25cdc09",
    "bridge": "4a6181df5f7ddfc5601b849c264918e1b3288716e4444c2ff1ac95ad09e968fe",
    "runtime": "fb327b1684d27fea80f9404321dd84128e2a555e9db5e8975b7ebd3b3b0fdc08"}
EXTRA_CODE_PATHS = ("scripts/prepare_private_visual_trial_v8.py",
    "scripts/score_private_source_display_v8.py", "scripts/score_private_source_display_v6.py",
    "scripts/navigation_raw_query_projection_v1.py", "backend/app/ai/source_judgment_visual.py",
    "backend/app/ai/source_judgment_visual_v2.py", "backend/app/ai/source_judgment_visual_v3.py",
    "backend/app/ai/source_judgment_visual_v4.py", "backend/app/ai/source_judgment_visual_v5.py",
    "backend/app/ai/source_navigation_context_v1.py", "backend/app/ai/source_navigation_context_v2.py",
    "backend/app/ai/providers/source_visual.py",
    "backend/app/ai/providers/source_visual_v5.py", "backend/app/ai/providers/__init__.py",
    "backend/app/ai/rate_limit.py")


class Refusal(ValueError):
    """Fixed content-free refusal; never source or provider exception text."""


def require(value: bool, code: str):
    if not value:
        raise Refusal(code)


def canonical(value: object) -> bytes:
    return contract.canonical(value)


def digest(value: bytes) -> str:
    return sha256(value).hexdigest()


def _bound(raw: bytes, pin: str, *, maximum: int = 2 * 1024 * 1024) -> dict:
    require(type(raw) is bytes and 0 < len(raw) <= maximum
            and scorer.legacy._sha(pin) and digest(raw) == pin, "input_changed")
    try:
        value = json.loads(raw, object_pairs_hook=scorer.legacy._unique, parse_constant=scorer.legacy._constant)
    except (ValueError, UnicodeError, RecursionError):
        raise Refusal("input_invalid") from None
    require(type(value) is dict, "input_invalid")
    return value


def guards() -> dict:
    reserved = (Decimal(MAX_INPUT_TOKENS) * INPUT_PRICE_USD_PER_MILLION
                + Decimal(MAX_OUTPUT_TOKENS) * OUTPUT_PRICE_USD_PER_MILLION) * MAX_CALLS / 1_000_000
    require(reserved <= MAX_COST_USD, "cost_envelope_invalid")
    return {"endpoint": ENDPOINT, "model": contract.MODEL, "thinking": "HIGH", "store": False,
        "max_calls": MAX_CALLS, "embedding_calls": 0, "answer_calls": 0, "verifier_calls": 0,
        "automatic_retries": 0, "min_call_interval_seconds": MIN_CALL_INTERVAL_SECONDS,
        "max_call_seconds": MAX_CALL_SECONDS, "max_startup_seconds": MAX_STARTUP_SECONDS,
        "max_total_seconds": MAX_TOTAL_SECONDS, "max_cpus": MAX_CPU, "max_memory_bytes": MAX_MEMORY_BYTES,
        "max_input_tokens_per_call": MAX_INPUT_TOKENS, "max_output_tokens_per_call": MAX_OUTPUT_TOKENS,
        "max_total_input_tokens": MAX_CALLS * MAX_INPUT_TOKENS,
        "max_total_output_tokens": MAX_CALLS * MAX_OUTPUT_TOKENS,
        "max_request_bytes": contract.MAX_REQUEST_BYTES, "max_http_response_bytes": MAX_HTTP_RESPONSE_BYTES,
        "max_verdict_bytes": contract.MAX_VERDICT_BYTES,
        "input_price_guard_per_million_usd": str(INPUT_PRICE_USD_PER_MILLION),
        "output_price_guard_per_million_usd": str(OUTPUT_PRICE_USD_PER_MILLION),
        "max_cost_usd": str(MAX_COST_USD), "reserved_cost_usd": str(reserved),
        "database_writes": 0, "fresh_sql_dispatch_check_required": True,
        "fresh_original_pdf_check_required": True, "actual_display_observation_required": True,
        "root_env_read": False, "release_gate_passed": False}


@dataclass(frozen=True, slots=True)
class FrozenCase:
    case_id: str
    request_sha256: str
    body_sha256: str
    admission_sha256: str
    current_question_sha256: str
    estimated_input_tokens: int
    request_bytes: bytes = field(repr=False)
    sources_bytes: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class PreparedTrial:
    bridge_sha256: str
    runtime_sha256: str
    requests_sha256: str
    scope_sha256: str
    code_sha256: tuple[tuple[str, str], ...]
    cases: tuple[FrozenCase, ...] = field(repr=False)
    artifacts: tuple[tuple[str, bytes], ...] = field(repr=False)
    raw_source_bytes: bytes = field(repr=False)


def _code_path(path: object) -> bool:
    return (type(path) is str and re.fullmatch(r"(?:backend|scripts)/[A-Za-z0-9_./-]+\.py", path) is not None
            and not any(part in ("", ".", "..") for part in path.split("/")))


def _runtime(manifest: dict, current_code: dict[str, bytes]) -> dict[str, str]:
    require(set(manifest) == {"schema", "actual_policy", "actual_contract", "image_sha256",
        "migration_heads", "runtime_profile", "runtime_source_hashes", "diagnostic_sha256",
        "scorer_sha256", "raw_projection_sha256"}
        and manifest["schema"] == "private_current_v8_runtime_manifest"
        and manifest["actual_policy"] == scorer.POLICY and manifest["actual_contract"] == scorer.CONTRACT
        and type(manifest["image_sha256"]) is str
        and re.fullmatch(r"sha256:[0-9a-f]{64}", manifest["image_sha256"]) is not None
        and manifest["migration_heads"] == ["20261002_0033"]
        and manifest["runtime_profile"] == {"ask": False, "judge": False,
            "contract": scorer.CONTRACT, "output": 4096, "required_policy": scorer.POLICY,
            "thinking": "high", "timeout": 120.0}
        and scorer.legacy._sha(manifest["diagnostic_sha256"])
        and scorer.legacy._sha(manifest["scorer_sha256"])
        and scorer.legacy._sha(manifest["raw_projection_sha256"])
        and type(manifest["runtime_source_hashes"]) is dict
        and manifest["runtime_source_hashes"], "runtime_manifest_invalid")
    profile = manifest["runtime_profile"]
    require(type(profile) is dict and profile["ask"] is False and profile["judge"] is False
        and type(profile["output"]) is int and type(profile["timeout"]) in (int, float),
        "runtime_manifest_invalid")
    require(all(type(key) is str for key in manifest["runtime_source_hashes"]),
            "runtime_code_invalid")
    expected = {"backend/" + key: value for key, value in manifest["runtime_source_hashes"].items()}
    require(all(_code_path(name) and scorer.legacy._sha(pin) for name, pin in expected.items()),
            "runtime_code_invalid")
    expected.update({"scripts/score_private_source_display_v8.py": manifest["scorer_sha256"],
        "scripts/navigation_raw_query_projection_v1.py": manifest["raw_projection_sha256"]})
    require(type(current_code) is dict and set(current_code) == set(expected) | set(EXTRA_CODE_PATHS),
            "runtime_code_incomplete")
    hashes = {}
    for name, raw in current_code.items():
        require(_code_path(name) and type(raw) is bytes and 0 < len(raw) <= 1024 * 1024,
                "runtime_code_invalid")
        hashes[name] = digest(raw)
        require(name not in expected or hashes[name] == expected[name], "runtime_code_changed")
    return hashes


def _request(row: dict, bound: dict, roster_case: dict) -> FrozenCase:
    request = row["request"]
    require(set(request) == {"model", "store", "systemInstruction", "contents", "generationConfig"}
        and request["model"] == contract.MODEL and request["store"] is False
        and type(request["contents"]) is list and len(request["contents"]) == 1
        and set(request["contents"][0]) == {"role", "parts"} and request["contents"][0]["role"] == "user",
        "request_profile_invalid")
    parts = request["contents"][0]["parts"]
    require(type(parts) is list and len(parts) == 9 and len(row["source_bindings"]) == 4,
            "request_source_count_invalid")
    expected_ids = [f"S{i:02}" for i in range(1, 5)]
    expected_generation = {"temperature": 0, "maxOutputTokens": MAX_OUTPUT_TOKENS,
        "thinkingConfig": {"thinkingLevel": "HIGH"}, "responseMimeType": "application/json",
        "responseJsonSchema": contract.v2.v1.response_schema(expected_ids)}
    require(request["generationConfig"] == expected_generation
        and type(request["systemInstruction"]) is dict
        and set(request["systemInstruction"]) == {"parts"}
        and type(request["systemInstruction"]["parts"]) is list
        and len(request["systemInstruction"]["parts"]) == 1, "request_profile_invalid")
    suffix = contract.CONTEXT_SYSTEM_SUFFIX if bound["context_status"] == "resolved_literal_subject" else ""
    require(request["systemInstruction"]["parts"][0] == {"text": contract.v2.v1.SYSTEM + suffix},
            "request_profile_invalid")
    sources = []
    for ordinal, local in enumerate(row["source_bindings"]):
        text_part, image_part = parts[1 + ordinal * 2:3 + ordinal * 2]
        require(type(text_part) is dict and set(text_part) == {"text"}
            and type(image_part) is dict and set(image_part) == {"inline_data"}
            and type(image_part["inline_data"]) is dict
            and set(image_part["inline_data"]) == {"mime_type", "data"}
            and image_part["inline_data"]["mime_type"] == "image/png"
            and type(image_part["inline_data"]["data"]) is str, "request_source_invalid")
        try:
            source = json.loads(text_part["text"], object_pairs_hook=scorer.legacy._unique,
                                parse_constant=scorer.legacy._constant)
            image = base64.b64decode(image_part["inline_data"]["data"], validate=True)
            require(base64.b64encode(image).decode("ascii") == image_part["inline_data"]["data"],
                    "request_source_invalid")
            metadata = contract.v2.v1.inspect_png(image)
        except (ValueError, UnicodeError, TypeError, contract.VisualSourceJudgmentError):
            raise Refusal("request_source_invalid") from None
        require(type(source) is dict and set(source) == contract.v2.v1.CANDIDATE_FIELDS - {"image"}
            and source["id"] == expected_ids[ordinal]
            and type(source["context"]) is str and 0 < len(source["context"]) <= contract.MAX_CONTEXT_CHARS
            and type(source["cue"]) is str and 0 < len(source["cue"]) <= contract.MAX_CUE_CHARS,
            "request_source_invalid")
        sources.append({**local, "provider_document_alias": source["document_id"],
            "page_key": roster_case["candidates"][ordinal]["page_key"],
            "pdf_sha256": source["pdf_sha256"], "cue_sha256": digest(source["cue"].encode("utf-8")),
            "page_text_sha256": source["page_text_sha256"], "png_sha256": digest(image),
            "png_bytes": len(image), "png_width": metadata["width"], "png_height": metadata["height"]})
    encoded = canonical(request)
    body = canonical({key: value for key, value in request.items() if key != "model"})
    estimated = contract.estimate_input_tokens(request)
    require(digest(encoded) == bound["request_sha256"] and len(encoded) <= contract.MAX_REQUEST_BYTES
        and len(body) <= contract.MAX_REQUEST_BYTES and 0 < estimated <= MAX_INPUT_TOKENS,
        "request_budget_invalid")
    return FrozenCase(row["case_id"], bound["request_sha256"], digest(body), bound["admission_sha256"],
        bound["current_question_sha256"], estimated, encoded, canonical(sources))


def prepare(artifacts: dict[str, bytes], *, current_code: dict[str, bytes]) -> PreparedTrial:
    """Validate supplied bytes; hashes establish identity, never current grants."""
    require(all(scorer.legacy._sha(pin) and pin != "0" * 64 for pin in FROZEN_PINS.values()),
            "matching_v8_freeze_required")
    require(type(artifacts) is dict and set(artifacts) == set(ARTIFACT_NAMES), "artifact_set_invalid")
    values = {name: _bound(raw, FROZEN_PINS[name], maximum=scorer.MAX_REQUEST_PACKET_BYTES
        if name == "requests" else 2 * 1024 * 1024) for name, raw in artifacts.items()}
    runtime = values["runtime"]
    code = _runtime(runtime, current_code)
    source_name = "backend/app/ai/source_navigation.py"
    require(source_name in code, "runtime_code_incomplete")
    try:
        resolver = raw_projection.from_production_source(current_code[source_name], source_sha256=code[source_name])
        bridge = scorer.freeze_bridge(artifacts["roster"], artifacts["labels"], artifacts["stage1"],
            artifacts["requests"], roster_sha256=FROZEN_PINS["roster"], labels_sha256=FROZEN_PINS["labels"],
            request_packet_sha256=FROZEN_PINS["requests"], review_receipt_bytes=artifacts["review_receipt"],
            review_receipt_sha256=FROZEN_PINS["review_receipt"],
            trusted_review_key_sha256=FROZEN_PINS["trusted_review_key"], runtime_sha256=FROZEN_PINS["runtime"],
            frozen_at_utc=values["bridge"]["frozen_at_utc"], raw_query_resolver=resolver)
    except (scorer.ScoreError, raw_projection.RawQueryError):
        raise Refusal("signed_bridge_invalid") from None
    require(bridge == values["bridge"] and bridge["component"] == "private_holdout"
        and tuple(row["case_id"] for row in bridge["cases"]) == CASE_IDS
        and digest(canonical(values["requests"]["scope"])) == bridge["scope_sha256"], "bridge_invalid")
    requests = {row["case_id"]: row for row in values["requests"]["cases"]}
    roster = {row["case_id"]: row for row in values["roster"]["cases"]}
    cases = tuple(_request(requests[row["case_id"]], row, roster[row["case_id"]]) for row in bridge["cases"])
    require(len(cases) == MAX_CALLS and sum(row["context_status"] == "resolved_literal_subject"
        for row in bridge["cases"]) == 2, "case_denominator_invalid")
    guards()
    return PreparedTrial(FROZEN_PINS["bridge"], FROZEN_PINS["runtime"], FROZEN_PINS["requests"],
        bridge["scope_sha256"], tuple(sorted(code.items())), cases,
        tuple((name, artifacts[name]) for name in ARTIFACT_NAMES), current_code[source_name])


def report(prepared: PreparedTrial) -> dict:
    require(type(prepared) is PreparedTrial and len(prepared.cases) == MAX_CALLS, "prepared_invalid")
    # Supplemental new code must be frozen by the prospective host before
    # approval; the old bridge does not pin this new preflight/dispatcher.
    code_pins = dict(prepared.code_sha256)
    preflight_identity = digest(canonical({"bridge_sha256": prepared.bridge_sha256,
        "runtime_sha256": prepared.runtime_sha256, "requests_sha256": prepared.requests_sha256,
        "scope_sha256": prepared.scope_sha256, "code_sha256": code_pins, "guards": guards(),
        "cases": [{"case_id": row.case_id, "request_sha256": row.request_sha256,
            "body_sha256": row.body_sha256, "admission_sha256": row.admission_sha256,
            "current_question_sha256": row.current_question_sha256,
            "sources_sha256": digest(row.sources_bytes)} for row in prepared.cases]}))
    return {"schema": SCHEMA, "status": "preflight_passed", "live_authorized": LIVE_AUTHORIZED,
        "case_count": MAX_CALLS, "candidate_count": MAX_CALLS * 4,
        "estimated_total_input_tokens": sum(case.estimated_input_tokens for case in prepared.cases),
        "maximum_total_input_tokens": MAX_CALLS * MAX_INPUT_TOKENS,
        "runtime_code_files_verified": len(prepared.code_sha256), "signed_review_verified": True,
        "runtime_code_sha256": code_pins, "preflight_identity_sha256": preflight_identity,
        "bridge_sha256": prepared.bridge_sha256, "runtime_sha256": prepared.runtime_sha256,
        "request_packet_sha256": prepared.requests_sha256,
        "provider_calls": 0, "embedding_calls": 0, "answer_calls": 0, "verifier_calls": 0,
        "database_reads": 0, "database_writes": 0, "guards": guards(), "release_gate_passed": False}


def parse_supplied_response(case: FrozenCase, raw_http_response: bytes) -> dict:
    """Parse supplied bytes using production adapter/v5 logic; no HTTP occurs."""
    require(type(case) is FrozenCase and case.case_id in CASE_IDS
            and type(raw_http_response) is bytes and 0 < len(raw_http_response) <= MAX_HTTP_RESPONSE_BYTES,
            "response_invalid")
    # Importing this definition constructs no Settings/provider/client or engine.
    from app.ai.providers.source_visual import parse_http_response
    try:
        response = parse_http_response(raw_http_response)
        require(response.finish_reason == "STOP" and response.raw_json is not None, "response_incomplete")
        inp, out = contract.validate_usage(response.input_tokens, response.candidate_tokens,
            thinking_tokens=response.thinking_tokens)
        verdict = contract.parse_verdict(response.raw_json, [f"S{i:02}" for i in range(1, 5)])
    except contract.VisualSourceJudgmentError:
        raise Refusal("response_invalid") from None
    micro = (Decimal(inp) * INPUT_PRICE_USD_PER_MILLION + Decimal(out) * OUTPUT_PRICE_USD_PER_MILLION)
    return {"schema": SCHEMA + "_response_projection", "case_id": case.case_id,
        "request_sha256": case.request_sha256, "body_sha256": case.body_sha256,
        "selected_ids": verdict["selected_ids"], "question_status": verdict["question_status"],
        "excluded_cue_conflicts": verdict["excluded_cue_conflicts"],
        "input_tokens": inp, "output_tokens_including_thinking": out,
        "known_guard_cost_microusd": int(micro.to_integral_value(rounding=ROUND_CEILING)),
        "source_only": True, "unverified_references": True, "generated_answer": False,
        "physical_execution_proved": False, "actual_display_integrity_proved": False,
        "release_gate_passed": False}


def score_supplied_measurement(prepared: PreparedTrial, measurement: bytes, *, measurement_sha256: str) -> dict:
    """Score externally observed complete displays; this module invents no observations."""
    require(type(prepared) is PreparedTrial, "prepared_invalid")
    artifacts = dict(prepared.artifacts)
    try:
        resolver = raw_projection.from_production_source(prepared.raw_source_bytes,
            source_sha256=dict(prepared.code_sha256)["backend/app/ai/source_navigation.py"])
        return scorer.score(artifacts["roster"], artifacts["labels"], artifacts["stage1"],
            artifacts["requests"], artifacts["bridge"], measurement,
            roster_sha256=FROZEN_PINS["roster"], labels_sha256=FROZEN_PINS["labels"],
            request_packet_sha256=FROZEN_PINS["requests"], bridge_sha256=FROZEN_PINS["bridge"],
            measurement_sha256=measurement_sha256, review_receipt_bytes=artifacts["review_receipt"],
            review_receipt_sha256=FROZEN_PINS["review_receipt"],
            trusted_review_key_sha256=FROZEN_PINS["trusted_review_key"],
            runtime_sha256=FROZEN_PINS["runtime"], raw_query_resolver=resolver)
    except (scorer.ScoreError, raw_projection.RawQueryError):
        raise Refusal("measurement_invalid") from None


def _file(path: Path, *, maximum: int) -> bytes:
    require(path.is_file() and not path.is_symlink() and not getattr(path, "is_junction", lambda: False)()
            and path.resolve() == path.absolute(), "input_file_invalid")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    require(0 < len(raw) <= maximum, "input_file_invalid")
    return raw


def preflight_directory(directory: Path) -> PreparedTrial:
    require(all(scorer.legacy._sha(pin) and pin != "0" * 64 for pin in FROZEN_PINS.values()),
            "matching_v8_freeze_required")
    root = Path(tempfile.gettempdir()).resolve()
    require(directory.is_absolute() and not directory.is_symlink()
            and not getattr(directory, "is_junction", lambda: False)()
            and directory.is_dir() and directory.resolve().parent == root,
            "private_temp_required")
    artifacts = {name: _file(directory / filename, maximum=scorer.MAX_REQUEST_PACKET_BYTES
        if name == "requests" else 2 * 1024 * 1024) for name, filename in FILES.items()}
    manifest = _bound(artifacts["runtime"], FROZEN_PINS["runtime"])
    hashes = manifest.get("runtime_source_hashes")
    require(type(hashes) is dict, "runtime_manifest_invalid")
    paths = set(EXTRA_CODE_PATHS) | {"backend/" + name for name in hashes}
    require(all(_code_path(name) for name in paths), "runtime_code_invalid")
    current_code = {}
    for name in paths:
        target = REPO / name
        require(target.resolve().is_relative_to(REPO.resolve()), "runtime_code_invalid")
        current_code[name] = _file(target, maximum=1024 * 1024)
    return prepare(artifacts, current_code=current_code)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args(argv)
    if args.execute:
        print(json.dumps({"schema": SCHEMA, "status": "live_dispatch_unimplemented",
            "live_authorized": False, "provider_calls": 0, "database_reads": 0, "database_writes": 0}))
        return 2
    if not args.preflight:
        print(json.dumps({"schema": SCHEMA, "status": "unexecuted", "live_authorized": False,
            "provider_calls": 0, "database_reads": 0, "database_writes": 0}))
        return 0
    try:
        require(args.directory is not None, "arguments_invalid")
        result = report(preflight_directory(args.directory))
    except Exception:
        result = {"schema": SCHEMA, "status": "preflight_refused", "live_authorized": False,
            "provider_calls": 0, "database_reads": 0, "database_writes": 0, "release_gate_passed": False}
    print(json.dumps(result))
    return 0 if result["status"] == "preflight_passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
