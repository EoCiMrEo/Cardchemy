"""Rehearsal destruction guards must reject resources outside their ownership."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


spec = importlib.util.spec_from_file_location(
    "test_production_rehearsal", Path(__file__).resolve().parents[2] / "scripts/test_production_rehearsal.py"
)
rehearsal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rehearsal)
PROJECT = "cardchemy-rehearsal-0123456789abcdef-source"


@pytest.mark.parametrize("name", ["cardchemy", "production", "../outside", "cardchemy-rehearsal-0123456789abcdef-prod", "cardchemy-rehearsal-not-unique-source"])
def test_generated_project_identity_rejects_operator_names(name):
    with pytest.raises(rehearsal.RehearsalError):
        rehearsal.project_name(name)


@pytest.mark.parametrize("name,project,volume", [
    ("production_postgres_data", PROJECT, "postgres_data"),
    (f"{PROJECT}_postgres_data", "production", "postgres_data"),
    (f"{PROJECT}_postgres_data", PROJECT, "unrelated"),
])
def test_volume_removal_requires_exact_name_and_both_owner_labels(name, project, volume):
    with pytest.raises(rehearsal.RehearsalError):
        rehearsal.owned_volume({"Name": name, "Labels": {"com.docker.compose.project": project, "com.docker.compose.volume": volume}}, PROJECT)


def test_rehearsal_filters_inherited_live_credentials(monkeypatch):
    for key in ("SECRET_KEY", "DATABASE_URL", "SMTP_PASSWORD", "FLASHCARD_AI_API_KEY", "RAG_AI_API_KEY", "RAG_EMBEDDING_API_KEY", "AI_API_KEY", "GEMINI_API_KEY", "GITHUB_TOKEN"):
        monkeypatch.setenv(key, "not-a-real-secret")
    filtered = rehearsal.environment()
    assert not {"SECRET_KEY", "DATABASE_URL", "SMTP_PASSWORD", "FLASHCARD_AI_API_KEY", "RAG_AI_API_KEY", "RAG_EMBEDDING_API_KEY", "AI_API_KEY", "GEMINI_API_KEY", "GITHUB_TOKEN"} & filtered.keys()


def test_recovered_set_verification_uses_computed_collection_counts():
    class ApplicationContract:
        def __init__(self):
            self.paths = []

        def login(self, *_):
            return "fixture-token"

        def request(self, method, path, **_):
            self.paths.append(path)
            if path == "/":
                return b"fixture", {name: "fixture" for name in (
                    "content-security-policy", "x-frame-options", "x-content-type-options", "strict-transport-security")}
            if path == "/api/subjects/subject-id/sets":
                # Selecting by fixture ID must ignore unrelated collection entries.
                return [{"id": "other-set", "is_published": False, "approved_count": 0},
                        {"id": "fixture-set", "is_published": True, "approved_count": 1}], {}
            if path == "/api/study/sets/fixture-set/session?mode=review_all":
                return {"cards": [{"id": "fixture-card"}]}, {}
            if path == "/api/study/sets/fixture-set/progress":
                return {"studied": 1, "correct_count": 1, "completion_percentage": 100}, {}
            if path == "/api/study/progress":
                return {"is_correct": True}, {}
            if path == "/api/subjects/subject-id/sets/fixture-set":
                pytest.fail("The single-set endpoint does not populate approved_count")
            return {}, {}

    app = ApplicationContract()
    rehearsal.verify_application(app, {"instructor_email": "fixture@example.com", "instructor_password": "fixture-password",
                                       "student_email": "student@example.com", "student_password": "fixture-password"},
                                 {"subject": "subject-id", "set": "fixture-set", "answer": {}, "key": "fixture-key", "result": {"is_correct": True}})
    assert "/api/subjects/subject-id/sets" in app.paths


@pytest.mark.parametrize("private_output,category", [
    (b"pull access denied for image, secret=sentinel-never-expose", "image_pull_access_denied"),
    (b"container sentinel-never-expose has no healthcheck configured", "healthcheck_missing"),
    (b"failed to solve: password=sentinel-never-expose", "image_build_failed"),
    (b"container unhealthy token=sentinel-never-expose", "service_unhealthy"),
    (b"asyncpg.CannotConnectNowError: database system is starting up secret=sentinel-never-expose", "database_starting"),
    (b"ConnectionResetError password=sentinel-never-expose", "connection_reset"),
    (b"ConnectionRefusedError address=sentinel-never-expose", "connection_refused"),
    (b"internal exception secret=sentinel-never-expose", "command_failed"),
])
def test_command_failures_emit_only_closed_diagnostics(monkeypatch, capsys, private_output, category):
    monkeypatch.setattr(rehearsal.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=1, stderr=private_output, stdout=b"untrusted private stdout=sentinel-never-expose"))
    with pytest.raises(rehearsal.RehearsalError) as failure:
        rehearsal.run(["docker", "compose", "up"], cwd=Path("."), environment={}, stage="compose_up")
    assert str(failure.value) == f"compose_up:{category}"
    output = capsys.readouterr()
    assert "sentinel-never-expose" not in output.out + output.err + str(failure.value)


def test_shared_images_are_built_before_startup_considers_image_pull():
    calls = []
    stack = object.__new__(rehearsal.Stack)
    stack.compose = lambda *args, **kwargs: calls.append(args)
    stack.start(build=True)
    assert calls[0] == ("build",)
    assert calls[1] == ("up", "-d", "--no-build", "--wait", "--wait-timeout", "180")


def diagnostic_fixture():
    return {"Name": f"/{PROJECT}-backend-1", "Config": {"Env": ["SECRET_KEY=sentinel-never-expose"],
            "Cmd": ["sentinel-never-expose"], "Labels": {"com.docker.compose.project": PROJECT,
            "com.docker.compose.service": "backend", "private-label": "sentinel-never-expose"}},
            "State": {"Status": "running", "ExitCode": 0, "Error": "sentinel-never-expose",
                      "Health": {"Status": "healthy", "Log": [{"Output": "sentinel-never-expose"}]}},
            "Id": "sentinel-never-expose"}


def test_container_diagnostic_excludes_all_private_inspect_fields():
    result = rehearsal.container_diagnostic(diagnostic_fixture(), PROJECT)
    assert result == {"service": "backend", "status": "running", "health": "healthy", "exit_code": 0}
    assert "sentinel-never-expose" not in str(result)


@pytest.mark.parametrize("mutation", ["project", "service", "name", "status", "health", "exit_code"])
def test_container_diagnostic_rejects_unowned_or_untrusted_fields(mutation):
    document = diagnostic_fixture()
    if mutation == "project":
        document["Config"]["Labels"]["com.docker.compose.project"] = "operator-production"
    elif mutation == "service":
        document["Config"]["Labels"]["com.docker.compose.service"] = "unowned-service"
    elif mutation == "name":
        document["Name"] = "/unowned-operator-container"
    elif mutation == "status":
        document["State"]["Status"] = "sentinel-never-expose"
    elif mutation == "health":
        document["State"]["Health"]["Status"] = "sentinel-never-expose"
    else:
        document["State"]["ExitCode"] = "sentinel-never-expose"
    with pytest.raises(rehearsal.RehearsalError) as failure:
        rehearsal.container_diagnostic(document, PROJECT)
    assert "sentinel-never-expose" not in str(failure.value)


def test_tls_edge_retains_a_real_loopback_image_probe(tmp_path):
    stack = rehearsal.Stack(Path("."), tmp_path, PROJECT, 62119, "fixture-backend:tested", "fixture-frontend:tested", {})
    import json
    services = json.loads(stack.config.read_text())["services"]
    assert "index-worker" in rehearsal.SERVICES
    assert "answer-worker" in rehearsal.SERVICES
    assert services["index-worker"]["image"] == "fixture-backend:tested"
    assert services["answer-worker"]["image"] == "fixture-backend:tested"
    edge = services["tls-edge"]
    assert "healthcheck" not in edge
    assert edge["ports"] == ["127.0.0.1:62119:8443"]
    configuration = rehearsal.tls_nginx_configuration()
    assert "listen 127.0.0.1:8080;" in configuration
    assert "location = /healthz" in configuration
    assert "listen 8443 ssl;" in configuration
    assert "listen 8080;" not in configuration


def rag_fixture_ids():
    return {
        "subject": "00000000-0000-0000-0000-000000000001",
        "other_subject": "00000000-0000-0000-0000-000000000002",
        "student": "00000000-0000-0000-0000-000000000003",
        "other_student": "00000000-0000-0000-0000-000000000004",
        "set": "00000000-0000-0000-0000-000000000005",
        "card": "00000000-0000-0000-0000-000000000006",
    }


def test_provider_free_rag_fixture_uses_real_guarded_transitions():
    captured = {}

    class StackContract:
        def compose(self, *args, **kwargs):
            captured["args"] = args
            captured["sql"] = kwargs["input_data"].decode()
            return b""

    fixture = rehearsal.seed_rag_fixture(StackContract(), rag_fixture_ids())
    sql = captured["sql"]
    assert captured["args"][-2:] == ("-f", "-")
    assert sql.index("status='pending_index'") < sql.index("status='ready',is_active=true")
    assert sql.index("'queued',repeat('b',64)") < sql.index("status='running'")
    assert sql.index("INSERT INTO rag_message_sources") < sql.index("status='completed'")
    assert "array_prepend(1::real,array_fill(0::real,ARRAY[1535]))::vector" in sql
    assert "reviewed_at=now(),published_at=now()" in sql
    assert "SET CONSTRAINTS ALL IMMEDIATE" in sql
    assert "https://rehearsal.invalid/v1" in sql
    assert "provider_request_count" not in sql  # guarded default remains zero
    assert "API_KEY" not in sql and "password" not in sql.lower()
    for key in ("document", "content_revision", "index_revision", "chunk", "thread",
                "question", "rag_answer", "citation", "answer_job", "answer_quota"):
        assert fixture[key]


def test_rag_database_readback_requires_extension_indexes_and_authorized_retrieval():
    fixture = rag_fixture_ids() | {
        key: f"00000000-0000-0000-0000-{value:012d}"
        for value, key in enumerate((
            "document", "content_revision", "index_revision", "chunk", "thread",
            "question", "rag_answer", "citation", "answer_job", "answer_quota",
        ), start=10)
    }
    required = {
        "vector_extension", "embedding_schema", "embedding_indexes",
        "published_active_revision", "page_chunk_vector", "authorized_exact_retrieval",
        "other_student_isolated", "private_conversation", "completed_answer_job",
        "grounded_citation",
    }
    captured = {}
    stack = object.__new__(rehearsal.Stack)

    def compose(*_args, **_kwargs):
        captured["sql"] = _args[-1]
        return __import__("json").dumps(dict.fromkeys(required, True)).encode()

    stack.compose = compose
    assert stack.verify_rag_database(fixture) == dict.fromkeys(required, True)
    sql = captured["sql"]
    assert "eligible_subject_knowledge_chunks" in sql
    assert "JOIN enrollments access" in sql
    assert "extversion = '0.8.6'" in sql
    assert "vector(1536)" in sql
    assert "provider_request_count=0" in sql
    assert fixture["student"] in sql and fixture["other_student"] in sql

    stack.compose = lambda *_args, **_kwargs: __import__("json").dumps(
        dict.fromkeys(required, True) | {"other_student_isolated": False}
    ).encode()
    with pytest.raises(rehearsal.RehearsalError, match="rag_recovery_contract"):
        stack.verify_rag_database(fixture)


def test_rag_api_readback_checks_private_owner_and_subject_boundaries():
    fixture = rag_fixture_ids() | {
        "document": "00000000-0000-0000-0000-000000000010",
        "content_revision": "00000000-0000-0000-0000-000000000011",
        "index_revision": "00000000-0000-0000-0000-000000000012",
        "chunk": "00000000-0000-0000-0000-000000000013",
        "thread": "00000000-0000-0000-0000-000000000014",
        "question": "00000000-0000-0000-0000-000000000015",
        "rag_answer": "00000000-0000-0000-0000-000000000016",
        "answer_job": "00000000-0000-0000-0000-000000000017",
    }
    accounts = {
        "instructor_email": "instructor@example.test", "instructor_password": "fixture",
        "student_email": "student@example.test", "student_password": "fixture",
        "other_student_email": "other@example.test", "other_student_password": "fixture",
    }

    class ApplicationContract:
        def __init__(self):
            self.calls = []

        def login(self, email, _password):
            return {accounts["instructor_email"]: "instructor",
                    accounts["student_email"]: "student"}.get(email, "other")

        def request(self, method, path, *, token=None, expected=200, **_kwargs):
            self.calls.append((method, path, token, expected))
            if token == "instructor" and path.endswith("/knowledge/documents"):
                return {"documents": [{
                    "id": fixture["document"],
                    "content_revision": {"id": fixture["content_revision"], "status": "ready",
                                         "is_active": True, "reviewed_at": "now", "published_at": "now"},
                    "index_revision": {"id": fixture["index_revision"], "status": "ready",
                                       "is_active": True, "chunk_count": 1, "embedded_count": 1},
                }]}, {}
            if path.endswith("/rag/threads"):
                if token == "student" and method == "GET":
                    return {"threads": [{"id": fixture["thread"]}]}, {}
                return {"threads": []}, {}
            if path.endswith(f"/rag/threads/{fixture['thread']}") and token == "student":
                return {"messages": [
                    {"id": fixture["question"], "role": "user"},
                    {"id": fixture["rag_answer"], "role": "assistant", "hidden": False,
                     "content": rehearsal.RAG_ANSWER,
                     "sources": [{"chunk_id": fixture["chunk"], "source_quote": rehearsal.RAG_QUOTE}]},
                ]}, {}
            if path.endswith(f"/messages/{fixture['rag_answer']}/sources") and token == "student":
                return [{"document_id": fixture["document"],
                         "content_revision_id": fixture["content_revision"],
                         "index_revision_id": fixture["index_revision"]}], {}
            if path.endswith("/answer-jobs") and token == "student":
                return {"jobs": [{"id": fixture["answer_job"], "status": "completed",
                                  "answer_message_id": fixture["rag_answer"],
                                  "provider_request_count": 0}]}, {}
            return {}, {}

    app = ApplicationContract()
    rehearsal.verify_rag_application(app, accounts, fixture)
    assert ("GET", f"/api/subjects/{fixture['subject']}/rag/threads/{fixture['thread']}",
            "instructor", 404) in app.calls
    assert ("GET", f"/api/subjects/{fixture['subject']}/rag/threads", "other", 403) in app.calls
    assert ("POST", f"/api/subjects/{fixture['subject']}/rag/threads", "student", 503) in app.calls
    assert ("GET", f"/api/subjects/{fixture['subject']}/knowledge/documents", "student", 403) in app.calls


def test_pgvector_restore_probe_requires_an_empty_target_and_access_scoped_queries(
    monkeypatch,
):
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    probe_spec = importlib.util.spec_from_file_location(
        "test_pgvector_restore_contract", scripts / "test_pgvector_restore.py"
    )
    probe = importlib.util.module_from_spec(probe_spec)
    probe_spec.loader.exec_module(probe)
    assert "table_schema='public'" in probe.EMPTY_SQL
    assert "NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')" in probe.EMPTY_SQL
    assert "USING hnsw" in probe.SCHEMA_SQL and "USING gin" in probe.SCHEMA_SQL
    assert "JOIN rag_restore_access" in probe.CHECK_SQL
    assert "p.published AND p.active" in probe.CHECK_SQL
    assert probe.STUDENT in probe.CHECK_SQL and probe.OTHER_STUDENT in probe.CHECK_SQL
