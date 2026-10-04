"""Synthetic complete rosters only; no public receipts or application imports."""
import copy
from itertools import combinations
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import score_visual_public_calibration_v3 as scorer


def invented():
    rows = []
    sizes = [1] * 17 + [2] * 21 + [3] * 14 + [4] * 2 + [0] * 11 + [-1]
    for index, size in enumerate(sizes):
        for candidate in range(4):
            label = "Unsure" if size == -1 and candidate < 3 else "Yes" if candidate < size else "No"
            rows.append({
                "pair_id": f"P{index * 4 + candidate + 1:03d}", "group_id": f"Q{index + 1:03d}",
                "candidate_id": f"S{candidate + 1:02d}",
                "form": scorer.FORMS[index % 3] if size > 0 else "no_useful",
                "historical_joint_usefulness": label, "qualification": label,
            })
    # Invented labels keep the sealed totals and known miss/conflict identities.
    rows[8]["historical_joint_usefulness"] = rows[8]["qualification"] = "No"
    rows[9]["historical_joint_usefulness"] = rows[9]["qualification"] = "Yes"
    rows[8]["qualification"] = rows[118]["qualification"] = "Unsure"
    rows[145]["qualification"] = "No"
    ids = {f"Q{i:03d}": list(scorer.ISSUED_IDS) for i in range(1, 68)}
    return rows, ids


def completed(gid, selection):
    return {"group_id": gid, "state": "completed", "selected_ids": list(selection), "question_status": "clear"}


def best_results(overlay, ids, *, one_per_positive=False):
    result = []
    for gid in ids:
        good = [r["candidate_id"] for r in overlay
                if r["group_id"] == gid and r["qualification"] == "Yes"]
        result.append(completed(gid, good[:1 if one_per_positive else 3]))
    return result


def test_missing_second_or_third_page_is_diagnostic_and_does_not_fail_release():
    rows, ids = invented()
    saved = copy.deepcopy(rows)
    score = scorer.evaluate(rows, best_results(rows, ids, one_per_positive=True), ids)
    assert score["calibration_passed"]
    assert set(score["gates"]) == {"complete", "availability", "error_budget", "positive_hits",
                                   "per_form_hits", "conclusive_no_match", "all_displayed_usefulness"}
    assert score["metrics"]["positive_hits"] == 54
    assert score["metrics"]["all_displayed_usefulness"] == 1.0
    assert score["metrics"]["historical_useful_pairs"] == 109
    diagnostics = score["diagnostics"]
    assert diagnostics["exact_sets"] == {1: 16, 2: 0, 3: 0, 4: 0}
    assert diagnostics["matching_selected_cardinality"] == {1: 17, 2: 0, 3: 0, 4: 0}
    assert len(diagnostics["omitted_historical_useful_pairs"]) == 55
    assert diagnostics["second_useful_page_recall"] == {"groups": 37, "groups_returning_at_least_two": 0}
    assert diagnostics["third_useful_page_recall"] == {"groups": 16, "groups_returning_at_least_three": 0}
    assert rows == saved
    assert score["release_gate_passed"] is score["heldout_opened"] is False


def test_exact_overflow_and_omissions_remain_separate_diagnostics():
    rows, ids = invented()
    score = scorer.evaluate(rows, best_results(rows, ids), ids)
    assert score["diagnostics"]["exact_sets"] == {1: 16, 2: 19, 3: 14, 4: 2}
    assert score["diagnostics"]["matching_selected_cardinality"] == {1: 17, 2: 20, 3: 14, 4: 2}
    assert score["diagnostics"]["second_useful_page_recall"]["groups_returning_at_least_two"] == 36
    assert score["diagnostics"]["third_useful_page_recall"]["groups_returning_at_least_three"] == 16
    assert score["diagnostics"]["unrepresented_historical_useful_pairs"] == [
        {"group_id": "Q037", "candidate_id": "S02"}]


def test_weak_extra_page_counts_in_every_displayed_card_denominator():
    rows, ids = invented()
    result = best_results(rows, ids)
    result[17]["selected_ids"].append("S03")
    score = scorer.evaluate(rows, result, ids)
    assert score["metrics"]["useful_displayed_cards"] == 106
    assert score["metrics"]["all_displayed_cards"] == 107
    assert score["metrics"]["nonuseful_displayed_cards"] == 1
    assert score["metrics"]["all_displayed_usefulness"] == 106 / 107
    assert score["diagnostics"]["exact_sets"][2] == 18
    assert score["calibration_passed"]  # The amendment permits no precision shortcut.


