"""Run the real instructor/student browser journey without operator configuration.

Creates PostgreSQL and Mailpit containers with generated credentials and random
loopback ports; starts the actual API and workers, a private deterministic AI
provider, and Vite with process-only public configuration. Cleanup is automatic.
"""
from __future__ import annotations

from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from uuid import uuid4

from test_services import ROOT, docker, port, system_environment, wait_ready


def available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_http(url: str, process: subprocess.Popen) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("A disposable journey process exited before readiness")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:
            pass
        time.sleep(0.25)
    raise RuntimeError("Disposable journey HTTP service did not become ready")


def write_pdf(target: Path) -> None:
    from io import BytesIO
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 72 720 Td (Chlorophyll gives leaves their Green color. Photosynthesis converts light into chemical energy.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    target.write_bytes(output.getvalue())


def main() -> int:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required for the journey browser test")
    suffix = uuid4().hex[:12]
    names: list[str] = []
    processes: list[subprocess.Popen] = []
    handles = []
    with tempfile.TemporaryDirectory(prefix="cardchemy-journey-") as directory:
        workspace = Path(directory)
        password = secrets.token_urlsafe(36)
        env_file = workspace / "database.env"
        env_file.write_text(f"POSTGRES_USER=qa\nPOSTGRES_DB=journey_test\nPOSTGRES_PASSWORD={password}\n", encoding="utf-8")
        env_file.chmod(0o600)
        try:
            database = f"cardchemy-journey-db-{suffix}"
            names.append(database)
            docker("run", "--rm", "-d", "--name", database, "--env-file", str(env_file),
                   "-p", "127.0.0.1::5432", "postgres:16")
            wait_ready(database, ["pg_isready", "-U", "qa", "-d", "journey_test"])
            mailpit = f"cardchemy-journey-mailpit-{suffix}"
            names.append(mailpit)
            docker("run", "--rm", "-d", "--name", mailpit, "-p", "127.0.0.1::8025",
                   "-p", "127.0.0.1::1025", "-e", "MP_DISABLE_VERSION_CHECK=true",
                   "-e", "MP_MAX_MESSAGES=20", "axllent/mailpit:v1.31.1")
            wait_ready(mailpit, ["/mailpit", "readyz"])
            api_port, app_port = available_port(), available_port()
            while app_port == api_port:
                app_port = available_port()
            app_origin = f"http://127.0.0.1:{app_port}"
            mailpit_origin = f"http://127.0.0.1:{port(mailpit, 8025)}"
            instructor_email = f"journey-instructor-{suffix}@example.com"
            student_email = f"journey-student-{suffix}@example.com"
            instructor_password, student_password = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
            backend_environment = system_environment() | {
                "ENVIRONMENT": "test", "RUN_JOURNEY_TESTS": "1", "PYTHONUTF8": "1",
                "PYTHONPATH": str(ROOT / "backend"),
                "DATABASE_URL": f"postgresql+asyncpg://qa:{password}@127.0.0.1:{port(database, 5432)}/journey_test",
                "SECRET_KEY": secrets.token_urlsafe(48),
                "GENERATION_SOURCE_ENCRYPTION_KEY": secrets.token_urlsafe(32),
                "FRONTEND_BASE_URL": app_origin, "CORS_ORIGINS": app_origin,
                "AI_PROVIDER_ENABLED": "true", "AI_API_KEY": "journey-deterministic-no-network",
                "AI_MODEL": "journey-deterministic", "AI_REFILL_ROUNDS": "0",
                "AI_PROVIDER_MAX_RETRIES": "0", "AI_CONCURRENCY": "1",
                "AI_INPUT_COST_PER_MILLION_USD": "0.1", "AI_OUTPUT_COST_PER_MILLION_USD": "0.1",
                "GENERATION_WORKER_POLL_SECONDS": "0.1", "EMAIL_WORKER_POLL_SECONDS": "0.1",
                "SMTP_HOST": "127.0.0.1", "SMTP_PORT": str(port(mailpit, 1025)),
                "SMTP_FROM_EMAIL": "no-reply@example.com", "SMTP_STARTTLS": "false",
                "SMTP_IMPLICIT_TLS": "false", "REFRESH_COOKIE_SECURE": "false",
                "JOURNEY_INSTRUCTOR_EMAIL": instructor_email,
                "JOURNEY_INSTRUCTOR_PASSWORD": instructor_password,
            }
            runtime = ROOT / "backend/tests/support/journey_runtime.py"
            subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                           cwd=ROOT / "backend", env=backend_environment, check=True)
            # Seed output includes only the generated disposable address.
            subprocess.run([sys.executable, str(runtime), "seed"],
                           cwd=ROOT / "backend", env=backend_environment, check=True)

            def start(name: str, command: list[str], environment: dict[str, str], cwd: Path):
                handle = (workspace / f"{name}.log").open("w", encoding="utf-8")
                handles.append(handle)
                process = subprocess.Popen(command, cwd=cwd, env=environment,
                                           stdout=handle, stderr=subprocess.STDOUT)
                processes.append(process)
                return process

            api = start("api", [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                                "--port", str(api_port), "--no-access-log"], backend_environment, ROOT / "backend")
            wait_http(f"http://127.0.0.1:{api_port}/health/ready", api)
            start("generation", [sys.executable, str(runtime), "worker"], backend_environment, ROOT / "backend")
            start("email", [sys.executable, "-m", "app.email_worker"], backend_environment, ROOT / "backend")
            public_environment = system_environment() | {
                "JOURNEY_API_ORIGIN": f"http://127.0.0.1:{api_port}",
                "JOURNEY_CACHE_DIR": str(workspace / "vite-cache"),
            }
            frontend = start("frontend", [node, "node_modules/vite/bin/vite.js", "--config", "journey/vite.config.ts",
                                          "--host", "127.0.0.1", "--port", str(app_port), "--strictPort"],
                             public_environment, ROOT / "frontend")
            wait_http(app_origin, frontend)
            pdf_file = workspace / "leaf-facts.pdf"
            write_pdf(pdf_file)
            browser_environment = system_environment() | {
                "RUN_JOURNEY_TESTS": "1", "JOURNEY_APP_ORIGIN": app_origin,
                "JOURNEY_OUTPUT_DIR": str(workspace / "browser-artifacts"),
                "JOURNEY_MAILPIT_ORIGIN": mailpit_origin, "JOURNEY_PDF_FILE": str(pdf_file),
                "JOURNEY_INSTRUCTOR_EMAIL": instructor_email,
                "JOURNEY_INSTRUCTOR_PASSWORD": instructor_password,
                "JOURNEY_STUDENT_EMAIL": student_email,
                "JOURNEY_STUDENT_PASSWORD": student_password,
            }
            result = subprocess.run([node, "node_modules/@playwright/test/cli.js", "test",
                                     "--config", "playwright.journey.config.ts"],
                                    cwd=ROOT / "frontend", env=browser_environment)
            if result.returncode:
                return result.returncode
            if any(process.poll() is not None for process in processes):
                raise RuntimeError("A required application process exited during the journey")
            subprocess.run([sys.executable, str(runtime), "verify"],
                           cwd=ROOT / "backend", env=backend_environment, check=True)
            return 0
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
            for process in reversed(processes):
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            for handle in handles:
                handle.close()
            for name in reversed(names):
                subprocess.run(["docker", "rm", "-f", name], capture_output=True)
            print("Disposable journey processes, containers, data, fixture and generated credentials cleaned up.")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError):
        raise SystemExit("Journey regression command failed; no credential values were printed.")
