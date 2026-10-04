"""Source-only Ask policy override confined to the disposable offline journey."""
import os

from sqlalchemy.engine import make_url

from app import config


def enable_disposable_source_policy() -> None:
    settings = config.get_settings()
    url = make_url(settings.database_url)
    if (
        os.getenv("RUN_JOURNEY_TESTS") != "1"
        or os.getenv("JOURNEY_RAG_MODE") != "rag-on"
        or settings.environment != "test"
        or url.drivername != "postgresql+asyncpg"
        or url.database != "journey_test"
        or url.host not in {"127.0.0.1", "localhost", "::1"}
        or settings.rag_ai_provider_enabled
        or settings.rag_embedding_api_key_value != "journey-deterministic-no-network"
    ):
        raise RuntimeError("Refusing source policy outside the disposable offline journey")
    config.ASK_RUNTIME_POLICY_VERSION = config.ASK_REQUIRED_RELEASE_POLICY_VERSION


if os.getenv("JOURNEY_RAG_MODE") == "rag-on":
    enable_disposable_source_policy()

from app.main import app  # noqa: E402,F401 - guard precedes application import
