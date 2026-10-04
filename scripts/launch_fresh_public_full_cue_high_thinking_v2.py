"""Single-credential launcher for the approved one-use v2 transport pilot.

The caller first validates the frozen public packet and SHA-bound approval in a
keyless child. Only after that reaches its expected missing-key stop does this
launcher read the one required key from the repository-root .env. Execution
is detached from the invoking tool session with a durable one-use launch
claim. The exact public envelope and receipt remain mandatory.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from collections.abc import Mapping
from tempfile import gettempdir
import time


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))
CALLER = Path(__file__).with_name("run_fresh_public_full_cue_high_thinking_v2.py")
KEY_NAME = "RAG_SOURCE_JUDGE_API_KEY"
KEY_ASSIGNMENT = re.compile(
    rf"^\s*(?:export\s+)?{KEY_NAME}\s*=(.*)$", re.IGNORECASE
)
KEY_FORMAT = re.compile(r"[!-~]{1,512}\Z")
KNOWN_PDF_WARNING = re.compile(
    r"Ignoring wrong pointing object [0-9]+ [0-9]+ \(offset [0-9]+\)\Z"
)
PASS_THROUGH_ENV = ("SystemRoot", "WINDIR", "TEMP", "TMP", "TMPDIR")


class LaunchError(ValueError):
    """A content-free local launch rejection."""


def _key_value(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith(("'", '"')):
        quote = raw[0]
        end = raw.find(quote, 1)
        tail = raw[end + 1 :].strip() if end >= 0 else ""
        if end < 0 or (tail and not tail.startswith("#")):
            raise LaunchError("source_judge_key_unavailable")
        value = raw[1:end]
    else:
        value = re.split(r"\s+#", raw, maxsplit=1)[0].strip()
    if KEY_FORMAT.fullmatch(value) is None:
        raise LaunchError("source_judge_key_unavailable")
    return value


def _read_key(env_path: Path) -> str:
    if not env_path.is_file() or env_path.stat().st_size > 1_048_576:
        raise LaunchError("source_judge_key_unavailable")
    found: str | None = None
    # Scan one line at a time. Values for every other setting are ignored.
    with env_path.open("r", encoding="utf-8-sig") as source:
        for line in source:
            match = KEY_ASSIGNMENT.fullmatch(line.rstrip("\r\n"))
            if match is None:
                continue
            if found is not None:
                raise LaunchError("source_judge_key_unavailable")
            found = _key_value(match.group(1))
    if found is None:
        raise LaunchError("source_judge_key_unavailable")
    return found


def _child_env(source: Mapping[str, str], key: str | None = None) -> dict[str, str]:
    child = {
        name: value
        for name in PASS_THROUGH_ENV
        for original, value in source.items()
        if original.casefold() == name.casefold() and value
    }
    child["PYTHONPATH"] = str(REPO_ROOT / "backend")
    child["PYTHONDONTWRITEBYTECODE"] = "1"
    child["PYTHONNOUSERSITE"] = "1"
    if key is not None:
        child[KEY_NAME] = key
    return child


def _keyless_preflight(argv: list[str], env: dict[str, str]) -> bool:
    preflight_args = ["--preflight-only" if arg == "--execute" else arg
                      for arg in argv]
    result = subprocess.run(
        [sys.executable, str(CALLER), *preflight_args],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True,
        timeout=300, check=False,
    )
    if result.returncode != 2:
        return False
    try:
        lines = result.stderr.splitlines()
        if not lines or any(KNOWN_PDF_WARNING.fullmatch(line) is None
                            for line in lines[:-1]):
            return False
        status = json.loads(lines[-1])
    except (TypeError, ValueError):
        return False
    return status == {"status": "pilot_rejected",
                      "reason": "source_judge_key_unavailable"}


def _argument(argv: list[str], name: str) -> str:
    if argv.count(name) != 1:
        raise LaunchError("launcher_arguments_invalid")
    index = argv.index(name)
    if index + 1 >= len(argv) or argv[index + 1].startswith("--"):
        raise LaunchError("launcher_arguments_invalid")
    return argv[index + 1]


def _output_path(argv: list[str]) -> Path:
    output = Path(_argument(argv, "--output-dir"))
    temp_root = Path(gettempdir()).resolve()
    if (not output.is_absolute() or output.exists() or output.is_symlink() or
            not output.parent.is_dir() or output.parent.is_symlink() or
            not output.resolve().is_relative_to(temp_root)):
        raise LaunchError("os_temp_output_required")
    return output


def _write_new(path: Path, value: dict) -> None:
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True) + "\n").encode("ascii")
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _detached_flags() -> tuple[int, bool]:
    if os.name != "nt":
        return 0, True
    names = ("DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP",
             "CREATE_BREAKAWAY_FROM_JOB", "CREATE_NO_WINDOW")
    if any(not hasattr(subprocess, name) for name in names):
        raise LaunchError("detached_process_unavailable")
    return sum(getattr(subprocess, name) for name in names), False


def _detached_execute(argv: list[str], env: dict[str, str],
                      approval_sha: str) -> int:
    """Spawn once; the ledger and attempt journal prevent uncertain replay."""
    import run_fresh_public_full_cue_high_thinking_v2 as caller
    if (argv.count("--execute") != 1 or
            caller.LIVE_ENVELOPE_APPROVED is not True):
        raise LaunchError("separate_operator_approval_required")
    try:
        caller._model_endpoint()
    except caller.PilotError as exc:
        raise LaunchError("separate_operator_approval_required") from exc
    if re.fullmatch(r"[0-9a-f]{64}", approval_sha) is None:
        raise LaunchError("approval_hash_required")
    output = _output_path(argv)
    flags, new_session = _detached_flags()
    claim = output.with_name(output.name + ".launch-claim.json")
    process_receipt = output.with_name(output.name + ".launch-process.json")
    if claim.exists() or process_receipt.exists():
        raise LaunchError("launch_already_claimed")
    _write_new(claim, {
        "schema_version": "fresh_public_full_cue_high_thinking_v2_launch_claim",
        "authorization_id": caller.AUTHORIZATION_ID,
        "approval_receipt_sha256": approval_sha,
        "caller_sha256": caller.digest(CALLER.read_bytes()),
        "created_epoch_ms": int(time.time() * 1_000),
    })
    child = subprocess.Popen(
        [sys.executable, str(CALLER), *argv],
        cwd=REPO_ROOT, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True, creationflags=flags, start_new_session=new_session,
    )
    try:
        _write_new(process_receipt, {
            "schema_version": "fresh_public_full_cue_high_thinking_v2_process",
            "approval_receipt_sha256": approval_sha,
            "pid": child.pid,
            "spawned_epoch_ms": int(time.time() * 1_000),
        })
    except OSError:
        # The child may already have issued a physical request. Keep the claim
        # consumed, disclose the PID, and require OS/process/ledger inspection.
        print(json.dumps({"status": "detached_execution_uncertain",
                          "pid": child.pid}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({"status": "detached_one_use_started", "pid": child.pid,
                      "process_receipt": str(process_receipt)}, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args.count("--execute") + args.count("--preflight-only") != 1:
        print("pilot_launcher_rejected: explicit_mode_required", file=sys.stderr)
        return 2
    try:
        # A new, exact provider envelope and operator approval must be pinned
        # before the real key can be read. No data-bearing child is launched.
        import run_fresh_public_full_cue_high_thinking_v2 as caller
        if caller.LIVE_ENVELOPE_APPROVED is not True:
            raise LaunchError("separate_operator_approval_required")
        keyless_env = _child_env(os.environ)
        if not _keyless_preflight(args, keyless_env):
            raise LaunchError("keyless_approval_preflight_rejected")
        key = _read_key(REPO_ROOT / ".env")
        child_env = _child_env(os.environ, key)
        if "--execute" in args:
            return _detached_execute(args, child_env,
                                     _argument(args, "--approval-sha256"))
        result = subprocess.run([sys.executable, str(CALLER), *args],
                                cwd=REPO_ROOT, env=child_env, check=False)
        return result.returncode
    except (LaunchError, OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        code = str(exc) if isinstance(exc, LaunchError) else "pilot_launcher_failed"
        print(f"pilot_launcher_rejected: {code}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
