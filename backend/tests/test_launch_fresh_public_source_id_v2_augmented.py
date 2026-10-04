"""Offline credential-isolation checks for the augmented public pilot."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest


_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "scripts"))
import launch_fresh_public_source_id_v2_augmented as launcher  # noqa: E402
import run_fresh_public_source_id_v2_augmented as caller  # noqa: E402


def test_caller_reads_only_process_injected_key(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.config as config

    monkeypatch.setattr(config, "Settings", lambda **_: pytest.fail("settings_loaded"))
    monkeypatch.setenv("RAG_SOURCE_JUDGE_API_KEY", "synthetic-judge-key")
    assert caller._source_judge_key() == "synthetic-judge-key"
    monkeypatch.delenv("RAG_SOURCE_JUDGE_API_KEY")
    with pytest.raises(caller.PilotError, match="^source_judge_key_unavailable$"):
        caller._source_judge_key()
    monkeypatch.setenv("RAG_SOURCE_JUDGE_API_KEY", "invalid key with spaces")
    with pytest.raises(caller.PilotError, match="^source_judge_key_unavailable$"):
        caller._source_judge_key()


def test_launcher_reads_only_targeted_root_setting(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "POSTGRES_PASSWORD=unrelated-decoy\n"
        "FLASHCARD_AI_API_KEY=another-decoy\n"
        "RAG_SOURCE_JUDGE_API_KEY='synthetic-judge-key' # local comment\n",
        encoding="utf-8",
    )
    assert launcher._read_key(env_file) == "synthetic-judge-key"
    env_file.write_text(
        "RAG_SOURCE_JUDGE_API_KEY=first-key\n"
        "RAG_SOURCE_JUDGE_API_KEY=second-key\n",
        encoding="utf-8",
    )
    with pytest.raises(launcher.LaunchError, match="^source_judge_key_unavailable$"):
        launcher._read_key(env_file)


def test_launcher_preflights_without_key_then_spawns_minimal_keyed_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".env").write_text(
        "RAG_SOURCE_JUDGE_API_KEY=synthetic-judge-key\n"
        "DATABASE_URL=unrelated-decoy\n", encoding="utf-8",
    )
    monkeypatch.setattr(launcher, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("FLASHCARD_AI_API_KEY", "ambient-decoy")
    monkeypatch.setenv("RAG_SOURCE_JUDGE_API_KEY", "ambient-judge-decoy")
    calls: list[tuple[list[str], dict]] = []

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append((command, kwargs))
        if len(calls) == 1:
            return SimpleNamespace(
                returncode=2,
                stderr=json.dumps({"status": "pilot_rejected",
                                   "reason": "source_judge_key_unavailable"}),
            )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(launcher.subprocess, "run", fake_run)
    assert launcher.main(["--execute", "--approval-sha256", "0" * 64]) == 0
    assert len(calls) == 2
    assert "--preflight-only" in calls[0][0]
    assert "--execute" in calls[1][0]
    first_env = calls[0][1]["env"]
    second_env = calls[1][1]["env"]
    assert launcher.KEY_NAME not in first_env
    assert second_env[launcher.KEY_NAME] == "synthetic-judge-key"
    assert "FLASHCARD_AI_API_KEY" not in second_env
    assert "DATABASE_URL" not in second_env
    assert set(second_env) <= set(launcher.PASS_THROUGH_ENV) | {
        "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "PYTHONNOUSERSITE",
        launcher.KEY_NAME,
    }
    assert calls[0][1]["capture_output"] is True
    assert calls[1][1]["check"] is False


def test_launcher_stops_before_key_access_on_failed_sha_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append(command)
        return SimpleNamespace(
            returncode=2,
            stderr=json.dumps({"status": "pilot_rejected",
                               "reason": "approval_receipt_changed"}),
        )

    monkeypatch.setattr(launcher.subprocess, "run", fake_run)
    monkeypatch.setattr(launcher, "_read_key", lambda _: pytest.fail("key_read_too_early"))
    assert launcher.main(["--execute"]) == 2
    assert len(calls) == 1


def test_keyless_preflight_accepts_only_known_pdf_warnings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            returncode=2,
            stderr=("Ignoring wrong pointing object 7 0 (offset 0)\n"
                    + json.dumps({"status": "pilot_rejected",
                                  "reason": "source_judge_key_unavailable"}) + "\n"),
        )

    monkeypatch.setattr(launcher.subprocess, "run", fake_run)
    assert launcher._keyless_preflight(["--execute"], {}) is True

    def noisy_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            returncode=2,
            stderr=("unexpected diagnostic\n"
                    + json.dumps({"status": "pilot_rejected",
                                  "reason": "source_judge_key_unavailable"}) + "\n"),
        )

    monkeypatch.setattr(launcher.subprocess, "run", noisy_run)
    assert launcher._keyless_preflight(["--execute"], {}) is False
