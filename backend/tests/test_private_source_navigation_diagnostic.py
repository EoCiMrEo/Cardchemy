"""Provider-free tests for the read-only v3/v9 private navigation probe."""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import diagnose_source_navigation as probe

from app.services.knowledge_retrieval import (
    AuthorizedKnowledgeScope, KnowledgeRetriever, KnowledgeRetrievalResult,
    RetrievedKnowledgeChunk, SOURCE_NAVIGATION_RETRIEVAL_POLICY,
)
from app.models.knowledge import embedding_space_hash


def sample_case(**overrides):
    values = dict(case_id="D01", group="direct", question="What does BLEU stand for?",
                  prior_question="", expected_pdf_sha256="a" * 64, expected_page=22,
                  gold_window="BLEU stands for Bilingual Evaluation Understudy.")
    values.update(overrides)
    return probe.Case(**values)


def sample_scope():
    return probe.Scope(uuid4(), uuid4(), 7, "b" * 64)


def test_default_cli_does_not_read_database_or_roster():
    script = Path(probe.__file__)
    result = subprocess.run([sys.executable, str(script)], capture_output=True,
                            text=True, check=True)
    report = json.loads(result.stdout)
    assert report == {"schema": probe.SCHEMA, "status": "preflight_unexecuted",
                      "provider_requests": 0, "database_reads": 0,
                      "database_writes": 0, "release_gate_passed": False}


def test_roster_is_private_path_and_byte_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(probe, "PRIVATE_MOUNT", tmp_path)
    case = sample_case()
    path = tmp_path / "roster.json"
    path.write_text(json.dumps({"schema": probe.ROSTER_SCHEMA, "cases": [asdict(case)]}),
                    encoding="utf-8")
    digest = sha256(path.read_bytes()).hexdigest()
    assert probe.load_roster(path, digest) == ((case,), digest)
    with pytest.raises(probe.Refusal, match="roster_changed"):
        probe.load_roster(path, "0" * 64)
    other = tmp_path.parent / "outside-roster.json"
    with pytest.raises(probe.Refusal, match="private_mount_required"):
        probe.load_roster(other, digest)


@pytest.mark.parametrize("change", [
    {"group": "follow_up"}, {"question": ""}, {"gold_window": "x" * 481},
    {"expected_page": 0}, {"expected_page": True}, {"expected_pdf_sha256": "bad"},
])
def test_roster_rejects_unusable_gold_without_printing_content(monkeypatch, tmp_path, change):
    monkeypatch.setattr(probe, "PRIVATE_MOUNT", tmp_path)
    case = asdict(sample_case()) | change
    path = tmp_path / "roster.json"
    path.write_text(json.dumps({"schema": probe.ROSTER_SCHEMA, "cases": [case]}),
                    encoding="utf-8")
    with pytest.raises(probe.Refusal) as error:
        probe.load_roster(path, sha256(path.read_bytes()).hexdigest())
    assert error.value.args == ("roster_invalid",)
    assert "BLEU" not in str(error.value)


def test_page_only_roster_does_not_invent_a_gold_quote(monkeypatch, tmp_path):
    monkeypatch.setattr(probe, "PRIVATE_MOUNT", tmp_path)
    case = asdict(sample_case())
    del case["gold_window"]
    path = tmp_path / "page-only.json"
    path.write_text(json.dumps({"schema": probe.ROSTER_SCHEMA, "cases": [case]}),
                    encoding="utf-8")
    loaded, _digest = probe.load_roster(path, sha256(path.read_bytes()).hexdigest())
    assert loaded[0].gold_window == ""


def _vector_packet(case, scope, roster_sha256):
    return {
        "schema": probe.VECTOR_SCHEMA,
        "roster_sha256": roster_sha256,
        "embedding_space_hash": scope.embedding_space_hash,
        "model": probe.VECTOR_MODEL,
        "vectors": [{
            "case_id": case.case_id,
            "question_sha256": sha256(case.question.encode("utf-8")).hexdigest(),
            "embedding": [1.0] + [0.0] * (probe.VECTOR_DIMENSIONS - 1),
        }],
    }


