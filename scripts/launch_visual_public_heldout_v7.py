"""Foreground resource supervisor for the separate one-use approved 23-call trial."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from types import FunctionType

import launch_visual_public_heldout_v3 as audited
import run_visual_public_heldout_v7 as caller

visual = audited.visual
REPO = caller.REPO
CALLER = Path(__file__).with_name("run_visual_public_heldout_v7.py")
AUTHORIZATION_ID = caller.AUTHORIZATION_ID
MAX_SECONDS = caller.MAX_SECONDS
child_env = audited.child_env
write_new = audited.write_new
check_arguments = audited.check_arguments


def ledger_dir() -> Path:
    return caller.ledger_dir()


def preflight(approval: Path, sha: str) -> bool:
    # Rebind reviewed pure utilities without mutating the consumed v3 module.
    namespace = dict(audited.preflight.__globals__, CALLER=CALLER, child_env=child_env, REPO=REPO)
    return FunctionType(audited.preflight.__code__, namespace)(approval, sha)


def supervise(approval: Path, sha: str, output: Path) -> None:
    visual.require(caller.LIVE_AUTHORIZED, "fresh_provider_authorization_required")
    namespace = dict(audited.supervise.__globals__, caller=caller, CALLER=CALLER, REPO=REPO,
                     MAX_SECONDS=MAX_SECONDS, child_env=child_env, write_new=write_new)
    FunctionType(audited.supervise.__code__, namespace)(approval, sha, output)
    complete, _ = caller.read_existing(output.with_name(output.name + ".supervisor-complete.json"))
    visual.require(complete == {"approval_sha256": sha, "exit_code": 0, "resume_permitted": False},
                   "resource_worker_failed")
    visual.require((output / "result.json").is_file() and not (output / "result.json").is_symlink(),
                   "worker_terminal_result_missing")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval-file", type=Path, required=True)
    parser.add_argument("--approval-sha", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        visual.require(caller.LIVE_AUTHORIZED, "fresh_provider_authorization_required")
        check_arguments(args.approval_file, args.approval_sha, args.output_dir)
        visual.require(preflight(args.approval_file, args.approval_sha), "keyless_preflight_failed")
        write_new(ledger_dir() / f"{AUTHORIZATION_ID}.launch-claim.json", {
            "authorization_id": AUTHORIZATION_ID, "approval_file": str(args.approval_file),
            "approval_sha256": args.approval_sha, "output_dir": str(args.output_dir),
            "launcher_sha256": visual.digest(Path(__file__).read_bytes()),
            "supervisor_pid": os.getpid(), "created_epoch_ms": int(time.time() * 1000)})
        supervise(args.approval_file, args.approval_sha, args.output_dir)
        return 0
    except Exception as error:
        code = str(error) if isinstance(error, visual.PreparationError) else "launcher_failed"
        try:
            write_new(args.output_dir.with_name(args.output_dir.name + ".launcher-failure.json"),
                      {"status": "stopped", "failure_code": code, "resume_permitted": False})
        except OSError:
            pass
        print(json.dumps({"status": "launcher_rejected", "failure_code": code}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
