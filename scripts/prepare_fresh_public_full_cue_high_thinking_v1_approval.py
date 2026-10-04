"""Prepare a SHA-bound receipt only after a new high-thinking live approval.

Calibration and heldout have distinct one-use receipts and attempt ledgers.
This preparer cannot call Gemini or read a credential. Heldout admission still
requires the completed, passing calibration score and its original receipt.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import run_fresh_public_full_cue_high_thinking_v1 as pilot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-dir", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--overlap-diagnostic", type=Path, required=True)
    parser.add_argument("--split", choices=pilot.baseline.SPLITS, required=True)
    parser.add_argument("--calibration-results", type=Path)
    parser.add_argument("--calibration-approval-receipt", type=Path)
    parser.add_argument("--calibration-approval-sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        pilot.require(pilot.LIVE_ENVELOPE_APPROVED is True,
                      "separate_operator_approval_required")
        admitted = pilot.admit_public_packet(
            args.frozen_dir, args.source_manifest, args.overlap_diagnostic,
            args.split, args.calibration_results,
            calibration_approval_path=args.calibration_approval_receipt,
            calibration_approval_sha=args.calibration_approval_sha256,
        )
        receipt = {
            "schema_version": pilot.APPROVAL_SCHEMA,
            "authorization_id": pilot.AUTHORIZATION_ID,
            "operator_approved": True,
            "public_only": True,
            "previous_attempt_cost_unknown": True,
            "corpus_id": pilot.freezer.CORPUS_ID,
            "split": admitted["split"],
            "source_manifest_sha256": admitted["source_manifest_sha256"],
            "overlap_diagnostic_sha256": admitted["overlap_diagnostic_sha256"],
            "freeze_sha256": admitted["freeze_sha256"],
            "packet_sha256": admitted["packet_sha256"],
            "labels_sha256": admitted["labels_sha256"],
            "body_manifest_sha256": admitted["body_manifest_sha256"],
            "source_sha256": admitted["source_sha256"],
            "calibration_score_sha256": admitted["calibration_score_sha256"],
            "endpoint": pilot._model_endpoint(),
            "model": pilot.MODEL,
            "thinking": pilot.THINKING,
            "automatic_retries": 0,
            "max_calls": len(admitted["requests"]),
            "max_input_tokens_per_call": pilot.MAX_INPUT_PER_CALL,
            "max_output_tokens_per_call": pilot.MAX_OUTPUT_PER_CALL,
            "max_new_cost_microusd": pilot.SPLIT_COST_CAPS_MICROUSD[args.split],
            "max_call_seconds": pilot.MAX_CALL_SECONDS,
            "max_total_seconds": pilot.MAX_TOTAL_SECONDS,
            "min_start_interval_seconds": pilot.MIN_START_INTERVAL_SECONDS,
            "input_price_usd_per_million": "0.30",
            "output_price_usd_per_million": "2.50",
        }
        if (not args.output.parent.is_dir() or args.output.parent.is_symlink()
                or args.output.exists() or args.output.is_symlink()):
            raise pilot.PilotError("approval_output_invalid")
        raw = pilot.canonical_bytes(receipt)
        approval_sha = pilot.digest(raw)
        pilot._write_exclusive(args.output, receipt)
        pilot.validate_approval(args.output, approval_sha, admitted)
    except (pilot.PilotError, pilot.freezer.FreezeError,
            pilot.baseline.ScoreError, OSError, ValueError,
            TypeError, KeyError) as exc:
        code = str(exc) if isinstance(exc, pilot.PilotError) else "approval_preparation_rejected"
        print(json.dumps({"status": "approval_preparation_rejected", "reason": code},
                         sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({"status": "approval_receipt_prepared",
                      "split": args.split, "sha256": approval_sha}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
