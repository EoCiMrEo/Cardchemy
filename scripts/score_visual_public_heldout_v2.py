"""Prospective heldout metric alignment; historical v1 results stay unchanged.

Every issued source with an uncertain review remains in the displayed-card
denominator with zero usefulness credit. Unissued IDs still fail strict v1
input validation. This pure module cannot authorize provider work or release.
"""
import score_visual_public_heldout_v1 as historical

SCHEMA_VERSION = "public_visual_heldout_v2_score"
FORMS = historical.FORMS
ISSUED_IDS = historical.ISSUED_IDS
ScoreError = historical.ScoreError
MIN_DISPLAYED_USEFULNESS_PERCENT = historical.MIN_DISPLAYED_USEFULNESS_PERCENT


def evaluate(overlay, results, expected_ids):
    score = historical.evaluate(overlay, results, expected_ids)
    score["schema_version"] = SCHEMA_VERSION
    # Review uncertainty is a usefulness label, not an unissued source ID.
    del score["gates"]["unknown_displayed_zero"]
    score["heldout_passed"] = all(score["gates"].values())
    score["diagnostics"]["uncertain_reviews_receive_zero_credit"] = True
    return score


def ceiling(overlay, results, expected_ids):
    bound = historical.ceiling(overlay, results, expected_ids)
    bound["schema_version"] = SCHEMA_VERSION + "_ceiling"
    bound["unreachable_reasons"] = [reason for reason in bound["unreachable_reasons"]
                                    if reason != "unknown_displayed_zero"]
    bound["quality_reachable"] = not bound["unreachable_reasons"]
    bound["diagnostics"]["uncertain_reviews_receive_zero_credit"] = True
    return bound
