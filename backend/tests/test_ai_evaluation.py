import json
from pathlib import Path

from app.ai.grounding import normalize_evidence


CORPUS = Path(__file__).parent / "fixtures" / "ai_eval" / "manifest.json"


def test_fixed_evaluation_corpus_has_all_release_cases_and_thresholds():
    manifest = json.loads(CORPUS.read_text(encoding="utf-8"))
    case_ids = {case["id"] for case in manifest["cases"]}

    assert case_ids == {
        "short_fact_sheet",
        "long_structured_document",
        "prompt_injection_document",
        "duplicate_and_invalid_candidates",
        "unicode_and_normalization",
    }
    assert manifest["thresholds"]["schema_valid_rate"] == 1.0
    assert manifest["thresholds"]["grounded_rate"] == 1.0
    assert manifest["thresholds"]["duplicate_rate"] == 0.0
    assert manifest["thresholds"]["partial_sets_on_failure"] == 0


def test_unicode_evidence_normalization_is_stable():
    manifest = json.loads(CORPUS.read_text(encoding="utf-8"))
    case = next(item for item in manifest["cases"] if item["id"] == "unicode_and_normalization")
    first, second, third, fourth = case["samples"]
    assert normalize_evidence(first) == normalize_evidence(second)
    assert normalize_evidence(third).replace("—", " ") == normalize_evidence(fourth)
