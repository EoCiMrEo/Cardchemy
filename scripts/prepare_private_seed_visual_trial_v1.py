"""Inert fourteen-case seed diagnostic; exact independent reviews, no authority.

The seed packet and independent review/reuse witness are SHA pinned. They are
not signed and never become a current source grant. The existing private12 v8
stage and helpers remain unchanged. Shared v8 utility bodies have isolated
function globals; importing this adapter never mutates their modules.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime
from decimal import Decimal, ROUND_CEILING
from hashlib import sha256
import json
import re
from pathlib import Path
import sys
from types import FunctionType

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
import prepare_private_visual_trial_v8 as base
import score_private_source_display_v8 as scorer
import navigation_raw_query_projection_v1 as raw_projection
from app.ai import source_judgment_visual_v5 as contract
from app.ai.source_navigation_context_v2 import resolve_subject_context

SCHEMA = "private_seed_visual_trial_v1_preflight"
LIVE_AUTHORIZED = False
CASE_IDS = tuple([*(f"D{i:02}" for i in range(1, 7)), *(f"P{i:02}" for i in range(1, 5)), "H01", "N12", "U01", "U02"])
MAX_CALLS, MAX_CALL_SECONDS, MIN_CALL_INTERVAL_SECONDS = 14, 120, 30
MAX_STARTUP_SECONDS, MAX_TOTAL_SECONDS, MAX_CPU = 30, 2400, 4
MAX_MEMORY_BYTES, MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS = 2147483648, 32768, 4096
MAX_COST_USD = Decimal("0.30")
INPUT_PRICE_USD_PER_MILLION, OUTPUT_PRICE_USD_PER_MILLION = Decimal("0.30"), Decimal("2.50")
MAX_HTTP_RESPONSE_BYTES = 64 * 1024
ENDPOINT = base.ENDPOINT
ARTIFACT_NAMES = ("source", "review", "witness", "panel", "runtime")
FILES = {"source": "seed-preparation.json", "review": "independent-review-v2.json",
    "witness": "review-reuse-witness-v2.json", "panel": "panel-manifest.json", "runtime": "runtime-manifest-v3.json"}
FROZEN_PINS = {
    "source": "4e57382d8bce23aac355968a07662814a935a04b91ef1a9f516b6157d1627380",
    "review": "fe101e4d4a4e799f217b6539b0a3c63989754adf95f759958580ed4fe9d802fe",
    "witness": "f112b4e2217c987603010674bec91c48ab74fac9b382d7af97b8a9f55ff65647",
    "panel": "e793e18b260e79a0278c9b921c7af53a2149c4d5e4bd099237bab80146265e76",
    "runtime": "fb327b1684d27fea80f9404321dd84128e2a555e9db5e8975b7ebd3b3b0fdc08"}
SEED_CODE_PATHS = (
    "scripts/prepare_private_seed_visual_trial_v1.py", "scripts/run_private_seed_visual_trial_v1.py",
    "scripts/launch_private_seed_visual_trial_v1.py", "backend/scripts/private_seed_visual_dispatch_guard_v1.py",
    "backend/scripts/rehearse_private_seed_visual_dispatch_v1.py",
    "backend/scripts/execute_private_seed_visual_trial_v1.py", "backend/scripts/private_seed_visual_trial_entry_v1.py")
EXTRA_CODE_PATHS = tuple(sorted(set(base.EXTRA_CODE_PATHS) | set(SEED_CODE_PATHS)
    | {"scripts/prepare_private_visual_trial_v8.py", "scripts/run_private_visual_trial_v8.py",
       "scripts/launch_private_visual_trial_v8.py", "backend/scripts/private_visual_dispatch_guard_v8.py",
       "backend/scripts/execute_private_visual_trial_v8.py", "backend/scripts/rehearse_private_visual_dispatch_v8.py"}))
FrozenCase, PreparedTrial, Refusal = base.FrozenCase, base.PreparedTrial, base.Refusal
require, canonical, digest, _bound, _code_path, _file = base.require, base.canonical, base.digest, base._bound, base._code_path, base._file


def _shared(function):
    """Reuse an immutable body with this module's explicit, isolated globals."""
    result = FunctionType(function.__code__, globals(), function.__name__, function.__defaults__, function.__closure__)
    result.__kwdefaults__ = function.__kwdefaults__
    return result


