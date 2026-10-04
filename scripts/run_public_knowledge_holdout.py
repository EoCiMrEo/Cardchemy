"""Preflight or rehearse the frozen public Knowledge holdout safely.

Default mode validates frozen artifacts and current code without Docker, a
database, an SDK client, or a provider call. `--mock` uses a one-off PostgreSQL
container and deterministic local vectors to check upload/index/PDF plumbing.
It never embeds heldout questions, runs the source selector, or scores quality.
There is deliberately no paid mode while the final candidate remains unfrozen.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
from uuid import uuid4

from test_services import (
    ROOT, cleanup_containers, docker, ensure_database_image, port,
    system_environment, wait_postgres_ready,
)
from test_journey import private_workspace

sys.path.insert(0, str(ROOT / "backend"))
from scripts import preflight_public_knowledge_disposable_run as admission  # noqa: E402


class Refusal(RuntimeError):
    """Fixed non-secret failure code."""


def _command(arguments: list[str], environment: dict[str, str], *, timeout: int) -> None:
    try:
        subprocess.run(
            arguments, cwd=ROOT / "backend", env=environment,
            capture_output=True, text=True, check=True, timeout=timeout,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise Refusal("disposable_setup_failed") from None


def _child(environment: dict[str, str], temp_dir: Path) -> dict:
    command = [
        sys.executable, str(ROOT / "backend/scripts/execute_public_knowledge_disposable.py"),
        "--mode", "mock", "--temp-dir", str(temp_dir),
    ]
    try:
        result = subprocess.run(
            command, cwd=ROOT / "backend", env=environment,
            capture_output=True, text=True, timeout=900,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise Refusal("disposable_mock_failed") from None
    if result.returncode:
        # The child may have seen generated tokens, database credentials and
        # PDF text in an exception. Never forward raw stdout/stderr.
        codes = re.findall(
            r"(?m)^Public Knowledge disposable execution refused: ([a-z_]+)$",
            result.stderr,
        )
        if len(codes) == 1:
            raise Refusal(f"disposable_mock_{codes[0]}")
        raise Refusal("disposable_mock_failed")
    try:
        rows = [json.loads(line) for line in result.stdout.splitlines()
                if line.startswith('{"status":"disposable_mock_plumbing_passed"')]
        report = rows[-1]
    except (IndexError, ValueError, TypeError):
        raise Refusal("disposable_mock_report_invalid") from None
    expected = {
        "status": "disposable_mock_plumbing_passed",
        "mode": "mock", "document_calls": 2, "query_calls": 12,
        "provider_retries": 0, "answer_calls": 0,
        "opened_pdf_document_count": 2, "selector_calls": 0,
        "holdout_questions_embedded": 0, "release_gate_passed": False,
    }
    if report != expected:
        raise Refusal("disposable_mock_report_invalid")
    return expected


def run_mock(temp_dir: Path) -> dict:
    """Own a unique no-volume database and verify exact cleanup on exit."""
    image, platform = ensure_database_image()
    suffix = uuid4().hex[:12]
    network = f"cardchemy-public-holdout-network-{suffix}"
    database = f"cardchemy-public-holdout-db-{suffix}"
    containers: list[str] = []
    networks: list[str] = []
    with tempfile.TemporaryDirectory(prefix="cardchemy-public-holdout-mock-") as path:
        workspace = Path(path)
        private_workspace(workspace)
        password = secrets.token_urlsafe(36)
        credential_file = workspace / "postgres.env"
        credential_file.write_text(
            f"POSTGRES_USER=qa\nPOSTGRES_DB=public_holdout_test\nPOSTGRES_PASSWORD={password}\n",
            encoding="utf-8",
        )
        credential_file.chmod(0o600)
        try:
            docker("network", "create", network)
            networks.append(network)
            containers.append(database)
            docker(
                "run", "--rm", "-d", "--name", database,
                "--platform", platform, "--network", network,
                "--env-file", str(credential_file),
                "-p", "127.0.0.1::5432", image,
            )
            database_port = port(database, 5432)
            wait_postgres_ready(database_port, password, "public_holdout_test")
            environment = system_environment() | {
                "ENVIRONMENT": "test", "PYTHONUTF8": "1",
                "PYTHONPATH": str(ROOT / "backend"),
                "DATABASE_URL": (
                    f"postgresql+asyncpg://qa:{password}@127.0.0.1:"
                    f"{database_port}/public_holdout_test"
                ),
                "SECRET_KEY": secrets.token_urlsafe(48),
                "GENERATION_SOURCE_ENCRYPTION_KEY": secrets.token_urlsafe(32),
                "KNOWLEDGE_PDF_ENCRYPTION_KEY": secrets.token_urlsafe(32),
                "FRONTEND_BASE_URL": "http://127.0.0.1",
                "CORS_ORIGINS": "http://127.0.0.1",
                "FLASHCARD_AI_PROVIDER_ENABLED": "false",
                "RAG_ENABLED": "true", "RAG_ASK_ENABLED": "false",
                "RAG_AI_PROVIDER_ENABLED": "false",
                "RAG_EMBEDDING_PROVIDER_ENABLED": "true",
                "RAG_EMBEDDING_API_KEY": "public-holdout-mock-no-network",
                "RAG_EMBEDDING_MODEL": "gemini-embedding-001",
                "RAG_EMBEDDING_PROVIDER_MAX_RETRIES": "0",
                "RAG_EMBEDDING_PROVIDER_TIMEOUT_SECONDS": "30",
                "RAG_EMBEDDING_BATCH_SIZE": "32",
                "RAG_EMBEDDING_MAX_INPUT_TOKENS": "2048",
                "RAG_EMBEDDING_INPUT_COST_PER_MILLION_USD": "0.20",
                "RAG_EMBEDDING_MAX_ESTIMATED_COST_USD": "0.002",
                "RAG_INDEX_MAX_ATTEMPTS": "1",
                "PDF_OCR_ENABLED": "false",
                "CARDCH_PUBLIC_HOLDOUT_MODE": "mock",
                "CARDCH_PUBLIC_HOLDOUT_RUN_ID": str(uuid4()),
            }
            for args in (
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                [sys.executable, "-m", "alembic", "current", "--check-heads"],
                [sys.executable, "-m", "alembic", "check"],
            ):
                _command(args, environment, timeout=180)
            return _child(environment, temp_dir)
        finally:
            try:
                cleanup_containers(containers)
            finally:
                for name in reversed(networks):
                    subprocess.run(["docker", "network", "rm", name], capture_output=True)
                if networks:
                    remaining = set(docker("network", "ls", "--format", "{{.Name}}").splitlines())
                    if remaining.intersection(networks):
                        raise Refusal("disposable_cleanup_failed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--temp-dir", type=Path, required=True)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()
    try:
        report = admission.preflight(args.temp_dir)
        if not args.mock:
            print(json.dumps(report, separators=(",", ":")))
            return 0
        mock = run_mock(args.temp_dir)
    except (Refusal, admission.Refusal, admission.source_preflight.Refusal) as exc:
        # These exception classes carry only fixed, non-content guard codes.
        # Preserve the code so a failed rehearsal can be repaired without
        # exposing subprocess output, PDF text, credentials, or URLs.
        raise SystemExit(f"Public Knowledge holdout run refused: {exc}") from None
    except (OSError, RuntimeError, subprocess.CalledProcessError):
        raise SystemExit("Public Knowledge holdout run failed; private diagnostics withheld.") from None
    print(json.dumps(mock, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
