"""Keyless synthetic guards for the inert full-page visual input preparation.

All documents, questions, native text and PNGs in this file are invented here.
No cached public/private PDF, review, provider response or operator setting is
needed. Renderer tests substitute a bounded local fake rather than Poppler.
"""

from __future__ import annotations

import base64
import builtins
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
from types import SimpleNamespace
import zlib

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "prepare_visual_page_source_input_v1.py"


@pytest.fixture(scope="module")
def visual():
    spec = importlib.util.spec_from_file_location("visual_source_test_helper", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Dataclass/type introspection must resolve this isolated module identity.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    with pytest.MonkeyPatch.context() as import_path:
        import_path.syspath_prepend(str(SCRIPT.parent))
        yield module


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(
        ">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _png(width: int = 80, height: int = 60, *, color: bytes = b"\x31\x67\x98",
         padding: int = 0) -> bytes:
    """Make a complete RGB PNG using only the standard library."""
    scanlines = (b"\x00" + color * width) * height
    raw = b"\x89PNG\r\n\x1a\n" + _chunk(
        b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    if padding:
        raw += _chunk(b"tEXt", b"synthetic\x00" + b"A" * padding)
    return raw + _chunk(b"IDAT", zlib.compress(scanlines)) + _chunk(b"IEND", b"")


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode()


@pytest.fixture
def synthetic_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, visual):
    """An invented calibration with all 66/264 cases and 80 source pages."""
    source_parent = tmp_path / "synthetic-public-pdfs"
    source_parent.mkdir()
    monkeypatch.setattr(visual, "PUBLIC_PDF_PARENT", source_parent)
    documents = {}
    for did in ("lec04", "lec05", "lec06", "lec07"):
        path = source_parent / f"{did}.pdf"
        raw = f"%PDF-1.7\nSynthetic bytes for {did}; not a real PDF.\n".encode()
        path.write_bytes(raw)
        documents[did] = {"pages": 20, "sha256": _sha(raw), "pdf_path": str(path)}
    groups, pairs, native_pages = [], [], {}
    for group_number in range(66):
        gid = f"synthetic-{group_number:03d}"
        candidates = []
        for ordinal in range(4):
            index = (group_number * 4 + ordinal) % 80
            did = ("lec04", "lec05", "lec06", "lec07")[(index // 2) % 4]
            page = (index // 8) * 2 + index % 2 + 1
            cue = f"Synthetic relation for {did}:{page}."
            context = f"Before\n{cue}\nAfter."
            native = f"Prefix 123\n{context}\nSuffix."
            native_pages[(did, page)] = native
            candidate = {
                "id": f"S{ordinal + 1:02d}", "document_id": did, "page": page,
                "context": context, "context_start": 11,
                "context_end": 11 + len(context), "cue": cue,
                "cue_start": 18, "cue_end": 18 + len(cue),
                "page_text_sha256": _sha(native.encode()),
            }
            candidates.append(candidate)
            pairs.append({
                "pair_id": f"P{group_number * 4 + ordinal + 1:03d}",
                "group_id": f"Q{group_number + 1:03d}",
                "old_group_id": gid, "old_candidate_id": candidate["id"],
                "document_id": did, "page": page,
                "page_text_sha256": candidate["page_text_sha256"],
                "context_start": candidate["context_start"],
                "context_end": candidate["context_end"],
                "cue_start": candidate["cue_start"], "cue_end": candidate["cue_end"],
                "pdf_path": documents[did]["pdf_path"],
                "pdf_sha256": documents[did]["sha256"],
            })
        groups.append({"group_id": gid,
                       "question": f"What connects synthetic learning step {group_number} to its result?",
                       "candidates": candidates})
    mapping = {"schema_version": "source_usefulness_contract_audit_v1", "pairs": pairs}
    packet = {"schema_version": "synthetic_calibration_packet_v1",
              "corpus_id": "synthetic-public-calibration", "documents": [
                  {"document_id": did, "pages": source["pages"], "sha256": source["sha256"]}
                  for did, source in documents.items()],
              "groups": groups, "source_manifest_sha256": "a" * 64,
              "split": "calibration"}
    freeze = {"schema_version": "source_usefulness_contract_audit_v1",
              "groups": 66, "candidate_pairs": 264,
              "mapping_sha256": _sha(_canonical(mapping)),
              "source_packet_sha256": _sha(_canonical(packet)),
              "source_manifest_sha256": packet["source_manifest_sha256"],
              "wire_packet_hashes": {str(n): str(n) * 64 for n in (1, 2, 3)},
              "rubric_sha256": "b" * 64, "shuffle_seed": "synthetic-seed"}
    summary = {"groups": 66, "pairs": 264,
               "parent_freeze_sha256": _sha(_canonical(freeze)),
               "provider_calls": 0, "quality_pass": False, "provider_trial_ready": False}
    monkeypatch.setattr(visual, "PACKET_SHA", freeze["source_packet_sha256"])
    monkeypatch.setattr(visual, "FREEZE_SHA", summary["parent_freeze_sha256"])
    return {"packet": packet, "mapping": mapping, "freeze": freeze,
            "summary": summary, "documents": documents, "native_pages": native_pages,
            "source_parent": source_parent}


def _validate(visual, inputs):
    return visual.validate_inputs(inputs["packet"], inputs["mapping"], inputs["freeze"],
                                  inputs["summary"], inputs["documents"])


def _images(visual, inputs):
    return {source: {"document_id": source[0],
                     "pdf_sha256": inputs["documents"][source[0]]["sha256"],
                     "physical_page": source[1], "render": copy.deepcopy(visual.RENDER_PARAMETERS),
                     "renderer_sha256": "c" * 64,
                     **visual.inspect_png(raw := _png()), "png_bytes": raw}
            for source in inputs["native_pages"]}


def _rebind(inputs, visual, monkeypatch):
    """Keep outer hashes valid so a semantic guard, not a stale hash, is tested."""
    inputs["freeze"]["mapping_sha256"] = _sha(_canonical(inputs["mapping"]))
    inputs["freeze"]["source_packet_sha256"] = _sha(_canonical(inputs["packet"]))
    inputs["summary"]["parent_freeze_sha256"] = _sha(_canonical(inputs["freeze"]))
    monkeypatch.setattr(visual, "PACKET_SHA", inputs["freeze"]["source_packet_sha256"])
    monkeypatch.setattr(visual, "FREEZE_SHA", inputs["summary"]["parent_freeze_sha256"])


def _enriched_group(inputs, group):
    enriched = copy.deepcopy(group)
    pairs = {(row["old_group_id"], row["old_candidate_id"]): row
             for row in inputs["mapping"]["pairs"]}
    for candidate in enriched["candidates"]:
        origin = pairs[(group["group_id"], candidate["id"])]
        candidate.update(pair_id=origin["pair_id"], pdf_sha256=origin["pdf_sha256"])
    return enriched


def test_png_metadata_is_computed_from_complete_encoded_bytes(visual):
    raw = _png(1600, 1250)
    metadata = visual.inspect_png(raw)
    assert metadata["width"] == 1600
    assert metadata["height"] == 1250
    assert metadata["bytes"] == len(raw)
    assert metadata["sha256"] == _sha(raw)


@pytest.mark.parametrize("width,height", [(1601, 10), (10, 1601), (1600, 1251)])
def test_png_long_side_and_pixel_caps_are_independent(visual, width, height):
    with pytest.raises(visual.PreparationError):
        visual.inspect_png(_png(width, height))


def test_encoded_png_cap_is_enforced_on_bytes_even_for_small_dimensions(visual):
    raw = _png(padding=visual.MAX_PNG_BYTES)
    assert len(raw) > 1_048_576
    with pytest.raises(visual.PreparationError):
        visual.inspect_png(raw)


def test_exact_one_mib_png_is_admitted_without_rescaling(visual):
    padding = visual.MAX_PNG_BYTES - len(_png(padding=1)) + 1
    raw = _png(padding=padding)
    assert len(raw) == 1_048_576
    metadata = visual.inspect_png(raw)
    assert metadata["bytes"] == 1_048_576
    assert (metadata["width"], metadata["height"]) == (80, 60)


@pytest.mark.parametrize("kind", ["signature", "crc", "truncated", "missing_idat",
                                  "trailing_bytes", "incomplete_scanlines"])
def test_png_integrity_rejects_complete_header_with_invalid_image(visual, kind):
    raw = _png()
    if kind == "signature":
        raw = b"not-a-png" + raw[8:]
    elif kind == "crc":
        raw = raw[:29] + bytes([raw[29] ^ 1]) + raw[30:]
    elif kind == "truncated":
        raw = raw[:-4]
    elif kind == "missing_idat":
        raw = raw[:33] + _chunk(b"IEND", b"")
    elif kind == "trailing_bytes":
        raw += b"synthetic-other-image"
    else:
        raw = raw[:33] + _chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")) + _chunk(b"IEND", b"")
    with pytest.raises(visual.PreparationError):
        visual.inspect_png(raw)


def test_public_calibration_admission_preserves_all_groups_pairs_and_pages(visual, synthetic_inputs):
    _validate(visual, synthetic_inputs)
    images = _images(visual, synthetic_inputs)
    groups = [visual.build_group_input(_enriched_group(synthetic_inputs, group), images)
              for group in synthetic_inputs["packet"]["groups"]]
    assert len(groups) == 66
    assert sum(len(group["candidates"]) for group in groups) == 264
    assert len(images) == 80
    for old, new in zip(synthetic_inputs["packet"]["groups"], groups, strict=True):
        assert new["group_id"] == old["group_id"]
        assert new["question"] == old["question"]
        assert [candidate["id"] for candidate in new["candidates"]] == ["S01", "S02", "S03", "S04"]
        for original, candidate in zip(old["candidates"], new["candidates"], strict=True):
            assert all(candidate[key] == value for key, value in original.items())


@pytest.mark.parametrize("kind", ["heldout_split", "missing_group", "duplicate_group",
                                  "missing_pair", "duplicate_pair", "wrong_roster",
                                  "wrong_source_hash", "wrong_source_page", "wrong_source_offset",
                                  "wrong_page_text_hash", "outside_source_path",
                                  "manifest_binding", "mapping_binding", "freeze_binding"])
def test_calibration_hash_roster_and_complete_mapping_are_required(
    visual, synthetic_inputs, kind, monkeypatch,
):
    inputs = copy.deepcopy(synthetic_inputs)
    packet, mapping = inputs["packet"], inputs["mapping"]
    if kind == "heldout_split":
        packet["split"] = "heldout"
    elif kind == "missing_group":
        packet["groups"].pop()
    elif kind == "duplicate_group":
        packet["groups"][-1] = copy.deepcopy(packet["groups"][0])
    elif kind == "missing_pair":
        mapping["pairs"].pop()
    elif kind == "duplicate_pair":
        mapping["pairs"][-1] = copy.deepcopy(mapping["pairs"][0])
    elif kind == "wrong_roster":
        packet["documents"][0]["document_id"] = "private-knowledge"
    elif kind == "wrong_source_hash":
        mapping["pairs"][0]["pdf_sha256"] = "0" * 64
    elif kind == "wrong_source_page":
        mapping["pairs"][0]["page"] = 21
    elif kind == "wrong_source_offset":
        mapping["pairs"][0]["cue_start"] += 1
    elif kind == "wrong_page_text_hash":
        mapping["pairs"][0]["page_text_sha256"] = "0" * 64
    elif kind == "outside_source_path":
        mapping["pairs"][0]["pdf_path"] = str(inputs["source_parent"].parent / "heldout" / "lec04.pdf")
    elif kind == "manifest_binding":
        packet["source_manifest_sha256"] = "0" * 64
    elif kind == "mapping_binding":
        inputs["freeze"]["mapping_sha256"] = "0" * 64
    else:
        inputs["summary"]["parent_freeze_sha256"] = "0" * 64
    if kind not in {"mapping_binding", "freeze_binding"}:
        _rebind(inputs, visual, monkeypatch)
    with pytest.raises(visual.PreparationError):
        _validate(visual, inputs)


@pytest.mark.parametrize("kind", ["context_length", "cue_length", "cue_offset",
                                  "negative_offset", "boolean_page", "foreign_id",
                                  "duplicate_id", "fifth_candidate", "label_leak"])
def test_source_windows_and_candidate_identity_cannot_be_invented(
    visual, synthetic_inputs, kind, monkeypatch,
):
    inputs = copy.deepcopy(synthetic_inputs)
    candidate = inputs["packet"]["groups"][0]["candidates"][0]
    if kind == "context_length":
        candidate["context_end"] += 1
    elif kind == "cue_length":
        candidate["cue_end"] += 1
    elif kind == "cue_offset":
        candidate["cue_start"] += 1
        candidate["cue_end"] += 1
    elif kind == "negative_offset":
        candidate["context_start"] = -1
    elif kind == "boolean_page":
        candidate["page"] = True
    elif kind == "foreign_id":
        candidate["id"] = "INVENTED"
    elif kind == "duplicate_id":
        candidate["id"] = "S02"
    elif kind == "fifth_candidate":
        inputs["packet"]["groups"][0]["candidates"].append(copy.deepcopy(candidate))
    else:
        candidate["page_usefulness"] = "Yes"
    _rebind(inputs, visual, monkeypatch)
    with pytest.raises(visual.PreparationError):
        _validate(visual, inputs)


def test_heldout_private_old_model_and_environment_are_not_read_by_pure_path(
    visual, synthetic_inputs, monkeypatch: pytest.MonkeyPatch,
):
    images = _images(visual, synthetic_inputs)
    reads = []
    network = []

    def forbidden_read(path, *args, **kwargs):
        reads.append(str(path))
        pytest.fail("The pure preparation path attempted an external file read")

    def forbidden_network(*args, **kwargs):
        network.append(args)
        pytest.fail("The offline preparation path attempted network execution")

    monkeypatch.setattr(Path, "read_bytes", forbidden_read)
    monkeypatch.setattr(Path, "read_text", forbidden_read)
    monkeypatch.setattr(builtins, "open", forbidden_read)
    monkeypatch.setattr(os, "getenv", forbidden_read)
    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(socket.socket, "connect", forbidden_network)
    monkeypatch.setattr(subprocess, "run", forbidden_network)
    monkeypatch.setattr(subprocess, "Popen", forbidden_network)
    _validate(visual, synthetic_inputs)
    for group in synthetic_inputs["packet"]["groups"]:
        payload = visual.build_payload(visual.build_group_input(
            _enriched_group(synthetic_inputs, group), images))
        assert len(_canonical(payload)) <= 6 * 1_048_576
    assert reads == network == []


def test_helper_import_needs_no_application_provider_or_renderer_dependencies():
    code = """
import importlib.util
import sys
import builtins
old_import = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'app', 'dotenv', 'pypdf', 'PIL', 'httpx', 'google', 'torch', 'onnxruntime'}:
        raise RuntimeError('forbidden external dependency import')
    return old_import(name, *args, **kwargs)
builtins.__import__ = guarded
spec = importlib.util.spec_from_file_location('synthetic_visual_import', sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
assert module.MAX_LONG_SIDE == 1600
"""
    result = subprocess.run([sys.executable, "-S", "-c", code, str(SCRIPT)],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("kind", ["missing", "bytes_changed", "hash_changed", "width_changed",
                                  "physical_page_changed", "pdf_hash_changed", "renderer_changed",
                                  "crop_changed", "substituted_metadata"])
def test_full_page_image_source_and_encoded_binding_cannot_be_substituted(
    visual, synthetic_inputs, kind,
):
    group = _enriched_group(synthetic_inputs, synthetic_inputs["packet"]["groups"][0])
    images = _images(visual, synthetic_inputs)
    first = group["candidates"][0]
    source = (first["document_id"], first["page"])
    image = images[source]
    if kind == "missing":
        images.pop(source)
    elif kind == "bytes_changed":
        image["png_bytes"] = _png(color=b"\x67\x31\x98")
    elif kind == "hash_changed":
        image["sha256"] = "0" * 64
    elif kind == "width_changed":
        image["width"] += 1
    elif kind == "physical_page_changed":
        image["physical_page"] += 1
    elif kind == "pdf_hash_changed":
        image["pdf_sha256"] = "0" * 64
    elif kind == "renderer_changed":
        image["renderer_sha256"] = "not-a-sha"
    elif kind == "crop_changed":
        image["render"]["crop"] = True
    else:
        other = group["candidates"][1]
        images[source] = copy.deepcopy(images[(other["document_id"], other["page"])])
    with pytest.raises(visual.PreparationError):
        visual.build_group_input(group, images)


@pytest.mark.parametrize("kind", ["mutated_png", "mutated_metadata", "different_source",
                                  "extra_image", "incomplete_images"])
def test_payload_rechecks_frozen_image_binding_and_four_image_window(
    visual, synthetic_inputs, kind,
):
    group = visual.build_group_input(
        _enriched_group(synthetic_inputs, synthetic_inputs["packet"]["groups"][0]),
        _images(visual, synthetic_inputs))
    candidate = group["candidates"][0]
    if kind == "mutated_png":
        candidate["_image_bytes"] = _png(color=b"\x98\x67\x31")
    elif kind == "mutated_metadata":
        candidate["image"]["bytes"] += 1
    elif kind == "different_source":
        candidate["page"] += 1
    elif kind == "extra_image":
        group["candidates"].append(copy.deepcopy(candidate))
    else:
        group["candidates"].pop()
    with pytest.raises(visual.PreparationError):
        visual.build_payload(group)


def test_payload_exact_png_bytes_and_actual_encoded_request_size(visual, synthetic_inputs, monkeypatch):
    images = _images(visual, synthetic_inputs)
    raw = _png(padding=visual.MAX_PNG_BYTES - len(_png(padding=1)) + 1)
    for image in images.values():
        image.update(**visual.inspect_png(raw), png_bytes=raw)
    group = visual.build_group_input(
        _enriched_group(synthetic_inputs, synthetic_inputs["packet"]["groups"][0]), images)
    payload = visual.build_payload(group)
    parts = payload["contents"][0]["parts"]
    assert len(parts) == 9
    assert json.loads(parts[0]["text"])["question"] == group["question"]
    for index, candidate in enumerate(group["candidates"]):
        text = json.loads(parts[index * 2 + 1]["text"])
        assert text["id"] == candidate["id"]
        assert text["context"] == candidate["context"] and text["cue"] == candidate["cue"]
        inline = parts[index * 2 + 2]["inline_data"]
        assert inline["mime_type"] == "image/png"
        assert base64.b64decode(inline["data"], validate=True) == raw
    actual_size = len(_canonical(payload))
    assert 4 * visual.MAX_PNG_BYTES < actual_size <= 6 * 1_048_576
    monkeypatch.setattr(visual, "MAX_REQUEST_BYTES", actual_size)
    assert visual.build_payload(group) == payload
    monkeypatch.setattr(visual, "MAX_REQUEST_BYTES", actual_size - 1)
    with pytest.raises(visual.PreparationError, match="request_byte_limit"):
        visual.build_payload(group)


def test_production_source_loader_rejects_unapproved_root_before_any_read(
    visual, tmp_path, monkeypatch,
):
    reads = []

    def forbidden(*args, **kwargs):
        reads.append(args)
        pytest.fail("An unapproved source root was opened")

    monkeypatch.setattr(visual, "read_json", forbidden)
    with pytest.raises(visual.PreparationError, match="approved_audit_root_required"):
        visual.load_inputs(tmp_path / "heldout")
    assert reads == []


def test_production_loader_reads_only_four_pinned_calibration_inputs(
    visual, synthetic_inputs, tmp_path, monkeypatch,
):
    root = tmp_path / "synthetic-audit-root"
    root.mkdir()
    packet_path = tmp_path / "synthetic-calibration" / "packet.json"
    monkeypatch.setattr(visual, "AUDIT_ROOT", root)
    monkeypatch.setattr(visual, "PACKET_PATH", packet_path)
    expected = {
        root / "freeze.json": (synthetic_inputs["freeze"], visual.FREEZE_SHA),
        packet_path: (synthetic_inputs["packet"], visual.PACKET_SHA),
        root / "mapping-root-only.json": (synthetic_inputs["mapping"],
                                          synthetic_inputs["freeze"]["mapping_sha256"]),
        root / "final" / "summary.json": (synthetic_inputs["summary"], visual.SUMMARY_SHA),
    }
    reads = []

    def pinned_read(path, fingerprint):
        assert path in expected
        value, expected_fingerprint = expected[path]
        assert fingerprint == expected_fingerprint
        reads.append(path)
        return copy.deepcopy(value)

    monkeypatch.setattr(visual, "read_json", pinned_read)
    loaded = visual.load_inputs(root)
    assert len(loaded[0]["groups"]) == 66 and len(loaded[1]["pairs"]) == 264
    assert reads == list(expected)
    assert not any("heldout" in str(path) or path.name == ".env" for path in reads)


@pytest.mark.parametrize("kind", ["hash", "duplicate_key", "nonobject", "oversized"])
def test_pinned_json_admission_uses_exact_bytes_closed_shape_and_size(
    visual, tmp_path, kind,
):
    raw = {"hash": b'{"a":1}', "duplicate_key": b'{"a":1,"a":2}',
           "nonobject": b"[]", "oversized": b" " * 2_000_001}[kind]
    path = tmp_path / "synthetic.json"
    path.write_bytes(raw)
    fingerprint = "0" * 64 if kind == "hash" else _sha(raw)
    with pytest.raises(visual.PreparationError):
        visual.read_json(path, fingerprint)


def test_freeze_write_is_exclusive_and_preserves_existing_bytes(visual, tmp_path):
    path = tmp_path / "one-use.json"
    original = b'{"synthetic":"immutable"}'
    assert visual.write_new(path, original) == _sha(original)
    with pytest.raises(FileExistsError):
        visual.write_new(path, b'{"synthetic":"replacement"}')
    assert path.read_bytes() == original


def test_arbitrary_preexisting_output_is_rejected_before_renderer_calls(
    visual, synthetic_inputs, tmp_path,
):
    destination = tmp_path / "output-with-existing-work"
    destination.mkdir()
    original = destination / "unrelated-user-file.txt"
    original.write_bytes(b"Preserve this pre-existing synthetic work.")
    calls = []
    with pytest.raises(visual.PreparationError, match="output_or_partial_state_exists"):
        _prepare(visual, synthetic_inputs, lambda *args: calls.append(args), tmp_path,
                 destination=destination)
    assert calls == [] and original.read_bytes() == b"Preserve this pre-existing synthetic work."


def _prepare(visual, inputs, renderer, output_parent, **kwargs):
    return visual.prepare_from_inputs(
        inputs["packet"], inputs["mapping"], inputs["freeze"], inputs["summary"],
        inputs["documents"], renderer, output_parent, **kwargs)


def test_complete_synthetic_freeze_binds_every_image_input_and_payload(
    visual, synthetic_inputs, tmp_path,
):
    calls = []

    def fake_render(pdf, page, destination, timeout):
        calls.append((pdf, page, destination, timeout))
        return _png(), "c" * 64

    output = _prepare(visual, synthetic_inputs, fake_render, tmp_path)
    manifest = json.loads((output / "manifest.json").read_bytes())
    frozen = json.loads((output / "freeze.json").read_bytes())
    receipt = json.loads((output / "preparation-receipt.json").read_bytes())
    assert len(calls) == manifest["distinct_pages"] == frozen["distinct_pages"] == 80
    assert manifest["groups"] == frozen["groups"] == 66
    assert manifest["candidate_pairs"] == frozen["candidate_pairs"] == 264
    assert len(manifest["requests"]) == 66
    assert len(manifest["files"]) == 80 + 66 + 66
    assert all(0 < call[3] <= 30 for call in calls)
    for relative, fingerprint in manifest["files"].items():
        assert _sha((output / relative).read_bytes()) == fingerprint
    manifest_sha = _sha((output / "manifest.json").read_bytes())
    assert frozen["manifest_sha256"] == receipt["manifest_sha256"] == manifest_sha
    assert manifest["provider_calls"] == manifest["count_tokens_calls"] == manifest["model_inferences"] == 0
    assert manifest["quality_pass"] is manifest["provider_trial_ready"] is False
    assert manifest["resource_limits_enforced"] is False and manifest["mock_renderer"] is True
    assert manifest["readability_review_complete"] is False
    assert manifest["resume_permitted"] is frozen["scoring_permitted"] is False
    assert receipt["complete"] is True and receipt["resource_limits_enforced"] is False
    before = {p.relative_to(output).as_posix(): _sha(p.read_bytes())
              for p in output.rglob("*") if p.is_file()}
    with pytest.raises(visual.PreparationError, match="output_or_partial_state_exists"):
        _prepare(visual, synthetic_inputs, fake_render, tmp_path, destination=output)
    assert len(calls) == 80
    assert before == {p.relative_to(output).as_posix(): _sha(p.read_bytes())
                      for p in output.rglob("*") if p.is_file()}


def test_failed_partial_preparation_is_preserved_and_cannot_replay(
    visual, synthetic_inputs, tmp_path,
):
    destination = tmp_path / "one-use-output"
    destination.mkdir()
    calls = []

    def fail_second(pdf, page, path, timeout):
        calls.append((pdf, page))
        if len(calls) == 2:
            raise visual.PreparationError("synthetic_render_failure")
        return _png(), "c" * 64

    with pytest.raises(visual.PreparationError, match="synthetic_render_failure"):
        _prepare(visual, synthetic_inputs, fail_second, tmp_path, destination=destination)
    failure = json.loads((destination / "failure-receipt.json").read_bytes())
    assert failure["complete"] is False and failure["resume_permitted"] is False
    assert failure["images_completed"] == 1 and failure["provider_calls"] == 0
    assert not (destination / "manifest.json").exists()
    assert not (destination / "preparation-receipt.json").exists()
    first = next((destination / "images").glob("*.png")).read_bytes()
    with pytest.raises(visual.PreparationError, match="output_or_partial_state_exists"):
        _prepare(visual, synthetic_inputs, fail_second, tmp_path, destination=destination)
    assert len(calls) == 2
    assert next((destination / "images").glob("*.png")).read_bytes() == first


def test_supplied_resource_receipt_cannot_claim_isolation_for_injected_renderer(
    visual, synthetic_inputs, tmp_path,
):
    def fake_render(*args):
        return _png(), "c" * 64

    output = _prepare(visual, synthetic_inputs, fake_render, tmp_path,
                      resource_receipt=copy.deepcopy(visual.RESOURCE_RECEIPT))
    manifest = json.loads((output / "manifest.json").read_bytes())
    assert manifest["resource_limits_enforced"] is False
    assert manifest["mock_renderer"] is True


@pytest.fixture
def synthetic_freeze(visual, synthetic_inputs, tmp_path):
    output = _prepare(visual, synthetic_inputs, lambda *args: (_png(), "c" * 64), tmp_path)
    return output, _sha((output / "freeze.json").read_bytes())


def test_frozen_loader_uses_independent_freeze_sha_and_rebuilds_exact_payload(
    visual, synthetic_freeze,
):
    output, freeze_sha = synthetic_freeze
    group = visual.load_frozen_group(output, 1, expected_freeze_sha256=freeze_sha, allow_mock=True)
    payload = visual.build_payload(group)
    assert _canonical(payload) == (output / "payloads/group-001.json").read_bytes()
    assert len(group["candidates"]) == 4


@pytest.mark.parametrize("kind", ["freeze_changed", "missing_freeze", "missing_image",
                                  "mutated_png", "substituted_png", "changed_input",
                                  "rebound_image_hash", "incomplete_denominator"])
def test_frozen_loader_rejects_partial_mutated_and_substituted_artifacts(
    visual, synthetic_freeze, kind,
):
    output, freeze_sha = synthetic_freeze
    frozen = json.loads((output / "freeze.json").read_bytes())
    manifest = json.loads((output / "manifest.json").read_bytes())
    first_image = output / manifest["images"][0]["path"]
    if kind == "freeze_changed":
        (output / "freeze.json").write_bytes((output / "freeze.json").read_bytes() + b" ")
    elif kind == "missing_freeze":
        (output / "freeze.json").unlink()
    elif kind == "missing_image":
        first_image.unlink()
    elif kind == "mutated_png":
        first_image.write_bytes(first_image.read_bytes()[:-4])
    elif kind == "substituted_png":
        first_image.write_bytes(_png(color=b"\x67\x98\x31"))
    elif kind == "changed_input":
        path = output / "inputs/group-001.json"
        value = json.loads(path.read_bytes())
        value["question"] += " silently altered"
        path.write_bytes(_canonical(value))
    elif kind == "rebound_image_hash":
        # Valid outer file hashes do not excuse an image substituted for the
        # source-bound metadata in the independently frozen group input.
        first_image.write_bytes(_png(color=b"\x98\x31\x67"))
        fingerprint = _sha(first_image.read_bytes())
        manifest["images"][0]["sha256"] = fingerprint
        manifest["files"][manifest["images"][0]["path"]] = fingerprint
        (output / "manifest.json").write_bytes(_canonical(manifest))
        frozen["manifest_sha256"] = _sha(_canonical(manifest))
        (output / "freeze.json").write_bytes(_canonical(frozen))
        # This separately supplied synthetic receipt intentionally binds the
        # new outer freeze so the deeper metadata guard is exercised.
        freeze_sha = _sha(_canonical(frozen))
    else:
        frozen["candidate_pairs"] = 260
        (output / "freeze.json").write_bytes(_canonical(frozen))
        freeze_sha = _sha(_canonical(frozen))
    with pytest.raises(visual.PreparationError):
        visual.load_frozen_group(output, 1, expected_freeze_sha256=freeze_sha, allow_mock=True)


def test_synthetic_preparation_is_not_admitted_as_real_frozen_input(visual, synthetic_freeze):
    output, freeze_sha = synthetic_freeze
    with pytest.raises(visual.PreparationError, match="enforced_preparation_required"):
        visual.load_frozen_group(output, 1, expected_freeze_sha256=freeze_sha)


def test_pdf_and_native_text_binding_reads_only_synthetic_calibration_sources(
    visual, synthetic_inputs, monkeypatch,
):
    opened, extracted = [], []
    original_open = Path.open
    approved = {Path(doc["pdf_path"]).resolve() for doc in synthetic_inputs["documents"].values()}

    def safe_open(path, *args, **kwargs):
        assert path.resolve() in approved
        opened.append(path.resolve())
        return original_open(path, *args, **kwargs)

    class FakeReader:
        def __init__(self, path):
            did = path.stem

            def page(number):
                def extract_text():
                    extracted.append((did, number))
                    return synthetic_inputs["native_pages"][(did, number)]
                return SimpleNamespace(extract_text=extract_text)

            self.pages = [page(number) for number in range(1, 21)]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=FakeReader))
    monkeypatch.setattr(Path, "open", safe_open)
    visual._verify_native_windows(synthetic_inputs["packet"], synthetic_inputs["documents"])
    assert set(opened) == approved and len(opened) == 4
    assert len(extracted) == len(set(extracted)) == 80


@pytest.mark.parametrize("kind", ["pdf_bytes", "page_count", "native_text"])
def test_native_verification_rejects_pdf_or_extracted_page_changes_before_render(
    visual, synthetic_inputs, monkeypatch, kind,
):
    render_calls = []
    monkeypatch.setattr(visual, "render_page", lambda *args: render_calls.append(args))
    first = Path(synthetic_inputs["documents"]["lec04"]["pdf_path"])
    if kind == "pdf_bytes":
        first.write_bytes(first.read_bytes() + b" changed")

    class FakeReader:
        def __init__(self, path):
            did = path.stem
            count = 19 if kind == "page_count" else 20
            self.pages = [SimpleNamespace(extract_text=lambda n=n: (
                synthetic_inputs["native_pages"][(did, n)] +
                (" changed" if kind == "native_text" else ""))) for n in range(1, count + 1)]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=FakeReader))
    with pytest.raises(visual.PreparationError):
        visual._verify_native_windows(synthetic_inputs["packet"], synthetic_inputs["documents"])
    assert render_calls == []


def test_production_preparation_checks_enforcement_before_source_or_renderer_access(
    visual, tmp_path, monkeypatch,
):
    opened = []
    monkeypatch.setattr(visual, "_inside_windows_job", lambda: False)
    monkeypatch.setattr(visual, "load_inputs", lambda *args: opened.append("inputs"))
    monkeypatch.setattr(visual, "discover_renderer", lambda: opened.append("renderer"))
    with pytest.raises(visual.PreparationError, match="enforceable_resource_mode_required"):
        visual.prepare(destination=tmp_path, resource_receipt=visual.RESOURCE_RECEIPT)
    assert opened == []


def test_rendering_requires_actual_job_limits_before_any_child_process(
    visual, synthetic_inputs, tmp_path, monkeypatch,
):
    calls = []
    monkeypatch.setattr(visual, "_inside_windows_job", lambda: False)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(visual.PreparationError, match="enforceable_resource_mode_required"):
        visual.render_page(tmp_path / "fake-poppler.exe", Path(synthetic_inputs["documents"]["lec04"]["pdf_path"]),
                           1, tmp_path / "unused.png")
    assert calls == []


def test_full_physical_page_renderer_command_and_child_timeout_are_enforced(
    visual, synthetic_inputs, tmp_path, monkeypatch,
):
    calls = []
    destination = tmp_path / "rendered.png"
    executable = tmp_path / "existing-poppler.exe"
    pdf = Path(synthetic_inputs["documents"]["lec04"]["pdf_path"])
    snapshot = visual._LockedPublicSources({}, tmp_path / "synthetic-snapshot-token")
    monkeypatch.setattr(snapshot, "contains_locked", lambda path: path == pdf)
    monkeypatch.setattr(visual, "_inside_windows_job", lambda: True)

    def run(command, **kwargs):
        calls.append((command, kwargs))
        destination.write_bytes(_png())
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-key-must-not-be-inherited")
    raw = visual.render_page(executable, pdf, 7, destination, timeout=29.5, snapshot=snapshot)
    command, options = calls[0]
    assert command == [str(executable), "-f", "7", "-l", "7", "-singlefile", "-png",
                       "-scale-to", "1600", str(pdf), str(destination.with_suffix(""))]
    assert options["timeout"] == 29.5 and options["check"] is False
    assert options["stdin"] == options["stdout"] == options["stderr"] == subprocess.DEVNULL
    assert set(options["env"]) == {"SystemRoot", "PATH"}
    assert "GEMINI_API_KEY" not in options["env"]
    assert not options["creationflags"] & 0x01000000  # No job breakaway.
    assert raw == _png() and len(calls) == 1


def test_renderer_timeout_is_one_failure_without_retry(visual, synthetic_inputs, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(visual, "_inside_windows_job", lambda: True)
    pdf = Path(synthetic_inputs["documents"]["lec04"]["pdf_path"])
    snapshot = visual._LockedPublicSources({}, tmp_path / "synthetic-snapshot-token")
    monkeypatch.setattr(snapshot, "contains_locked", lambda path: path == pdf)

    def timeout(command, **kwargs):
        calls.append(command)
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(visual.PreparationError, match="render_timeout"):
        visual.render_page(tmp_path / "existing-poppler.exe",
                           pdf, 1, tmp_path / "never-created.png", timeout=30, snapshot=snapshot)
    assert len(calls) == 1


def test_renderer_rejects_unlocked_source_even_inside_restricted_job(
    visual, synthetic_inputs, tmp_path, monkeypatch,
):
    calls = []
    monkeypatch.setattr(visual, "_inside_windows_job", lambda: True)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: calls.append(args))
    snapshot = visual._LockedPublicSources({}, tmp_path / "synthetic-snapshot-token")
    with pytest.raises(visual.PreparationError, match="locked_public_snapshot_required"):
        visual.render_page(tmp_path / "existing-poppler.exe",
                           Path(synthetic_inputs["documents"]["lec04"]["pdf_path"]),
                           1, tmp_path / "never-created.png", snapshot=snapshot)
    assert calls == []


def test_snapshot_read_lock_denies_write_and_delete_sharing(visual, tmp_path, monkeypatch):
    import ctypes

    calls = []

    def create_file(*args):
        calls.append(args)
        return 201

    kernel = SimpleNamespace(CreateFileW=_FakeApi(create_file))
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: kernel, raising=False)
    snapshot = visual._LockedPublicSources({}, tmp_path / "synthetic-snapshot-token")
    assert snapshot._lock_read(tmp_path / "synthetic.pdf")[1] == 201
    assert calls[0][1:6] == (0x80000000, 1, None, 3, 0x80)


