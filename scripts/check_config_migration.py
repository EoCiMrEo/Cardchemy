"""Reject removed AI configuration keys before a Compose launch or bootstrap.

This standalone preflight needs only the standard library. It inspects key names
and whether their values are nonempty; it never returns or prints values.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import os
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
REMOVED_AI_NAMES = frozenset({
    "AI_PROVIDER_ENABLED", "AI_PROVIDER", "AI_MODEL", "AI_API_KEY", "AI_BASE_URL",
    "AI_ALLOW_UNSTABLE_MODEL", "AI_PROVIDER_MAX_RETRIES", "AI_RETRY_BASE_SECONDS",
    "AI_RETRY_MAX_SECONDS", "AI_MAX_OUTPUT_TOKENS", "AI_TEMPERATURE",
    "AI_CONTEXT_WINDOW_TOKENS", "AI_PROVIDER_TIMEOUT_SECONDS", "AI_CONCURRENCY",
    "AI_REQUESTS_PER_MINUTE", "AI_INPUT_TOKENS_PER_MINUTE",
    "AI_RATE_LIMIT_SAFETY_PERCENT", "AI_REQUEST_INPUT_TARGET_TOKENS",
    "AI_CARDS_PER_REQUEST", "AI_CHUNK_INPUT_TOKENS", "AI_CHUNK_OVERLAP_TOKENS",
    "AI_SUMMARY_OUTPUT_TOKENS", "AI_MAX_JOB_INPUT_TOKENS", "AI_MAX_JOB_OUTPUT_TOKENS",
    "AI_REFILL_ROUNDS", "AI_DUPLICATE_SIMILARITY_THRESHOLD",
    "AI_INPUT_COST_PER_MILLION_USD", "AI_OUTPUT_COST_PER_MILLION_USD",
    "AI_MAX_ESTIMATED_COST_USD", "GEMINI_API_KEY",
})
RETIRED_ENDPOINT_NAMES = frozenset({
    "FLASHCARD_AI_BASE_URL", "RAG_AI_BASE_URL", "RAG_EMBEDDING_BASE_URL",
})
RETIRED_TASK_MODE_NAMES = frozenset({
    "RAG_EMBEDDING_DOCUMENT_TASK_MODE", "RAG_EMBEDDING_QUERY_TASK_MODE",
})
GEMINI_ONLY_PROVIDER_NAMES = frozenset({
    "FLASHCARD_AI_PROVIDER", "RAG_AI_PROVIDER", "RAG_EMBEDDING_PROVIDER",
})
_ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")


class ConfigMigrationError(RuntimeError):
    """A fixed, value-free migration diagnostic."""


def _env_assignment_value(raw: str) -> str:
    value = raw.strip()
    if not value or value.startswith("#"):
        return ""
    if value[0] in {"'", '"'}:
        closing = value.find(value[0], 1)
        if closing >= 0:
            return value[1:closing].strip()
    return re.split(r"\s+#", value, maxsplit=1)[0].strip()


def _nonempty_env_value(raw: str) -> bool:
    return bool(_env_assignment_value(raw))


def _retired(name: str, value: str) -> bool:
    return (
        (name in REMOVED_AI_NAMES and bool(value))
        or (name in RETIRED_ENDPOINT_NAMES and bool(value))
        or (name in RETIRED_TASK_MODE_NAMES and bool(value))
        or (name in GEMINI_ONLY_PROVIDER_NAMES and bool(value) and value.casefold() != "gemini")
    )


def removed_names(
    env_file: Path | None = ROOT / ".env",
    *,
    environment: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Return only retired key names or legacy provider selections, never values."""

    source = os.environ if environment is None else environment
    found = {
        key.upper() for key, value in source.items()
        if _retired(key.upper(), value.strip())
    }
    if env_file is not None:
        try:
            if env_file.is_file():
                # UTF-8 BOM is tolerated, as by common dotenv readers. The
                # content stays in memory only and is never logged.
                for line in env_file.read_text(encoding="utf-8-sig").splitlines():
                    match = _ASSIGNMENT.match(line)
                    if match:
                        name = match.group(1).upper()
                        if _retired(name, _env_assignment_value(match.group(2))):
                            found.add(name)
        except (OSError, UnicodeError) as exc:
            raise ConfigMigrationError("Could not inspect the root configuration file.") from exc
    return tuple(sorted(found))


def ensure_no_legacy_configuration(
    env_file: Path | None = ROOT / ".env",
    *,
    environment: Mapping[str, str] | None = None,
) -> None:
    names = removed_names(env_file, environment=environment)
    if names:
        raise ConfigMigrationError(
            "Removed AI configuration keys: " + ", ".join(names)
            + ". Migrate AI_* to FLASHCARD_AI_*, use only verified Gemini "
            "providers, and remove custom AI BASE_URL values before starting services."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env",
                        help="Configuration file to inspect (default: root .env)")
    arguments = parser.parse_args()
    try:
        ensure_no_legacy_configuration(arguments.env_file)
    except ConfigMigrationError as exc:
        parser.exit(1, f"{exc}\n")
    print("AI configuration migration preflight passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
