"""Combine complete blind development reviews without a model quality score."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import prepare_visual_page_source_input_v1 as visual
import prepare_visual_source_feasibility_review_v1 as review

FIELDS = ("readability", "input_usefulness", "cue_usefulness", "question_clarity")
VALUES = {"Yes", "No", "Unsure"}
REASONS = {"direct_relation", "explicit_learning_step", "shared_topic_only",
           "generic_prerequisite", "question_restatement", "unrelated", "unclear_relation",
           "unresolved_referent", "condition_mismatch", "cue_does_not_locate",
           "outside_inference_required", "unreadable"}


def validate_review(value: dict, roster: set[str], packet_sha: str, reviewer: str) -> dict:
    visual.require(set(value) == {"reviewer", "packet_sha256", "judgments", "images_visually_inspected",
                                 "provider_calls", "model_quality_pass", "access_mapping_sha256"},
                   "review_fields_invalid")
    visual.require(value["reviewer"] == reviewer and value["packet_sha256"] == packet_sha and
                   value["images_visually_inspected"] == 29 and value["provider_calls"] == 0 and
                   value["model_quality_pass"] is False and
                   value["access_mapping_sha256"] == "b437660b9344fb00c8d346112dbf9dc08ef2d8f089d78996fba7225e2136224c",
                   "review_binding_invalid")
    rows = value["judgments"]
    visual.require(type(rows) is list and len(rows) == 29, "complete_review_required")
    indexed = {}
    for row in rows:
        visual.require(set(row) == {"review_id", *FIELDS, "reason"} and
                       row["review_id"] in roster and row["review_id"] not in indexed and
                       all(type(row[field]) is str and row[field] in VALUES for field in FIELDS) and
                       type(row["reason"]) is str and row["reason"] in REASONS,
                       "review_judgment_invalid")
        visual.require(row["cue_usefulness"] != "Yes" or row["input_usefulness"] == "Yes",
                       "cue_without_useful_input")
        indexed[row["review_id"]] = row
    visual.require(set(indexed) == roster, "complete_review_required")
    return indexed


def summarize(root: Path) -> dict:
    # Fixed packet/reviewer SHAs are recorded before root semantic comparison.
    freeze = visual.read_json(root / "freeze.json",
                             "9791994e5657dd3062659a105ea0dd71c5f6ff9b7201292ce542d6075dae840c")
    packet = visual.read_json(root / "review-packet.json", freeze["packet_sha256"])
    mapping = visual.read_json(root / "mapping-root-only.json", freeze["mapping_sha256"])
    roster = {r["review_id"] for r in packet["cases"] + packet["controls"]}
    a = validate_review(visual.read_json(root / "review-a.json",
        "37f388ac626785c7f067323d65ee02ebbec3aa208304b12352b49857c18cbf6d"), roster, freeze["packet_sha256"], "a")
    b = validate_review(visual.read_json(root / "review-b.json",
        "8f03c7017f9843c9d1026b352b203c81c8feae169c4af92b052d11c8f87dcf06"), roster, freeze["packet_sha256"], "b")
    gaps = {r["pair_id"]: {"review_id": rid, "a": a[rid]["input_usefulness"],
                           "b": b[rid]["input_usefulness"]}
            for rid, r in mapping.items() if r["kind"] == "gap"}
    weak = [rid for rid, row in mapping.items() if row["kind"] == "agreed_weak"]
    visual.require(set(gaps) == review.GAPS and len(weak) == 16 and len(roster) == 29,
                   "complete_feasibility_roster")
    omitted = {"P122", "P139", "P146", "P199"}
    represented = [pid for pid in sorted(omitted) if gaps[pid]["a"] == gaps[pid]["b"] == "Yes"]
    negative = ("N01", "N02", "N03", "N04")
    control_no = all(a[rid][f] == b[rid][f] == "No" for rid in negative
                     for f in ("input_usefulness", "cue_usefulness"))
    control_clear = all(a[rid]["question_clarity"] == b[rid]["question_clarity"] == "Yes"
                        for rid in negative)
    weak_preserved = all(a[rid][f] == b[rid][f] == "No" for rid in weak
                         for f in ("input_usefulness", "cue_usefulness"))
    readable = all(a[rid]["readability"] == b[rid]["readability"] == "Yes" for rid in roster)
    passed = len(represented) == 4 and control_no and control_clear and weak_preserved and readable
    return {
        "schema_version": "visual_source_feasibility_summary_v1",
        "parent_visual_freeze_sha256": freeze["parent_visual_freeze_sha256"],
        "packet_sha256": freeze["packet_sha256"], "review_rows": 29,
        "agreement": {field: sum(a[rid][field] == b[rid][field] for rid in roster) for field in FIELDS},
        "review_counts": {who: {field: dict(Counter(row[field] for row in indexed.values()))
                               for field in FIELDS} for who, indexed in (("a", a), ("b", b))},
        "gaps": gaps, "represented_diagnosed_visual_omissions": represented,
        "weak_input_counts": {who: dict(Counter(indexed[rid]["input_usefulness"] for rid in weak))
                              for who, indexed in (("a", a), ("b", b))},
        "weak_input_disputes": sorted(rid for rid in weak if a[rid]["input_usefulness"] != b[rid]["input_usefulness"]),
        "weak_input_unresolved": sorted(rid for rid in weak if
                                        "Unsure" in (a[rid]["input_usefulness"], b[rid]["input_usefulness"])),
        "new_control_all_four_input_and_cue_no": control_no,
        "new_control_question_clarity_conclusive": control_clear,
        "new_control_admitted": control_no and control_clear, "original_uncertainty_labels_changed": False,
        "all_original_cases_retained": True, "provider_calls": 0, "heldout_opened": False,
        "model_quality_pass": False, "input_feasibility_passed": passed,
        "provider_trial_ready": False,
        "status": "input_review_complete_no_provider_authorization" if passed else
                  "stopped_unrepresented_relation_and_control_uncertainty",
    }
