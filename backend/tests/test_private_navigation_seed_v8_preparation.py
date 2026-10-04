"""Frozen exposed questions, current scope and bounded controls, no provider."""
from __future__ import annotations

import asyncio
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prepare_private_navigation_seed_v8 as prep


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def inputs():
    space = "a" * 64
    old = {"principal_id": str(UUID(int=1)), "subject_id": str(UUID(int=2)),
        "corpus_revision": 3, "embedding_space_hash": space}
    pages = []
    for i in range(3):
        pages.append({"document_id": str(UUID(int=10+i)), "content_revision_id": str(UUID(int=20+i)),
            "index_revision_id": str(UUID(int=30+i)), "page_number": 1,
            "page_text": "Invented canonical evidence", "original_pdf_sha256": str(i+1)*64,
            "original_pdf_page_count": 40, "corpus_revision": 4,
            "embedding_space_hash": space, "current_authorized": True,
            "published": True, "index_ready": True})
    rows = [{"case_id": key, "group": ("follow_up" if key == "H01" else
        "paraphrase" if key.startswith("P") else "direct"),
        "question": ("What does it stand for?" if key == "H01" else f"What is invented topic {key}?"),
        "prior_question": "What is invented topic D01?" if key == "H01" else "",
        "expected_pdf_sha256": pages[n % 3]["original_pdf_sha256"], "expected_page": 2+n}
        for n, key in enumerate(prep.SEEDS)]
    roster = {"schema": "cardchemy_original_pdf_page_holdout_v1", "label": "invented", "cases": rows}
    source = {"schema": prep.snapshot.SCHEMA, "principal_id": old["principal_id"],
        "subject_id": old["subject_id"], "scope": {"corpus_revision": 4, "embedding_space_hash": space},
        "authorized_pages": pages, "release_gate_passed": False}
    roster_raw = encode(roster)
    vectors = {"schema": "cardchemy_private_query_vectors_v1", "roster_sha256": sha256(roster_raw).hexdigest(),
        "embedding_space_hash": space, "model": "gemini-embedding-001", "vectors": [
            {"case_id": row["case_id"], "question_sha256": sha256(row["question"].encode()).hexdigest(),
             "embedding": [1.0] + [0.0]*1535} for row in rows]}
    return roster, old, vectors, source


def prepared(values):
    raw = tuple(encode(x) for x in values)
    return prep.prepare(*raw, roster_sha256=sha256(raw[0]).hexdigest(),
        scope_sha256=sha256(raw[1]).hexdigest(), vectors_sha256=sha256(raw[2]).hexdigest(),
        source_sha256=sha256(raw[3]).hexdigest())


def test_default_cli_is_keyless_and_does_not_read_supplied_paths():
    result = subprocess.run([sys.executable, str(Path(prep.__file__)),
        "--roster", "missing-private-file"], capture_output=True, text=True, check=True)
    assert result.stderr == ""
    assert json.loads(result.stdout) == {"schema": prep.SCHEMA, "status": "unexecuted",
        "database_reads": 0, "database_writes": 0, "provider_calls": 0, "release_gate_passed": False}


def test_current_corpus_rebind_preserves_old_questions_vectors_and_eleven_cases():
    values = inputs()
    originals = tuple(encode(x) for x in values)
    scope, cases, documents, vectors, provenance = prepared(values)
    assert scope.corpus_revision == 4 and provenance["historical_corpus_revision"] == 3
    assert set(cases) == set(prep.SEEDS) and len(vectors) == 11 and len(documents) == 3
    assert provenance["existing_raw_query_vectors_reused"] == 11
    assert tuple(encode(x) for x in values) == originals
    assert cases["H01"]["previous_turn"] == values[0]["cases"][-1]["prior_question"]


def test_bound_legacy_decimal_revision_is_normalized_without_input_mutation():
    values = inputs()
    values[1]["corpus_revision"] = "3"
    before = encode(values[1])
    assert prepared(values)[4]["historical_corpus_revision"] == 3
    assert encode(values[1]) == before
    values[1]["corpus_revision"] = "03"
    with pytest.raises(prep.previous.Refusal, match="scope_invalid"):
        prepared(values)


@pytest.mark.parametrize("failure", ["space", "principal", "unpublished", "duplicate_pdf", "changed_question",
    "bad_vector", "missing_seed", "duplicate_seed", "bad_page", "history", "bool_revision"])
def test_changed_scope_questions_vectors_or_source_are_refused(failure):
    values = inputs()
    roster, old, vectors, source = values
    if failure == "space": source["scope"]["embedding_space_hash"] = "b"*64
    elif failure == "principal": source["principal_id"] = str(UUID(int=3))
    elif failure == "unpublished": source["authorized_pages"][0]["published"] = False
    elif failure == "duplicate_pdf":
        source["authorized_pages"][1]["original_pdf_sha256"] = source["authorized_pages"][0]["original_pdf_sha256"]
    elif failure == "changed_question": roster["cases"][0]["question"] += " changed"
    elif failure == "bad_vector": vectors["vectors"][0]["embedding"] = [0.0]*1536
    elif failure == "missing_seed": roster["cases"].pop()
    elif failure == "duplicate_seed": roster["cases"][1] = dict(roster["cases"][0])
    elif failure == "bad_page": roster["cases"][0]["expected_page"] = True
    elif failure == "history": roster["cases"][0]["prior_question"] = "later user content"
    elif failure == "bool_revision": source["scope"]["corpus_revision"] = True
    with pytest.raises(prep.previous.Refusal):
        prepared(values)