guards = _shared(base.guards)
_runtime = _shared(base._runtime)


def _scope(packet):
    return {"principal_id": packet["principal_id"], "subject_id": packet["subject_id"], **packet["scope"]}


def _review(packet, review, witness):
    require(packet["schema"] == "private_seed_visual_v8_preparation_v1"
        and packet["policy"] == scorer.POLICY and packet["contract"] == scorer.CONTRACT
        and packet["provider_calls"] == packet["database_writes"] == 0
        and tuple(row["case_id"] for row in packet["cases"]) == CASE_IDS, "seed_packet_invalid")
    require(review["schema"] == "private_seed_source_review_v8"
        and review["source_preparation_sha256"] == witness["source_preparation_sha256"] == FROZEN_PINS["source"]
        and review["panel_manifest_sha256"] == witness["panel_manifest_sha256"] == FROZEN_PINS["panel"]
        and witness["schema"] == "private_seed_v8_exact_review_reuse_witness"
        and witness["independent_review_sha256"] == FROZEN_PINS["review"]
        and review["model_outcomes_read"] is witness["model_outcomes_read"] is False
        and review["independent_of_runtime_selection"] is True
        and review["original_pdf_full_page_png_inspected"] is True
        and witness["original_pdf_hashes_verified"] is witness["previous_labels_unchanged"] is True
        and review["provider_calls"] == review["database_writes"] == witness["provider_calls"] == witness["database_writes"] == 0
        and witness["old_exact_slots"] == 42 and witness["new_slots"] == 8
        and witness["new_case_ids"] == ["D04", "N12"], "independent_review_invalid")
    require(tuple(row["case_id"] for row in review["cases"]) == CASE_IDS, "review_case_denominator_invalid")
    provenance = {(row["case_id"], row["id"]): row for row in witness["candidate_provenance"]}
    require(len(provenance) == 50, "review_provenance_invalid")
    reviewed = {}
    for row, labels in zip(packet["cases"], review["cases"], strict=True):
        require(labels["question_sha256"] == digest(row["question"].encode())
            and labels["previous_turn_sha256"] == digest((row["previous_turn"] or "").encode())
            and labels["evaluation_role"] == row["evaluation_role"]
            and labels["require_empty_candidate_slate"] is row["require_empty_candidate_slate"]
            and labels["corpus_absence_claim"] is row["corpus_absence_claim"] is False
            and labels["expected_question_status"] == "clear", "review_question_binding_invalid")
        expected_count = 1 if row["case_id"] in ("U01", "U02") else 4
        require(len(row["candidates"]) == len(labels["candidates"]) == expected_count, "review_source_denominator_invalid")
        for ordinal, (candidate, label) in enumerate(zip(row["candidates"], labels["candidates"], strict=True), 1):
            cid = f"S{ordinal:02}"
            origin = provenance.get((row["case_id"], cid))
            require(label["id"] == cid and label["page_key"] == candidate["page_key"]
                and label["cue_sha256"] == candidate["cue_sha256"] and label["source_integrity_verified"] is True
                and label["page_useful"] in ("Yes", "No", "Unsure") and label["cue_useful"] in ("Yes", "No", "Unsure")
                and label["learning_category"] in ("direct", "concrete_learning_step", "topic_only", "unrelated")
                and type(origin) is dict and origin["candidate_label_sha256"] == digest(canonical(label)), "review_source_binding_invalid")
            if row["case_id"] in ("D04", "N12"):
                require(origin["review_origin"] == "fresh_independent_full_original_page_and_exact_cue", "review_provenance_invalid")
            else:
                require(origin["review_origin"] == "unchanged_previous_exact_before_outcomes"
                    and origin["previous_candidate_label_sha256"] == origin["candidate_label_sha256"], "review_provenance_invalid")
        reviewed[row["case_id"]] = labels
    return reviewed


