"""Inert public text/full-page PNG preparation; never calls a provider.

The CLI admits only the already approved four cached calibration PDFs and
hash-bound audit inputs. Its Windows supervisor starts the entire preparation
inside a Job Object before source access. Unsupported enforcement modes fail
closed. An interrupted exclusive output is evidence, never a resume ledger.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import uuid
import zlib

VERSION = "visual_page_source_input_v1"
RESOURCE_JOB_NAME: str | None = None
RESOURCE_JOB_PREFIX = "cardchemy-visual-"
MAX_LONG_SIDE = 1600
MAX_PIXELS = 2_000_000
MAX_PNG_BYTES = 1_048_576
MAX_REQUEST_BYTES = 6_291_456
MAX_RENDER_SECONDS = 30
MAX_PREPARATION_SECONDS = 600
MAX_CPUS = 4
MAX_MEMORY_BYTES = 2_147_483_648
AUDIT_ROOT = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-source-contract-v1-dk54c0v7")
PACKET_PATH = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-fresh-public-source-id-v2-augmented-934ur3zj/calibration/packet.json")
PUBLIC_PDF_PARENT = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-source-id-fresh-sp2022-v2")
FREEZE_SHA = "0d52a52bdc160f5cc159f5f2571b3c8562a7142d1493d027e00c5168f356ae28"
PACKET_SHA = "cd7c6aefdda0b6f33e75a5e499c7eef42b9cc1797c414e17c742d5bde5ac8965"
SUMMARY_SHA = "59c3b1975e8032580f613d28966d15927f112d4ba5ec1d44e398c2e0bf515220"
ROSTER = frozenset(("lec04", "lec05", "lec06", "lec07"))
RENDER_PARAMETERS = {"renderer": "poppler_pdftoppm", "format": "png",
                     "scale_to": MAX_LONG_SIDE, "singlefile": True,
                     "full_page": True, "crop": False, "ocr": False,
                     "annotation": False}
RESOURCE_RECEIPT = {"mode": "windows_job_object_v1", "cpus": MAX_CPUS,
                    "aggregate_committed_memory_bytes": MAX_MEMORY_BYTES,
                    "total_timeout_seconds": MAX_PREPARATION_SECONDS,
                    "child_timeout_seconds": MAX_RENDER_SECONDS,
                    "kill_tree_on_close": True}
CANDIDATE_FIELDS = {"context", "context_end", "context_start", "cue", "cue_end",
                    "cue_start", "document_id", "id", "page", "page_text_sha256"}
MAPPING_FIELDS = {"context_end", "context_start", "cue_end", "cue_start", "document_id",
                  "group_id", "old_candidate_id", "old_group_id", "page", "page_text_sha256",
                  "pair_id", "pdf_path", "pdf_sha256"}


class PreparationError(ValueError):
    """Closed, content-free failure code."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PreparationError(code)


