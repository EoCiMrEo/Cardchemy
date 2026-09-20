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
    operator_keys = ("ENVIRONMENT", "DATABASE_URL", "SECRET_KEY", "FLASHCARD_AI_API_KEY",
                     "RAG_AI_API_KEY", "RAG_EMBEDDING_API_KEY", "AI_API_KEY", "GEMINI_API_KEY",
                     "SMTP_HOST", "SMTP_PASSWORD", "RUN_LIVE_AI_TESTS",
                     "POSTGRES_TEST_DATABASE_URL", "JOURNEY_INSTRUCTOR_PASSWORD")
    for key in operator_keys:
        monkeypatch.setenv(key, "operator-setting-must-not-leak")
    monkeypatch.setenv("PATH", "runtime-path")
    monkeypatch.setenv("CI", "true")
    environment = namespace["system_environment"]()
    assert environment["PATH"] == "runtime-path"
    assert environment["CI"] == "true"
    assert all(key not in environment for key in operator_keys)


def test_journey_rag_off_scenario_starts_no_rag_workers_or_credentials(monkeypatch):
    script = Path(__file__).resolve().parents[2] / "scripts/test_journey.py"
    monkeypatch.syspath_prepend(str(script.parent))
    namespace = runpy.run_path(str(script))

    disabled = namespace["rag_environment"](False)
    assert disabled == {
        "RAG_ENABLED": "false",
        "RAG_AI_PROVIDER_ENABLED": "false",
        "RAG_EMBEDDING_PROVIDER_ENABLED": "false",
    }
    assert namespace["journey_worker_actions"](False) == (
        "worker",
        "email-worker",
    )

    enabled = namespace["rag_environment"](True)
    assert enabled["RAG_ENABLED"] == "true"
    assert enabled["RAG_EMBEDDING_MODEL"] == "gemini-embedding-001"
    assert enabled["RAG_AI_PROVIDER_MAX_RETRIES"] == "0"
    assert enabled["RAG_EMBEDDING_PROVIDER_MAX_RETRIES"] == "0"
    assert namespace["journey_worker_actions"](True) == (
        "worker",
        "index-worker",
        "answer-worker",
        "email-worker",
    )


def test_service_harness_reports_only_static_failure_identity_and_location(monkeypatch, capsys):
    script = Path(__file__).resolve().parents[2] / "scripts/test_services.py"
    namespace = runpy.run_path(str(script))
    captured = subprocess.CompletedProcess(
        args=["pytest"],
        returncode=1,
        stdout=(
            "FAILED tests/postgres/test_example.py::test_safe_case - AssertionError\n"
            "tests/postgres/test_example.py:42: GENERATED_CREDENTIAL_MUST_NOT_PRINT\n"
            "sqlalchemy.exc.IntegrityError: private database detail\n"
        ),
        stderr="private fixture text must not print",
    )
    monkeypatch.setattr(namespace["subprocess"], "run", lambda *args, **kwargs: captured)

    assert namespace["run_service_tests"](
        ["pytest"], cwd=Path.cwd(), environment={}
    ) == 1
    output = capsys.readouterr().out
    assert "Failed service test: tests/postgres/test_example.py::test_safe_case" in output
    assert "Safe failure location: tests/postgres/test_example.py:42" in output
    assert "Safe failure type: sqlalchemy.exc.IntegrityError" in output
    assert "GENERATED_CREDENTIAL_MUST_NOT_PRINT" not in output
    assert "private fixture text" not in output


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


def test_postgres_readiness_does_not_retry_invalid_credentials(monkeypatch):
    import asyncpg
    script = Path(__file__).resolve().parents[2] / "scripts/test_services.py"
    namespace = runpy.run_path(str(script))
    attempts = []

    async def connect(**_options):
        attempts.append(True)
        raise asyncpg.InvalidPasswordError("invalid generated credential")

    monkeypatch.setattr(asyncpg, "connect", connect)
    with pytest.raises(asyncpg.InvalidPasswordError):
        namespace["wait_postgres_ready"](54321, "generated-test-secret", "regression_test")
    assert len(attempts) == 1


async def test_private_journey_worker_refuses_an_ordinary_application_database(monkeypatch):
    script = Path(__file__).resolve().parent / "support/journey_runtime.py"
    namespace = runpy.run_path(str(script))
    monkeypatch.setenv("RUN_JOURNEY_TESTS", "0")
    with pytest.raises(RuntimeError, match="generated disposable journey database"):
        await namespace["require_disposable_database"]()


async def test_journey_rag_providers_satisfy_grounding_and_support_contracts():
    from uuid import uuid4

    from app.ai.answering import (
        ClaimSupportOutput,
        GroundedAnswerOutput,
        render_answer_prompts,
        render_support_prompts,
        validate_grounded_answer,
        validate_support_output,
    )
    from app.services.knowledge_retrieval import RetrievedKnowledgeChunk
    from tests.support.journey_runtime import JourneyAnswerProvider, JourneyEmbeddingProvider

    chunk = RetrievedKnowledgeChunk(
        chunk_id=uuid4(), document_id=uuid4(), document_title="Journey Leaf Facts",
        content_revision_id=uuid4(), index_revision_id=uuid4(), page_number=1,
        section=None,
        content="Chlorophyll gives leaves their Green color. Photosynthesis converts light into chemical energy.",
        token_count=16, embedding_space_hash="a" * 64, corpus_revision=1,
        vector_similarity=1.0, lexical_score=1.0, vector_rank=1, lexical_rank=1,
        fusion_score=1.0,
    )
    provider = JourneyAnswerProvider()
    system, user = render_answer_prompts(
        question="What color does chlorophyll give leaves?", history=(), chunks=(chunk,)
    )
    answer = await provider.generate_structured(
        response_model=GroundedAnswerOutput, system_prompt=system, user_prompt=user,
        max_output_tokens=512, operation="rag_answer",
    )
    claims = validate_grounded_answer(answer.data, (chunk,))
    support_system, support_user = render_support_prompts(
        question="What color does chlorophyll give leaves?", claims=claims, chunks=(chunk,)
    )
    support = await provider.generate_structured(
        response_model=ClaimSupportOutput, system_prompt=support_system,
        user_prompt=support_user, max_output_tokens=256, operation="rag_support",
    )
    assert validate_support_output(support.data, len(claims))
    embedding = await JourneyEmbeddingProvider().embed_query("chlorophyll color")
    assert len(embedding.vectors[0]) == 1536
