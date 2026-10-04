"""Pure, keyless binding for a future private v4 source-display review.

The caller supplies byte-frozen Temp artifacts and a *separately obtained*
current-authorized page snapshot. This module validates their identities and
exact canonical cues; it never reads a database, PDF, provider, or private file.
The caller must establish the snapshot's provenance in a read-only authorized
transaction before treating a successful binding as release evidence.
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
import re
from typing import Any
from uuid import UUID

import score_source_judgment_display_v4 as scorer


SCHEMA = "private_source_gold_v4_stage1"
_FORMS = ("direct", "paraphrase", "followup")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class InvalidBridge(ValueError):
    """Fixed, content-free refusal; never include source data in the message."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise InvalidBridge(code)


def _is_sha(value: Any) -> bool:
    return type(value) is str and _SHA.fullmatch(value) is not None


def _uuid(value: Any) -> bool:
    if type(value) is not str:
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def _digest(value: object) -> str:
    # Match freeze_private_source_gold_v4._digest for document/page keys.
    body = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
    return sha256(body).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate_json_key")
        value[key] = item
    return value


def _json_exact(raw: bytes, expected_sha: str, code: str) -> dict:
    _require(type(raw) is bytes and 0 < len(raw) <= 512 * 1024
             and _is_sha(expected_sha) and sha256(raw).hexdigest() == expected_sha,
             code)
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except (UnicodeError, ValueError):
        raise InvalidBridge(code) from None
    _require(type(value) is dict, code)
    return value


def _stage1(raw: dict, stage1_sha256: str) -> tuple[dict[str, dict], dict[str, dict]]:
    _require(set(raw) == {
        "schema", "authored_input_sha256", "reviewer_kind", "review_method",
        "candidate_selection_seen", "frozen_at_utc", "scope", "cases",
    } and raw["schema"] == SCHEMA
        and _is_sha(raw["authored_input_sha256"])
        and raw["reviewer_kind"] == "agent_self_review"
        and raw["review_method"] == "authenticated_original_pdf_browser"
        and raw["candidate_selection_seen"] is False
        and type(raw["scope"]) is dict
        and set(raw["scope"]) == {"corpus_revision", "embedding_space_hash"}
        and type(raw["scope"]["corpus_revision"]) is int
        and raw["scope"]["corpus_revision"] >= 1
        and _is_sha(raw["scope"]["embedding_space_hash"])
        and type(raw["cases"]) is list and len(raw["cases"]) == 12,
        "invalid_stage1")
    try:
        scorer._utc(raw["frozen_at_utc"])
    except scorer.InvalidObservation:
        raise InvalidBridge("invalid_stage1") from None
    cases: dict[str, dict] = {}
    documents: dict[str, dict] = {}
    slots: dict[int, str] = {}
    forms: Counter[str] = Counter()
    page_keys: set[str] = set()
    for index, case in enumerate(raw["cases"], 1):
        _require(type(case) is dict and set(case) == {
            "case_id", "form", "question", "previous_turn", "document_slot",
            "page_number", "page_useful", "document_id", "content_revision_id",
            "index_revision_id", "page_sha256", "page_key", "original_pdf_sha256",
            "original_pdf_page_count",
        } and case["case_id"] == f"T{index:02}"
            and case["form"] in _FORMS
            and type(case["question"]) is str and 8 <= len(case["question"].strip()) <= 400
            and type(case["previous_turn"]) is str
            and (case["form"] == "followup") == bool(case["previous_turn"].strip())
            and type(case["document_slot"]) is int
            and 1 <= case["document_slot"] <= 3
            and type(case["page_number"]) is int
            and 1 <= case["page_number"] <= 100
            and case["page_useful"] == "Yes"
            and all(_uuid(case[key]) for key in (
                "document_id", "content_revision_id", "index_revision_id"
            ))
            and all(_is_sha(case[key]) for key in (
                "page_sha256", "page_key", "original_pdf_sha256"
            ))
            and type(case["original_pdf_page_count"]) is int
            and case["page_number"] <= case["original_pdf_page_count"] <= 10_000
            and case["page_key"] == _digest([case["document_id"], case["page_number"]])
            and case["page_key"] not in page_keys,
            "invalid_stage1_case")
        page_keys.add(case["page_key"])
        forms[case["form"]] += 1
        cases[case["case_id"]] = case
        binding = {key: case[key] for key in (
            "content_revision_id", "index_revision_id", "original_pdf_sha256",
            "original_pdf_page_count"
        )}
        document_id = case["document_id"]
        _require(documents.get(document_id, binding) == binding
                 and slots.get(case["document_slot"], document_id) == document_id,
                 "inconsistent_stage1_revision")
        documents[document_id] = binding
        slots[case["document_slot"]] = document_id
    _require(all(forms[form] == 4 for form in _FORMS)
             and set(slots) == {1, 2, 3} and len(set(slots.values())) == 3,
             "invalid_stage1_balance")
    _require(_is_sha(stage1_sha256), "invalid_stage1")
    return cases, documents