def validate_resource_job_name(value: object) -> str:
    require(type(value) is str and value.startswith(RESOURCE_JOB_PREFIX) and
            len(value) == len(RESOURCE_JOB_PREFIX) + 32 and
            all(c in "0123456789abcdef" for c in value[len(RESOURCE_JOB_PREFIX):]),
            "resource_job_identity_required")
    return value


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha(value: object) -> bool:
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _unique(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate_json_key")
        value[key] = item
    return value


def read_json(path: Path, expected_sha: str) -> dict:
    require(path.is_file() and not path.is_symlink(), "input_path_invalid")
    with path.open("rb") as stream:
        raw = stream.read(2_000_001)
    require(len(raw) <= 2_000_000 and digest(raw) == expected_sha, "input_hash_mismatch")
    try:
        value = json.loads(raw, object_pairs_hook=_unique)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise PreparationError("input_json_invalid") from error
    require(type(value) is dict, "input_object_required")
    return value


def write_new(path: Path, raw: bytes) -> str:
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return digest(raw)


def validate_inputs(packet: dict, mapping: dict, freeze: dict, summary: dict,
                    documents: dict, *, expected_groups: int = 66,
                    expected_pages: int = 80) -> dict:
    """Validate complete original input/mapping binding without labels/results."""
    require(packet.get("split") == "calibration", "calibration_only")
    require(set(packet) == {"schema_version", "corpus_id", "documents", "groups",
                            "source_manifest_sha256", "split"}, "packet_fields")
    require(set(documents) == ROSTER and len(packet["documents"]) == 4,
            "complete_source_roster")
    require({d["document_id"] for d in packet["documents"]} == ROSTER,
            "packet_source_roster")
    for doc in packet["documents"]:
        require(set(doc) == {"document_id", "pages", "sha256"}, "document_fields")
        actual = documents[doc["document_id"]]
        require(type(doc["pages"]) is int and doc["pages"] > 0 and _sha(doc["sha256"])
                and actual["pages"] == doc["pages"] and actual["sha256"] == doc["sha256"],
                "document_binding")
        path = Path(actual["pdf_path"])
        require(path.name == doc["document_id"] + ".pdf" and not path.is_symlink()
                and path.resolve().parent == PUBLIC_PDF_PARENT.resolve(), "public_source_path")
    require(freeze.get("groups") == expected_groups and
            freeze.get("candidate_pairs") == expected_groups * 4 and
            freeze.get("source_packet_sha256") == PACKET_SHA and
            freeze.get("source_manifest_sha256") == packet["source_manifest_sha256"],
            "freeze_binding")
    require(summary.get("groups") == expected_groups and summary.get("pairs") == expected_groups * 4
            and summary.get("parent_freeze_sha256") == FREEZE_SHA
            and summary.get("provider_calls") == 0 and summary.get("quality_pass") is False
            and summary.get("provider_trial_ready") is False, "summary_binding")
    require(set(mapping) == {"schema_version", "pairs"} and
            mapping["schema_version"] == "source_usefulness_contract_audit_v1",
            "mapping_fields")
    rows = mapping["pairs"]
    require(type(rows) is list and len(rows) == expected_groups * 4, "complete_mapping")
    require(digest(canonical(mapping)) == freeze.get("mapping_sha256"), "mapping_hash_binding")
    index = {}
    pair_ids = set()
    for row in rows:
        require(type(row) is dict and set(row) == MAPPING_FIELDS, "mapping_row_fields")
        key = (row["old_group_id"], row["old_candidate_id"])
        require(key not in index and row["pair_id"] not in pair_ids
                and type(row["pair_id"]) is str, "unique_mapping_required")
        index[key] = row
        pair_ids.add(row["pair_id"])
    groups = packet["groups"]
    require(type(groups) is list and len(groups) == expected_groups and
            len({g["group_id"] for g in groups}) == expected_groups, "complete_unique_groups")
    pages, seen = set(), set()
    for group in groups:
        require(set(group) == {"group_id", "question", "candidates"} and
                type(group["group_id"]) is str and type(group["question"]) is str and
                0 < len(group["question"]) <= 1024, "group_invalid")
        candidates = group["candidates"]
        require(type(candidates) is list and len(candidates) == 4 and
                len({c["id"] for c in candidates}) == 4, "four_unique_candidates")
        for candidate in candidates:
            require(set(candidate) == CANDIDATE_FIELDS, "candidate_fields")
            key = (group["group_id"], candidate["id"])
            require(key in index and key not in seen, "candidate_mapping_missing")
            seen.add(key)
            row = index[key]
            did, page = candidate["document_id"], candidate["page"]
            require(did in documents and type(page) is int and
                    1 <= page <= documents[did]["pages"], "physical_page_invalid")
            require(all(row[k] == candidate[k] for k in
                        ("document_id", "page", "page_text_sha256", "context_start",
                         "context_end", "cue_start", "cue_end")) and
                    row["pdf_sha256"] == documents[did]["sha256"] and
                    Path(row["pdf_path"]).resolve() == Path(documents[did]["pdf_path"]).resolve(),
                    "mapping_source_binding")
            context, cue = candidate["context"], candidate["cue"]
            cs, ce, qs, qe = (candidate[k] for k in
                              ("context_start", "context_end", "cue_start", "cue_end"))
            require(type(context) is str and 0 < len(context) <= 1200 and
                    type(cue) is str and 0 < len(cue) <= 480 and
                    all(type(n) is int for n in (cs, ce, qs, qe)) and
                    0 <= cs <= qs < qe <= ce and ce - cs == len(context) and
                    qe - qs == len(cue) and context[qs - cs:qe - cs] == cue and
                    _sha(candidate["page_text_sha256"]), "exact_window_invalid")
            pages.add((did, page))
    require(len(pages) == expected_pages and seen == set(index), "complete_cited_page_roster")
    return {"mapping": index, "pages": sorted(pages)}


def inspect_png(raw: bytes) -> dict:
    """Validate a complete bounded lossless PNG, including CRC and scanline size."""
    require(type(raw) is bytes and 0 < len(raw) <= MAX_PNG_BYTES, "png_byte_limit")
    require(raw.startswith(b"\x89PNG\r\n\x1a\n"), "png_signature")
    offset, chunks, compressed = 8, [], bytearray()
    width = height = channels = 0
    saw_idat_end = False
    while offset < len(raw):
        require(offset + 12 <= len(raw), "png_truncated")
        length = struct.unpack_from(">I", raw, offset)[0]
        end = offset + 12 + length
        require(end <= len(raw), "png_truncated")
        kind, data = raw[offset + 4:offset + 8], raw[offset + 8:offset + 8 + length]
        require(zlib.crc32(kind + data) & 0xffffffff == struct.unpack_from(">I", raw, end - 4)[0],
                "png_crc")
        if not chunks:
            require(kind == b"IHDR" and length == 13, "png_header")
            width, height, depth, color, comp, filt, interlace = struct.unpack(">IIBBBBB", data)
            require(0 < width <= MAX_LONG_SIDE and 0 < height <= MAX_LONG_SIDE and
                    max(width, height) <= MAX_LONG_SIDE and width * height <= MAX_PIXELS,
                    "png_dimension_limit")
            require(depth == 8 and color in (0, 2, 4, 6) and comp == 0 and filt == 0
                    and interlace == 0, "png_format_unsupported")
            channels = {0: 1, 2: 3, 4: 2, 6: 4}[color]
        elif kind == b"IHDR":
            raise PreparationError("png_duplicate_header")
        if kind == b"IDAT":
            require(not saw_idat_end, "png_noncontiguous_data")
            compressed.extend(data)
        elif b"IDAT" in chunks:
            saw_idat_end = True
        require(kind in (b"IHDR", b"IDAT", b"IEND") or
                (len(kind) == 4 and 97 <= kind[0] <= 122), "png_unknown_critical_chunk")
        chunks.append(kind)
        offset = end
        if kind == b"IEND":
            require(length == 0 and offset == len(raw), "png_trailing_bytes")
            break
    require(chunks and chunks[-1] == b"IEND" and b"IDAT" in chunks, "png_incomplete")
    expected = height * (1 + width * channels)
    try:
        inflater = zlib.decompressobj()
        decoded = inflater.decompress(bytes(compressed), expected + 1)
        require(len(decoded) == expected and inflater.eof and not inflater.unused_data
                and not inflater.unconsumed_tail, "png_data_size")
        row_size = 1 + width * channels
        require(all(decoded[n] <= 4 for n in range(0, expected, row_size)), "png_filter_invalid")
    except zlib.error as error:
        raise PreparationError("png_data_invalid") from error
    return {"width": width, "height": height, "bytes": len(raw), "sha256": digest(raw)}


def validate_raster_bindings(candidate: dict, image: dict) -> dict:
    require(type(image) is dict and set(image) == {
        "document_id", "pdf_sha256", "physical_page", "render", "renderer_sha256",
        "width", "height", "bytes", "sha256", "png_bytes"}, "image_fields")
    require(image["document_id"] == candidate["document_id"] and
            image["physical_page"] == candidate["page"] and
            image["pdf_sha256"] == candidate["pdf_sha256"] and
            image["render"] == RENDER_PARAMETERS and _sha(image["renderer_sha256"]),
            "raster_source_binding")
    inspected = inspect_png(image["png_bytes"])
    require(all(image[k] == v for k, v in inspected.items()), "raster_bytes_binding")
    return {k: copy.deepcopy(v) for k, v in image.items() if k != "png_bytes"}


def _validate_enriched_candidate(candidate: dict, *, assembled: bool = False) -> None:
    fields = CANDIDATE_FIELDS | {"pair_id", "pdf_sha256"}
    if assembled:
        fields |= {"image", "_image_bytes"}
    require(type(candidate) is dict and set(candidate) == fields, "enriched_candidate_fields")
    require(candidate["id"] in {"S01", "S02", "S03", "S04"} and
            type(candidate["pair_id"]) is str and len(candidate["pair_id"]) == 4 and
            candidate["pair_id"].startswith("P") and candidate["pair_id"][1:].isdigit()
            and 1 <= int(candidate["pair_id"][1:]) <= 264,
            "issued_candidate_identity")
    require(candidate["document_id"] in ROSTER and type(candidate["page"]) is int
            and candidate["page"] > 0 and _sha(candidate["pdf_sha256"])
            and _sha(candidate["page_text_sha256"]), "candidate_source_identity")
    context, cue = candidate["context"], candidate["cue"]
    cs, ce, qs, qe = (candidate[k] for k in
                      ("context_start", "context_end", "cue_start", "cue_end"))
    require(type(context) is str and 0 < len(context) <= 1200 and
            type(cue) is str and 0 < len(cue) <= 480 and
            all(type(n) is int for n in (cs, ce, qs, qe)) and
            0 <= cs <= qs < qe <= ce and ce - cs == len(context) and
            qe - qs == len(cue) and context[qs - cs:qe - cs] == cue,
            "exact_window_invalid")


def build_group_input(group: dict, images_by_source: dict) -> dict:
    require(type(group) is dict and set(group) == {"group_id", "question", "candidates"},
            "group_input_fields")
    require(len(group["candidates"]) == 4 and
            len({c["id"] for c in group["candidates"]}) == 4, "four_unique_candidates")
    result = {"group_id": group["group_id"], "question": group["question"], "candidates": []}
    for candidate in group["candidates"]:
        _validate_enriched_candidate(candidate)
        key = (candidate["document_id"], candidate["page"])
        require(key in images_by_source, "image_source_missing")
        image = images_by_source[key]
        metadata = validate_raster_bindings(candidate, image)
        result["candidates"].append({**copy.deepcopy(candidate), "image": metadata,
                                      "_image_bytes": image["png_bytes"]})
    return result


def build_payload(group_input: dict) -> dict:
    """Inert future generateContent parts; no prompt, policy, model or execution."""
    require(set(group_input) == {"group_id", "question", "candidates"}, "group_input_fields")
    require(type(group_input["question"]) is str and 0 < len(group_input["question"]) <= 1024,
            "question_invalid")
    candidates = group_input["candidates"]
    require(type(candidates) is list and len(candidates) == 4 and
            len({c["id"] for c in candidates}) == 4, "four_unique_candidates")
    parts = [{"text": canonical({"group_id": group_input["group_id"],
                                  "question": group_input["question"]}).decode()}]
    for candidate in candidates:
        _validate_enriched_candidate(candidate, assembled=True)
        image = {**candidate["image"], "png_bytes": candidate["_image_bytes"]}
        validate_raster_bindings(candidate, image)
        text = {k: v for k, v in candidate.items() if k not in ("image", "_image_bytes")}
        parts.append({"text": canonical(text).decode()})
        parts.append({"inline_data": {"mime_type": "image/png",
                                     "data": base64.b64encode(image["png_bytes"]).decode("ascii")}})
    payload = {"contents": [{"role": "user", "parts": parts}]}
    require(len(canonical(payload)) <= MAX_REQUEST_BYTES, "request_byte_limit")
    return payload


# Kept explicit for callers that only need inert image validation.
validate_png = inspect_png


def load_frozen_group(root: Path, ordinal: int, *, expected_freeze_sha256: str,
                      allow_mock: bool = False) -> dict:
    """Load one input from a complete 66/264/80 freeze and verify image bytes."""
    require(type(ordinal) is int and 1 <= ordinal <= 66 and root.is_dir()
            and not root.is_symlink(), "frozen_input_identity")
    # The small freeze is a local integrity binding, never a quality approval.
    freeze_path = root / "freeze.json"
    require(freeze_path.is_file() and not freeze_path.is_symlink() and _sha(expected_freeze_sha256),
            "external_freeze_binding_required")
    with freeze_path.open("rb") as stream:
        raw = stream.read(16_385)
    require(len(raw) <= 16_384 and digest(raw) == expected_freeze_sha256, "external_freeze_hash_mismatch")
    try:
        freeze = json.loads(raw, object_pairs_hook=_unique)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise PreparationError("freeze_json_invalid") from error
    require(type(freeze) is dict, "freeze_object_required")
    require(freeze == {"schema_version": VERSION, "manifest_sha256": freeze.get("manifest_sha256"),
                      "groups": 66, "candidate_pairs": 264, "distinct_pages": 80,
                      "quality_pass": False, "provider_calls": 0, "scoring_permitted": False}
            and _sha(freeze.get("manifest_sha256")), "complete_visual_freeze_required")
    manifest = read_json(root / "manifest.json", freeze["manifest_sha256"])
    require(manifest.get("schema_version") == VERSION and manifest.get("groups") == 66
            and manifest.get("candidate_pairs") == 264 and manifest.get("distinct_pages") == 80
            and manifest.get("source_packet_sha256") == PACKET_SHA
            and manifest.get("parent_freeze_sha256") == FREEZE_SHA
            and manifest.get("source_summary_sha256") == SUMMARY_SHA
            and manifest.get("provider_calls") == 0 and manifest.get("quality_pass") is False
            and len(manifest.get("images", [])) == 80 and len(manifest.get("requests", [])) == 66,
            "manifest_binding")
    require(allow_mock or (manifest.get("resource_limits_enforced") is True
                          and manifest.get("resource_enforcement") == RESOURCE_RECEIPT
                          and manifest.get("mock_renderer") is False),
            "enforced_preparation_required")
    require(type(allow_mock) is bool, "mock_mode_invalid")
    receipt_path = root / "preparation-receipt.json"
    require(receipt_path.is_file() and not receipt_path.is_symlink(), "complete_preparation_receipt_required")
    with receipt_path.open("rb") as stream:
        receipt_raw = stream.read(16_385)
    require(len(receipt_raw) <= 16_384, "receipt_byte_limit")
    try:
        receipt = json.loads(receipt_raw, object_pairs_hook=_unique)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise PreparationError("receipt_json_invalid") from error
    require(receipt.get("schema_version") == VERSION and receipt.get("complete") is True
            and receipt.get("manifest_sha256") == freeze["manifest_sha256"]
            and receipt.get("provider_calls") == 0 and receipt.get("quality_pass") is False,
            "complete_preparation_receipt_required")
    image_paths = {r["path"] for r in manifest["images"]}
    expected_files = image_paths | {f"{kind}/group-{number:03d}.json"
                                     for kind in ("inputs", "payloads") for number in range(1, 67)}
    require(len(image_paths) == 80 and set(manifest["files"]) == expected_files,
            "complete_frozen_file_roster")
    requests = manifest["requests"]
    require(len({r["group_id"] for r in requests}) == 66 and
            {r["input_path"] for r in requests} == {f"inputs/group-{n:03d}.json" for n in range(1, 67)}
            and {r["payload_path"] for r in requests} == {f"payloads/group-{n:03d}.json" for n in range(1, 67)}
            and all(r["images"] == 4 and type(r["bytes"]) is int and
                    0 < r["bytes"] <= MAX_REQUEST_BYTES and
                    manifest["files"][r["payload_path"]] == r["payload_sha256"] for r in requests),
            "complete_unique_request_roster")
    # All 66 requests must already be frozen before any individual input can be used.
    for relative, sha256 in manifest["files"].items():
        path = root / relative
        require(not Path(relative).is_absolute() and ".." not in Path(relative).parts
                and path.resolve().is_relative_to(root.resolve()) and path.is_file()
                and not path.is_symlink() and _sha(sha256), "frozen_file_path_invalid")
        cap = MAX_PNG_BYTES if relative in image_paths else MAX_REQUEST_BYTES
        with path.open("rb") as stream:
            data = stream.read(cap + 1)
        require(len(data) <= cap and digest(data) == sha256, "frozen_file_hash_mismatch")
    relative = f"inputs/group-{ordinal:03d}.json"
    require(relative in manifest["files"], "frozen_input_missing")
    group = read_json(root / relative, manifest["files"][relative])
    images = {(r["document_id"], r["physical_page"]): r for r in manifest["images"]}
    require(len(images) == 80, "unique_image_roster")
    for candidate in group["candidates"]:
        key = (candidate["document_id"], candidate["page"])
        require(key in images, "image_source_missing")
        row = images[key]
        image_relative = f"images/{key[0]}-page-{key[1]:03d}.png"
        require(row["path"] == image_relative and manifest["files"].get(image_relative) == row["sha256"],
                "frozen_image_path_binding")
        path = root / image_relative
        require(path.is_file() and not path.is_symlink(), "frozen_image_path_invalid")
        with path.open("rb") as stream:
            image_raw = stream.read(MAX_PNG_BYTES + 1)
        candidate["_image_bytes"] = image_raw
        require(candidate["image"] == {k: v for k, v in row.items() if k != "path"},
                "frozen_image_metadata_binding")
    # Recheck every source/physical-page/render/image-byte binding at use time.
    payload = build_payload(group)
    from prototype_visual_page_source_judge_v1 import build_request
    wire = canonical(build_request(payload["contents"][0]["parts"],
                                   [c["id"] for c in group["candidates"]]))
    request = manifest["requests"][ordinal - 1]
    require(request["group_id"] == group["group_id"] and
            request.get("full_wire_bytes") == len(wire) and
            request.get("full_wire_sha256") == digest(wire), "frozen_full_wire_binding")
    return group


def load_inputs(source_root: Path = AUDIT_ROOT) -> tuple:
    require(source_root.resolve() == AUDIT_ROOT.resolve() and not source_root.is_symlink(),
            "approved_audit_root_required")
    freeze = read_json(source_root / "freeze.json", FREEZE_SHA)
    packet = read_json(PACKET_PATH, PACKET_SHA)
    mapping = read_json(source_root / "mapping-root-only.json", freeze["mapping_sha256"])
    summary = read_json(source_root / "final/summary.json", SUMMARY_SHA)
    documents = {d["document_id"]: {**d, "pdf_path": str(PUBLIC_PDF_PARENT / (d["document_id"] + ".pdf"))}
                 for d in packet["documents"]}
    validate_inputs(packet, mapping, freeze, summary, documents)
    return packet, mapping, freeze, summary, documents


def discover_renderer() -> Path:
    """Use only already installed Poppler; never installs or downloads."""
    candidates = []
    found = shutil.which("pdftoppm")
    if found:
        candidates.append(Path(found))
    runtime = Path("C:/Users/eocim/.cache/codex-runtimes/codex-primary-runtime/dependencies")
    candidates.extend(runtime.glob("native/poppler/**/pdftoppm.exe"))
    candidates.extend(runtime.glob("bin/*/pdftoppm.exe"))
    for path in candidates:
        if path.is_file() and not path.is_symlink():
            return path.resolve()
    raise PreparationError("cached_poppler_unavailable")


def render_page(executable: Path, pdf: Path, page: int, destination: Path,
                *, timeout: float = MAX_RENDER_SECONDS, snapshot=None) -> bytes:
    require(_inside_windows_job(), "enforceable_resource_mode_required")
    require(isinstance(snapshot, _LockedPublicSources) and snapshot.contains_locked(pdf),
            "locked_public_snapshot_required")
    require(pdf.name in {name + ".pdf" for name in ROSTER} and not pdf.is_symlink()
            and type(page) is int and page >= 1, "render_public_source_required")
    require(0 < timeout <= MAX_RENDER_SECONDS and not destination.exists(), "render_admission")
    prefix = destination.with_suffix("")
    command = [str(executable), "-f", str(page), "-l", str(page), "-singlefile", "-png",
               "-scale-to", str(MAX_LONG_SIDE), str(pdf), str(prefix)]
    try:
        completed = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=timeout, check=False,
                                   env={"SystemRoot": os.environ.get("SystemRoot", "C:/Windows"),
                                        "PATH": str(executable.parent)},
                                   creationflags=0x08000000 if os.name == "nt" else 0)
    except subprocess.TimeoutExpired as error:
        raise PreparationError("render_timeout") from error
    require(completed.returncode == 0 and destination.is_file() and not destination.is_symlink(),
            "render_failed")
    with destination.open("rb") as stream:
        raw = stream.read(MAX_PNG_BYTES + 1)
    inspect_png(raw)
    return raw


