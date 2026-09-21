"""Deterministic Phase 19 RAG corpus loading and metric contracts.

This module performs no provider calls.  It gives the offline and PostgreSQL
tests one reviewed definition of recall, ranking, support, exposure, latency,
throughput, and bounded context/usage measurements.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Iterable, Mapping, Sequence


CORPUS_PATH = Path(__file__).resolve().parents[1] / "fixtures/rag_eval/subject_knowledge_v2.json"


@dataclass(frozen=True, slots=True)
class EvaluationObservation:
    case_id: str
    expected_pages: tuple[str, ...]
    retrieved_pages: tuple[str, ...]
    expected_outcome: str
    actual_outcome: str
    citations_valid: bool
    claims_supported: bool
    forbidden_sources_exposed: int = 0
    duplicate_overlap_count: int = 0
    latency_milliseconds: float = 0.0
    history_context_messages: int = 0
    provider_calls: int = 0


def load_corpus(path: Path = CORPUS_PATH) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _percentile_95(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, int(len(ordered) * 0.95 + 0.999999) - 1)]


def evaluate(
    observations: Iterable[EvaluationObservation],
    *,
    indexed_chunks: int,
    indexing_seconds: float,
) -> Mapping[str, float | int]:
    items = tuple(observations)
    feasible = tuple(item for item in items if item.expected_outcome == "answer")
    abstentions = tuple(item for item in items if item.expected_outcome == "abstain")
    rejected = tuple(item for item in items if item.expected_outcome == "reject")

    recall_scores: list[float] = []
    reciprocal_ranks: list[float] = []
    for item in feasible:
        expected = set(item.expected_pages)
        retrieved = set(item.retrieved_pages)
        recall_scores.append(len(expected & retrieved) / len(expected) if expected else 1.0)
        ranks = [item.retrieved_pages.index(page) + 1 for page in expected if page in retrieved]
        reciprocal_ranks.append(1.0 / min(ranks) if ranks else 0.0)

    total_retrieved = sum(len(item.retrieved_pages) for item in items)
    return {
        "retrieval_recall_at_k": fmean(recall_scores) if recall_scores else 1.0,
        "mean_reciprocal_rank": fmean(reciprocal_ranks) if reciprocal_ranks else 1.0,
        "supported_claim_rate": (
            sum(item.claims_supported and item.actual_outcome == "answer" for item in feasible)
            / len(feasible) if feasible else 1.0
        ),
        "unsupported_abstention_rate": (
            sum(item.actual_outcome == "abstain" for item in abstentions) / len(abstentions)
            if abstentions else 1.0
        ),
        "citation_validity_rate": (
            sum(item.citations_valid and item.actual_outcome == "reject" for item in rejected)
            / len(rejected) if rejected else 1.0
        ),
        "forbidden_source_exposure_count": sum(item.forbidden_sources_exposed for item in items),
        "overlap_duplicate_rate": (
            sum(item.duplicate_overlap_count for item in items) / total_retrieved
            if total_retrieved else 0.0
        ),
        "offline_retrieval_p95_milliseconds": _percentile_95(
            [item.latency_milliseconds for item in items]
        ),
        "indexed_chunks_per_second": (
            indexed_chunks / indexing_seconds if indexing_seconds > 0 else 0.0
        ),
        "maximum_history_context_messages": max(
            (item.history_context_messages for item in items), default=0
        ),
        "maximum_provider_calls_per_answer": max(
            (item.provider_calls for item in items), default=0
        ),
    }


def assert_thresholds(metrics: Mapping[str, float | int], thresholds: Mapping[str, float | int]) -> None:
    minimums = {
        "retrieval_recall_at_k",
        "mean_reciprocal_rank",
        "supported_claim_rate",
        "unsupported_abstention_rate",
        "citation_validity_rate",
        "minimum_indexed_chunks_per_second",
    }
    aliases = {"minimum_indexed_chunks_per_second": "indexed_chunks_per_second"}
    for threshold_name, expected in thresholds.items():
        metric_name = aliases.get(threshold_name, threshold_name)
        if threshold_name.endswith("_max"):
            metric_name = threshold_name.removesuffix("_max")
            assert metrics[metric_name] <= expected, (metric_name, metrics[metric_name], expected)
        elif threshold_name in minimums:
            assert metrics[metric_name] >= expected, (metric_name, metrics[metric_name], expected)
        else:
            assert metrics[metric_name] <= expected, (metric_name, metrics[metric_name], expected)