def test_snapshot_copies_exact_four_sources_holds_locks_and_cleans_only_owned_copy(
    visual, synthetic_inputs, tmp_path, monkeypatch,
):
    preparation = tmp_path / "preparation"
    preparation.mkdir()
    root = preparation / "source-snapshots"
    snapshot = visual._LockedPublicSources(synthetic_inputs["documents"], root)
    locked, closed = [], []
    kernel = SimpleNamespace(CloseHandle=_FakeApi(lambda handle: closed.append(handle) or 1))

    def fake_lock(path):
        handle = len(locked) + 1
        locked.append((path, handle))
        return kernel, handle

    monkeypatch.setattr(visual, "_inside_windows_job", lambda: True)
    monkeypatch.setattr(visual.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(snapshot, "_lock_read", fake_lock)
    before = {did: Path(doc["pdf_path"]).read_bytes()
              for did, doc in synthetic_inputs["documents"].items()}
    with snapshot as active:
        assert set(active.paths) == {"lec04", "lec05", "lec06", "lec07"}
        assert len(active.handles) == 4 and len(locked) == 8 and len(closed) == 4
        for did, path in active.paths.items():
            assert path.parent == root
            assert path.read_bytes() == before[did]
            assert active.contains_locked(path)
            assert not active.contains_locked(Path(synthetic_inputs["documents"][did]["pdf_path"]))
    assert len(closed) == 8 and len(snapshot.handles) == 0
    assert not root.exists() and preparation.is_dir()
    assert before == {did: Path(doc["pdf_path"]).read_bytes()
                      for did, doc in synthetic_inputs["documents"].items()}


def test_snapshot_admission_denies_unsupported_isolation_before_source_copy(
    visual, synthetic_inputs, tmp_path, monkeypatch,
):
    root = tmp_path / "preparation" / "source-snapshots"
    snapshot = visual._LockedPublicSources(synthetic_inputs["documents"], root)
    locks = []
    monkeypatch.setattr(visual, "_inside_windows_job", lambda: False)
    monkeypatch.setattr(snapshot, "_lock_read", lambda path: locks.append(path))
    with pytest.raises(visual.PreparationError, match="enforceable_resource_mode_required"):
        snapshot.__enter__()
    assert locks == [] and not root.exists()


def test_snapshot_substitution_between_copy_and_lock_is_rejected(
    visual, synthetic_inputs, tmp_path, monkeypatch,
):
    preparation = tmp_path / "preparation"
    preparation.mkdir()
    root = preparation / "source-snapshots"
    snapshot = visual._LockedPublicSources(synthetic_inputs["documents"], root)
    kernel = SimpleNamespace(CloseHandle=_FakeApi(lambda handle: 1))
    before = {did: Path(doc["pdf_path"]).read_bytes()
              for did, doc in synthetic_inputs["documents"].items()}
    def fake_lock(path):
        if path.parent == root:
            path.write_bytes(b"substituted invented snapshot")
        return kernel, 201
    monkeypatch.setattr(visual, "_inside_windows_job", lambda: True)
    monkeypatch.setattr(visual.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(snapshot, "_lock_read", fake_lock)
    with pytest.raises(visual.PreparationError, match="locked_snapshot_hash_mismatch"):
        snapshot.__enter__()
    assert not root.exists() and not snapshot.handles
    assert before == {did: Path(doc["pdf_path"]).read_bytes()
                      for did, doc in synthetic_inputs["documents"].items()}


def test_real_renderer_uses_locked_snapshot_for_native_source_identity(
    visual, synthetic_inputs, tmp_path, monkeypatch,
):
    pdf = Path(synthetic_inputs["documents"]["lec04"]["pdf_path"])
    snapshot = visual._LockedPublicSources({}, tmp_path / "snapshot")
    snapshot.paths = {"lec04": tmp_path / "snapshot" / "lec04.pdf"}
    calls = []
    monkeypatch.setattr(visual, "_inside_windows_job", lambda: True)

    def render(executable, source, page, destination, **kwargs):
        calls.append((executable, source, page, destination, kwargs))
        return _png()

    monkeypatch.setattr(visual, "render_page", render)
    bounded = visual._BoundedPopplerRenderer(tmp_path / "poppler.exe", "c" * 64, snapshot)
    assert bounded(pdf, 7, tmp_path / "image.png", 30) == (_png(), "c" * 64)
    assert calls[0][1] == snapshot.paths["lec04"] and calls[0][1] != pdf
    assert calls[0][4] == {"timeout": 30, "snapshot": snapshot}


def test_total_preparation_deadline_stops_before_next_image_and_disallows_resume(
    visual, synthetic_inputs, tmp_path, monkeypatch,
):
    clock = [0.0]
    calls = []
    destination = tmp_path / "deadline-output"
    destination.mkdir()
    monkeypatch.setattr(visual.time, "monotonic", lambda: clock[0])

    def advance_past_deadline(*args):
        calls.append(args)
        clock[0] = 601.0
        return _png(), "c" * 64

    with pytest.raises(visual.PreparationError, match="preparation_timeout"):
        _prepare(visual, synthetic_inputs, advance_past_deadline, tmp_path, destination=destination)
    assert len(calls) == 1 and calls[0][3] == 30
    assert not (destination / "manifest.json").exists()
    assert json.loads((destination / "failure-receipt.json").read_bytes())["resume_permitted"] is False


class _FakeApi:
    """Callable ctypes API double supporting argtypes/restype assignment."""
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *args):
        return self.callback(*args)


def _windows_kernel(monkeypatch, visual, *, wait_status=0, assigned=True,
                    query_flags=0x2210, query_affinity=15,
                    query_memory=2_147_483_648, in_job=True):
    import ctypes

    events = []

    def affinity(process, allowed, system):
        allowed._obj.value = 255
        system._obj.value = 65535
        return 1

    def set_limits(job, kind, limits, length):
        value = limits._obj
        events.append(("limits", kind, value.basic.flags,
                       value.basic.affinity, value.job_memory))
        return 1

    def create(executable, command, sa, ta, inherited, flags, environment, cwd, startup, process):
        info = process._obj
        info.process, info.thread, info.pid, info.tid = 201, 202, 203, 204
        env_block = ctypes.wstring_at(environment, len(environment))
        events.append(("create", inherited, flags, env_block, command.value))
        return 1

    def assign(job, process):
        events.append(("assign", job, process))
        return int(assigned)

    def resume(thread):
        events.append(("resume", thread))
        return 0

    def wait(process, timeout):
        events.append(("wait", process, timeout))
        return wait_status

    def exit_code(process, code):
        code._obj.value = 0
        return 1

    def is_in_job(process, job, flag):
        flag._obj.value = int(in_job)
        return 1

    def query(job, kind, limits, length, returned):
        limits._obj.basic.flags = query_flags
        limits._obj.basic.affinity = query_affinity
        limits._obj.job_memory = query_memory
        return 1

    callbacks = {
        "GetCurrentProcess": lambda: 101,
        "CreateJobObjectW": lambda *args: 102,
        "GetLastError": lambda: 0,
        "OpenJobObjectW": lambda *args: events.append(("open_job", *args)) or 102,
        "GetProcessAffinityMask": affinity,
        "SetInformationJobObject": set_limits,
        "CreateProcessW": create,
        "AssignProcessToJobObject": assign,
        "ResumeThread": resume,
        "WaitForSingleObject": wait,
        "GetExitCodeProcess": exit_code,
        "IsProcessInJob": is_in_job,
        "QueryInformationJobObject": query,
        "TerminateJobObject": lambda *args: events.append(("terminate_job", *args)) or 1,
        "TerminateProcess": lambda *args: events.append(("terminate_process", *args)) or 1,
        "CloseHandle": lambda *args: events.append(("close", *args)) or 1,
    }
    kernel = SimpleNamespace(**{name: _FakeApi(callback) for name, callback in callbacks.items()})
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: kernel, raising=False)
    monkeypatch.setattr(visual, "os", SimpleNamespace(name="nt", environ={
        "SystemRoot": "C:/Windows", "GEMINI_API_KEY": "synthetic-secret-must-not-inherit"}))
    return events


