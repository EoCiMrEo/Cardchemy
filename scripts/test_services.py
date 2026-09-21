"""Run PostgreSQL/Mailpit regressions on throwaway, loopback-only services.

Use the backend development environment's Python. No operator .env is read.
Containers have unique names, generated credentials, and no persistent volumes.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
DATABASE_ARTIFACT = json.loads((ROOT / "runtime-artifacts.json").read_text(encoding="utf-8"))["database"]
DATABASE_IMAGE = DATABASE_ARTIFACT["image"]
DATABASE_PLATFORM = DATABASE_ARTIFACT["supported_platform"]


def ensure_database_image() -> tuple[str, str]:
    """Resolve the verified recipe image only when a service is requested.

    Load by path so runpy/importlib contract callers do not need the scripts
    directory on sys.path. Importing this harness never builds an image.
    """
    path = ROOT / "scripts" / "runtime_database.py"
    spec = importlib.util.spec_from_file_location("cardchemy_runtime_database", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the reviewed database recipe verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ensure_database_image(root=ROOT)


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


def cleanup_containers(names: list[str]) -> None:
    """Require a successful daemon inventory and exact owned-name absence."""
    for name in reversed(names):
        # A failed start may leave nothing to remove. An rm error establishes
        # neither presence nor absence; the successful inventory below does.
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    remaining = set(docker("ps", "-a", "--format", "{{.Names}}").splitlines())
    if remaining.intersection(names):
        raise RuntimeError("An owned disposable verification container could not be removed")


def run_service_tests(command: list[str], *, cwd: Path, environment: dict[str, str]) -> int:
    """Emit counts/static test identities without credential-bearing tracebacks."""
    result = subprocess.run(command, cwd=cwd, env=environment,
                            capture_output=True, text=True)
    output = result.stdout + "\n" + result.stderr
    counts = re.findall(
        r"^(?:\d+ (?:passed|failed|skipped|deselected|xfailed|xpassed|errors?|warnings?)(?:, )?)+ in \d+(?:\.\d+)?s(?: \(\d+:\d{2}:\d{2}\))?$",
        output, flags=re.MULTILINE,
    )
    if counts:
        print(counts[-1])
    else:
        print(f"Service pytest completed with exit code {result.returncode}.")
    if result.returncode:
        # Parameter IDs and exception summaries can themselves carry secrets.
        # Report only static source-file/function identities, never either.
        failures = re.findall(
            r"^(?:FAILED|ERROR) (tests/[A-Za-z0-9_/]+\.py::[A-Za-z0-9_]+)(?:\[|\s|$)",
            output, flags=re.MULTILINE,
        )
        for identity in sorted(set(failures)):
            print(f"Failed service test: {identity}")
        # Short tracebacks end with repository-relative test locations. Expose
        # only those static paths/line numbers, never captured exception text.
        locations = re.findall(
            r"^(tests[\\/][A-Za-z0-9_.\\/-]+\.py:\d+)(?::|$)",
            output,
            flags=re.MULTILINE,
        )
        for location in list(dict.fromkeys(locations))[:20]:
            print(f"Safe failure location: {location}")
        failure_types = re.findall(
            r"^(?:E\s+)?([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception))(?::|\()",
            output,
            flags=re.MULTILINE,
        )
        for failure_type in list(dict.fromkeys(failure_types))[:20]:
            print(f"Safe failure type: {failure_type}")
        print("Detailed service-test diagnostics withheld to protect generated credentials and message content.")
    return result.returncode


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
    database_image, database_platform = ensure_database_image()
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
                   "--platform", database_platform, "--env-file", str(environment_file),
                   "-p", "127.0.0.1::5432", database_image)
            database_port = port(database, 5432)
            wait_postgres_ready(database_port, password, "regression_test")
            database_url = f"postgresql+asyncpg://qa:{password}@127.0.0.1:{database_port}/regression_test"
            environment = system_environment() | {
                "ENVIRONMENT": "test",
                "DATABASE_URL": database_url,
                "POSTGRES_TEST_DATABASE_URL": database_url,
                "POSTGRES_TEST_CONTAINER_NAME": database,
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
            returncode = run_service_tests(
                [sys.executable, "-m", "pytest", "-q", "--tb=short", "-m", arguments.suite + " and not smtp_tls"],
                cwd=ROOT / "backend", environment=environment,
            )
            if returncode:
                return returncode
            # Rehearse the entire migration chain only on this generated DB.
            if arguments.suite == "postgres":
                for target in ("base", "head"):
                    operation = "downgrade" if target == "base" else "upgrade"
                    subprocess.run([sys.executable, "-m", "alembic", operation, target],
                                   cwd=ROOT / "backend", env=environment, check=True)
                for command in (
                    [sys.executable, "-m", "alembic", "current", "--check-heads"],
                    [sys.executable, "-m", "alembic", "check"],
                ):
                    subprocess.run(command, cwd=ROOT / "backend", env=environment, check=True)
            return 0
        finally:
            cleanup_containers(names)
            print("Disposable test services and generated credential file cleaned up.")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError):
        raise SystemExit("Service regression command failed; no credential values were printed.")