def validate_bridge(
    *, stage1_bytes: bytes, stage1_sha256: str,
    roster_bytes: bytes, roster_sha256: str,
    labels_bytes: bytes, labels_sha256: str,
    authorized_pages: list[dict], slates: list[dict],
) -> dict[str, Any]:
    """Bind stage-1 gold, current source revisions, issued cues and labels.

    ``authorized_pages`` must come from a separately verified, same-snapshot
    current principal/Subject/publication/revision/space/PDF read. Its booleans
    are assertions here; this pure function cannot prove their origin.
    ``slates`` must be captured before source-ID selection or label review.
    """

    stage1 = _json_exact(stage1_bytes, stage1_sha256, "stage1_digest_changed")
    roster = _json_exact(roster_bytes, roster_sha256, "roster_digest_changed")
    labels = _json_exact(labels_bytes, labels_sha256, "labels_digest_changed")
    cases, documents = _stage1(stage1, stage1_sha256)
    _require(roster.get("component") == "private_holdout"
             and roster.get("stage1_roster_sha256") == stage1_sha256,
             "stage1_roster_mismatch")
    try:
        scored_cases = scorer._roster(roster)
        scorer._labels(labels, scored_cases, roster_sha256,
                       scorer._utc(roster["frozen_at_utc"]))
        _require(scorer._utc(roster["frozen_at_utc"])
                 > scorer._utc(stage1["frozen_at_utc"]),
                 "roster_precedes_stage1")
    except scorer.InvalidObservation:
        raise InvalidBridge("invalid_v4_roster_or_labels") from None
    _require(set(scored_cases) == set(cases), "case_set_changed")
    for case_id, case in cases.items():
        scored = scored_cases[case_id]
        _require(scored["form"] == case["form"]
                 and scored["cohort"] == "holdout"
                 and scored["gold_page_key"] == case["page_key"],
                 "gold_case_changed")

    _require(type(authorized_pages) is list and type(slates) is list,
             "invalid_source_snapshot")
    pages: dict[str, dict] = {}
    for page in authorized_pages:
        _require(type(page) is dict and set(page) == {
            "document_id", "content_revision_id", "index_revision_id",
            "page_number", "page_text", "original_pdf_sha256",
            "original_pdf_page_count", "corpus_revision", "embedding_space_hash",
            "current_authorized", "published", "index_ready",
        } and _uuid(page["document_id"])
            and all(_uuid(page[key]) for key in ("content_revision_id", "index_revision_id"))
            and type(page["page_number"]) is int
            and 1 <= page["page_number"] <= 100
            and type(page["page_text"]) is str
            and 0 < len(page["page_text"]) <= 100_000
            and _is_sha(page["original_pdf_sha256"])
            and type(page["original_pdf_page_count"]) is int
            and page["page_number"] <= page["original_pdf_page_count"] <= 10_000
            and type(page["corpus_revision"]) is int
            and page["corpus_revision"] == stage1["scope"]["corpus_revision"]
            and page["embedding_space_hash"] == stage1["scope"]["embedding_space_hash"]
            and page["current_authorized"] is True
            and page["published"] is True and page["index_ready"] is True,
            "source_not_current")
        binding = documents.get(page["document_id"])
        _require(binding is not None and all(page[key] == binding[key] for key in binding),
                 "source_revision_changed")
        page_key = _digest([page["document_id"], page["page_number"]])
        _require(page_key not in pages, "duplicate_source_page")
        pages[page_key] = page
    for case in cases.values():
        gold = pages.get(case["page_key"])
        _require(gold is not None and sha256(gold["page_text"].encode("utf-8")).hexdigest()
                 == case["page_sha256"], "gold_page_changed")

    slate_by_case: dict[str, list[dict]] = {}
    for row in slates:
        _require(type(row) is dict and set(row) == {"case_id", "candidates"}
                 and row["case_id"] in cases and row["case_id"] not in slate_by_case
                 and type(row["candidates"]) is list
                 and len(row["candidates"]) <= 4, "invalid_slate")
        slate_by_case[row["case_id"]] = row["candidates"]
    _require(set(slate_by_case) == set(cases), "missing_slate")
    candidate_count = 0
    for case_id, candidates in slate_by_case.items():
        derived: list[dict[str, str]] = []
        seen_pages: set[str] = set()
        for index, candidate in enumerate(candidates, 1):
            _require(type(candidate) is dict and set(candidate) == {
                "runtime_id", "document_id", "page_number", "start_offset", "end_offset"
            } and candidate["runtime_id"] == f"S{index:02}"
                and _uuid(candidate["document_id"])
                and type(candidate["page_number"]) is int
                and type(candidate["start_offset"]) is int
                and type(candidate["end_offset"]) is int,
                "invalid_candidate_slice")
            page_key = _digest([candidate["document_id"], candidate["page_number"]])
            page = pages.get(page_key)
            _require(page is not None and page_key not in seen_pages,
                     "candidate_page_unavailable")
            start, end = candidate["start_offset"], candidate["end_offset"]
            _require(0 <= start < end <= len(page["page_text"])
                     and end - start <= 480,
                     "invalid_candidate_slice")
            cue = page["page_text"][start:end]
            _require(bool(cue.strip()), "invalid_candidate_slice")
            derived.append({"id": f"C{index}", "page_key": page_key,
                            "cue_sha256": sha256(cue.encode("utf-8")).hexdigest()})
            seen_pages.add(page_key)
        _require(scored_cases[case_id]["candidates"] == derived,
                 "candidate_identity_changed")
        candidate_count += len(derived)
    return {
        "schema": "private_source_gold_v4_bridge_v1",
        "stage1_sha256": stage1_sha256,
        "roster_sha256": roster_sha256,
        "labels_sha256": labels_sha256,
        "gold_pages_bound": len(cases),
        "candidates_bound": candidate_count,
        "release_gate_passed": False,
    }


if __name__ == "__main__":
    print(json.dumps({"schema": "private_source_gold_v4_bridge_v1",
                      "status": "preflight_only", "database_reads": 0,
                      "provider_requests": 0, "release_gate_passed": False}))
