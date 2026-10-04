"""Keyless guards for the read-only private retrieval ablation."""

import importlib.util
from pathlib import Path
import sys
from uuid import uuid4

import pytest

from app.services.knowledge_retrieval import RetrievedKnowledgeChunk
from app.models.vector import EMBEDDING_DIMENSIONS


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/evaluate_private_retrieval_ablation.py"
spec = importlib.util.spec_from_file_location("private_retrieval_ablation", SCRIPT)
assert spec is not None and spec.loader is not None
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)


def _chunk(content: str, *, page: int = 22) -> RetrievedKnowledgeChunk:
    return RetrievedKnowledgeChunk(
        chunk_id=uuid4(), document_id=uuid4(),
        document_title="private-title-sentinel",
        content_revision_id=uuid4(), index_revision_id=uuid4(),
        page_number=page, section="private-section-sentinel",
        content=content, token_count=20,
        embedding_space_hash="a" * 64, corpus_revision=1,
        vector_similarity=None, lexical_score=None, vector_rank=None,
        lexical_rank=None, fusion_score=0.0,
    )


def test_fixed_policies_keep_exact_baseline_and_candidate_ablation_only():
    assert probe.POLICIES[0] is probe.EXACT_V1_POLICY
    assert all(policy.max_results == 5 for policy in probe.POLICIES)
    assert all(policy.minimum_vector_similarity == 0.5 for policy in probe.POLICIES)
    assert all(policy.candidate_limit_per_channel == 20 for policy in probe.POLICIES)
    assert [policy.policy_id for policy in probe.POLICIES] == [
        "hybrid_exact_v1", "bounded_and_12", "bounded_or_12",
        "bounded_or_section_12", "bounded_or_section_diverse_12",
    ]
    assert all(
        probe._topic_group(probe.PROBES[i].label)
        != probe._topic_group(probe.PROBES[probe._different_topic_index(i)].label)
        for i in range(len(probe.PROBES))
    )


def test_source_selection_refuses_ambiguous_or_missing_page():
    selected = _chunk("BLEU means Bilingual Evaluation Understudy.")
    case = probe.PROBES[0]
    assert probe._select_source(case, ()) is None
    assert probe._select_source(case, (selected,)) is selected
    assert probe._select_source(case, (selected, selected)) is None
    assert probe._select_source(case, (_chunk("Different concept."),)) is None


def test_vector_parser_rejects_bad_shape_and_nonfinite_values():
    valid = probe._vector("[1," + "0," * (EMBEDDING_DIMENSIONS - 2) + "0]")
    assert len(valid) == EMBEDDING_DIMENSIONS
    for value in ("[]", "[0]", "[1,NaN]", "not a vector"):
        with pytest.raises(probe.EvaluationUnavailable) as error:
            probe._vector(value)
        assert error.value.code == "vector_unavailable"


def test_summary_and_cutover_are_content_free_and_never_authorize():
    source = _chunk("private-source-sentinel")
    rows = [{
        "label": "bleu_acronym", "policy": "hybrid_exact_v1",
        "mode": "source_chunk_oracle", "page_rank": 2,
        "source_chunk_rank": 2, "selected_count": 5,
        "overlap_count": 0, "query_ms": 9.3, "scope_violations": 0,
    }]
    summary = probe._summary(rows, "hybrid_exact_v1", "source_chunk_oracle")
    assert summary["confirmed_page_recall_at_5"] == 1.0
    assert summary["confirmed_page_mrr"] == 0.5
    assert probe._cutover_decision([summary]).startswith("blocked_")
    rendered = probe.json.dumps(summary)
    assert source.content not in rendered
    assert source.document_title not in rendered
    assert str(source.chunk_id) not in rendered


def test_overlap_count_uses_term_containment_not_only_exact_text():
    first = _chunk("cosine compares vector angles rather than magnitudes")
    second = _chunk("cosine compares vector angles rather than magnitudes and scale")
    different = _chunk("BLEU scores n gram overlap")
    assert probe._overlap_count((first, second, different)) == 1


def test_authorized_sql_and_operator_gate(monkeypatch, capsys):
    for query in (probe._ELIGIBLE_ROWS, probe._SOURCE_VECTORS):
        statement = str(query)
        assert "eligible_subject_knowledge_chunks" in statement
        assert "active_embedding_space_hash" in statement
        assert "corpus_revision" in statement
        assert "principal.role" in statement
        assert "document_ids" in statement
    monkeypatch.setattr(sys, "argv", ["evaluate_private_retrieval_ablation.py"])
    monkeypatch.setattr(probe, "async_session_maker", lambda: pytest.fail("DB read not authorized"))
    assert probe.main() == 1
    assert "operator_selection_required" in capsys.readouterr().out
