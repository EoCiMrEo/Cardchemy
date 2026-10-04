"""Content-free proposed source-only display gate; no provider or database."""

from copy import deepcopy
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import sys
from uuid import UUID

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import score_source_first_display as gate  # noqa: E402


def _rows(config=None):
    config = gate.manifest() if config is None else config
    ids = [case_id for cases in (config["seed"], config["holdout"])
           for values in cases.values() if isinstance(values, list) for case_id in values]
    ids += list(config["controls"])
    return [{
        "case_id": case_id,
        "gold_document_key": f"doc-{index % 3}",
        "gold_page_key": f"page-{index}",
        "gold_page_rank": 1,
        "owner_reviewed_gold": True,
        "owner_reviewed_windows": True,
        "result_kind": "related_knowledge",
        "windows": [{
            "page_key": f"page-{index}", "chars": 220,
            "question_relevant": True, "exact_chunk_slice": True,
            "canonical_page_aligned": True, "opened_current_page": True,
            "current_authorized": True, "known_irrelevant_u01_pair": False,
        }],
        "embedding_calls": 1, "answer_calls": 0, "automatic_retries": 0,
        "answer_assertion_present": False, "retrieval_ms": 8.0,
    } for index, case_id in enumerate(ids)]


def _row(rows, case_id):
    return next(row for row in rows if row["case_id"] == case_id)


def test_manifest_is_unobserved_and_default_preflight_is_keyless(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["score_source_first_display.py"])
    assert gate.main() == 0
    preflight = json.loads(capsys.readouterr().out)
    assert preflight == {
        "status": "candidate_preregistration_unobserved", "candidate_passed": False,
        "seed_cases": 11, "holdout_cases_required": 12, "control_cases_required": 2,
        "provider_calls": 0, "database_reads": 0, "database_writes": 0,
    }


def test_perfect_synthetic_measurements_can_pass_candidate_scorer():
    report = gate.score(_rows())
    assert report["candidate_passed"]
    assert report["seed_useful_hit_at_3"] == 11
    assert report["holdout_useful_hit_at_3"] == 12
    assert report["reviewed_page_recall_at_5"] == report["reviewed_page_mrr"] == 1.0
    assert report["answer_calls"] == 0


def test_seed_labels_do_not_pass_without_independent_holdout_or_window_review():
    rows = _rows()
    seed = set(sum(gate.manifest()["seed"].values(), []))
    report = gate.score([row for row in rows if row["case_id"] in seed])
    assert report["status"] == "incomplete_unreviewed"
    assert report["cases_missing"] == 14
    assert not report["candidate_passed"]
    rows[0]["owner_reviewed_windows"] = False
    assert not gate.score(rows)["candidate_passed"]


def test_irrelevant_pair_and_no_match_controls_cannot_be_called_success():
    rows = _rows()
    _row(rows, "U01")["windows"][0]["known_irrelevant_u01_pair"] = True
    assert not gate.score(rows)["candidate_passed"]
    assert gate.score(rows)["known_irrelevant_u01_windows"] == 1
    rows = _rows()
    n12 = _row(rows, "N12")
    n12["result_kind"] = "no_match"
    n12["windows"] = []
    assert not gate.score(rows)["controls_pass"]


def test_u01_safe_no_match_passes_its_negative_control():
    rows = _rows()
    u01 = _row(rows, "U01")
    u01["result_kind"] = "no_match"
    u01["windows"] = []
    report = gate.score(rows)
    assert report["controls_pass"]
    assert report["candidate_passed"]
    rows = _rows()
    _row(rows, "U01")["windows"][0]["question_relevant"] = False
    assert not gate.score(rows)["controls_pass"]


@pytest.mark.parametrize("damage", ["opened_current_page", "canonical_page_aligned", "current_authorized"])
def test_exact_page_open_and_authorization_are_hard_gates(damage):
    rows = _rows()
    _row(rows, "D01")["windows"][0][damage] = False
    report = gate.score(rows)
    assert not report["candidate_passed"]
    if damage == "opened_current_page":
        assert report["page_open_failures"] == 1
    if damage == "current_authorized":
        assert report["unauthorized_or_stale_exposures"] == 1


def test_answer_assertion_or_second_provider_call_fails_source_only_contract():
    rows = _rows()
    _row(rows, "P02")["answer_assertion_present"] = True
    assert not gate.score(rows)["candidate_passed"]
    rows = _rows()
    _row(rows, "D05")["embedding_calls"] = 2
    assert not gate.score(rows)["request_contract_pass"]
    rows = _rows()
    _row(rows, "D05")["answer_calls"] = 1
    assert not gate.score(rows)["candidate_passed"]


