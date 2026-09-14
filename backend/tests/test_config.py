from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import BACKEND_DIR, Settings


def test_required_secrets_fail_fast(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_known_insecure_secret_is_rejected():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://user:password@database/app",
            secret_key="replace-with-at-least-32-random-characters",
            generation_source_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        )


def test_generation_source_key_must_decode_to_32_bytes():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://user:password@database/app",
            secret_key="a-test-secret-with-real-entropy-1234567890",
            generation_source_encryption_key="not-a-32-byte-key",
        )


def test_generation_worker_must_heartbeat_before_lease_expires():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://user:password@database/app",
            secret_key="a-test-secret-with-real-entropy-1234567890",
            generation_source_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            generation_lease_seconds=30,
            generation_heartbeat_seconds=30,
        )


def test_production_security_settings_are_required():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            database_url="postgresql+asyncpg://user:password@database/app",
            secret_key="a-production-secret-with-real-entropy-123456789",
            generation_source_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            refresh_cookie_secure=False,
        )


def test_environment_file_path_is_absolute_and_backend_relative():
    configured_path = Path(Settings.model_config["env_file"])
    assert configured_path.is_absolute()
    assert configured_path == BACKEND_DIR / ".env"
