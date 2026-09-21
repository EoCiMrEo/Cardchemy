"""Rehearse a clean production-profile installation and recovery, without live services.

Linux/amd64 Docker hosts only. All configuration, accounts, certificates, dumps,
containers and volumes are generated in a private temporary workspace. The real
operator .env is never read. Only a small content-free result may be retained.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import runpy
import secrets
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode
from uuid import UUID, uuid4


ensure_no_legacy_configuration = runpy.run_path(
    str(Path(__file__).with_name("check_config_migration.py"))
)["ensure_no_legacy_configuration"]

ROOT = Path(__file__).resolve().parents[1]
HOST = "cards.rehearsal.test"
PREFIX = "cardchemy-rehearsal-"
SERVICES = {
    "db", "migrate", "backend", "worker", "index-worker", "answer-worker", "email-worker",
    "frontend", "tls-edge",
}
CONTAINER_STATUSES = {"created", "running", "paused", "restarting", "removing", "exited", "dead"}
HEALTH_STATUSES = {None, "starting", "healthy", "unhealthy"}
STARTUP_EVENTS = {"api_started", "api_stopped", "database_revision_verified", "worker_started", "process_failed"}
ALLOWED_ENVIRONMENT = {"PATH", "HOME", "TMP", "TEMP", "TMPDIR",
                       "SYSTEMROOT", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "PROGRAMDATA",
                       "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432"}
RAG_EVIDENCE = "Synthetic recovery evidence confirms chlorophyll gives leaves their green color."
RAG_QUOTE = "chlorophyll gives leaves their green color"
RAG_ANSWER = "Chlorophyll gives leaves their green color."
RAG_SPACE_IDENTITY = (
    "openai_compatible", "https://rehearsal.invalid/v1", "synthetic-recovery-embedding",
    "rehearsal-v1", "raw_text_v1", 1536, "float32", "cosine",
    "shared_input", "shared_input",
)


class RehearsalError(RuntimeError):
    """Only fixed diagnostic stages may leave the private workspace."""


def embedding_space_hash(identity: tuple[object, ...]) -> str:
    """Match the migration's credential-free, length-framed identity hash."""
    values = [str(value) for value in identity]
    framed = "".join(f"{len(value.encode('utf-8'))}:{value}" for value in values)
    return hashlib.sha256(framed.encode("utf-8")).hexdigest()


def fixture_uuid(fixture: dict, key: str) -> str:
    """Accept only canonical UUID fixture identifiers before composing SQL."""
    try:
        return str(UUID(str(fixture[key])))
    except (KeyError, TypeError, ValueError, AttributeError):
        raise RehearsalError("rag_fixture_identity") from None


def failure_category(output: bytes) -> str:
    """Classify private command output without echoing any captured text."""
    lowered = output[-128 * 1024:].lower()
    rules = (
        ("healthcheck_missing", (b"has no healthcheck configured",)),
        ("database_starting", (b"cannotconnectnowerror", b"database system is starting up")),
        ("connection_reset", (b"connectionreseterror",)),
        ("connection_refused", (b"connectionrefusederror",)),
        ("image_pull_access_denied", (b"pull access denied", b"repository does not exist", b"insufficient_scope")),
        ("image_build_failed", (b"failed to solve:", b"failed to build", b"build failed")),
        ("service_unhealthy", (b"unhealthy", b"didn't complete successfully")),
        ("host_port_busy", (b"port is already allocated", b"address already in use")),
        ("docker_daemon_unavailable", (b"cannot connect to the docker daemon", b"error during connect")),
    )
    return next((category for category, phrases in rules if any(phrase in lowered for phrase in phrases)), "command_failed")


def container_diagnostic(document: dict, project: str) -> dict:
    """Select only closed lifecycle fields after validating exact ownership."""
    project_name(project)
    labels = document.get("Config", {}).get("Labels", {}) or {}
    service = labels.get("com.docker.compose.service")
    if (labels.get("com.docker.compose.project") != project or service not in SERVICES
            or document.get("Name") != f"/{project}-{service}-1"):
        raise RehearsalError("diagnostic_container_ownership")
    state = document.get("State", {})
    status, health, exit_code = state.get("Status"), state.get("Health", {}).get("Status"), state.get("ExitCode")
    if (status not in CONTAINER_STATUSES or health not in HEALTH_STATUSES
            or type(exit_code) is not int or not 0 <= exit_code <= 255):
        raise RehearsalError("diagnostic_container_contract")
    return {"service": service, "status": status, "health": health, "exit_code": exit_code}