def test_holdout_must_use_distinct_unseen_pages_and_multiple_documents():
    rows = _rows()
    seed_page = _row(rows, "D01")["gold_page_key"]
    _row(rows, "T01")["gold_page_key"] = seed_page
    assert not gate.score(rows)["holdout_page_disjoint"]
    rows = _rows()
    holdout = set(sum((value for value in gate.manifest()["holdout"].values()
                       if isinstance(value, list)), []))
    for row in rows:
        if row["case_id"] in holdout:
            row["gold_document_key"] = "one-doc"
    assert not gate.score(rows)["holdout_page_disjoint"]


def test_private_text_or_unknown_fields_are_rejected_and_not_echoed(tmp_path, capsys, monkeypatch):
    rows = _rows()
    rows[0]["source_quote"] = "private-course-sentinel"
    with pytest.raises(gate.InvalidObservation):
        gate.score(rows)
    path = tmp_path / "observations.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["score_source_first_display.py", "--score", str(path)])
    assert gate.main() == 1
    output = capsys.readouterr().out
    assert "private-course-sentinel" not in output
    assert json.loads(output) == {"status": "invalid_local_observations", "candidate_passed": False}


def test_chunk_window_must_align_with_current_canonical_page():
    chunk = "BLEU compares n-gram\n\noverlap with a reference."
    page = "BLEU compares n-gram\n overlap with a reference."
    measured = gate.inspect_source_window(
        chunk_text=chunk, start_offset=0, end_offset=len(chunk), canonical_page_text=page,
    )
    assert measured == {
        "chars": len(chunk), "exact_chunk_slice": True, "canonical_page_aligned": True,
    }
    assert not gate.inspect_source_window(
        chunk_text=chunk, start_offset=0, end_offset=len(chunk),
        canonical_page_text="An unrelated current page.",
    )["canonical_page_aligned"]
    assert not gate.inspect_source_window(
        chunk_text=chunk, start_offset=-1, end_offset=len(chunk), canonical_page_text=page,
    )["exact_chunk_slice"]


def test_canonical_page_window_uses_exact_page_offsets_not_chunk_offsets():
    page = "BLEU\nstands for Bilingual Evaluation Understudy."
    start = page.index("BLEU")
    end = len(page)
    measured = gate.inspect_source_window(
        chunk_text="stands for Bilingual Evaluation Understudy.",
        start_offset=start, end_offset=end, canonical_page_text=page,
        source_kind="canonical_page",
    )
    assert measured == {
        "source_kind": "canonical_page", "chars": len(page),
        "exact_source_slice": True, "exact_chunk_slice": False,
        "canonical_page_aligned": True,
    }
    assert not gate.inspect_source_window(
        chunk_text="body", start_offset=0, end_offset=len(page) + 1,
        canonical_page_text=page, source_kind="canonical_page",
    )["exact_source_slice"]


def test_source_kind_flags_score_canonical_pages_and_reject_mismatches():
    rows = _rows()
    window = _row(rows, "D01")["windows"][0]
    window.update(source_kind="canonical_page", exact_source_slice=True,
                  exact_chunk_slice=False)
    assert gate.score(rows)["candidate_passed"]
    for bad in (
        {"source_kind": "future"},
        {"exact_source_slice": "unknown"},
        {"exact_chunk_slice": True},
        {"canonical_page_aligned": False},
    ):
        damaged = deepcopy(rows)
        _row(damaged, "D01")["windows"][0].update(bad)
        with pytest.raises(gate.InvalidObservation):
            gate.score(damaged)
    damaged = deepcopy(rows)
    _row(damaged, "D01")["windows"][0]["exact_source_slice"] = False
    _row(damaged, "D01")["windows"][0]["canonical_page_aligned"] = False
    report = gate.score(damaged)
    assert not report["candidate_passed"]
    assert report["source_integrity_failures"] == 1


def test_too_many_irrelevant_windows_fail_even_with_useful_first_windows():
    rows = deepcopy(_rows())
    for case_id in ("D01", "D02", "D03"):
        row = _row(rows, case_id)
        extra = dict(row["windows"][0], page_key=f"irrelevant-{case_id}", question_relevant=False)
        row["windows"].append(extra)
    report = gate.score(rows)
    assert report["seed_useful_hit_at_3"] == 11
    assert report["irrelevant_window_rate"] > 0.1
    assert not report["candidate_passed"]


