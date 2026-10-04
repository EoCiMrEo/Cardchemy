"""Dormant single-credential launcher for the public per-page verdict pilot.

The caller first validates the frozen public packet and SHA-bound approval in a
keyless child. Only after that reaches its expected missing-key stop does this
launcher read the one required key from the repository-root .env and start the
one-shot caller in a minimal environment. Without the exact approved receipt,
the launcher stops before reading that key or starting the network child.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from collections.abc import Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
CALLER = Path(__file__).with_name("run_fresh_public_per_page_verdict_v3.py")
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


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args.count("--execute") + args.count("--preflight-only") != 1:
        print("pilot_launcher_rejected: explicit_mode_required", file=sys.stderr)
        return 2
    try:
        # A new, exact provider envelope and operator approval must be pinned
        # before the real key can be read. No data-bearing child is launched.
        import run_fresh_public_per_page_verdict_v3 as caller
        if caller.LIVE_ENVELOPE_APPROVED is not True:
            raise LaunchError("separate_operator_approval_required")
        keyless_env = _child_env(os.environ)
        if not _keyless_preflight(args, keyless_env):
            raise LaunchError("keyless_approval_preflight_rejected")
        key = _read_key(REPO_ROOT / ".env")
        result = subprocess.run(
            [sys.executable, str(CALLER), *args],
            cwd=REPO_ROOT, env=_child_env(os.environ, key), check=False,
        )
        return result.returncode
    except (LaunchError, OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        code = str(exc) if isinstance(exc, LaunchError) else "pilot_launcher_failed"
        print(f"pilot_launcher_rejected: {code}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
