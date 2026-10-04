"""Evaluate the pinned local Ask verifier without provider or network calls."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.ai.answering import ValidatedAnswerClaim, normalize_text  # noqa: E402
from app.ai.local_support import (  # noqa: E402
    LOCAL_SUPPORT_POLICY_VERSION,
    NLI_MODEL_ID,
    NLI_MODEL_REVISION,
    QA_MODEL_ID,
    QA_MODEL_REVISION,
    create_local_support_verifier,
)
from app.services.knowledge_retrieval import RetrievedKnowledgeChunk  # noqa: E402


DEFAULT_FIXTURE = (
    BACKEND / "tests" / "fixtures" / "rag_eval"
    / "product_quality_lane5_local_support_v1.json"
)
MAX_BUNDLE_BYTES = 200 * 1024 * 1024
MAX_STARTUP_MS = 10_000
MAX_P95_MS = 1_000
MAX_RSS_INCREASE_MIB = 512


def _rss_bytes() -> int:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCounters),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        process = kernel32.GetCurrentProcess()
        if not psapi.GetProcessMemoryInfo(
            process, ctypes.byref(counters), counters.cb
        ):
            raise RuntimeError("Could not read process memory")
        return int(counters.WorkingSetSize)
    status = Path("/proc/self/status")
    if status.is_file():
        for line in status.read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    import resource

    scale = 1 if sys.platform == "darwin" else 1024
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * scale


def _chunk(case: dict[str, object]) -> RetrievedKnowledgeChunk:
    quote = str(case["source_quote"])
    evidence = [str(value) for value in case.get("additional_evidence", [])]
    content = " ".join([quote, *evidence])
    return RetrievedKnowledgeChunk(
        chunk_id=uuid4(), document_id=uuid4(), document_title="Synthetic release corpus",
        content_revision_id=uuid4(), index_revision_id=uuid4(), page_number=1,
        section="Release evaluation", content=content,
        token_count=max(1, math.ceil(len(content) / 4)),
        embedding_space_hash="a" * 64, corpus_revision=1,
        vector_similarity=1.0, lexical_score=1.0, vector_rank=1,
        lexical_rank=1, fusion_score=1.0,
    )


def evaluate(model_dir: Path, fixture_path: Path, repetitions: int) -> dict[str, object]:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if payload.get("policy_version") != LOCAL_SUPPORT_POLICY_VERSION:
        raise RuntimeError("Fixture policy does not match the runtime policy")
    if not isinstance(cases, list) or len(cases) < 10:
        raise RuntimeError("Release corpus must contain at least ten cases")
    supported_count = sum(bool(case["expected_supported"]) for case in cases)
    conflict_count = sum(bool(case.get("additional_evidence")) for case in cases)
    if supported_count < 5 or len(cases) - supported_count < 5 or conflict_count < 2:
        raise RuntimeError("Release corpus is missing supported, unsupported, or conflict coverage")

    bundle_bytes = sum(path.stat().st_size for path in model_dir.rglob("*") if path.is_file())
    rss_before = _rss_bytes()
    started = time.perf_counter()
    verifier = create_local_support_verifier(model_dir)
    startup_ms = (time.perf_counter() - started) * 1000
    rss_loaded = _rss_bytes()
    latencies: list[float] = []
    passed = 0
    supported_false_rejections = 0
    unsupported_false_accepts = 0
    case_results: list[dict[str, object]] = []
    design_verdicts: dict[str, list[tuple[bool, bool]]] = {
        "literal_quote_only": [],
        "nli_only": [],
        "extractive_literal_only": [],
        "nli_plus_extractive_qa": [],
    }

    for case in cases:
        case_passed = True
        expected = bool(case["expected_supported"])
        for _ in range(repetitions):
            chunk = _chunk(case)
            claim = ValidatedAnswerClaim(
                statement=str(case["statement"]),
                source=chunk,
                source_quote=str(case["source_quote"]),
            )
            started = time.perf_counter()
            actual = verifier.supports(
                question=str(case["question"]), claims=(claim,), chunks=(chunk,)
            )
            latencies.append((time.perf_counter() - started) * 1000)
            case_passed = case_passed and actual is expected
            if expected and not actual:
                supported_false_rejections += 1
            if not expected and actual:
                unsupported_false_accepts += 1
        passed += int(case_passed)
        case_results.append({"id": str(case["id"]), "passed": case_passed})
        quote, statement, question = (
            str(case["source_quote"]), str(case["statement"]), str(case["question"])
        )
        relation = verifier._nli.score(quote, statement)
        nli_only = relation.entailment >= 0.80 and relation.entailment > max(
            relation.contradiction, relation.neutral
        )
        for sentence in case.get("additional_evidence", []):
            conflict = verifier._nli.score(str(sentence), statement)
            if conflict.contradiction >= 0.50 and conflict.contradiction > max(
                conflict.entailment, conflict.neutral
            ):
                nli_only = False
        answer_span = verifier._qa.answer(question, quote)
        candidates = {
            "literal_quote_only": normalize_text(quote) in normalize_text(statement),
            "nli_only": nli_only,
            "extractive_literal_only": bool(
                answer_span and normalize_text(answer_span) in normalize_text(statement)
            ),
            "nli_plus_extractive_qa": actual,
        }
        for name, verdict in candidates.items():
            design_verdicts[name].append((expected, verdict))

    design_comparison = {
        name: {
            "supported_false_rejections": sum(expected and not verdict for expected, verdict in verdicts),
            "unsupported_false_accepts": sum(not expected and verdict for expected, verdict in verdicts),
            "correct_cases": sum(expected is verdict for expected, verdict in verdicts),
        }
        for name, verdicts in design_verdicts.items()
    }

    ordered = sorted(latencies)
    p95 = ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]
    report = {
        "fixture_version": payload["version"],
        "policy_version": LOCAL_SUPPORT_POLICY_VERSION,
        "models": [
            {"id": NLI_MODEL_ID, "revision": NLI_MODEL_REVISION, "license": "Apache-2.0"},
            {"id": QA_MODEL_ID, "revision": QA_MODEL_REVISION, "license": "CC-BY-4.0"},
        ],
        "case_count": len(cases),
        "repetitions": repetitions,
        "passed_case_count": passed,
        "supported_false_rejections": supported_false_rejections,
        "unsupported_false_accepts": unsupported_false_accepts,
        "bundle_bytes": bundle_bytes,
        "startup_milliseconds": round(startup_ms, 3),
        "latency_milliseconds": {
            "median": round(statistics.median(latencies), 3),
            "p95": round(p95, 3),
            "maximum": round(max(latencies), 3),
        },
        "rss_before_mib": round(rss_before / 1024 / 1024, 3),
        "rss_loaded_mib": round(rss_loaded / 1024 / 1024, 3),
        "rss_increase_mib": round(max(0, rss_loaded - rss_before) / 1024 / 1024, 3),
        "thresholds": {
            "maximum_bundle_bytes": MAX_BUNDLE_BYTES,
            "maximum_startup_milliseconds": MAX_STARTUP_MS,
            "maximum_p95_milliseconds": MAX_P95_MS,
            "maximum_rss_increase_mib": MAX_RSS_INCREASE_MIB,
            "required_case_accuracy_percent": 100,
        },
        "case_results": case_results,
        "design_comparison": design_comparison,
    }
    report["passed"] = bool(
        passed == len(cases)
        and supported_false_rejections == 0
        and unsupported_false_accepts == 0
        and bundle_bytes <= MAX_BUNDLE_BYTES
        and startup_ms <= MAX_STARTUP_MS
        and p95 <= MAX_P95_MS
        and report["rss_increase_mib"] <= MAX_RSS_INCREASE_MIB
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--repetitions", type=int, default=3, choices=range(1, 11))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate(args.model_dir.resolve(), args.fixture.resolve(), args.repetitions)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
