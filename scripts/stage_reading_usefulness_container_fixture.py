"""Stage a validated public reading-usefulness fixture for a Linux container.

The input remains in OS Temp. The destination must be a new, isolated OS-Temp
directory; only the fixture and evidence files named by review_evidence are
written. Bind destination/evidence read-only at
/tmp/cardchemy-reading-usefulness-evidence when validating inside Linux.
This script does not freeze inputs, start Docker, or score a model.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
from tempfile import gettempdir

import acquire_reading_usefulness_corpus as corpus
import validate_reading_usefulness_fixture as validator


CONTAINER_EVIDENCE_ROOT = PurePosixPath("/tmp/cardchemy-reading-usefulness-evidence")
OUTPUT_FIXTURE_NAME = "container_fixture.json"
BATCH_EVIDENCE_STEMS = (
    "author_draft", "blind_packet", "opaque_mapping", "review_a", "review_b",
    "adjudication",
)
ROOT_EVIDENCE_STEMS = ("semantic_leakage_audit", "rights_audit")
SAFE_BASENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}\Z")


class StageError(ValueError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise StageError(reason)


def _os_temp_path(path: Path, *, exists: bool) -> Path:
    """Refuse a broad Temp root, path traversal, symlinks and junctions."""
    require(path.is_absolute() and ".." not in path.parts, "os_temp_path_required")
    temp = Path(gettempdir()).resolve()
    resolved = path.resolve(strict=exists)
    require(temp in resolved.parents, "os_temp_path_required")
    for component in (path, *path.parents):
        if component == temp:
            break
        require(not component.is_symlink() and
                not (hasattr(component, "is_junction") and component.is_junction()),
                "symlink_or_junction")
    return resolved


def _evidence_references(fixture: dict) -> list[tuple[dict, str, str]]:
    refs = fixture["review_evidence"]
    result: list[tuple[dict, str, str]] = []
    for batch in refs["batches"]:
        for stem in BATCH_EVIDENCE_STEMS:
            result.append((batch, f"{stem}_path", f"{stem}_sha256"))
    for stem in ROOT_EVIDENCE_STEMS:
        result.append((refs, f"{stem}_path", f"{stem}_sha256"))
    return result


def stage(corpus_root: Path, fixture_path: Path, destination: Path) -> dict[str, object]:
    corpus_root = Path(corpus_root)
    fixture_path = Path(fixture_path)
    destination = Path(destination)
    _os_temp_path(corpus_root, exists=True)
    _os_temp_path(fixture_path, exists=True)
    _os_temp_path(destination, exists=False)
    require(corpus_root.is_dir() and fixture_path.is_file(), "input_missing")
    require(destination.parent.is_dir() and not destination.exists() and
            not destination.is_symlink(), "destination_must_be_new")
    require(corpus_root.resolve() not in destination.resolve().parents,
            "destination_inside_corpus")

    # Full admission uses the repository's pinned v4 corpus, source-window,
    # independent-review, rights and evidence checks before anything is copied.
    admission = validator.validate(corpus_root, fixture_path)
    original, raw = validator.read_json(fixture_path, validator.MAX_FIXTURE_BYTES)
    require(validator.digest(raw) == admission["fixture_sha256"],
            "fixture_changed_during_validation")
    staged = copy.deepcopy(original)
    original_refs = _evidence_references(original)
    staged_refs = _evidence_references(staged)
    require(len(original_refs) == len(staged_refs) == 14, "evidence_reference_count")

    evidence: dict[str, tuple[Path, bytes, str]] = {}
    basenames_by_casefold: dict[str, str] = {}
    for (source_owner, source_key, sha_key), (staged_owner, staged_key, _) in zip(
            original_refs, staged_refs, strict=True):
        source = Path(source_owner[source_key])
        _os_temp_path(source, exists=True)
        basename = source.name
        require(SAFE_BASENAME.fullmatch(basename) is not None and
                basename not in {".", ".."}, "unsafe_evidence_basename")
        folded = basename.casefold()
        require(basenames_by_casefold.get(folded, basename) == basename,
                "evidence_basename_collision")
        basenames_by_casefold[folded] = basename
        expected_sha = source_owner[sha_key]
        content = validator.file_bytes(source, validator.MAX_EVIDENCE_BYTES)
        require(validator.digest(content) == expected_sha,
                "evidence_changed_during_validation")
        if basename in evidence:
            prior_source, _, prior_sha = evidence[basename]
            require(source == prior_source and expected_sha == prior_sha,
                    "evidence_basename_collision")
        else:
            evidence[basename] = (source, content, expected_sha)
        staged_owner[staged_key] = str(CONTAINER_EVIDENCE_ROOT / basename)

    # Reversing just the path edits must recover the entire original object.
    roundtrip = copy.deepcopy(staged)
    for (source_owner, source_key, _), (roundtrip_owner, roundtrip_key, _) in zip(
            original_refs, _evidence_references(roundtrip), strict=True):
        roundtrip_owner[roundtrip_key] = source_owner[source_key]
    require(roundtrip == original, "fixture_content_changed")
    staged_raw = corpus.canonical_bytes(staged)
    require(len(staged_raw) <= validator.MAX_FIXTURE_BYTES, "fixture_size_limit")

    destination.mkdir(mode=0o700)
    evidence_dir = destination / "evidence"
    evidence_dir.mkdir(mode=0o700)
    for basename, (_, content, expected_sha) in sorted(evidence.items()):
        target = evidence_dir / basename
        with target.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        require(validator.digest(validator.file_bytes(target, validator.MAX_EVIDENCE_BYTES)) ==
                expected_sha, "staged_evidence_hash")
    output = destination / OUTPUT_FIXTURE_NAME
    with output.open("xb") as stream:
        stream.write(staged_raw)
        stream.flush()
        os.fsync(stream.fileno())
    require(validator.file_bytes(output, validator.MAX_FIXTURE_BYTES) == staged_raw,
            "staged_fixture_hash")
    return {"status": "container_fixture_staged_no_scoring",
            "source_fixture_sha256": admission["fixture_sha256"],
            "container_fixture_sha256": validator.digest(staged_raw),
            "groups_sha256": validator.digest(corpus.canonical_bytes(original["groups"])),
            "evidence_files": len(evidence),
            "fixture_name": OUTPUT_FIXTURE_NAME,
            "evidence_mount_target": str(CONTAINER_EVIDENCE_ROOT)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = stage(args.corpus, args.fixture, args.destination)
    except (StageError, validator.FixtureError, OSError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, (StageError, validator.FixtureError)) else type(exc).__name__
        print(json.dumps({"status": "container_fixture_stage_rejected_no_scoring",
                          "reason": reason}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