def _verify_native_windows(packet: dict, documents: dict, *, snapshots=None) -> None:
    from pypdf import PdfReader
    import logging
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    needed = {(c["document_id"], c["page"]) for g in packet["groups"] for c in g["candidates"]}
    texts = {}
    for did in sorted(documents):
        path = Path(documents[did]["pdf_path"]) if snapshots is None else snapshots.paths[did]
        require(path.is_file() and not path.is_symlink(), "pdf_path_invalid")
        # No unapproved path is opened; the roster and parent were checked first.
        with path.open("rb") as stream:
            hash_ = hashlib.sha256()
            size = 0
            for chunk in iter(lambda: stream.read(65_536), b""):
                size += len(chunk)
                require(size <= 16_000_000, "pdf_byte_limit")
                hash_.update(chunk)
        require(hash_.hexdigest() == documents[did]["sha256"], "pdf_hash_mismatch")
        reader = PdfReader(path)
        require(len(reader.pages) == documents[did]["pages"], "pdf_page_count")
        for source, page in sorted(needed):
            if source == did:
                texts[(did, page)] = reader.pages[page - 1].extract_text() or ""
    for group in packet["groups"]:
        for candidate in group["candidates"]:
            text = texts[(candidate["document_id"], candidate["page"])]
            require(digest(text.encode()) == candidate["page_text_sha256"] and
                    text[candidate["context_start"]:candidate["context_end"]] == candidate["context"] and
                    text[candidate["cue_start"]:candidate["cue_end"]] == candidate["cue"],
                    "native_source_window_changed")


