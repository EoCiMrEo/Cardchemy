"""Prospective 80% reading/no-match metric; never regrades frozen old pilots."""
import score_visual_public_calibration_v3 as previous

SCHEMA_VERSION = "public_visual_calibration_v5_score"
MIN_NO_MATCH = 10  # ceil(80% of the twelve independently reviewed controls).
MIN_DISPLAYED_USEFULNESS_PERCENT = previous.MIN_DISPLAYED_USEFULNESS_PERCENT


def evaluate(overlay, results, expected_ids):
    score = previous.evaluate(overlay, results, expected_ids)
    score["schema_version"] = SCHEMA_VERSION
    score["gates"]["conclusive_no_match"] = score["metrics"]["valid_empty_no_match"] >= MIN_NO_MATCH
    score["metrics"]["minimum_valid_empty_no_match"] = MIN_NO_MATCH
    score["calibration_passed"] = all(score["gates"].values())
    return score


def ceiling(overlay, results, expected_ids):
    bound = previous.ceiling(overlay, results, expected_ids)
    reasons = [reason for reason in bound["unreachable_reasons"] if reason != "conclusive_no_match"]
    if bound["upper_bounds"]["valid_empty_no_match"] < MIN_NO_MATCH:
        reasons.append("conclusive_no_match")
    bound["schema_version"] = SCHEMA_VERSION + "_ceiling"
    bound["upper_bounds"]["minimum_valid_empty_no_match"] = MIN_NO_MATCH
    bound["unreachable_reasons"] = reasons
    bound["quality_reachable"] = not reasons
    return bound