def test_supervisor_applies_real_memory_affinity_before_resuming_worker_and_bounds_whole_stage(
    visual, tmp_path, monkeypatch,
):
    events = _windows_kernel(monkeypatch, visual)
    visual.supervise(tmp_path)
    labels = [event[0] for event in events]
    limits = next(event for event in events if event[0] == "limits")
    assert limits == ("limits", 9, 0x2210, 15, 2_147_483_648)
    assert labels.index("limits") < labels.index("create") < labels.index("assign") < labels.index("resume")
    create = next(event for event in events if event[0] == "create")
    assert create[1] is False
    assert create[2] & 0x4 and create[2] & 0x400 and create[2] & 0x08000000
    assert not create[2] & 0x01000000
    env = dict(item.split("=", 1) for item in create[3].split("\0") if "=" in item)
    assert set(env) == {"SystemRoot", "PATH", "PYTHONUTF8", "TEMP", "TMP"}
    assert "GEMINI_API_KEY" not in env
    assert "--worker" in create[4]
    assert next(event for event in events if event[0] == "wait")[2] == 600_000
    assert ("close", 102) in events  # KILL_ON_JOB_CLOSE covers remaining descendants.


@pytest.mark.parametrize("failure", ["timeout", "assignment"])
def test_supervisor_kills_tree_on_timeout_or_failed_assignment(
    visual, tmp_path, monkeypatch, failure,
):
    events = _windows_kernel(monkeypatch, visual, wait_status=0x102 if failure == "timeout" else 0,
                             assigned=failure != "assignment")
    with pytest.raises(visual.PreparationError,
                       match="preparation_timeout" if failure == "timeout" else "resource_assignment_unavailable"):
        visual.supervise(tmp_path)
    assert ("close", 102) in events
    assert ("terminate_process", 201, 2) in events
    if failure == "timeout":
        assert ("terminate_job", 102, 2) in events
    else:
        assert not any(event[0] == "resume" for event in events)