def _request(row, labels, resolver):
    request = row["request"]
    require(set(request) == {"model", "store", "systemInstruction", "contents", "generationConfig"}
        and request["model"] == contract.MODEL and request["store"] is False
        and len(request["contents"]) == 1 and set(request["contents"][0]) == {"role", "parts"}
        and request["contents"][0]["role"] == "user", "request_profile_invalid")
    parts = request["contents"][0]["parts"]
    count = len(row["candidates"])
    require(len(parts) == 1 + 2 * count, "request_source_count_invalid")
    snapshot = scorer._snapshot(row["question_context"]["admission"])
    raw_query = resolver(row["question"])
    previous = row["previous_turn"] if snapshot.preceding is not None else None
    resolution = resolve_subject_context(row["question"], (("user", previous),) if previous else (), raw_navigation_query=raw_query)
    binding = contract.bind_question_context(row["question"], snapshot, checked_at=snapshot.captured_at,
        raw_navigation_query=raw_query, preceding_question=previous, anchor=resolution.anchor)
    require(binding.status != "needs_clarification"
        and binding.admission_sha256 == row["question_context"]["admission_sha256"]
        and binding.current_question_sha256 == row["question_context"]["current_question_sha256"], "admission_binding_invalid")
    envelope = json.loads(parts[0]["text"])
    sources, aliases = [], {}
    pdfs = {pdf["document_id"]: pdf for pdf in row["bindings"]}
    for ordinal, (local, label) in enumerate(zip(row["candidates"], labels["candidates"], strict=True)):
        source = json.loads(parts[1 + 2 * ordinal]["text"])
        png = base64.b64decode(parts[2 + 2 * ordinal]["inline_data"]["data"], validate=True)
        document = local["document_id"]
        aliases.setdefault(document, f"D{len(aliases) + 1:02}")
        page = local["page_text"]
        cue = page[local["start_offset"]:local["end_offset"]]
        require(set(source) == contract.v2.v1.CANDIDATE_FIELDS - {"image"}
            and set(parts[1 + 2 * ordinal]) == {"text"} and set(parts[2 + 2 * ordinal]) == {"inline_data"}
            and set(parts[2 + 2 * ordinal]["inline_data"]) == {"mime_type", "data"}
            and parts[2 + 2 * ordinal]["inline_data"]["mime_type"] == "image/png"
            and base64.b64encode(png).decode() == parts[2 + 2 * ordinal]["inline_data"]["data"]
            and source["id"] == f"S{ordinal + 1:02}" and source["document_id"] == aliases[document]
            and source["page"] == local["page_number"] and source["cue_start"] == local["start_offset"]
            and source["cue_end"] == local["end_offset"] and source["cue"] == cue
            and 0 <= local["start_offset"] < local["end_offset"] <= len(page)
            and len(cue) <= 480 and source["pdf_sha256"] == pdfs[document]["source_sha256"] == label["pdf_sha256"]
            and source["page_text_sha256"] == digest(page.encode()) == local["page_sha256"]
            and digest(cue.encode()) == label["cue_sha256"] and digest(png) == label["image_sha256"], "request_source_binding_invalid")
        require(type(source["context_start"]) is int and type(source["context_end"]) is int
            and 0 <= source["context_start"] <= local["start_offset"] < local["end_offset"] <= source["context_end"] <= len(page)
            and source["context"] == page[source["context_start"]:source["context_end"]]
            and 0 < len(source["context"]) <= contract.MAX_CONTEXT_CHARS, "request_context_binding_invalid")
        contract.v2.v1.inspect_png(png)
        sources.append({"id": source["id"], "document_id": document, "content_revision_id": local["content_revision_id"],
            "page_number": local["page_number"], "page_key": local["page_key"], "pdf_sha256": label["pdf_sha256"],
            "cue_sha256": label["cue_sha256"], "png_sha256": label["image_sha256"], "page_text_sha256": local["page_sha256"]})
    # Raster provenance is not serialized into the provider wire. Do not invent
    # a renderer receipt to rebuild it: compare the exact envelope/schema here;
    # the fresh guard separately authenticates/renders the entire wire later.
    expected_question = {"group_id": envelope["group_id"], "question": row["question"]}
    if binding.anchor is not None:
        expected_question["referent_context"] = {"literal_subject": binding.anchor.subject, "purpose": contract.CONTEXT_PURPOSE}
    system = contract.v2.v1.SYSTEM if count == 4 else contract.v2.v1.SYSTEM.replace("the four issued IDs", "every issued ID")
    if binding.anchor is not None: system += contract.CONTEXT_SYSTEM_SUFFIX
    expected_generation = {"temperature": 0, "maxOutputTokens": MAX_OUTPUT_TOKENS,
        "thinkingConfig": {"thinkingLevel": "HIGH"}, "responseMimeType": "application/json",
        "responseJsonSchema": contract.v2.v1.response_schema([source["id"] for source in sources])}
    require(type(envelope["group_id"]) is str and 0 < len(envelope["group_id"]) <= 64
        and parts[0] == {"text": canonical(expected_question).decode()}
        and request["systemInstruction"] == {"parts": [{"text": system}]}
        and request["generationConfig"] == expected_generation, "request_profile_invalid")
    encoded, body = canonical(request), canonical({k: v for k, v in request.items() if k != "model"})
    estimated = contract.estimate_input_tokens(request)
    require(len(encoded) <= contract.MAX_REQUEST_BYTES and 0 < estimated <= MAX_INPUT_TOKENS, "request_budget_invalid")
    return FrozenCase(row["case_id"], digest(encoded), digest(body), binding.admission_sha256,
        binding.current_question_sha256, estimated, encoded, canonical(sources))


