"""Keyless public-PDF source-ID judge contract and one-shot offline scorer.

This module makes no provider request, reads no application database or private
Knowledge, and never enables Ask. ``prepare`` revalidates the independently
reviewed public fixture and PDFs before emitting label-free requests. A future
separately approved caller may supply raw JSON model outputs for ``score``.
Both stages write only to an exclusive operator-chosen temporary directory.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from pypdf import PdfReader

from validate_reading_usefulness_fixture import validate as validate_public_fixture

# Keep the model-facing contract pure and reusable by a future versioned
# runtime policy. This evaluator does not import a provider or execute Ask.
_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
from app.ai.source_judgment import (  # noqa: E402
    MAX_OUTPUT_TOKENS,
    SOURCE_ID_PROMPT_VERSION,
    SourceJudgmentError,
    build_source_id_request,
    canonical_bytes,
    parse_source_id_output,
)


SCHEMA = "cardchemy_public_source_id_judge_v1"
LOCAL_QUERY_POLICY = "source_navigation_query_v4"
# Host-path projection of the previously audited container fixture. The only
# intended difference is the reviewed evidence references' absolute OS-Temp
# paths. The full validator rechecks the same external evidence SHA pins.
PUBLIC_FIXTURE_SHA256 = "2180d4124417d5f4c9730134fa4d656957d3d6d92d4848f2f41d96927d8020d8"
SPLIT_COUNTS = {"train": 96, "calibration": 48, "heldout": 48}
MAX_RESPONSE_FILE_BYTES = 256_000
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class AuditError(ValueError):
    """Content-free failure code for the public-only harness."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise AuditError(code)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bounded_json(path: Path, limit: int) -> dict:
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_size <= limit, "file_invalid")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(type(value) is dict, "json_object_required")
    return value


def write_exclusive(path: Path, value: object) -> str:
    raw = canonical_bytes(value)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha256_bytes(raw)


def _local_navigation_query(question: str, previous_question: str | None) -> str | None:
    # Import only when projecting the public fixture; the returned expansion is
    # strictly local and is never serialized into a provider request.
    from app.ai.source_navigation import navigation_query_v4
    history = (("user", previous_question),) if previous_question else ()
    return navigation_query_v4(question, history)


def _public_pages(corpus: Path, fixture: dict) -> dict[str, list[str]]:
    manifest = bounded_json(corpus / "manifest.json", 64_000)
    documents = manifest.get("documents")
    require(type(documents) is list and len(documents) == 14, "public_manifest_invalid")
    known = {doc["sha256"] for doc in documents}
    required = {group["source_document_sha256"] for group in fixture["groups"]}
    require(required.issubset(known), "public_document_missing")
    pages = {}
    for doc in documents:
        sha, name = doc["sha256"], doc["path"]
        if sha not in required:
            continue
        require(type(name) is str and re.fullmatch(r"lec\d{2}[.]pdf", name),
                "public_document_path")
        file = corpus / name
        require(file.is_file() and not file.is_symlink(), "public_document_missing")
        pages[sha] = [(page.extract_text() or "") for page in PdfReader(file, strict=False).pages]
    return pages


def project_public_group(group: dict, pages: dict[str, list[str]]) -> dict:
    """Strip labels, reviewer data, prior question and source identity from wire."""
    question = group["question"]
    previous = group["prior_question_context_if_followup"]
    resolved_locally = _local_navigation_query(question, previous)
    if resolved_locally is None:
        return {"group_id": group["id"], "status": "clarification", "wire": None,
                "wire_sha256": None}
    source_sha = group["source_document_sha256"]
    candidates = []
    seen_pages = set()
    for index, (cue, offset) in enumerate(zip(
            group["four_exact_candidate_windows"],
            group["page_number_and_text_offsets_for_each_window"], strict=True), 1):
        page_number = offset["page_number"]
        require(page_number not in seen_pages and 1 <= page_number <= len(pages[source_sha]),
                "candidate_page_invalid")
        seen_pages.add(page_number)
        page_text = pages[source_sha][page_number - 1]
        require(sha256_bytes(page_text.encode("utf-8")) == offset["page_text_sha256"]
                and page_text[offset["start"]:offset["end"]] == cue,
                "candidate_exact_text_invalid")
        candidates.append({"id": f"S{index:02d}", "page": page_number,
                           "page_text": page_text, "cue": cue})
    wire = build_source_id_request(question, candidates)
    wire_raw = canonical_bytes(wire)
    # No prior question, local expansion, labels, file path, source SHA or
    # reviewer metadata can pass this exact allowlist.
    require(set(wire["user_payload"]) == {"question", "candidates"} and
            all(set(row) == {"id", "page", "page_text", "cue"} for row in candidates),
            "wire_field_boundary")
    return {"group_id": group["id"], "status": "callable", "wire": wire,
            "wire_sha256": sha256_bytes(wire_raw)}