def _private_inputs():
    from evaluate_private_source_display import Case, Scope, roster_fingerprint, runtime_fingerprint

    scope = Scope(UUID(int=1), UUID(int=2), (UUID(int=10), UUID(int=11), UUID(int=12)),
                  4, "a" * 64)
    groups = ("direct", "paraphrase", "followup")
    cases = []
    positives = []
    for index in range(12):
        document = scope.document_ids[index % 3]
        category = groups[index // 4]
        question = f"Synthetic question {index + 1}?"
        previous_turn = "Previous synthetic turn?" if category == "followup" else ""
        cases.append(Case(f"X{index + 1:02d}", question, document, index + 1, True,
                          (("user", previous_turn),) if previous_turn else ()))
        positives.append({"case_id": cases[-1].case_id, "category": category,
                          "question": question, "previous_turn": previous_turn,
                          "source": {"document_id": str(document), "page_number": index + 1},
                          "labels": {"source_fidelity": "unreviewed",
                                     "excerpt_sufficient": "unreviewed", "page_useful": "unreviewed"}})
    scope_raw = {"principal_id": str(scope.principal_id), "subject_id": str(scope.subject_id),
                 "document_ids": [str(value) for value in scope.document_ids],
                 "corpus_revision": scope.corpus_revision, "space_hash": scope.space_hash}
    candidate = {"schema": "source_sufficiency_candidate_packet_v1",
                 "source_frozen": True, "owner_reviewed": False,
                 "authored_template_mode": "private_source_sufficiency_authored_v1",
                 "authored_spec_sha256": "b" * 64,
                 "discovery_policy_id": gate.AUTHORED_DISCOVERY_POLICY,
                 "scope": {**scope_raw, "scope_job_id": str(UUID(int=3))},
                 "positives": positives, "insufficient_pairs": []}
    old_scope = {"corpus_revision": scope.corpus_revision,
                 "embedding_space_hash": scope.space_hash}
    old_gold = {"version": "source_navigation_holdout_gold_v1", "scope": old_scope,
                "cases": [{"gold_document_id": str(scope.document_ids[0]), "gold_page": 90}]}
    old_raw = json.dumps(old_gold).encode()
    old_alternatives = {"version": "source_gold_context_alternatives_v1", "scope": old_scope,
        "original_roster_sha256": hashlib.sha256(old_raw).hexdigest(),
        "candidates": [{"gold_document_id": str(scope.document_ids[0]), "page": 91}]}
    alternatives_raw = json.dumps(old_alternatives).encode()
    prior = {"schema": "source_sufficiency_candidate_packet_v1", "source_frozen": True,
             "scope": scope_raw, "positives": [{"source": {"document_id": str(scope.document_ids[1]),
                                                      "page_number": 92}}],
             "insufficient_pairs": []}
    development_raw = json.dumps(prior).encode()
    candidate["excluded_development_sources"] = {
        "old_scope": old_scope,
        "old_gold_sha256": hashlib.sha256(old_raw).hexdigest(),
        "old_alternatives_sha256": hashlib.sha256(alternatives_raw).hexdigest(),
        "old_review_pages_excluded": 2,
        "exposed_candidate_packet_sha256": [hashlib.sha256(development_raw).hexdigest()],
        "exposed_candidate_pages_excluded": 1}
    review = {"candidate_roster_sha256": gate._digest(candidate),
              "labels": {case.case_id: {"source_fidelity": "Yes",
                                        "excerpt_sufficient": "Yes", "page_useful": "Yes"}
                         for case in cases}}
    roster = {"schema": "source_only_display_roster_v1", "frozen": True,
              "scope": scope_raw, "cases": [{"case_id": case.case_id,
                  "question": case.question, "gold_document_id": str(case.gold_document_id),
                  "gold_page_number": case.gold_page_number, "owner_reviewed_gold": True,
                  "history": [list(turn) for turn in case.history]} for case in cases],
              "roster_sha256": roster_fingerprint(cases, scope),
              "runtime_sha256": runtime_fingerprint()}
    return candidate, review, roster, old_raw, alternatives_raw, (development_raw,)


def _private_measurement(frozen):
    config = deepcopy(gate.manifest())
    config["holdout"].update(frozen["holdout"])
    rows = _rows(config)
    for row in rows:
        gold = frozen["gold_keys"].get(row["case_id"])
        if gold is not None:
            row.update(gold)
            row["windows"][0]["page_key"] = gold["gold_page_key"]
    return {"schema": gate.PRIVATE_MEASUREMENT_SCHEMA,
            "holdout_manifest_sha256": frozen["holdout_manifest_sha256"],
            "roster_sha256": frozen["roster_sha256"],
            "runtime_sha256": frozen["runtime_sha256"], "observations": rows}


def test_reviewed_private_x_roster_is_frozen_before_scoring_and_v1_remains_unchanged():
    frozen = gate.freeze_private_holdout(*_private_inputs())
    assert frozen["holdout"] == {"direct": ["X01", "X02", "X03", "X04"],
                                 "paraphrase": ["X05", "X06", "X07", "X08"],
                                 "followup": ["X09", "X10", "X11", "X12"]}
    assert "question" not in json.dumps(frozen)
    gate.validate_private_holdout(frozen)
    report = gate.score_private_holdout(_private_measurement(frozen), frozen)
    assert report["candidate_passed"]
    assert report["holdout_useful_hit_at_3"] == 12
    assert report["holdout_useful_by_category"] == {group: 4 for group in gate._GROUPS}
    assert gate.manifest()["holdout"]["direct"] == ["T01", "T02", "T03", "T04"]


@pytest.mark.parametrize("field", ["source_fidelity", "excerpt_sufficient", "page_useful"])
def test_private_holdout_never_infers_owner_gold_labels(field):
    candidate, review, roster, *exclusions = _private_inputs()
    review["labels"]["X01"][field] = "No"
    with pytest.raises(gate.InvalidObservation, match="holdout_not_owner_reviewed"):
        gate.freeze_private_holdout(candidate, review, roster, *exclusions)


def test_private_holdout_rejects_changed_case_page_group_or_candidate_digest():
    candidate, review, roster, *exclusions = _private_inputs()
    roster["cases"][0]["gold_page_number"] = 99
    with pytest.raises(gate.InvalidObservation):
        gate.freeze_private_holdout(candidate, review, roster, *exclusions)


def test_private_holdout_requires_exact_discovery_policy_and_prior_page_proof():
    candidate, review, roster, *exclusions = _private_inputs()
    candidate["discovery_policy_id"] = "unknown_policy"
    review["candidate_roster_sha256"] = gate._digest(candidate)
    with pytest.raises(gate.InvalidObservation):
        gate.freeze_private_holdout(candidate, review, roster, *exclusions)

    candidate, review, roster, old_raw, alternatives_raw, development = _private_inputs()
    tampered = old_raw + b" "
    with pytest.raises(gate.InvalidObservation, match="exclusion_proof_changed"):
        gate.freeze_private_holdout(candidate, review, roster, tampered,
                                    alternatives_raw, development)

    candidate, review, roster, *exclusions = _private_inputs()
    candidate["positives"][0]["source"]["page_number"] = 90
    roster["cases"][0]["gold_page_number"] = 90
    from evaluate_private_source_display import Case, Scope, roster_fingerprint
    scope_raw = roster["scope"]
    scope = Scope(UUID(scope_raw["principal_id"]), UUID(scope_raw["subject_id"]),
                  tuple(UUID(value) for value in scope_raw["document_ids"]),
                  scope_raw["corpus_revision"], scope_raw["space_hash"])
    cases = tuple(Case(row["case_id"], row["question"], UUID(row["gold_document_id"]),
                       row["gold_page_number"], row["owner_reviewed_gold"],
                       tuple(tuple(turn) for turn in row["history"])) for row in roster["cases"])
    roster["roster_sha256"] = roster_fingerprint(cases, scope)
    review["candidate_roster_sha256"] = gate._digest(candidate)
    with pytest.raises(gate.InvalidObservation, match="old_page_reused"):
        gate.freeze_private_holdout(candidate, review, roster, *exclusions)
    candidate, review, roster, *exclusions = _private_inputs()
    candidate["positives"][0]["category"] = "paraphrase"
    review["candidate_roster_sha256"] = gate._digest(candidate)
    with pytest.raises(gate.InvalidObservation, match="invalid_private_roster"):
        gate.freeze_private_holdout(candidate, review, roster, *exclusions)
    candidate, review, roster, *exclusions = _private_inputs()
    candidate["positives"][0]["question"] = "Changed without owner review"
    with pytest.raises(gate.InvalidObservation):
        gate.freeze_private_holdout(candidate, review, roster, *exclusions)


def test_private_measurement_rejects_manifest_drift_gold_swap_and_missing_window_review():
    frozen = gate.freeze_private_holdout(*_private_inputs())
    measurement = _private_measurement(frozen)
    measurement["holdout_manifest_sha256"] = "0" * 64
    with pytest.raises(gate.InvalidObservation, match="measurement_not_preregistered"):
        gate.score_private_holdout(measurement, frozen)
    measurement = _private_measurement(frozen)
    _row(measurement["observations"], "X01")["gold_page_key"] = frozen["gold_keys"]["X02"]["gold_page_key"]
    with pytest.raises(gate.InvalidObservation, match="private_gold_mismatch"):
        gate.score_private_holdout(measurement, frozen)
    measurement = _private_measurement(frozen)
    _row(measurement["observations"], "X01")["owner_reviewed_windows"] = False
    assert not gate.score_private_holdout(measurement, frozen)["candidate_passed"]
    changed = deepcopy(frozen)
    changed["holdout"]["direct"].reverse()
    with pytest.raises(gate.InvalidObservation, match="private_holdout_changed"):
        gate.score_private_holdout(_private_measurement(frozen), changed)


def test_private_freeze_cli_is_exclusive_and_reports_only_digest(tmp_path, monkeypatch, capsys):
    candidate, review, roster, old_raw, alternatives_raw, (development_raw,) = _private_inputs()
    paths = [tmp_path / name for name in ("candidate.json", "review.json", "roster.json")]
    for path, content in zip(paths, (candidate, review, roster), strict=True):
        path.write_text(json.dumps(content), encoding="utf-8")
    old_paths = [tmp_path / name for name in ("old-gold.json", "old-alternatives.json", "prior.json")]
    for path, raw in zip(old_paths, (old_raw, alternatives_raw, development_raw), strict=True):
        path.write_bytes(raw)
    output = tmp_path / "preregistered.json"
    monkeypatch.setattr(sys, "argv", ["score_source_first_display.py", "--freeze-holdout",
        "--candidate", str(paths[0]), "--owner-review", str(paths[1]),
        "--roster", str(paths[2]), "--old-holdout", str(old_paths[0]),
        "--old-alternatives", str(old_paths[1]), "--development-packet", str(old_paths[2]),
        "--output", str(output)])
    assert gate.main() == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "private_holdout_frozen"
    assert summary["candidate_passed"] is False
    assert summary["holdout_cases"] == 12
    assert summary["verified_prior_page_exclusions"] == 3
    assert summary["development_seed_exclusion_independently_verified"] is False
    assert output.is_file()
    assert gate.main() == 1
    assert json.loads(capsys.readouterr().out)["status"] == "invalid_private_holdout"


def test_private_score_cli_requires_existing_earlier_registration(tmp_path, monkeypatch, capsys):
    frozen = gate.freeze_private_holdout(*_private_inputs())
    registered = tmp_path / "registered.json"
    observed = tmp_path / "observed.json"
    registered.write_text(json.dumps(frozen), encoding="utf-8")
    observed.write_text(json.dumps(_private_measurement(frozen)), encoding="utf-8")
    marker = registered.stat().st_mtime_ns
    os.utime(observed, ns=(marker - 1, marker - 1))
    monkeypatch.setattr(sys, "argv", ["score_source_first_display.py", "--score",
        str(observed), "--private-holdout", str(registered)])
    assert gate.main() == 1
    assert json.loads(capsys.readouterr().out) == {
        "status": "invalid_local_observations", "candidate_passed": False}
    os.utime(observed, ns=(marker + 1_000_000_000, marker + 1_000_000_000))
    assert gate.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["candidate_passed"]
    assert report["holdout_preregistration_sha256"] == frozen["holdout_manifest_sha256"]


def _independent_inputs(*, source_labels=None):
    candidate, review, roster, *exclusions = _private_inputs()
    if source_labels is None:
        source_labels = {"source_fidelity": "Yes", "excerpt_sufficient": "Yes", "page_useful": "Yes"}
    for row in candidate["positives"]:
        row["relation"] = "definition"
        row["quote"] = "Public synthetic source quote."
        row["source"]["quote_sha256"] = hashlib.sha256(b"Public synthetic source quote.").hexdigest()
    source_review = {"schema": "independent_source_sufficiency_frozen_v1",
                    "source_origin": "original_local_pdf_pages", "frozen_at_utc": "2026-01-01T00:00:00Z",
                    "runtime_evaluated": False, "owner_labels_immutable": True,
                    "provider_calls": 0, "database_reads": 0, "database_writes": 0,
                    "positives": [{**deepcopy(row), "review_authority": "independent_original_pdf_review",
                                   "labels": deepcopy(source_labels)}
                                  for row in candidate["positives"]]}
    artifact = json.dumps(source_review).encode()
    for row, reviewed in zip(candidate["positives"], source_review["positives"], strict=True):
        row["source_review_case_sha256"] = gate._digest(reviewed)
        row["reviewed_quote_sha256"] = reviewed["source"]["quote_sha256"]
    provenance = {
        "schema": "independent_source_review_provenance_v1",
        "reviewer_kind": "independent_agent", "reviewer_id": "pdf_reviewer",
        "independent_of_runtime_selection": True, "original_pdf_inspected": True,
        "source_fidelity_inspected": True, "excerpt_relation_and_context_inspected": True,
        "source_review_artifact_sha256": hashlib.sha256(artifact).hexdigest(),
        "source_review_frozen_at_utc": "2026-01-01T00:00:00Z",
        "frozen_before_runtime": True, "runtime_evaluated": False,
    }
    candidate.update(schema=gate.INDEPENDENT_CANDIDATE_SCHEMA,
                     discovery_policy_id=gate.INDEPENDENT_DISCOVERY_POLICY,
                     runtime_evaluated=False, provenance=provenance)
    review.update(schema=gate.INDEPENDENT_REVIEW_SCHEMA, provenance=deepcopy(provenance),
                  candidate_roster_sha256=gate._digest(candidate))
    roster["schema"] = gate.INDEPENDENT_ROSTER_SCHEMA
    for row in roster["cases"]:
        row.update(owner_reviewed_gold=False, independently_reviewed_gold=True)
    roster["roster_sha256"] = gate._digest({"scope": roster["scope"], "cases": roster["cases"]})
    return candidate, review, roster, exclusions, artifact


def _freeze_independent():
    candidate, review, roster, exclusions, artifact = _independent_inputs()
    return gate.freeze_private_holdout(candidate, review, roster, *exclusions,
                                      source_review_artifact=artifact)


def _independent_measurement(frozen):
    measurement = _private_measurement(frozen)
    measurement["schema"] = gate.INDEPENDENT_MEASUREMENT_SCHEMA
    evaluated = gate._utc_time(frozen["registered_at_utc"]) + timedelta(seconds=1)
    measurement["evaluated_at_utc"] = evaluated.isoformat().replace("+00:00", "Z")
    provenance = frozen["review_provenance"]
    for row in measurement["observations"]:
        if row["case_id"] in frozen["gold_keys"]:
            row.update(owner_reviewed_gold=False, owner_reviewed_windows=False,
                       independently_reviewed_gold=True, independently_reviewed_windows=True,
                       independent_review={**{key: provenance[key] for key in (
                           "reviewer_kind", "reviewer_id", "source_review_artifact_sha256")},
                           "reviewed_at_utc": measurement["evaluated_at_utc"]})
    return measurement


def test_independent_pdf_review_freezes_and_scores_without_owner_metadata_spoofing():
    frozen = _freeze_independent()
    assert frozen["schema"] == gate.INDEPENDENT_HOLDOUT_SCHEMA
    assert "owner_review_sha256" not in frozen
    assert "question" not in json.dumps(frozen)
    assert frozen["discovery_policy_id"] == gate.INDEPENDENT_DISCOVERY_POLICY
    gate.validate_private_holdout(frozen)
    report = gate.score_private_holdout(_independent_measurement(frozen), frozen)
    assert report["candidate_passed"]
    assert report["all_windows_reviewed"]
    assert not report["all_windows_owner_reviewed"]
    assert report["holdout_useful_by_category"] == {group: 4 for group in gate._GROUPS}


@pytest.mark.parametrize("field", [
    "reviewer_kind", "reviewer_id", "independent_of_runtime_selection", "original_pdf_inspected",
    "source_fidelity_inspected", "excerpt_relation_and_context_inspected",
    "source_review_artifact_sha256", "source_review_frozen_at_utc", "frozen_before_runtime", "runtime_evaluated",
])
def test_independent_review_requires_all_explicit_provenance_fields(field):
    candidate, review, roster, exclusions, artifact = _independent_inputs()
    del candidate["provenance"][field]
    with pytest.raises(gate.InvalidObservation, match="invalid_review_provenance"):
        gate.freeze_private_holdout(candidate, review, roster, *exclusions,
                                    source_review_artifact=artifact)


@pytest.mark.parametrize("field,value", [
    ("reviewer_kind", "owner"), ("reviewer_id", ""), ("original_pdf_inspected", False),
    ("independent_of_runtime_selection", False), ("runtime_evaluated", True),
    ("source_review_frozen_at_utc", "2026-01-01T00:00:00"),
    ("source_review_frozen_at_utc", "2999-01-01T00:00:00Z"),
])
def test_independent_review_rejects_invalid_or_runtime_derived_provenance(field, value):
    candidate, review, roster, exclusions, artifact = _independent_inputs()
    candidate["provenance"][field] = value
    with pytest.raises(gate.InvalidObservation, match="invalid_review_provenance"):
        gate.freeze_private_holdout(candidate, review, roster, *exclusions,
                                    source_review_artifact=artifact)


def test_independent_review_binds_actual_artifact_bytes_and_separate_yes_labels():
    candidate, review, roster, exclusions, artifact = _independent_inputs()
    with pytest.raises(gate.InvalidObservation, match="source_review_artifact_changed"):
        gate.freeze_private_holdout(candidate, review, roster, *exclusions)
    with pytest.raises(gate.InvalidObservation, match="source_review_artifact_changed"):
        gate.freeze_private_holdout(candidate, review, roster, *exclusions,
                                    source_review_artifact=artifact + b"changed")
    review["labels"]["X01"]["excerpt_sufficient"] = "No"
    with pytest.raises(gate.InvalidObservation, match="holdout_not_independently_reviewed"):
        gate.freeze_private_holdout(candidate, review, roster, *exclusions,
                                    source_review_artifact=artifact)


def test_context_discovery_cannot_be_spoofed_as_standard_or_independent_gold():
    candidate, review, roster, *exclusions = _private_inputs()
    candidate.update(schema="source_sufficiency_context_candidates_v1",
                     source_snapshot_verified_twice=True, runtime_evaluated=False)
    review["candidate_roster_sha256"] = gate._digest(candidate)
    with pytest.raises(gate.InvalidObservation):
        gate.freeze_private_holdout(candidate, review, roster, *exclusions)


def test_independent_windows_require_post_runtime_review_and_matching_reviewer():
    frozen = _freeze_independent()
    measurement = _independent_measurement(frozen)
    measurement["evaluated_at_utc"] = frozen["registered_at_utc"]
    with pytest.raises(gate.InvalidObservation, match="measurement_predates_registration"):
        gate.score_private_holdout(measurement, frozen)
    for field in ("reviewer_id", "source_review_artifact_sha256", "reviewed_at_utc"):
        measurement = _independent_measurement(frozen)
        _row(measurement["observations"], "X01")["independent_review"][field] = (
            "2026-01-01T00:00:00Z" if field == "reviewed_at_utc" else "changed")
        with pytest.raises(gate.InvalidObservation, match="invalid_window_review_provenance"):
            gate.score_private_holdout(measurement, frozen)
    measurement = _independent_measurement(frozen)
    _row(measurement["observations"], "X01")["owner_reviewed_gold"] = True
    with pytest.raises(gate.InvalidObservation, match="invalid_review_authority"):
        gate.score_private_holdout(measurement, frozen)
    measurement = _independent_measurement(frozen)
    _row(measurement["observations"], "X01")["independently_reviewed_windows"] = False
    assert not gate.score_private_holdout(measurement, frozen)["candidate_passed"]
    with pytest.raises(gate.InvalidObservation):
        gate.score(_independent_measurement(frozen)["observations"])


@pytest.mark.parametrize("field", ["question", "previous_turn", "category", "relation", "source_review_case_sha256", "reviewed_quote_sha256", "source"])
def test_independent_artifact_prevents_relabeling_or_source_identity_swaps(field):
    candidate, review, roster, exclusions, artifact = _independent_inputs()
    if field == "source":
        candidate["positives"][0][field]["page_number"] = 99
    else:
        candidate["positives"][0][field] = "changed"
    review["candidate_roster_sha256"] = gate._digest(candidate)
    with pytest.raises(gate.InvalidObservation, match="source_review_identity_changed"):
        gate.freeze_private_holdout(candidate, review, roster, *exclusions,
                                    source_review_artifact=artifact)


def test_independent_artifact_preserves_exact_lowercase_yes_labels_and_bytes():
    labels = {"source_fidelity": "yes", "excerpt_sufficient": "yes", "page_useful": "yes"}
    candidate, review, roster, exclusions, artifact = _independent_inputs(source_labels=labels)
    original_hash = hashlib.sha256(artifact).hexdigest()
    frozen = gate.freeze_private_holdout(candidate, review, roster, *exclusions,
                                        source_review_artifact=artifact)
    assert frozen["review_provenance"]["source_review_artifact_sha256"] == original_hash
    assert json.loads(artifact)["positives"][0]["labels"] == labels
    assert gate.score_private_holdout(_independent_measurement(frozen), frozen)["candidate_passed"]


@pytest.mark.parametrize("labels", [
    {"source_fidelity": "yes", "excerpt_sufficient": "no", "page_useful": "yes"},
    {"source_fidelity": "yes", "excerpt_sufficient": "Yes", "page_useful": "yes"},
    {"source_fidelity": "yes", "excerpt_sufficient": "unknown", "page_useful": "yes"},
    {"source_fidelity": True, "excerpt_sufficient": True, "page_useful": True},
])
def test_independent_artifact_rejects_non_yes_and_mixed_original_labels(labels):
    candidate, review, roster, exclusions, artifact = _independent_inputs(source_labels=labels)
    with pytest.raises(gate.InvalidObservation, match="source_review_identity_changed"):
        gate.freeze_private_holdout(candidate, review, roster, *exclusions,
                                    source_review_artifact=artifact)


def test_context_candidates_are_excluded_prior_pages_with_their_real_schema():
    candidate, review, roster, old_raw, alternatives_raw, (prior_raw,) = _private_inputs()
    prior = json.loads(prior_raw)
    prior.update(schema="source_sufficiency_context_candidates_v1",
                 source_snapshot_verified_twice=True, runtime_evaluated=False)
    del prior["source_frozen"]
    changed_raw = json.dumps(prior).encode()
    candidate["excluded_development_sources"]["exposed_candidate_packet_sha256"] = [hashlib.sha256(changed_raw).hexdigest()]
    review["candidate_roster_sha256"] = gate._digest(candidate)
    frozen = gate.freeze_private_holdout(candidate, review, roster, old_raw, alternatives_raw, (changed_raw,))
    assert frozen["verified_prior_page_count"] == 3
    prior["source_snapshot_verified_twice"] = False
    changed_raw = json.dumps(prior).encode()
    candidate["excluded_development_sources"]["exposed_candidate_packet_sha256"] = [hashlib.sha256(changed_raw).hexdigest()]
    review["candidate_roster_sha256"] = gate._digest(candidate)
    with pytest.raises(gate.InvalidObservation, match="exclusion_proof_changed"):
        gate.freeze_private_holdout(candidate, review, roster, old_raw, alternatives_raw, (changed_raw,))


def test_pdf_page_gold_with_missing_current_chunk_never_passes_display_gate():
    frozen = _freeze_independent()
    measurement = _independent_measurement(frozen)
    for row in measurement["observations"]:
        if row["case_id"] in frozen["gold_keys"]:
            row.update(result_kind="no_match", windows=[])
    report = gate.score_private_holdout(measurement, frozen)
    assert report["all_windows_reviewed"]
    assert report["holdout_useful_hit_at_3"] == 0
    assert not report["candidate_passed"]


def test_independent_freeze_cli_requires_separate_artifact_and_preserves_authority(tmp_path, monkeypatch, capsys):
    candidate, review, roster, (old_raw, alternatives_raw, (development_raw,)), artifact = _independent_inputs()
    paths = {name: tmp_path / f"{name}.json" for name in (
        "candidate", "review", "roster", "old", "alternatives", "development", "artifact", "registered")}
    for name, content in (("candidate", candidate), ("review", review), ("roster", roster)):
        paths[name].write_text(json.dumps(content), encoding="utf-8")
    for name, raw in (("old", old_raw), ("alternatives", alternatives_raw),
                      ("development", development_raw), ("artifact", artifact)):
        paths[name].write_bytes(raw)
    argv = ["score_source_first_display.py", "--freeze-holdout",
            "--candidate", str(paths["candidate"]), "--independent-review", str(paths["review"]),
            "--source-review-artifact", str(paths["artifact"]), "--roster", str(paths["roster"]),
            "--old-holdout", str(paths["old"]), "--old-alternatives", str(paths["alternatives"]),
            "--development-packet", str(paths["development"]), "--output", str(paths["registered"])]
    monkeypatch.setattr(sys, "argv", argv)
    assert gate.main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "private_holdout_frozen"
    frozen = json.loads(paths["registered"].read_text())
    assert frozen["schema"] == gate.INDEPENDENT_HOLDOUT_SCHEMA
    assert frozen["review_provenance"]["reviewer_kind"] == "independent_agent"
    assert "owner_review_sha256" not in frozen