def prepare(artifacts, *, current_code):
    require(type(artifacts) is dict and set(artifacts) == set(ARTIFACT_NAMES), "artifact_set_invalid")
    values = {name: _bound(raw, FROZEN_PINS[name], maximum=64 * 1024 * 1024 if name == "source" else 2 * 1024 * 1024)
        for name, raw in artifacts.items()}
    code = _runtime(values["runtime"], current_code)
    reviewed = _review(values["source"], values["review"], values["witness"])
    resolver = raw_projection.from_production_source(current_code["backend/app/ai/source_navigation.py"],
        source_sha256=code["backend/app/ai/source_navigation.py"])
    cases = tuple(_request(row, reviewed[row["case_id"]], resolver) for row in values["source"]["cases"])
    guards()
    return PreparedTrial(FROZEN_PINS["witness"], FROZEN_PINS["runtime"], FROZEN_PINS["source"],
        digest(canonical(_scope(values["source"]))), tuple(sorted(code.items())), cases,
        tuple((name, artifacts[name]) for name in ARTIFACT_NAMES), current_code["backend/app/ai/source_navigation.py"])


def report(prepared):
    require(type(prepared) is PreparedTrial and len(prepared.cases) == MAX_CALLS, "prepared_invalid")
    identities = [{"case_id": c.case_id, "request_sha256": c.request_sha256, "body_sha256": c.body_sha256,
        "admission_sha256": c.admission_sha256, "sources_sha256": digest(c.sources_bytes)} for c in prepared.cases]
    identity = digest(canonical({"inputs": FROZEN_PINS, "scope_sha256": prepared.scope_sha256,
        "code": dict(prepared.code_sha256), "guards": guards(), "cases": identities}))
    return {"schema": SCHEMA, "status": "preflight_passed", "preflight_identity_sha256": identity,
        "case_count": MAX_CALLS, "candidate_count": 50, "cases": identities, "input_sha256": dict(FROZEN_PINS),
        "runtime_code_files_verified": len(prepared.code_sha256), "runtime_code_sha256": dict(prepared.code_sha256),
        "independent_review_sha_verified": True, "signed_review_verified": False,
        "review_authority": "explicitly_pinned_independent_reviewer_and_exact_reuse_witness",
        "estimated_total_input_tokens": sum(c.estimated_input_tokens for c in prepared.cases),
        "live_authorized": False, "provider_calls": 0, "database_reads": 0, "database_writes": 0,
        "guards": guards(), "release_gate_passed": False}


def parse_supplied_response(case, raw_http_response):
    require(type(case) is FrozenCase and case.case_id in CASE_IDS and type(raw_http_response) is bytes
        and 0 < len(raw_http_response) <= MAX_HTTP_RESPONSE_BYTES, "response_invalid")
    from app.ai.providers.source_visual import parse_http_response
    response = parse_http_response(raw_http_response)
    require(response.finish_reason == "STOP" and response.raw_json is not None, "response_incomplete")
    inp, out = contract.validate_usage(response.input_tokens, response.candidate_tokens, thinking_tokens=response.thinking_tokens)
    verdict = contract.parse_verdict(response.raw_json, [row["id"] for row in json.loads(case.sources_bytes)])
    micro = Decimal(inp) * INPUT_PRICE_USD_PER_MILLION + Decimal(out) * OUTPUT_PRICE_USD_PER_MILLION
    return {"case_id": case.case_id, "selected_ids": verdict["selected_ids"], "question_status": verdict["question_status"],
        "excluded_cue_conflicts": verdict["excluded_cue_conflicts"], "input_tokens": inp, "output_tokens_including_thinking": out,
        "known_guard_cost_microusd": int(micro.to_integral_value(rounding=ROUND_CEILING))}


