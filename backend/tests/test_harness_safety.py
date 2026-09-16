"""Regression safety boundaries for disposable service/browser verification."""
from pathlib import Path
import runpy

import pytest


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


async def test_private_journey_worker_refuses_an_ordinary_application_database(monkeypatch):
    script = Path(__file__).resolve().parent / "support/journey_runtime.py"
    namespace = runpy.run_path(str(script))
    monkeypatch.setenv("RUN_JOURNEY_TESTS", "0")
    with pytest.raises(RuntimeError, match="generated disposable journey database"):
        await namespace["require_disposable_database"]()
