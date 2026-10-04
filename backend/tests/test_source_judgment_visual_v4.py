"""Pure conservative parser proof; no provider, source, DB or runtime work."""
import itertools
import json

import pytest

from app.ai import source_judgment_visual_v3 as old
from app.ai import source_judgment_visual_v4 as new

IDS = ["S01", "S02", "S03", "S04"]
LABELS = ("direct", "concrete_learning_step", "topic_only", "unrelated", "uncertain")


def packet(rows, status="clear"):
    return old.canonical({"question_status": status, "pages": [
        {"id": sid, "usefulness": label, "cue_locates": flag}
        for sid, (label, flag) in zip(IDS, rows, strict=True)]})


def test_exhaustive_four_page_selection_is_conservative_and_legacy_equivalent():
    valid = repaired = 0
    for rows in itertools.product(itertools.product(LABELS, (False, True)), repeat=4):
        raw = packet(rows)
        before = raw
        result = new.parse_verdict(raw, IDS)
        eligible = [sid for sid, (label, cue) in zip(IDS, rows, strict=True)
                    if label in {"direct", "concrete_learning_step"} and cue]
        eligible.sort(key=lambda sid: (rows[IDS.index(sid)][0] != "direct", IDS.index(sid)))
        assert result["selected_ids"] == eligible[:3]
        assert result["generated_answer"] is False and result["unverified_references"] is True
        assert raw == before
        try:
            previous = old.parse_verdict(raw, IDS)
        except old.VisualSourceJudgmentError as error:
            assert str(error) == "cue_without_useful_page"
            assert result["excluded_cue_conflicts"] > 0
            repaired += 1
        else:
            assert {k: v for k, v in result.items() if k != "excluded_cue_conflicts"} == dict(
                previous, schema_version=new.CONTRACT_VERSION)
            assert result["excluded_cue_conflicts"] == 0
            valid += 1
    assert valid == 7 ** 4 and repaired == 10 ** 4 - 7 ** 4


@pytest.mark.parametrize("label", LABELS)
def test_clarification_cannot_select_or_silently_hide_a_positive_page(label):
    raw = packet([(label, True), ("unrelated", False), ("topic_only", False), ("uncertain", False)],
                 status="needs_clarification")
    if label in {"direct", "concrete_learning_step"}:
        with pytest.raises(new.VisualSourceJudgmentError, match="clarification_qualified_page"):
            new.parse_verdict(raw, IDS)
    else:
        result = new.parse_verdict(raw, IDS)
        assert result["selected_ids"] == [] and result["question_status"] == "needs_clarification"


@pytest.mark.parametrize("bad", [
    {"id": "S99", "usefulness": "direct", "cue_locates": True},
    {"id": "S01", "usefulness": "direct", "cue_locates": True},
    {"id": "S02", "usefulness": "invented", "cue_locates": True},
    {"id": "S02", "usefulness": "direct", "cue_locates": 1},
    {"id": "S02", "usefulness": "direct", "cue_locates": True, "answer": "untrusted"},
    {"id": "S02", "usefulness": "direct"}, None,
])
def test_conflicting_first_page_never_masks_invalid_later_rows(bad):
    value = json.loads(packet([("topic_only", True)] + [("direct", True)] * 3))
    value["pages"][1] = bad
    with pytest.raises(new.VisualSourceJudgmentError):
        new.parse_verdict(old.canonical(value), IDS)


@pytest.mark.parametrize("raw", [
    b'{"question_status":"clear","question_status":"clear","pages":[]}',
    b'{"question_status":"clear","pages":[],"extra":true}',
    b'{"question_status":"clear","pages":NaN}', b"\xff", b"x" * 2049,
])
def test_structural_failures_remain_global_failures(raw):
    with pytest.raises(new.VisualSourceJudgmentError):
        new.parse_verdict(raw, IDS)


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_bounded_rosters_and_all_negative_clear_response(count):
    ids = IDS[:count]
    raw = old.canonical({"question_status": "clear", "pages": [
        {"id": sid, "usefulness": "topic_only", "cue_locates": True} for sid in ids]})
    result = new.parse_verdict(raw, ids)
    assert result["selected_ids"] == [] and result["excluded_cue_conflicts"] == count


def test_request_and_usage_validation_are_the_existing_v3_functions():
    assert new.build_request is old.build_request
    assert new.validate_usage is old.validate_usage
