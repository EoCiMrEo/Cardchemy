"""Validate two independent public PDF reviews without scoring a model.

Only candidate IDs and aggregate counts leave the private OS-Temp packets.
Disagreements and uncertain judgments remain unresolved until a separate
source-page adjudication. This tool never promotes author labels to truth.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from tempfile import gettempdir


class ReviewError(ValueError):
    pass


def _read(path: Path, expected_sha256: str | None = None) -> tuple[dict, str]:
    temp = Path(gettempdir()).resolve()
    if (path.resolve().parent != temp or path.is_symlink() or not path.is_file()
        or not 0 < path.stat().st_size <= 2 * 1024 * 1024):
        raise ReviewError("temp_packet_invalid")
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and sha != expected_sha256:
        raise ReviewError("packet_identity_invalid")
    try:
        data = json.loads(raw)
    except (UnicodeError, ValueError):
        raise ReviewError("packet_json_invalid") from None
    if not isinstance(data, dict):
        raise ReviewError("packet_json_invalid")
    return data, sha


def _expected(blind: dict) -> dict[str, tuple[str, str, int]]:
    if (blind.get("schema") not in {
            "cardchemy_reading_usefulness_blind_review_v1",
            "cardchemy_reading_usefulness_blind_review_v2"}
        or not isinstance(blind.get("groups"), list)
        or len(blind["groups"]) != 96):
        raise ReviewError("blind_packet_invalid")
    result = {}
    for group in blind["groups"]:
        if not isinstance(group, dict) or not isinstance(group.get("candidates"), list):
            raise ReviewError("blind_packet_invalid")
        candidates = group["candidates"]
        if len(candidates) != 4:
            raise ReviewError("blind_packet_invalid")
        for candidate in candidates:
            try:
                key = candidate["id"]
                value = (group["id"], group["source_document_path_author_aid"],
                         candidate["source_offset"]["page_number"])
            except (KeyError, TypeError):
                raise ReviewError("blind_packet_invalid") from None
            if (not isinstance(key, str) or key in result
                or not isinstance(value[0], str) or not isinstance(value[1], str)
                or type(value[2]) is not int):
                raise ReviewError("blind_packet_invalid")
            result[key] = value
    if len(result) != 384:
        raise ReviewError("blind_packet_invalid")
    return result


def _review(review: dict, packet_sha: str,
            expected: dict[str, tuple[str, str, int]]) -> tuple[str, dict[str, dict]]:
    reviewer = review.get("reviewer_id")
    rows = review.get("judgments")
    if (not isinstance(reviewer, str) or not reviewer.strip()
        or review.get("packet_sha256") != packet_sha
        or review.get("reviewed_group_count", 96) != 96
        or review.get("reviewed_candidate_count", 384) != 384
        or not isinstance(rows, list) or len(rows) != 384):
        raise ReviewError("review_incomplete_or_wrong_packet")
    by_id = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ReviewError("review_row_invalid")
        key = row.get("id")
        if not isinstance(key, str) or key not in expected or key in by_id:
            raise ReviewError("review_row_invalid")
        identity = (row.get("group_id"), row.get("source_pdf"), row.get("page_number"))
        page, cue, uncertain = (row.get(name) for name in
                                ("original_page_useful", "exact_visible_cue_useful", "uncertain"))
        if (identity != expected[key] or type(page) is not bool or type(cue) is not bool
            or type(uncertain) is not bool or (cue and not page)
            or not isinstance(row.get("reason"), str) or not row["reason"].strip()):
            raise ReviewError("review_row_invalid")
        by_id[key] = row
    return reviewer, by_id


def compare(blind_path: Path, blind_sha: str,
            first_path: Path, second_path: Path) -> dict[str, object]:
    blind, actual_sha = _read(blind_path, blind_sha)
    expected = _expected(blind)
    first, first_sha = _read(first_path)
    second, second_sha = _read(second_path)
    first_id, a = _review(first, actual_sha, expected)
    second_id, b = _review(second, actual_sha, expected)
    if first_id == second_id or first_sha == second_sha:
        raise ReviewError("review_independence_invalid")
    counts = Counter()
    unresolved = []
    for key in sorted(expected):
        left, right = a[key], b[key]
        left_label = (left["original_page_useful"], left["exact_visible_cue_useful"])
        right_label = (right["original_page_useful"], right["exact_visible_cue_useful"])
        uncertain = left["uncertain"] or right["uncertain"]
        if uncertain:
            counts["uncertain_candidates"] += 1
        if left_label != right_label:
            counts["disagreed_candidates"] += 1
        if uncertain or left_label != right_label:
            unresolved.append({"candidate_id": key,
                               "uncertain": uncertain,
                               "page_disagreement": left_label[0] != right_label[0],
                               "cue_disagreement": left_label[1] != right_label[1]})
        else:
            counts["agreed_candidates"] += 1
    return {"status": "independent_reviews_compared_no_model_scoring",
            "blind_packet_sha256": actual_sha,
            "review_sha256": sorted((first_sha, second_sha)),
            "reviewer_ids": sorted((first_id, second_id)),
            "candidate_count": len(expected), **dict(counts),
            "unresolved": unresolved,
            "ready_for_adjudication": bool(unresolved),
            "fully_agreed_without_uncertainty": not unresolved}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", type=Path, required=True)
    parser.add_argument("--blind-sha256", required=True)
    parser.add_argument("--review-a", type=Path, required=True)
    parser.add_argument("--review-b", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = compare(args.blind, args.blind_sha256, args.review_a, args.review_b)
    except ReviewError as exc:
        raise SystemExit(f"Independent review comparison refused: {exc}") from None
    except OSError:
        raise SystemExit("Independent review comparison refused: file_unavailable") from None
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
