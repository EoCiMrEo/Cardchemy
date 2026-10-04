"""Synthetic prospective metric contracts; no historic result is regraded."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import score_visual_public_heldout_v2 as scorer
import score_visual_public_heldout_v1 as historical
from test_visual_public_heldout_v1_score import fixture


def test_uncertainty_is_zero_credit_without_becoming_id_integrity_failure():
    overlay, results, ids = fixture()
    overlay[3]["qualification"] = "Unsure"
    results[0]["selected_ids"].append("S04")
    saved = copy.deepcopy((overlay, results, ids))
    old = historical.evaluate(overlay, results, ids)
    new = scorer.evaluate(overlay, results, ids)
    assert not old["heldout_passed"] and new["heldout_passed"]
    assert new["metrics"] == old["metrics"]
    assert new["metrics"]["unknown_displayed_cards"] == 1
    assert new["metrics"]["useful_displayed_cards"] == 48
    assert new["metrics"]["all_displayed_cards"] == 49
    assert "unknown_displayed_zero" not in new["gates"]
    assert (overlay, results, ids) == saved
    assert new["release_gate_passed"] is False
    assert scorer.ceiling(overlay, results[:1], ids)["quality_reachable"]
    assert not historical.ceiling(overlay, results[:1], ids)["quality_reachable"]


@pytest.mark.parametrize("label", ["No", "Unsure"])
@pytest.mark.parametrize("weak,passed", [(12, True), (13, False)])
def test_both_nonuseful_labels_count_at_exact_eighty_percent(label, weak, passed):
    overlay, results, ids = fixture()
    for index in range(weak):
        overlay[index * 4 + 3]["qualification"] = label
        results[index]["selected_ids"].append("S04")
    score = scorer.evaluate(overlay, results, ids)
    assert score["heldout_passed"] is passed
    assert score["metrics"]["all_displayed_cards"] == 48 + weak
    assert score["metrics"]["useful_displayed_cards"] == 48


@pytest.mark.parametrize("ids", [["unissued"], ["S01", "S01"], ["S01", "S02", "S03", "S04"]])
def test_invalid_or_duplicate_or_excess_reference_still_rejected(ids):
    overlay, results, expected = fixture()
    results[0]["selected_ids"] = ids
    with pytest.raises(scorer.ScoreError, match="result_row_invalid"):
        scorer.evaluate(overlay, results, expected)


def test_old_label_cannot_be_upgraded_and_full_cases_remain_required():
    overlay, results, ids = fixture()
    overlay[3]["qualification"] = "Yes"
    with pytest.raises(scorer.ScoreError, match="qualification_regrades_historical_label"):
        scorer.evaluate(overlay, results, ids)
    overlay[3]["qualification"] = "No"
    assert not scorer.evaluate(overlay, results[:-1], ids)["heldout_passed"]


def test_only_uncertain_review_ceiling_obligation_is_removed():
    overlay, results, ids = fixture()
    overlay[3]["qualification"] = "Unsure"
    results[0]["selected_ids"].append("S04")
    for row in results[1:4]:
        row.update(state="failed", question_status=None, selected_ids=[])
    old = historical.ceiling(overlay, results[:4], ids)
    new = scorer.ceiling(overlay, results[:4], ids)
    assert new["upper_bounds"] == old["upper_bounds"]
    assert set(new["unreachable_reasons"]) == set(old["unreachable_reasons"]) - {"unknown_displayed_zero"}
    assert not new["quality_reachable"]
    assert {"availability", "error_budget"} <= set(new["unreachable_reasons"])