def run(command: list[str], *, cwd: Path, environment: dict[str, str],
        stage: str, input_data: bytes | None = None, timeout: int = 900,
        combined_output: bool = False) -> bytes:
    try:
        result = subprocess.run(command, cwd=cwd, env=environment, input=input_data,
                                capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RehearsalError(stage + ":command_timeout") from None
    except OSError:
        raise RehearsalError(stage + ":command_unavailable") from None
    if result.returncode:
        diagnostic = stage + ":" + failure_category(result.stderr + result.stdout)
        print("Rehearsal: fixed command failure category " + diagnostic, flush=True)
        raise RehearsalError(diagnostic)
    return result.stdout + result.stderr if combined_output else result.stdout


def environment() -> dict[str, str]:
    # In particular, do not inherit application/provider/SMTP/GitHub credentials.
    result = {key: value for key, value in os.environ.items() if key.upper() in ALLOWED_ENVIRONMENT} | {
        "PYTHONUTF8": "1", "COMPOSE_DISABLE_ENV_FILE": "true", "GIT_TERMINAL_PROMPT": "0",
    }
    if sys.platform == "linux":
        result["DOCKER_HOST"] = "unix:///var/run/docker.sock"
    return result


def project_name(value: str) -> str:
    if not re.fullmatch(r"cardchemy-rehearsal-[a-f0-9]{16}-(source|restore)", value):
        raise RehearsalError("project_identity")
    return value


def owned_volume(document: dict, project: str) -> str:
    """Refuse cleanup unless both exact name and Compose ownership match."""
    project_name(project)
    name = document.get("Name")
    labels = document.get("Labels") or {}
    if (name != f"{project}_postgres_data"
            or labels.get("com.docker.compose.project") != project
            or labels.get("com.docker.compose.volume") != "postgres_data"):
        raise RehearsalError("volume_ownership")
    return name


def port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


class LoopbackTLS(http.client.HTTPSConnection):
    """Use real certificate/SNI validation while keeping .test DNS offline."""

    def connect(self) -> None:
        self.sock = self._context.wrap_socket(
            socket.create_connection(("127.0.0.1", self.port), self.timeout),
            server_hostname=self.host,
        )


class Application:
    def __init__(self, tls_port: int, certificate: Path):
        self.port = tls_port
        self.context = ssl.create_default_context(cafile=str(certificate))
        self.cookies: str | None = None

    def request(self, method: str, path: str, *, data=None, token: str | None = None,
                form: bool = False, expected: int = 200, extra_headers: dict | None = None):
        headers = dict(extra_headers or {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if self.cookies:
            headers["Cookie"] = self.cookies
        body = None
        if data is not None:
            body = urlencode(data) if form else json.dumps(data)
            headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
        connection = LoopbackTLS(HOST, self.port, context=self.context, timeout=15)
        try:
            connection.request(method, path, body, headers)
            response = connection.getresponse()
            content = response.read(2 * 1024 * 1024)
            response_headers = {key.lower(): value for key, value in response.getheaders()}
            if response.status != expected:
                raise RehearsalError("https_api_contract")
            if "set-cookie" in response_headers:
                cookie = response_headers["set-cookie"]
                if method == "POST" and path == "/api/auth/login":
                    if not all(term in cookie.lower() for term in ("secure", "httponly", "path=/api/auth")):
                        raise RehearsalError("secure_cookie")
                self.cookies = cookie.split(";", 1)[0]
            if response_headers.get("content-type", "").startswith("application/json"):
                return json.loads(content), response_headers
            return content, response_headers
        finally:
            connection.close()

    def login(self, email: str, password: str) -> str:
        self.cookies = None
        result, _ = self.request("POST", "/api/auth/login", data={"username": email, "password": password}, form=True)
        token = result["access_token"]
        refreshed, _ = self.request("POST", "/api/auth/refresh")
        if not refreshed.get("access_token"):
            raise RehearsalError("refresh_contract")
        return token


class Stack:
    def __init__(self, checkout: Path, workspace: Path, project: str, tls_port: int,
                 backend_image: str, frontend_image: str, shared_secrets: dict[str, str]):
        self.checkout, self.workspace = checkout, workspace
        self.project = project_name(project)
        self.tls_port = tls_port
        self.environment = environment()
        self.config = workspace / f"{project}.json"
        self.env_file = workspace / f"{project}.env"
        # Configuration is an injected rehearsal fixture, not another operator file.
        values = shared_secrets | {
            "POSTGRES_DB": "cardchemy_rehearsal", "POSTGRES_USER": "rehearsal",
            "APP_PORT": "0", "ENVIRONMENT": "production", "DEBUG": "false",
            "FLASHCARD_AI_PROVIDER_ENABLED": "false", "FLASHCARD_AI_API_KEY": "",
            "RAG_ENABLED": "false",
            "RAG_AI_PROVIDER_ENABLED": "false", "RAG_AI_API_KEY": "",
            "RAG_EMBEDDING_PROVIDER_ENABLED": "false", "RAG_EMBEDDING_API_KEY": "",
            "FRONTEND_BASE_URL": f"https://{HOST}:{tls_port}", "CORS_ORIGINS": f"https://{HOST}:{tls_port}",
            "API_DOCS_ENABLED": "false", "REFRESH_COOKIE_SECURE": "true",
            # No outbox events are created. This reserved .test host cannot be a live relay.
            "SMTP_HOST": "smtp.rehearsal.test", "SMTP_PORT": "587",
            "SMTP_FROM_EMAIL": "no-reply@example.com", "SMTP_STARTTLS": "true", "SMTP_IMPLICIT_TLS": "false",
            "SMTP_USERNAME": "", "SMTP_PASSWORD": "", "TELEMETRY_ENABLED": "false",
        }
        self.env_file.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
        self.env_file.chmod(0o600)
        labels = {"cardchemy.rehearsal": self.project.rsplit("-", 1)[0]}
        services = {
            name: {"image": backend_image, "build": {"labels": labels}}
            for name in ("migrate", "backend", "worker", "index-worker", "answer-worker", "email-worker")
        }
        services["frontend"] = {"image": frontend_image, "build": {"labels": labels}}
        services["tls-edge"] = {
            "image": frontend_image, "profiles": ["production"],
            "ports": [f"127.0.0.1:{tls_port}:8443"],
            "depends_on": {"frontend": {"condition": "service_healthy"}},
            "volumes": [f"{workspace / 'tls-nginx.conf'}:/etc/nginx/conf.d/default.conf:ro",
                        f"{workspace / 'certificate.pem'}:/etc/nginx/rehearsal.crt:ro",
                        f"{workspace / 'key.pem'}:/etc/nginx/rehearsal.key:ro"],
        }
        self.config.write_text(json.dumps({"services": services}), encoding="utf-8")
        self.started = False

    def compose(self, *arguments: str, input_data: bytes | None = None, timeout: int = 900) -> bytes:
        ensure_no_legacy_configuration(self.env_file, environment=self.environment)
        # Commands never contain secret values; stdin may contain a generated password.
        category = "_".join(arguments[:1])
        if arguments[0] in {"exec", "run"}:
            programs = {"psql", "pg_dump", "pg_restore", "sha256sum", "alembic", "python"}
            category += "_" + next((item for item in arguments if item in programs), "service")
        return run(["docker", "compose", "--project-name", self.project, "--project-directory", str(self.checkout),
                    "--env-file", str(self.env_file), "-f", str(self.checkout / "docker-compose.yml"),
                    "-f", str(self.checkout / "docker-compose.prod.yml"), "-f", str(self.config),
                    "--profile", "production", *arguments], cwd=self.checkout, environment=self.environment,
                   stage="compose_" + category, input_data=input_data, timeout=timeout)

    def validate(self) -> dict:
        document = json.loads(self.compose("config", "--format", "json"))
        services = document["services"]
        if "mailpit" in services:
            raise RehearsalError("production_mailpit")
        for name in ("db", "backend", "worker", "index-worker", "answer-worker", "email-worker", "migrate"):
            if services[name].get("ports") or services[name].get("volumes", []) and name != "db":
                raise RehearsalError("production_private_services")
        for name in ("frontend", "tls-edge"):
            if any(mapping.get("host_ip") != "127.0.0.1" for mapping in services[name].get("ports", [])):
                raise RehearsalError("production_loopback")
        for name in ("backend", "worker", "index-worker", "answer-worker", "email-worker", "migrate"):
            values = services[name]["environment"]
            if (values["ENVIRONMENT"] != "production" or values["DEBUG"] != "false"
                    or values["API_DOCS_ENABLED"] != "false" or values["REFRESH_COOKIE_SECURE"] != "true"):
                raise RehearsalError("production_settings")
        if any(key in services["backend"]["environment"] for key in (
            "FLASHCARD_AI_API_KEY", "RAG_AI_API_KEY", "RAG_EMBEDDING_API_KEY", "SMTP_PASSWORD"
        )):
            raise RehearsalError("credential_isolation")
        if any(key in services["index-worker"]["environment"] for key in (
            "FLASHCARD_AI_API_KEY", "RAG_AI_API_KEY", "SMTP_PASSWORD"
        )) or "RAG_EMBEDDING_API_KEY" not in services["index-worker"]["environment"]:
            raise RehearsalError("credential_isolation")
        if any(key in services["answer-worker"]["environment"] for key in (
            "FLASHCARD_AI_API_KEY", "SMTP_PASSWORD"
        )) or any(key not in services["answer-worker"]["environment"] for key in (
            "RAG_AI_API_KEY", "RAG_EMBEDDING_API_KEY"
        )):
            raise RehearsalError("credential_isolation")
        for name in ("backend", "worker", "index-worker", "answer-worker"):
            values = services[name]["environment"]
            if values["RAG_ENABLED"] != "false" or values["RAG_AI_PROVIDER_ENABLED"] != "false" \
                    or values["RAG_EMBEDDING_PROVIDER_ENABLED"] != "false":
                raise RehearsalError("rehearsal_ai_must_be_disabled")
        return document

    def start(self, *, build: bool = False) -> None:
        self.started = True
        if build:
            # tls-edge consumes the shared frontend image but does not build it.
            # Finish local builds before Compose considers pulling/starting it.
            self.compose("build", timeout=1200)
        self.compose("up", "-d", "--no-build", "--wait", "--wait-timeout", "180", timeout=300)

    def verify_heads(self) -> None:
        self.compose("run", "--rm", "--no-deps", "backend", "alembic", "current", "--check-heads")
        self.compose("run", "--rm", "--no-deps", "backend", "alembic", "check")

    def counts(self) -> dict:
        sql = """SELECT json_build_object(
          'users',(SELECT count(*) FROM users),
          'subjects',(SELECT count(*) FROM subjects),
          'sets',(SELECT count(*) FROM flashcard_sets),
          'cards',(SELECT count(*) FROM flashcards),
          'enrollments',(SELECT count(*) FROM enrollments),
          'progress',(SELECT count(*) FROM study_progress),
          'receipts',(SELECT count(*) FROM study_answer_submissions),
          'outbox',(SELECT count(*) FROM email_outbox_messages),
          'embedding_spaces',(SELECT count(*) FROM rag_embedding_spaces),
          'knowledge_documents',(SELECT count(*) FROM subject_documents),
          'knowledge_pages',(SELECT count(*) FROM subject_document_pages),
          'knowledge_chunks',(SELECT count(*) FROM subject_document_chunks),
          'knowledge_vectors',(SELECT count(*) FROM subject_document_chunks WHERE embedding IS NOT NULL),
          'rag_threads',(SELECT count(*) FROM rag_threads),
          'rag_messages',(SELECT count(*) FROM rag_messages),
          'rag_answer_jobs',(SELECT count(*) FROM rag_answer_jobs),
          'rag_answer_quota',(SELECT count(*) FROM rag_answer_quota_events),
          'rag_citations',(SELECT count(*) FROM rag_message_sources),
          'head',(SELECT version_num FROM alembic_version));"""
        return json.loads(self.compose("exec", "-T", "db", "psql", "-U", "rehearsal", "-d", "cardchemy_rehearsal", "-At", "-c", sql))

    def verify_rag_database(self, fixture: dict) -> dict:
        """Verify restored vector structure and principal-scoped exact retrieval."""
        subject = fixture_uuid(fixture, "subject")
        document = fixture_uuid(fixture, "document")
        content_revision = fixture_uuid(fixture, "content_revision")
        index_revision = fixture_uuid(fixture, "index_revision")
        chunk = fixture_uuid(fixture, "chunk")
        student = fixture_uuid(fixture, "student")
        other_student = fixture_uuid(fixture, "other_student")
        thread = fixture_uuid(fixture, "thread")
        question = fixture_uuid(fixture, "question")
        answer = fixture_uuid(fixture, "rag_answer")
        job = fixture_uuid(fixture, "answer_job")
        space_hash = embedding_space_hash(RAG_SPACE_IDENTITY)
        sql = f"""SELECT json_build_object(
          'vector_extension', coalesce((SELECT extversion = '0.8.6' FROM pg_extension WHERE extname='vector'), false),
          'embedding_schema', EXISTS(
            SELECT 1 FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
            WHERE c.relname='subject_document_chunks' AND a.attname='embedding'
              AND format_type(a.atttypid,a.atttypmod)='vector(1536)' AND NOT a.attisdropped),
          'embedding_indexes', (SELECT count(*)=4 FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid
            WHERE c.relname IN ('ix_knowledge_chunks_subject_revision','ix_knowledge_chunks_document',
              'ix_knowledge_chunks_content_page','uq_knowledge_chunks_local_id') AND i.indisvalid),
          'published_active_revision', EXISTS(
            SELECT 1 FROM subject_document_content_revisions c
            JOIN subject_document_index_revisions i ON i.content_revision_id=c.id
            JOIN subjects s ON s.id=c.subject_id
            WHERE c.id='{content_revision}'::uuid AND c.document_id='{document}'::uuid
              AND c.subject_id='{subject}'::uuid AND c.status='ready' AND c.is_active
              AND c.reviewed_at IS NOT NULL AND c.published_at IS NOT NULL
              AND i.id='{index_revision}'::uuid AND i.status='ready' AND i.is_active
              AND i.actual_chunk_count=1 AND i.actual_embedded_count=1
              AND i.embedding_space_hash='{space_hash}' AND s.active_embedding_space_hash=i.embedding_space_hash),
          'page_chunk_vector', EXISTS(
            SELECT 1 FROM subject_document_pages p JOIN subject_document_chunks c
              ON c.content_revision_id=p.content_revision_id AND c.page_number=p.page_number
            WHERE p.content_revision_id='{content_revision}'::uuid AND c.id='{chunk}'::uuid
              AND vector_dims(c.embedding)=1536 AND position('{RAG_QUOTE}' IN c.content)>0),
          'authorized_exact_retrieval', coalesce((
            SELECT eligible.id='{chunk}'::uuid FROM eligible_subject_knowledge_chunks eligible
            JOIN enrollments access ON access.subject_id=eligible.subject_id
            WHERE access.student_id='{student}'::uuid AND eligible.subject_id='{subject}'::uuid
              AND eligible.embedding_space_hash='{space_hash}'
            ORDER BY eligible.embedding <=> (SELECT embedding FROM subject_document_chunks WHERE id='{chunk}'::uuid), eligible.id
            LIMIT 1), false),
          'other_student_isolated', NOT EXISTS(
            SELECT 1 FROM eligible_subject_knowledge_chunks eligible
            JOIN enrollments access ON access.subject_id=eligible.subject_id
            WHERE access.student_id='{other_student}'::uuid AND eligible.subject_id='{subject}'::uuid),
          'private_conversation', EXISTS(
            SELECT 1 FROM rag_threads t
            JOIN rag_messages q ON q.thread_id=t.id AND q.id='{question}'::uuid AND q.role='user'
            JOIN rag_messages a ON a.thread_id=t.id AND a.id='{answer}'::uuid AND a.role='assistant'
            WHERE t.id='{thread}'::uuid AND t.user_id='{student}'::uuid AND t.subject_id='{subject}'::uuid
              AND a.content='{RAG_ANSWER}' AND a.outcome='answer' AND a.source_count=1),
          'completed_answer_job', EXISTS(
            SELECT 1 FROM rag_answer_jobs j JOIN auth_sessions auth
              ON auth.id=j.auth_session_id AND auth.user_id=j.user_id
            WHERE j.id='{job}'::uuid AND j.thread_id='{thread}'::uuid
              AND j.question_message_id='{question}'::uuid AND j.answer_message_id='{answer}'::uuid
              AND j.user_id='{student}'::uuid AND j.subject_id='{subject}'::uuid
              AND j.status='completed' AND j.provider_request_count=0 AND auth.revoked_at IS NULL),
          'grounded_citation', EXISTS(
            SELECT 1 FROM rag_message_sources s WHERE s.message_id='{answer}'::uuid
              AND s.chunk_id='{chunk}'::uuid AND s.document_id='{document}'::uuid
              AND s.content_revision_id='{content_revision}'::uuid AND s.index_revision_id='{index_revision}'::uuid
              AND s.citation_order=1 AND s.source_quote='{RAG_QUOTE}'));
        """
        checks = json.loads(self.compose(
            "exec", "-T", "db", "psql", "-U", "rehearsal", "-d", "cardchemy_rehearsal",
            "-At", "-v", "ON_ERROR_STOP=1", "-c", sql,
        ))
        required = {
            "vector_extension", "embedding_schema", "embedding_indexes",
            "published_active_revision", "page_chunk_vector", "authorized_exact_retrieval",
            "other_student_isolated", "private_conversation", "completed_answer_job",
            "grounded_citation",
        }
        if set(checks) != required or not all(checks.values()):
            raise RehearsalError("rag_recovery_contract")
        return checks

    def diagnose(self) -> None:
        """Emit lifecycle state only, without IDs/names/configuration/raw output."""
        if not self.started:
            return
        try:
            identifiers = self.compose("ps", "--all", "--quiet").decode().split()
            if any(not re.fullmatch(r"[a-f0-9]{12,64}", identity) for identity in identifiers):
                raise RehearsalError("diagnostic_identity_contract")
            if not identifiers:
                print(json.dumps({"rehearsal_failure_services": []}), flush=True)
                return
            details = json.loads(run(["docker", "inspect", *identifiers], cwd=self.checkout,
                                     environment=self.environment, stage="diagnostic_inspection", timeout=30))
            # Validate all ownership before reading even one container's logs.
            diagnostics = [container_diagnostic(detail, self.project) for detail in details]
            for detail, diagnostic in zip(details, diagnostics):
                if (not re.fullmatch(r"[a-f0-9]{64}", detail["Id"])
                        or not any(detail["Id"].startswith(identity) for identity in identifiers)):
                    raise RehearsalError("diagnostic_inspected_identity")
                logs = run(["docker", "logs", "--tail", "60", detail["Id"]], cwd=self.checkout,
                           environment=self.environment, stage="diagnostic_startup", timeout=30,
                           combined_output=True)
                # Parse private stdout/stderr but select only known JSON lifecycle
                # event names. Never forward fields or exception strings.
                events = []
                for line in logs[-128 * 1024:].splitlines():
                    try:
                        item = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(item, dict) and item.get("event") in STARTUP_EVENTS:
                        events.append(item["event"])
                diagnostic["startup_events"] = events[-10:]
                category = failure_category(logs)
                if category != "command_failed":
                    diagnostic["startup_failure_category"] = category
            print(json.dumps({"rehearsal_failure_services": diagnostics}, sort_keys=True), flush=True)
        except (RehearsalError, OSError, ValueError, KeyError, TypeError):
            print(json.dumps({"rehearsal_failure_diagnostic": "query_or_ownership_contract_failed"}), flush=True)

    def cleanup(self) -> None:
        if not self.started:
            return
        # Inspect before any removal: never trust a computed project name alone.
        identifiers = self.compose("ps", "--all", "--quiet").decode().split()
        if identifiers:
            details = json.loads(run(["docker", "inspect", *identifiers], cwd=self.checkout,
                                     environment=self.environment, stage="container_inspection"))
            for detail in details:
                labels = detail.get("Config", {}).get("Labels", {})
                if (labels.get("com.docker.compose.project") != self.project
                        or labels.get("com.docker.compose.service") not in SERVICES):
                    raise RehearsalError("container_ownership")
        # Stop/remove only project-owned containers. Never use down --volumes.
        self.compose("down", "--timeout", "45")
        name = f"{self.project}_postgres_data"
        names = run(["docker", "volume", "ls", "--format", "{{.Name}}"], cwd=self.checkout,
                    environment=self.environment, stage="volume_listing").decode().splitlines()
        if name not in names:
            return
        result = run(["docker", "volume", "inspect", name], cwd=self.checkout, environment=self.environment,
                     stage="volume_inspection")
        owned_volume(json.loads(result)[0], self.project)
        run(["docker", "volume", "rm", name], cwd=self.checkout, environment=self.environment, stage="volume_cleanup")


def ready(application: Application) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            application.request("GET", "/api/health/ready")
            return
        except (OSError, http.client.HTTPException, RehearsalError):
            time.sleep(0.5)
    raise RehearsalError("tls_readiness")


def generate_tls_certificate(workspace: Path, system: dict[str, str]) -> None:
    """Generate a strict-verification-compatible CA and separate server leaf."""
    run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-sha256", "-days", "1",
         "-subj", "/CN=Cardchemy disposable rehearsal CA",
         "-addext", "basicConstraints=critical,CA:TRUE",
         "-addext", "keyUsage=critical,keyCertSign,cRLSign",
         "-addext", "subjectKeyIdentifier=hash",
         "-addext", "authorityKeyIdentifier=keyid:always",
         "-keyout", str(workspace / "ca-key.pem"), "-out", str(workspace / "ca.pem")],
        cwd=workspace, environment=system, stage="local_certificate_ca")
    (workspace / "ca-key.pem").chmod(0o600)
    run(["openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes", "-sha256",
         "-subj", f"/CN={HOST}", "-keyout", str(workspace / "key.pem"),
         "-out", str(workspace / "server.csr")], cwd=workspace,
        environment=system, stage="local_certificate_request")
    extensions = workspace / "server-extensions.conf"
    extensions.write_text("basicConstraints=critical,CA:FALSE\n"
                          "keyUsage=critical,digitalSignature,keyEncipherment\n"
                          "extendedKeyUsage=serverAuth\n"
                          "subjectKeyIdentifier=hash\n"
                          "authorityKeyIdentifier=keyid:always\n"
                          f"subjectAltName=DNS:{HOST}\n", encoding="utf-8")
    run(["openssl", "x509", "-req", "-sha256", "-days", "1",
         "-in", str(workspace / "server.csr"), "-CA", str(workspace / "ca.pem"),
         "-CAkey", str(workspace / "ca-key.pem"), "-CAcreateserial",
         "-extfile", str(extensions), "-out", str(workspace / "certificate.pem")],
        cwd=workspace, environment=system, stage="local_certificate_issued")
    # Bind-mounted only into container UID101; owner-only host directory protects it.
    (workspace / "key.pem").chmod(0o644)


def tls_nginx_configuration() -> str:
    # Preserve the image's real health probe on a container-loopback-only HTTP
    # listener. The public fixture port is HTTPS; Application validates its CA.
    return ("server { listen 127.0.0.1:8080; server_name _; access_log off; error_log /dev/null; "
            "location = /healthz { default_type text/plain; return 200 \"ok\\n\"; } }\n"
            "server { listen 8443 ssl; server_name " + HOST + "; "
            "ssl_certificate /etc/nginx/rehearsal.crt; ssl_certificate_key /etc/nginx/rehearsal.key; "
            "access_log off; error_log /dev/null; add_header Strict-Transport-Security \"max-age=300\" always; "
            "location / { proxy_pass http://frontend:8080; proxy_set_header Host $http_host; "
            "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; proxy_set_header X-Forwarded-Proto https; } }\n")


def create_fixture(stack: Stack, app: Application, accounts: dict) -> dict:
    stack.compose("exec", "-T", "backend", "python", "-m", "app.cli", "create-instructor",
                  "--email", accounts["instructor_email"], input_data=(accounts["instructor_password"] + "\n").encode() * 2)
    instructor = app.login(accounts["instructor_email"], accounts["instructor_password"])
    subject, _ = app.request("POST", "/api/subjects", data={"name": "Disposable recovery rehearsal"}, token=instructor, expected=201)
    subject_id = subject["id"]
    card_set, _ = app.request("POST", f"/api/subjects/{subject_id}/sets", data={"title": "Recovery fixture"}, token=instructor, expected=201)
    set_id = card_set["id"]
    card, _ = app.request("POST", f"/api/flashcards/sets/{set_id}/cards", token=instructor, expected=201,
                          data={"front_content": "Which option is the rehearsal answer?", "back_content": "Alpha", "options": ["Alpha", "Beta", "Gamma", "Delta"]})
    app.request("PUT", f"/api/subjects/{subject_id}/sets/{set_id}", token=instructor, data={"is_published": True})
    invitation, _ = app.request("POST", f"/api/subjects/{subject_id}/invite", token=instructor, data={"expires_in_hours": 1})
    if invitation["delivery_queued"]:
        raise RehearsalError("unexpected_email")
    registered, _ = app.request("POST", "/api/auth/register", expected=201, data={"email": accounts["student_email"], "password": accounts["student_password"], "invite_token": invitation["token"]})
    student = app.login(accounts["student_email"], accounts["student_password"])
    key = "recovery-rehearsal-" + uuid4().hex
    answer = {"flashcard_id": card["id"], "selected_option_index": 0}
    result, _ = app.request("POST", "/api/study/progress", token=student, data=answer, extra_headers={"Idempotency-Key": key})
    if not result["is_correct"] or result["quality"] != 5:
        raise RehearsalError("study_answer")
    other_subject, _ = app.request(
        "POST", "/api/subjects", data={"name": "Isolation control subject"},
        token=instructor, expected=201,
    )
    other_invitation, _ = app.request(
        "POST", f"/api/subjects/{other_subject['id']}/invite", token=instructor,
        data={"expires_in_hours": 1},
    )
    if other_invitation["delivery_queued"]:
        raise RehearsalError("unexpected_email")
    other_registered, _ = app.request(
        "POST", "/api/auth/register", expected=201,
        data={"email": accounts["other_student_email"],
              "password": accounts["other_student_password"],
              "invite_token": other_invitation["token"]},
    )
    return {
        "subject": subject_id, "other_subject": other_subject["id"],
        "set": set_id, "card": card["id"], "key": key, "answer": answer, "result": result,
        "student": registered["id"], "other_student": other_registered["id"],
    }


def seed_rag_fixture(stack: Stack, fixture: dict) -> dict:
    """Seed provider-free synthetic RAG state through the database's real guards."""
    fixture = dict(fixture)
    for key in (
        "document", "content_revision", "index_revision", "chunk", "thread",
        "question", "rag_answer", "citation", "answer_job", "answer_quota",
    ):
        fixture[key] = str(uuid4())
    subject = fixture_uuid(fixture, "subject")
    student = fixture_uuid(fixture, "student")
    document = fixture_uuid(fixture, "document")
    content_revision = fixture_uuid(fixture, "content_revision")
    index_revision = fixture_uuid(fixture, "index_revision")
    chunk = fixture_uuid(fixture, "chunk")
    thread = fixture_uuid(fixture, "thread")
    question = fixture_uuid(fixture, "question")
    answer = fixture_uuid(fixture, "rag_answer")
    citation = fixture_uuid(fixture, "citation")
    job = fixture_uuid(fixture, "answer_job")
    quota = fixture_uuid(fixture, "answer_quota")
    (provider, base_url, model, space_revision, format_version, dimensions,
     representation, metric, document_task_mode, query_task_mode) = RAG_SPACE_IDENTITY
    space_hash = embedding_space_hash(RAG_SPACE_IDENTITY)
    page_chars = len(RAG_EVIDENCE)
    page_bytes = len(RAG_EVIDENCE.encode("utf-8"))
    section = "Recovery fixture"
    index_bytes = page_bytes + len(section.encode("utf-8")) + 6408
    sql = rf"""\set ON_ERROR_STOP on
BEGIN;
INSERT INTO rag_embedding_spaces(
  identity_hash,provider,base_url,model,space_revision,format_version,
  dimensions,representation,metric,document_task_mode,query_task_mode)
VALUES ('{space_hash}','{provider}','{base_url}','{model}','{space_revision}','{format_version}',
  {dimensions},'{representation}','{metric}','{document_task_mode}','{query_task_mode}');
INSERT INTO subject_documents(id,subject_id,uploader_id,title,source_pdf_name,source_sha256)
SELECT '{document}'::uuid,s.id,s.instructor_id,'Synthetic recovery knowledge',
  'synthetic-recovery.pdf',repeat('a',64) FROM subjects s WHERE s.id='{subject}'::uuid;
INSERT INTO subject_document_content_revisions(
  id,document_id,subject_id,uploader_id,revision_no,source_sha256,extraction_version,
  reserved_page_count,reserved_page_chars,reserved_page_bytes)
SELECT '{content_revision}'::uuid,'{document}'::uuid,s.id,s.instructor_id,1,repeat('a',64),
  'recovery_fixture_v1',1,{page_chars},{page_bytes} FROM subjects s WHERE s.id='{subject}'::uuid;
INSERT INTO subject_document_pages(
  content_revision_id,document_id,subject_id,uploader_id,page_number,content)
SELECT '{content_revision}'::uuid,'{document}'::uuid,s.id,s.instructor_id,1,'{RAG_EVIDENCE}'
  FROM subjects s WHERE s.id='{subject}'::uuid;
UPDATE subject_document_content_revisions SET status='pending_index',updated_at=now()
  WHERE id='{content_revision}'::uuid;
INSERT INTO subject_document_index_revisions(
  id,content_revision_id,document_id,subject_id,uploader_id,revision_no,chunker_version,
  embedding_provider,embedding_base_url,embedding_model,embedding_space_revision,
  embedding_format_version,embedding_dimensions,embedding_representation,embedding_metric,
  embedding_space_hash,document_task_mode,query_task_mode,reserved_chunk_count,reserved_index_bytes)
SELECT '{index_revision}'::uuid,'{content_revision}'::uuid,'{document}'::uuid,s.id,s.instructor_id,
  1,'recovery_fixture_v1','{provider}','{base_url}','{model}','{space_revision}','{format_version}',
  {dimensions},'{representation}','{metric}','{space_hash}','{document_task_mode}','{query_task_mode}',1,{index_bytes}
  FROM subjects s WHERE s.id='{subject}'::uuid;
INSERT INTO subject_document_chunks(
  id,index_revision_id,content_revision_id,document_id,subject_id,uploader_id,chunk_index,
  local_chunk_id,page_number,section,content,token_count,embedding_space_hash,embedding)
SELECT '{chunk}'::uuid,'{index_revision}'::uuid,'{content_revision}'::uuid,'{document}'::uuid,
  s.id,s.instructor_id,0,'chunk-0001-p1',1,'{section}','{RAG_EVIDENCE}',12,'{space_hash}',
  array_prepend(1::real,array_fill(0::real,ARRAY[1535]))::vector
  FROM subjects s WHERE s.id='{subject}'::uuid;
UPDATE subject_document_index_revisions SET status='ready',is_active=true,updated_at=now()
  WHERE id='{index_revision}'::uuid;
UPDATE subject_document_content_revisions SET status='ready',is_active=true,updated_at=now()
  WHERE id='{content_revision}'::uuid;
UPDATE subjects SET active_embedding_space_hash='{space_hash}' WHERE id='{subject}'::uuid;
UPDATE subject_document_content_revisions
  SET reviewed_by_id=(SELECT instructor_id FROM subjects WHERE id='{subject}'::uuid),
      reviewed_at=now(),published_at=now(),updated_at=now()
  WHERE id='{content_revision}'::uuid;
INSERT INTO rag_threads(id,user_id,subject_id,created_at,updated_at)
VALUES ('{thread}'::uuid,'{student}'::uuid,'{subject}'::uuid,now()-interval '3 minutes',now());
INSERT INTO rag_messages(
  id,thread_id,user_id,subject_id,role,outcome,content,source_count,
  corpus_revision,embedding_space_hash,created_at,expires_at)
VALUES ('{question}'::uuid,'{thread}'::uuid,'{student}'::uuid,'{subject}'::uuid,
  'user',NULL,'Why are leaves green?',0,NULL,NULL,now()-interval '2 minutes',now()+interval '1 day');
INSERT INTO rag_answer_jobs(
  id,thread_id,question_message_id,auth_session_id,user_id,subject_id,status,
  operation_key_hash,request_fingerprint,document_ids,corpus_revision,retrieval_policy,
  embedding_space_hash,ai_provider,ai_base_url,ai_model,deadline_at)
SELECT '{job}'::uuid,'{thread}'::uuid,'{question}'::uuid,a.id,'{student}'::uuid,'{subject}'::uuid,
  'queued',repeat('b',64),repeat('c',64),jsonb_build_array('{document}'::uuid),s.corpus_revision,
  'hybrid_exact_v1','{space_hash}','rehearsal_fixture','https://rehearsal.invalid/v1',
  'synthetic-grounded-answer',now()+interval '1 hour'
FROM subjects s JOIN LATERAL (
  SELECT id FROM auth_sessions WHERE user_id='{student}'::uuid AND revoked_at IS NULL
    AND expires_at>now() ORDER BY created_at DESC,id DESC LIMIT 1
) a ON true WHERE s.id='{subject}'::uuid;
UPDATE rag_answer_jobs SET status='running',attempt_count=1,worker_id='recovery-fixture',
  claim_token=repeat('d',64),heartbeat_at=now(),lease_expires_at=now()+interval '5 minutes',
  updated_at=now() WHERE id='{job}'::uuid;
INSERT INTO rag_messages(
  id,thread_id,user_id,subject_id,role,outcome,content,source_count,
  corpus_revision,embedding_space_hash,created_at,expires_at)
SELECT '{answer}'::uuid,'{thread}'::uuid,'{student}'::uuid,s.id,'assistant','answer',
  '{RAG_ANSWER}',1,s.corpus_revision,'{space_hash}',now()-interval '1 minute',now()+interval '1 day'
  FROM subjects s WHERE s.id='{subject}'::uuid;
INSERT INTO rag_message_sources(
  id,message_id,thread_id,user_id,subject_id,chunk_id,document_id,content_revision_id,
  index_revision_id,citation_order,claim_text,source_quote)
VALUES ('{citation}'::uuid,'{answer}'::uuid,'{thread}'::uuid,'{student}'::uuid,'{subject}'::uuid,
  '{chunk}'::uuid,'{document}'::uuid,'{content_revision}'::uuid,'{index_revision}'::uuid,1,
  '{RAG_ANSWER}','{RAG_QUOTE}');
UPDATE rag_answer_jobs SET status='completed',answer_message_id='{answer}'::uuid,
  completed_at=now(),updated_at=now() WHERE id='{job}'::uuid;
INSERT INTO rag_answer_quota_events(id,user_id,job_id,operation_key_hash,job_units)
VALUES ('{quota}'::uuid,'{student}'::uuid,'{job}'::uuid,repeat('b',64),1);
SET CONSTRAINTS ALL IMMEDIATE;
COMMIT;
"""
    stack.compose(
        "exec", "-T", "db", "psql", "-U", "rehearsal", "-d", "cardchemy_rehearsal",
        "-f", "-", input_data=sql.encode("utf-8"),
    )
    return fixture


def verify_application(app: Application, accounts: dict, fixture: dict) -> None:
    ready(app)
    _, headers = app.request("GET", "/")
    for name in ("content-security-policy", "x-frame-options", "x-content-type-options", "strict-transport-security"):
        if name not in headers:
            raise RehearsalError("edge_headers")
    app.request("GET", "/instructor/dashboard")  # SPA deep-link serving.
    app.request("GET", "/api/docs", expected=404)
    app.request("GET", "/api/openapi.json", expected=404)
    instructor = app.login(accounts["instructor_email"], accounts["instructor_password"])
    # The collection computes counts; the single-set response has default counts.
    card_sets, _ = app.request("GET", f"/api/subjects/{fixture['subject']}/sets", token=instructor)
    card_set = next((item for item in card_sets if item["id"] == fixture["set"]), None)
    if card_set is None or not card_set["is_published"] or card_set["approved_count"] != 1:
        raise RehearsalError("restored_instructor_read")
    student = app.login(accounts["student_email"], accounts["student_password"])
    session, _ = app.request("GET", f"/api/study/sets/{fixture['set']}/session?mode=review_all", token=student)
    if len(session["cards"]) != 1 or "back_content" in session["cards"][0]:
        raise RehearsalError("restored_student_read")
    progress, _ = app.request("GET", f"/api/study/sets/{fixture['set']}/progress", token=student)
    if progress["studied"] != 1 or progress["correct_count"] != 1 or progress["completion_percentage"] != 100:
        raise RehearsalError("restored_progress")
    result, _ = app.request("POST", "/api/study/progress", token=student, data=fixture["answer"], extra_headers={"Idempotency-Key": fixture["key"]})
    if result != fixture["result"]:
        raise RehearsalError("restored_receipt")
    app.request("POST", "/api/auth/logout", token=student)
    app.request("POST", "/api/auth/refresh", expected=401)


def verify_rag_application(app: Application, accounts: dict, fixture: dict) -> None:
    """Read the recovered provider-free RAG fixture through authorized APIs."""
    subject = fixture["subject"]
    thread = fixture["thread"]
    answer = fixture["rag_answer"]
    instructor = app.login(accounts["instructor_email"], accounts["instructor_password"])
    documents, _ = app.request(
        "GET", f"/api/subjects/{subject}/knowledge/documents", token=instructor,
    )
    document = next(
        (item for item in documents["documents"] if item["id"] == fixture["document"]), None
    )
    if document is None or document["content_revision"]["id"] != fixture["content_revision"] \
            or document["content_revision"]["status"] != "ready" \
            or not document["content_revision"]["is_active"] \
            or document["content_revision"]["reviewed_at"] is None \
            or document["content_revision"]["published_at"] is None \
            or document["index_revision"]["id"] != fixture["index_revision"] \
            or document["index_revision"]["status"] != "ready" \
            or not document["index_revision"]["is_active"] \
            or document["index_revision"]["chunk_count"] != 1 \
            or document["index_revision"]["embedded_count"] != 1:
        raise RehearsalError("restored_knowledge_read")
    own_threads, _ = app.request(
        "GET", f"/api/subjects/{subject}/rag/threads", token=instructor,
    )
    if own_threads != {"threads": []}:
        raise RehearsalError("rag_instructor_thread_privacy")
    app.request(
        "GET", f"/api/subjects/{subject}/rag/threads/{thread}",
        token=instructor, expected=404,
    )

    student = app.login(accounts["student_email"], accounts["student_password"])
    threads, _ = app.request(
        "GET", f"/api/subjects/{subject}/rag/threads", token=student,
    )
    if [item["id"] for item in threads["threads"]] != [thread]:
        raise RehearsalError("restored_rag_thread")
    history, _ = app.request(
        "GET", f"/api/subjects/{subject}/rag/threads/{thread}", token=student,
    )
    messages = history["messages"]
    if len(messages) != 2 or messages[0]["id"] != fixture["question"] \
            or messages[0]["role"] != "user" or messages[1]["id"] != answer \
            or messages[1]["role"] != "assistant" or messages[1]["hidden"] \
            or messages[1]["content"] != RAG_ANSWER or len(messages[1]["sources"]) != 1 \
            or messages[1]["sources"][0]["chunk_id"] != fixture["chunk"] \
            or messages[1]["sources"][0]["source_quote"] != RAG_QUOTE:
        raise RehearsalError("restored_rag_history")
    sources, _ = app.request(
        "GET", f"/api/subjects/{subject}/rag/threads/{thread}/messages/{answer}/sources",
        token=student,
    )
    if len(sources) != 1 or sources[0]["document_id"] != fixture["document"] \
            or sources[0]["content_revision_id"] != fixture["content_revision"] \
            or sources[0]["index_revision_id"] != fixture["index_revision"]:
        raise RehearsalError("restored_rag_citation")
    jobs, _ = app.request(
        "GET", f"/api/subjects/{subject}/rag/threads/{thread}/answer-jobs", token=student,
    )
    if len(jobs["jobs"]) != 1 or jobs["jobs"][0]["id"] != fixture["answer_job"] \
            or jobs["jobs"][0]["status"] != "completed" \
            or jobs["jobs"][0]["answer_message_id"] != answer \
            or jobs["jobs"][0]["provider_request_count"] != 0:
        raise RehearsalError("restored_rag_answer_job")
    app.request("POST", f"/api/subjects/{subject}/rag/threads", token=student, expected=503)
    app.request(
        "GET", f"/api/subjects/{subject}/knowledge/documents", token=student, expected=403,
    )

    other = app.login(accounts["other_student_email"], accounts["other_student_password"])
    app.request("GET", f"/api/subjects/{subject}/rag/threads", token=other, expected=403)
    app.request(
        "GET", f"/api/subjects/{subject}/rag/threads/{thread}", token=other, expected=403,
    )
    own_control, _ = app.request(
        "GET", f"/api/subjects/{fixture['other_subject']}/rag/threads", token=other,
    )
    if own_control != {"threads": []}:
        raise RehearsalError("rag_other_student_control")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, help="Save only the non-secret verification summary")
    args = parser.parse_args()
    if sys.platform != "linux":
        raise RehearsalError("linux_host_required")
    system = environment()
    status = run(["git", "status", "--porcelain"], cwd=ROOT, environment=system, stage="source_status")
    if status.strip():
        raise RehearsalError("clean_committed_source_required")
    source_sha = run(["git", "rev-parse", "HEAD"], cwd=ROOT, environment=system, stage="source_identity").decode().strip()
    if not re.fullmatch(r"[a-f0-9]{40}", source_sha):
        raise RehearsalError("source_identity")
    daemon = json.loads(run(["docker", "info", "--format", "{{json .}}"], cwd=ROOT, environment=system, stage="docker_host"))
    if daemon.get("OSType") != "linux" or daemon.get("Architecture") not in {"x86_64", "amd64"}:
        raise RehearsalError("linux_amd64_daemon_required")
    compose_version = run(["docker", "compose", "version", "--short"], cwd=ROOT,
                          environment=system, stage="compose_version").decode().strip()
    if not re.fullmatch(r"v?\d+\.\d+\.\d+", compose_version):
        raise RehearsalError("compose_version_contract")
    compose_version = compose_version.removeprefix("v")
    print(json.dumps({"rehearsal_compose_version": compose_version}), flush=True)
    suffix = uuid4().hex[:16]
    stacks: list[Stack] = []
    images: list[str] = []
    evidence = {"source_sha": source_sha, "host": "linux/amd64", "compose_version": compose_version,
                "utc": datetime.now(timezone.utc).isoformat(), "external_ai_calls": 0, "external_smtp_messages": 0}
    with tempfile.TemporaryDirectory(prefix=PREFIX) as directory:
        workspace = Path(directory).resolve()
        if workspace.parent != Path(tempfile.gettempdir()).resolve() or not workspace.name.startswith(PREFIX):
            raise RehearsalError("temporary_workspace_identity")
        workspace.chmod(0o700)
        checkout = workspace / "source"
        try:
            print("Rehearsal: cloning the exact committed source into private temporary storage.", flush=True)
            run(["git", "clone", "--no-local", "--quiet", str(ROOT), str(checkout)], cwd=workspace, environment=system, stage="clean_clone")
            run(["git", "checkout", "--detach", source_sha], cwd=checkout, environment=system, stage="exact_checkout")
            run([sys.executable, "scripts/bootstrap_env.py"], cwd=checkout, environment=system, stage="bootstrap")
            generated = dict(line.split("=", 1) for line in (checkout / ".env").read_text().splitlines() if line and not line.startswith("#") and "=" in line)
            shared = {key: generated[key] for key in ("POSTGRES_PASSWORD", "SECRET_KEY", "GENERATION_SOURCE_ENCRYPTION_KEY")}
            generate_tls_certificate(workspace, system)
            (workspace / "tls-nginx.conf").write_text(tls_nginx_configuration(), encoding="utf-8")
            backend_image, frontend_image = f"{PREFIX}{suffix}-backend:tested", f"{PREFIX}{suffix}-frontend:tested"
            images = [backend_image, frontend_image]
            source = Stack(checkout, workspace, f"{PREFIX}{suffix}-source", port(), backend_image, frontend_image, shared)
            stacks.append(source)
            source.validate()
            print("Rehearsal: building and starting the strict production profile with a loopback HTTPS edge.", flush=True)
            source.start(build=True)
            source.verify_heads()
            app = Application(source.tls_port, workspace / "ca.pem")
            ready(app)
            accounts = {
                "instructor_email": "rehearsal-instructor@example.com",
                "student_email": "rehearsal-student@example.com",
                "other_student_email": "rehearsal-isolation-student@example.com",
                "instructor_password": secrets.token_urlsafe(24),
                "student_password": secrets.token_urlsafe(24),
                "other_student_password": secrets.token_urlsafe(24),
            }
            fixture = create_fixture(source, app, accounts)
            fixture = seed_rag_fixture(source, fixture)
            verify_application(app, accounts, fixture)
            verify_rag_application(app, accounts, fixture)
            source.verify_rag_database(fixture)
            expected = source.counts()
            if {key: value for key, value in expected.items() if key != "head"} != {
                "users": 3, "subjects": 2, "sets": 1, "cards": 1, "enrollments": 2,
                "progress": 1, "receipts": 1, "outbox": 0, "embedding_spaces": 1,
                "knowledge_documents": 1, "knowledge_pages": 1, "knowledge_chunks": 1,
                "knowledge_vectors": 1, "rag_threads": 1, "rag_messages": 2,
                "rag_answer_jobs": 1, "rag_answer_quota": 1, "rag_citations": 1,
            }:
                raise RehearsalError("fixture_counts")
            source.compose(
                "stop", "--timeout", "45", "tls-edge", "frontend", "backend",
                "worker", "index-worker", "answer-worker", "email-worker",
            )
            print("Rehearsal: writers drained; creating and checksumming a custom-format backup.", flush=True)
            source.compose("exec", "-T", "db", "pg_dump", "-U", "rehearsal", "-d", "cardchemy_rehearsal", "--format=custom", "--no-owner", "--file=/tmp/rehearsal.dump")
            backup = workspace / "rehearsal.dump"
            source.compose("cp", "db:/tmp/rehearsal.dump", str(backup))
            backup.chmod(0o600)
            checksum = hashlib.sha256(backup.read_bytes()).hexdigest()
            remote = source.compose("exec", "-T", "db", "sha256sum", "/tmp/rehearsal.dump").decode().split()[0]
            if checksum != remote:
                raise RehearsalError("archive_checksum")
            restore_port = port()
            restore = Stack(checkout, workspace, f"{PREFIX}{suffix}-restore", restore_port, backend_image, frontend_image, shared)
            stacks.append(restore)
            restore.validate()
            restore.started = True
            restore.compose("up", "-d", "--no-build", "--wait", "db")
            empty = restore.compose("exec", "-T", "db", "psql", "-U", "rehearsal", "-d", "cardchemy_rehearsal", "-At", "-c", "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")
            if empty.strip() != b"0":
                raise RehearsalError("restore_requires_empty_database")
            restore.compose("cp", str(backup), "db:/tmp/rehearsal.dump")
            if hashlib.sha256(backup.read_bytes()).hexdigest() != checksum:
                raise RehearsalError("archive_changed")
            restored_checksum = restore.compose("exec", "-T", "db", "sha256sum", "/tmp/rehearsal.dump").decode().split()[0]
            if restored_checksum != checksum:
                raise RehearsalError("restore_archive_checksum")
            restore.compose("exec", "-T", "db", "pg_restore", "-U", "rehearsal", "-d", "cardchemy_rehearsal", "--exit-on-error", "--no-owner", "--no-privileges", "/tmp/rehearsal.dump")
            if restore.counts() != expected:
                raise RehearsalError("restored_counts")
            restore.verify_rag_database(fixture)
            print("Rehearsal: restored into a fresh volume; upgrading and verifying recovered application behavior.", flush=True)
            restore.compose("run", "--rm", "--no-deps", "migrate")
            restore.verify_heads()
            restore.start()
            restored_app = Application(restore_port, workspace / "ca.pem")
            verify_application(restored_app, accounts, fixture)
            verify_rag_application(restored_app, accounts, fixture)
            restore.verify_rag_database(fixture)
            if restore.counts() != expected:
                raise RehearsalError("recovered_counts")
            evidence.update({"alembic_head": expected["head"], "archive_sha256": checksum, "counts": expected,
                             "checks": ["fresh_clone_bootstrap", "strict_production_profile", "private_api_database", "tls_certificate_validation", "secure_refresh_cookie", "edge_headers_spa_closed_docs", "instructor_student_reads", "server_graded_study", "provider_free_rag_fixture", "pgvector_extension_schema_indexes", "published_active_knowledge_revision", "authorized_exact_retrieval", "private_rag_history_job_citation", "instructor_enrolled_other_student_isolation", "custom_backup_checksum", "separate_empty_volume_restore", "populated_rag_restore", "upgrade_heads_drift", "restored_answer_receipt_progress"]})
        except Exception:
            for stack in stacks:
                stack.diagnose()
            raise
        finally:
            cleanup_failures = []
            for stack in reversed(stacks):
                try:
                    stack.cleanup()
                except RehearsalError:
                    cleanup_failures.append("owned_stack_cleanup")
            available = run(["docker", "image", "ls", "--format", "{{.Repository}}:{{.Tag}}"], cwd=ROOT,
                            environment=system, stage="image_listing").decode().splitlines()
            for image in images:
                if image not in available:
                    continue
                details = json.loads(run(["docker", "image", "inspect", image], cwd=ROOT,
                                         environment=system, stage="image_inspection"))[0]
                if details.get("Config", {}).get("Labels", {}).get("cardchemy.rehearsal") != f"{PREFIX}{suffix}":
                    cleanup_failures.append("image_ownership")
                    continue
                try:
                    run(["docker", "image", "rm", image], cwd=ROOT, environment=system, stage="image_cleanup")
                except RehearsalError:
                    cleanup_failures.append("owned_image_cleanup")
            if cleanup_failures:
                raise RehearsalError("cleanup_incomplete")
            print("Rehearsal: owned disposable containers, volumes and image tags removed; temporary files scheduled for removal.", flush=True)
    evidence["cleanup"] = "passed"
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RehearsalError as failure:
        raise SystemExit(f"Production rehearsal failed at {failure}; no credential values were printed.") from None
    except (OSError, ValueError, KeyError, http.client.HTTPException):
        raise SystemExit("Production rehearsal failed at a closed verification contract; no credential values were printed.") from None