def prepare_from_inputs(packet: dict, mapping: dict, freeze: dict, summary: dict,
                        documents: dict, renderer, output_parent: Path, *,
                        resource_receipt: dict | None = None,
                        destination: Path | None = None) -> Path:
    """Shared assembly; injected fake renderers never establish enforced limits."""
    started = time.monotonic()
    bound = validate_inputs(packet, mapping, freeze, summary, documents)
    if destination is None:
        destination = Path(tempfile.mkdtemp(prefix="cardchemy-visual-input-v1-", dir=output_parent))
    owned_snapshot = isinstance(renderer, _BoundedPopplerRenderer) and renderer.snapshots.root.parent == destination
    existing = list(destination.iterdir()) if destination.is_dir() else []
    require(destination.is_dir() and not destination.is_symlink() and
            (not existing or (owned_snapshot and existing == [renderer.snapshots.root])),
            "output_or_partial_state_exists")
    write_new(destination / "preparation-started.json", canonical({"schema_version": VERSION,
              "provider_calls": 0, "quality_pass": False, "resume_permitted": False}))
    image_dir, input_dir, payload_dir = (destination / name for name in ("images", "inputs", "payloads"))
    for directory in (image_dir, input_dir, payload_dir):
        directory.mkdir()
    images, image_rows, files = {}, [], {}
    enforced = isinstance(renderer, _BoundedPopplerRenderer) and resource_receipt == RESOURCE_RECEIPT
    require(not enforced or _inside_windows_job(), "enforceable_resource_mode_required")
    try:
        for did, page in bound["pages"]:
            remaining = MAX_PREPARATION_SECONDS - (time.monotonic() - started)
            require(remaining > 0, "preparation_timeout")
            path = image_dir / f"{did}-page-{page:03d}.png"
            rendered = renderer(Path(documents[did]["pdf_path"]), page, path,
                                min(MAX_RENDER_SECONDS, remaining))
            require(type(rendered) is tuple and len(rendered) == 2, "renderer_result_invalid")
            raw, renderer_sha = rendered
            metrics = inspect_png(raw)
            require(_sha(renderer_sha), "renderer_sha_invalid")
            if not path.exists():
                write_new(path, raw)
            else:
                require(not path.is_symlink() and path.read_bytes() == raw, "renderer_disk_binding")
            image = {"document_id": did, "pdf_sha256": documents[did]["sha256"],
                     "physical_page": page, "render": copy.deepcopy(RENDER_PARAMETERS),
                     "renderer_sha256": renderer_sha, **metrics, "png_bytes": raw}
            images[(did, page)] = image
            relative = path.relative_to(destination).as_posix()
            files[relative] = metrics["sha256"]
            image_rows.append({**{k: v for k, v in image.items() if k != "png_bytes"},
                               "path": relative})
            write_new(destination / f"checkpoint-image-{len(image_rows):03d}.json",
                      canonical({"images_completed": len(image_rows), "image_sha256": metrics["sha256"],
                                 "elapsed_ms": round((time.monotonic() - started) * 1000),
                                 "provider_calls": 0, "quality_pass": False}))
        request_rows = []
        for ordinal, group in enumerate(packet["groups"], 1):
            require(time.monotonic() - started <= MAX_PREPARATION_SECONDS, "preparation_timeout")
            enriched = copy.deepcopy(group)
            for candidate in enriched["candidates"]:
                row = bound["mapping"][(group["group_id"], candidate["id"])]
                candidate.update({"pair_id": row["pair_id"], "pdf_sha256": row["pdf_sha256"]})
            assembled = build_group_input(enriched, images)
            payload_object = build_payload(assembled)
            payload = canonical(payload_object)
            from prototype_visual_page_source_judge_v1 import build_request, VisualVerdictError
            try:
                wire = canonical(build_request(payload_object["contents"][0]["parts"],
                                               [c["id"] for c in assembled["candidates"]]))
            except VisualVerdictError as error:
                raise PreparationError("full_wire_admission_failed") from error
            require(len(wire) <= MAX_REQUEST_BYTES, "full_wire_byte_limit")
            serialized = {**assembled, "candidates": [
                {k: v for k, v in c.items() if k != "_image_bytes"} for c in assembled["candidates"]]}
            input_relative = f"inputs/group-{ordinal:03d}.json"
            payload_relative = f"payloads/group-{ordinal:03d}.json"
            files[input_relative] = write_new(destination / input_relative, canonical(serialized))
            files[payload_relative] = write_new(destination / payload_relative, payload)
            request_rows.append({"group_id": group["group_id"], "input_path": input_relative,
                                 "payload_path": payload_relative, "bytes": len(payload), "images": 4,
                                 "payload_sha256": files[payload_relative],
                                 "full_wire_bytes": len(wire), "full_wire_sha256": digest(wire)})
        manifest = {"schema_version": VERSION, "source_packet_sha256": PACKET_SHA,
                    "parent_freeze_sha256": FREEZE_SHA, "source_summary_sha256": SUMMARY_SHA,
                    "mapping_sha256": freeze["mapping_sha256"], "groups": len(packet["groups"]),
                    "candidate_pairs": len(mapping["pairs"]), "distinct_pages": len(images),
                    "images": image_rows, "requests": request_rows, "files": files,
                    "render_parameters": RENDER_PARAMETERS,
                    "resource_enforcement": RESOURCE_RECEIPT if enforced else None,
                    "resource_limits_enforced": enforced,
                    "max_image_bytes": max(r["bytes"] for r in image_rows),
                    "total_image_bytes": sum(r["bytes"] for r in image_rows),
                    "max_request_bytes": max(r["bytes"] for r in request_rows),
                    "total_request_bytes": sum(r["bytes"] for r in request_rows),
                    "max_full_wire_bytes": max(r["full_wire_bytes"] for r in request_rows),
                    "total_full_wire_bytes": sum(r["full_wire_bytes"] for r in request_rows),
                    "elapsed_ms": round((time.monotonic() - started) * 1000),
                    "quality_pass": False, "provider_calls": 0, "model_inferences": 0,
                    "count_tokens_calls": 0, "provider_trial_ready": False,
                    "readability_review_complete": False, "mock_renderer": not enforced,
                    "resume_permitted": False}
        manifest_sha = write_new(destination / "manifest.json", canonical(manifest))
        write_new(destination / "freeze.json", canonical({"schema_version": VERSION,
                  "manifest_sha256": manifest_sha, "groups": len(packet["groups"]),
                  "candidate_pairs": len(mapping["pairs"]), "distinct_pages": len(images),
                  "quality_pass": False, "provider_calls": 0, "scoring_permitted": False}))
        write_new(destination / "preparation-receipt.json", canonical({"schema_version": VERSION,
                  "complete": True, "manifest_sha256": manifest_sha, "provider_calls": 0,
                  "quality_pass": False, "resource_limits_enforced": enforced}))
    except Exception as error:
        code = str(error) if isinstance(error, PreparationError) else "preparation_failed"
        write_new(destination / "failure-receipt.json", canonical({"schema_version": VERSION,
                  "complete": False, "failure_code": code, "images_completed": len(image_rows),
                  "provider_calls": 0, "quality_pass": False, "resume_permitted": False}))
        raise
    return destination


