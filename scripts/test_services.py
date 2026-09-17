"""Run PostgreSQL/Mailpit regressions on throwaway, loopback-only services.

Use the backend development environment's Python. No operator .env is read.
Containers have unique names, generated credentials, and no persistent volumes.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def system_environment() -> dict[str, str]:
    """Keep OS/runtime paths while excluding operator application settings."""
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP",
               "HOME", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "PROGRAMDATA",
               "PROGRAMFILES", "PROGRAMFILES(X86)", "CI", "PLAYWRIGHT_BROWSERS_PATH"}
    return {key: value for key, value in os.environ.items() if key.upper() in allowed}


def docker(*arguments: str) -> str:
    result = subprocess.run(["docker", *arguments], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Docker command failed; check Docker availability and permissions")
    return result.stdout.strip()


def wait_ready(name: str, command: list[str]) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if subprocess.run(["docker", "exec", name, *command], capture_output=True).returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError("Disposable test service did not become ready")


def wait_postgres_ready(tcp_port: int, password: str, database_name: str) -> None:
    """Wait for the final server via authenticated host TCP, not its init socket."""
    import asyncpg

    async def probe() -> None:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                connection = await asyncpg.connect(
                    host="127.0.0.1", port=tcp_port, user="qa", password=password,
                    database=database_name, timeout=2, command_timeout=2,
                )
                try:
                    actual_database = await connection.fetchval("SELECT current_database()")
                finally:
                    await connection.close(timeout=2)
                if actual_database != database_name:
                    raise RuntimeError("Disposable PostgreSQL readiness reached an unexpected database")
                return
            except (OSError, TimeoutError, asyncpg.CannotConnectNowError,
                    asyncpg.PostgresConnectionError, asyncpg.InterfaceError):
                await asyncio.sleep(0.5)
        raise RuntimeError("Disposable PostgreSQL did not become ready")

    asyncio.run(probe())


def port(name: str, internal_port: int) -> int:
    address = docker("port", name, f"{internal_port}/tcp")
    return int(address.rsplit(":", 1)[1])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=["postgres", "mailpit"])
    arguments = parser.parse_args()
    suffix = uuid4().hex[:12]
    names: list[str] = []
    with tempfile.TemporaryDirectory(prefix="flashcard-regression-") as directory:
        environment_file = Path(directory) / "database.env"
        password = secrets.token_urlsafe(36)
        environment_file.write_text(
            f"POSTGRES_USER=qa\nPOSTGRES_DB=regression_test\nPOSTGRES_PASSWORD={password}\n",
            encoding="utf-8",
        )
        environment_file.chmod(0o600)
        try:
            database = f"flashcard-regression-db-{suffix}"
            names.append(database)
            docker("run", "--rm", "-d", "--name", database,
                   "--env-file", str(environment_file), "-p", "127.0.0.1::5432", "postgres:16")
            database_port = port(database, 5432)
            wait_postgres_ready(database_port, password, "regression_test")
            database_url = f"postgresql+asyncpg://qa:{password}@127.0.0.1:{database_port}/regression_test"
            environment = system_environment() | {
                "ENVIRONMENT": "test",
                "DATABASE_URL": database_url,
                "POSTGRES_TEST_DATABASE_URL": database_url,
                "SECRET_KEY": "test-only-secret-with-adequate-entropy-1234567890",
                "GENERATION_SOURCE_ENCRYPTION_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "PYTHONUTF8": "1",
            }
            import sys
            for command in (
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                [sys.executable, "-m", "alembic", "current", "--check-heads"],
                [sys.executable, "-m", "alembic", "check"],
            ):
                subprocess.run(command, cwd=ROOT / "backend", env=environment, check=True)
            if arguments.suite == "mailpit":
                mailpit = f"flashcard-regression-mailpit-{suffix}"
                names.append(mailpit)
                docker("run", "--rm", "-d", "--name", mailpit,
                       "-p", "127.0.0.1::8025", "-p", "127.0.0.1::1025",
                       "-e", "MP_ENABLE_CHAOS=true", "-e", "MP_DISABLE_VERSION_CHECK=true",
                       "axllent/mailpit:v1.31.1")
                wait_ready(mailpit, ["/mailpit", "readyz"])
                environment |= {
                    "MAILPIT_API_URL": f"http://127.0.0.1:{port(mailpit, 8025)}",
                    "MAILPIT_SMTP_HOST": "127.0.0.1",
                    "MAILPIT_SMTP_PORT": str(port(mailpit, 1025)),
                }
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-m", arguments.suite],
                cwd=ROOT / "backend", env=environment,
            )
            if result.returncode:
                return result.returncode
            # Rehearse the entire migration chain only on this generated DB.
            if arguments.suite == "postgres":
                for target in ("base", "head"):
                    operation = "downgrade" if target == "base" else "upgrade"
                    subprocess.run([sys.executable, "-m", "alembic", operation, target],
                                   cwd=ROOT / "backend", env=environment, check=True)
            return 0
        finally:
            for name in reversed(names):
                subprocess.run(["docker", "rm", "-f", name], capture_output=True)
            print("Disposable test services and generated credential file cleaned up.")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError):
        raise SystemExit("Service regression command failed; no credential values were printed.")
