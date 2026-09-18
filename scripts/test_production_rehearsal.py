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
from uuid import uuid4


ensure_no_legacy_configuration = runpy.run_path(
    str(Path(__file__).with_name("check_config_migration.py"))
)["ensure_no_legacy_configuration"]

ROOT = Path(__file__).resolve().parents[1]
HOST = "cards.rehearsal.test"
PREFIX = "cardchemy-rehearsal-"
SERVICES = {"db", "migrate", "backend", "worker", "email-worker", "frontend", "tls-edge"}
CONTAINER_STATUSES = {"created", "running", "paused", "restarting", "removing", "exited", "dead"}
HEALTH_STATUSES = {None, "starting", "healthy", "unhealthy"}
STARTUP_EVENTS = {"api_started", "api_stopped", "database_revision_verified", "worker_started", "process_failed"}
ALLOWED_ENVIRONMENT = {"PATH", "HOME", "TMP", "TEMP", "TMPDIR",
                       "SYSTEMROOT", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "PROGRAMDATA",
                       "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432"}


class RehearsalError(RuntimeError):
    """Only fixed diagnostic stages may leave the private workspace."""


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
        services = {name: {"image": backend_image, "build": {"labels": labels}} for name in ("migrate", "backend", "worker", "email-worker")}
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
        for name in ("db", "backend", "worker", "email-worker", "migrate"):
            if services[name].get("ports") or services[name].get("volumes", []) and name != "db":
                raise RehearsalError("production_private_services")
        for name in ("frontend", "tls-edge"):
            if any(mapping.get("host_ip") != "127.0.0.1" for mapping in services[name].get("ports", [])):
                raise RehearsalError("production_loopback")
        for name in ("backend", "worker", "email-worker", "migrate"):
            values = services[name]["environment"]
            if (values["ENVIRONMENT"] != "production" or values["DEBUG"] != "false"
                    or values["API_DOCS_ENABLED"] != "false" or values["REFRESH_COOKIE_SECURE"] != "true"):
                raise RehearsalError("production_settings")
        if any(key in services["backend"]["environment"] for key in (
            "FLASHCARD_AI_API_KEY", "RAG_AI_API_KEY", "RAG_EMBEDDING_API_KEY", "SMTP_PASSWORD"
        )):
            raise RehearsalError("credential_isolation")
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
        sql = "SELECT json_build_object('users',(SELECT count(*) FROM users),'subjects',(SELECT count(*) FROM subjects),'sets',(SELECT count(*) FROM flashcard_sets),'cards',(SELECT count(*) FROM flashcards),'enrollments',(SELECT count(*) FROM enrollments),'progress',(SELECT count(*) FROM study_progress),'receipts',(SELECT count(*) FROM study_answer_submissions),'outbox',(SELECT count(*) FROM email_outbox_messages),'head',(SELECT version_num FROM alembic_version));"
        return json.loads(self.compose("exec", "-T", "db", "psql", "-U", "rehearsal", "-d", "cardchemy_rehearsal", "-At", "-c", sql))

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
    app.request("POST", "/api/auth/register", expected=201, data={"email": accounts["student_email"], "password": accounts["student_password"], "invite_token": invitation["token"]})
    student = app.login(accounts["student_email"], accounts["student_password"])
    key = "recovery-rehearsal-" + uuid4().hex
    answer = {"flashcard_id": card["id"], "selected_option_index": 0}
    result, _ = app.request("POST", "/api/study/progress", token=student, data=answer, extra_headers={"Idempotency-Key": key})
    if not result["is_correct"] or result["quality"] != 5:
        raise RehearsalError("study_answer")
    return {"subject": subject_id, "set": set_id, "card": card["id"], "key": key, "answer": answer, "result": result}


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
            accounts = {"instructor_email": "rehearsal-instructor@example.com", "student_email": "rehearsal-student@example.com", "instructor_password": secrets.token_urlsafe(24), "student_password": secrets.token_urlsafe(24)}
            fixture = create_fixture(source, app, accounts)
            verify_application(app, accounts, fixture)
            expected = source.counts()
            if {key: value for key, value in expected.items() if key != "head"} != {"users": 2, "subjects": 1, "sets": 1, "cards": 1, "enrollments": 1, "progress": 1, "receipts": 1, "outbox": 0}:
                raise RehearsalError("fixture_counts")
            source.compose("stop", "--timeout", "45", "tls-edge", "frontend", "backend", "worker", "email-worker")
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
            print("Rehearsal: restored into a fresh volume; upgrading and verifying recovered application behavior.", flush=True)
            restore.compose("run", "--rm", "--no-deps", "migrate")
            restore.verify_heads()
            restore.start()
            verify_application(Application(restore_port, workspace / "ca.pem"), accounts, fixture)
            if restore.counts() != expected:
                raise RehearsalError("recovered_counts")
            evidence.update({"alembic_head": expected["head"], "archive_sha256": checksum, "counts": expected,
                             "checks": ["fresh_clone_bootstrap", "strict_production_profile", "private_api_database", "tls_certificate_validation", "secure_refresh_cookie", "edge_headers_spa_closed_docs", "instructor_student_reads", "server_graded_study", "custom_backup_checksum", "separate_empty_volume_restore", "upgrade_heads_drift", "restored_answer_receipt_progress"]})
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