def prepare(source_root: Path = AUDIT_ROOT, *, destination: Path,
            resource_receipt: dict) -> Path:
    require(resource_receipt == RESOURCE_RECEIPT and _inside_windows_job(),
            "enforceable_resource_mode_required")
    inputs = load_inputs(source_root)
    executable = discover_renderer()
    renderer_sha = digest(executable.read_bytes())
    require(destination.is_dir() and not destination.is_symlink() and not any(destination.iterdir()),
            "output_or_partial_state_exists")
    with _LockedPublicSources(inputs[4], destination / "source-snapshots") as snapshots:
        _verify_native_windows(inputs[0], inputs[4], snapshots=snapshots)
        return prepare_from_inputs(*inputs, _BoundedPopplerRenderer(executable, renderer_sha, snapshots),
                                   destination.parent, resource_receipt=resource_receipt, destination=destination)


class _LockedPublicSources:
    """Copy only approved public sources and deny writes/deletion while used."""
    def __init__(self, documents: dict, root: Path):
        self.documents, self.root = documents, root
        self.paths, self.handles = {}, []

    def _lock_read(self, path: Path):
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        # GENERIC_READ, FILE_SHARE_READ only, OPEN_EXISTING. No write/delete share.
        handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x80, None)
        require(handle not in (None, ctypes.c_void_p(-1).value), "source_read_lock_unavailable")
        return kernel, handle

    def __enter__(self):
        require(os.name == "nt" and _inside_windows_job(), "enforceable_resource_mode_required")
        require(not self.root.exists() and self.root.parent.resolve().parent == Path(tempfile.gettempdir()).resolve(),
                "owned_snapshot_path_required")
        self.root.mkdir()
        try:
            for did in sorted(self.documents):
                source = Path(self.documents[did]["pdf_path"])
                require(did in ROSTER and source.name == did + ".pdf" and not source.is_symlink()
                        and source.resolve().parent == PUBLIC_PDF_PARENT.resolve(), "public_source_path")
                kernel, source_handle = self._lock_read(source)
                try:
                    target = self.root / (did + ".pdf")
                    sha256, size = hashlib.sha256(), 0
                    with source.open("rb") as input_, target.open("xb") as output:
                        for chunk in iter(lambda: input_.read(65_536), b""):
                            size += len(chunk)
                            require(size <= 16_000_000, "pdf_byte_limit")
                            sha256.update(chunk)
                            output.write(chunk)
                        output.flush()
                        os.fsync(output.fileno())
                    require(sha256.hexdigest() == self.documents[did]["sha256"], "pdf_hash_mismatch")
                    kernel, snapshot_handle = self._lock_read(target)
                    self.handles.append((kernel, snapshot_handle))
                    # Bind the bytes actually held under the deny-write/delete
                    # lock, closing the copy-close/lock acquisition race.
                    locked_sha, locked_size = hashlib.sha256(), 0
                    with target.open("rb") as locked_input:
                        for chunk in iter(lambda: locked_input.read(65_536), b""):
                            locked_size += len(chunk)
                            require(locked_size <= 16_000_000, "pdf_byte_limit")
                            locked_sha.update(chunk)
                    require(locked_size == size and
                            locked_sha.hexdigest() == self.documents[did]["sha256"],
                            "locked_snapshot_hash_mismatch")
                    self.paths[did] = target
                finally:
                    kernel.CloseHandle.argtypes = [__import__("ctypes").c_void_p]
                    kernel.CloseHandle(source_handle)
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def contains_locked(self, path: Path) -> bool:
        return len(self.handles) == 4 and path in self.paths.values() and path.is_file() and not path.is_symlink()

    def __exit__(self, *unused):
        import ctypes
        for kernel, handle in self.handles:
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(handle)
        self.handles.clear()
        # Delete only this exact exclusively created, resolved Temp child.
        if (self.root.exists() and not self.root.is_symlink() and
                self.root.resolve().parent.parent == Path(tempfile.gettempdir()).resolve()):
            shutil.rmtree(self.root)


