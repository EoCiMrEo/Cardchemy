"""Invented complete rosters; no source, key, provider or application access."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import score_visual_public_calibration_v2 as scorer


def invented():
    rows = []
    sizes = [1] * 17 + [2] * 21 + [3] * 14 + [4] * 2 + [0] * 11 + [-1]
    for index, size in enumerate(sizes):
        for c in range(4):
            label = "Unsure" if size == -1 and c < 3 else "Yes" if c < size else "No"
            rows.append({"pair_id": f"P{index * 4 + c + 1:03d}", "group_id": f"Q{index + 1:03d}",
                         "candidate_id": f"S{c + 1:02d}",
                         "form": scorer.FORMS[index % 3] if size > 0 else "no_useful",
                         "historical_joint_usefulness": label, "qualification": label})
    # Preserve hard miss/conflict IDs, without using a real question or source.
    rows[8]["historical_joint_usefulness"] = rows[8]["qualification"] = "No"
    rows[9]["historical_joint_usefulness"] = rows[9]["qualification"] = "Yes"
    rows[8]["qualification"] = rows[118]["qualification"] = "Unsure"
    rows[145]["qualification"] = "No"
    ids = {f"Q{i:03d}": list(scorer.ISSUED_IDS) for i in range(1, 68)}
    return rows, ids


def best_results(overlay, ids):
    result = []
    for gid in ids:
        good = [r["candidate_id"] for r in overlay if r["group_id"] == gid and r["qualification"] == "Yes"]
        result.append({"group_id": gid, "state": "completed", "selected_ids": good[:3]})
    return result


def test_complete_conservative_best_case_passes_without_erasing_known_misses():
    rows, ids = invented()
    result = scorer.evaluate(rows, best_results(rows, ids), ids)
    assert result["calibration_passed"]
    assert result["metrics"]["exact_sets"] == {1: 16, 2: 19, 3: 14, 4: 2}
    assert result["metrics"]["valid_empty_no_match"] == 12
    assert result["metrics"]["total_request_denominator"] == 67
    assert result["release_gate_passed"] is False


def test_unknown_selected_card_counts_and_is_not_binary_no_match():
    rows, ids = invented()
    results = best_results(rows, ids)
    results[65]["selected_ids"] = ["S01", "S02", "S03"]
    score = scorer.evaluate(rows, results, ids)
    assert score["metrics"]["unknown_displayed_cards"] == 3
    assert score["metrics"]["all_displayed_cards"] == 109
    assert score["metrics"]["useful_displayed_cards"] == 106
    assert score["metrics"]["valid_empty_no_match"] == 12


@pytest.mark.parametrize("state,selection", [("failed", []), ("completed", ["S01"])])
def test_any_no_match_failure_is_unreachable_and_cannot_be_called_success(state, selection):
    rows, ids = invented()
    results = [{"group_id": "Q067", "state": state, "selected_ids": selection}]
    ceiling = scorer.ceiling(rows, results, ids)
    assert ceiling["quality_reachable"] is False
    assert "conclusive_no_match" in ceiling["unreachable_reasons"]


def test_two_errors_on_positive_groups_can_retain_availability_three_cannot():
    rows, ids = invented()
    result = best_results(rows, ids)
    for i in (0, 1):
        result[i] = dict(result[i], state="failed", selected_ids=[])
    score = scorer.evaluate(rows, result, ids)
    assert score["gates"]["availability"]
    result[2] = dict(result[2], state="failed", selected_ids=[])
    assert not scorer.evaluate(rows, result, ids)["gates"]["availability"]


def test_clarification_is_valid_but_not_conclusive_no_match():
    rows, ids = invented()
    result = [{"group_id": "Q067", "state": "completed", "selected_ids": [], "question_status": "needs_clarification"}]
    score = scorer.evaluate(rows, result, ids)
    assert score["metrics"]["valid_responses"] == 1
    assert score["metrics"]["valid_empty_no_match"] == 0
    assert not scorer.ceiling(rows, result, ids)["quality_reachable"]


def test_incomplete_denominator_and_unreachable_per_form_are_retained():
    rows, ids = invented()
    assert not scorer.evaluate(rows, [], ids)["calibration_passed"]
    assert scorer.ceiling(rows, [], ids)["quality_reachable"]
    result = [{"group_id": f"Q{i:03d}", "state": "completed", "selected_ids": []} for i in (1, 4, 7, 10)]
    assert "positive_hits_direct" in scorer.ceiling(rows, result, ids)["unreachable_reasons"]


@pytest.mark.parametrize("mutation", ["duplicate", "extra_id", "four_ids", "answer", "failed_ids", "bool_state", "relabel", "omit_group"])
def test_malformed_or_regraded_inputs_rejected(mutation):
    rows, ids = invented()
    result = best_results(rows, ids)
    if mutation == "duplicate":
        result[-1] = copy.deepcopy(result[0])
    elif mutation == "extra_id":
        result[0]["selected_ids"] = ["S99"]
    elif mutation == "four_ids":
        result[0]["selected_ids"] = list(scorer.ISSUED_IDS)
    elif mutation == "answer":
        result[0]["answer"] = "forbidden"
    elif mutation == "failed_ids":
        result[0]["state"] = "failed"
    elif mutation == "bool_state":
        result[0]["state"] = True
    elif mutation == "relabel":
        rows[145]["qualification"] = "Yes"
    else:
        ids.pop("Q067")
    with pytest.raises(scorer.ScoreError):
        scorer.evaluate(rows, result, ids)


def test_overflow_requires_three_distinct_qualified_pages_both_groups():
    rows, ids = invented()
    result = best_results(rows, ids)
    result[52]["selected_ids"] = ["S01", "S02"]
    score = scorer.evaluate(rows, result, ids)
    assert not score["gates"]["overflow"]
    assert "exact_4" in scorer.ceiling(rows, result, ids)["unreachable_reasons"]


def test_ceiling_precision_keeps_weak_and_unknown_denominator():
    rows, ids = invented()
    results = [{"group_id": f"Q{i:03d}", "state": "completed", "selected_ids": ["S02", "S03", "S04"]}
               for i in range(1, 18) if i != 3]
    ceiling = scorer.ceiling(rows, results, ids)
    assert "all_displayed_usefulness" in ceiling["unreachable_reasons"]