def build_packet(corpus: Path, fixture_path: Path, split: str, model: str,
                 thinking: str) -> dict:
    require(split in SPLIT_COUNTS and model == "gemini-3.8-flash" and
            thinking == "low", "public_stage_config_invalid")
    require(fixture_path.is_file() and not fixture_path.is_symlink() and
            sha256_bytes(fixture_path.read_bytes()) == PUBLIC_FIXTURE_SHA256,
            "public_fixture_identity")
    validate_public_fixture(corpus, fixture_path)
    fixture = bounded_json(fixture_path, 4 * 1024 * 1024)
    groups = [group for group in fixture["groups"] if group["split"] == split]
    require(len(groups) == SPLIT_COUNTS[split], "public_split_count")
    pages = _public_pages(corpus, fixture)
    requests = [project_public_group(group, pages) for group in groups]
    return {"schema": SCHEMA, "prompt_version": SOURCE_ID_PROMPT_VERSION,
            "local_query_policy": LOCAL_QUERY_POLICY,
            "public_fixture_sha256": PUBLIC_FIXTURE_SHA256, "split": split,
            "model": model, "thinking": thinking,
            "max_output_tokens": MAX_OUTPUT_TOKENS, "requests": requests}


def _packet_fingerprint(packet: dict) -> str:
    return sha256_bytes(canonical_bytes({key: packet[key] for key in
        ("schema", "prompt_version", "local_query_policy", "public_fixture_sha256", "model", "thinking",
         "max_output_tokens")}))


def prepare(packet: dict, output: Path, calibration_receipt: Path | None = None,
            calibration_sha256: str | None = None) -> dict:
    split = packet["split"]
    if split == "heldout":
        require(calibration_receipt is not None and type(calibration_sha256) is str
                and HEX64.fullmatch(calibration_sha256), "calibration_gate_required")
        previous = bounded_json(calibration_receipt, 64_000)
        require(sha256_bytes(calibration_receipt.read_bytes()) == calibration_sha256
                and previous.get("split") == "calibration"
                and previous.get("public_passed") is True
                and previous.get("fingerprint") == _packet_fingerprint(packet),
                "calibration_gate_failed")
    require(not output.exists(), "output_already_exists")
    output.mkdir(parents=False, exist_ok=False)
    packet_sha = write_exclusive(output / "requests.json", packet)
    receipt = {"schema": SCHEMA, "status": "prepared_no_provider_call",
               "split": split, "fingerprint": _packet_fingerprint(packet),
               "requests_sha256": packet_sha,
               "harness_sha256": sha256_bytes(Path(__file__).read_bytes()),
               "contract_sha256": sha256_bytes((
                   _BACKEND / "app/ai/source_judgment.py").read_bytes()),
               "callable_count": sum(row["status"] == "callable"
                                     for row in packet["requests"]),
               "clarification_count": sum(row["status"] == "clarification"
                                          for row in packet["requests"]),
               "max_wire_bytes": max((len(canonical_bytes(row["wire"]))
                                      for row in packet["requests"]
                                      if row["wire"] is not None), default=0)}
    write_exclusive(output / "prepare-receipt.json", receipt)
    return receipt


