"""Failure-conservative prospective bounds using invented review rosters."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import summarize_visual_semantic_control_v2 as summary


def packet(n=4):
    return {"cases": [{"review_id": f"R{i:03d}"} for i in range(1, n + 1)]}


def review(n=4):
    return {"reviewer": "a", "packet_sha256": "a" * 64, "images_visually_inspected": n,
            "provider_calls": 0, "model_quality_pass": False, "judgments": [
                {"review_id": f"R{i:03d}", "readability": "Yes", "input_usefulness": "No",
                 "cue_usefulness": "No", "question_clarity": "Yes", "reason": "unrelated"}
                for i in range(1, n + 1)]}


@pytest.mark.parametrize("n", [3, 4])
def test_complete_bound_review_required(n):
    assert len(summary.validate_review(review(n), packet(n), "a" * 64, "a")) == n


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "sha", "count", "provider", "pass", "cue", "answer"])
def test_unbound_incomplete_or_non_source_review_cannot_admit_control(mutation):
    value = review()
    if mutation == "missing":
        value["judgments"].pop()
    elif mutation == "duplicate":
        value["judgments"][-1] = copy.deepcopy(value["judgments"][0])
    elif mutation == "sha":
        value["packet_sha256"] = "b" * 64
    elif mutation == "count":
        value["images_visually_inspected"] = False
    elif mutation == "provider":
        value["provider_calls"] = False
    elif mutation == "pass":
        value["model_quality_pass"] = True
    elif mutation == "cue":
        value["judgments"][0]["cue_usefulness"] = "Yes"
    else:
        value["judgments"][0]["answer"] = "forbidden"
    with pytest.raises(summary.visual.PreparationError):
        summary.validate_review(value, packet(), "a" * 64, "a")


def overlay():
    result = []
    sizes = [1] * 17 + [2] * 21 + [3] * 14 + [4] * 2 + [0] * 11 + [-1]
    for i, n in enumerate(sizes):
        for c in range(4):
            useful = "Unsure" if n == -1 and c < 3 else "Yes" if c < n else "No"
            result.append({"pair_id": f"P{i * 4 + c + 1:03d}", "group_id": f"G{i:03d}",
                           "candidate_id": f"S{c + 1:02d}", "form": ("direct", "paraphrase", "followup")[i % 3],
                           "historical_joint_usefulness": useful, "qualification": useful})
    return result


def test_unknown_source_keeps_request_denominator_and_gets_no_no_match_credit():
    value = summary.conservative_bounds(overlay(), False)
    assert value["total_request_denominator"] == 66
    assert value["conclusive_no_match_groups"] == 11
    assert value["unresolved_historical_groups"] == 1
    assert value["bounded_input_can_support_thresholds"] is False
    assert value["unknown_selection_usefulness_credit"] == value["unknown_no_match_credit"] == 0


def test_reviewed_control_can_admit_one_group_without_removing_originals():
    value = summary.conservative_bounds(overlay(), True)
    assert value["total_request_denominator"] == 67
    assert value["all_original_groups_retained"] == 66
    assert value["conclusive_no_match_groups"] == 12
    assert value["minimum_valid_responses"] == 65
    assert value["bounded_input_can_support_thresholds"] is True
    assert value["model_quality_pass"] is value["provider_trial_ready"] is False


def test_partial_representation_can_pass_bound_without_100_percent_input_repair():
    rows = overlay()
    # A two-page positive still has one available useful page: hit possible,
    # exact selection impossible. A weak conflict cannot be counted as useful.
    rows[17 * 4]["qualification"] = "No"
    rows[3]["qualification"] = "Unsure"
    result = summary.conservative_bounds(rows, True)
    assert result["historical_positive_strata"] == {1: 17, 2: 21, 3: 14, 4: 2}
    assert result["possible_exact_sets"] == {1: 16, 2: 20, 3: 14, 4: 2}
    assert result["required_exact_sets"] == {1: 15, 2: 18, 3: 12, 4: 2}
    assert result["unrepresented_historical_useful_pairs"] == [rows[68]["pair_id"]]
    assert result["bounded_input_can_support_thresholds"] is True


def test_unrepresented_overflow_cannot_satisfy_two_of_two_gate():
    rows = overlay()
    for row in rows[52 * 4:52 * 4 + 2]:
        row["qualification"] = "No"
    assert summary.conservative_bounds(rows, True)["bounded_input_can_support_thresholds"] is False


def test_insufficient_per_form_hits_fail_even_if_other_forms_all_possible():
    rows = overlay()
    positives = sorted({r["group_id"] for r in rows if r["historical_joint_usefulness"] == "Yes" and r["form"] == "direct"})
    for row in rows:
        if row["group_id"] in positives[:5]:
            row["qualification"] = "No"
    value = summary.conservative_bounds(rows, True)
    assert value["possible_hits_by_form"]["direct"] == 13
    assert value["bounded_input_can_support_thresholds"] is False


def test_public_calibration_keeps_five_sixths_per_form_above_private_floor():
    rows = overlay()
    positives = sorted({r["group_id"] for r in rows if r["historical_joint_usefulness"] == "Yes" and r["form"] == "direct"})
    for row in rows:
        if row["group_id"] in positives[:4]:
            row["qualification"] = "No"
    result = summary.conservative_bounds(rows, True)
    assert result["possible_hits_by_form"]["direct"] == 14
    assert result["required_hits_by_form"]["direct"] == 15
    assert result["bounded_input_can_support_thresholds"] is False


def test_new_positive_conflict_gets_uncertain_and_old_positive_input_miss_is_retained():
    parent = []
    for i in range(1, 265):
        parent.append({"pair_id": f"P{i:03d}", "group_id": f"G{(i - 1) // 4}", "form": "direct",
                       "old_candidate_id": f"S{(i - 1) % 4 + 1:02d}", "new_labels": {
                           "page_usefulness": "No", "cue_usefulness": "No", "input_sufficiency": "No"}})
    parent[145]["new_labels"] = {"page_usefulness": "Yes", "cue_usefulness": "Yes", "input_sufficiency": "No"}
    judgments = {}
    for pid in summary.projection.PAIRS:
        positive = pid != "P146"
        judgments[pid] = {"readability": "Yes", "question_clarity": "Yes",
                          "input_usefulness": "Yes" if positive else "No",
                          "cue_usefulness": "Yes" if positive else "No"}
    saved = copy.deepcopy(parent)
    result = {r["pair_id"]: r for r in summary.build_overlay(parent, {}, judgments)}
    assert parent == saved
    assert result["P009"]["qualification"] == result["P119"]["qualification"] == "Unsure"
    assert result["P146"]["historical_joint_usefulness"] == "Yes"
    assert result["P146"]["qualification"] == "No"


@pytest.mark.parametrize("field", ["readability", "question_clarity"])
def test_useful_input_without_readable_clear_task_cannot_qualify(field):
    parent = [{"pair_id": f"P{i:03d}", "group_id": f"G{(i - 1) // 4}", "form": "direct",
               "old_candidate_id": f"S{(i - 1) % 4 + 1:02d}", "new_labels": {
                   "page_usefulness": "Yes", "cue_usefulness": "Yes", "input_sufficiency": "Yes"}}
              for i in range(1, 265)]
    fresh = {pid: {"readability": "Yes", "question_clarity": "Yes", "input_usefulness": "Yes",
                   "cue_usefulness": "Yes"} for pid in summary.projection.PAIRS}
    fresh["P146"][field] = "No"
    result = {r["pair_id"]: r for r in summary.build_overlay(parent, {}, fresh)}
    assert result["P146"]["qualification"] == "Unsure"
