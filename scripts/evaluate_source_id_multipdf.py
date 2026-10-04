"""Prepare and score a reviewed multi-PDF source-ID pilot without provider calls.

The model-facing packet omits labels, document identity and prior questions.
Heldout preparation requires an unchanged, passing calibration score receipt.
This script never imports provider credentials or executes a network request.
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
from tempfile import gettempdir

from finalize_public_source_id_multipdf import (
    LABEL_SCHEMA, PACKET_SCHEMA, PACKET_SHA256, ReviewError,
    read_pinned, require,
)
from prepare_public_source_id_multipdf import canonical_bytes

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
from app.ai.source_judgment import (  # noqa: E402
    MAX_OUTPUT_TOKENS, SOURCE_ID_PROMPT_VERSION, SourceJudgmentError,
    build_source_id_request, parse_source_id_output,
)
from app.ai.source_navigation import navigation_query_v4  # noqa: E402


SCHEMA = "cardchemy_public_source_id_multipdf_pilot_v1"
MODEL = "gemini-3.8-flash"
THINKING = "low"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
MAX_RESPONSE_FILE_BYTES = 256_000


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def ceil_ratio(numerator: int, denominator: int, count: int) -> int:
    return (numerator * count + denominator - 1) // denominator


def write_exclusive(path: Path, value: object) -> str:
    raw = canonical_bytes(value)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return digest(raw)


def _read_json(path: Path, max_bytes: int) -> dict:
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_size <= max_bytes, "input_invalid")
    raw = path.read_bytes()
    value = json.loads(raw)
    require(type(value) is dict and raw == canonical_bytes(value),
            "input_object_invalid")
    return value


def _fingerprint(source_packet_sha: str, labels_sha: str,
                 freeze_receipt_sha: str) -> str:
    material = {"schema": SCHEMA, "prompt_version": SOURCE_ID_PROMPT_VERSION,
                "source_packet_sha256": source_packet_sha,
                "labels_sha256": labels_sha, "model": MODEL,
                "freeze_receipt_sha256": freeze_receipt_sha,
                "thinking": THINKING, "max_output_tokens": MAX_OUTPUT_TOKENS,
                "contract_sha256": digest((_BACKEND / "app/ai/source_judgment.py").read_bytes()),
                "query_sha256": digest((_BACKEND / "app/ai/source_navigation.py").read_bytes()),
                "harness_sha256": digest(Path(__file__).read_bytes())}
    return digest(canonical_bytes(material))


def _global_score_claim_path(fingerprint: str, split: str) -> Path:
    """One scoring decision per frozen candidate and split across Temp dirs."""
    require(type(fingerprint) is str and HEX64.fullmatch(fingerprint) and
            split in {"calibration", "heldout"}, "score_claim_identity_invalid")
    directory = Path(gettempdir()).resolve() / "cardchemy-source-id-pilot-ledger"
    directory.mkdir(mode=0o700, exist_ok=True)
    require(directory.is_dir() and not directory.is_symlink(),
            "score_ledger_unavailable")
    return directory / f"score-{fingerprint}-{split}.claim"


def _split_requests(packet: dict, split: str) -> list[dict]:
    require(split in {"calibration", "heldout"} and
            packet.get("schema") == PACKET_SCHEMA and
            type(packet.get("groups")) is list and len(packet["groups"]) == 96,
            "source_packet_invalid")
    rows = []
    for group in packet["groups"]:
        if group["split"] != split:
            continue
        question = group["question"]
        prior = group["prior_for_local_context_only"]
        history = (("user", prior),) if prior else ()
        resolved = navigation_query_v4(question, history)
        if resolved is None:
            rows.append({"group_id": group["group_id"],
                         "status": "clarification", "wire": None,
                         "wire_sha256": None})
            continue
        candidates = [{key: item[key] for key in
                       ("id", "page", "page_text", "cue")}
                      for item in group["candidates"]]
        require(len(candidates) == 4, "candidate_count_invalid")
        wire = build_source_id_request(question, candidates)
        require(set(wire["user_payload"]) == {"question", "candidates"} and
                wire["user_payload"]["question"] == question and
                all(set(item) == {"id", "page", "page_text", "cue"}
                    for item in wire["user_payload"]["candidates"]),
                "wire_boundary_invalid")
        rows.append({"group_id": group["group_id"], "status": "callable",
                     "wire": wire,
                     "wire_sha256": digest(canonical_bytes(wire))})
    require(len(rows) == 48 and len({row["group_id"] for row in rows}) == 48,
            "split_count_invalid")
    return rows


def prepare(packet_dir: Path, labels_path: Path, labels_sha: str,
            freeze_receipt_sha: str, split: str, output: Path,
            calibration_score: Path | None = None,
            calibration_sha: str | None = None) -> dict:
    require(type(labels_sha) is str and HEX64.fullmatch(labels_sha) and
            labels_path.is_file() and not labels_path.is_symlink() and
            digest(labels_path.read_bytes()) == labels_sha,
            "frozen_labels_required")
    require(type(freeze_receipt_sha) is str and
            HEX64.fullmatch(freeze_receipt_sha), "freeze_receipt_required")
    freeze_path = labels_path.parent / "freeze-receipt.json"
    freeze = _read_json(freeze_path, 8_192)
    require(digest(freeze_path.read_bytes()) == freeze_receipt_sha and
            freeze.get("schema") == LABEL_SCHEMA + "_freeze" and
            freeze.get("packet_sha256") == PACKET_SHA256 and
            freeze.get("labels_sha256") == labels_sha and
            all(type(freeze.get(name)) is str and HEX64.fullmatch(freeze[name])
                for name in ("review_a_sha256", "review_b_sha256")) and
            freeze["review_a_sha256"] != freeze["review_b_sha256"],
            "freeze_receipt_invalid")
    labels = read_pinned(labels_path, labels_sha, 100_000)
    require(labels.get("schema") == LABEL_SCHEMA and
            labels.get("packet_sha256") == PACKET_SHA256 and
            type(labels.get("groups")) is list and len(labels["groups"]) == 96 and
            type(labels.get("reviewer_ids")) is list and
            len(labels["reviewer_ids"]) == 2 and
            labels["reviewer_ids"][0] != labels["reviewer_ids"][1],
            "frozen_labels_invalid")
    packet = read_pinned(packet_dir / "blind-review-packet.json",
                         PACKET_SHA256, 1_000_000)
    fingerprint = _fingerprint(PACKET_SHA256, labels_sha, freeze_receipt_sha)
    if split == "heldout":
        require(calibration_score is not None and type(calibration_sha) is str
                and HEX64.fullmatch(calibration_sha), "calibration_gate_required")
        prior = _read_json(calibration_score, 100_000)
        require(digest(calibration_score.read_bytes()) == calibration_sha and
                prior.get("schema") == SCHEMA and
                prior.get("split") == "calibration" and
                prior.get("public_passed") is True and
                prior.get("fingerprint") == fingerprint and
                prior.get("labels_sha256") == labels_sha and
                prior.get("freeze_receipt_sha256") == freeze_receipt_sha,
                "calibration_gate_failed")
    rows = _split_requests(packet, split)
    temp = Path(gettempdir()).resolve()
    require(output.is_absolute() and temp in output.resolve().parents and
            not output.exists() and output.parent.is_dir(),
            "os_temp_output_required")
    output.mkdir(parents=False, exist_ok=False)
    request_packet = {"schema": SCHEMA, "split": split,
                      "source_packet_sha256": PACKET_SHA256,
                      "labels_sha256": labels_sha,
                      "freeze_receipt_sha256": freeze_receipt_sha,
                      "fingerprint": fingerprint, "model": MODEL,
                      "thinking": THINKING, "max_output_tokens": MAX_OUTPUT_TOKENS,
                      "requests": rows}
    packet_sha = write_exclusive(output / "requests.json", request_packet)
    receipt = {"schema": SCHEMA, "status": "prepared_no_provider_call",
               "split": split, "fingerprint": fingerprint,
               "source_packet_sha256": PACKET_SHA256,
               "labels_sha256": labels_sha,
               "freeze_receipt_sha256": freeze_receipt_sha,
               "requests_sha256": packet_sha,
               "callable_count": sum(row["status"] == "callable" for row in rows),
               "clarification_count": sum(row["status"] == "clarification"
                                          for row in rows),
               "max_wire_bytes": max((len(canonical_bytes(row["wire"])) for row in rows
                                      if row["wire"] is not None), default=0)}
    write_exclusive(output / "prepare-receipt.json", receipt)
    return receipt


def _responses(path: Path, requests: list[dict]) -> dict[str, tuple[str, ...] | None]:
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_size <= MAX_RESPONSE_FILE_BYTES, "responses_file_invalid")
    expected = {row["group_id"]: row for row in requests}
    results: dict[str, tuple[str, ...] | None] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        require(0 < len(line.encode("utf-8")) <= 4_096, "response_line_invalid")
        item = json.loads(line)
        require(type(item) is dict and
                line.encode("utf-8") + b"\n" == canonical_bytes(item) and
                set(item) == {
            "group_id", "wire_sha256", "raw_json"}, "response_fields_invalid")
        group_id = item["group_id"]
        require(type(group_id) is str and group_id in expected and
                expected[group_id]["status"] == "callable" and
                group_id not in results and
                item["wire_sha256"] == expected[group_id]["wire_sha256"],
                "response_identity_invalid")
        candidate_ids = [item["id"] for item in
                         expected[group_id]["wire"]["user_payload"]["candidates"]]
        try:
            results[group_id] = parse_source_id_output(item["raw_json"], candidate_ids)
        except SourceJudgmentError:
            results[group_id] = None
    require(set(results) == {group_id for group_id, row in expected.items()
                             if row["status"] == "callable"},
            "response_count_invalid")
    return results


def score(request_packet: dict, labels: dict,
          responses: dict[str, tuple[str, ...] | None]) -> dict:
    split = request_packet["split"]
    require(labels.get("schema") == LABEL_SCHEMA and
            labels.get("packet_sha256") == PACKET_SHA256 and
            type(labels.get("groups")) is list and len(labels["groups"]) == 96,
            "labels_invalid")
    label_groups = {group["group_id"]: group for group in labels["groups"]
                    if group["split"] == split}
    require(len(label_groups) == len(request_packet["requests"]) == 48,
            "labels_count_invalid")
    counts = Counter()
    forms: dict[str, Counter] = defaultdict(Counter)
    by_available: dict[int, Counter] = defaultdict(Counter)
    for request in request_packet["requests"]:
        group_id = request["group_id"]
        group = label_groups[group_id]
        issued = request["wire"]["user_payload"]["candidates"] if request["wire"] else []
        labels_by_id = {item["id"]: item for item in group["labels"]}
        require(len(labels_by_id) == 4 and
                (not issued or set(labels_by_id) == {item["id"] for item in issued}) and
                all(type(item["page_useful"]) is bool and
                    type(item["cue_useful"]) is bool
                    for item in group["labels"]), "group_labels_invalid")
        available = sum(item["page_useful"] and item["cue_useful"]
                        for item in group["labels"])
        selected = (() if request["status"] == "clarification" else
                    responses.get(group_id))
        invalid = request["status"] == "callable" and selected is None
        if invalid:
            selected = ()
            counts["invalid_model_outputs"] += 1
        elif request["status"] == "clarification":
            counts["clarification_groups"] += 1
        selected_labels = [labels_by_id[item] for item in selected]
        useful_selected = sum(item["page_useful"] and item["cue_useful"]
                              for item in selected_labels)
        counts["groups"] += 1
        counts["positive_groups"] += available > 0
        counts["no_useful_groups"] += available == 0
        counts["available_useful_cards"] += available
        counts["displayed_cards"] += len(selected_labels)
        counts["displayed_useful_pages"] += sum(item["page_useful"]
                                                for item in selected_labels)
        counts["displayed_useful_cues_and_pages"] += useful_selected
        counts["positive_hit_at_three"] += available > 0 and useful_selected > 0
        counts["useful_first"] += available > 0 and bool(selected_labels) and (
            selected_labels[0]["page_useful"] and selected_labels[0]["cue_useful"])
        counts["false_no_useful_displays"] += available == 0 and bool(selected_labels)
        counts["valid_no_useful_abstentions"] += (
            available == 0 and request["status"] == "callable"
            and not selected_labels and not invalid
        )
        counts["clarification_no_useful_groups"] += (
            available == 0 and request["status"] == "clarification"
        )
        counts["cardinality_correct"] += available > 0 and len(selected_labels) == min(available, 3)
        form = forms[group["question_form"]]
        form["positive_groups"] += available > 0
        form["positive_hit_at_three"] += available > 0 and useful_selected > 0
        bucket = by_available[available]
        bucket["groups"] += 1
        bucket["cardinality_correct"] += len(selected_labels) == min(available, 3)
    require(counts["groups"] == 48 and set(forms) == {
        "direct", "paraphrase", "follow-up"}, "question_forms_invalid")
    denominator = counts["displayed_cards"]
    useful_fraction = (counts["displayed_useful_cues_and_pages"] / denominator
                       if denominator else 0.0)
    page_fraction = (counts["displayed_useful_pages"] / denominator
                     if denominator else 0.0)
    common = (counts["invalid_model_outputs"] == 0 and
              counts["false_no_useful_displays"] == 0 and
              counts["valid_no_useful_abstentions"] == counts["no_useful_groups"] and
              useful_fraction >= 0.9 and denominator > 0)
    positive = counts["positive_groups"]
    if split == "calibration":
        passed = (common and counts["positive_hit_at_three"] >=
                  max(30, ceil_ratio(5, 6, positive)) and
                  all(row["positive_hit_at_three"] >=
                      ceil_ratio(5, 6, row["positive_groups"])
                      for row in forms.values()))
    elif split == "heldout":
        passed = (common and counts["positive_hit_at_three"] >=
                  max(33, ceil_ratio(11, 12, positive)) and
                  counts["useful_first"] >=
                  max(31, ceil_ratio(31, 36, positive)) and
                  counts["displayed_useful_cues_and_pages"] >= 60 and
                  counts["cardinality_correct"] >= ceil_ratio(5, 6, positive) and
                  all(row["positive_hit_at_three"] >=
                      max(10, ceil_ratio(5, 6, row["positive_groups"]))
                      for row in forms.values()) and
                  all(row["cardinality_correct"] >= ceil_ratio(5, 6, row["groups"])
                      for amount, row in by_available.items() if amount > 0))
    else:
        passed = False
    return {"schema": SCHEMA + "_metrics", "split": split,
            "public_passed": bool(passed), "counts": dict(counts),
            "by_form": {name: dict(value) for name, value in sorted(forms.items())},
            "by_available": {str(amount): dict(value)
                             for amount, value in sorted(by_available.items())},
            "displayed_cue_and_page_useful_fraction": useful_fraction,
            "displayed_original_page_useful_fraction": page_fraction,
            "gate": {"calibration_positive": "max(30,ceil(5P/6))",
                     "heldout_positive": "max(33,ceil(11P/12))",
                     "heldout_useful_first": "max(31,ceil(31P/36))",
                     "no_useful_display": 0, "displayed_card_precision": 0.9,
                     "heldout_useful_cards": 60,
                     "heldout_cardinality": "ceil(5P/6) and ceil(5N/6) per nonzero stratum"}}


def score_once(output: Path, labels_path: Path, labels_sha: str,
               freeze_receipt_sha: str, responses_path: Path,
               expected_prepare_sha: str) -> dict:
    require(type(expected_prepare_sha) is str and HEX64.fullmatch(expected_prepare_sha)
            and output.is_dir() and not output.is_symlink(),
            "external_freeze_required")
    receipt_path = output / "prepare-receipt.json"
    receipt = _read_json(receipt_path, 8_192)
    request_path = output / "requests.json"
    packet = _read_json(request_path, 1_000_000)
    require(digest(receipt_path.read_bytes()) == expected_prepare_sha and
            receipt.get("requests_sha256") == digest(request_path.read_bytes()) and
            receipt.get("labels_sha256") == labels_sha and
            receipt.get("freeze_receipt_sha256") == freeze_receipt_sha and
            packet.get("schema") == SCHEMA and
            packet.get("fingerprint") == receipt.get("fingerprint") ==
            _fingerprint(PACKET_SHA256, labels_sha, freeze_receipt_sha) and
            packet.get("labels_sha256") == labels_sha and
            packet.get("freeze_receipt_sha256") == freeze_receipt_sha,
            "score_identity_drift")
    live_path = output / "live-result.json"
    require(live_path.is_file() and not live_path.is_symlink(),
            "live_run_incomplete")
    live_result = _read_json(live_path, 8192)
    usage_path = output / "usage-receipts.jsonl"
    require(responses_path == output / "response-ids.jsonl" and
            live_result.get("status") == "complete_one_shot" and
            live_result.get("split") == packet["split"] and
            live_result.get("fingerprint") == receipt["fingerprint"] and
            live_result.get("requests_sha256") == receipt["requests_sha256"] and
            type(live_result.get("attempts")) is int and
            live_result["attempts"] == receipt["callable_count"] and
            type(live_result.get("known_cost_microusd")) is int and
            0 <= live_result["known_cost_microusd"] <= 2_000_000 and
            responses_path.is_file() and not responses_path.is_symlink() and
            usage_path.is_file() and not usage_path.is_symlink() and
            live_result.get("response_ids_sha256") ==
            digest(responses_path.read_bytes()) and
            live_result.get("usage_receipts_sha256") ==
            digest(usage_path.read_bytes()),
            "live_run_incomplete")
    labels = read_pinned(labels_path, labels_sha, 100_000)
    claim = output / "score.claim"
    write_exclusive(_global_score_claim_path(receipt["fingerprint"],
                                           packet["split"]),
                    {"requests_sha256": receipt["requests_sha256"],
                     "responses_sha256": live_result["response_ids_sha256"]})
    write_exclusive(claim, {"requests_sha256": receipt["requests_sha256"]})
    results = _responses(responses_path, packet["requests"])
    metrics = score(packet, labels, results)
    result = {"schema": SCHEMA, "split": packet["split"],
              "fingerprint": receipt["fingerprint"],
              "source_packet_sha256": PACKET_SHA256,
              "labels_sha256": labels_sha,
              "freeze_receipt_sha256": freeze_receipt_sha,
              "requests_sha256": receipt["requests_sha256"],
              "responses_sha256": digest(responses_path.read_bytes()),
              "public_passed": metrics["public_passed"],
              "release_gate_passed": False, "metrics": metrics}
    write_exclusive(output / "score-result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "score"))
    parser.add_argument("--packet-dir", type=Path)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--labels-sha256", required=True)
    parser.add_argument("--freeze-receipt-sha256", required=True)
    parser.add_argument("--split", choices=("calibration", "heldout"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--calibration-score", type=Path)
    parser.add_argument("--calibration-sha256")
    parser.add_argument("--responses", type=Path)
    parser.add_argument("--expected-prepare-sha256")
    args = parser.parse_args()
    try:
        if args.mode == "prepare":
            require(args.packet_dir is not None and args.split is not None,
                    "prepare_arguments_required")
            result = prepare(args.packet_dir, args.labels, args.labels_sha256,
                             args.freeze_receipt_sha256, args.split, args.output,
                             args.calibration_score, args.calibration_sha256)
        else:
            require(args.responses is not None and
                    args.expected_prepare_sha256 is not None,
                    "score_arguments_required")
            result = score_once(args.output, args.labels, args.labels_sha256,
                                args.freeze_receipt_sha256,
                                args.responses, args.expected_prepare_sha256)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ReviewError, OSError, ValueError, KeyError, TypeError) as exc:
        code = str(exc) if isinstance(exc, ReviewError) else type(exc).__name__
        print(json.dumps({"status": "pilot_rejected", "reason": code},
                         sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
