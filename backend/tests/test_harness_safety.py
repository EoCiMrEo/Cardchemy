"""Regression safety boundaries for disposable service/browser verification."""
from pathlib import Path
import runpy
import subprocess
import sys

import pytest


def test_image_probe_imports_without_backend_dependencies():
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    result = subprocess.run(
        [sys.executable, "-S", "-c",
         "import sys; sys.path.insert(0, sys.argv[1]); import check_images", str(scripts)],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_service_harness_does_not_inherit_operator_settings(monkeypatch):
    script = Path(__file__).resolve().parents[2] / "scripts/test_services.py"
    namespace = runpy.run_path(str(script))
    operator_keys = ("ENVIRONMENT", "DATABASE_URL", "SECRET_KEY", "AI_API_KEY",
                     "GEMINI_API_KEY", "SMTP_HOST", "SMTP_PASSWORD", "RUN_LIVE_AI_TESTS",
                     "POSTGRES_TEST_DATABASE_URL", "JOURNEY_INSTRUCTOR_PASSWORD")
    for key in operator_keys:
        monkeypatch.setenv(key, "operator-setting-must-not-leak")
    monkeypatch.setenv("PATH", "runtime-path")
    monkeypatch.setenv("CI", "true")
    environment = namespace["system_environment"]()
    assert environment["PATH"] == "runtime-path"
    assert environment["CI"] == "true"
    assert all(key not in environment for key in operator_keys)


def test_postgres_readiness_waits_for_authenticated_tcp_and_target_database(monkeypatch):
    import asyncpg
    script = Path(__file__).resolve().parents[2] / "scripts/test_services.py"
    namespace = runpy.run_path(str(script))
    attempts = []
    queries = []
    closed = []

    class Connection:
        async def fetchval(self, query):
            queries.append(query)
            return "regression_test"

        async def close(self, *, timeout):
            closed.append(timeout)

    async def connect(**options):
        attempts.append(options)
        if len(attempts) == 1:
            raise ConnectionResetError("temporary server stopped")
        if len(attempts) == 2:
            raise asyncpg.CannotConnectNowError("database system is starting up")
        return Connection()

    async def no_delay(_seconds):
        pass

    monkeypatch.setattr(asyncpg, "connect", connect)
    monkeypatch.setattr(namespace["asyncio"], "sleep", no_delay)
    namespace["wait_postgres_ready"](54321, "generated-test-secret", "regression_test")

    assert len(attempts) == 3
    assert all(options == {
        "host": "127.0.0.1", "port": 54321, "user": "qa",
        "password": "generated-test-secret", "database": "regression_test",
        "timeout": 2, "command_timeout": 2,
    } for options in attempts)
    assert queries == ["SELECT current_database()"]
    assert closed == [2]


def test_postgres_readiness_refuses_a_different_database(monkeypatch):
    import asyncpg
    script = Path(__file__).resolve().parents[2] / "scripts/test_services.py"
    namespace = runpy.run_path(str(script))
    closed = []

    class Connection:
        async def fetchval(self, _query):
            return "another_database"

        async def close(self, *, timeout):
            closed.append(timeout)

    async def connect(**_options):
        return Connection()

    monkeypatch.setattr(asyncpg, "connect", connect)
    with pytest.raises(RuntimeError, match="unexpected database"):
        namespace["wait_postgres_ready"](54321, "generated-test-secret", "regression_test")
    assert closed == [2]


async def test_private_journey_worker_refuses_an_ordinary_application_database(monkeypatch):
    script = Path(__file__).resolve().parent / "support/journey_runtime.py"
    namespace = runpy.run_path(str(script))
    monkeypatch.setenv("RUN_JOURNEY_TESTS", "0")
    with pytest.raises(RuntimeError, match="generated disposable journey database"):
        await namespace["require_disposable_database"]()
