"""Invented public proof records; no keys, private sources or provider calls."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import public_visual_parser_equivalence_v1 as proof


def historical_verdict():
    value = {"question_status": "clear", "pages": [
        {"id": sid, "usefulness": "direct" if sid == "S01" else "unrelated",
         "cue_locates": sid == "S01"} for sid in proof.ISSUED]}
    return dict(proof.strict.parse_verdict(proof.strict.canonical(value), proof.ISSUED),
                schema_version="public_visual_page_source_v2")


def invented_proof(monkeypatch):
    records, files = [], {}
    for index in range(138):
        state = "completed" if index < 118 else "failed"
        gid = f"Q{index:03d}"
        claim_path = Path(f"invented/claim-{index}.json")
        receipt_path = Path(f"invented/receipt-{index}.json")
        claim = {"rest_sha256": "a" * 64}
        claim_sha = proof.digest(proof.strict.canonical(claim))
        verdict = historical_verdict() if state == "completed" else None
        receipt = {"group_id": gid, "state": state, "request_sha256": "a" * 64,
            "attempt_claim_sha256": claim_sha, "verdict": verdict,
            "selected_ids": verdict["selected_ids"] if verdict else [],
            "question_status": "clear" if verdict else None}
        receipt_sha = proof.digest(proof.strict.canonical(receipt))
        files[claim_path], files[receipt_path] = (claim, claim_sha), (receipt, receipt_sha)
        records.append({"state": state, "group_id": gid, "claim_path": str(claim_path),
            "claim_sha256": claim_sha, "receipt_path": str(receipt_path), "receipt_sha256": receipt_sha})
    value = {"schema": "public_visual_parser_equivalence_v1", "valid_equivalent": 118,
        "failed_preserved": 20, "records": records, "historical_failed_results_credited": 0,
        "provider_calls": 0, "parser_code_hashes": {"invented": "b" * 64},
        "old_parser": "visual_source_id_v3", "new_parser": "visual_source_id_v4"}
    target, sha = Path("invented/proof.json"), "c" * 64
    files[target] = (value, sha)
    def read(path, expected=None):
        data, frozen = files[path]
        proof.require(expected is None or frozen == expected, "proof_file_changed")
        return data, frozen
    monkeypatch.setattr(proof, "read", read)
    monkeypatch.setattr(proof, "parser_hashes", lambda: {"invented": "b" * 64})
    return target, sha, value, files


def test_inherited_successes_are_selection_equivalent_and_failures_remain_failed(monkeypatch):
    target, sha, value, files = invented_proof(monkeypatch)
    before = copy.deepcopy(files)
    result = proof.validate(target, sha)
    assert result["valid_equivalent"] == 118 and result["failed_preserved"] == 20
    assert result["historical_failed_results_credited"] == 0 and result["mixed_historical_parser_lineage"]
    assert files == before


@pytest.mark.parametrize("mutation", ["code", "old_selection", "failed_verdict", "request", "state", "record_hash"])
def test_changed_or_unusable_historical_proof_cannot_be_admitted(monkeypatch, mutation):
    target, sha, value, files = invented_proof(monkeypatch)
    first = files[Path(value["records"][0]["receipt_path"])][0]
    if mutation == "code": value["parser_code_hashes"]["invented"] = "d" * 64
    elif mutation == "old_selection": first["verdict"]["selected_ids"] = ["S99"]
    elif mutation == "failed_verdict":
        files[Path(value["records"][-1]["receipt_path"])][0]["verdict"] = historical_verdict()
    elif mutation == "request": first["request_sha256"] = "e" * 64
    elif mutation == "state": value["records"][0]["state"] = "failed"
    else: value["records"][0]["receipt_sha256"] = "f" * 64
    with pytest.raises(proof.EquivalenceError):
        proof.validate(target, sha)


def test_failed_raw_verdict_cannot_be_reconstructed_as_a_historical_success():
    verdict = historical_verdict()
    verdict["page_verdicts"][1]["cue_locates"] = True
    with pytest.raises(proof.strict.VisualSourceJudgmentError, match="cue_without_useful_page"):
        proof.compare(verdict)
