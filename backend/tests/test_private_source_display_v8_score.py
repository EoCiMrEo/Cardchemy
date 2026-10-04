"""Provider-free v8 review reuse; all source, message and key inputs are synthetic."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from uuid import uuid4

import pytest

from app.ai import source_judgment_visual_v2 as v2
from app.ai import source_judgment_visual_v5 as v3
from app.ai.source_navigation_context_v2 import resolve_subject_context
from test_private_source_display_v6_score import packets as old_packets, seal
from tests.test_source_judgment_visual import candidates

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import score_private_source_display_v8 as scorer
import navigation_raw_query_projection_v1 as raw_projection


NOW = datetime(2026, 10, 2, 0, 3, tzinfo=timezone.utc)
SOURCE = (Path(__file__).resolve().parents[1] / "app/ai/source_navigation.py").read_bytes()
RAW_RESOLVER = raw_projection.from_production_source(SOURCE, source_sha256=sha256(SOURCE).hexdigest())


def encode(value):
    return v3.canonical(value)


def digest(value):
    return sha256(encode(value)).hexdigest()


def fixture(*, labels_change=None, component="private_holdout", unicode_source=False,
            clear_question="What does spectral index measure?"):
    roster, labels, measured = old_packets()
    if component == "exposed_seed":
        ids = sorted(scorer.SEEDS) + ["N12", "U01", "N02"]
        for body in (roster, labels, measured):
            template = deepcopy(body["cases"][0])
            body["cases"] = [dict(deepcopy(template), case_id=cid) for cid in ids]
        roster["component"] = component
        for index, row in enumerate(roster["cases"]):
            row["form"] = "direct" if row["case_id"] in scorer.SEEDS else "control"
            row["gold_page_key"] = digest(f"seed-gold-{index}")
            if row["case_id"] in ("U01", "N02"):
                row.update(gold_page_key=None, require_empty=True)
    principal, subject = uuid4(), uuid4()
    requests, gold = [], []
    for index, row in enumerate(roster["cases"], 1):
        followup = index in (9, 10)
        question = "How does it work?" if followup else clear_question
        prior = "Define spectral index" if followup else ""
        gold.append({"case_id": row["case_id"], "question": question, "previous_turn": prior})
        source = candidates()
        if unicode_source:
            source[0]["context"] = source[0]["context"].replace("concrete", "cóncrete")
        local_document, local_revision = str(uuid4()), str(uuid4())
        for item in source:
            item["document_id"] = "D01"
            item["image"]["document_id"] = "D01"
        old = v2.build_request(question, source, group_id="G01")
        row["request_sha256"] = sha256(scorer._legacy_request_bytes(old)).hexdigest()
        row["candidates"] = [{"id": item["id"], "page_key": digest([local_document, item["page"]]),
            "cue_sha256": sha256(item["cue"].encode()).hexdigest(), "pdf_sha256": item["pdf_sha256"]}
            for item in source]
        labels["cases"][index - 1]["candidates"] = [dict(item, page_useful="Yes", cue_useful="Yes")
            for item in row["candidates"]]
        measured["cases"][index - 1]["displayed"] = [dict(row["candidates"][0],
            **dict.fromkeys(scorer.INTEGRITY, True))]
        if row["require_empty"]:
            for item in labels["cases"][index - 1]["candidates"]:
                item.update(page_useful="No", cue_useful="No")
            measured["cases"][index - 1].update(state="no_match", displayed=[])
        current = v3.AdmissionUserMessage(uuid4(), principal, uuid4(), subject,
            sha256(question.encode()).hexdigest(), NOW - timedelta(seconds=10), NOW + timedelta(hours=2))
        preceding = (v3.AdmissionUserMessage(uuid4(), principal, current.thread_id, subject,
            sha256(prior.encode()).hexdigest(), NOW - timedelta(seconds=20), NOW + timedelta(hours=2))
            if followup else None)
        snapshot = v3.SubjectAdmissionSnapshot(current, preceding, 3, "e" * 64,
            NOW - timedelta(seconds=9), not followup)
        raw = None if followup else question
        anchor = resolve_subject_context(question, (("user", prior),) if prior else (),
                                         raw_navigation_query=raw).anchor
        new = v3.build_request(question, source, group_id="G01", snapshot=snapshot, checked_at=NOW,
            raw_navigation_query=raw, preceding_question=prior or None, anchor=anchor)
        requests.append({"case_id": row["case_id"], "legacy_request": old, "request": new,
            "admission_snapshot": scorer.admission_packet(snapshot), "raw_navigation_query": raw,
            "preceding_question": prior or None, "checked_at_utc": NOW.isoformat(),
            "source_bindings": [{"id": item["id"], "document_id": local_document,
                "content_revision_id": local_revision, "page_number": item["page"]} for item in source]})
    stage1 = {"schema": "synthetic-frozen-question-review", "cases": gold}
    roster["stage1_sha256"] = digest(stage1)
    roster_raw = encode(roster)
    roster_sha = sha256(roster_raw).hexdigest()
    labels["roster_sha256"] = roster_sha
    if labels_change:
        labels_change(labels)
    labels_raw = encode(labels)
    labels_sha = sha256(labels_raw).hexdigest()
    receipt, key_sha = seal(roster_sha, labels_sha, labels["frozen_at_utc"])
    packet = {"schema": scorer.SCHEMA + "_requests", "legacy_roster_sha256": roster_sha,
        "scope": {"principal_id": str(principal), "subject_id": str(subject),
            "corpus_revision": 3, "embedding_space_hash": "e" * 64}, "cases": requests}
    return {"roster": roster, "labels": labels, "stage1": stage1, "receipt": receipt,
            "key_sha": key_sha, "packet": packet, "runtime_sha": digest("new-v8-runtime"),
            "base_measured": measured}


def freeze(values):
    return scorer.freeze_bridge(encode(values["roster"]), encode(values["labels"]), encode(values["stage1"]),
        encode(values["packet"]), roster_sha256=digest(values["roster"]),
        labels_sha256=digest(values["labels"]), request_packet_sha256=digest(values["packet"]),
        review_receipt_bytes=encode(values["receipt"]), review_receipt_sha256=digest(values["receipt"]),
        trusted_review_key_sha256=values["key_sha"], runtime_sha256=values["runtime_sha"],
        frozen_at_utc="2026-10-02T00:04:00Z", raw_query_resolver=RAW_RESOLVER)


def observations(values, bridge):
    rows = []
    by_case = {row["case_id"]: row for row in bridge["cases"]}
    for source in values["base_measured"]["cases"]:
        binding = by_case[source["case_id"]]
        rows.append({**source, "request_sha256": binding["request_sha256"],
            "admission_sha256": binding["admission_sha256"],
            "embedding_input_sha256": binding["current_question_sha256"], "context_rechecked": True})
    return {"schema": scorer.SCHEMA + "_measurement", "policy": scorer.POLICY,
        "contract": scorer.CONTRACT, "runtime_sha256": values["runtime_sha"],
        "bridge_sha256": digest(bridge), "executed_at_utc": "2026-10-02T00:05:00Z", "cases": rows}


def score(values, *, bridge=None, measured=None):
    bridge = freeze(values) if bridge is None else bridge
    measured = observations(values, bridge) if measured is None else measured
    return scorer.score(encode(values["roster"]), encode(values["labels"]), encode(values["stage1"]),
        encode(values["packet"]), encode(bridge), encode(measured), roster_sha256=digest(values["roster"]),
        labels_sha256=digest(values["labels"]), request_packet_sha256=digest(values["packet"]),
        bridge_sha256=digest(bridge), measurement_sha256=digest(measured),
        review_receipt_bytes=encode(values["receipt"]), review_receipt_sha256=digest(values["receipt"]),
        trusted_review_key_sha256=values["key_sha"], runtime_sha256=values["runtime_sha"],
        raw_query_resolver=RAW_RESOLVER)


def test_unchanged_signed_review_scores_actual_new_wire_without_rewriting_inputs():
    values = fixture()
    before = deepcopy(values)
    bridge = freeze(values)
    assert sum(row["context_status"] == "resolved_literal_subject" for row in bridge["cases"]) == 2
    assert values["packet"]["cases"][0]["request"] == values["packet"]["cases"][0]["legacy_request"]
    assert values["packet"]["cases"][8]["request"] != values["packet"]["cases"][8]["legacy_request"]
    result = score(values, bridge=bridge)
    assert values == before
    assert result["component_passed"] and not result["release_gate_passed"]
    assert result["schema"] == scorer.SCHEMA + "_aggregate" and result["unchanged_review_reused"] is True
    assert result["runtime_sha256"] == values["runtime_sha"] and result["useful_hit_at_3"] == 12


def test_historical_ascii_review_hash_is_distinct_from_identical_current_utf8_wire():
    values = fixture(unicode_source=True)
    old_request = values["packet"]["cases"][0]["legacy_request"]
    assert sha256(scorer._legacy_request_bytes(old_request)).hexdigest() != digest(old_request)
    assert values["packet"]["cases"][0]["request"] == old_request
    bridge = freeze(values)
    assert bridge["legacy_request_encoding"] == "v6_review_ascii_json_v1"
    assert bridge["current_request_encoding"] == "visual_wire_utf8_json_v5"
    assert bridge["cases"][0]["request_sha256"] == digest(old_request)
    assert score(values, bridge=bridge)["component_passed"]


def test_current_learning_verb_ignore_is_clear_without_subject_transfer_or_question_rewrite():
    question = "What limitation makes Bag-of-Words ignore word order?"
    assert RAW_RESOLVER(question) == question
    values = fixture(clear_question=question)
    bridge = freeze(values)
    first = values["packet"]["cases"][0]
    assert first["admission_snapshot"]["schema_version"] == "literal_subject_admission_v2"
    assert first["admission_snapshot"]["preceding"] is None
    assert first["preceding_question"] is None
    assert first["request"] == first["legacy_request"]
    assert json.loads(first["request"]["contents"][0]["parts"][0]["text"])["question"] == question
    assert bridge["cases"][0]["current_question_sha256"] == sha256(question.encode()).hexdigest()
    assert bridge["cases"][0]["context_status"] == "clear_current_question"


def test_immutable_v7_admission_cannot_be_spliced_into_new_v8_bridge():
    values = fixture()
    values["packet"]["cases"][0]["admission_snapshot"]["schema_version"] = "literal_subject_admission_v1"
    with pytest.raises(scorer.ScoreError):
        freeze(values)


@pytest.mark.parametrize("change", ["missing", "document", "page", "revision", "wire_alias"])
def test_server_aliases_require_signed_local_page_identity(change):
    values = fixture()
    row = values["packet"]["cases"][0]
    if change == "missing":
        row["source_bindings"].pop()
    elif change == "document":
        row["source_bindings"][0]["document_id"] = str(uuid4())
    elif change == "page":
        row["source_bindings"][0]["page_number"] += 1
    elif change == "revision":
        row["source_bindings"][1]["content_revision_id"] = str(uuid4())
    else:
        parts = row["legacy_request"]["contents"][0]["parts"]
        source = json.loads(parts[1]["text"])
        source["document_id"] = "D02"
        parts[1]["text"] = encode(source).decode()
    with pytest.raises(scorer.ScoreError, match="source_alias_binding_invalid|fresh_review_required"):
        freeze(values)


@pytest.mark.parametrize("change", ["new_cue", "new_image", "new_question", "extra_history", "new_config"])
def test_unreviewed_wire_changes_need_fresh_review(change):
    values = fixture()
    wire = values["packet"]["cases"][0]["request"]
    parts = wire["contents"][0]["parts"]
    if change == "new_cue":
        parts[1]["text"] = parts[1]["text"].replace("Exact cue", "Changed cue")
    elif change == "new_image":
        parts[2]["inline_data"]["data"] += "AAAA"
    elif change == "new_question":
        parts[0]["text"] = parts[0]["text"].replace("measure", "mean")
    elif change == "extra_history":
        wire["contents"].append({"role": "user", "parts": [{"text": "old question"}]})
    else:
        wire["generationConfig"]["maxOutputTokens"] = 8192
    with pytest.raises(scorer.ScoreError, match="fresh_review_required"):
        freeze(values)


def test_prior_question_meaning_is_pinned_by_original_signed_stage1():
    values = fixture()
    row = values["packet"]["cases"][8]
    row["preceding_question"] = "Define albedo"
    row["admission_snapshot"]["preceding"]["content_sha256"] = sha256(b"Define albedo").hexdigest()
    with pytest.raises(scorer.ScoreError, match="fresh_review_required"):
        freeze(values)


@pytest.mark.parametrize("raw_clear", [True, False])
def test_clarity_cannot_be_forged_in_packet_or_admission_snapshot(raw_clear):
    values = fixture()
    row = values["packet"]["cases"][8 if raw_clear else 0]
    if raw_clear:
        row["raw_navigation_query"] = values["stage1"]["cases"][8]["question"]
        row["preceding_question"] = None
        row["admission_snapshot"].update(raw_question_clear=True, preceding=None)
        row["request"] = deepcopy(row["legacy_request"])
    else:
        row["raw_navigation_query"] = None
        row["admission_snapshot"]["raw_question_clear"] = False
    with pytest.raises(scorer.ScoreError, match="raw_question_binding_invalid"):
        freeze(values)
    values["stage1"]["cases"][8]["previous_turn"] = "Define albedo"
    with pytest.raises(scorer.ScoreError, match="input_sha_invalid"):
        freeze(values)


@pytest.mark.parametrize("change", ["signature", "labels", "key", "review_after_bridge"])
def test_legacy_review_signature_is_validated_independently(change):
    values = fixture()
    if change == "signature":
        values["receipt"]["reviewer_signature_hex"] = "00" * 64
    elif change == "labels":
        values["labels"]["cases"][0]["candidates"][0]["cue_useful"] = "No"
    elif change == "key":
        values["key_sha"] = digest("untrusted key")
    else:
        values["labels"]["frozen_at_utc"] = "2026-10-02T00:06:00Z"
    with pytest.raises(scorer.ScoreError):
        freeze(values)


@pytest.mark.parametrize("change", ["candidate_omission", "duplicate", "wrong_scope", "later_prior", "assistant_prior"])
def test_new_packet_requires_complete_same_scope_admission(change):
    values = fixture()
    row = values["packet"]["cases"][8]
    if change == "candidate_omission":
        values["packet"]["cases"].pop()
    elif change == "duplicate":
        values["packet"]["cases"].append(deepcopy(row))
    elif change == "wrong_scope":
        row["admission_snapshot"]["current"]["subject_id"] = str(uuid4())
    elif change == "later_prior":
        row["admission_snapshot"]["preceding"]["created_at"] = "2026-10-02T00:03:00Z"
    else:
        row["admission_snapshot"]["preceding"]["role"] = "assistant"
    with pytest.raises(scorer.ScoreError):
        freeze(values)


@pytest.mark.parametrize("field", ["request_sha256", "admission_sha256", "embedding_input_sha256"])
def test_measurement_cannot_splice_request_admission_or_nonraw_embedding(field):
    values = fixture()
    bridge = freeze(values)
    measured = observations(values, bridge)
    measured["cases"][0][field] = digest("changed")
    with pytest.raises(scorer.ScoreError, match="measurement_context_invalid"):
        score(values, bridge=bridge, measured=measured)


def test_expired_context_or_missing_context_recheck_cannot_pass():
    values = fixture()
    bridge = freeze(values)
    measured = observations(values, bridge)
    measured["cases"][0]["context_rechecked"] = False
    result = score(values, bridge=bridge, measured=measured)
    assert result["context_failures"] == 1 and not result["component_passed"]
    measured["executed_at_utc"] = "2026-10-02T03:00:00Z"
    with pytest.raises(scorer.ScoreError, match="measurement_context_invalid"):
        score(values, bridge=bridge, measured=measured)


def test_new_bridge_is_frozen_before_measurements_and_has_separate_runtime_identity():
    values = fixture()
    values["runtime_sha"] = values["roster"]["runtime_sha256"]
    with pytest.raises(scorer.ScoreError, match="bridge_runtime_invalid"):
        freeze(values)
    values["runtime_sha"] = digest("new-runtime")
    bridge = freeze(values)
    measured = observations(values, bridge)
    measured["executed_at_utc"] = bridge["frozen_at_utc"]
    with pytest.raises(scorer.ScoreError, match="measurement_binding_invalid"):
        score(values, bridge=bridge, measured=measured)


def test_every_card_unknown_and_missing_case_still_counts_under_unchanged_metrics():
    def unknown(labels):
        for row in labels["cases"][:3]:
            row["candidates"][1]["cue_useful"] = "Unsure"
    values = fixture(labels_change=unknown)
    bridge = freeze(values)
    measured = observations(values, bridge)
    for row, source in zip(measured["cases"][:3], values["roster"]["cases"][:3], strict=True):
        row["displayed"].append(dict(source["candidates"][1], **dict.fromkeys(scorer.INTEGRITY, True)))
    result = score(values, bridge=bridge, measured=measured)
    assert result["component_passed"] and result["displayed_cards"] == 15
    assert result["useful_cards"] == 12 and result["unknown_cards"] == 3
    assert result["displayed_usefulness"] == .8
    measured["cases"].pop()
    result = score(values, bridge=bridge, measured=measured)
    assert not result["component_passed"] and result["case_denominator"] == 12
    assert result["missing_cases"] == 1 and result["displayed_cards"] == 14


def test_per_form_and_one_attempt_policy_gates_remain_independent_of_card_precision():
    values = fixture()
    bridge = freeze(values)
    measured = observations(values, bridge)
    for row in measured["cases"][:2]:
        row.update(state="no_match", displayed=[])
    result = score(values, bridge=bridge, measured=measured)
    assert result["useful_hit_at_3"] == 10 and result["displayed_usefulness"] == 1
    assert not result["gates"]["per_form_hits"] and not result["component_passed"]
    measured = observations(values, bridge)
    measured["cases"][0]["automatic_retries"] = 1
    result = score(values, bridge=bridge, measured=measured)
    assert result["policy_violations"] == 1 and not result["component_passed"]


@pytest.mark.parametrize("control", ["U01", "N02", "N12"])
def test_exposed_seed_negative_controls_and_n12_are_not_erased_by_bridge(control):
    values = fixture(component="exposed_seed")
    bridge = freeze(values)
    measured = observations(values, bridge)
    assert score(values, bridge=bridge, measured=measured)["component_passed"]
    row = next(row for row in measured["cases"] if row["case_id"] == control)
    if control == "N12":
        row.update(state="no_match", displayed=[])
    else:
        row.update(state="clarification_needed")
    result = score(values, bridge=bridge, measured=measured)
    assert not result["component_passed"]
    assert result["case_denominator"] == len(scorer.SEEDS) + 3
    assert not result["gates"]["n12_control" if control == "N12" else "negative_controls"]


def test_pure_module_has_no_provider_settings_file_database_or_activation_access():
    source = Path(scorer.__file__).read_text()
    assert "Settings(" not in source and "httpx" not in source and "os.environ" not in source
    assert ".read_bytes(" not in source and ".read_text(" not in source and "AsyncSession" not in source
    assert "from app.config" not in source and "from app.services" not in source
