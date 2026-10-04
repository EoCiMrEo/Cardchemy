"""Project public author drafts into blinded, OS-Temp-only review packets.

The review packet omits author-proposed labels, useful-count-bearing IDs and
source order. A separate OS-Temp mapping is needed only after independent
review. Neither output is itself a scoring fixture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import secrets
from tempfile import gettempdir


GROUP_KEYS = (
    "id", "split", "relation_family", "question_form", "question",
    "prior_question_context_if_followup", "source_document_sha256",
)
AUTHOR_STATUSES = frozenset({
    "author_only_pending_independent_blind_review_and_adjudication_no_model_score",
    "AUTHOR DRAFT ONLY; provisional labels; no independent reviews, rights review, adjudication, freeze, or model score",
})


def project(draft: Path, output: Path, mapping_output: Path,
            expected_sha256: str) -> dict[str, object]:
    temp = Path(gettempdir()).resolve()
    if (draft.resolve().parent != temp or output.resolve().parent != temp
        or mapping_output.resolve().parent != temp or output == mapping_output
        or not draft.is_file() or draft.is_symlink() or output.exists()
        or output.is_symlink() or mapping_output.exists() or mapping_output.is_symlink()
        or draft.stat().st_size > 4 * 1024 * 1024):
        raise ValueError("temp_input_or_output_invalid")
    raw = draft.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("author_draft_identity_invalid")
    source = json.loads(raw)
    if (not isinstance(source, dict) or not isinstance(source.get("groups"), list)
        or source.get("status") not in AUTHOR_STATUSES):
        raise ValueError("author_draft_invalid")
    groups = []
    mapping = []
    ids: set[str] = set()
    for group in source["groups"]:
        if not isinstance(group, dict) or any(key not in group for key in GROUP_KEYS):
            raise ValueError("author_group_invalid")
        windows = group.get("four_exact_candidate_windows")
        offsets = group.get("page_number_and_text_offsets_for_each_window")
        if (not isinstance(windows, list) or not isinstance(offsets, list)
            or len(windows) != 4 or len(offsets) != 4
            or not isinstance(group["id"], str) or group["id"] in ids):
            raise ValueError("author_group_invalid")
        ids.add(group["id"])
        opaque_group_id = "g_" + secrets.token_hex(12)
        projected = {key: group[key] for key in (
            "relation_family", "question_form", "question",
            "prior_question_context_if_followup", "source_document_sha256")}
        projected["id"] = opaque_group_id
        name = group.get("source_document_path_author_aid", group.get("source_pdf"))
        if (not isinstance(name, str) or not name.startswith("lec")
            or not name.endswith(".pdf") or "/" in name or "\\" in name):
            raise ValueError("author_group_invalid")
        projected["source_document_path_author_aid"] = name
        candidate_map = []
        projected["candidates"] = []
        for position, (window, offset) in enumerate(zip(windows, offsets, strict=True)):
            opaque_candidate_id = "c_" + secrets.token_hex(12)
            projected["candidates"].append({
                "id": opaque_candidate_id, "exact_window": window,
                "source_offset": offset})
            candidate_map.append({"opaque_candidate_id": opaque_candidate_id,
                                  "author_candidate_index": position})
        random.SystemRandom().shuffle(projected["candidates"])
        groups.append(projected)
        mapping.append({"opaque_group_id": opaque_group_id,
                        "author_group_id": group["id"], "split": group["split"],
                        "candidates": candidate_map})
    random.SystemRandom().shuffle(groups)
    packet = {
        "schema": "cardchemy_reading_usefulness_blind_review_v2",
        "corpus_id": source.get("corpus_id"),
        "manifest_sha256": source.get("manifest_sha256"),
        "groups": groups,
        "review_instruction": (
            "Independently inspect each original PDF page and the exact visible cue. "
            "For each candidate, decide separately whether the page and cue help "
            "a student investigate the relation and conditions asked. Do not infer "
            "the author's provisional label or see another review."
        ),
    }
    data = (json.dumps(packet, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")
    packet_sha = hashlib.sha256(data).hexdigest()
    map_data = (json.dumps({
        "schema": "cardchemy_reading_usefulness_blind_mapping_v1",
        "author_draft_sha256": expected_sha256,
        "blind_packet_sha256": packet_sha,
        "groups": mapping,
    }, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")) + "\n").encode("utf-8")
    with output.open("xb") as stream:
        stream.write(data)
    with mapping_output.open("xb") as stream:
        stream.write(map_data)
    return {"status": "blind_review_packet_created_no_scoring",
            "groups": len(groups), "candidates": len(groups) * 4,
            "packet_sha256": packet_sha,
            "mapping_sha256": hashlib.sha256(map_data).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mapping-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = project(args.draft, args.output, args.mapping_output,
                         args.expected_sha256)
    except (OSError, ValueError, TypeError, KeyError):
        raise SystemExit("Blind review packet rejected; private diagnostics withheld.") from None
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
