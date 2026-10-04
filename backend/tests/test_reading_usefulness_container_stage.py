"""Offline transport checks for the public reviewed-fixture container stage."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import acquire_reading_usefulness_corpus as corpus
import stage_reading_usefulness_container_fixture as stage
import validate_reading_usefulness_fixture as validator
from test_reading_usefulness_fixture import packet, synthetic_corpus_pins  # noqa: F401


def _save(path: Path, value: dict) -> None:
    path.write_bytes(corpus.canonical_bytes(value))


def test_stage_copies_only_hash_bound_evidence_and_rewrites_only_paths(packet, tmp_path):
    root, fixture_path, original = packet
    original_bytes = fixture_path.read_bytes()
    destination = tmp_path / "isolated-stage"

    result = stage.stage(root, fixture_path, destination)

    assert result["status"] == "container_fixture_staged_no_scoring"
    assert result["source_fixture_sha256"] == hashlib.sha256(original_bytes).hexdigest()
    assert result["evidence_files"] == 14
    assert result["evidence_mount_target"] == "/tmp/cardchemy-reading-usefulness-evidence"
    assert fixture_path.read_bytes() == original_bytes
    output = destination / "container_fixture.json"
    raw = output.read_bytes()
    staged = json.loads(raw)
    assert raw == corpus.canonical_bytes(staged)
    assert result["container_fixture_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["groups_sha256"] == hashlib.sha256(
        corpus.canonical_bytes(original["groups"])).hexdigest()
    restored = copy.deepcopy(staged)
    expected_names = set()
    for (source_owner, source_key, sha_key), (staged_owner, staged_key, _) in zip(
            stage._evidence_references(original), stage._evidence_references(restored), strict=True):
        source = Path(source_owner[source_key])
        expected_names.add(source.name)
        assert staged_owner[staged_key] == str(stage.CONTAINER_EVIDENCE_ROOT / source.name)
        target = destination / "evidence" / source.name
        assert target.read_bytes() == source.read_bytes()
        assert hashlib.sha256(target.read_bytes()).hexdigest() == source_owner[sha_key]
        staged_owner[staged_key] = source_owner[source_key]
    assert restored == original
    assert {path.name for path in (destination / "evidence").iterdir()} == expected_names
    assert {path.name for path in destination.iterdir()} == {"evidence", "container_fixture.json"}


def test_stage_rejects_tampered_evidence_before_writing(packet, tmp_path):
    root, _, original = packet
    changed = copy.deepcopy(original)
    tampered = tmp_path / "tampered.json"
    tampered.write_bytes(b"{}\n")
    changed["review_evidence"]["semantic_leakage_audit_path"] = str(tampered)
    fixture = tmp_path / "tampered-fixture.json"
    _save(fixture, changed)
    destination = tmp_path / "should-not-exist"

    with pytest.raises(validator.FixtureError, match="evidence_hash"):
        stage.stage(root, fixture, destination)
    assert not destination.exists()


def test_stage_rejects_basename_collision_after_full_validation(packet, tmp_path):
    root, _, original = packet
    changed = copy.deepcopy(original)
    train, evaluation = changed["review_evidence"]["batches"]
    duplicate_dir = tmp_path / "different-source"
    duplicate_dir.mkdir()
    duplicate = duplicate_dir / Path(train["review_a_path"]).name
    duplicate.write_bytes(Path(evaluation["review_a_path"]).read_bytes())
    evaluation["review_a_path"] = str(duplicate)
    fixture = tmp_path / "same-basename-fixture.json"
    _save(fixture, changed)
    destination = tmp_path / "should-not-exist"

    # The review is still valid evidence; its destination name is ambiguous.
    assert validator.validate(root, fixture)["groups"] == 192
    with pytest.raises(stage.StageError, match="evidence_basename_collision"):
        stage.stage(root, fixture, destination)
    assert not destination.exists()


def test_stage_refuses_existing_or_non_temp_destination(packet, tmp_path):
    root, fixture, _ = packet
    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "preserve.txt"
    sentinel.write_text("preserve", encoding="utf-8")

    with pytest.raises(stage.StageError, match="destination_must_be_new"):
        stage.stage(root, fixture, existing)
    assert sentinel.read_text(encoding="utf-8") == "preserve"
    with pytest.raises(stage.StageError, match="os_temp_path_required"):
        stage.stage(root, fixture, Path(__file__).resolve().parent / "non-temp-stage")


def test_stage_refuses_symlinked_fixture(packet, tmp_path, monkeypatch):
    root, fixture, _ = packet
    link = tmp_path / "fixture-link.json"
    try:
        link.symlink_to(fixture)
    except (OSError, NotImplementedError):
        # Windows runners often lack symlink privileges. Exercise the same
        # explicit guard against an existing fixture in that environment.
        original = Path.is_symlink
        monkeypatch.setattr(Path, "is_symlink", lambda path:
                            path == fixture or original(path))
        link = fixture
    destination = tmp_path / "should-not-exist"

    with pytest.raises(stage.StageError, match="symlink_or_junction"):
        stage.stage(root, link, destination)
    assert not destination.exists()


def test_cli_reports_hashes_without_source_paths(packet, tmp_path, capsys):
    root, fixture, _ = packet
    destination = tmp_path / "cli-stage"

    assert stage.main(["--corpus", str(root), "--fixture", str(fixture),
                       "--destination", str(destination)]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["fixture_name"] == "container_fixture.json"
    assert result["evidence_files"] == 14
    assert str(root) not in json.dumps(result)
    assert str(fixture) not in json.dumps(result)
    assert (destination / result["fixture_name"]).is_file()
