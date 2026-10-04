"""Pure source-navigation release metrics; completeness is diagnostic only.

The caller owns external SHA binding, strict response parsing and usage guards.
This module reads no files, imports no provider/configuration code and changes
no historical labels. ``ceiling`` is an optimistic bound, never a score/pass.
"""
from __future__ import annotations

from collections import Counter, defaultdict


SCHEMA_VERSION = "public_visual_heldout_v1_score"
FORMS = ("direct", "paraphrase", "followup")
ISSUED_IDS = ("S01", "S02", "S03", "S04")
VALUES = {"Yes", "No", "Unsure"}
STRATA = {1: 12, 2: 16, 3: 20}
USEFULNESS_NUMERATOR = 4
USEFULNESS_DENOMINATOR = 5
MIN_DISPLAYED_USEFULNESS_PERCENT = 100 * USEFULNESS_NUMERATOR // USEFULNESS_DENOMINATOR


class ScoreError(ValueError):
    """Closed, content-free rejection of a malformed scorer input."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ScoreError(code)


def _inputs(overlay: list[dict], results: list[dict], expected_ids: dict) -> tuple[dict, dict]:
    _require(type(expected_ids) is dict and len(expected_ids) == 60 and
             all(type(gid) is str and bool(gid) and type(ids) in (list, tuple) and
                 tuple(ids) == ISSUED_IDS for gid, ids in expected_ids.items()),
             "issued_roster_invalid")
    _require(type(overlay) is list and len(overlay) == 240, "overlay_roster_invalid")
    groups = defaultdict(list)
    pairs = set()
    for row in overlay:
        _require(type(row) is dict and {
            "pair_id", "group_id", "candidate_id", "form",
            "historical_joint_usefulness", "qualification"} <= set(row),
            "overlay_fields_invalid")
        pid, gid, sid = row["pair_id"], row["group_id"], row["candidate_id"]
        historical, qualification = row["historical_joint_usefulness"], row["qualification"]
        _require(type(pid) is str and pid not in pairs and type(gid) is str and
                 gid in expected_ids and type(sid) is str and sid in ISSUED_IDS and
                 type(row["form"]) is str and row["form"] in (*FORMS, "no_useful") and
                 type(historical) is str and historical in VALUES and
                 type(qualification) is str and qualification in VALUES,
                 "overlay_row_invalid")
        _require((qualification != "Yes" or historical == "Yes") and
                 (historical != "Unsure" or qualification == "Unsure"),
                 "qualification_regrades_historical_label")
        pairs.add(pid)
        groups[gid].append(row)
    _require(pairs == {f"P{i:03d}" for i in range(1, 241)} and len(groups) == 60 and
             all(len(rows) == 4 and {r["candidate_id"] for r in rows} == set(ISSUED_IDS) and
                 len({r["form"] for r in rows}) == 1 for rows in groups.values()),
             "complete_original_roster_required")
    _require(Counter(r["historical_joint_usefulness"] for r in overlay) ==
             Counter({"Yes": 104, "No": 136}), "frozen_historical_label_totals_changed")
    normalized = {}
    strata, forms = Counter(), Counter()
    unresolved = no_match = 0
    for gid, rows in groups.items():
        useful = {r["candidate_id"] for r in rows if r["historical_joint_usefulness"] == "Yes"}
        qualified = {r["candidate_id"] for r in rows if r["qualification"] == "Yes"}
        uncertain = {r["candidate_id"] for r in rows if r["qualification"] == "Unsure"}
        unknown_gold = any(r["historical_joint_usefulness"] == "Unsure" for r in rows)
        form = rows[0]["form"]
        if useful:
            _require(form in FORMS and not unknown_gold, "positive_group_binding_invalid")
            strata[len(useful)] += 1
            forms[form] += 1
        else:
            _require(form == "no_useful", "negative_group_binding_invalid")
            unresolved += int(unknown_gold)
            no_match += int(not unknown_gold and not uncertain)
        normalized[gid] = {"useful": useful, "qualified": qualified,
                           "uncertain": uncertain, "unknown_gold": unknown_gold,
                           "form": form, "no_match": not useful and not unknown_gold and not uncertain}
    _require(strata == Counter(STRATA) and forms == Counter({f: 16 for f in FORMS}) and
             unresolved == 0 and no_match <= 12, "frozen_group_obligations_changed")
    _require(type(results) is list and len(results) <= 60, "result_roster_invalid")
    indexed = {}
    for row in results:
        _require(type(row) is dict and {"group_id", "state", "selected_ids"} <= set(row) and
                 set(row) <= {"group_id", "state", "selected_ids", "usage", "question_status"},
                 "result_fields_invalid")
        gid, state, selected = row["group_id"], row["state"], row["selected_ids"]
        _require(type(gid) is str and gid in normalized and gid not in indexed and
                 type(state) is str and state in ("completed", "failed") and
                 type(selected) is list and len(selected) <= 3 and
                 all(type(sid) is str and sid in expected_ids[gid] for sid in selected) and
                 len(set(selected)) == len(selected) and
                 (state != "failed" or not selected) and
                 ("usage" not in row or type(row["usage"]) is dict),
                 "result_row_invalid")
        status = row.get("question_status")
        _require((state == "failed" and status is None) or
                 (state == "completed" and type(status) is str and
                  status in ("clear", "needs_clarification") and
                  (status != "needs_clarification" or not selected)), "question_status_invalid")
        indexed[gid] = {"state": state, "selected_ids": tuple(selected), "question_status": status}
    return normalized, indexed


def _exact(group: dict, selected: set[str]) -> bool:
    if not group["useful"] or group["unknown_gold"] or group["uncertain"]:
        return False
    if len(group["useful"]) <= 3:
        return selected == group["useful"] and selected <= group["qualified"]
    return len(selected) == 3 and selected <= group["useful"] & group["qualified"]


def _counts(groups: dict, results: dict) -> dict:
    valid = failed = displayed = credited = unknown = no_match = 0
    hits = Counter({f: 0 for f in FORMS})
    exact = Counter({n: 0 for n in STRATA})
    cardinality = Counter({n: 0 for n in STRATA})
    omitted = set()
    unrepresented = set()
    recall = Counter({n: 0 for n in (2, 3)})
    available = Counter({n: 0 for n in (2, 3)})
    for gid, group in groups.items():
        result = results.get(gid)
        selected = (set(result["selected_ids"]) if result is not None and
                    result["state"] == "completed" else set())
        omitted.update((gid, sid) for sid in group["useful"] - selected)
        unrepresented.update((gid, sid) for sid in group["useful"] - group["qualified"])
        good = selected & group["useful"] & group["qualified"]
        for n in (2, 3):
            if len(group["useful"]) >= n:
                available[n] += 1
                recall[n] += int(len(good) >= n)
    for gid, result in results.items():
        if result["state"] == "failed":
            failed += 1
            continue
        valid += 1
        group = groups[gid]
        selected = set(result["selected_ids"])
        good = selected & group["useful"] & group["qualified"]
        displayed += len(selected)
        credited += len(good)
        unknown += len(selected & group["uncertain"])
        if group["useful"]:
            hits[group["form"]] += int(bool(good))
            exact[len(group["useful"])] += int(_exact(group, selected))
            cardinality[len(group["useful"])] += int(len(selected) == min(3, len(group["useful"])))
        no_match += int(group["no_match"] and not selected and result["question_status"] == "clear")
    return {"valid": valid, "failed": failed, "displayed": displayed, "useful": credited,
            "unknown": unknown, "no_match": no_match, "hits": hits, "exact": exact,
            "cardinality": cardinality, "omitted": omitted, "unrepresented": unrepresented,
            "recall": recall, "available": available}


def evaluate(overlay: list[dict], results: list[dict], expected_ids: dict) -> dict:
    """Score reported outcomes; an incomplete pilot never passes.

    ``expected_ids`` must contain all 60 externally frozen group IDs. Results
    are strictly parsed 0–3 distinct issued IDs, or a failure with no IDs.
    Optional usage is opaque caller metadata and never included in the score.
    """
    groups, indexed = _inputs(overlay, results, expected_ids)
    counts = _counts(groups, indexed)
    complete = len(indexed) == 60
    gates = {"complete": complete, "availability": counts["valid"] >= 58,
             "error_budget": counts["failed"] <= 2,
             "positive_hits": sum(counts["hits"].values()) >= 40,
             "per_form_hits": all(counts["hits"][f] >= 14 for f in FORMS),
             "conclusive_no_match": counts["no_match"] >= 10,
             "unknown_displayed_zero": counts["unknown"] == 0,
             "all_displayed_usefulness": counts["displayed"] > 0 and
             USEFULNESS_DENOMINATOR * counts["useful"] >= USEFULNESS_NUMERATOR * counts["displayed"]}
    return {"schema_version": SCHEMA_VERSION, "heldout_passed": all(gates.values()),
            "complete": complete, "gates": gates, "metrics": {
                "total_request_denominator": 60, "original_groups": 60,
                "additional_control_groups": 0, "attempted_groups": len(indexed),
                "valid_responses": counts["valid"], "failed_groups": counts["failed"],
                "unattempted_groups": 60 - len(indexed),
                "unavailable_groups": 60 - counts["valid"],
                "historical_useful_pairs": 104, "qualified_historical_useful_pairs": sum(len(g["qualified"]) for g in groups.values()),
                "positive_groups": 48, "positive_hits": sum(counts["hits"].values()),
                "positive_hits_by_form": dict(counts["hits"]),
                "positive_groups_by_form": {f: 16 for f in FORMS},
                "historical_positive_strata": dict(STRATA),
                "conclusive_no_match_groups": 12, "valid_empty_no_match": counts["no_match"],
                "unresolved_original_groups": 0, "all_displayed_cards": counts["displayed"],
                "useful_displayed_cards": counts["useful"], "unknown_displayed_cards": counts["unknown"],
                "nonuseful_displayed_cards": counts["displayed"] - counts["useful"],
                "minimum_displayed_usefulness_percent": MIN_DISPLAYED_USEFULNESS_PERCENT,
                "all_displayed_usefulness": (counts["useful"] / counts["displayed"]
                                             if counts["displayed"] else 0.0)},
            "diagnostics": {
                "completeness_is_release_gate": False,
                "exact_sets": dict(counts["exact"]),
                "matching_selected_cardinality": dict(counts["cardinality"]),
                "omitted_historical_useful_pairs": [
                    {"group_id": gid, "candidate_id": sid} for gid, sid in sorted(counts["omitted"])],
                "unrepresented_historical_useful_pairs": [
                    {"group_id": gid, "candidate_id": sid} for gid, sid in sorted(counts["unrepresented"])],
                "second_useful_page_recall": {"groups": counts["available"][2],
                                             "groups_returning_at_least_two": counts["recall"][2]},
                "third_useful_page_recall": {"groups": counts["available"][3],
                                            "groups_returning_at_least_three": counts["recall"][3]},
                "omissions_include_failed_and_unattempted": True},
            "historical_labels_changed": False, "model_outcomes_supplied": bool(results),
            "release_gate_passed": False}


def ceiling(overlay: list[dict], results: list[dict], expected_ids: dict) -> dict:
    """Stop only if even optimistic outcomes for every remaining group fail.

    Remaining responses are assumed valid. Each can display all its qualifying
    historical-useful IDs up to three, maximizing precision and hit credit
    simultaneously. Uncertain selections get zero useful-card credit.
    A completed nonempty or failed no-match group cannot be repaired later.
    """
    groups, indexed = _inputs(overlay, results, expected_ids)
    counts = _counts(groups, indexed)
    hits, exact = counts["hits"].copy(), counts["exact"].copy()
    possible_no_match, additional_useful = counts["no_match"], 0
    for gid in set(groups) - set(indexed):
        group = groups[gid]
        good = group["useful"] & group["qualified"]
        additional_useful += min(3, len(good))
        if group["useful"]:
            hits[group["form"]] += int(bool(good))
            exact[len(group["useful"])] += int(_exact(group, set(sorted(good)[:3])))
        possible_no_match += int(group["no_match"])
    remaining = 60 - len(indexed)
    max_useful = counts["useful"] + additional_useful
    precision_denominator = counts["displayed"] + additional_useful
    checks = {"availability": counts["valid"] + remaining >= 58,
              "error_budget": counts["failed"] <= 2,
              "positive_hits": sum(hits.values()) >= 40,
              **{f"positive_hits_{f}": hits[f] >= 14 for f in FORMS},
              "conclusive_no_match": possible_no_match >= 10,
              "unknown_displayed_zero": counts["unknown"] == 0,
              "all_displayed_usefulness": precision_denominator > 0 and
              USEFULNESS_DENOMINATOR * max_useful >= USEFULNESS_NUMERATOR * precision_denominator}
    return {"schema_version": SCHEMA_VERSION + "_ceiling",
            "quality_reachable": all(checks.values()),
            "unreachable_reasons": [key for key, possible in checks.items() if not possible],
            "attempted_groups": len(indexed), "remaining_groups": remaining,
            "upper_bounds": {"valid_responses": counts["valid"] + remaining,
                             "positive_hits": sum(hits.values()), "positive_hits_by_form": dict(hits),
                             "valid_empty_no_match": possible_no_match,
                             "useful_displayed_cards": max_useful,
                             "usefulness_denominator_at_maximum": precision_denominator,
                             "minimum_displayed_usefulness_percent": MIN_DISPLAYED_USEFULNESS_PERCENT,
                             "all_displayed_usefulness": (max_useful / precision_denominator
                                                          if precision_denominator else 0.0)},
            "diagnostics": {"possible_exact_sets": dict(exact), "completeness_is_release_gate": False},
            "bound_is_not_selector_accuracy": True, "heldout_passed": False,
            "model_outcomes_supplied": bool(results), "release_gate_passed": False}
