"""Synthetic clarity/projection regressions without cached corpus or providers."""
import copy
import json
from pathlib import Path
import struct
import sys
import zlib

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import prepare_visual_semantic_control_v2 as projection
import prepare_visual_source_feasibility_review_v1 as old_review
import prototype_visual_page_source_judge_v1 as old_judge
import prototype_visual_page_source_judge_v2 as judge


def verdict(status="clear", label="unrelated"):
    return {"question_status": status, "pages": [
        {"id": f"S{n:02d}", "usefulness": label,
         "cue_locates": label in old_judge.QUALIFYING} for n in range(1, 5)]}


def test_clear_discovery_and_no_evidence_do_not_become_clarification():
    value = judge.parse_verdict(json.dumps(verdict()), [f"S{n:02d}" for n in range(1, 5)])
    assert value["question_status"] == "clear" and value["selected_ids"] == []
    assert value["generated_answer"] is False
    assert value["schema_version"] != old_judge.VERSION
    assert "need not contain its answer" in judge.SYSTEM
    assert "Missing evidence on the supplied pages is not question ambiguity" in judge.SYSTEM


def test_new_wire_preserves_previous_freeze_and_all_other_fields():
    before = old_judge.SYSTEM
    parts = [{"text": "Invented discovery task"}] + [
        {"inline_data": {"mime_type": "image/png", "data": "prevalidated"}} for _ in range(4)]
    ids = [f"S{n:02d}" for n in range(1, 5)]
    previous = old_judge.build_request(parts, ids)
    current = judge.build_request(parts, ids)
    assert old_judge.SYSTEM == before
    assert current["systemInstruction"] != previous["systemInstruction"]
    current["systemInstruction"] = previous["systemInstruction"]
    assert current == previous


@pytest.mark.parametrize("label", ["direct", "concrete_learning_step"])
@pytest.mark.parametrize("cue", [False, True])
def test_dangling_referent_cannot_qualify_a_page(label, cue):
    value = verdict("needs_clarification")
    value["pages"][0].update(usefulness=label, cue_locates=cue)
    with pytest.raises(old_judge.VisualVerdictError, match="clarification_qualified_page"):
        judge.parse_verdict(json.dumps(value), [f"S{n:02d}" for n in range(1, 5)])


@pytest.mark.parametrize("extra", ["answer", "explanation", "quote"])
def test_source_only_parser_rejects_free_text(extra):
    value = verdict()
    value[extra] = "forbidden"
    with pytest.raises(old_judge.VisualVerdictError, match="verdict_fields_invalid"):
        judge.parse_verdict(json.dumps(value), [f"S{n:02d}" for n in range(1, 5)])


def png():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress((b"\x00" + b"\x12\x34\x56" * 2) * 2)) + chunk(b"IEND", b""))


def sample_row(tmp_path, monkeypatch):
    root = tmp_path / "parent"
    (root / "images").mkdir(parents=True)
    monkeypatch.setattr(projection, "VISUAL_ROOT", root)
    source = root / "images" / "synthetic.png"
    source.write_bytes(png())
    return {"review_id": "N01", "question": "Invented question", "context": "Invented text",
            "cue": "Invented cue", "image_path": str(source), "image_sha256": projection.visual.digest(png()),
            "width": 2, "height": 2}


def test_projection_hides_control_roles_and_keeps_exact_image_bytes(tmp_path, monkeypatch):
    row = sample_row(tmp_path, monkeypatch)
    target = tmp_path / "owned"
    target.mkdir()
    result = projection.project([row], target, {})[0]
    assert result["review_id"] == "R001"
    assert "N01" not in json.dumps(result)
    assert "synthetic.png" not in result["image_path"]
    assert Path(result["image_path"]).read_bytes() == Path(row["image_path"]).read_bytes()
    assert set(result) == {"review_id", "question", "context", "cue", "image_path",
                           "image_sha256", "width", "height"}


@pytest.mark.parametrize("changed", ["image_sha256", "width", "height", "path"])
def test_projection_rejects_changed_or_unissued_images(tmp_path, monkeypatch, changed):
    row = sample_row(tmp_path, monkeypatch)
    if changed == "path":
        outside = tmp_path / "unissued.png"
        outside.write_bytes(png())
        row["image_path"] = str(outside)
    elif changed == "image_sha256":
        row[changed] = "a" * 64
    else:
        row[changed] += 1
    target = tmp_path / "owned"
    target.mkdir()
    with pytest.raises(projection.visual.PreparationError):
        projection.project([row], target, {})
    assert not list(target.iterdir())


def test_review_projection_rechecks_external_freeze_after_concurrent_replacement(tmp_path, monkeypatch):
    root = tmp_path / "visual"
    root.mkdir()
    original = projection.visual.canonical({"manifest_sha256": "a" * 64})
    (root / "freeze.json").write_bytes(original)
    expected = projection.visual.digest(original)
    mapping = {"pairs": [{"pair_id": f"P{n:03d}"} for n in range(1, 265)]}
    monkeypatch.setattr(old_review.visual, "AUDIT_ROOT", tmp_path / "no-real-audit")
    real_reader = old_review.visual.read_json

    def read(path, sha):
        return mapping if path.name == "complete-label-mapping.json" else real_reader(path, sha)

    monkeypatch.setattr(old_review.visual, "read_json", read)
    rows = {f"P{n:03d}": {"page_usefulness": "No", "cue_usefulness": "No"} for n in range(1, 265)}
    monkeypatch.setattr(old_review.prior, "load_sealed", lambda *args: copy.deepcopy(rows))

    def completed_loader(*args, **kwargs):
        # Even a new mutually consistent manifest cannot replace the external anchor.
        (root / "freeze.json").write_bytes(projection.visual.canonical({"manifest_sha256": "b" * 64}))

    monkeypatch.setattr(old_review.visual, "load_frozen_group", completed_loader)
    with pytest.raises(projection.visual.PreparationError, match="input_hash_mismatch"):
        old_review.prepare(root, expected)
