"""Keyless public verdict equivalence proof; no provider or runtime activation."""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
from app.ai import source_judgment_visual_v3 as strict
from app.ai import source_judgment_visual_v4 as candidate

PROOF_PATH = REPO / ".agent/.verification/visual-parser-v4-equivalence-20261002.json"
PARSER_CODE_PATHS = (
    "backend/app/ai/source_judgment_visual.py",
    "backend/app/ai/source_judgment_visual_v2.py",
    "backend/app/ai/source_judgment_visual_v3.py",
    "backend/app/ai/source_judgment_visual_v4.py",
    "backend/tests/test_source_judgment_visual_v4.py",
    "scripts/public_visual_parser_equivalence_v1.py",
)
ISSUED = ["S01", "S02", "S03", "S04"]


class EquivalenceError(ValueError):
    """Finite diagnostic without source or response content."""


def require(ok: bool, code: str) -> None:
    if not ok:
        raise EquivalenceError(code)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read(path: Path, sha: str | None = None) -> tuple[dict, str]:
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 262144,
            "proof_file_invalid")
    raw = path.read_bytes()
    found = digest(raw)
    require(sha is None or found == sha, "proof_file_changed")
    value = json.loads(raw, object_pairs_hook=strict._unique, parse_constant=strict._reject_constant)
    require(type(value) is dict, "proof_object_invalid")
    return value, found


def parser_hashes() -> dict:
    return {name: digest((REPO / name).read_bytes()) for name in PARSER_CODE_PATHS}


def compare(verdict: dict) -> None:
    raw = strict.canonical({"question_status": verdict["question_status"], "pages": verdict["page_verdicts"]})
    prior, after = strict.parse_verdict(raw, ISSUED), candidate.parse_verdict(raw, ISSUED)
    require(after["excluded_cue_conflicts"] == 0 and
            {k: v for k, v in after.items() if k != "excluded_cue_conflicts"} ==
            dict(prior, schema_version=candidate.CONTRACT_VERSION) and
            all(prior[k] == verdict[k] for k in ("question_status", "page_verdicts", "selected_ids",
                                                "unverified_references", "generated_answer")),
            "historical_selection_changed")


def enumerate_contract() -> dict:
    labels = sorted(strict.v2.v1.LABELS)
    choices = list(itertools.product(labels, (False, True)))
    stats = {"combinations": 0, "old_valid_equivalent": 0, "new_only_conservative": 0,
             "clarification_rejected": 0}
    for count in range(1, 5):
        ids = ISSUED[:count]
        for rows in itertools.product(choices, repeat=count):
            for status in ("clear", "needs_clarification"):
                value = {"question_status": status, "pages": [
                    {"id": sid, "usefulness": label, "cue_locates": flag}
                    for sid, (label, flag) in zip(ids, rows)]}
                raw = strict.canonical(value)
                stats["combinations"] += 1
                try:
                    old = strict.parse_verdict(raw, ids)
                    old_error = None
                except strict.VisualSourceJudgmentError as error:
                    old, old_error = None, str(error)
                try:
                    new = candidate.parse_verdict(raw, ids)
                except strict.VisualSourceJudgmentError as error:
                    require(old is None and old_error in {"cue_without_useful_page", "clarification_qualified_page"}
                            and str(error) == "clarification_qualified_page", "unexpected_rejection_change")
                    stats["clarification_rejected"] += 1
                    continue
                eligible = [sid for sid, (label, flag) in zip(ids, rows)
                            if label in strict.v2.v1.QUALIFYING and flag]
                eligible.sort(key=lambda sid: (rows[ids.index(sid)][0] != "direct", ids.index(sid)))
                require(new["selected_ids"] == eligible[:3], "unsafe_new_selection")
                if old is None:
                    require(old_error == "cue_without_useful_page", "unexpected_acceptance_change")
                    stats["new_only_conservative"] += 1
                else:
                    require(new["excluded_cue_conflicts"] == 0 and
                            {k: v for k, v in new.items() if k != "excluded_cue_conflicts"} ==
                            dict(old, schema_version=candidate.CONTRACT_VERSION), "valid_selection_changed")
                    stats["old_valid_equivalent"] += 1
    require(stats == {"combinations": 22220, "old_valid_equivalent": 2920,
                     "new_only_conservative": 9744, "clarification_rejected": 9556}, "enumeration_changed")
    return stats