def score_supplied_measurement(prepared, measurement, *, measurement_sha256):
    observed = _bound(measurement, measurement_sha256, maximum=128 * 1024)
    require(observed["schema"] == "private_seed_visual_trial_v1_execution" and observed["status"] == "completed"
        and observed["synthetic_interfaces"] is False and observed["case_denominator"] == observed["completed_cases"] == 14
        and tuple(row["case_id"] for row in observed["cases"]) == CASE_IDS
        and observed["provider_calls"] == 14
        and observed["embedding_calls"] == observed["answer_calls"] == observed["verifier_calls"] == observed["automatic_retries"] == observed["database_writes"] == 0,
        "complete_measurement_required")
    review = json.loads(dict(prepared.artifacts)["review"])
    useful, shown, hits, controls, integrity = 0, 0, {}, {}, True
    for row, frozen, labels in zip(observed["cases"], prepared.cases, review["cases"], strict=True):
        indexed = {label["id"]: label for label in labels["candidates"]}
        selected = row["selected_ids"]
        require(type(selected) is list and len(selected) <= 3 and len(set(selected)) == len(selected)
            and all(s in indexed for s in selected) and row["request_sha256"] == frozen.request_sha256
            and row["admission_sha256"] == frozen.admission_sha256, "measurement_binding_invalid")
        page_credit = [indexed[s]["page_useful"] == "Yes" and indexed[s]["cue_useful"] == "Yes" for s in selected]
        shown += len(selected); useful += sum(page_credit)
        hits[row["case_id"]] = any(page_credit)
        integrity &= row["backend_association_verified"] is True and row["unverified_references"] is True
        if row["case_id"] in ("U01", "U02"):
            # The provider contract has clear/needs_clarification only. A clear
            # question with zero eligible issued IDs is the local no-match
            # outcome; never invent a provider `no_match` status.
            controls[row["case_id"]] = selected == [] and row["question_status"] == "clear"
    seed_hits = sum(hits[cid] for cid in CASE_IDS[:11])
    passed = shown > 0 and useful * 100 >= shown * 80 and seed_hits >= 10 and hits["N12"] and all(controls.values()) and integrity
    return {"schema": SCHEMA + "_supplied_score", "selection_gate_passed": passed,
        "useful_displayed_cards": useful, "displayed_cards": shown, "useful_percent": 100 * useful / shown if shown else 0,
        "seed_positive_hit_at_3": seed_hits, "seed_positive_denominator": 11, "n12_hit": hits["N12"],
        "restricted_wrong_source_controls": controls, "corpus_absence_claim": False,
        "backend_association_verified": integrity, "browser_page_open_observed": False,
        "actual_display_integrity_proved": False, "release_gate_passed": False}


def preflight_directory(directory):
    artifacts = {name: _file(directory / FILES[name], maximum=64 * 1024 * 1024 if name == "source" else 2 * 1024 * 1024) for name in ARTIFACT_NAMES}
    runtime = json.loads(artifacts["runtime"])
    paths = {"backend/" + name for name in runtime["runtime_source_hashes"]} | set(EXTRA_CODE_PATHS)
    return prepare(artifacts, current_code={name: _file(REPO / name, maximum=1024 * 1024) for name in paths})


def main(argv=None):
    parser = argparse.ArgumentParser(__doc__); parser.add_argument("directory", type=Path, nargs="?"); parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if args.execute:
        result, code = {"schema": SCHEMA, "status": "external_host_required", "provider_calls": 0}, 2
    else:
        try:
            result = report(preflight_directory(args.directory)) if args.directory else {"schema": SCHEMA, "status": "unexecuted", "provider_calls": 0}
            code = 0
        except Exception:
            result, code = {"schema": SCHEMA, "status": "preflight_refused", "provider_calls": 0}, 2
    print(json.dumps(result, sort_keys=True)); return code


if __name__ == "__main__":
    raise SystemExit(main())
