"""Synthetic candidate discovery and private packet boundaries; no live corpus."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import asyncio
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import build_private_source_sufficiency_packet as packet
import evaluate_private_source_display as display


_TEXTS = (
    "POS means part-of-speech tagging: words receive a grammatical category in the lecture example.",
    "RNN means recurrent neural network: a sequence model carries a hidden state over time.",
    "A language model assigns probability to a word sequence and predicts the next word.",
    "Named entity recognition identifies a person, organization or location mentioned in text.",
    "The attention mechanism assigns a weight to each token according to relevance.",
    "RNN sequence processing updates a hidden state over time as new words arrive.",
    "Perplexity measures uncertainty in the probability predicted by a language model.",
    "F1 combines precision and recall with their harmonic mean for a classifier.",
    "Smoothing avoids zero probability for unseen terms during language modeling.",
    "TF-IDF is useful because rare terms can receive more informative weights than common terms.",
    "A vocabulary maps tokens to input IDs through an index used by the model.",
    "Byte-pair encoding forms subword units by repeatedly merging frequent pairs.",
    "Bag-of-Words ignores word order and context when it represents text.",
    "Naive Bayes assumes features are conditionally independent given the class.",
    "Sentiment analysis is used to analyze customer feedback and product reviews.",
    "Named entity recognition is used for information extraction in medical documents.",
    "ROUGE measures recall-based overlap with a reference summary.",
    "A term-document matrix represents term counts for each document in the corpus.",
    "Euclidean distance is sensitive to scale and magnitude and not ideal for sparse text vectors.",
    "Machine translation converts texts and documents between languages.",
    "Naive Bayes selects the class with the highest posterior probability.",
    "Removing stop words filters uninformative noise from text.",
)


def synthetic_corpus():
    documents = [uuid4() for _ in range(3)]
    chunks, pages = [], {}
    slots = {value: index + 1 for index, value in enumerate(documents)}
    for index, content in enumerate(_TEXTS, 1):
        chunk = SimpleNamespace(chunk_id=uuid4(), document_id=documents[(index-1) % 3],
            document_title=f"Synthetic lecture {index % 3}", page_number=index,
            content_revision_id=uuid4(), index_revision_id=uuid4(),
            corpus_revision=4, embedding_space_hash="a"*64,
            content=content)
        chunks.append(chunk)
        pages[chunk.chunk_id] = "Page header\n" + content + "\nPage footer"
    return chunks, pages, slots


def synthetic_manifest():
    chunks, pages, slots = synthetic_corpus()
    positives, controls, discovery = packet.discover_candidates(chunks, pages, slots, set())
    scope = {"principal_id": str(uuid4()), "subject_id": str(uuid4()),
        "document_ids": [], "corpus_revision": 4, "space_hash": "a"*64}
    return {"schema": packet.SCHEMA, "status": "candidate_unreviewed", "source_frozen": True,
        "owner_reviewed": False, "authored_templates_sha256": packet._templates_sha(),
        "scope": scope, "excluded_development_sources": {"old_gold_sha256": "b"*64,
            "old_alternatives_sha256": "c"*64, "old_review_pages_excluded": 0},
        "positives": positives, "insufficient_pairs": controls, "discovery": discovery,
        "provider_calls": 0, "database_writes": 0}, chunks, pages


def review(manifest):
    labels = {}
    for row in manifest["positives"]:
        labels[row["case_id"]] = {"source_fidelity": "Yes", "excerpt_sufficient": "Yes",
                                  "page_useful": "Yes"}
    for row in manifest["insufficient_pairs"]:
        labels[row["case_id"]] = {"source_fidelity": "Yes", "excerpt_sufficient": "No",
                                  "page_useful": "No"}
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {"candidate_roster_sha256": packet._sha(canonical), "labels": labels}


def test_default_preflight_reads_no_database_or_provider():
    script = Path(packet.__file__)
    code = ("import runpy,sys;sys.argv=['packet'];"
            f"runpy.run_path({str(script)!r},run_name='__main__')")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    assert info["status"] == "preflight_unexecuted"
    assert info["database_reads"] == info["database_writes"] == info["provider_calls"] == 0
    assert info["all_labels_unreviewed"] is True
    assert info["target_positive_cases"] == 12
    assert info["target_insufficient_pairs"] == 16


def authored_case(**changes):
    row = {"case_id": "X01", "relation": "mechanism", "category": "paraphrase",
        "question": "How does A+B identify text features?", "entity": "A+B",
        "evidence": ["filter"], "requirements": [["applies", "uses"], ["extracts"]],
        "previous_turn": ""}
    row.update(changes)
    return row


def write_authored_spec(root, cases):
    path = root / "private-authored.json"
    path.write_text(json.dumps({"schema": packet.AUTHORED_SPEC_SCHEMA, "cases": cases}),
                    encoding="utf-8")
    return path


def test_private_literal_spec_finds_exact_unreviewed_window_without_regex_interpretation(tmp_path):
    path = write_authored_spec(tmp_path, [authored_case()])
    templates, raw_sha = packet._load_authored_spec(path, tmp_path)
    assert raw_sha == packet._sha(path.read_bytes())
    assert packet._templates_sha(templates) != packet._templates_sha()
    content = "A+B\n• Applies a filter that extracts features from tokens."
    assert packet._source_windows(content, templates[0]) == ((0, len(content)),)
    assert packet._source_windows(content.replace("A+B", "AB"), templates[0]) == ()
    document = uuid4()
    chunk = SimpleNamespace(chunk_id=uuid4(), document_id=document,
        document_title="Synthetic", page_number=1, content_revision_id=uuid4(),
        index_revision_id=uuid4(), corpus_revision=4, embedding_space_hash="a"*64,
        content=content)
    positives, controls, discovery = packet.discover_candidates(
        [chunk], {chunk.chunk_id: content}, {document: 1}, set(), templates)
    assert len(positives) == 1 and controls == []
    assert positives[0]["case_id"] == "X01"
    assert set(positives[0]["labels"].values()) == {"unreviewed"}
    assert discovery["counts"]["missing_positive_candidates"] == 11


def test_private_followup_spec_requires_one_resolvable_acronym_and_linked_expansion(tmp_path):
    row = authored_case(case_id="X02", relation="acronym_expansion",
        category="followup", question="What does it stand for?", entity="QBR",
        evidence=["Quarterly Business Review"], requirements=[],
        previous_turn="Where is QBR discussed?")
    templates, _ = packet._load_authored_spec(write_authored_spec(tmp_path, [row]), tmp_path)
    from app.ai.related_evidence import local_followup_query
    assert local_followup_query(templates[0].question,
        (("user", templates[0].previous_turn),)) == "QBR"
    source = "QBR (Quarterly Business Review) is introduced in this example."
    assert packet._source_windows(source, templates[0]) == ((0, len(source)),)
    heading_source = "QBR - Quarterly Business Review\n• Introduces an example for this topic."
    assert packet._source_windows(heading_source, templates[0]) == ((0, len(heading_source)),)
    assert packet._source_windows("QBR and Quarterly Business Review are separate topics.",
        templates[0]) == ()


@pytest.mark.parametrize("change", [
    lambda row: row.update(case_id="A01"),
    lambda row: row.update(case_id="X001"),
    lambda row: row.update(relation="not_a_relation"),
    lambda row: row.update(category="followup"),
    lambda row: row.update(entity=""),
    lambda row: row.update(requirements=[]),
    lambda row: row.update(requirements=[["applies"], ["extracts\nmore"]]),
    lambda row: row.update(previous_turn=None),
    lambda row: row.update(unknown="unexpected"),
    lambda row: row.update(case_id="X01", relation="acronym_expansion",
                           category="followup", question="What does it stand for?",
                           entity="QBR", evidence=["Quarterly Business Review"],
                           requirements=[], previous_turn="Where are QBR and LSA discussed?"),
])
def test_private_authored_spec_rejects_invalid_shape_or_ambiguous_followup(tmp_path, change):
    row = authored_case()
    change(row)
    path = write_authored_spec(tmp_path, [row])
    with pytest.raises(ValueError, match="authored_spec_invalid"):
        packet._load_authored_spec(path, tmp_path)


def test_private_authored_spec_rejects_duplicate_keys_ids_and_excess_bytes(tmp_path):
    path = tmp_path / "private-authored.json"
    path.write_text('{"schema":"private_source_sufficiency_authored_v1",'
        '"schema":"private_source_sufficiency_authored_v1","cases":[]}', encoding="utf-8")
    with pytest.raises(ValueError, match="authored_spec_invalid"):
        packet._load_authored_spec(path, tmp_path)
    write_authored_spec(tmp_path, [authored_case(), authored_case()])
    with pytest.raises(ValueError, match="authored_spec_invalid"):
        packet._load_authored_spec(path, tmp_path)
    path.write_bytes(b" " * (packet._AUTHORED_SPEC_MAX_BYTES + 1))
    with pytest.raises(ValueError, match="authored_spec_invalid"):
        packet._load_authored_spec(path, tmp_path)


def test_private_authored_spec_must_be_within_owner_temp_and_fail_before_db(tmp_path, monkeypatch):
    restricted_root = tmp_path / "restricted"
    restricted_root.mkdir()
    outside = tmp_path / "outside-authored.json"
    outside.write_text(json.dumps({"schema": packet.AUTHORED_SPEC_SCHEMA,
        "cases": [authored_case()]}), encoding="utf-8")
    with pytest.raises(ValueError, match="authored_spec_invalid"):
        packet._load_authored_spec(outside, restricted_root)
    path = write_authored_spec(tmp_path, [authored_case(requirements=[])])
    monkeypatch.setattr(packet, "_output_root", lambda: tmp_path)
    monkeypatch.setattr(packet, "_load_old_exclusions",
        lambda *_args: pytest.fail("old private inputs read before authored spec validation"))
    monkeypatch.setattr(packet, "_authorized_snapshot",
        lambda: pytest.fail("database read before authored spec validation"))
    with pytest.raises(ValueError, match="authored_spec_invalid"):
        asyncio.run(packet.build(tmp_path / "old.json", tmp_path / "alternatives.json", [], path))


def test_private_authored_spec_preflight_never_reads_spec_or_db(tmp_path):
    script = Path(packet.__file__)
    result = subprocess.run([sys.executable, str(script), "--authored-spec",
        str(tmp_path / "missing.json")], capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    assert info["status"] == "preflight_unexecuted"
    assert info["authored_input_requested"] is True
    assert info["authored_templates"] is None
    assert info["database_reads"] == info["provider_calls"] == 0


def test_authored_template_fingerprint_required_for_review_conversion(tmp_path):
    manifest, _, _ = synthetic_manifest()
    templates, _ = packet._load_authored_spec(
        write_authored_spec(tmp_path, [authored_case()]), tmp_path)
    with pytest.raises(ValueError, match="review_binding_invalid"):
        packet.convert_reviewed_roster(manifest, review(manifest), templates)


def test_authored_case_ids_survive_conversion_and_display_roster_validation():
    manifest, _, _ = synthetic_manifest()
    ids = {row["case_id"]: f"X{index:02d}"
           for index, row in enumerate(manifest["positives"], 1)}
    templates = tuple(replace(template(old_id), case_id=new_id)
                      for old_id, new_id in ids.items())
    for row in manifest["positives"]:
        row["case_id"] = ids[row["case_id"]]
    for row in manifest["insufficient_pairs"]:
        row["paired_positive_case_id"] = ids[row["paired_positive_case_id"]]
        row["source_candidate_case_id"] = ids.get(
            row["source_candidate_case_id"], row["source_candidate_case_id"])
    manifest["authored_template_mode"] = packet.AUTHORED_SPEC_SCHEMA
    manifest["authored_templates_sha256"] = packet._templates_sha(templates)
    manifest["authored_spec_sha256"] = "a" * 64
    positive, controls = packet.convert_reviewed_roster(manifest, review(manifest), templates)
    assert len(positive["cases"]) == 12 and len(controls["pairs"]) == 16
    scope_data = positive["scope"]
    scope = display.Scope(UUID(scope_data["principal_id"]), UUID(scope_data["subject_id"]),
        tuple(UUID(value) for value in scope_data["document_ids"]),
        scope_data["corpus_revision"], scope_data["space_hash"])
    cases = tuple(display.Case(row["case_id"], row["question"], UUID(row["gold_document_id"]),
        row["gold_page_number"], row["owner_reviewed_gold"], tuple(map(tuple, row["history"])))
        for row in positive["cases"])
    display.validate_roster(display.FrozenRoster(
        cases, scope, positive["roster_sha256"], positive["runtime_sha256"]))


def test_synthetic_discovery_yields_twelve_distinct_positive_pages_and_paired_controls():
    manifest, chunks, pages = synthetic_manifest()
    positives, controls = manifest["positives"], manifest["insufficient_pairs"]
    assert len(positives) == 12 and len(controls) == 16
    assert manifest["discovery"]["counts"]["positive_by_category"] == {
        "direct": 4, "paraphrase": 4, "followup": 4}
    assert manifest["discovery"]["counts"]["positive_documents"] == 3
    assert manifest["discovery"]["counts"]["positive_distinct_pages"] == 12
    assert all(any(row["relation"] == relation for row in positives) for relation in packet._RELATIONS)
    assert all(sum(row["relation"] == relation for row in controls) >= 2 for relation in packet._RELATIONS)
    by_id = {str(chunk.chunk_id): chunk for chunk in chunks}
    for row in positives + controls:
        source = row["source"]
        chunk = by_id[source["chunk_id"]]
        quote = chunk.content[source["quote_start"]:source["quote_end"]]
        assert 1 <= len(quote) <= 480
        assert packet._sha(chunk.content) == source["chunk_sha256"]
        assert packet._sha(pages[chunk.chunk_id]) == source["page_sha256"]
        assert packet._sha(quote) == source["quote_sha256"]
        assert packet._page_span(pages[chunk.chunk_id], quote) == (
            source["page_reference_start"], source["page_reference_end"])
        assert row["labels"] == {"source_fidelity": "unreviewed",
            "excerpt_sufficient": "unreviewed", "page_useful": "unreviewed"}
    assert all(row["previous_turn"] for row in positives if row["category"] == "followup")
    from app.ai.related_evidence import local_followup_query
    for row in positives:
        if row["category"] == "followup":
            resolved = local_followup_query(row["question"], (("user", row["previous_turn"]),))
            assert resolved is not None and resolved != row["question"]
    by_positive = {row["case_id"]: row for row in positives}
    for control in controls:
        assert control["paired_positive_case_id"] in by_positive
        assert control["relation"] == by_positive[control["paired_positive_case_id"]]["relation"]
        assert control["question"] == by_positive[control["paired_positive_case_id"]]["question"]
        assert control["control_type"] in ("wrong_entity_same_relation", "same_entity_other_relation")


def test_source_disjointness_and_missing_cases_are_explicit():
    chunks, pages, slots = synthetic_corpus()
    excluded = {(str(chunks[0].document_id), chunks[0].page_number)}
    positives, controls, discovery = packet.discover_candidates(chunks, pages, slots, excluded)
    assert all((row["source"]["document_id"], row["source"]["page_number"]) not in excluded
               for row in positives)
    assert discovery["counts"]["positive_candidates"] <= 12
    assert discovery["counts"]["missing_positive_candidates"] == 12-len(positives)
    assert discovery["counts"]["insufficient_pair_candidates"] <= 16
    empty, negatives, missing = packet.discover_candidates((), {}, {}, set())
    assert not empty and not negatives
    assert missing["counts"]["missing_positive_candidates"] == 12


def test_every_authored_followup_has_a_local_referent():
    from app.ai.related_evidence import local_followup_query
    for template in packet.TEMPLATES:
        if template.category == "followup":
            resolved = local_followup_query(template.question, (("user", template.previous_turn),))
            assert resolved is not None and resolved != template.question, template.case_id


def test_known_development_pages_are_excluded_without_answer_probe_import():
    document = uuid4()
    chunks = [SimpleNamespace(document_id=document, page_number=page, section="",
               content=content) for page, content in (
                   (22, "BLEU Bilingual Evaluation Understudy compares n-grams with a reference."),
                   (13, "Cosine uses the angle between vectors rather than magnitude."),
                   (9, "Bag-of-Words loses word order or context."),
                   (30, "Logistic regression applies sigmoid for probability."),
                   (4, "Topic analysis helps legal and medical documents."),
               )]
    assert packet._seed_pages(chunks) == {(str(document), page) for page in (22, 13, 9, 30, 4)}
    with pytest.raises(ValueError, match="seed_identity_unavailable"):
        packet._seed_pages(chunks + [chunks[0]])


def test_wrong_entity_quote_that_names_target_is_not_auto_negative():
    chunks, pages, slots = synthetic_corpus()
    # A02's source also names POS. Its swap against A01 is ambiguous and must
    # remain missing instead of getting an automatic relation-negative label.
    chunks[1].content += " POS is another label discussed here."
    pages[chunks[1].chunk_id] = chunks[1].content
    positives, controls, discovery = packet.discover_candidates(chunks, pages, slots, set())
    assert len(positives) == 12
    by_id = {str(chunk.chunk_id): chunk for chunk in chunks}
    for control in controls:
        if control["control_type"] == "wrong_entity_same_relation":
            target = next(row for row in positives if row["case_id"] == control["paired_positive_case_id"])
            source = control["source"]
            quote = by_id[source["chunk_id"]].content[source["quote_start"]:source["quote_end"]]
            assert not packet.re.search(target["entity_pattern"], quote, packet.re.I)


def test_render_escapes_source_and_question_and_keeps_review_unlabelled():
    manifest, chunks, pages = synthetic_manifest()
    mutated = deepcopy(manifest)
    mutated["positives"][0]["question"] = "<script>alert(1)</script>"
    chunks[0].content += " <img src=x onerror=alert(1)>"
    html = packet.render(mutated, {str(chunk.chunk_id): chunk for chunk in chunks}, pages)
    assert "<script>" not in html and "<img" not in html
    assert "&lt;script&gt;" in html
    assert "No / Unsure" in html and "candidate groups only" in html
    assert "default-src" in html


def test_previous_private_manifests_are_digest_bound_and_exclusions_are_source_page_pairs(tmp_path):
    document = uuid4()
    gold = {"version": "source_navigation_holdout_gold_v1",
            "scope": {"corpus_revision": 4, "embedding_space_hash": "a"*64},
            "cases": [{"gold_document_id": str(document), "gold_page": 9}]}
    raw_gold = json.dumps(gold).encode()
    alternatives = {"version": "source_gold_context_alternatives_v1",
                    "original_roster_sha256": packet._sha(raw_gold),
                    "scope": gold["scope"],
                    "candidates": [{"gold_document_id": str(document), "page": 10}]}
    first, second = tmp_path/"gold.json", tmp_path/"alternatives.json"
    first.write_bytes(raw_gold)
    second.write_text(json.dumps(alternatives), encoding="utf-8")
    excluded, fingerprints = packet._load_old_exclusions(first, second, tmp_path)
    assert excluded == {(str(document), 9), (str(document), 10)}
    assert fingerprints["old_review_pages_excluded"] == 2
    alternatives["original_roster_sha256"] = "f"*64
    second.write_text(json.dumps(alternatives), encoding="utf-8")
    with pytest.raises(ValueError, match="private_input_invalid"):
        packet._load_old_exclusions(first, second, tmp_path)


def test_complete_owner_overlay_converts_only_reviewed_gold_to_display_roster():
    manifest, _, _ = synthetic_manifest()
    positive, controls = packet.convert_reviewed_roster(manifest, review(manifest))
    assert positive["schema"] == "source_only_display_roster_v1"
    assert positive["frozen"] is True and len(positive["cases"]) == 12
    assert all(case["owner_reviewed_gold"] is True for case in positive["cases"])
    assert controls["whole_question_unsupported"] is False
    assert len(controls["pairs"]) == 16
    assert controls["frozen"] is True and controls["owner_reviewed"] is True
    canonical_controls = dict(controls)
    fingerprint = canonical_controls.pop("controls_sha256")
    assert packet._sha(json.dumps(canonical_controls, sort_keys=True,
        separators=(",", ":"), ensure_ascii=False)) == fingerprint
    assert all(row["sufficient_owner_labels"] == {
        "source_fidelity": "Yes", "excerpt_sufficient": "Yes", "page_useful": "Yes"}
        for row in controls["pairs"])
    assert all(len(controls["positive_groups"][category]) == 4 for category in
               ("direct", "paraphrase", "followup"))
    assert all(row["owner_labels"]["excerpt_sufficient"] == "No" for row in controls["pairs"])
    cases = tuple(display.Case(row["case_id"], row["question"], UUID(row["gold_document_id"]),
        row["gold_page_number"], row["owner_reviewed_gold"], tuple(map(tuple, row["history"])))
        for row in positive["cases"])
    scope_data = positive["scope"]
    scope = display.Scope(UUID(scope_data["principal_id"]), UUID(scope_data["subject_id"]),
        tuple(UUID(value) for value in scope_data["document_ids"]),
        scope_data["corpus_revision"], scope_data["space_hash"])
    display.validate_roster(display.FrozenRoster(cases, scope,
        positive["roster_sha256"], positive["runtime_sha256"]))


@pytest.mark.parametrize("change", [
    lambda manifest, owner: owner["labels"].pop(manifest["positives"][0]["case_id"]),
    lambda manifest, owner: owner["labels"][manifest["positives"][0]["case_id"]].update(excerpt_sufficient="No"),
    lambda manifest, owner: owner["labels"][manifest["insufficient_pairs"][0]["case_id"]].update(excerpt_sufficient="Yes"),
    lambda manifest, owner: owner["labels"][manifest["insufficient_pairs"][0]["case_id"]].update(page_useful="Unsure"),
    lambda manifest, owner: owner.update(candidate_roster_sha256="b"*64),
])
def test_incomplete_or_mismatched_owner_review_cannot_be_promoted(change):
    manifest, _, _ = synthetic_manifest()
    labels = review(manifest)
    change(manifest, labels)
    with pytest.raises(ValueError):
        packet.convert_reviewed_roster(manifest, labels)


def test_source_record_rejects_unaligned_page():
    chunks, _, slots = synthetic_corpus()
    chunk = chunks[0]
    with pytest.raises(ValueError, match="source_unavailable"):
        packet._source_record(chunk, "different canonical page", 0, 50, slots[chunk.document_id])


def template(case_id):
    return next(value for value in packet.TEMPLATES if value.case_id == case_id)


@pytest.mark.parametrize("case_id,content", [
    ("M02", "Naive Bayes classification: feature probabilities and model topics."),
    ("D03", "POS tagging and grammatical tagging are topics for next week."),
    ("P02", "Term-document matrix, document features and frequency are lecture topics."),
    ("V02", "Accuracy\n• Precision is a ratio of correct positives over total predicted positives."),
    ("V02", "Accuracy is listed beside precision, which is a ratio of correct positives over total positives."),
    ("D05", "Recap\n• Word embedding is a vector representation of a word."),
    ("D05", "Next: Word Embeddings\n• Word embedding is a vector representation of a word."),
])
def test_recap_self_clue_and_cross_subject_failures_have_no_candidate(case_id, content):
    assert packet._source_windows(content, template(case_id)) == ()


def test_heading_and_wrapped_bullet_are_retained_as_one_exact_complete_unit():
    content = "RNN\n• Updates the hidden state over time when\n  a new token arrives."
    windows = packet._source_windows(content, template("M03"))
    assert windows == ((0, len(content)),)
    assert content[slice(*windows[0])] == content
    changed = "RNN\nCNN\n• Applies convolution filters to extract features from tokens."
    assert packet._source_windows(changed, template("M03")) == ()


def test_complete_oversized_unit_is_not_clipped_and_repeated_page_span_is_ambiguous():
    content = "A word embedding is a vector representation of a word " + "additional context " * 35 + "."
    assert len(content) > 480
    assert packet._source_windows(content, template("D05")) == ()
    quote = "A word embedding is a vector representation of a word."
    assert packet._page_span(quote + "\n" + quote, quote) is None


def test_enumeration_skips_early_recap_before_assigning_and_does_not_require_two_gold_per_relation():
    chunks, pages, slots = synthetic_corpus()
    recap = deepcopy(chunks[2])
    recap.chunk_id = uuid4()
    recap.page_number = 0
    recap.content = "Recap\nA language model assigns probability to a word sequence and predicts the next word."
    pages[recap.chunk_id] = recap.content
    positives, controls, discovery = packet.discover_candidates([recap] + chunks, pages, slots, set())
    assert not any(row["source"]["chunk_id"] == str(recap.chunk_id) for row in positives)
    assert len(positives) == 12 and len(controls) == 16
    assert discovery["assignment"]["complete_category_and_relation_assignment"] is True
    assert any(sum(row["relation"] == relation for row in positives) == 1 for relation in packet._RELATIONS)
    assert any(row["control_type"] == "same_entity_other_relation" for row in controls)


def test_exposed_candidate_pages_are_development_exclusions_without_relabeling(tmp_path):
    manifest, _, _ = synthetic_manifest()
    target = tmp_path / "exposed.json"
    raw = json.dumps(manifest).encode()
    target.write_bytes(raw)
    excluded, digests = packet._load_development_exclusions([target], tmp_path,
        {"corpus_revision": 4, "embedding_space_hash": "a"*64})
    assert excluded.issuperset({packet._source_identity(row["source"]) for row in manifest["positives"]})
    assert digests == [packet._sha(raw)]
    assert target.read_bytes() == raw
    with pytest.raises(ValueError, match="development_exclusions_required"):
        packet._load_development_exclusions([], tmp_path, {})