def build() -> dict:
    # Load existing public metadata only. No main/execute/key function is used.
    import run_visual_public_heldout_v10 as terminal
    report_path = REPO / ".agent/.verification/public-heldout-v10-terminal-20261002.json"
    report, report_sha = read(report_path, "a2921593d26c6285a71698584e37f6e21c1a803f51f533b1ffd00ae94e6836d6")
    require(report["caller_code_sha256"] == terminal.code_hashes(), "legacy_code_changed")
    chain, node = {}, terminal
    for version in range(10, 0, -1):
        chain[version] = node
        if version > 1:
            node = getattr(node, "parent_trial", getattr(node, "previous_trial", None))
            require(node is not None, "legacy_chain_invalid")
    scopes = []
    for version in range(1, 11):
        owner = chain[version]
        if version == 10:
            out = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-public-heldout-v10-20261002-d1a171bb")
        else:
            nxt = chain[version + 1]
            out = nxt.OLD_RESULT_PATH.parent if version == 1 else nxt.PARENT_OUTPUT
        scopes.append(("heldout", version, out, REPO / f".agent/.verification/visual-public-heldout-v{version}-ledger", owner))
    cal = terminal.calibration
    calibration = {5: cal, 4: cal.checkpoint_previous, 3: cal.checkpoint_previous.checkpoint_previous, 2: cal.previous}
    for version in (2, 3, 4, 5):
        owner = calibration[version]
        out = chain[1].CALIBRATION_RESULT_PATH.parent if version == 5 else calibration[version + 1].OLD_RESULT_PATH.parent
        scopes.append(("calibration", version, out, REPO / f".agent/.verification/visual-public-calibration-v{version}-ledger", owner))
    records, valid, failed = [], 0, 0
    for kind, version, out, ledger, owner in scopes:
        for path in sorted(out.glob("attempt-*.json")):
            receipt, receipt_sha = read(path)
            gid = receipt["group_id"]
            claim_path = ledger / f"{owner.AUTHORIZATION_ID}-{gid}.claim.json"
            claim, claim_sha = read(claim_path)
            require(claim["authorization_id"] == owner.AUTHORIZATION_ID and
                    receipt["attempt_claim_sha256"] == claim_sha and receipt["request_sha256"] == claim["rest_sha256"],
                    "legacy_receipt_binding_changed")
            if receipt["state"] == "completed":
                terminal.require(terminal.calibration.prototype.parse_verdict(strict.canonical({
                    "question_status": receipt["verdict"]["question_status"], "pages": receipt["verdict"]["page_verdicts"]}), ISSUED)
                    == receipt["verdict"], "legacy_verdict_changed")
                compare(receipt["verdict"])
                valid += 1
            else:
                require(receipt["state"] == "failed" and receipt["verdict"] is None and
                        receipt["selected_ids"] == [] and receipt["question_status"] is None, "legacy_failure_changed")
                failed += 1
            records.append({"kind": kind, "scope_version": version, "group_id": gid,
                "state": receipt["state"], "receipt_path": str(path), "receipt_sha256": receipt_sha,
                "claim_path": str(claim_path), "claim_sha256": claim_sha})
    require(valid == 118 and failed == 20 and len(records) == 138, "legacy_roster_changed")
    require(candidate.build_request is strict.build_request and candidate.validate_usage is strict.validate_usage,
            "wire_usage_changed")
    return {"schema": "public_visual_parser_equivalence_v1", "old_parser": strict.CONTRACT_VERSION,
        "new_parser": candidate.CONTRACT_VERSION, "parser_code_hashes": parser_hashes(),
        "legacy_caller_code_hashes": report["caller_code_sha256"], "terminal_observer_sha256": report_sha,
        "enumeration": enumerate_contract(), "valid_equivalent": valid, "failed_preserved": failed,
        "records": records, "historical_failed_results_credited": 0, "provider_calls": 0}


def validate(path: Path, sha: str) -> dict:
    proof, _ = read(path, sha)
    require(proof["schema"] == "public_visual_parser_equivalence_v1" and proof["valid_equivalent"] == 118 and
            proof["failed_preserved"] == 20 and len(proof["records"]) == 138 and
            proof["historical_failed_results_credited"] == proof["provider_calls"] == 0 and
            proof["parser_code_hashes"] == parser_hashes(), "parser_proof_changed")
    valid = failed = 0
    for record in proof["records"]:
        receipt, _ = read(Path(record["receipt_path"]), record["receipt_sha256"])
        claim, _ = read(Path(record["claim_path"]), record["claim_sha256"])
        require(receipt["state"] == record["state"] and receipt["group_id"] == record["group_id"] and
                receipt["attempt_claim_sha256"] == record["claim_sha256"] and
                receipt["request_sha256"] == claim["rest_sha256"], "historical_proof_binding_changed")
        if record["state"] == "completed":
            compare(receipt["verdict"])
            valid += 1
        else:
            require(record["state"] == "failed" and receipt["verdict"] is None and
                    receipt["selected_ids"] == [] and receipt["question_status"] is None, "legacy_failure_changed")
            failed += 1
    require(valid == 118 and failed == 20, "legacy_count_changed")
    return {"schema": proof["schema"], "proof_sha256": sha, "old_parser": proof["old_parser"],
        "new_parser": proof["new_parser"], "valid_equivalent": valid, "failed_preserved": failed,
        "historical_failed_results_credited": 0, "wire_unchanged": True, "candidate_local_repair": True,
        "mixed_historical_parser_lineage": True}


if __name__ == "__main__":
    require(sys.argv[1:] == ["--write-proof"], "proof_mode_required")
    proof = build()
    with PROOF_PATH.open("xb") as target:
        target.write(strict.canonical(proof))
    print(json.dumps({"proof_path": str(PROOF_PATH), "proof_sha256": digest(strict.canonical(proof)),
                      "valid_equivalent": proof["valid_equivalent"], "failed_preserved": proof["failed_preserved"],
                      "provider_calls": 0}, sort_keys=True))
