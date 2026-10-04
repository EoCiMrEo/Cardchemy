"""Synthetic tri-state blind-review admission; no actual heldout or outcomes."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
import review_visual_public_heldout_v1 as review


def fixture():
    packet={"cases":[{"review_id":f"R{i:03d}"} for i in range(1,4)],"distinct_images":2}
    record={"reviewer":"independent-invented-reviewer","packet_sha256":"a"*64,
        "images_visually_inspected":2,"provider_calls":0,"model_quality_pass":False,
        "judgments":[{"review_id":f"R{i:03d}","readability":"Yes","question_clarity":"Yes",
            "input_usefulness":"Unsure","cue_usefulness":"Unsure","reason":"uncertain_relation"}
            for i in range(1,4)]}
    # Choose an existing closed reason without coupling tests to public examples.
    for row in record["judgments"]:row["reason"]=sorted(review.REASONS)[0]
    return packet,record


def test_unsure_remains_unsure_and_review_claims_no_model_quality():
    packet,record=fixture();before=copy.deepcopy(record)
    values=review.validate_review(record,packet,"a"*64,record["reviewer"])
    assert record==before and {r["input_usefulness"] for r in values.values()}=={"Unsure"}


@pytest.mark.parametrize("mutation,code",[
    (lambda r:r["judgments"].pop(),"complete_review_required"),
    (lambda r:r.update(images_visually_inspected=True),"review_binding_invalid"),
    (lambda r:r.update(model_quality_pass=True),"review_binding_invalid"),
    (lambda r:r["judgments"][0].update(input_usefulness=False),"review_judgment_invalid"),
    (lambda r:r["judgments"][1].update(review_id="R001"),"review_judgment_invalid"),
    (lambda r:r["judgments"][0].update(cue_usefulness="Yes"),"cue_without_useful_input"),
])
def test_incomplete_coerced_or_unbound_review_rejected(mutation,code):
    packet,record=fixture();mutation(record)
    with pytest.raises(review.input_.PreparationError,match=code):
        review.validate_review(record,packet,"a"*64,record["reviewer"])
