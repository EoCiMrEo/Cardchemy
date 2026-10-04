"""Synthetic, provider-free checks for the private v4 candidate-recall probe."""

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
import diagnose_source_judge_v4_candidates as probe

from app.services.knowledge_retrieval import (
    AuthorizedKnowledgeScope, AuthorizedKnowledgeSource, KnowledgeRetrievalResult,
    KnowledgeRetriever, RetrievedKnowledgeChunk, SOURCE_NAVIGATION_RETRIEVAL_POLICY,
)


def _case(page: int = 5) -> probe.base.Case:
    return probe.base.Case(
        "D01", "direct", "How does the method update weights?", "",
        "a" * 64, page, "Gold lecture page.",
    )


def _scope() -> probe.base.Scope:
    return probe.base.Scope(uuid4(), uuid4(), 7, "b" * 64)


class _Db:
    def __init__(self):
        self.statements = []

    async def execute(self, statement):
        self.statements.append(str(statement))


class _Retriever:
    def __init__(self, scope, chunks):
        self.scope = AuthorizedKnowledgeScope(
            scope.principal_id, scope.subject_id, scope.corpus_revision,
            scope.embedding_space_hash, scope.document_ids,
        )
        self.chunks = chunks
        self.calls = []

    async def retrieve(self, vector, *, embedding_space_hash):
        self.calls.append(("retrieve", vector, embedding_space_hash))
        return KnowledgeRetrievalResult(
            SOURCE_NAVIGATION_RETRIEVAL_POLICY.policy_id,
            self.scope.subject_id, self.scope.corpus_revision,
            self.scope.embedding_space_hash, self.chunks,
        )

    async def expand_source_neighbors(self, anchors, **kwargs):
        self.calls.append(("neighbors", kwargs))
        return ()

    async def read_current_sources(self, ids):
        self.calls.append(("sources", len(ids)))
        by_id = {chunk.chunk_id: chunk for chunk in self.chunks}
        return tuple(AuthorizedKnowledgeSource(**{
            key: getattr(by_id[chunk_id], key)
            for key in AuthorizedKnowledgeSource.__dataclass_fields__
        }) for chunk_id in ids)

    async def read_current_source_pages(self, ids, **kwargs):
        self.calls.append(("pages", kwargs))
        by_id = {chunk.chunk_id: chunk for chunk in self.chunks}
        return {chunk_id: by_id[chunk_id].content for chunk_id in ids}


def _chunks(scope, document_id):
    return tuple(RetrievedKnowledgeChunk(
        chunk_id=uuid4(), document_id=document_id,
        document_title="Synthetic lecture", content_revision_id=uuid4(),
        index_revision_id=uuid4(), page_number=page,
        section="Methods",
        content=("The method updates weights after each example."
                 if page < 5 else "Gold lecture page."),
        token_count=20, embedding_space_hash=scope.embedding_space_hash,
        corpus_revision=scope.corpus_revision,
        vector_similarity=.8, lexical_score=.4, vector_rank=page,
        lexical_rank=page, fusion_score=.1,
    ) for page in range(1, 6))