def test_weak_padding_cannot_pass_the_eighty_percent_gate():
    rows, ids = invented()
    result = best_results(rows, ids, one_per_positive=True)
    for index in range(14):
        result[index]["selected_ids"].append("S04")
    score = scorer.evaluate(rows, result, ids)
    assert score["metrics"]["positive_hits"] == 54
    assert score["metrics"]["all_displayed_usefulness"] == 54 / 68
    assert not score["gates"]["all_displayed_usefulness"]
    assert not score["calibration_passed"]


def test_unknown_and_missing_relation_selected_cards_receive_zero_credit():
    rows, ids = invented()
    result = best_results(rows, ids)
    result[2]["selected_ids"].append("S01")  # Conflicting weak/positive label.
    result[65]["selected_ids"] = ["S01", "S02", "S03"]  # Original unresolved group.
    result[36]["selected_ids"].append("S02")  # Historical useful relation absent from input.
    score = scorer.evaluate(rows, result, ids)
    assert score["metrics"]["unknown_displayed_cards"] == 4
    assert score["metrics"]["useful_displayed_cards"] == 106
    assert score["metrics"]["all_displayed_cards"] == 111
    assert score["metrics"]["nonuseful_displayed_cards"] == 5
    assert score["metrics"]["valid_empty_no_match"] == 12
    assert score["metrics"]["unresolved_original_groups"] == 1


@pytest.mark.parametrize("kind", ["failed", "nonempty", "clarification"])
def test_all_twelve_no_match_require_valid_clear_zero_ids(kind):
    rows, ids = invented()
    result = best_results(rows, ids)
    if kind == "failed":
        result[-1] = {"group_id": "Q067", "state": "failed", "selected_ids": []}
    elif kind == "nonempty":
        result[-1]["selected_ids"] = ["S01"]
    else:
        result[-1]["question_status"] = "needs_clarification"
    score = scorer.evaluate(rows, result, ids)
    assert score["metrics"]["valid_empty_no_match"] == 11
    assert not score["calibration_passed"]
    bound = scorer.ceiling(rows, [result[-1]], ids)
    assert not bound["quality_reachable"]
    assert "conclusive_no_match" in bound["unreachable_reasons"]


def test_partial_four_results_with_four_of_five_useful_is_never_a_complete_pass():
    rows, ids = invented()
    result = [completed("Q001", ["S01", "S04"]), completed("Q002", ["S01"]),
              completed("Q003", ["S02"]), completed("Q004", ["S01"])]
    score = scorer.evaluate(rows, result, ids)
    assert score["complete"] is score["calibration_passed"] is False
    assert score["metrics"]["total_request_denominator"] == 67
    assert score["metrics"]["valid_responses"] == 4
    assert score["metrics"]["unattempted_groups"] == 63
    assert score["metrics"]["all_displayed_usefulness"] == 4 / 5
    assert score["gates"]["all_displayed_usefulness"]
    bound = scorer.ceiling(rows, result, ids)
    assert bound["quality_reachable"]
    assert bound["calibration_passed"] is False


def test_ceiling_cannot_stop_only_for_low_exact_set_or_overflow_recall():
    rows, ids = invented()
    result = best_results(rows, ids, one_per_positive=True)[:54]
    bound = scorer.ceiling(rows, result, ids)
    assert bound["quality_reachable"]
    assert bound["unreachable_reasons"] == []
    assert bound["diagnostics"]["possible_exact_sets"] == {1: 16, 2: 0, 3: 0, 4: 0}
    assert bound["upper_bounds"]["valid_empty_no_match"] == 12


def test_exactly_two_errors_keep_availability_but_third_error_is_unreachable():
    rows, ids = invented()
    result = best_results(rows, ids)
    for index in (0, 1):
        result[index] = {"group_id": f"Q{index + 1:03d}", "state": "failed", "selected_ids": []}
    assert scorer.evaluate(rows, result, ids)["calibration_passed"]
    result[2] = {"group_id": "Q003", "state": "failed", "selected_ids": []}
    score = scorer.evaluate(rows, result, ids)
    assert score["metrics"]["valid_responses"] == 64
    assert not score["calibration_passed"]
    assert {"availability", "error_budget"} <= set(scorer.ceiling(rows, result[:3], ids)["unreachable_reasons"])


def test_per_form_fifteen_hits_remain_a_gate_with_all_original_obligations():
    rows, ids = invented()
    result = best_results(rows, ids)
    for index in (0, 3, 6, 9):
        result[index]["selected_ids"] = []
    score = scorer.evaluate(rows, result, ids)
    assert score["metrics"]["positive_hits"] == 50
    assert score["metrics"]["positive_hits_by_form"]["direct"] == 14
    assert not score["calibration_passed"]
    assert "positive_hits_direct" in scorer.ceiling(rows, result[:10], ids)["unreachable_reasons"]


