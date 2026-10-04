"""Invented heldout rosters exercise prospective full-denominator80%gates."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
import score_visual_public_heldout_v1 as score


def fixture():
    overlay=[];expected={};results=[]
    strata=[1]*12+[2]*16+[3]*20+[0]*12
    for ordinal,count in enumerate(strata,1):
        gid=f"Q{ordinal:03d}";expected[gid]=list(score.ISSUED_IDS)
        form=score.FORMS[(ordinal-1)%3] if count else "no_useful"
        for k,sid in enumerate(score.ISSUED_IDS):
            useful="Yes" if k<count else "No"
            overlay.append({"pair_id":f"P{(ordinal-1)*4+k+1:03d}","group_id":gid,
                "candidate_id":sid,"form":form,"historical_joint_usefulness":useful,
                "qualification":useful})
        results.append({"group_id":gid,"state":"completed","question_status":"clear",
            "selected_ids":["S01"] if count else []})
    return overlay,results,expected


def test_complete_useful_first_page_passes_without_padding():
    overlay,results,expected=fixture();before=copy.deepcopy(overlay)
    result=score.evaluate(overlay,results,expected)
    assert result["heldout_passed"] is True and overlay==before
    assert result["metrics"]["total_request_denominator"]==60
    assert result["metrics"]["positive_hits"]==48
    assert result["metrics"]["all_displayed_cards"]==48
    assert result["metrics"]["positive_hits_by_form"]==dict.fromkeys(score.FORMS,16)
    assert result["diagnostics"]["completeness_is_release_gate"] is False
    assert result["release_gate_passed"] is False


@pytest.mark.parametrize("weak,passed",[(12,True),(13,False)])
def test_exact80percent_every_displayed_card_boundary(weak,passed):
    overlay,results,expected=fixture()
    for i in range(weak):results[i]["selected_ids"].append("S04")
    outcome=score.evaluate(overlay,results,expected)
    assert outcome["heldout_passed"] is passed
    assert outcome["metrics"]["all_displayed_cards"]==48+weak
    assert outcome["metrics"]["useful_displayed_cards"]==48


@pytest.mark.parametrize("errors,passed",[(2,True),(3,False)])
def test_failed_controls_are_misses_and_not_nomatch(errors,passed):
    overlay,results,expected=fixture()
    for row in results[-errors:]:row.update(state="failed",question_status=None,selected_ids=[])
    outcome=score.evaluate(overlay,results,expected)
    assert outcome["heldout_passed"] is passed
    assert outcome["metrics"]["valid_responses"]==60-errors
    assert outcome["metrics"]["valid_empty_no_match"]==12-errors


@pytest.mark.parametrize("bad,passed",[(2,True),(3,False)])
def test_ordinary_nomatch10of12_boundary(bad,passed):
    overlay,results,expected=fixture()
    for row in results[-bad:]:row["selected_ids"]=["S01"]
    assert score.evaluate(overlay,results,expected)["heldout_passed"] is passed


def test_uncertain_source_receives_zero_credit_and_stops_optimistic_ceiling():
    overlay,results,expected=fixture()
    overlay[3]["qualification"]="Unsure";results[0]["selected_ids"].append("S04")
    outcome=score.evaluate(overlay,results,expected)
    assert outcome["heldout_passed"] is False
    assert outcome["metrics"]["unknown_displayed_cards"]==1
    assert outcome["metrics"]["useful_displayed_cards"]==48
    assert score.ceiling(overlay,results[:1],expected)["quality_reachable"] is False


def test_cannot_relabel_old_negative_as_useful():
    overlay,results,expected=fixture();overlay[3]["qualification"]="Yes"
    with pytest.raises(score.ScoreError,match="qualification_regrades_historical_label"):
        score.evaluate(overlay,results,expected)


def test_missing_groups_cannot_pass():
    overlay,results,expected=fixture()
    outcome=score.evaluate(overlay,results[:-1],expected)
    assert outcome["complete"] is False and outcome["heldout_passed"] is False
    assert outcome["metrics"]["unattempted_groups"]==1
    assert score.ceiling(overlay,results[:-1],expected)["quality_reachable"] is True


def test_clarification_is_not_valid_empty_nomatch():
    overlay,results,expected=fixture()
    for row in results[-3:]:row["question_status"]="needs_clarification"
    assert score.evaluate(overlay,results,expected)["gates"]["conclusive_no_match"] is False


def test_foreign_id_source_integrity_rejected():
    overlay,results,expected=fixture();results[0]["selected_ids"]=["foreign"]
    with pytest.raises(score.ScoreError,match="result_row_invalid"):
        score.evaluate(overlay,results,expected)