def _write_packet(path, packet):
    path.write_text(json.dumps(packet), encoding="utf-8")
    return sha256(path.read_bytes()).hexdigest()


def test_private_vector_packet_is_complete_sha_frozen_and_question_bound(monkeypatch, tmp_path):
    monkeypatch.setattr(probe, "PRIVATE_MOUNT", tmp_path)
    case, scope = sample_case(), sample_scope()
    roster_sha256 = "c" * 64
    path = tmp_path / "vectors.json"
    packet = _vector_packet(case, scope, roster_sha256)
    digest = _write_packet(path, packet)
    vectors, actual_digest = probe.load_vectors(
        path, digest, roster_sha256=roster_sha256, cases=(case,), scope=scope,
    )
    assert actual_digest == digest
    assert vectors[case.case_id] == tuple(packet["vectors"][0]["embedding"])
    with pytest.raises(probe.Refusal, match="vector_packet_changed"):
        probe.load_vectors(path, "0" * 64, roster_sha256=roster_sha256,
                           cases=(case,), scope=scope)
    with pytest.raises(probe.Refusal, match="private_mount_required"):
        probe.load_vectors(tmp_path.parent / "outside.json", digest,
                           roster_sha256=roster_sha256, cases=(case,), scope=scope)


@pytest.mark.parametrize("alter,code", [
    (lambda p: p.update(model="other-model"), "vector_scope_mismatch"),
    (lambda p: p.update(embedding_space_hash="d" * 64), "vector_scope_mismatch"),
    (lambda p: p.update(roster_sha256="d" * 64), "vector_packet_invalid"),
    (lambda p: p["vectors"][0].update(question_sha256="d" * 64), "vector_packet_invalid"),
    (lambda p: p["vectors"][0].update(case_id="D02"), "vector_packet_invalid"),
    (lambda p: p["vectors"][0].update(embedding=[1.0]), "vector_packet_invalid"),
    (lambda p: p["vectors"][0].update(embedding=[0.0] * probe.VECTOR_DIMENSIONS),
     "vector_packet_invalid"),
    (lambda p: p["vectors"][0].update(embedding=[2.0] + [0.0] * (probe.VECTOR_DIMENSIONS - 1)),
     "vector_packet_invalid"),
    (lambda p: p["vectors"][0]["embedding"].__setitem__(0, float("nan")),
     "vector_packet_invalid"),
    (lambda p: p["vectors"][0]["embedding"].__setitem__(0, True),
     "vector_packet_invalid"),
    (lambda p: p["vectors"].append(p["vectors"][0]), "vector_packet_invalid"),
])
def test_bad_private_vector_or_reference_refuses_before_db(monkeypatch, tmp_path, alter, code):
    monkeypatch.setattr(probe, "PRIVATE_MOUNT", tmp_path)
    case, scope = sample_case(), sample_scope()
    roster_sha256 = "c" * 64
    packet = _vector_packet(case, scope, roster_sha256)
    alter(packet)
    path = tmp_path / "vectors.json"
    digest = _write_packet(path, packet)
    with pytest.raises(probe.Refusal, match=code):
        probe.load_vectors(path, digest, roster_sha256=roster_sha256,
                           cases=(case,), scope=scope)


