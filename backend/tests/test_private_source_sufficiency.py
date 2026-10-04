"""Provider-free pair audit guards and exact reviewed-window qualification."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import evaluate_private_source_sufficiency as audit


_EXAMPLES = {
    "acronym_expansion": ("What does BLEU stand for?", "BLEU means Bilingual Evaluation Understudy."),
    "definition": ("What is tokenization?", "Tokenization is the division of text into tokens."),
    "mechanism": ("What function does Logistic Regression use to output probabilities?",
        "Logistic Regression uses the sigmoid function to output probabilities."),
    "measurement": ("What does BLEU measure?", "BLEU measures n-gram overlap with a reference translation."),
    "reason": ("Why does TF-IDF weight rare terms?", "TF-IDF weights rare terms because they are informative."),
    "process": ("What steps does tokenization follow?", "Tokenization first splits text, then emits tokens."),
    "property_limitation": ("What limitation of Bag-of-Words means word order is lost?",
        "Bag-of-Words ignores word order and context when it represents text."),
    "application_example": ("What is an example application of topic modeling?",
        "Topic modeling is used to organize documents by topic."),
}


def seal(raw):
    raw["controls_sha256"] = audit.digest({key: value for key, value in raw.items() if key != "controls_sha256"})
    return raw


def manifest(raw):
    positives = {}
    for pair in raw["pairs"]:
        positives.setdefault(pair["paired_positive_case_id"], {
            "case_id": pair["paired_positive_case_id"],
            **{key: pair[key] for key in ("relation", "category", "question", "previous_turn")},
            "source": pair.get("sufficient_source")})
    return {"schema": "source_sufficiency_candidate_packet_v1", "source_frozen": True,
        "discovery_policy_id": "complete_source_units_v2", "scope": raw["scope"],
        "positives": list(positives.values()), "insufficient_pairs": [
            {key: pair[key] for key in ("case_id", "relation", "category", "question", "previous_turn",
                "paired_positive_case_id", "source_candidate_case_id", "control_type", "source")}
            for pair in raw["pairs"]]}


def parse(raw):
    return audit.parse_controls(raw, candidate_manifest=manifest(raw))


def fixture():
    principal, subject, doc = uuid4(), uuid4(), uuid4()
    scope = {"principal_id": str(principal), "subject_id": str(subject), "document_ids": [str(doc)],
        "corpus_revision": 4, "space_hash": "a" * 64}
    current = {}

    def source(text, page, *, quote=None):
        chunk = SimpleNamespace(chunk_id=uuid4(), document_id=doc, document_title="PRIVATE_MARKER",
            content_revision_id=uuid4(), index_revision_id=uuid4(), page_number=page, section=None,
            content=text, token_count=50, embedding_space_hash=scope["space_hash"], corpus_revision=4)
        page_content = "header\n" + text + "\nfooter"
        window = text if quote is None else quote
        start = text.index(window)
        src = {key: str(getattr(chunk, key)) for key in
            ("chunk_id", "document_id", "content_revision_id", "index_revision_id")}
        src.update(document_title=chunk.document_title, document_slot=1, page_number=page,
            corpus_revision=4, embedding_space_hash=scope["space_hash"],
            chunk_sha256=audit._sha(text), page_sha256=audit._sha(page_content),
            quote_sha256=audit._sha(window), quote_start=start, quote_end=start+len(window),
            page_reference_start=start+7, page_reference_end=start+7+len(window))
        current[chunk.chunk_id] = chunk, page_content
        return src

    pairs = []
    for index, (relation, (question, sufficient)) in enumerate(_EXAMPLES.items()):
        positive = source(sufficient, index*3+1)
        for number in (1, 2):
            negative = source(f"PRIVATE_MARKER topic mention {number}.", index*3+number+1)
            pairs.append({"case_id": f"I-{relation}-{number}", "relation": relation,
                "category": "direct", "question": question, "previous_turn": "",
                "paired_positive_case_id": f"P-{relation}", "source_candidate_case_id": f"N-{relation}-{number}",
                "control_type": "same_entity_other_relation", "source": negative,
                "sufficient_source": positive,
                "owner_labels": {"source_fidelity": "Yes", "excerpt_sufficient": "No", "page_useful": "No"},
                "sufficient_owner_labels": {"source_fidelity": "Yes", "excerpt_sufficient": "Yes", "page_useful": "Yes"}})
    raw = {"schema": audit.SCHEMA, "frozen": True, "owner_reviewed": True,
        "runtime_sha256": audit.runtime_fingerprint(), "evaluator_sha256": audit.evaluator_fingerprint(), "scope": scope,
        "source_candidate_sha256": "b"*64, "control_types": ["same_entity_other_relation"],
        "whole_question_unsupported": False, "positive_groups": {
            "direct": [f"P-{relation}" for relation in _EXAMPLES], "paraphrase": [], "followup": []},
        "pairs": pairs}
    raw["source_candidate_sha256"] = audit.digest(manifest(raw))
    return seal(raw), current


class Reader:
    def __init__(self, current):
        self.rows, self.calls = current, 0

    async def current(self, sources):
        self.calls += 1
        return self.rows


def test_default_preflight_does_not_import_app_or_connect():
    code = ("import sys; sys.path.insert(0, " + repr(str(Path(audit.__file__).parent)) + "); "
        "import evaluate_private_source_sufficiency as a; a.main([]); "
        "assert not any(k == 'app' or k.startswith('app.') for k in sys.modules)")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    report = json.loads(result.stdout)
    assert report["database_reads"] == report["provider_requests"] == 0
    assert report["release_gate_passed"] is False


@pytest.mark.parametrize("mutation,code", [
    (lambda raw: raw.update(frozen=False), "controls_not_reviewed"),
    (lambda raw: raw.update(owner_reviewed=False), "controls_not_reviewed"),
    (lambda raw: raw.update(runtime_sha256="c"*64), "runtime_changed"),
    (lambda raw: raw.update(evaluator_sha256="c"*64), "runtime_changed"),
    (lambda raw: raw["pairs"].pop(), "controls_not_reviewed"),
    (lambda raw: raw["pairs"][0]["owner_labels"].update(page_useful="Unsure"), "controls_not_reviewed"),
    (lambda raw: raw["pairs"][0]["sufficient_owner_labels"].update(excerpt_sufficient="No"), "controls_not_reviewed"),
    (lambda raw: raw["pairs"][0].pop("sufficient_source"), "inputs_invalid"),
    (lambda raw: raw["pairs"][0]["source"].update(document_id=str(uuid4())), "inputs_invalid"),
])
def test_unreviewed_incomplete_or_drifted_inputs_are_refused(mutation, code):
    raw, _ = fixture()
    mutation(raw)
    with pytest.raises(audit.Refusal, match=f"^{code}$"):
        parse(seal(raw))


def test_changed_digest_and_duplicate_negative_windows_refused():
    raw, _ = fixture()
    raw["pairs"][0]["question"] += " drift"
    with pytest.raises(audit.Refusal, match="^inputs_invalid$"):
        parse(raw)
    raw, _ = fixture()
    raw["pairs"][1]["source"] = deepcopy(raw["pairs"][0]["source"])
    with pytest.raises(audit.Refusal, match="^inputs_invalid$"):
        parse(seal(raw))


@pytest.mark.parametrize("change", ["digest", "positive_window", "negative_question"])
def test_manifest_digest_and_exact_original_records_are_required(change):
    raw, _ = fixture()
    candidate = deepcopy(manifest(raw))
    if change == "digest":
        candidate["discovery_note"] = "Changed original roster"
    elif change == "positive_window":
        candidate["positives"][0]["source"]["quote_end"] -= 1
        raw["source_candidate_sha256"] = audit.digest(candidate)
    else:
        candidate["insufficient_pairs"][0]["question"] += " different question"
        raw["source_candidate_sha256"] = audit.digest(candidate)
    with pytest.raises(audit.Refusal, match="^inputs_invalid$"):
        audit.parse_controls(seal(raw), candidate_manifest=candidate)


@pytest.mark.asyncio
async def test_invalid_manifest_is_refused_before_database_factory(monkeypatch):
    raw, _ = fixture()
    objects = {"controls": raw, "candidate": {}, "profile": {"database_url": "private"}}
    monkeypatch.setattr(audit, "_private_json", lambda path: objects[str(path)])
    def forbidden(*args):
        pytest.fail("Unbound review inputs must not construct a DB reader")
    monkeypatch.setattr(audit, "explicit_reader", forbidden)
    with pytest.raises(audit.Refusal, match="^inputs_invalid$"):
        await audit._execute(SimpleNamespace(controls="controls", candidate_manifest="candidate", profile="profile"))


@pytest.mark.asyncio
async def test_passing_aggregate_never_claims_release_and_contains_no_private_data():
    raw, current = fixture()
    reader = Reader(current)
    result = await audit.evaluate(parse(raw), reader,
        qualifier=lambda pair, chunk, quote, **kwargs: "PRIVATE_MARKER" not in quote)
    assert reader.calls == 2
    assert result["source_pair_gate_passed"] is True
    assert result["release_gate_passed"] is False
    assert result["whole_question_unsupported"] is False
    assert all(row["reviewed_pairs"] == row["sufficient_control_qualified"] == 2
        and row["negative_qualified"] == row["unknown"] == 0 for row in result["relations"].values())
    output = json.dumps(result)
    assert "PRIVATE_MARKER" not in output
    assert all(str(identity) not in output for identity in current)


@pytest.mark.parametrize("kind", ["negative_positive", "sufficient_rejected", "unknown"])
@pytest.mark.asyncio
async def test_false_positive_empty_selector_and_unknown_cannot_pass(kind):
    raw, current = fixture()
    result = await audit.evaluate(parse(raw), Reader(current), qualifier=
        (lambda *args, **kwargs: True) if kind == "negative_positive" else
        (lambda *args, **kwargs: False) if kind == "sufficient_rejected" else (lambda *args, **kwargs: None))
    assert result["source_pair_gate_passed"] is False
    if kind == "unknown":
        assert all(row["unknown"] == 2 for row in result["relations"].values())


@pytest.mark.parametrize("field,value", [("content", "changed"), ("document_id", uuid4()),
    ("content_revision_id", uuid4()), ("index_revision_id", uuid4()),
    ("embedding_space_hash", "d"*64), ("corpus_revision", 5), ("page_number", 99)])
@pytest.mark.asyncio
async def test_current_identity_or_content_change_refused(field, value):
    raw, current = fixture()
    chunk, page = current[UUID(raw["pairs"][0]["source"]["chunk_id"])]
    setattr(chunk, field, value)
    with pytest.raises(audit.Refusal, match="^source_changed$"):
        await audit.evaluate(parse(raw), Reader(current), qualifier=lambda *args, **kwargs: False)


@pytest.mark.asyncio
async def test_second_read_drift_is_refused():
    raw, current = fixture()
    class DriftReader(Reader):
        async def current(self, sources):
            self.calls += 1
            if self.calls == 2:
                return {}
            return self.rows
    with pytest.raises(audit.Refusal, match="^source_changed$"):
        await audit.evaluate(parse(raw), DriftReader(current), qualifier=lambda *args, **kwargs: False)


def test_actual_selector_sees_only_exact_reviewed_window_and_unknown_is_not_pass():
    raw, current = fixture()
    pair = raw["pairs"][0]
    chunk, _ = current[UUID(pair["source"]["chunk_id"])]
    chunk.content = "BLEU is mentioned here. BLEU means Bilingual Evaluation Understudy."
    assert audit._qualifies(pair, chunk, "BLEU is mentioned here.") is False
    assert audit._qualifies(pair, chunk, "BLEU means Bilingual Evaluation Understudy.") is True
    assert audit._qualifies(dict(pair, question="How many moons does BLEU have?"), chunk,
        "BLEU means Bilingual Evaluation Understudy.") is None


def test_positive_cropped_subspan_is_unknown_but_negative_subspan_is_failure():
    raw, current = fixture()
    pair = raw["pairs"][0]
    chunk, _ = current[UUID(pair["source"]["chunk_id"])]
    reviewed = "BLEU means Bilingual Evaluation Understudy. A separate sentence adds context."
    assert audit._qualifies(pair, chunk, reviewed, sufficient=True) is None
    assert audit._qualifies(pair, chunk, reviewed, sufficient=False) is True


@pytest.mark.asyncio
async def test_actual_eight_family_selector_audit_counts_match_exact_windows():
    raw, current = fixture()
    result = await audit.evaluate(parse(raw), Reader(current))
    for pair in raw["pairs"]:
        row = result["relations"][pair["relation"]]
        assert row["reviewed_pairs"] == 2
        assert row["negative_qualified"] == 0
        source = pair["sufficient_source"]
        chunk, page = current[UUID(source["chunk_id"])]
        value = audit._qualifies(pair, chunk, audit.validate_current(source, (chunk, page)), sufficient=True)
        assert row["sufficient_control_qualified"] == (2 if value is True else 0)
        assert row["unknown"] == (2 if value is None else 0)
    assert result["release_gate_passed"] is False


@pytest.mark.parametrize("mutation", [
    lambda source: source.update(page_sha256="e"*64),
    lambda source: source.update(quote_start=1),
    lambda source: source.update(page_reference_start=8),
])
def test_page_and_offset_drift_refused(mutation):
    raw, current = fixture()
    src = deepcopy(raw["pairs"][0]["source"])
    mutation(src)
    with pytest.raises(audit.Refusal, match="^source_changed$"):
        audit.validate_current(src, current[UUID(src["chunk_id"])])


def test_cli_refusal_omits_raw_exception_and_private_data(monkeypatch, capsys):
    async def failure(args):
        raise RuntimeError("PRIVATE_MARKER internal details")
    monkeypatch.setattr(audit, "_execute", failure)
    assert audit.main(["--execute", "--controls", "ignored", "--profile", "ignored", "--candidate-manifest", "ignored"]) == 2
    result = capsys.readouterr().out
    assert "PRIVATE_MARKER" not in result
    assert json.loads(result)["reason"] == "audit_failed"


@pytest.mark.asyncio
async def test_postgres_reader_requires_current_instructor_owner_before_sources(monkeypatch):
    from app.services.knowledge_retrieval import KnowledgeRetriever
    raw, _ = fixture()
    controls = parse(raw)
    statements = []
    class DB:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
        async def execute(self, statement):
            statements.append(str(statement))
        async def scalar(self, statement):
            statements.append(str(statement))
            return None
    async def forbidden(*args, **kwargs):
        pytest.fail("No sources may be read for a non-owner or enrolled student")
    monkeypatch.setattr(KnowledgeRetriever, "authorize", forbidden)
    with pytest.raises(audit.Refusal, match="^scope_changed$"):
        await audit.ReadOnlyPostgresReader(DB, controls.scope).current((raw["pairs"][0]["source"],))
    assert statements[0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    assert "users.role" in statements[2] and "subjects.instructor_id" in statements[2]


@pytest.mark.asyncio
async def test_postgres_reader_refuses_revision_drift_before_chunk_lookup(monkeypatch):
    from app.services.knowledge_retrieval import KnowledgeRetriever
    raw, _ = fixture()
    controls = parse(raw)
    class DB:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
        async def execute(self, statement):
            return None
        async def scalar(self, statement):
            return controls.scope.principal_id
    async def changed(db, **kwargs):
        assert kwargs["document_ids"] == controls.scope.document_ids
        async def forbidden(*args):
            pytest.fail("Stale corpus must not reach source lookup")
        return SimpleNamespace(scope=SimpleNamespace(corpus_revision=5,
            embedding_space_hash=controls.scope.space_hash,
            document_ids=controls.scope.document_ids), read_current_sources=forbidden)
    monkeypatch.setattr(KnowledgeRetriever, "authorize", changed)
    with pytest.raises(audit.Refusal, match="^scope_changed$"):
        await audit.ReadOnlyPostgresReader(DB, controls.scope).current((raw["pairs"][0]["source"],))


def test_profile_refuses_nonlocal_and_ambient_database_without_connecting():
    raw, _ = fixture()
    with pytest.raises(audit.Refusal, match="^database_target_invalid$"):
        audit.explicit_reader({"database_url": "postgresql+asyncpg://hostile.example/private"},
            parse(raw).scope)
