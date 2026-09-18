import pytest
from pydantic import ValidationError

from app.config import Settings


def configured(**overrides):
    return Settings(_env_file=None, **({
        "database_url": "postgresql+asyncpg://test:test@localhost/test",
        "secret_key": "test-only-secret-with-adequate-entropy-1234567890",
        "generation_source_encryption_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    } | overrides))


def test_telemetry_has_no_default_destination_and_requires_explicit_enablement():
    settings = configured()
    assert settings.telemetry_enabled is False
    assert settings.telemetry_endpoint is None
    with pytest.raises(ValidationError, match="requires TELEMETRY_ENDPOINT"):
        configured(telemetry_enabled=True)
    assert configured(telemetry_enabled=True,
                      telemetry_endpoint="https://collector.example.test/metrics").telemetry_enabled


@pytest.mark.parametrize("endpoint", [
    "http://collector.example.test", "https://user:password@collector.example.test",
    "https://collector.example.test?key=private", "https://collector.example.test/#private",
])
def test_reporting_destination_cannot_use_cleartext_or_embed_secrets(endpoint):
    with pytest.raises(ValidationError, match="must use HTTPS"):
        configured(telemetry_endpoint=endpoint)


@pytest.mark.parametrize("field", ["request_retention_days", "generation_job_retention_days",
                                  "database_metadata_retention_days", "audit_retention_days",
                                  "retention_batch_size"])
def test_retention_settings_refuse_unbounded_or_invalid_cleanup(field):
    with pytest.raises(ValidationError):
        configured(**{field: 0})


def test_worker_health_threshold_must_cover_slow_scheduling_polls():
    with pytest.raises(ValidationError, match="two scheduling poll intervals"):
        configured(generation_worker_poll_seconds=30, worker_health_stale_seconds=10)
    assert configured(generation_worker_poll_seconds=30, worker_health_stale_seconds=60)
