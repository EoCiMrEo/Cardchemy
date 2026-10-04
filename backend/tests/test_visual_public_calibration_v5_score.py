"""Complete synthetic groups; unknowns, all cards and old failures remain visible."""
from copy import deepcopy
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import score_visual_public_calibration_v5 as scorer
from tests.test_visual_public_calibration_v3_score import invented, best_results


@pytest.mark.parametrize("false_matches,passed", [(0, True), (1, True), (2, True), (3, False)])
def test_ordinary_current_unverified_no_match_errors_have_eighty_percent_floor(false_matches, passed):
    overlay, ids = invented()
    results = best_results(overlay, ids)
    for row in results[54:54 + false_matches]:
        row["selected_ids"] = ["S01"]
    original = deepcopy((overlay, results))
    score = scorer.evaluate(overlay, results, ids)
    assert score["calibration_passed"] is passed
    assert scorer.ceiling(overlay, results, ids)["quality_reachable"] is passed
    assert score["metrics"]["valid_empty_no_match"] == 12 - false_matches
    assert score["metrics"]["nonuseful_displayed_cards"] == false_matches
    assert original == (overlay, results)
    assert score["heldout_opened"] is score["release_gate_passed"] is False


def test_partial_precision_and_old_gate_do_not_become_a_success():
    overlay, ids = invented()
    results = best_results(overlay, ids)
    results[-1]["selected_ids"] = ["S01"]
    assert not scorer.previous.evaluate(overlay, results, ids)["calibration_passed"]
    assert scorer.evaluate(overlay, results[:20], ids)["calibration_passed"] is False
    assert scorer.evaluate(overlay, results, ids)["calibration_passed"]


@pytest.mark.parametrize("problem", ["third_error", "weak_padding", "per_form_miss", "unknown_control", "unissued"])
def test_other_release_and_integrity_requirements_are_preserved(problem):
    overlay, ids = invented()
    results = best_results(overlay, ids, one_per_positive=True)
    if problem == "third_error":
        for index in range(3):
            results[index].update(state="failed", selected_ids=[], question_status=None)
    elif problem == "weak_padding":
        for row in results[:14]:
            row["selected_ids"].append("S04")
    elif problem == "per_form_miss":
        for index in (0, 3, 6, 9):
            results[index]["selected_ids"] = []
    elif problem == "unknown_control":
        for row in results[54:57]:
            row["question_status"] = "needs_clarification"
    else:
        results[0]["selected_ids"] = ["invented-id"]
        with pytest.raises(scorer.previous.ScoreError):
            scorer.evaluate(overlay, results, ids)
        return
    assert not scorer.evaluate(overlay, results, ids)["calibration_passed"]
    assert not scorer.ceiling(overlay, results, ids)["quality_reachable"]