@pytest.mark.parametrize("changes,accepted", [
    ({}, True),
    ({"in_job": False}, False),
    ({"query_flags": 0x2010}, False),  # No aggregate memory limit.
    ({"query_flags": 0x0210}, False),  # No process-tree close guard.
    ({"query_flags": 0x2A10}, False),  # Breakaway permitted.
    ({"query_affinity": 31}, False),
    ({"query_affinity": 0}, False),
    ({"query_memory": 2_147_483_649}, False),
    ({"query_memory": 0}, False),
])
def test_worker_queries_job_limits_instead_of_accepting_job_membership_or_receipt(
    visual, monkeypatch, changes, accepted,
):
    _windows_kernel(monkeypatch, visual, **changes)
    assert visual._inside_windows_job() is accepted


def test_worker_queries_named_resource_ancestor_instead_of_venv_inner_job(
    visual, monkeypatch,
):
    events = _windows_kernel(monkeypatch, visual)
    name = "cardchemy-visual-" + "a" * 32
    monkeypatch.setattr(visual, "RESOURCE_JOB_NAME", name)
    assert visual._inside_windows_job() is True
    assert ("open_job", 4, False, name) in events
    assert ("close", 102) in events


def test_generated_resource_job_identity_is_accepted_by_worker(visual):
    name = visual.RESOURCE_JOB_PREFIX + visual.uuid.uuid4().hex
    assert visual.validate_resource_job_name(name) == name
    for malformed in (None, "", name[:-1], name + "a", name.upper(), "outside-" + "a" * 32):
        with pytest.raises(visual.PreparationError, match="resource_job_identity_required"):
            visual.validate_resource_job_name(malformed)
