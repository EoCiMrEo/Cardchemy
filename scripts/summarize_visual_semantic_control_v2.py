"""Prospective conservative input bounds; never a model-quality score.

Historical page/cue labels remain intact. Fresh input reviews can expose a
conflict with old labels; conflicts receive no usefulness or exact-set credit.
Missing representation remains a miss even when an optimal selector could
avoid displaying it. No parent pilot is rescored and no heldout is opened.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import math
from pathlib import Path
import tempfile

import prepare_visual_page_source_input_v1 as visual
import prepare_visual_semantic_control_v2 as projection
import prototype_visual_page_source_judge_v2 as prospective
import summarize_visual_source_feasibility_v1 as previous

ROOT = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-semantic-v2-zn3h5eqb")
FREEZE_SHA = "caee7777a313813a3b46917d6245cc693422eb4f418e9cf6d1cef49e697c7097"
REVIEW_SHAS = {
    "semantic": "a303aead84e35b5839a44d2f8f8dcf661b9ffc8aa26b9c03d1544e81e042aeb2",
    "a": "5592c944cb374783f03b2ed304da2802f1eb5e28302ba804afdbe8199519f795",
    "b": "95892ecabd9b063a161dfcf8a820f01db8a98b5b8d5aabb21685f65a4c46e703",
}
PARENT_MAPPING_SHA = "1a25153b1ac6163671b1f18e69c836e3007faf44a2ba24875990e83e0938847d"
FIELDS = previous.FIELDS
VALUES = previous.VALUES


def validate_review(value: dict, packet: dict, packet_sha: str, reviewer: str) -> dict:
    visual.require(type(value) is dict and set(value) == {
        "reviewer", "packet_sha256", "images_visually_inspected", "provider_calls",
        "model_quality_pass", "judgments"}, "review_fields_invalid")
    roster = {r["review_id"] for r in packet["cases"]}
    visual.require(value["reviewer"] == reviewer and value["packet_sha256"] == packet_sha and
                   type(value["images_visually_inspected"]) is int and
                   value["images_visually_inspected"] == len(roster) and
                   type(value["provider_calls"]) is int and value["provider_calls"] == 0 and
                   value["model_quality_pass"] is False, "review_binding_invalid")
    visual.require(type(value["judgments"]) is list and len(value["judgments"]) == len(roster),
                   "complete_review_required")
    indexed = {}
    for row in value["judgments"]:
        visual.require(type(row) is dict and set(row) == {"review_id", *FIELDS, "reason"} and
                       type(row["review_id"]) is str and row["review_id"] in roster and
                       row["review_id"] not in indexed and
                       all(type(row[f]) is str and row[f] in VALUES for f in FIELDS) and
                       type(row["reason"]) is str and row["reason"] in previous.REASONS,
                       "review_judgment_invalid")
        visual.require(row["cue_usefulness"] != "Yes" or row["input_usefulness"] == "Yes",
                       "cue_without_useful_input")
        indexed[row["review_id"]] = row
    visual.require(set(indexed) == roster, "complete_review_required")
    return indexed


def joint(labels: dict) -> str:
    values = [labels["page_usefulness"], labels["cue_usefulness"]]
    visual.require(all(v in VALUES for v in values), "parent_labels_invalid")
    return "Yes" if values == ["Yes", "Yes"] else "No" if "No" in values else "Unsure"


def build_overlay(parent: list[dict], recovered: dict, semantic: dict) -> list[dict]:
    visual.require(len(parent) == 264 and len({r["pair_id"] for r in parent}) == 264 and
                   set(semantic) == projection.PAIRS, "complete_parent_roster")
    output = []
    for row in parent:
        labels = row["new_labels"]
        old_joint = joint(labels)
        input_usefulness = recovered.get(row["pair_id"], labels["input_sufficiency"])
        visual.require(input_usefulness in VALUES, "input_review_invalid")
        latest = semantic.get(row["pair_id"])
        fresh_joint = None
        conflict = False
        if latest:
            input_usefulness = latest["input_usefulness"]
            fresh_joint = ("Yes" if latest["input_usefulness"] == latest["cue_usefulness"] == "Yes"
                           else "No" if "No" in (latest["input_usefulness"], latest["cue_usefulness"])
                           else "Unsure")
            conflict = old_joint != fresh_joint
        # Neither conflicting new positives nor unresolved source labels can
        # receive usefulness credit. Old positives missing their visual relation
        # remain unrepresented obligations in the conservative hit/set bound.
        if old_joint == "Unsure" or (conflict and fresh_joint == "Yes"):
            qualification = "Unsure"
        elif old_joint == "No" or input_usefulness == "No" or fresh_joint == "No":
            qualification = "No"
        elif input_usefulness == "Unsure" or fresh_joint == "Unsure":
            qualification = "Unsure"
        else:
            qualification = "Yes"
        if latest and (latest["readability"] != "Yes" or latest["question_clarity"] != "Yes"):
            qualification = "Unsure"
        output.append({"pair_id": row["pair_id"], "group_id": row["group_id"],
                       "form": row["form"], "candidate_id": row["old_candidate_id"],
                       "historical_joint_usefulness": old_joint,
                       "historical_labels": dict(labels), "input_usefulness": input_usefulness,
                       "fresh_input_joint_usefulness": fresh_joint,
                       "historical_input_conflict": conflict, "qualification": qualification})
    return output


def conservative_bounds(overlay: list[dict], control_admitted: bool) -> dict:
    groups = defaultdict(list)
    for row in overlay:
        visual.require(row["qualification"] in VALUES and
                       row["historical_joint_usefulness"] in VALUES, "overlay_label_invalid")
        groups[row["group_id"]].append(row)
    visual.require(len(groups) == 66 and all(len(rows) == 4 for rows in groups.values()),
                   "complete_group_roster")
    strata = Counter()
    possible_exact = Counter()
    positives_by_form = Counter()
    possible_hits_by_form = Counter()
    no_match = unresolved = 0
    unavoidable_exact_miss = []
    missing_useful = []
    for gid, rows in sorted(groups.items()):
        useful = {r["candidate_id"] for r in rows if r["historical_joint_usefulness"] == "Yes"}
        unknown_gold = any(r["historical_joint_usefulness"] == "Unsure" for r in rows)
        eligible = {r["candidate_id"] for r in rows if r["qualification"] == "Yes"}
        unknown_qualification = any(r["qualification"] == "Unsure" for r in rows)
        missing_useful.extend(r["pair_id"] for r in rows if
                              r["historical_joint_usefulness"] == "Yes" and r["qualification"] != "Yes")
        if unknown_gold:
            unresolved += 1
        if not useful:
            if not unknown_gold and not unknown_qualification and all(r["qualification"] == "No" for r in rows):
                no_match += 1
            continue
        visual.require(len({r["form"] for r in rows}) == 1, "form_binding_invalid")
        form = rows[0]["form"]
        positives_by_form[form] += 1
        possible_hits_by_form[form] += int(bool(useful & eligible))
        n = len(useful)
        strata[n] += 1
        exact_possible = not unknown_gold and not unknown_qualification and (
            useful <= eligible if n <= 3 else len(useful & eligible) >= 3)
        possible_exact[n] += int(exact_possible)
        if not exact_possible:
            unavoidable_exact_miss.append(gid)
    total = 66 + int(control_admitted)
    no_match += int(control_admitted)
    required_exact = {n: (strata[n] if n == 4 else math.ceil(5 * strata[n] / 6)) for n in (1, 2, 3, 4)}
    required_hits_by_form = {f: math.ceil(5 * count / 6) for f, count in positives_by_form.items()}
    possible = (no_match >= 12 and all(strata[n] >= 12 for n in (1, 2, 3)) and
                all(possible_exact[n] >= required_exact[n] for n in (1, 2, 3, 4)) and
                sum(possible_hits_by_form.values()) * 12 >= 10 * sum(positives_by_form.values()) and
                all(possible_hits_by_form[f] >= required for f, required in required_hits_by_form.items()))
    return {"total_request_denominator": total, "all_original_groups_retained": 66,
            "admitted_additional_control_groups": int(control_admitted),
            "conclusive_no_match_groups": no_match, "unresolved_historical_groups": unresolved,
            "historical_positive_strata": dict(strata), "possible_exact_sets": dict(possible_exact),
            "required_exact_sets": required_exact, "possible_hits_by_form": dict(possible_hits_by_form),
            "required_hits_by_form": required_hits_by_form,
            "positives_by_form": dict(positives_by_form), "unavoidable_exact_miss_groups": unavoidable_exact_miss,
            "unrepresented_historical_useful_pairs": sorted(missing_useful),
            "minimum_valid_responses": total - 2, "allowed_transport_failures": 2,
            "bounded_input_can_support_thresholds": possible,
            "bound_is_not_selector_accuracy": True, "all_displayed_usefulness_threshold": 0.9,
            "unknown_selection_usefulness_credit": 0, "unknown_no_match_credit": 0,
            "model_quality_pass": False, "provider_trial_ready": False}


def summarize(destination: Path) -> None:
    visual.require(visual._inside_windows_job(), "enforceable_resource_mode_required")
    freeze = visual.read_json(ROOT / "freeze.json", FREEZE_SHA)
    semantic_packet = visual.read_json(ROOT / "semantic-packet.json", freeze["files"]["semantic-packet.json"])
    control_packet = visual.read_json(ROOT / "source_group-packet.json", freeze["files"]["source_group-packet.json"])
    hidden = visual.read_json(ROOT / "mapping-root-only.json", freeze["files"]["mapping-root-only.json"])
    reviews = {}
    for who, packet, name in (("semantic", semantic_packet, "semantic"), ("a", control_packet, "source_group"),
                              ("b", control_packet, "source_group")):
        reviews[who] = validate_review(visual.read_json(ROOT / f"review-{who}.json", REVIEW_SHAS[who]),
                                      packet, freeze["files"][f"{name}-packet.json"], who)
    for row in semantic_packet["cases"] + control_packet["cases"]:
        path = Path(row["image_path"])
        visual.require(path.resolve().parent == Path(freeze["access_root"]).resolve() and
                       not path.is_symlink(), "issued_image_source_required")
        raw = path.read_bytes()
        inspected = visual.inspect_png(raw)
        visual.require(inspected["sha256"] == row["image_sha256"] and
                       all(inspected[k] == row[k] for k in ("width", "height")), "review_image_changed")
    parent = visual.read_json(visual.AUDIT_ROOT / "final/complete-label-mapping.json", PARENT_MAPPING_SHA)
    old_freeze = visual.read_json(projection.OLD_ROOT / "freeze.json", projection.OLD_FREEZE_SHA)
    old_mapping = visual.read_json(projection.OLD_ROOT / "mapping-root-only.json", old_freeze["mapping_sha256"])
    old_a = visual.read_json(projection.OLD_ROOT / "review-a.json",
                            "37f388ac626785c7f067323d65ee02ebbec3aa208304b12352b49857c18cbf6d")
    old_b = visual.read_json(projection.OLD_ROOT / "review-b.json",
                            "8f03c7017f9843c9d1026b352b203c81c8feae169c4af92b052d11c8f87dcf06")
    indexed_a = {r["review_id"]: r for r in old_a["judgments"]}
    indexed_b = {r["review_id"]: r for r in old_b["judgments"]}
    recovered = {r["pair_id"]: "Yes" for rid, r in old_mapping.items() if r["kind"] == "gap" and
                 all(indexed[rid][f] == "Yes" for indexed in (indexed_a, indexed_b)
                     for f in ("readability", "input_usefulness", "cue_usefulness"))}
    semantic = {hidden["semantic"][rid]["pair_id"]: row for rid, row in reviews["semantic"].items()}
    visual.require(set(semantic) == projection.PAIRS, "approved_semantic_roster_required")
    roster = {r["review_id"] for r in control_packet["cases"]}
    admitted = all(reviews[w][rid]["readability"] == reviews[w][rid]["question_clarity"] == "Yes" and
                   reviews[w][rid]["input_usefulness"] == reviews[w][rid]["cue_usefulness"] == "No"
                   for w in ("a", "b") for rid in roster)
    overlay = build_overlay(parent["pairs"], recovered, semantic)
    bounds = conservative_bounds(overlay, admitted)
    files = {}
    files["qualification-overlay.json"] = visual.write_new(destination / "qualification-overlay.json", visual.canonical({
        "schema_version": "visual_source_qualification_overlay_v2", "parent_mapping_sha256": PARENT_MAPPING_SHA,
        "reconciliation_freeze_sha256": FREEZE_SHA, "historical_labels_changed": False,
        "review_shas": REVIEW_SHAS, "pairs": overlay}))
    files["bounds.json"] = visual.write_new(destination / "bounds.json", visual.canonical(bounds))
    # Freeze all current-question/image inputs under the new wire without render,
    # provider inference, answer drafting or modifying any prior full-wire SHA.
    control_group = None
    max_bytes = 0
    (destination / "requests").mkdir()
    for ordinal in range(1, 67):
        group = visual.load_frozen_group(projection.VISUAL_ROOT, ordinal,
                                        expected_freeze_sha256=projection.VISUAL_FREEZE_SHA)
        request = prospective.build_bound_request(group)
        raw = visual.canonical(request)
        max_bytes = max(max_bytes, len(raw))
        files[f"requests/group-{ordinal:03d}.json"] = visual.write_new(
            destination / f"requests/group-{ordinal:03d}.json", raw)
        # The retained unresolved group already carries exactly the four control
        # pages. Bind by original draft cue/image values, never by a new source.
        wanted = {(r["image_sha256"], r["context"], r["cue"]) for r in control_packet["cases"]}
        offered = {(r["image"]["sha256"], r["context"], r["cue"]) for r in group["candidates"]}
        if wanted == offered:
            visual.require(control_group is None, "control_source_group_not_unique")
            control_group = group
    visual.require(control_group is not None, "control_source_group_unbound")
    if admitted:
        control_group = dict(control_group, question=control_packet["cases"][0]["question"])
        raw = visual.canonical(prospective.build_bound_request(control_group))
        max_bytes = max(max_bytes, len(raw))
        files["requests/group-067.json"] = visual.write_new(destination / "requests/group-067.json", raw)
    summary = {"schema_version": "visual_semantic_control_summary_v2", "review_shas": REVIEW_SHAS,
               "reconciliation_freeze_sha256": FREEZE_SHA, "parent_mapping_sha256": PARENT_MAPPING_SHA,
               "parent_visual_freeze_sha256": projection.VISUAL_FREEZE_SHA,
               "semantic_judgments": {p: {f: r[f] for f in (*FIELDS, "reason")} for p, r in semantic.items()},
               "control_admitted": admitted, "control_reviews_agree": reviews["a"] == reviews["b"],
               "qualification_counts": dict(Counter(r["qualification"] for r in overlay)),
               "historical_input_conflicts": sorted(r["pair_id"] for r in overlay if r["historical_input_conflict"]),
               "bounds": bounds, "inert_request_count": 66 + int(admitted), "max_full_wire_bytes": max_bytes,
               "prototype_sha256": visual.digest(Path(prospective.__file__).read_bytes()),
               "files": files, "resource_limits_enforced": True, "old_labels_changed": False,
               "provider_calls": 0, "model_inferences": 0, "heldout_opened": False,
               "model_quality_pass": False, "provider_trial_ready": False}
    sha = visual.write_new(destination / "summary.json", visual.canonical(summary))
    visual.write_new(destination / "receipt.json", visual.canonical({
        "root": str(destination), "summary_sha256": sha, "control_admitted": admitted,
        "bounded_input_can_support_thresholds": bounds["bounded_input_can_support_thresholds"],
        "inert_request_count": summary["inert_request_count"], "provider_calls": 0}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--resource-job")
    args = parser.parse_args()
    if args.worker:
        visual.RESOURCE_JOB_NAME = visual.validate_resource_job_name(args.resource_job)
        visual.require(args.destination is not None and args.destination.resolve().parent ==
                       Path(tempfile.gettempdir()).resolve(), "temp_destination_required")
        summarize(args.destination)
    else:
        visual.require(args.destination is None and args.resource_job is None,
                       "internal_worker_arguments_forbidden")
        destination = Path(tempfile.mkdtemp(prefix="cardchemy-visual-semantic-summary-v2-"))
        visual.__file__ = __file__
        visual.supervise(destination)
        print((destination / "receipt.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