def _response_rows(path: Path, expected: dict[str, dict]) -> dict[str, tuple[str, ...] | None]:
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_size <= MAX_RESPONSE_FILE_BYTES, "responses_file_invalid")
    results: dict[str, tuple[str, ...] | None] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        require(0 < len(line.encode("utf-8")) <= 4_096, "response_line_invalid")
        try:
            item = json.loads(line)
        except (TypeError, ValueError) as exc:
            raise AuditError("response_line_invalid") from exc
        require(type(item) is dict and set(item) == {"group_id", "wire_sha256", "raw_json"},
                "response_fields_invalid")
        group_id = item["group_id"]
        require(type(group_id) is str and group_id in expected and
                expected[group_id]["status"] == "callable" and
                group_id not in results and
                item["wire_sha256"] == expected[group_id]["wire_sha256"],
                "response_identity_invalid")
        candidate_ids = [row["id"] for row in
                         expected[group_id]["wire"]["user_payload"]["candidates"]]
        try:
            results[group_id] = parse_source_id_output(item["raw_json"], candidate_ids)
        except SourceJudgmentError:
            results[group_id] = None
    require(set(results) == {key for key, row in expected.items()
                             if row["status"] == "callable"},
            "response_count_invalid")
    return results


def score(packet: dict, fixture: dict, responses: dict[str, tuple[str, ...] | None]) -> dict:
    """Invalid model outputs count as failures, never successful abstentions."""
    groups = {row["id"]: row for row in fixture["groups"]
              if row["split"] == packet["split"]}
    require(len(groups) == SPLIT_COUNTS[packet["split"]] and
            len(packet["requests"]) == len(groups), "score_group_count")
    counts = Counter()
    forms: dict[str, Counter] = defaultdict(Counter)
    available_counts: dict[int, Counter] = defaultdict(Counter)
    for request in packet["requests"]:
        group = groups[request["group_id"]]
        selected = (() if request["status"] == "clarification" else
                    responses.get(request["group_id"]))
        invalid = request["status"] == "callable" and selected is None
        if invalid:
            selected = ()
            counts["invalid_model_outputs"] += 1
        elif request["status"] == "clarification":
            counts["clarification_groups"] += 1
        selected_indices = [int(source_id[1:]) - 1 for source_id in selected]
        page_labels = group["original_page_usefulness_per_window"]
        cue_labels = group["exact_cue_usefulness_per_window"]
        both = [page and cue for page, cue in zip(page_labels, cue_labels, strict=True)]
        available = sum(both)
        counts["groups"] += 1
        counts["positive_groups"] += available > 0
        counts["no_useful_groups"] += available == 0
        counts["available_useful_cards"] += available
        counts["displayed_cards"] += len(selected_indices)
        counts["displayed_useful_pages"] += sum(page_labels[index]
                                                for index in selected_indices)
        counts["displayed_useful_cues_and_pages"] += sum(both[index]
                                                         for index in selected_indices)
        counts["positive_hit_at_three"] += available > 0 and any(
            both[index] for index in selected_indices)
        counts["useful_first"] += available > 0 and bool(selected_indices) and both[selected_indices[0]]
        counts["false_no_useful_displays"] += available == 0 and bool(selected_indices)
        counts["valid_no_useful_abstentions"] += available == 0 and not selected_indices and not invalid
        counts["count_exact"] += len(selected_indices) == available
        form_counts = forms[group["question_form"]]
        form_counts["groups"] += 1
        form_counts["positive_groups"] += available > 0
        form_counts["positive_hit_at_three"] += available > 0 and any(
            both[index] for index in selected_indices)
        count_counts = available_counts[available]
        count_counts["groups"] += 1
        count_counts["count_exact"] += len(selected_indices) == available
    useful_share = (counts["displayed_useful_cues_and_pages"] / counts["displayed_cards"]
                    if counts["displayed_cards"] else 0.0)
    page_share = (counts["displayed_useful_pages"] / counts["displayed_cards"]
                  if counts["displayed_cards"] else 0.0)
    summary = {"counts": dict(counts), "by_form": {key: dict(value)
               for key, value in sorted(forms.items())},
               "by_available_count": {str(key): dict(value)
               for key, value in sorted(available_counts.items())},
               "displayed_cue_and_page_useful_fraction": useful_share,
               "displayed_original_page_useful_fraction": page_share}
    if packet["split"] == "calibration":
        summary["public_passed"] = (counts["invalid_model_outputs"] == 0 and
            counts["false_no_useful_displays"] == 0 and
            counts["valid_no_useful_abstentions"] == 12 and
            counts["positive_hit_at_three"] >= 30 and useful_share >= 0.9)
    elif packet["split"] == "heldout":
        summary["public_passed"] = (counts["invalid_model_outputs"] == 0 and
            counts["false_no_useful_displays"] == 0 and
            counts["valid_no_useful_abstentions"] == 12 and
            counts["positive_hit_at_three"] >= 33 and counts["useful_first"] >= 31
            and counts["displayed_useful_cues_and_pages"] >= 60 and
            useful_share >= 0.9 and
            all(row["positive_hit_at_three"] >= 10 for row in forms.values()) and
            all(available_counts[count]["count_exact"] >= 10 for count in (1, 2, 3)))
    else:
        summary["public_passed"] = False
    return summary


