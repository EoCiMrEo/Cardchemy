"""No-provider admission check for the frozen public Knowledge holdout.

This checks the original source freeze, independent labels, current selector
bytes, extraction, and embedding admission bounds. It does not create a
database, construct an SDK client, contact an API, or print source content.
The paid disposable run remains a separate, explicitly approved operation.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import preflight_public_knowledge_holdout as source_preflight  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    "preflight-manifest.json",
    "1dda8eae4ab998bae83daa142ddb0caab6699ddf02695c875ebaf694c53e0251",
)
HOLDOUT = (
    "holdout-v2.json",
    "d841ae6489995f884266abf212f7c63f14952a348419bfc7aa42e923c00d6b12",
)
LABELS = (
    "holdout-v2-independent-labels.json",
    "13bf7aa9518b5d125948aa4a98045ffd4f3bcdba9761d010c8750fcb8b259877",
)
PRELABEL = (
    "prelabel-freeze.json",
    "cf28e6c4939c16b962cdcec91b6e2d5f0e6e917025f91b2f9e9fd1a5b0bf8156",
)
LABEL_SCHEMA = "cardchemy_lane6_holdout_v2_independent_original_pdf_labels_v1"
MAX_LABEL_BYTES = 32_768
RUNTIME_PATHS = frozenset({
    "backend/app/ai/source_navigation.py",
    "backend/app/ai/related_evidence.py",
    "backend/app/services/knowledge_retrieval.py",
    "backend/scripts/diagnose_source_navigation.py",
})


class Refusal(RuntimeError):
    """Fixed safe failure code; never include PDF, question, or parser text."""


def _frozen_json(directory: Path, frozen: tuple[str, str]) -> dict:
    name, expected_sha256 = frozen
    path = source_preflight._within_temp(directory / name)
    if (path.parent != directory or not path.is_file()
        or not 0 < path.stat().st_size <= MAX_LABEL_BYTES):
        raise Refusal("frozen_artifact_unavailable")
    try:
        raw = path.read_bytes()
    except OSError:
        raise Refusal("frozen_artifact_unavailable") from None
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise Refusal("frozen_artifact_changed")
    try:
        result = json.loads(raw)
    except (UnicodeDecodeError, ValueError):
        raise Refusal("frozen_artifact_invalid") from None
    if not isinstance(result, dict):
        raise Refusal("frozen_artifact_invalid")
    return result


def check_freeze(directory: Path, cases: list[dict[str, object]]) -> None:
    labels = _frozen_json(directory, LABELS)
    receipt = _frozen_json(directory, PRELABEL)
    if (
        labels.get("schema") != LABEL_SCHEMA
        or labels.get("packet_sha256") != HOLDOUT[1]
        or labels.get("selector_outputs_inspected") is not False
        or labels.get("provider_requests") != 0
        or labels.get("database_writes") != 0
        or not isinstance(labels.get("cases"), list)
        or len(labels["cases"]) != 12
        or receipt.get("selector_results_seen") is not False
        or receipt.get("question_labels_frozen") is not False
        or receipt.get("provider_requests") != 0
        or receipt.get("database_writes") != 0
    ):
        raise Refusal("freeze_invalid")
    runtime_hashes = receipt.get("runtime_hashes")
    if not isinstance(runtime_hashes, dict) or set(runtime_hashes) != RUNTIME_PATHS:
        raise Refusal("freeze_invalid")
    for name, expected in runtime_hashes.items():
        try:
            actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        except OSError:
            raise Refusal("runtime_changed_since_freeze") from None
        if not isinstance(expected, str) or actual != expected:
            raise Refusal("runtime_changed_since_freeze")

    by_id = {case["id"]: case for case in cases}
    source_groups = Counter((case["document_sha256"], case["group"]) for case in cases)
    source_pages = {(case["document_sha256"], case["gold_physical_page"]) for case in cases}
    if (len(by_id) != 12 or len(source_groups) != 6
        or set(source_groups.values()) != {2} or len(source_pages) != 12):
        raise Refusal("freeze_invalid")
    seen: set[str] = set()
    for label in labels["cases"]:
        if not isinstance(label, dict):
            raise Refusal("freeze_invalid")
        case_id = label.get("id")
        if not isinstance(case_id, str) or case_id not in by_id or case_id in seen:
            raise Refusal("freeze_invalid")
        seen.add(case_id)
        case = by_id[case_id]
        window = case["gold_window_exact_extracted_text"]
        expected_window_hash = hashlib.sha256(window.encode("utf-8")).hexdigest()
        if (
            label.get("group") != case["group"]
            or label.get("document_sha256") != case["document_sha256"]
            or label.get("physical_page") != case["gold_physical_page"]
            or label.get("exact_window_sha256") != expected_window_hash
            or label.get("source_identity") != "Yes"
            or label.get("exact_app_extracted_substring") != "Yes"
            or label.get("excerpt_relation_and_conditions") != "Yes"
            or label.get("visual_page_useful") != "Yes"
            or label.get("followup_referent") != (
                "Yes" if case["group"] == "follow_up" else "N/A"
            )
        ):
            raise Refusal("freeze_invalid")


def preflight(directory: Path) -> dict[str, object]:
    source_preflight._check_code_defaults()
    directory = source_preflight._within_temp(directory)
    manifest_dir, sources, _ = source_preflight.load_manifest(
        directory / MANIFEST[0], MANIFEST[1]
    )
    if manifest_dir != directory:
        raise Refusal("frozen_artifact_unavailable")
    cases, query_tokens, _ = source_preflight.load_holdout(
        directory / HOLDOUT[0], HOLDOUT[1], directory=directory,
        source_hashes={source["sha256"] for source in sources},
    )
    check_freeze(directory, cases)
    report = source_preflight.inspect_sources(directory, sources, cases)
    report.update({
        "status": "provider_free_preflight_passed",
        "manifest_sha256": MANIFEST[1],
        "holdout_sha256": HOLDOUT[1],
        "independent_labels_sha256": LABELS[1],
        "prelabel_sha256": PRELABEL[1],
        "query_case_count": len(cases),
        "estimated_query_tokens": query_tokens,
        "estimated_total_tokens": report["estimated_document_tokens"] + query_tokens,
        "runtime_matches_prelabel_freeze": True,
        "paid_execution_authorized": False,
    })
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--temp-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = preflight(args.temp_dir)
    except (Refusal, source_preflight.Refusal) as exc:
        raise SystemExit(f"Public Knowledge disposable run preflight refused: {exc}") from None
    print(json.dumps(report, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
