from pathlib import Path
import re
import secrets

import pytest
from pydantic import ValidationError

from app.config import ROOT_DIR, Settings


def test_required_secrets_fail_fast(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
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


def test_environment_file_path_is_absolute_and_root_relative():
    configured_path = Path(Settings.model_config["env_file"])
    assert configured_path.is_absolute()
    assert configured_path == ROOT_DIR / ".env"


def test_root_loader_is_cwd_independent_and_process_environment_wins(tmp_path, monkeypatch):
    test_secret = secrets.token_urlsafe(48)
    root_env = tmp_path / ".env"
    root_env.write_text(
        "POSTGRES_DB=sample_db\n"
        "POSTGRES_USER=sample_user\n"
        "POSTGRES_PASSWORD=a:p@ssword\n"
        "APP_NAME=From root file\n"
        f"SECRET_KEY={test_secret}\n"
        "GENERATION_SOURCE_ENCRYPTION_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n",
        encoding="utf-8",
    )
    monkeypatch.setitem(Settings.model_config, "env_file", root_env)
    for key in (
        "DATABASE_URL",
        "POSTGRES_PASSWORD",
        "APP_NAME",
        "SECRET_KEY",
        "GENERATION_SOURCE_ENCRYPTION_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path / "..")
    from_root_parent = Settings()
    monkeypatch.chdir(tmp_path)
    from_root = Settings()
    assert from_root.database_url == from_root_parent.database_url
    assert from_root.database_url == (
        "postgresql+asyncpg://sample_user:a%3Ap%40ssword@127.0.0.1:5432/sample_db"
    )
    assert from_root.app_name == "From root file"

    monkeypatch.setenv("APP_NAME", "From process")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@127.0.0.1/override")
    overridden = Settings()
    assert overridden.app_name == "From process"
    assert overridden.database_url.endswith("/override")

    monkeypatch.delenv("APP_NAME")
    isolated = Settings(
        _env_file=None,
        secret_key=test_secret,
        generation_source_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    )
    assert isolated.app_name == "Cardchemy"


def test_root_example_covers_application_and_compose_settings():
    example = (ROOT_DIR / ".env.example").read_text(encoding="utf-8")
    names = re.findall(r"(?m)^([A-Z][A-Z0-9_]*)=", example)
    assert len(names) == len(set(names))
    application_names = {name.upper() for name in Settings.model_fields}
    compose_text = "\n".join(
        (ROOT_DIR / name).read_text(encoding="utf-8")
        for name in (
            "docker-compose.yml",
            "docker-compose.dev.yml",
            "docker-compose.prod.yml",
        )
    )
    # Deliberate fail-fast interpolation references removed keys, but those
    # names are not supported template settings. Their guard contract has
    # separate migration tests; keep this check about active Compose inputs.
    active_compose_text = "\n".join(
        line for line in compose_text.splitlines()
        if "CARDCH_LEGACY_AI_CONFIGURATION_ERROR" not in line
    )
    compose_names = set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)", active_compose_text))
    assert application_names | compose_names <= set(names)
    assert "SMTP_PORT=1025" in example
    assert "GENERATION_DAILY_JOBS_PER_USER=20" in example
    assert "VITE_API_URL=/api" in example


def test_bootstrap_template_validates_without_operator_environment_and_never_overwrites(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("bootstrap_env", ROOT_DIR / "scripts/bootstrap_env.py")
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    rendered = bootstrap.render_environment((ROOT_DIR / ".env.example").read_text(encoding="utf-8"))
    temporary_env = tmp_path / ".env"
    temporary_env.write_text(rendered, encoding="utf-8")
    loaded = Settings(_env_file=temporary_env)
    assert loaded.generation_daily_jobs_per_user == 20
    assert loaded.smtp_port == 1025
    assert loaded.smtp_security == "none"
    assert loaded.database_url.startswith("postgresql+asyncpg://admin:")
    assert "@127.0.0.1:5432/cardchemy" in loaded.database_url
    monkeypatch.setattr(bootstrap, "OUTPUT", temporary_env)
    before = temporary_env.read_bytes()
    with pytest.raises(SystemExit, match="Refusing to overwrite"):
        bootstrap.main()
    assert temporary_env.read_bytes() == before


def test_unrelated_root_environment_key_remains_accepted(tmp_path):
    root_env = tmp_path / ".env"
    root_env.write_text("UNRELATED_OPERATOR_SETTING=retained\n", encoding="utf-8")
    configured = Settings(
        _env_file=root_env,
        database_url="postgresql+asyncpg://user:password@database/app",
        secret_key="a-test-secret-with-real-entropy-1234567890",
        generation_source_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    )
    assert configured.flashcard_ai_provider_enabled is False
    assert configured.rag_enabled is False


def test_removed_email_verification_switch_cannot_create_a_partial_workflow():
    assert "email_verification_required" not in Settings.model_fields


def test_ai_request_pack_must_fit_context_and_safety_adjusted_tpm():
    base = {
        "_env_file": None,
        "database_url": "postgresql+asyncpg://user:password@database/app",
        "secret_key": "a-test-secret-with-real-entropy-1234567890",
        "generation_source_encryption_key": (
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        ),
    }
    with pytest.raises(ValidationError):
        Settings(
            **base,
            flashcard_ai_request_input_target_tokens=10_000,
            flashcard_ai_max_output_tokens=2_000,
            flashcard_ai_context_window_tokens=11_000,
        )
    with pytest.raises(ValidationError):
        Settings(
            **base,
            flashcard_ai_request_input_target_tokens=10_000,
            flashcard_ai_input_tokens_per_minute=10_000,
            flashcard_ai_rate_limit_safety_percent=80,
        )