def test_byte_identity_and_duplicate_json_fields_refuse_before_runtime():
    values = inputs()
    raw = tuple(encode(x) for x in values)
    with pytest.raises(prep.previous.Refusal, match="input_changed"):
        prep.prepare(*raw, source_sha256="a"*64)
    duplicate = b'{"a":1,"a":2}'
    with pytest.raises(prep.previous.Refusal, match="input_invalid"):
        prep._bound(duplicate, sha256(duplicate).hexdigest())


class Db:
    def __init__(self): self.rollbacks = 0
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def rollback(self): self.rollbacks += 1


def test_current_collector_keeps_all_seed_and_controls_pending_without_absence_claim(monkeypatch):
    scope, cases, documents, embeddings, provenance = prepared(inputs())
    seen, sessions = [], []
    def factory():
        db = Db(); sessions.append(db); return db
    async def gold_pages(db, **kwargs):
        return [{"document_id": doc, "page_number": page, "page_text": "Invented exact source"}
            for doc, page in kwargs["pointers"]]
    async def current_collect(db, *, runtime, cases, embeddings, **kwargs):
        case = next(iter(cases.values()))
        seen.append((case["case_id"], case["question"], runtime.candidate_pool))
        return {"cases": [{"case_id": case["case_id"], "form": case["form"],
            "question": case["question"], "candidates": [], "request": None}]}, {
                "gold_in_initial": 1, "gold_in_pool": 1, "candidate_pages": 0}
    monkeypatch.setattr(prep.snapshot, "_collect_pages", gold_pages)
    monkeypatch.setattr(prep.current, "collect", current_collect)
    runtime = SimpleNamespace(space_hash=scope.embedding_space_hash, candidate_pool=object())
    body, report = asyncio.run(prep.collect(factory, runtime=runtime, scope=scope,
        cases=cases, documents=documents, embeddings=embeddings, provenance=provenance))
    assert len(body["cases"]) == 14 and [c[0] for c in seen] == [*prep.SEEDS, "N12", "U01", "U02"]
    assert report["seed_gold_in_initial"] == report["seed_gold_in_pool"] == 11
    assert all(c["independent_candidate_labels"] == "pending" and not c["corpus_absence_claim"]
        for c in body["cases"])
    assert body["cases"][-2]["question"] == cases["D05"]["question"]
    assert body["cases"][-1]["question"] == cases["D03"]["question"]
    assert all(c["require_empty_candidate_slate"] and c["gold_page_key"] is None
        for c in body["cases"][-2:])
    assert len(sessions) == 15 and all(db.rollbacks == 1 for db in sessions)
    assert report["provider_calls"] == report["database_writes"] == 0
    assert body["release_gate_passed"] is False


def test_wrong_source_pool_reauthorizes_anchor_and_reads_canonical_page():
    from app.services.knowledge_retrieval import AuthorizedKnowledgeSource
    scope, cases, documents, _vectors, _pins = prepared(inputs())
    case = cases["D02"]
    binding = documents[case["document_id"]]
    chunk_id = UUID(int=77)
    source = AuthorizedKnowledgeSource(chunk_id, UUID(case["document_id"]), "Invented title",
        UUID(binding["content_revision_id"]), UUID(binding["index_revision_id"]), case["page_number"],
        None, "Invented chunk", 4, scope.embedding_space_hash, scope.corpus_revision)
    class Database:
        async def scalar(self, statement):
            assert "subject_document_chunks" in str(statement)
            return chunk_id
    class Retriever:
        calls = []
        async def read_current_sources(self, ids):
            self.calls.append(("authorize", ids)); return (source,)
        async def read_current_source_pages(self, ids, **kwargs):
            self.calls.append(("page", ids)); return {chunk_id: "Invented full canonical page"}
    retriever = Retriever()
    pool = asyncio.run(prep._control_pool(Database(), retriever, case, documents))
    assert retriever.calls == [("authorize", (chunk_id,)), ("page", (chunk_id,))]
    assert pool.selections[0].source.chunk_id == chunk_id
    assert pool.selections[0].source_kind == "canonical_page"
    assert pool.selections[0].quote == "Invented full canonical page"


def test_default_execute_refuses_provider_credentials_before_private_file_read():
    args = SimpleNamespace(expected_database="invented")
    with pytest.raises(prep.snapshot.Refusal, match="ai_credentials_present"):
        asyncio.run(prep.execute(args, environment={"ENVIRONMENT": "development",
            "RAG_ASK_ENABLED": "false", "RAG_SOURCE_JUDGE_PROVIDER_ENABLED": "false",
            "RAG_SOURCE_JUDGE_API_KEY": "invented-value"}))
