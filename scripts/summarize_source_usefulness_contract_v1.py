"""Combine sealed offline reviews; never execute or rescore a model.

The disagreement packet hides votes and original labels. Uncertainty is not
silently resolved by majority or converted into a positive judgment.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import audit_source_usefulness_contract_v1 as audit

FIELDS = ("input_sufficiency", "page_usefulness", "cue_usefulness")
OLD_LABELS_SHA = "401359c12875521238d50d8723f6261daf31474f245dde573250ad80de34c6a5"


def load_sealed(root: Path, batch: int, reviewer: str) -> dict[str, dict]:
    freeze, _ = audit.read(root / "freeze.json")
    directory = root / f"batch-{batch}"
    wire, wsha = audit.read(directory / "wire-packet.json")
    audit.require(wsha == freeze["wire_packet_hashes"][str(batch)], "wire_packet_changed")
    owned = directory / reviewer
    wr, wrsha = audit.read(owned / "wire-sealed.json")
    ws, _ = audit.read(owned / "wire-seal.json")
    pages, psha = audit.read(owned / "pages-packet.json")
    pr, prsha = audit.read(owned / "pages-sealed.json")
    ps, _ = audit.read(owned / "pages-seal.json")
    audit.require(ws == {"review_sha256": wrsha, "pages_packet_sha256": psha} and
                  ps == {"review_sha256": prsha, "packet_sha256": psha} and
                  pages["wire_review_sha256"] == wrsha, "sealed_binding_changed")
    audit.validate_review(wr, wire, wsha, reviewer, "wire")
    audit.validate_review(pr, pages, psha, reviewer, "pages")
    result = {row["pair_id"]: {"input_sufficiency": row["input_sufficiency"],
                               "wire_reason": row["reason"]} for row in wr["judgments"]}
    for row in pr["judgments"]:
        result[row["pair_id"]].update({"page_usefulness": row["page_usefulness"],
                                      "cue_usefulness": row["cue_usefulness"],
                                      "page_reason": row["reason"]})
    return result


def comparison(a: dict[str, dict], b: dict[str, dict]) -> tuple[dict, dict]:
    audit.require(set(a) == set(b) and bool(a), "review_rosters_differ")
    agreement = {}
    disputes = {}
    for field in FIELDS:
        pairs = Counter((a[pid][field], b[pid][field]) for pid in a)
        audit.require(all(left in audit.VALUES and right in audit.VALUES for left, right in pairs),
                      "review_label_invalid")
        agreement[field] = {
            "pairs": len(a), "same_label": sum(n for (x, y), n in pairs.items() if x == y),
            "same_decisive_label": sum(n for (x, y), n in pairs.items() if x == y and x != "Unsure"),
            "matrix": {f"{x}/{y}": n for (x, y), n in sorted(pairs.items())},
        }
    for pid in sorted(a):
        pending = [field for field in FIELDS if a[pid][field] != b[pid][field] or
                   "Unsure" in (a[pid][field], b[pid][field])]
        if pending:
            disputes[pid] = pending
    return agreement, disputes


def prepare_adjudication(root: Path) -> Path:
    freeze, fsha = audit.read(root / "freeze.json")
    mapping, msha = audit.read(root / "mapping-root-only.json")
    audit.require(msha == freeze["mapping_sha256"], "mapping_changed")
    a, b, groups, all_hashes = {}, {}, [], {}
    for batch in (1, 2, 3):
        packet, psha = audit.read(root / f"batch-{batch}" / "wire-packet.json")
        audit.require(psha == freeze["wire_packet_hashes"][str(batch)], "wire_packet_changed")
        groups.extend(packet["groups"])
        for reviewer, combined in (("a", a), ("b", b)):
            rows = load_sealed(root, batch, reviewer)
            audit.require(not set(combined).intersection(rows), "duplicate_review_pair")
            combined.update(rows)
            for stage in ("wire", "pages"):
                _, sha = audit.read(root / f"batch-{batch}" / reviewer / f"{stage}-sealed.json")
                all_hashes[f"{batch}/{reviewer}/{stage}"] = sha
    audit.require(len(a) == len(b) == 264 and len(groups) == 66, "all_cases_required")
    agreement, disputes = comparison(a, b)
    destination = root / "adjudication"
    destination.mkdir()  # One immutable preparation; never replace reviews.
    summary = {"schema_version": audit.VERSION, "parent_freeze_sha256": fsha,
               "review_hashes": all_hashes, "agreement": agreement,
               "disputed_pairs": len(disputes), "disputed_fields": sum(map(len, disputes.values())),
               "provider_calls": 0, "quality_pass": False}
    audit.write_new(destination / "agreement.json", summary)
    audit.write_new(destination / "dispute-fields-root-only.json", {"fields": disputes})
    # Votes, reasons, original IDs and cardinality are absent from reviewer input.
    selected = [{**g, "candidates": [c for c in g["candidates"] if c["pair_id"] in disputes]}
                for g in groups]
    selected = [g for g in selected if g["candidates"]]
    packet = {"schema_version": audit.VERSION, "stage": "wire", "batch": 1,
              "rubric": audit.RUBRIC, "groups": selected}
    batch_dir = destination / "batch-1"
    batch_dir.mkdir()
    (batch_dir / "a").mkdir()
    wsha = audit.write_new(batch_dir / "wire-packet.json", packet)
    origin = {"schema_version": audit.VERSION,
              "pairs": [p for p in mapping["pairs"] if p["pair_id"] in disputes]}
    selected_msha = audit.write_new(destination / "mapping-root-only.json", origin)
    audit.write_new(destination / "freeze.json", {
        "schema_version": audit.VERSION, "kind": "disagreements_only_no_votes",
        "parent_freeze_sha256": fsha, "mapping_sha256": selected_msha,
        "rubric_sha256": freeze["rubric_sha256"], "wire_packet_hashes": {"1": wsha},
        "groups": len(selected), "candidate_pairs": len(disputes),
    })
    return destination


def final_labels(a: dict[str, dict], b: dict[str, dict], resolved: dict[str, dict]) -> dict:
    _, disputes = comparison(a, b)
    audit.require(set(resolved) == set(disputes), "adjudication_roster")
    final = {}
    for pid in a:
        final[pid] = {}
        for field in FIELDS:
            label = resolved[pid][field] if field in disputes.get(pid, []) else a[pid][field]
            audit.require(label in audit.VALUES, "adjudication_label")
            final[pid][field] = label
        # Mixing unchanged consensus with adjudication can expose contradictions.
        # Retain these as unresolved; never promote a page to make the cue pass.
        if final[pid]["cue_usefulness"] == "Yes" and final[pid]["page_usefulness"] != "Yes":
            final[pid]["cue_usefulness"] = "Unsure"
    return final


def adjudication_bindings(root: Path, pending: dict, groups: list[dict], mapping: dict,
                          parent_sha: str, rubric_sha: str) -> dict:
    """Bind the fresh reviewer to the exact disputed original inputs."""
    directory = root / "adjudication"
    frozen, fsha = audit.read(directory / "freeze.json")
    packet, psha = audit.read(directory / "batch-1/wire-packet.json")
    origin, msha = audit.read(directory / "mapping-root-only.json")
    selected = [{**group, "candidates": [candidate for candidate in group["candidates"]
                 if candidate["pair_id"] in pending]} for group in groups]
    selected = [group for group in selected if group["candidates"]]
    expected = {"schema_version": audit.VERSION, "stage": "wire", "batch": 1,
                "rubric": audit.RUBRIC, "groups": selected}
    expected_mapping = {"schema_version": audit.VERSION,
                        "pairs": [pair for pair in mapping["pairs"] if pair["pair_id"] in pending]}
    audit.require(packet == expected and origin == expected_mapping and frozen == {
        "schema_version": audit.VERSION, "kind": "disagreements_only_no_votes",
        "parent_freeze_sha256": parent_sha, "mapping_sha256": msha,
        "rubric_sha256": rubric_sha, "wire_packet_hashes": {"1": psha},
        "groups": len(selected), "candidate_pairs": len(pending),
    }, "adjudication_input_changed")
    hashes = {"freeze": fsha, "wire_packet": psha, "mapping": msha}
    if pending:
        for stage in ("wire", "pages"):
            _, sha = audit.read(directory / f"batch-1/a/{stage}-sealed.json")
            hashes[f"{stage}_review"] = sha
    return hashes


def summarize_labels(rows: dict[str, dict], groups: list[dict]) -> dict:
    roster = {c["pair_id"] for g in groups for c in g["candidates"]}
    audit.require(roster == set(rows), "final_roster")
    counts = {field: dict(Counter(row[field] for row in rows.values())) for field in FIELDS}
    unresolved = sorted(pid for pid, row in rows.items() if "Unsure" in row.values())
    useful = {pid for pid, row in rows.items() if row["page_usefulness"] == row["cue_usefulness"] == "Yes"}
    input_missing = sorted(pid for pid in useful if rows[pid]["input_sufficiency"] == "No")
    cue_missing = sorted(pid for pid, row in rows.items() if row["page_usefulness"] == "Yes" and row["cue_usefulness"] == "No")
    strata = Counter()
    for g in groups:
        ids = {c["pair_id"] for c in g["candidates"]}
        strata["unresolved" if ids.intersection(unresolved) else str(len(ids & useful))] += 1
    return {"groups": len(groups), "pairs": len(rows), "label_counts": counts,
            "unresolved_pairs": len(unresolved), "adjudicated_cardinality": dict(strata),
            "useful_page_and_cue_pairs": len(useful), "useful_pairs_missing_wire_link": len(input_missing),
            "useful_page_missing_cue": len(cue_missing),
            "unresolved_pair_ids": unresolved, "missing_wire_pair_ids": input_missing,
            "missing_cue_pair_ids": cue_missing, "quality_pass": False,
            "historical_models_rescored": False, "provider_calls": 0}


def prospective_feasibility(rows: dict[str, dict], groups: list[dict], forms: dict[str, str]) -> dict:
    """Optimistic label/input bound, not execution or a model score.

    Unknown labels block inference. The hypothetical selector knows exactly
    which agreed useful links are visible in its actual input and makes no
    false selections or transport errors. Real behavior can only be worse
    than this idealized witness under these labels; it is never a pass.
    """
    report = summarize_labels(rows, groups)
    if report["unresolved_pairs"]:
        return {"status": "unresolved_labels", "quality_pass": False}
    from collections import defaultdict
    import math
    buckets, per_form = defaultdict(Counter), defaultdict(Counter)
    totals = Counter()
    for group in groups:
        ids = [candidate["pair_id"] for candidate in group["candidates"]]
        useful = {pid for pid in ids if rows[pid]["page_usefulness"] == rows[pid]["cue_usefulness"] == "Yes"}
        observable = {pid for pid in useful if rows[pid]["input_sufficiency"] == "Yes"}
        n = len(useful)
        hit = bool(observable)
        exact = len(observable) >= 3 if n == 4 else observable == useful
        buckets[n]["groups"] += 1
        buckets[n]["maximum_exact"] += exact
        if n:
            totals["positive_groups"] += 1
            totals["maximum_positive_hits"] += hit
            per_form[forms[group["group_id"]]]["positive_groups"] += 1
            per_form[forms[group["group_id"]]]["maximum_hits"] += hit
        totals["maximum_displayed_useful_cards"] += min(3, len(observable))
    required_hit = max(30, math.ceil(5 * totals["positive_groups"] / 6))
    for amount, data in buckets.items():
        data["required_exact"] = data["groups"] if amount == 4 else math.ceil(5 * data["groups"] / 6)
    for data in per_form.values():
        data["required_hits"] = math.ceil(5 * data["positive_groups"] / 6)
    shape = (buckets[0]["groups"] == 12 and buckets[4]["groups"] == 2 and
             all(buckets[n]["groups"] >= 12 for n in (1, 2, 3)))
    quality_bound = (totals["maximum_positive_hits"] >= required_hit and
                     all(data["maximum_hits"] >= data["required_hits"] for data in per_form.values()) and
                     all(buckets[n]["maximum_exact"] >= buckets[n]["required_exact"] for n in (1, 2, 3, 4)))
    return {"status": "prospective_input_bound_only", "complete_denominators": dict(totals),
            "strata": {str(n): dict(data) for n, data in buckets.items()},
            "forms": {form: dict(data) for form, data in per_form.items()},
            "required_positive_hits": required_hit, "frozen_corpus_shape_preserved": shape,
            "idealized_input_can_meet_gates": bool(shape and quality_bound),
            "assumptions": "Perfect known-useful selection, zero transport errors, zero false displays; not measured behavior",
            "quality_pass": False}


def finalize(root: Path, old_labels_path: Path) -> dict:
    """Report all old/new labels; do not load any provider response or heldout."""
    freeze, fsha = audit.read(root / "freeze.json")
    mapping, msha = audit.read(root / "mapping-root-only.json")
    audit.require(msha == freeze["mapping_sha256"], "mapping_changed")
    a, b, groups = {}, {}, []
    agreement_receipt, agreement_sha = audit.read(root / "adjudication" / "agreement.json")
    audit.require(agreement_receipt["parent_freeze_sha256"] == fsha, "parent_freeze_changed")
    for batch in (1, 2, 3):
        packet, psha = audit.read(root / f"batch-{batch}" / "wire-packet.json")
        audit.require(psha == freeze["wire_packet_hashes"][str(batch)], "wire_packet_changed")
        groups.extend(packet["groups"])
        for reviewer, combined in (("a", a), ("b", b)):
            combined.update(load_sealed(root, batch, reviewer))
            for stage in ("wire", "pages"):
                _, sha = audit.read(root / f"batch-{batch}" / reviewer / f"{stage}-sealed.json")
                audit.require(sha == agreement_receipt["review_hashes"][f"{batch}/{reviewer}/{stage}"],
                              "review_changed_after_adjudication")
    _, pending = comparison(a, b)
    adjudication_hashes = adjudication_bindings(root, pending, groups, mapping, fsha,
                                              freeze["rubric_sha256"])
    adjudicated = load_sealed(root / "adjudication", 1, "a") if pending else {}
    resolved = final_labels(a, b, adjudicated)
    report = summarize_labels(resolved, groups)
    # Historical gold is visible to root only after every fresh judgment is
    # immutable and bound, including the independent disagreement review.
    original, oldsha = audit.read(old_labels_path)
    audit.require(oldsha == OLD_LABELS_SHA, "exposed_old_labels_hash")
    old = {(g["group_id"], c["id"]): c for g in original["groups"] for c in g["candidates"]}
    forms = {g["group_id"]: g["form"] for g in original["groups"]}
    changes = Counter()
    pairs = []
    for origin in mapping["pairs"]:
        pid = origin["pair_id"]
        former = old[(origin["old_group_id"], origin["old_candidate_id"])]
        now = resolved[pid]
        old_joint = former["page_useful"] and former["cue_useful"]
        new_joint = ("Unsure" if "Unsure" in (now["page_usefulness"], now["cue_usefulness"])
                     else "Yes" if now["page_usefulness"] == now["cue_usefulness"] == "Yes" else "No")
        changes[f"{'Yes' if old_joint else 'No'}/{new_joint}"] += 1
        pairs.append({**origin, "new_labels": now, "old_page_useful": former["page_useful"],
                      "old_cue_useful": former["cue_useful"], "form": forms[origin["old_group_id"]]})
    audit.require(len(pairs) == 264 and len(resolved) == 264 and len(groups) == 66, "complete_audit_required")
    report["old_to_new_joint_label_counts"] = dict(changes)
    report["agreement"] = agreement_receipt["agreement"]
    report["parent_freeze_sha256"] = fsha
    report["old_labels_sha256"] = oldsha
    report["review_hashes"] = agreement_receipt["review_hashes"]
    report["agreement_receipt_sha256"] = agreement_sha
    report["adjudication_hashes"] = adjudication_hashes
    blind_forms = {origin["group_id"]: forms[origin["old_group_id"]] for origin in mapping["pairs"]}
    report["prospective_feasibility"] = prospective_feasibility(resolved, groups, blind_forms)
    # This is feasibility of labels alone, with no historical model outcomes.
    strata = report["adjudicated_cardinality"]
    report["old_corpus_shape_preserved"] = bool(
        report["unresolved_pairs"] == 0 and strata.get("0", 0) == 12 and
        strata.get("4", 0) == 2 and all(strata.get(str(n), 0) >= 12 for n in (1, 2, 3)))
    report["provider_trial_ready"] = False
    destination = root / "final"
    destination.mkdir()
    audit.write_new(destination / "complete-label-mapping.json", {"schema_version": audit.VERSION,
                    "parent_freeze_sha256": fsha, "pairs": pairs})
    audit.write_new(destination / "summary.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--finalize-old-labels", type=Path)
    args = parser.parse_args()
    if args.finalize_old_labels:
        print(json.dumps(finalize(args.root, args.finalize_old_labels)))
    else:
        print(json.dumps({"adjudication_root": str(prepare_adjudication(args.root))}))


if __name__ == "__main__":
    main()