class _BoundedPopplerRenderer:
    def __init__(self, executable: Path, sha256: str, snapshots: _LockedPublicSources):
        self.executable, self.sha256, self.snapshots = executable, sha256, snapshots

    def __call__(self, pdf: Path, page: int, path: Path, timeout: float) -> tuple:
        require(_inside_windows_job(), "enforceable_resource_mode_required")
        source = self.snapshots.paths[pdf.stem]
        return render_page(self.executable, source, page, path, timeout=timeout, snapshot=self.snapshots), self.sha256


def _inside_windows_job() -> bool:
    if os.name != "nt":
        return False
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    kernel.OpenJobObjectW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.OpenJobObjectW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    job = None
    if RESOURCE_JOB_NAME is not None:
        job = kernel.OpenJobObjectW(0x4, False, RESOURCE_JOB_NAME)
        if not job:
            return False
    flag = wintypes.BOOL()
    if not (kernel.IsProcessInJob(kernel.GetCurrentProcess(), job, ctypes.byref(flag)) and flag.value):
        if job:
            kernel.CloseHandle(job)
        return False
    size = ctypes.c_size_t
    class Basic(ctypes.Structure):
        _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                    ("flags", wintypes.DWORD), ("min_ws", size), ("max_ws", size),
                    ("active", wintypes.DWORD), ("affinity", size),
                    ("priority", wintypes.DWORD), ("scheduling", wintypes.DWORD)]
    class IO(ctypes.Structure):
        _fields_ = [(f"counter{i}", ctypes.c_ulonglong) for i in range(6)]
    class Extended(ctypes.Structure):
        _fields_ = [("basic", Basic), ("io", IO), ("process_memory", size),
                    ("job_memory", size), ("peak_process_memory", size), ("peak_job_memory", size)]
    kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                                wintypes.DWORD, ctypes.c_void_p]
    limits = Extended()
    try:
        return bool(kernel.QueryInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits), None)
                    and limits.basic.flags & (0x10 | 0x200 | 0x2000) == (0x10 | 0x200 | 0x2000)
                    and not limits.basic.flags & (0x800 | 0x1000)
                    and limits.basic.affinity.bit_count() <= MAX_CPUS
                    and limits.basic.affinity > 0
                    and 0 < limits.job_memory <= MAX_MEMORY_BYTES)
    finally:
        if job:
            kernel.CloseHandle(job)