@pytest.mark.asyncio
@pytest.mark.parametrize("wrong_model", [False, True])
async def test_hybrid_profile_mismatch_refuses_before_database(monkeypatch, tmp_path, wrong_model):
    from app import config, database

    identity = ("native_gemini", "endpoint", probe.VECTOR_MODEL, "r1", "f1",
                1536, "v1", "cosine", "RETRIEVAL_DOCUMENT", "QUESTION_ANSWERING")
    actual_space = embedding_space_hash(identity)
    base = sample_scope()
    scope = probe.Scope(base.principal_id, base.subject_id, base.corpus_revision,
                        actual_space if wrong_model else "b" * 64)
    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(
        database_url="postgresql+asyncpg://reader@db/probe", environment="development",
        rag_ask_enabled=False, rag_embedding_model="wrong-model" if wrong_model else probe.VECTOR_MODEL,
        rag_embedding_space_identity=identity,
    ))
    monkeypatch.setattr(database, "async_session_maker",
                        lambda: pytest.fail("database must not be opened"))
    case = sample_case()
    with pytest.raises(probe.Refusal, match="vector_scope_mismatch"):
        await probe.execute((case,), "c" * 64, tmp_path / "roster.json",
                            tmp_path / "output.json", scope,
                            vectors={case.case_id: (1.0,) + (0.0,) * (probe.VECTOR_DIMENSIONS - 1)},
                            vector_path=tmp_path / "vectors.json", vector_sha256="d" * 64)


class Result:
    def __init__(self, rows=()):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return list(self.rows)

    def one_or_none(self):
        return self.rows[0] if self.rows else None


class FakeDb:
    def __init__(self, document_id):
        self.document_id = document_id
        self.statements = []

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append(sql)
        assert not any(word in sql.upper() for word in ("INSERT INTO", "UPDATE ", "DELETE FROM"))
        if sql.startswith("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"):
            return Result()
        if "page_indexed" in sql:
            return Result(({"document_id": self.document_id, "page_present": True,
                            "gold_window_extracted": True, "page_indexed": True,
                            "original_pdf_manifest_current": True},))
        if "original_pdf_manifest_current" in sql:
            return Result(({"original_pdf_manifest_current": True},))
        raise AssertionError("Unexpected SQL in fake read-only probe")


class FakeRetriever:
    def __init__(self, scope, chunk):
        self.scope = AuthorizedKnowledgeScope(
            scope.principal_id, scope.subject_id, scope.corpus_revision,
            scope.embedding_space_hash, scope.document_ids,
        )
        self.chunk = chunk
        self.calls = []

    async def retrieve_lexical(self):
        self.calls.append("lexical")
        return self._result()

    async def retrieve(self, query_embedding, *, embedding_space_hash):
        self.calls.append(("hybrid", tuple(query_embedding), embedding_space_hash))
        return self._result()

    def _result(self):
        return KnowledgeRetrievalResult(
            SOURCE_NAVIGATION_RETRIEVAL_POLICY.policy_id, self.scope.subject_id,
            self.scope.corpus_revision, self.scope.embedding_space_hash, (self.chunk,),
        )

    async def expand_source_neighbors(self, anchors, **kwargs):
        self.calls.append("neighbors")
        return ()

    async def read_current_source_pages(self, chunk_ids, **kwargs):
        self.calls.append("pages")
        return {self.chunk.chunk_id: self.chunk.content} if self.chunk.chunk_id in chunk_ids else {}

    async def read_current_sources(self, chunk_ids):
        self.calls.append("reauthorize")
        return (SimpleNamespace(**asdict(self.chunk)),) if self.chunk.chunk_id in chunk_ids else ()


