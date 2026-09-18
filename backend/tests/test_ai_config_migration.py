"""Removed AI names fail closed across root-file and process settings."""

from __future__ import annotations

import pytest

from app.config import REMOVED_AI_NAMES, Settings


BASE = {
    "database_url": "postgresql+asyncpg://test:test@127.0.0.1/test",
    "secret_key": "test-only-secret-key-with-adequate-entropy-1234567890",
    "generation_source_encryption_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
}
PRIVATE_SENTINEL = "PRIVATE_LEGACY_VALUE_MUST_NOT_LEAK"


@pytest.mark.parametrize(
    ("root_value", "process_value", "expected_rejection"),
    [
        (PRIVATE_SENTINEL, None, True),
        (None, PRIVATE_SENTINEL, True),
        (PRIVATE_SENTINEL, "", True),
        ("", PRIVATE_SENTINEL, True),
        ("", "", False),
        (None, None, False),
    ],
    ids=[
        "root-only", "process-only", "empty-process-does-not-hide-root",
        "empty-root-does-not-hide-process", "both-empty", "both-absent",
    ],
)
@pytest.mark.parametrize("removed_name", sorted(REMOVED_AI_NAMES))
def test_removed_names_rejected_from_each_source_without_value_leak(
    tmp_path, monkeypatch, removed_name, root_value, process_value, expected_rejection,
):
    assert removed_name in REMOVED_AI_NAMES
    env_file = tmp_path / ".env"
    if root_value is not None:
        env_file.write_text(f"{removed_name}={root_value}\n", encoding="utf-8")
    for name in REMOVED_AI_NAMES:
        monkeypatch.delenv(name, raising=False)
    if process_value is not None:
        monkeypatch.setenv(removed_name, process_value)

    if expected_rejection:
        with pytest.raises(ValueError, match="Removed AI configuration keys") as error:
            Settings(_env_file=env_file, **BASE)
        assert removed_name in str(error.value)
        assert PRIVATE_SENTINEL not in str(error.value)
    else:
        Settings(_env_file=env_file, **BASE)


def test_new_name_does_not_mask_removed_root_name(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(f"AI_MODEL={PRIVATE_SENTINEL}\n", encoding="utf-8")
    for name in REMOVED_AI_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FLASHCARD_AI_MODEL", "gemini-3.8-flash")
    with pytest.raises(ValueError, match="AI_MODEL") as error:
        Settings(_env_file=env_file, **BASE)
    assert PRIVATE_SENTINEL not in str(error.value)