def supervise(destination: Path) -> None:
    """Enforce total process-tree memory/CPU affinity/time before worker runs."""
    require(os.name == "nt", "enforceable_resource_mode_unavailable")
    import ctypes
    from ctypes import wintypes as w
    size = ctypes.c_size_t
    class Basic(ctypes.Structure):
        _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                    ("flags", w.DWORD), ("min_ws", size), ("max_ws", size),
                    ("active", w.DWORD), ("affinity", size), ("priority", w.DWORD), ("scheduling", w.DWORD)]
    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in ("read_ops", "write_ops", "other_ops",
                                                         "read_bytes", "write_bytes", "other_bytes")]
    class Extended(ctypes.Structure):
        _fields_ = [("basic", Basic), ("io", IO), ("process_memory", size),
                    ("job_memory", size), ("peak_process_memory", size), ("peak_job_memory", size)]
    class Startup(ctypes.Structure):
        _fields_ = [("cb", w.DWORD), ("reserved", w.LPWSTR), ("desktop", w.LPWSTR),
                    ("title", w.LPWSTR), ("x", w.DWORD), ("y", w.DWORD),
                    ("x_size", w.DWORD), ("y_size", w.DWORD), ("x_chars", w.DWORD),
                    ("y_chars", w.DWORD), ("fill", w.DWORD), ("flags", w.DWORD),
                    ("show", w.WORD), ("reserved_size", w.WORD),
                    ("reserved_bytes", ctypes.POINTER(ctypes.c_byte)),
                    ("stdin", w.HANDLE), ("stdout", w.HANDLE), ("stderr", w.HANDLE)]
    class Process(ctypes.Structure):
        _fields_ = [("process", w.HANDLE), ("thread", w.HANDLE),
                    ("pid", w.DWORD), ("tid", w.DWORD)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.GetLastError.restype = w.DWORD
    kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    kernel.GetProcessAffinityMask.argtypes = [w.HANDLE, ctypes.POINTER(size), ctypes.POINTER(size)]
    kernel.CreateProcessW.argtypes = [w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
                                     w.BOOL, w.DWORD, ctypes.c_void_p, w.LPCWSTR,
                                     ctypes.POINTER(Startup), ctypes.POINTER(Process)]
    kernel.ResumeThread.argtypes = [w.HANDLE]
    kernel.ResumeThread.restype = w.DWORD
    kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    kernel.WaitForSingleObject.restype = w.DWORD
    kernel.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    kernel.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
    kernel.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    # The Windows venv launcher may add its own inner job. Query the named
    # resource ancestor explicitly rather than trusting the null/nearest job.
    job_name = RESOURCE_JOB_PREFIX + uuid.uuid4().hex
    job, info = kernel.CreateJobObjectW(None, job_name), Process()
    require(bool(job), "resource_job_create_failed")
    try:
        require(kernel.GetLastError() != 183, "resource_job_identity_collision")
        allowed, system = size(), size()
        require(bool(kernel.GetProcessAffinityMask(kernel.GetCurrentProcess(), ctypes.byref(allowed),
                                                   ctypes.byref(system))), "resource_affinity_unavailable")
        bits = [1 << i for i in range(ctypes.sizeof(size) * 8) if allowed.value & (1 << i)]
        require(bool(bits), "resource_affinity_unavailable")
        limits = Extended()
        # AFFINITY | JOB_MEMORY | KILL_ON_JOB_CLOSE; no breakaway is allowed.
        limits.basic.flags = 0x10 | 0x200 | 0x2000
        limits.basic.affinity = sum(bits[:MAX_CPUS])
        limits.job_memory = MAX_MEMORY_BYTES
        require(bool(kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits))),
                "resource_limits_unavailable")
        command = subprocess.list2cmdline([sys.executable, str(Path(__file__).resolve()),
                                            "--worker", "--destination", str(destination),
                                            "--resource-job", job_name])
        startup = Startup()
        startup.cb = ctypes.sizeof(startup)
        # Child receives no credentials, inherited handles or operator settings.
        environment = {"SystemRoot": os.environ.get("SystemRoot", "C:/Windows"),
                       "PATH": str(Path(sys.executable).parent), "PYTHONUTF8": "1",
                       "TEMP": str(destination.parent), "TMP": str(destination.parent)}
        block = ctypes.create_unicode_buffer("\0".join(f"{k}={v}" for k, v in sorted(environment.items())) + "\0\0")
        require(bool(kernel.CreateProcessW(sys.executable, ctypes.create_unicode_buffer(command), None, None,
                                          False, 0x4 | 0x400 | 0x08000000, block,
                                          str(destination), ctypes.byref(startup), ctypes.byref(info))),
                "resource_worker_create_failed")
        require(bool(kernel.AssignProcessToJobObject(job, info.process)), "resource_assignment_unavailable")
        require(kernel.ResumeThread(info.thread) != 0xffffffff, "resource_worker_resume_failed")
        status = kernel.WaitForSingleObject(info.process, MAX_PREPARATION_SECONDS * 1000)
        if status == 0x102:
            kernel.TerminateJobObject(job, 2)
            raise PreparationError("preparation_timeout")
        require(status == 0, "resource_worker_wait_failed")
        code = w.DWORD()
        require(bool(kernel.GetExitCodeProcess(info.process, ctypes.byref(code))),
                "resource_worker_exit_unavailable")
        if code.value != 0:
            write_new(destination / "worker-exit.json", canonical({
                "schema_version": VERSION, "exit_code": code.value,
                "provider_calls": 0, "quality_pass": False}))
            raise PreparationError("preparation_worker_failed")
    finally:
        if info.process:
            # Also stops a suspended process if assignment/resume failed.
            kernel.TerminateProcess(info.process, 2)
        kernel.CloseHandle(job)
        for handle in (info.thread, info.process):
            if handle:
                kernel.CloseHandle(handle)