def score_once(output: Path, fixture_path: Path, responses_path: Path,
               expected_prepare_sha256: str) -> dict:
    require(output.is_dir() and not output.is_symlink(), "output_missing")
    require(type(expected_prepare_sha256) is str and
            HEX64.fullmatch(expected_prepare_sha256), "external_freeze_required")
    prepare_path = output / "prepare-receipt.json"
    prepare_receipt = bounded_json(output / "prepare-receipt.json", 8_192)
    packet_path = output / "requests.json"
    require(sha256_bytes(prepare_path.read_bytes()) == expected_prepare_sha256
            and packet_path.is_file() and not packet_path.is_symlink()
            and packet_path.stat().st_size <= 1_000_000
            and sha256_bytes(packet_path.read_bytes()) == prepare_receipt["requests_sha256"]
            and sha256_bytes(fixture_path.read_bytes()) == PUBLIC_FIXTURE_SHA256,
            "score_identity_drift")
    packet = bounded_json(packet_path, 1_000_000)
    require(packet["schema"] == SCHEMA and
            _packet_fingerprint(packet) == prepare_receipt["fingerprint"] and
            sha256_bytes(Path(__file__).read_bytes()) == prepare_receipt["harness_sha256"] and
            sha256_bytes((_BACKEND / "app/ai/source_judgment.py").read_bytes()) ==
            prepare_receipt["contract_sha256"],
            "score_identity_drift")
    # The exclusive claim survives malformed/incomplete output. A charged
    # external attempt must never be silently repeated by the audit harness.
    claim = output / "score.claim"
    with claim.open("xb") as stream:
        stream.write(canonical_bytes({"requests_sha256": prepare_receipt["requests_sha256"]}))
        stream.flush()
        os.fsync(stream.fileno())
    expected = {row["group_id"]: row for row in packet["requests"]}
    results = _response_rows(responses_path, expected)
    fixture = bounded_json(fixture_path, 4 * 1024 * 1024)
    metrics = score(packet, fixture, results)
    result = {"schema": SCHEMA, "split": packet["split"],
              "fingerprint": prepare_receipt["fingerprint"],
              "requests_sha256": prepare_receipt["requests_sha256"],
              "responses_sha256": sha256_bytes(responses_path.read_bytes()),
              "public_passed": metrics["public_passed"],
              "release_gate_passed": False, "metrics": metrics}
    write_exclusive(output / "score-result.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "score"))
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--split", choices=tuple(SPLIT_COUNTS))
    parser.add_argument("--model")
    parser.add_argument("--thinking", choices=("low",))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--responses", type=Path)
    parser.add_argument("--expected-prepare-sha256")
    parser.add_argument("--calibration-receipt", type=Path)
    parser.add_argument("--calibration-sha256")
    args = parser.parse_args(argv)
    try:
        if args.mode == "prepare":
            require(args.corpus is not None and args.split is not None and
                    args.model is not None and args.thinking is not None,
                    "prepare_arguments")
            packet = build_packet(args.corpus, args.fixture, args.split,
                                  args.model, args.thinking)
            result = prepare(packet, args.output, args.calibration_receipt,
                             args.calibration_sha256)
        else:
            require(args.responses is not None, "score_arguments")
            result = score_once(args.output, args.fixture, args.responses,
                                args.expected_prepare_sha256 or "")
    except (AuditError, SourceJudgmentError, OSError, KeyError, ValueError) as exc:
        print(json.dumps({"status": "public_source_id_audit_rejected",
                          "reason": str(exc) if isinstance(exc, (AuditError, SourceJudgmentError))
                          else type(exc).__name__}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
