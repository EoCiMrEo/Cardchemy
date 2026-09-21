"""The standalone configuration preflight never exposes removed values."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1]
PREFLIGHT = runpy.run_path(str(SCRIPTS / "check_config_migration.py"))


def test_preflight_reports_only_nonempty_removed_names(tmp_path):
    env_file = tmp_path / ".env"
    sentinel = "PRIVATE_VALUE_MUST_NOT_LEAK"
    env_file.write_text(
        "# AI_MODEL=commented\n"
        "AI_PROVIDER=   # blank\n"
        "AI_API_KEY=\"\"\n"
        "GEMINI_API_KEY=''\n"
        f"export AI_MODEL='{sentinel}'\n"
        "UNRELATED_SETTING=allowed\n",
        encoding="utf-8",
    )
    assert PREFLIGHT["removed_names"](env_file, environment={}) == ("AI_MODEL",)
    with pytest.raises(PREFLIGHT["ConfigMigrationError"]) as error:
        PREFLIGHT["ensure_no_legacy_configuration"](env_file, environment={})
    assert "AI_MODEL" in str(error.value)
    assert sentinel not in str(error.value)


def test_process_values_override_empty_file_without_exposing_values(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("AI_API_KEY=\nFLASHCARD_AI_MODEL=fixture\n", encoding="utf-8")
    assert PREFLIGHT["removed_names"](
        env_file,
        environment={"ai_api_key": "PRIVATE_PROCESS_VALUE", "GEMINI_API_KEY": " "},
    ) == ("AI_API_KEY",)
    assert PREFLIGHT["removed_names"](env_file, environment={}) == ()


def test_compose_guard_is_single_pass_name_only_and_complete():
    compose = (SCRIPTS.parent / "docker-compose.yml").read_text(encoding="utf-8")
    guard = next(
        line for line in compose.splitlines()
        if line.startswith("x-removed-ai-name-guard:")
    )
    assert "CARDCH_LEGACY_AI_CONFIGURATION_ERROR" not in guard
    for name in PREFLIGHT["REMOVED_AI_NAMES"]:
        assert "${" + name + ":+-" + name + "}" in guard
    assert "scale: *removed-ai-name-guard" in compose


def test_bootstrap_preserves_existing_file_and_reports_removed_name(tmp_path, monkeypatch):
    bootstrap = runpy.run_path(str(SCRIPTS / "bootstrap_env.py"))
    env_file = tmp_path / ".env"
    env_file.write_text("AI_MODEL=PRIVATE_EXISTING_VALUE\n", encoding="utf-8")
    before = env_file.read_bytes()
    monkeypatch.setitem(bootstrap["main"].__globals__, "OUTPUT", env_file)
    with pytest.raises(RuntimeError) as error:
        bootstrap["main"]()
    assert "AI_MODEL" in str(error.value)
    assert "PRIVATE_EXISTING_VALUE" not in str(error.value)
    assert env_file.read_bytes() == before


def test_rehearsal_compose_checks_injected_fixture_before_launch(tmp_path, monkeypatch):
    rehearsal = runpy.run_path(str(SCRIPTS / "test_production_rehearsal.py"))
    monkeypatch.setitem(rehearsal["Stack"].compose.__globals__, "run",
                        lambda *_args, **_kwargs: pytest.fail("Compose was launched"))
    stack = rehearsal["Stack"](
        tmp_path, tmp_path, "cardchemy-rehearsal-0123456789abcdef-source", 8443,
        "backend:fixture", "frontend:fixture", {},
    )
    with stack.env_file.open("a", encoding="utf-8") as output:
        output.write("\nAI_MODEL=PRIVATE_REHEARSAL_VALUE\n")
    with pytest.raises(RuntimeError) as error:
        stack.compose("config")
    assert "AI_MODEL" in str(error.value)
    assert "PRIVATE_REHEARSAL_VALUE" not in str(error.value)