def main() -> None:
    global RESOURCE_JOB_NAME
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-approved-offline", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--destination", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--resource-job", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.worker:
            RESOURCE_JOB_NAME = validate_resource_job_name(args.resource_job)
            require(args.destination is not None and args.destination.resolve().parent == Path(tempfile.gettempdir()).resolve(),
                    "temp_destination_required")
            # Preflight failures occur before assembly owns its own receipt.
            # Keep a content-free diagnostic without capturing stderr, source
            # text, environment values or any raw exception.
            try:
                require(_inside_windows_job(), "enforceable_resource_mode_required")
                prepare(destination=args.destination, resource_receipt=RESOURCE_RECEIPT)
            except Exception as error:
                code = str(error) if isinstance(error, PreparationError) else "preparation_worker_failed"
                if not (code.isascii() and len(code) <= 64 and
                        all(c in "abcdefghijklmnopqrstuvwxyz_0123456789" for c in code)):
                    code = "preparation_worker_failed"
                write_new(args.destination / "worker-failure.json", canonical({
                    "schema_version": VERSION, "failure_code": code,
                    "provider_calls": 0, "quality_pass": False, "resume_permitted": False}))
                raise PreparationError(code) from None
            return
        require(args.prepare_approved_offline and args.destination is None and args.resource_job is None,
                "explicit_offline_preparation_required")
        require(os.name == "nt", "enforceable_resource_mode_unavailable")
        destination = Path(tempfile.mkdtemp(prefix="cardchemy-visual-input-v1-"))
        try:
            supervise(destination)
        except PreparationError as error:
            if not (destination / "failure-receipt.json").exists():
                write_new(destination / "supervisor-failure.json", canonical({"schema_version": VERSION,
                          "failure_code": str(error), "provider_calls": 0, "quality_pass": False,
                          "resume_permitted": False}))
            raise
        print(json.dumps({"output_dir": str(destination),
                          "freeze_sha256": digest((destination / "freeze.json").read_bytes()),
                          "provider_calls": 0, "quality_pass": False}))
    except (PreparationError, OSError) as error:
        parser.exit(2, (str(error) if isinstance(error, PreparationError) else "preparation_io_failed") + "\n")


if __name__ == "__main__":
    main()
