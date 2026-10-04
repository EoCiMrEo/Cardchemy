"""Synthetic review disagreement and denominator contracts, with no corpus."""
from pathlib import Path
import sys

import pytest
from test_source_usefulness_contract_audit import synthetic_source, review_for

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import audit_source_usefulness_contract_v1 as audit
import summarize_source_usefulness_contract_v1 as summary


def row(wire="Yes", page="Yes", cue="Yes"):
    return {"input_sufficiency": wire, "page_usefulness": page, "cue_usefulness": cue}


def test_uncertainty_even_when_agreed_requires_adjudication():
    a = {"P001": row("Unsure"), "P002": row("No", "No", "No")}
    b = {"P001": row("Unsure"), "P002": row("No", "Yes", "No")}
    agreement, disputes = summary.comparison(a, b)
    assert agreement["input_sufficiency"]["same_label"] == 2
    assert agreement["input_sufficiency"]["same_decisive_label"] == 1
    assert disputes == {"P001": ["input_sufficiency"], "P002": ["page_usefulness"]}


def test_adjudicator_only_changes_disputed_fields_and_preserves_unsure():
    a = {"P001": row("No"), "P002": row("Unsure", "No", "No")}
    b = {"P001": row(), "P002": row("Unsure", "No", "No")}
    resolved = {"P001": row("Unsure", "No", "No"), "P002": row("No")}
    final = summary.final_labels(a, b, resolved)
    assert final == {"P001": row("Unsure"), "P002": row("No", "No", "No")}


def test_conflicting_final_page_and_cue_does_not_promote_page():
    a = {"P001": row()}
    b = {"P001": row("Yes", "No", "Yes")}
    assert summary.final_labels(a, b, {"P001": row("Yes", "No", "No")}) == {
        "P001": row("Yes", "No", "Unsure")}


def test_missing_and_extra_adjudication_rejected():
    a, b = {"P001": row("No")}, {"P001": row()}
    for resolved in ({}, {"P001": row(), "P002": row()}):
        with pytest.raises(audit.AuditError, match="adjudication_roster"):
            summary.final_labels(a, b, resolved)


def test_complete_denominator_preserves_unobservable_and_uncertain_sources():
    rows = {"P001": row("No"), "P002": row("Unsure"),
            "P003": row("No", "No", "No"), "P004": row("Yes", "Yes", "No")}
    groups = [{"group_id": "Q001", "candidates": [{"pair_id": x} for x in rows]}]
    report = summary.summarize_labels(rows, groups)
    assert report["pairs"] == 4
    assert report["adjudicated_cardinality"] == {"unresolved": 1}
    assert report["useful_pairs_missing_wire_link"] == 1
    assert report["useful_page_missing_cue"] == 1
    assert report["unresolved_pair_ids"] == ["P002"]
    assert report["quality_pass"] is False
    assert report["historical_models_rescored"] is False
    assert report["provider_calls"] == 0


def test_summary_rejects_excluded_pair():
    with pytest.raises(audit.AuditError, match="final_roster"):
        summary.summarize_labels({"P001": row()}, [{"candidates": []}])


def test_review_pairs_must_match():
    with pytest.raises(audit.AuditError, match="review_rosters_differ"):
        summary.comparison({"P001": row()}, {"P002": row()})


