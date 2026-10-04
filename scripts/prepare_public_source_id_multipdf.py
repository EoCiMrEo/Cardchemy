"""Prepare unlabelled cross-document public PDF source-judge review slates.

This does not call a model or score a split. The existing independently
reviewed public groups supply questions and three exact candidate pages; one
reviewed insufficient page is replaced with a lexical-near page from another
PDF in the same split. The replacement requires an independent page-and-cue
review before this packet can become an evaluation fixture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from tempfile import gettempdir

from pypdf import PdfReader

from validate_reading_usefulness_fixture import validate as validate_source_fixture

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
from app.ai.source_navigation import navigation_query_v4, navigation_terms  # noqa: E402
from app.ai.source_judgment import build_source_id_request, canonical_bytes  # noqa: E402


SOURCE_FIXTURE_SHA256 = "2180d4124417d5f4c9730134fa4d656957d3d6d92d4848f2f41d96927d8020d8"
SCHEMA = "cardchemy_public_source_id_multipdf_review_v1"
MAX_PAGE_CHARS = 1_200
MAX_CUE_CHARS = 480
MIN_PAGE_ALNUM = 80
WORD = re.compile(r"[A-Za-z0-9]")


class PacketError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise PacketError(code)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, limit: int) -> dict:
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= limit,
            "input_file_invalid")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(type(value) is dict, "input_object_invalid")
    return value


def _exact_cue(page: str, terms: frozenset[str]) -> tuple[int, int]:
    if len(page) <= MAX_CUE_CHARS:
        return 0, len(page)
    # Compare bounded exact slices at each question-term occurrence; every
    # resulting cue is still a contiguous slice of the canonical page.
    choices: list[tuple[int, int, int]] = []
    lowered = page.casefold()
    for term in sorted(terms):
        start_at = 0
        while (at := lowered.find(term, start_at)) >= 0:
            start = max(0, min(at - 80, len(page) - MAX_CUE_CHARS))
            end = start + MAX_CUE_CHARS
            choices.append((len(navigation_terms(page[start:end]) & terms), start, end))
            start_at = at + len(term)
            if len(choices) >= 100:
                break
        if len(choices) >= 100:
            break
    if not choices:
        return 0, MAX_CUE_CHARS
    _score, start, end = max(choices, key=lambda row: (row[0], -row[1]))
    return start, end


def _pages(corpus: Path, fixture: dict) -> tuple[dict[str, dict], dict[str, list[str]]]:
    manifest = _read_json(corpus / "manifest.json", 64_000)
    documents = manifest.get("documents")
    require(type(documents) is list and len(documents) == 14, "manifest_invalid")
    metadata: dict[str, dict] = {}
    pages: dict[str, list[str]] = {}
    for doc in documents:
        sha, filename, split = doc["sha256"], doc["path"], doc["split"]
        require(type(sha) is str and len(sha) == 64 and sha not in metadata and
                type(filename) is str and re.fullmatch(r"lec\d{2}[.]pdf", filename)
                and split in {"train", "calibration", "heldout"}, "document_invalid")
        file = corpus / filename
        require(file.is_file() and not file.is_symlink() and
                digest(file.read_bytes()) == sha, "document_hash_invalid")
        metadata[sha] = {"filename": filename, "split": split}
        pages[sha] = [(page.extract_text() or "") for page in PdfReader(file, strict=False).pages]
    require(all(group["source_document_sha256"] in metadata and
                metadata[group["source_document_sha256"]]["split"] == group["split"]
                for group in fixture["groups"]), "source_split_invalid")
    return metadata, pages


def _original_rows(group: dict, pages: dict[str, list[str]]) -> list[dict]:
    sha = group["source_document_sha256"]
    rows: list[dict] = []
    for cue, offset, page_good, cue_good in zip(
        group["four_exact_candidate_windows"],
        group["page_number_and_text_offsets_for_each_window"],
        group["original_page_usefulness_per_window"],
        group["exact_cue_usefulness_per_window"], strict=True,
    ):
        number = offset["page_number"]
        require(1 <= number <= len(pages[sha]), "original_page_invalid")
        page = pages[sha][number - 1]
        require(digest(page.encode("utf-8")) == offset["page_text_sha256"] and
                page[offset["start"]:offset["end"]] == cue and
                0 < len(page) <= MAX_PAGE_CHARS, "original_span_invalid")
        rows.append({"document_sha256": sha, "page": number,
                     "page_text": page, "cue": cue,
                     "cue_start": offset["start"], "cue_end": offset["end"],
                     "reviewed_page_useful": page_good,
                     "reviewed_cue_useful": cue_good})
    require(len(rows) == 4, "original_count_invalid")
    return rows


def _external_row(group: dict, metadata: dict[str, dict],
                  pages: dict[str, list[str]]) -> dict:
    source_sha = group["source_document_sha256"]
    previous = group["prior_question_context_if_followup"]
    history = (("user", previous),) if previous else ()
    local = navigation_query_v4(group["question"], history) or group["question"]
    terms = navigation_terms(local)
    choices: list[tuple[int, str, int, str]] = []
    for sha, doc in metadata.items():
        if sha == source_sha or doc["split"] != group["split"]:
            continue
        for number, page in enumerate(pages[sha], 1):
            if number == 1 or not 80 <= len(page) <= MAX_PAGE_CHARS or sum(
                WORD.fullmatch(character) is not None for character in page
            ) < MIN_PAGE_ALNUM:
                continue
            score = len(navigation_terms(page) & terms)
            choices.append((score, sha, number, page))
    require(bool(choices), "external_page_unavailable")
    score, sha, number, page = sorted(choices, key=lambda row: (-row[0], row[1], row[2]))[0]
    start, end = _exact_cue(page, terms)
    return {"document_sha256": sha, "page": number, "page_text": page,
            "cue": page[start:end], "cue_start": start, "cue_end": end,
            "lexical_overlap": score, "reviewed_page_useful": None,
            "reviewed_cue_useful": None}


def build(corpus: Path, fixture_path: Path) -> tuple[dict, dict]:
    require(digest(fixture_path.read_bytes()) == SOURCE_FIXTURE_SHA256,
            "source_fixture_hash_invalid")
    validate_source_fixture(corpus, fixture_path)
    fixture = _read_json(fixture_path, 4 * 1024 * 1024)
    metadata, pages = _pages(corpus, fixture)
    review_groups = []
    sealed_groups = []
    for group in fixture["groups"]:
        if group["split"] not in {"calibration", "heldout"}:
            continue
        rows = _original_rows(group, pages)
        insufficient = [index for index, row in enumerate(rows)
                        if not (row["reviewed_page_useful"] and row["reviewed_cue_useful"])]
        require(bool(insufficient), "no_replacement_slot")
        rows[insufficient[-1]] = _external_row(group, metadata, pages)
        # A deterministic shuffle avoids advertising which page is the new
        # external candidate to a judge. Reviewer labels remain sealed.
        rows.sort(key=lambda row: digest((group["id"] + row["document_sha256"] +
                                          str(row["page"])).encode("utf-8")))
        candidates = []
        labels = []
        for index, row in enumerate(rows, 1):
            candidate_id = f"S{index:02d}"
            candidate = {"id": candidate_id, "page": row["page"],
                         "page_text": row["page_text"], "cue": row["cue"]}
            candidates.append(candidate)
            labels.append({"id": candidate_id, "document_sha256": row["document_sha256"],
                           "page": row["page"], "page_useful": row["reviewed_page_useful"],
                           "cue_useful": row["reviewed_cue_useful"]})
        build_source_id_request(group["question"], candidates)
        review_groups.append({"group_id": group["id"], "split": group["split"],
                              "question_form": group["question_form"],
                              "question": group["question"],
                              "prior_for_local_context_only": group["prior_question_context_if_followup"],
                              "candidates": [{**candidate,
                                              "document_sha256": labels[index]["document_sha256"],
                                              "filename": metadata[labels[index]["document_sha256"]]["filename"]}
                                             for index, candidate in enumerate(candidates)]})
        sealed_groups.append({"group_id": group["id"], "split": group["split"],
                              "labels": labels})
    require(len(review_groups) == 96 and len(sealed_groups) == 96,
            "review_group_count_invalid")
    return ({"schema": SCHEMA, "status": "unreviewed_no_provider_call",
             "source_fixture_sha256": SOURCE_FIXTURE_SHA256, "groups": review_groups},
            {"schema": SCHEMA + "_sealed_existing_labels", "groups": sealed_groups})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        temp = Path(gettempdir()).resolve()
        require(args.output.is_absolute() and temp in args.output.resolve().parents
                and args.output.parent.is_dir() and not args.output.exists(),
                "os_temp_output_required")
        review, sealed = build(args.corpus, args.fixture)
        new_only = []
        for group, old in zip(review["groups"], sealed["groups"], strict=True):
            require(group["group_id"] == old["group_id"], "review_identity_invalid")
            candidates = [candidate for candidate, label in zip(
                group["candidates"], old["labels"], strict=True,
            ) if label["page_useful"] is None and label["cue_useful"] is None]
            require(len(candidates) == 1, "new_review_candidate_invalid")
            new_only.append({"group_id": group["group_id"],
                             "split": group["split"],
                             "question_form": group["question_form"],
                             "question": group["question"],
                             "prior_for_local_context_only": group["prior_for_local_context_only"],
                             "candidate": candidates[0]})
        args.output.mkdir(parents=False, exist_ok=False)
        hashes = {}
        for name, value in (("blind-review-packet.json", review),
                            ("sealed-existing-labels.json", sealed),
                            ("new-page-review.json", {"schema": SCHEMA + "_new_page_review",
                                                      "groups": new_only})):
            raw = canonical_bytes(value)
            with (args.output / name).open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            hashes[name] = digest(raw)
        print(json.dumps({"status": "unreviewed_no_provider_call",
                          "groups": len(review["groups"]), "sha256": hashes},
                         sort_keys=True))
        return 0
    except (PacketError, ValueError, OSError, KeyError, TypeError) as exc:
        code = str(exc) if isinstance(exc, PacketError) else type(exc).__name__
        print(json.dumps({"status": "packet_rejected", "reason": code},
                         sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