@pytest.mark.parametrize("weak_cards", [13, 14])
def test_exact_eighty_percent_precision_passes_but_below_it_fails(weak_cards):
    rows, ids = invented()
    result = best_results(rows, ids, one_per_positive=True)
    for index in (0, 1):
        result[index] = {"group_id": f"Q{index + 1:03d}", "state": "failed", "selected_ids": []}
    for index in range(2, 2 + weak_cards):
        result[index]["selected_ids"].append("S04")
    score = scorer.evaluate(rows, result, ids)
    assert scorer.MIN_DISPLAYED_USEFULNESS_PERCENT == 80
    assert score["metrics"]["all_displayed_usefulness"] == 52 / (52 + weak_cards)
    assert score["gates"]["all_displayed_usefulness"] is (weak_cards == 13)
    assert score["calibration_passed"] is (weak_cards == 13)
    assert scorer.ceiling(rows, result, ids)["quality_reachable"] is (weak_cards == 13)


def test_mathematical_precision_ceiling_keeps_every_observed_weak_or_unknown_card():
    rows, ids = invented()
    result = [completed(f"Q{i:03d}", ["S02", "S03", "S04"])
              for i in range(1, 18) if i != 3]
    bound = scorer.ceiling(rows, result, ids)
    assert "all_displayed_usefulness" in bound["unreachable_reasons"]
    assert bound["upper_bounds"]["usefulness_denominator_at_maximum"] == 48 + 90
    assert bound["upper_bounds"]["useful_displayed_cards"] == 90


def test_ceiling_precision_upper_bound_dominates_every_issued_remaining_selection():
    rows, ids = invented()
    result = best_results(rows, ids)
    result[0]["selected_ids"].append("S04")
    prefix = result[:17] + result[18:]
    bound = scorer.ceiling(rows, prefix, ids)
    all_selections = [selection for n in range(4) for selection in combinations(scorer.ISSUED_IDS, n)]
    for selection in all_selections:
        complete = prefix + [completed("Q018", selection)]
        score = scorer.evaluate(rows, complete, ids)
        assert score["metrics"]["all_displayed_usefulness"] <= bound["upper_bounds"]["all_displayed_usefulness"]
        if score["calibration_passed"]:
            assert bound["quality_reachable"]


@pytest.mark.parametrize("mutation", [
    "duplicate_group", "duplicate_id", "foreign_id", "four_ids", "answer", "failed_ids",
    "bool_state", "bool_label", "false_status", "missing_status", "clarification_ids", "failed_status",
    "relabel", "missing_group", "missing_pair", "foreign_pair", "missing_usage_type",
])
def test_strict_closed_ids_counts_status_and_tri_states(mutation):
    rows, ids = invented()
    result = best_results(rows, ids)
    if mutation == "duplicate_group":
        result[-1] = copy.deepcopy(result[0])
    elif mutation == "duplicate_id":
        result[0]["selected_ids"] *= 2
    elif mutation == "foreign_id":
        result[0]["selected_ids"] = ["S99"]
    elif mutation == "four_ids":
        result[0]["selected_ids"] = list(scorer.ISSUED_IDS)
    elif mutation == "answer":
        result[0]["answer"] = "forbidden"
    elif mutation == "failed_ids":
        result[0]["state"] = "failed"
    elif mutation == "bool_state":
        result[0]["state"] = True
    elif mutation == "bool_label":
        rows[0]["qualification"] = True
    elif mutation == "false_status":
        result[0]["question_status"] = False
    elif mutation == "missing_status":
        del result[-1]["question_status"]
    elif mutation == "clarification_ids":
        result[0]["question_status"] = "needs_clarification"
    elif mutation == "failed_status":
        result[0] = {"group_id": "Q001", "state": "failed", "selected_ids": [], "question_status": "clear"}
    elif mutation == "relabel":
        rows[145]["qualification"] = "Yes"
    elif mutation == "missing_group":
        ids.pop("Q067")
    elif mutation == "missing_pair":
        rows.pop()
    elif mutation == "foreign_pair":
        rows[0]["pair_id"] = "P999"
    else:
        result[0]["usage"] = True
    with pytest.raises(scorer.ScoreError):
        scorer.evaluate(rows, result, ids)
    with pytest.raises(scorer.ScoreError):
        scorer.ceiling(rows, result, ids)