@pytest.fixture
def complete_synthetic_audit(tmp_path, synthetic_source):
    from copy import deepcopy
    packet, documents = synthetic_source
    prototype = packet["groups"][0]
    packet["groups"] = []
    for number in range(66):
        group = deepcopy(prototype)
        group["group_id"] = f"invented-{number:03d}"
        packet["groups"].append(group)
    batches, mapping = audit.build_packets(packet, documents, "synthetic-only")
    root = tmp_path / "complete"
    root.mkdir()
    msha = audit.write_new(root / "mapping-root-only.json", mapping)
    hashes = {}
    for batch in batches:
        directory = root / f"batch-{batch['batch']}"
        directory.mkdir()
        hashes[str(batch["batch"])] = audit.write_new(directory / "wire-packet.json", batch)
        for reviewer in ("a", "b"):
            owned = directory / reviewer
            owned.mkdir()
    audit.write_new(root / "freeze.json", {"schema_version": audit.VERSION,
                    "mapping_sha256": msha, "wire_packet_hashes": hashes,
                    "rubric_sha256": audit.digest(audit.canonical(audit.RUBRIC)),
                    "groups": 66, "candidate_pairs": 264})
    for batch in (1, 2, 3):
        for reviewer in ("a", "b"):
            for stage in ("wire", "pages"):
                owned = root / f"batch-{batch}" / reviewer
                path = owned.parent / "wire-packet.json" if stage == "wire" else owned / "pages-packet.json"
                value, sha = audit.read(path)
                review = review_for(value, sha, reviewer)
                for judgment in review["judgments"]:
                    for field in summary.FIELDS:
                        if field in judgment:
                            judgment[field] = "Yes"
                if batch == 1 and reviewer == "b" and stage == "wire":
                    review["judgments"][0]["input_sufficiency"] = "Unsure"
                draft = owned / f"{stage}-draft.json"
                audit.write_new(draft, review)
                audit.seal(root, batch, reviewer, stage, draft)
    return root, mapping


def test_adjudication_then_final_mapping_preserves_all_cases(complete_synthetic_audit, monkeypatch):
    root, mapping = complete_synthetic_audit
    adjudication = summary.prepare_adjudication(root)
    packet, sha = audit.read(adjudication / "batch-1/wire-packet.json")
    assert sum(len(g["candidates"]) for g in packet["groups"]) == 1
    blind = audit.canonical(packet).decode()
    for field in ("old_group_id", "old_candidate_id", "review_hashes", "page_useful", "pdf_path"):
        assert f'"{field}":' not in blind
    for stage in ("wire", "pages"):
        owned = adjudication / "batch-1/a"
        path = owned.parent / "wire-packet.json" if stage == "wire" else owned / "pages-packet.json"
        packet, sha = audit.read(path)
        review = review_for(packet, sha)
        if stage == "wire":
            review["judgments"][0]["input_sufficiency"] = "Unsure"
        draft = owned / f"{stage}-draft.json"
        audit.write_new(draft, review)
        audit.seal(adjudication, 1, "a", stage, draft)
    groups = {}
    for origin in mapping["pairs"]:
        group = groups.setdefault(origin["old_group_id"], {"group_id": origin["old_group_id"],
            "form": "direct", "candidates": []})
        group["candidates"].append({"id": origin["old_candidate_id"], "page_useful": True, "cue_useful": True})
    old = root / "invented-old-labels.json"
    sha = audit.write_new(old, {"groups": list(groups.values())})
    monkeypatch.setattr(summary, "OLD_LABELS_SHA", sha)
    report = summary.finalize(root, old)
    assert report["groups"] == 66 and report["pairs"] == 264
    assert report["unresolved_pairs"] == 1
    assert report["adjudicated_cardinality"] == {"unresolved": 1, "4": 65}
    assert report["old_to_new_joint_label_counts"] == {"Yes/Yes": 264}
    assert report["provider_trial_ready"] is False
    assert len(report["review_hashes"]) == 12
    assert len(report["adjudication_hashes"]["wire_review"]) == 64
    complete, _ = audit.read(root / "final/complete-label-mapping.json")
    assert len(complete["pairs"]) == 264
    with pytest.raises(FileExistsError):
        summary.finalize(root, old)


def test_preparation_refuses_incomplete_review_without_dispute_artifacts(complete_synthetic_audit):
    root, _ = complete_synthetic_audit
    (root / "batch-3/b/pages-sealed.json").unlink()
    with pytest.raises(FileNotFoundError):
        summary.prepare_adjudication(root)
    assert not (root / "adjudication").exists()