def test_default_cli_reads_no_database_or_private_packet():
    result = subprocess.run(
        [sys.executable, str(Path(probe.__file__))],
        capture_output=True, text=True, check=True,
    )
    report = json.loads(result.stdout)
    assert report == {
        "schema": probe.SCHEMA, "status": "preflight_unexecuted",
        "provider_requests": 0, "database_reads": 0,
        "database_writes": 0, "release_gate_passed": False,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("gold_page,expected_sent", [(1, True), (5, False)])
async def test_retrieval_counts_gold_in_inspected_and_four_sent(
    monkeypatch, gold_page, expected_sent,
):
    case, scope = _case(gold_page), _scope()
    document_id = uuid4()
    chunks = _chunks(scope, document_id)
    retriever = _Retriever(scope, chunks)

    async def authorize(_cls, _db, **kwargs):
        assert kwargs["principal"].id == scope.principal_id
        assert kwargs["subject_id"] == scope.subject_id
        assert kwargs["query"] == case.question
        assert kwargs["policy"] == SOURCE_NAVIGATION_RETRIEVAL_POLICY
        return retriever

    async def gold(_db, _scope, _case):
        return {
            "document_id": document_id,
            "current_published_gold": True, "page_present": True,
            "page_indexed": True, "original_pdf_manifest_current": True,
            "gold_window_extracted": True,
        }

    monkeypatch.setattr(KnowledgeRetriever, "authorize", classmethod(authorize))
    monkeypatch.setattr(probe.base, "_read_gold", gold)
    db = _Db()
    vector = (1.0, 0.0)
    result = await probe.evaluate_case(db, scope, case, vector)
    assert db.statements == ["SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"]
    assert retriever.calls[0] == ("retrieve", vector, scope.embedding_space_hash)
    assert result["sql_gold_hit"] is True
    assert result["gold_inspected_hit"] is True
    assert result["gold_sent_hit"] is expected_sent
    assert result["inspected_pages"] == 5
    assert result["sent_pages"] == 4
    assert case.question not in json.dumps(result)
    assert str(document_id) not in json.dumps(result)


@pytest.mark.asyncio
async def test_scope_drift_refuses_before_gold_or_retrieval(monkeypatch):
    case, scope = _case(), _scope()
    retriever = _Retriever(scope, ())
    retriever.scope = AuthorizedKnowledgeScope(
        scope.principal_id, uuid4(), scope.corpus_revision,
        scope.embedding_space_hash, scope.document_ids,
    )

    async def authorize(_cls, _db, **_kwargs):
        return retriever

    async def no_gold(*_args):
        pytest.fail("Gold must not be read after scope drift")

    monkeypatch.setattr(KnowledgeRetriever, "authorize", classmethod(authorize))
    monkeypatch.setattr(probe.base, "_read_gold", no_gold)
    with pytest.raises(probe.Refusal, match="scope_changed"):
        await probe.evaluate_case(_Db(), scope, case, (1.0,))
    assert retriever.calls == []


@pytest.mark.asyncio
async def test_missing_current_gold_refuses_instead_of_lowering_denominator(monkeypatch):
    case, scope = _case(), _scope()
    retriever = _Retriever(scope, ())

    async def authorize(_cls, _db, **_kwargs):
        return retriever

    async def gold(_db, _scope, _case):
        return {
            "document_id": None,
            "current_published_gold": False, "page_present": False,
            "page_indexed": False, "original_pdf_manifest_current": False,
            "gold_window_extracted": False,
        }

    monkeypatch.setattr(KnowledgeRetriever, "authorize", classmethod(authorize))
    monkeypatch.setattr(probe.base, "_read_gold", gold)
    with pytest.raises(probe.Refusal, match="gold_unavailable"):
        await probe.evaluate_case(_Db(), scope, case, (1.0,))
    assert retriever.calls == []


def test_aggregate_keeps_unreviewed_usefulness_ungraded():
    observations = (
        {"group": "direct", "resolved": True, "sql_gold_hit": True,
         "gold_inspected_hit": True, "gold_sent_hit": False,
         "inspected_pages": 12, "sent_pages": 4},
        {"group": "follow_up", "resolved": False, "sql_gold_hit": False,
         "gold_inspected_hit": False, "gold_sent_hit": False,
         "inspected_pages": 0, "sent_pages": 0},
    )
    report = probe.aggregate(observations)
    assert report["cases"] == 2
    assert report["gold_inspected_hit"] == 1
    assert report["gold_sent_hit"] == 0
    assert report["any_useful_page_hit"] == "ungraded"
    assert report["quality_labels_independent_for_this_slate"] is False
    assert "question" not in json.dumps(report)


def test_runtime_refuses_credentials_and_nonlocal_database(monkeypatch):
    scope = _scope()
    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        "app.models.knowledge.embedding_space_hash",
        lambda _identity: scope.embedding_space_hash,
    )
    settings = SimpleNamespace(
        database_url="postgresql+asyncpg://test:test@db/cardchemy",
        environment="development", rag_ask_enabled=False,
        flashcard_ai_api_key_value=None, rag_ai_api_key_value=None,
        rag_embedding_api_key_value=None, rag_source_judge_api_key_value=None,
        rag_embedding_model=probe.base.VECTOR_MODEL,
        rag_embedding_space_identity=("test",),
    )
    probe._require_safe_runtime(settings, scope)
    settings.rag_source_judge_api_key_value = "synthetic-test-key"
    with pytest.raises(probe.Refusal, match="ai_credentials_present"):
        probe._require_safe_runtime(settings, scope)
    settings.rag_source_judge_api_key_value = None
    settings.database_url = "postgresql+asyncpg://test:test@example.invalid/cardchemy"
    with pytest.raises(probe.Refusal, match="database_target_invalid"):
        probe._require_safe_runtime(settings, scope)


@pytest.mark.asyncio
async def test_execute_writes_only_aggregate_to_exclusive_private_output(
    monkeypatch, tmp_path,
):
    from app import config, database

    case, scope = _case(), _scope()
    roster_path = tmp_path / "roster.json"
    vector_path = tmp_path / "vectors.json"
    output_path = tmp_path / "result.json"
    roster_path.write_text(json.dumps({"cases": [asdict(case)]}), encoding="utf-8")
    vector_path.write_text(json.dumps({"vector": [1.0]}), encoding="utf-8")
    monkeypatch.setattr(probe.base, "PRIVATE_MOUNT", tmp_path)
    monkeypatch.setattr(probe, "EXPECTED_CASES", 1)
    monkeypatch.setattr(probe, "ROSTER_SHA256", sha256(roster_path.read_bytes()).hexdigest())
    monkeypatch.setattr(probe, "VECTOR_SHA256", sha256(vector_path.read_bytes()).hexdigest())
    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(probe, "_require_safe_runtime", lambda _settings, _scope: None)
    monkeypatch.setattr(probe, "_runtime_sha256", lambda: "c" * 64)
    closed = []

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def rollback(self):
            closed.append("rollback")

    async def close_database():
        closed.append("close")

    async def evaluate(_db, _scope, _case, _vector):
        return {
            "group": "direct", "resolved": True, "sql_gold_hit": True,
            "gold_inspected_hit": True, "gold_sent_hit": False,
            "inspected_pages": 5, "sent_pages": 4,
        }

    monkeypatch.setattr(database, "async_session_maker", _Session)
    monkeypatch.setattr(database, "close_database", close_database)
    monkeypatch.setattr(probe, "evaluate_case", evaluate)
    report = await probe.execute(
        (case,), scope, {case.case_id: (1.0,)},
        roster_path, vector_path, output_path,
    )
    assert report["aggregate"]["gold_sent_hit"] == 0
    assert report["provider_requests"] == report["answer_requests"] == report["database_writes"] == 0
    assert closed == ["rollback", "close"]
    encoded = output_path.read_text(encoding="ascii")
    assert case.question not in encoded
    assert str(scope.principal_id) not in encoded
    assert json.loads(encoded)["aggregate"]["any_useful_page_hit"] == "ungraded"
    with pytest.raises(probe.Refusal, match="output_exists"):
        await probe.execute(
            (case,), scope, {case.case_id: (1.0,)},
            roster_path, vector_path, output_path,
        )