@pytest.mark.asyncio
async def test_actual_selector_uses_lexical_candidates_and_exact_current_page(monkeypatch):
    case, scope = sample_case(), sample_scope()
    document_id = uuid4()
    chunk = RetrievedKnowledgeChunk(
        chunk_id=uuid4(), document_id=document_id, document_title="Synthetic lecture",
        content_revision_id=uuid4(), index_revision_id=uuid4(), page_number=22,
        section="BLEU", content=case.gold_window, token_count=18,
        embedding_space_hash=scope.embedding_space_hash,
        corpus_revision=scope.corpus_revision, vector_similarity=None,
        lexical_score=.4, vector_rank=None, lexical_rank=1, fusion_score=1 / 61,
    )
    retriever = FakeRetriever(scope, chunk)

    async def authorize(cls, db, *, principal, subject_id, query, document_ids, limit, policy):
        assert principal.id == scope.principal_id and subject_id == scope.subject_id
        assert policy == SOURCE_NAVIGATION_RETRIEVAL_POLICY and limit == 20
        assert query == case.question and document_ids == ()
        return retriever

    monkeypatch.setattr(KnowledgeRetriever, "authorize", classmethod(authorize))
    db = FakeDb(document_id)
    row = await probe.evaluate_case(db, scope, case)
    assert db.statements[0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    assert "lexical" in retriever.calls and "reauthorize" in retriever.calls
    assert row["gold_sql_rank"] == row["gold_display_rank"] == 1
    assert row["selected"][0]["quote"] == case.gold_window
    assert row["selected"][0]["canonical_page_aligned"]
    assert row["selected"][0]["original_pdf_manifest_current"]
    assert not row["selected"][0]["opened_original_pdf"]
    assert row["provider_requests"] == row["answer_requests"] == row["database_writes"] == 0
    summary = probe.aggregate((row,))
    assert summary["display_gold_hit"] == 1
    assert "BLEU" not in json.dumps(summary)


@pytest.mark.asyncio
async def test_actual_selector_uses_precomputed_vector_and_current_hybrid_retrieval(monkeypatch):
    case, scope = sample_case(), sample_scope()
    document_id = uuid4()
    chunk = RetrievedKnowledgeChunk(
        chunk_id=uuid4(), document_id=document_id, document_title="Synthetic lecture",
        content_revision_id=uuid4(), index_revision_id=uuid4(), page_number=22,
        section="BLEU", content=case.gold_window, token_count=18,
        embedding_space_hash=scope.embedding_space_hash,
        corpus_revision=scope.corpus_revision, vector_similarity=.8,
        lexical_score=.4, vector_rank=1, lexical_rank=1, fusion_score=2 / 61,
    )
    retriever = FakeRetriever(scope, chunk)

    async def authorize(cls, db, **kwargs):
        return retriever

    monkeypatch.setattr(KnowledgeRetriever, "authorize", classmethod(authorize))
    vector = tuple([1.0] + [0.0] * (probe.VECTOR_DIMENSIONS - 1))
    db = FakeDb(document_id)
    row = await probe.evaluate_case(db, scope, case, query_embedding=vector)
    assert db.statements[0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    assert retriever.calls.count("lexical") == 0
    assert ("hybrid", vector, scope.embedding_space_hash) in retriever.calls
    assert row["query_vector_used"] is True
    assert row["gold_sql_rank"] == row["gold_display_rank"] == 1
    assert probe.aggregate((row,))["query_vectors_used"] == 1


@pytest.mark.asyncio
async def test_stale_scope_fails_before_gold_or_candidate_sql(monkeypatch):
    case, scope = sample_case(), sample_scope()
    chunk = RetrievedKnowledgeChunk(
        chunk_id=uuid4(), document_id=uuid4(), document_title="Synthetic",
        content_revision_id=uuid4(), index_revision_id=uuid4(), page_number=22,
        section=None, content=case.gold_window, token_count=10,
        embedding_space_hash=scope.embedding_space_hash,
        corpus_revision=scope.corpus_revision, vector_similarity=None,
        lexical_score=.4, vector_rank=None, lexical_rank=1, fusion_score=1 / 61,
    )
    stale = probe.Scope(scope.principal_id, scope.subject_id, scope.corpus_revision + 1,
                        scope.embedding_space_hash)

    async def authorize(cls, db, **kwargs):
        return FakeRetriever(stale, chunk)

    monkeypatch.setattr(KnowledgeRetriever, "authorize", classmethod(authorize))
    db = FakeDb(chunk.document_id)
    with pytest.raises(probe.Refusal, match="scope_changed"):
        await probe.evaluate_case(db, scope, case)
    assert len(db.statements) == 1
