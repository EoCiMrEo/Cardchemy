"""Inert container entry for an externally approved, source-ID-only private12 trial."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time

REPO = Path(__file__).resolve().parents[2]
if Path("/app/app/__init__.py").is_file():
    sys.path.insert(0, "/app")
    import app  # noqa: F401 - prefer the complete immutable image package
sys.path.insert(0, str(REPO / "scripts"))
import launch_private_visual_trial_v7 as host

LIVE_AUTHORIZED = False


def keyless_settings(output, bound):
    """Validate the real namespace/profile before any credential lookup."""
    host.require(output == Path("/tmp/output") and not (host.REPO / ".env").exists()
        and not Path("/app/.env").exists() and not any(name.endswith("API_KEY") for name in os.environ),
        "runtime_not_keyless")
    host.require(Path("/sys/fs/cgroup/memory.max").read_text().strip() == "2147483648"
        and Path("/sys/fs/cgroup/cpu.max").read_text().strip() == "400000 100000", "resource_fence_required")
    from app.config import Settings
    settings = Settings(_env_file=None)
    host.modules()[-1]._environment(settings, bound)
    return settings


async def execute(directory, output, external_sha, *, stdin):
    # A supplied external digest is an explicit host authorization witness.
    # The copied approval, exact code/image bindings and durable host claim
    # must all pass before settings or credential lookup is possible.
    began = time.monotonic()
    host.require(type(external_sha) is str and len(external_sha) == 64, "private_execution_not_authorized")
    manifest, prepared, bound = host.validate_stage(directory, image=True)
    host.path_check(output, directory=True)
    approval_raw = host.bounded(directory / "approval.json", 64 * 1024)
    inner_raw, inner_sha = host.validate_approval(approval_raw, external_sha, manifest, prepared, bound)
    claim = host.parse(host.bounded(output / "host-claim.json", 4096), 4096)
    host.require(claim["schema"] == host.SCHEMA + "_claim" and claim["approval_sha256"] == external_sha
        and claim["stage_sha256"] == host.digest(host.canonical(manifest)) and claim["one_use"] is True,
        "host_claim_required")
    # Claim entry before reading credentials. Existing claim.json in the inner
    # TrialLedger additionally prevents replay on the next controller invocation.
    host.exclusive(output / "entry-claim.json", host.canonical({"approval_sha256": external_sha, "one_use": True}))
    settings = keyless_settings(output, bound)
    _, _, _, executor = host.modules()
    host.require(time.monotonic() - began <= executor.preparation.MAX_STARTUP_SECONDS, "startup_deadline")
    message = host.read_credential_stdin(stdin)
    api_key = host.parse(message, host.MAX_STDIN_BYTES)["api_key"]
    message = b""
    host.validate_approval(approval_raw, external_sha, manifest, prepared, bound)
    host.require(time.monotonic() - began <= executor.preparation.MAX_STARTUP_SECONDS, "startup_deadline")
    executor.LIVE_AUTHORIZED = True
    try:
        return await executor.execute_private_trial_v7(prepared, bound, settings=settings, api_key=api_key,
            approval_bytes=inner_raw, approval_sha256=inner_sha, ledger=executor.TrialLedger(output))
    finally:
        executor.LIVE_AUTHORIZED = False
        api_key = ""


def main(argv=None):
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("directory", type=Path, nargs="?")
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("approval_sha256", nargs="?")
    args = parser.parse_args(argv)
    if not args.execute:
        result = {"status": "fresh_external_authority_required", "live_authorized": False, "provider_calls": 0}
        code = 2
    else:
        try:
            result = asyncio.run(execute(args.directory, args.output, args.approval_sha256, stdin=sys.stdin.buffer))
            code = 0 if result.get("status") == "completed" else 2
        except Exception:
            result = {"status": "private_trial_entry_refused", "provider_usage_unknown": True, "release_gate_passed": False}
            code = 2
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
