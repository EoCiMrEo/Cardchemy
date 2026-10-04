"""Separate keyless, networkless heldout text/full-page PNG preparation.

Only the four cached, SHA-pinned public heldout PDFs are admitted. This script
preserves all 60 questions and all 240 candidates, creates blinded review
inputs without labels/results, and does not establish model quality. The
resource helpers below reuse the reviewed calibration preparer's implementation
in this distinct file; the original frozen calibration files remain unchanged.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

import prepare_visual_page_source_input_v1 as shared
import prototype_visual_page_source_judge_v2 as prototype

VERSION = "visual_public_heldout_input_v2"
MAX_LONG_SIDE = shared.MAX_LONG_SIDE
MAX_PIXELS = shared.MAX_PIXELS
MAX_PNG_BYTES = shared.MAX_PNG_BYTES
MAX_REQUEST_BYTES = shared.MAX_REQUEST_BYTES
MAX_RENDER_SECONDS = shared.MAX_RENDER_SECONDS
MAX_PREPARATION_SECONDS = shared.MAX_PREPARATION_SECONDS
MAX_CPUS = shared.MAX_CPUS
MAX_MEMORY_BYTES = shared.MAX_MEMORY_BYTES
MAX_OUTPUT_TOKENS = 4096
RENDER_SCALES = (1600, 1400, 1200, 1000)
RESOURCE_JOB_NAME: str | None = None
RESOURCE_JOB_PREFIX = "cardchemy-visual-heldout-"
ROSTER = frozenset(("lec08", "lec09", "lec11", "lec13"))
PUBLIC_PDF_PARENT = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-source-id-fresh-sp2022-v2")
PACKET_ROOT = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-fresh-public-source-id-v2-augmented-934ur3zj")
PACKET_SHA = "a56a5f44ac3d782310d0be9adbcb9bf9b4a19b4ef2d807cb18620548c51db3e1"
LABEL_SHA = "9e2cd6b5fb3aefe3f65a8b8e3813e95fb13ccdcf6d74b146706cf35c07eb54a4"
PARENT_FREEZE_SHA = "c8b97e3851f081c40108d6f6a40b9bb675dc3b824329d4fc7f047480425017b1"
GROUPS = 60
PAIRS = 240
DISTINCT_PAGES = 86
RENDER_PARAMETERS = copy.deepcopy(shared.RENDER_PARAMETERS)
RESOURCE_RECEIPT = copy.deepcopy(shared.RESOURCE_RECEIPT)
CANDIDATE_FIELDS = shared.CANDIDATE_FIELDS
PreparationError = shared.PreparationError
require = shared.require
canonical = shared.canonical
digest = shared.digest
write_new = shared.write_new
read_json = shared.read_json
inspect_png = shared.inspect_png
_sha = shared._sha


def validate_resource_job_name(value: object) -> str:
    require(type(value) is str and value.startswith(RESOURCE_JOB_PREFIX) and
            len(value) == len(RESOURCE_JOB_PREFIX) + 32 and
            all(c in "0123456789abcdef" for c in value[len(RESOURCE_JOB_PREFIX):]),
            "resource_job_identity_required")
    return value


def validate_packet(packet: dict, *, expected_groups: int = GROUPS,
                    expected_pages: int = DISTINCT_PAGES) -> dict:
    require(type(packet) is dict and set(packet) == {
        "schema_version", "corpus_id", "documents", "groups", "source_manifest_sha256", "split"
    } and packet["split"] == "heldout", "heldout_packet_required")
    require(type(packet["documents"]) is list and len(packet["documents"]) == 4,
            "complete_document_roster")
    documents = {}
    for row in packet["documents"]:
        require(type(row) is dict and set(row) == {"document_id", "pages", "sha256"}
                and row["document_id"] in ROSTER and row["document_id"] not in documents
                and type(row["pages"]) is int and 0 < row["pages"] <= 100
                and _sha(row["sha256"]), "document_identity_invalid")
        documents[row["document_id"]] = {
            **row, "pdf_path": str(PUBLIC_PDF_PARENT / (row["document_id"] + ".pdf"))}
    require(set(documents) == ROSTER and _sha(packet["source_manifest_sha256"]),
            "heldout_document_roster")
    groups = packet["groups"]
    require(type(groups) is list and len(groups) == expected_groups, "complete_group_roster")
    seen, pages, mapping, projected = set(), set(), [], []
    for ordinal, group in enumerate(groups, 1):
        require(type(group) is dict and set(group) == {"group_id", "question", "candidates"}
                and type(group["group_id"]) is str and group["group_id"] not in seen
                and type(group["question"]) is str and 0 < len(group["question"]) <= 1024,
                "group_identity_invalid")
        seen.add(group["group_id"])
        rows = group["candidates"]
        require(type(rows) is list and len(rows) == 4 and
                [c.get("id") for c in rows] == ["S01", "S02", "S03", "S04"],
                "four_issued_candidates_required")
        alias = f"Q{ordinal:03d}"
        new_group = {"group_id": alias, "question": group["question"], "candidates": []}
        for offset, candidate in enumerate(rows):
            require(type(candidate) is dict and set(candidate) == CANDIDATE_FIELDS,
                    "candidate_fields_invalid")
            did, page = candidate["document_id"], candidate["page"]
            require(did in documents and type(page) is int and
                    1 <= page <= documents[did]["pages"] and _sha(candidate["page_text_sha256"]),
                    "candidate_source_identity")
            context, cue = candidate["context"], candidate["cue"]
            cs, ce, qs, qe = (candidate[k] for k in
                              ("context_start", "context_end", "cue_start", "cue_end"))
            require(type(context) is str and 0 < len(context) <= 1200 and
                    type(cue) is str and 0 < len(cue) <= 480 and
                    all(type(n) is int for n in (cs, ce, qs, qe)) and
                    0 <= cs <= qs < qe <= ce and ce - cs == len(context) and
                    qe - qs == len(cue) and context[qs-cs:qe-cs] == cue,
                    "exact_source_window_required")
            pair_id = f"P{(ordinal-1)*4+offset+1:03d}"
            review_id = f"K{(ordinal-1)*4+offset+1:03d}"
            new_group["candidates"].append({**copy.deepcopy(candidate), "pair_id": pair_id,
                                            "pdf_sha256": documents[did]["sha256"]})
            mapping.append({"pair_id": pair_id, "review_id": review_id,
                            "group_id": alias, "old_group_id": group["group_id"],
                            "candidate_id": candidate["id"], "document_id": did,
                            "physical_page": page, "pdf_sha256": documents[did]["sha256"],
                            "page_text_sha256": candidate["page_text_sha256"]})
            pages.add((did, page))
        require(len({(c["document_id"], c["page"]) for c in rows}) == 4,
                "four_distinct_source_pages")
        require(len({c["document_id"] for c in rows}) == 2, "two_pdf_group_required")
        projected.append(new_group)
    require(len(pages) == expected_pages, "complete_cited_page_roster")
    return {"documents": documents, "pages": sorted(pages), "mapping": mapping,
            "groups": projected}


def load_inputs() -> tuple:
    require(PACKET_ROOT.is_dir() and not PACKET_ROOT.is_symlink(), "pinned_packet_root_required")
    freeze = read_json(PACKET_ROOT / "freeze.json", PARENT_FREEZE_SHA)
    packet = read_json(PACKET_ROOT / "heldout/packet.json", PACKET_SHA)
    labels = read_json(PACKET_ROOT / "heldout/labels.json", LABEL_SHA)
    require(freeze.get("files", {}).get("heldout/packet.json") == PACKET_SHA and
            freeze.get("files", {}).get("heldout/labels.json") == LABEL_SHA and
            freeze.get("source_manifest_sha256") == packet["source_manifest_sha256"],
            "frozen_parent_binding")
    require(labels.get("packet_sha256") == PACKET_SHA and labels.get("split") == "heldout"
            and labels.get("source_manifest_sha256") == packet["source_manifest_sha256"]
            and len(labels.get("groups", [])) == GROUPS and
            {g["group_id"] for g in labels["groups"]} == {g["group_id"] for g in packet["groups"]},
            "historical_labels_binding")
    return packet, validate_packet(packet)


def build_group_payload(group: dict, images: dict) -> tuple[dict, dict]:
    """Bind exact PNG bytes to immutable source/page/text before wire admission."""
    parts = [{"text": canonical({"group_id": group["group_id"],
                                  "question": group["question"]}).decode("utf-8")}]
    candidates = []
    for candidate in group["candidates"]:
        key = (candidate["document_id"], candidate["page"])
        require(key in images, "candidate_image_missing")
        image = images[key]
        metadata = validate_raster_bindings(candidate, image)
        candidates.append({**copy.deepcopy(candidate), "image": metadata})
        parts.append({"text": canonical(candidate).decode("utf-8")})
        parts.append({"inline_data": {"mime_type": "image/png",
                        "data": base64.b64encode(image["png_bytes"]).decode("ascii")}})
    wire = prototype.build_request(parts, [c["id"] for c in group["candidates"]])
    wire["generationConfig"]["maxOutputTokens"] = MAX_OUTPUT_TOKENS
    require(len(canonical(wire)) <= MAX_REQUEST_BYTES, "full_wire_byte_limit")
    return {**group, "candidates": candidates}, wire


def validate_raster_bindings(candidate: dict, image: dict) -> dict:
    require(type(image) is dict and set(image) == {
        "document_id", "pdf_sha256", "physical_page", "render", "renderer_sha256",
        "width", "height", "bytes", "sha256", "png_bytes"}, "image_fields")
    parameters = image["render"]
    require(type(parameters) is dict and type(parameters.get("scale_to")) is int and
            parameters["scale_to"] in RENDER_SCALES and
            parameters == {**RENDER_PARAMETERS, "scale_to": parameters["scale_to"]},
            "full_page_render_parameters")
    require(image["document_id"] == candidate["document_id"] and
            image["physical_page"] == candidate["page"] and
            image["pdf_sha256"] == candidate["pdf_sha256"] and
            _sha(image["renderer_sha256"]), "raster_source_binding")
    inspected = inspect_png(image["png_bytes"])
    require(all(image[k] == value for k, value in inspected.items()) and
            max(inspected["width"], inspected["height"]) == parameters["scale_to"],
            "raster_bytes_binding")
    return {k:copy.deepcopy(value) for k,value in image.items() if k != "png_bytes"}


def prepare_from_inputs(packet: dict, bound: dict, renderer, destination: Path, *,
                        enforced: bool = False) -> Path:
    require(type(enforced) is bool and (not enforced or _inside_windows_job()),
            "enforceable_resource_mode_required")
    require(destination.is_dir() and not destination.is_symlink(), "owned_output_required")
    existing = list(destination.iterdir())
    owned = isinstance(renderer, _BoundedPopplerRenderer) and renderer.snapshots.root.parent == destination
    require(not existing or (owned and existing == [renderer.snapshots.root]),
            "output_or_partial_state_exists")
    started = time.monotonic()
    write_new(destination / "preparation-started.json", canonical({
        "schema_version": VERSION, "provider_calls": 0, "quality_pass": False,
        "resume_permitted": False}))
    for name in ("images", "inputs", "wires", "review"):
        (destination / name).mkdir()
    images, image_rows, files, requests, review_cases = {}, [], {}, [], []
    try:
        for did, page in bound["pages"]:
            remaining = MAX_PREPARATION_SECONDS - (time.monotonic() - started)
            require(remaining > 0, "preparation_timeout")
            relative = f"images/{did}-page-{page:03d}.png"
            path = destination / relative
            raw, renderer_sha, scale = renderer(Path(bound["documents"][did]["pdf_path"]),
                                         page, path, min(MAX_RENDER_SECONDS, remaining))
            metrics = inspect_png(raw)
            require(_sha(renderer_sha), "renderer_hash_required")
            if not path.exists():
                write_new(path, raw)
            else:
                require(not path.is_symlink() and path.read_bytes() == raw, "render_disk_binding")
            image = {"document_id": did, "pdf_sha256": bound["documents"][did]["sha256"],
                     "physical_page": page, "render": {**RENDER_PARAMETERS, "scale_to": scale},
                     "renderer_sha256": renderer_sha, **metrics, "png_bytes": raw}
            images[(did, page)] = image
            image_rows.append({**{k:v for k,v in image.items() if k != "png_bytes"}, "path": relative})
            files[relative] = metrics["sha256"]
            write_new(destination / f"checkpoint-image-{len(image_rows):03d}.json", canonical({
                "images_completed": len(image_rows), "provider_calls": 0, "quality_pass": False}))
        by_pair = {r["pair_id"]:r for r in bound["mapping"]}
        for ordinal, group in enumerate(bound["groups"], 1):
            require(time.monotonic()-started <= MAX_PREPARATION_SECONDS, "preparation_timeout")
            assembled, wire = build_group_payload(group, images)
            input_relative, wire_relative = f"inputs/group-{ordinal:03d}.json", f"wires/group-{ordinal:03d}.json"
            files[input_relative] = write_new(destination/input_relative, canonical(assembled))
            wire_raw = canonical(wire)
            files[wire_relative] = write_new(destination/wire_relative, wire_raw)
            requests.append({"group_id": group["group_id"], "input_path": input_relative,
                             "wire_path": wire_relative, "wire_sha256": files[wire_relative],
                             "wire_bytes": len(wire_raw), "images": 4})
            for c in assembled["candidates"]:
                mapped = by_pair[c["pair_id"]]
                review_cases.append({"review_id": mapped["review_id"], "question": group["question"],
                    "context": c["context"], "cue": c["cue"], "document_id": c["document_id"],
                    "physical_page": c["page"], "pdf_sha256": c["pdf_sha256"],
                    "image_path": f"../images/{c['document_id']}-page-{c['page']:03d}.png",
                    "image_sha256": c["image"]["sha256"]})
        review_packet = {"schema_version": VERSION, "source_packet_sha256": PACKET_SHA,
            "model_outcomes_included": False, "historical_labels_included": False,
            "provider_calls": 0, "cases": review_cases}
        files["review/packet.json"] = write_new(destination/"review/packet.json", canonical(review_packet))
        write_new(destination/"mapping-root-only.json", canonical({"schema_version": VERSION,
            "source_packet_sha256": PACKET_SHA, "historical_labels_sha256": LABEL_SHA,
            "pairs": bound["mapping"]}))
        manifest = {"schema_version": VERSION, "source_packet_sha256": PACKET_SHA,
            "parent_freeze_sha256": PARENT_FREEZE_SHA, "historical_labels_sha256": LABEL_SHA,
            "groups": GROUPS, "candidate_pairs": PAIRS, "distinct_pages": len(image_rows),
            "documents": packet["documents"], "images": image_rows, "requests": requests,
            "files": files, "resource_enforcement": RESOURCE_RECEIPT if enforced else None,
            "resource_limits_enforced": enforced, "mock_renderer": not enforced,
            "max_image_bytes": max(r["bytes"] for r in image_rows),
            "total_image_bytes": sum(r["bytes"] for r in image_rows),
            "render_scales": list(RENDER_SCALES),
            "adaptive_pages": sum(r["render"]["scale_to"] != MAX_LONG_SIDE for r in image_rows),
            "max_wire_bytes": max(r["wire_bytes"] for r in requests),
            "total_wire_bytes": sum(r["wire_bytes"] for r in requests),
            "elapsed_ms": round((time.monotonic()-started)*1000),
            "provider_calls": 0, "model_inferences": 0, "quality_pass": False,
            "scoring_permitted": False, "readability_review_complete": False,
            "source_qualification_review_complete": False, "resume_permitted": False}
        manifest_sha = write_new(destination/"manifest.json", canonical(manifest))
        write_new(destination/"freeze.json", canonical({"schema_version": VERSION,
            "manifest_sha256": manifest_sha, "groups": GROUPS, "candidate_pairs": PAIRS,
            "distinct_pages": len(image_rows), "provider_calls": 0, "quality_pass": False,
            "scoring_permitted": False}))
        write_new(destination/"preparation-receipt.json", canonical({"schema_version": VERSION,
            "complete": True, "manifest_sha256": manifest_sha,
            "resource_limits_enforced": enforced, "provider_calls": 0, "quality_pass": False}))
    except Exception as error:
        code = str(error) if isinstance(error, PreparationError) else "preparation_failed"
        write_new(destination/"failure-receipt.json", canonical({"schema_version": VERSION,
            "complete": False, "failure_code": code, "images_completed": len(image_rows),
            "provider_calls": 0, "quality_pass": False, "resume_permitted": False}))
        raise
    return destination


def prepare(*, destination: Path, resource_receipt: dict) -> Path:
    require(resource_receipt == RESOURCE_RECEIPT and _inside_windows_job(),
            "enforceable_resource_mode_required")
    packet, bound = load_inputs()
    executable = discover_renderer()
    renderer_sha = digest(executable.read_bytes())
    require(destination.is_dir() and not destination.is_symlink() and not any(destination.iterdir()),
            "output_or_partial_state_exists")
    with _LockedPublicSources(bound["documents"], destination/"source-snapshots") as snapshots:
        _verify_native_windows(packet, bound["documents"], snapshots=snapshots)
        return prepare_from_inputs(packet, bound,
            _BoundedPopplerRenderer(executable, renderer_sha, snapshots), destination, enforced=True)


def preflight() -> dict:
    packet, bound = load_inputs()
    for did, doc in bound["documents"].items():
        path = Path(doc["pdf_path"])
        require(path.is_file() and not path.is_symlink() and path.resolve().parent == PUBLIC_PDF_PARENT.resolve(),
                "pinned_public_pdf_required")
        require(path.stat().st_size <= 16_000_000 and digest(path.read_bytes()) == doc["sha256"],
                "cached_public_pdf_hash_mismatch")
    renderer = discover_renderer()
    return {"schema_version": VERSION, "groups": len(packet["groups"]), "candidate_pairs": PAIRS,
            "distinct_pages": len(bound["pages"]), "source_packet_sha256": PACKET_SHA,
            "historical_labels_sha256": LABEL_SHA, "renderer_sha256": digest(renderer.read_bytes()),
            "provider_calls": 0, "quality_pass": False, "scoring_permitted": False}


def main() -> None:
    global RESOURCE_JOB_NAME
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true")
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
            prepare(destination=args.destination, resource_receipt=RESOURCE_RECEIPT)
            return
        require(args.destination is None and args.resource_job is None and
                args.preflight != args.prepare_approved_offline, "explicit_mode_required")
        if args.preflight:
            print(json.dumps(preflight()))
            return
        require(os.name == "nt", "enforceable_resource_mode_unavailable")
        destination = Path(tempfile.mkdtemp(prefix="cardchemy-visual-heldout-input-v2-"))
        try:
            supervise(destination)
        except PreparationError as error:
            write_new(destination/"supervisor-failure.json", canonical({"schema_version": VERSION,
                "failure_code": str(error), "provider_calls": 0, "quality_pass": False,
                "resume_permitted": False}))
            raise
        print(json.dumps({"output_dir": str(destination),
            "freeze_sha256": digest((destination/"freeze.json").read_bytes()),
            "provider_calls": 0, "quality_pass": False}))
    except (PreparationError, OSError) as error:
        parser.exit(2, (str(error) if isinstance(error, PreparationError) else "preparation_io_failed")+"\n")



# Resource/render helpers retained from the reviewed offline implementation.
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
                *, timeout: float = MAX_RENDER_SECONDS, snapshot=None) -> tuple[bytes, int]:
    require(_inside_windows_job(), "enforceable_resource_mode_required")
    require(isinstance(snapshot, _LockedPublicSources) and snapshot.contains_locked(pdf),
            "locked_public_snapshot_required")
    require(pdf.name in {name + ".pdf" for name in ROSTER} and not pdf.is_symlink()
            and type(page) is int and page >= 1, "render_public_source_required")
    require(0 < timeout <= MAX_RENDER_SECONDS and not destination.exists() and
            not destination.parent.is_symlink() and destination.parent.name == "images" and
            destination.parent.parent.resolve().parent == Path(tempfile.gettempdir()).resolve(),
            "render_admission")
    prefix = destination.with_suffix("")
    deadline = time.monotonic()+timeout
    for scale in RENDER_SCALES:
        remaining = deadline-time.monotonic()
        require(remaining > 0, "render_timeout")
        command = [str(executable), "-f", str(page), "-l", str(page), "-singlefile", "-png",
                   "-scale-to", str(scale), str(pdf), str(prefix)]
        try:
            completed = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, timeout=remaining, check=False,
                                       env={"SystemRoot": os.environ.get("SystemRoot", "C:/Windows"),
                                            "PATH": str(executable.parent)},
                                       creationflags=0x08000000 if os.name == "nt" else 0)
        except subprocess.TimeoutExpired as error:
            raise PreparationError("render_timeout") from error
        require(time.monotonic() <= deadline, "render_timeout")
        require(completed.returncode == 0 and destination.is_file() and not destination.is_symlink(),
                "render_failed")
        if destination.stat().st_size > MAX_PNG_BYTES:
            if scale == RENDER_SCALES[-1]:
                raise PreparationError("png_byte_limit")
            # Only this exact exclusively-owned output file is removed; no
            # source PDF, other output directory, recursive path or shell is used.
            require(destination.resolve().parent == destination.parent.resolve(), "render_output_path")
            destination.unlink()
            continue
        with destination.open("rb") as stream:
            raw = stream.read(MAX_PNG_BYTES + 1)
        inspected = inspect_png(raw)
        require(max(inspected["width"], inspected["height"]) == scale,
                "full_page_scale_binding")
        return raw, scale
    raise PreparationError("png_byte_limit")

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
        raw, scale = render_page(self.executable, source, page, path, timeout=timeout, snapshot=self.snapshots)
        return raw, self.sha256, scale

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

if __name__ == "__main__":
    main()