def test_summary_rejects_review_tampering(complete_synthetic_audit):
    root, _ = complete_synthetic_audit
    path = root / "batch-2/a/wire-sealed.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(audit.AuditError, match="sealed_binding_changed"):
        summary.prepare_adjudication(root)
    assert not (root / "adjudication").exists()


def test_finalization_rejects_substituted_adjudication_input(complete_synthetic_audit, monkeypatch):
    root, mapping = complete_synthetic_audit
    destination = summary.prepare_adjudication(root)
    for stage in ("wire", "pages"):
        owned = destination / "batch-1/a"
        path = owned.parent / "wire-packet.json" if stage == "wire" else owned / "pages-packet.json"
        packet, sha = audit.read(path)
        draft = owned / f"{stage}-draft.json"
        audit.write_new(draft, review_for(packet, sha))
        audit.seal(destination, 1, "a", stage, draft)
    old = root / "invented-old-labels.json"
    groups = {}
    for origin in mapping["pairs"]:
        group = groups.setdefault(origin["old_group_id"], {
            "group_id": origin["old_group_id"], "form": "direct", "candidates": []})
        group["candidates"].append({"id": origin["old_candidate_id"],
                                    "page_useful": True, "cue_useful": True})
    monkeypatch.setattr(summary, "OLD_LABELS_SHA", audit.write_new(old, {"groups": list(groups.values())}))
    # Valid-looking replacement freeze cannot change the source lineage.
    freeze, _ = audit.read(destination / "freeze.json")
    freeze["parent_freeze_sha256"] = "f" * 64
    (destination / "freeze.json").write_bytes(audit.canonical(freeze))
    with pytest.raises(audit.AuditError, match="adjudication_input_changed"):
        summary.finalize(root, old)
    assert not (root / "final").exists()


def test_premature_finalization_cannot_open_historical_gold(complete_synthetic_audit, monkeypatch):
    root, _ = complete_synthetic_audit
    summary.prepare_adjudication(root)
    old = root / "historical-gold-must-not-be-opened.json"
    original_read = audit.read

    def guarded_read(path):
        assert path != old, "Historical labels opened before fresh adjudication was sealed"
        return original_read(path)

    monkeypatch.setattr(audit, "read", guarded_read)
    with pytest.raises(FileNotFoundError):
        summary.finalize(root, old)
    assert not (root / "final").exists()


def test_feasibility_keeps_missing_inputs_and_never_marks_quality_pass():
    rows, groups, forms = {}, [], {}
    for number, amount in enumerate([0]*12 + [1]*19 + [2]*17 + [3]*16 + [4]*2):
        group = {"group_id": f"G{number}", "candidates": []}
        forms[group["group_id"]] = "direct"
        for index in range(4):
            pid = f"{number}:{index}"
            useful = index < amount
            rows[pid] = row("Yes" if useful else "No", "Yes" if useful else "No", "Yes" if useful else "No")
            group["candidates"].append({"pair_id": pid})
        groups.append(group)
    good = summary.prospective_feasibility(rows, groups, forms)
    assert good["idealized_input_can_meet_gates"] is True
    assert good["quality_pass"] is False
    # Three cases in the two-useful stratum lose one observable link.
    for number in (31, 32, 33):
        rows[f"{number}:0"]["input_sufficiency"] = "No"
    bad = summary.prospective_feasibility(rows, groups, forms)
    assert bad["strata"]["2"] == {"groups": 17, "maximum_exact": 14, "required_exact": 15}
    assert bad["idealized_input_can_meet_gates"] is False
    assert bad["complete_denominators"]["positive_groups"] == 54
    rows["31:0"]["input_sufficiency"] = "Unsure"
    assert summary.prospective_feasibility(rows, groups, forms)["status"] == "unresolved_labels"
