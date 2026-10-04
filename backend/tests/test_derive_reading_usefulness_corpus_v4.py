"""Offline contracts for the pinned v3-to-v4 public corpus derivation."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import acquire_reading_usefulness_corpus as acquired
import derive_reading_usefulness_corpus_v4 as derived


def _write(path: Path, value: dict[str, object]) -> str:
    raw = derived.canonical_bytes(value)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, dict[str, bytes]]:
    monkeypatch.setattr(derived, "gettempdir", lambda: str(tmp_path))
    source = tmp_path / derived.V3_DIR
    source.mkdir()
    prereg = acquired.preregistration()
    prereg_sha = _write(source / "preregistration.json", prereg)
    monkeypatch.setattr(derived, "V3_PREREGISTRATION_SHA256", prereg_sha)

    pdfs: dict[str, bytes] = {}
    rows = []
    for split, numbers in derived.V3_SPLITS.items():
        for number in numbers:
            name = f"lec{number:02d}.pdf"
            raw = b"%PDF-1.7\n" + f"public synthetic lecture {number}\n".encode()
            (source / name).write_bytes(raw)
            pdfs[name] = raw
            rows.append({
                "split": split, "url": derived._pdf_url(number), "path": name,
                "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                "license_url": acquired.LICENSE_URL,
                "pages": 4, "alphanumeric_text_chars": 1500,
                "pages_with_at_least_40_alphanumeric_chars": 4,
                "first_page_license": "CC BY 4.0",
            })
    manifest = {
        "schema": "cardchemy_public_reading_corpus_manifest_v1",
        "corpus_id": derived.V3_CORPUS_ID,
        "preregistration_sha256": prereg_sha,
        "index_url": acquired.INDEX_URL,
        "license_url": acquired.LICENSE_URL,
        "documents": rows, "requests_including_redirects": 15,
        "received_bytes": sum(len(raw) for raw in pdfs.values()),
        "elapsed_seconds": 2, "all_pdf_first_pages_cc_by_4": True,
        "labels_written": False,
    }
    manifest_sha = _write(source / "manifest.json", manifest)
    monkeypatch.setattr(derived, "V3_MANIFEST_SHA256", manifest_sha)
    plan_sha = _write(source / "empty_fixture_plan.json",
                      acquired.empty_fixture_plan(manifest_sha))
    monkeypatch.setattr(derived, "V3_EMPTY_PLAN_SHA256", plan_sha)
    return source, tmp_path / derived.V4_DIR, pdfs


def test_derives_same_fourteen_pdf_bytes_into_new_v4_bundle(parent):
    source, output, original_pdfs = parent
    before = {path.name: path.read_bytes() for path in source.iterdir()}

    result = derived.derive(source, output)

    assert result["status"] == "derived_unlabeled_no_scoring"
    assert result["documents"] == 14
    assert result["pdf_bytes"] == sum(map(len, original_pdfs.values()))
    assert {path.name: path.read_bytes() for path in source.iterdir()} == before
    assert {path.name: path.read_bytes() for path in output.glob("*.pdf")} == original_pdfs
    assert set(output.glob("*.pdf")) == {output / name for name in original_pdfs}

    prereg = json.loads((output / "preregistration.json").read_text())
    manifest = json.loads((output / "manifest.json").read_text())
    plan = json.loads((output / "empty_fixture_plan.json").read_text())
    receipt = json.loads((output / "derivation_receipt.json").read_text())
    assert prereg["corpus_id"] == manifest["corpus_id"] == plan["corpus_id"] == derived.V4_CORPUS_ID
    assert {split: [url.rsplit("/", 1)[-1] for url in urls]
            for split, urls in prereg["splits"].items()} == {
                split: [f"lec{n:02d}.pdf" for n in numbers]
                for split, numbers in derived.V4_SPLITS.items()}
    assert {split: [row["path"] for row in manifest["documents"] if row["split"] == split]
            for split in derived.V4_SPLITS} == {
                split: [f"lec{n:02d}.pdf" for n in numbers]
                for split, numbers in derived.V4_SPLITS.items()}
    assert manifest["requests_including_redirects"] == manifest["received_bytes"] == 0
    assert manifest["labels_written"] is False and plan["groups"] == []
    assert receipt["provider_calls"] == receipt["model_scores"] == 0
    assert receipt["derived_from"]["manifest_sha256"] == derived.V3_MANIFEST_SHA256
    assert receipt["manifest_sha256"] == result["manifest_sha256"]
    assert plan["manifest_sha256"] == result["manifest_sha256"]
    assert receipt["empty_fixture_plan_sha256"] == result["empty_fixture_plan_sha256"]


def test_tampered_parent_pdf_refuses_before_output(parent):
    source, output, _ = parent
    target = source / "lec25.pdf"
    target.write_bytes(target.read_bytes() + b"corrupted")

    with pytest.raises(derived.DerivationError, match="parent_pdf_hash_or_size_mismatch"):
        derived.derive(source, output)
    assert not output.exists()


def test_parent_metadata_pin_refuses_before_output(parent):
    source, output, _ = parent
    path = source / "manifest.json"
    path.write_bytes(path.read_bytes() + b" ")

    with pytest.raises(derived.DerivationError, match="parent_metadata_hash_mismatch"):
        derived.derive(source, output)
    assert not output.exists()


def test_existing_output_is_exclusive_and_unchanged(parent):
    source, output, _ = parent
    output.mkdir()
    sentinel = output / "preexisting.txt"
    sentinel.write_text("preserve", encoding="utf-8")

    with pytest.raises(derived.DerivationError, match="fresh_v4_os_temp_root_required"):
        derived.derive(source, output)
    assert sentinel.read_text(encoding="utf-8") == "preserve"


def test_rejects_output_outside_os_temp(parent, tmp_path):
    source, _, _ = parent
    nested = tmp_path / "nested"
    nested.mkdir()
    output = nested / derived.V4_DIR

    with pytest.raises(derived.DerivationError, match="fresh_v4_os_temp_root_required"):
        derived.derive(source, output)
    assert not output.exists()


def test_rejects_roster_that_uses_reserved_release_pdf(parent, monkeypatch):
    source, output, _ = parent
    altered = copy.deepcopy(derived.V4_SPLITS)
    altered["heldout"] = (17, 31, 32, 38)
    monkeypatch.setattr(derived, "V4_SPLITS", altered)

    with pytest.raises(derived.DerivationError, match="v4_roster_invalid"):
        derived.derive(source, output)
    assert not output.exists()


def test_rejects_roster_with_wrong_split_counts(parent, monkeypatch):
    source, output, _ = parent
    altered = copy.deepcopy(derived.V4_SPLITS)
    altered["train"] = (*altered["train"], 22)
    altered["calibration"] = (25, 26, 27)
    monkeypatch.setattr(derived, "V4_SPLITS", altered)

    with pytest.raises(derived.DerivationError, match="v4_roster_invalid"):
        derived.derive(source, output)
    assert not output.exists()


def test_preflight_cli_does_not_write(parent, capsys):
    _, output, _ = parent
    assert derived.main(["--output", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "local_derivation_preflight_no_write"
    assert not output.exists()
