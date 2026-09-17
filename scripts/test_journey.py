"""Run the real instructor/student browser journey without operator configuration.

Creates PostgreSQL and Mailpit containers with generated credentials and random
loopback ports; starts the actual API and workers, a private deterministic AI
provider, and Vite with process-only public configuration. Cleanup is automatic.
"""
from __future__ import annotations

import argparse
import csv
from io import BytesIO
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.request import urlopen
from uuid import uuid4

from test_services import ROOT, cleanup_containers, docker, port, system_environment, wait_postgres_ready, wait_ready


class PackagedDemoUnavailable(RuntimeError):
    """A fixed non-secret setup stage, without Docker or HTTP exception text."""

    def __init__(self, stage: str):
        self.stage = stage if stage in {"container_start", "container_health", "loopback_api"} else "setup"
        super().__init__(self.stage)


def private_workspace(directory: Path) -> None:
    """Restrict temporary logs, fixture and credentials before writing them."""
    directory.chmod(0o700)
    if os.name == "nt":
        identity = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
                                  capture_output=True, text=True, check=True)
        sid = next(csv.reader([identity.stdout.strip()]))[1]
        if not sid.startswith("S-1-") or any(not item.isdigit() for item in sid[2:].split("-")):
            raise RuntimeError("Private journey permissions could not be established")
        subprocess.run(["icacls", str(directory), "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)(F)"],
                       capture_output=True, check=True)
        # Python 3.13's secure Windows mkdir can add these explicit entries;
        # remove them too so only the current user's SID remains in the DACL.
        others = [f"*{principal}" for principal in ("S-1-5-18", "S-1-5-32-544", "S-1-3-4")
                  if principal != sid]
        subprocess.run(["icacls", str(directory), "/remove:g", *others],
                       capture_output=True, check=True)


def demo_minutes(value: str) -> int:
    try:
        minutes = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Demo minutes must be an integer from 1 to 60") from None
    if not 1 <= minutes <= 60:
        raise argparse.ArgumentTypeError("Demo minutes must be an integer from 1 to 60")
    return minutes


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true",
                        help="Keep the verified disposable application available for local exploration")
    parser.add_argument("--demo-minutes", type=demo_minutes,
                        help="Stop the interactive demo after 1-60 minutes (default: 15)")
    parser.add_argument("--demo-frontend-image", type=local_image_reference,
                        help="Serve an already-built local Nginx frontend image for packaged-candidate checks")
    arguments = parser.parse_args()
    if arguments.demo_minutes is not None and not arguments.demo:
        parser.error("--demo-minutes requires --demo")
    if arguments.demo_frontend_image is not None and not arguments.demo:
        parser.error("--demo-frontend-image requires --demo")
    return arguments


def local_image_reference(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/:@-]{0,511}", value):
        raise argparse.ArgumentTypeError("Use a single local Docker image reference")
    return value


def require_local_frontend_image(reference: str) -> str:
    image_id = docker("image", "inspect", reference, "--format", "{{.Id}}")
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image_id):
        raise RuntimeError("The local frontend image could not be pinned")
    packaged = docker("run", "--pull=never", "--rm", "--entrypoint", "cat", image_id,
                      "/etc/nginx/conf.d/default.conf")
    if packaged != (ROOT / "frontend/nginx.conf").read_text(encoding="utf-8").strip():
        raise RuntimeError("Rebuild the local frontend image: its packaged Nginx configuration differs")
    return image_id


def packaged_frontend_config(target: Path, api_port: int) -> None:
    if type(api_port) is not int or not 1 <= api_port <= 65535:
        raise RuntimeError("Invalid disposable API port")
    original = (ROOT / "frontend/nginx.conf").read_text(encoding="utf-8")
    upstream = "server backend:8000 resolve;"
    if original.count(upstream) != 1:
        raise RuntimeError("The packaged frontend upstream contract changed")
    target.write_text(original.replace(upstream, f"server host.docker.internal:{api_port} resolve;"),
                      encoding="utf-8")


def copy_packaged_frontend_config(configuration: Path, container: str) -> None:
    """Copy only the public edge config with its original root-owned file mode."""
    content = configuration.read_bytes()
    archive = BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as output:
        entry = tarfile.TarInfo("default.conf")
        entry.size = len(content)
        entry.mode = 0o644
        entry.uid = entry.gid = 0
        entry.uname = entry.gname = "root"
        output.addfile(entry, BytesIO(content))
    result = subprocess.run(["docker", "cp", "-", f"{container}:/etc/nginx/conf.d"],
                            input=archive.getvalue(), capture_output=True)
    if result.returncode:
        raise RuntimeError("The disposable frontend configuration copy failed")


def containers_running(names: list[str]) -> bool:
    states = docker("inspect", "--format", "{{.State.Running}}", *names).splitlines()
    return len(states) == len(names) and all(state == "true" for state in states)


def hold_demo(workspace: Path, app_origin: str, mailpit_origin: str,
              instructor_email: str, instructor_password: str,
              student_email: str, student_password: str,
              processes: list[subprocess.Popen], minutes: int,
              containers: list[str] | None = None) -> None:
    credentials = workspace / "demo-sign-in.json"
    # Exclusive creation inside the owner-only directory; never print values.
    with os.fdopen(os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                   "w", encoding="utf-8") as output:
        json.dump({"app_url": app_origin, "mailpit_url": mailpit_origin,
                   "instructor": {"email": instructor_email, "password": instructor_password},
                   "student": {"email": student_email, "password": student_password}}, output, indent=2)
        output.write("\n")
    print(f"Verified no-quota demo: {app_origin}", flush=True)
    print(f"Private sign-in file: {credentials}", flush=True)
    print(f"The demo stops and removes its data after {minutes} minute(s), or when you press Ctrl+C.", flush=True)
    deadline = time.monotonic() + minutes * 60
    next_container_check = 0.0
    while time.monotonic() < deadline:
        if any(process.poll() is not None for process in processes):
            raise RuntimeError("A required demo process exited")
        if containers and time.monotonic() >= next_container_check:
            if not containers_running(containers):
                raise RuntimeError("A required demo container exited")
            next_container_check = time.monotonic() + 5
        time.sleep(min(0.5, max(0, deadline - time.monotonic())))


def failure_summary(workspace: Path, processes: list[subprocess.Popen]) -> None:
    """Report closed diagnostic fields, never raw logs or private artifacts."""
    sys.path.append(str(ROOT / "backend"))
    from app.observability import ENUM_FIELDS, EVENTS, SAFE_ERROR_CODES

    events = []
    for name in ("api", "generation", "email", "frontend"):
        log_file = workspace / f"{name}.log"
        if not log_file.exists():
            continue
        with log_file.open(encoding="utf-8", errors="replace") as output:
            lines = output.read(1024 * 1024).splitlines()[-70:]
        for line in lines:
            try:
                value = json.loads(line)
            except (ValueError, TypeError):
                continue
            if (not isinstance(value, dict) or not isinstance(value.get("event"), str)
                    or value["event"] not in EVENTS):
                continue
            if value["event"] in {"request_completed", "external_log"}:
                continue
            event = {"process": name, "event": value["event"]}
            if isinstance(value.get("error_code"), str) and value["error_code"] in SAFE_ERROR_CODES:
                event["error_code"] = value["error_code"]
            if isinstance(value.get("stage"), str) and value["stage"] in ENUM_FIELDS["stage"]:
                event["stage"] = value["stage"]
            events.append(event)
    print(json.dumps({"journey_failure": {"process_exit_codes": [process.poll() for process in processes],
                                         "events": events[-20:]}}, ensure_ascii=True), flush=True)


def available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_http(url: str, process: subprocess.Popen, container: str | None = None) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("A disposable journey process exited before readiness")
        if container is not None and not containers_running([container]):
            raise RuntimeError("The disposable frontend container exited before readiness")
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
    arguments = parse_arguments()
    # Inspect before creating services; pin the existing local image and never pull.
    frontend_image = (require_local_frontend_image(arguments.demo_frontend_image)
                      if arguments.demo_frontend_image else None)
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required for the journey browser test")
    suffix = uuid4().hex[:12]
    names: list[str] = []
    networks: list[str] = []
    processes: list[subprocess.Popen] = []
    handles = []
    with tempfile.TemporaryDirectory(prefix="cardchemy-journey-") as directory:
        workspace = Path(directory)
        private_workspace(workspace)
        password = secrets.token_urlsafe(36)
        env_file = workspace / "database.env"
        env_file.write_text(f"POSTGRES_USER=qa\nPOSTGRES_DB=journey_test\nPOSTGRES_PASSWORD={password}\n", encoding="utf-8")
        env_file.chmod(0o600)
        try:
            database = f"cardchemy-journey-db-{suffix}"
            names.append(database)
            docker("run", "--rm", "-d", "--name", database, "--env-file", str(env_file),
                   "-p", "127.0.0.1::5432", "postgres:16")
            database_port = port(database, 5432)
            wait_postgres_ready(database_port, password, "journey_test")
            mailpit = f"cardchemy-journey-mailpit-{suffix}"
            names.append(mailpit)
            docker("run", "--rm", "-d", "--name", mailpit, "-p", "127.0.0.1::8025",
                   "-p", "127.0.0.1::1025", "-e", "MP_DISABLE_VERSION_CHECK=true",
                   "-e", "MP_MAX_MESSAGES=20", "axllent/mailpit:v1.31.1")
            wait_ready(mailpit, ["/mailpit", "readyz"])
            api_port, app_port = available_port(), available_port()
            while app_port == api_port:
                app_port = available_port()
            frontend_container = None
            if frontend_image:
                frontend_container = f"cardchemy-journey-frontend-{suffix}"
                network = f"cardchemy-journey-network-{suffix}"
                configuration = workspace / "demo-nginx.conf"
                packaged_frontend_config(configuration, api_port)
                names.append(frontend_container)
                networks.append(network)
                try:
                    # A user-defined network supplies the shipped 127.0.0.11
                    # resolver contract. Docker assigns the loopback host port.
                    docker("network", "create", network)
                    docker("create", "--pull=never", "--name", frontend_container,
                           "--network", network, "-p", "127.0.0.1::8080", frontend_image)
                    # Copy only this non-secret config using the owner's CLI;
                    # never mount or relax access to the credential directory.
                    copy_packaged_frontend_config(configuration, frontend_container)
                    docker("start", frontend_container)
                    app_port = port(frontend_container, 8080)
                except RuntimeError:
                    raise PackagedDemoUnavailable("container_start") from None
            app_origin = f"http://127.0.0.1:{app_port}"
            mailpit_origin = f"http://127.0.0.1:{port(mailpit, 8025)}"
            instructor_email = f"journey-instructor-{suffix}@example.com"
            student_email = f"journey-student-{suffix}@example.com"
            instructor_password, student_password = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
            backend_environment = system_environment() | {
                "ENVIRONMENT": "test", "RUN_JOURNEY_TESTS": "1", "PYTHONUTF8": "1",
                "PYTHONPATH": str(ROOT / "backend"),
                "DATABASE_URL": f"postgresql+asyncpg://qa:{password}@127.0.0.1:{database_port}/journey_test",
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
            frontend_command = [node, "node_modules/vite/bin/vite.js"]
            if frontend_image:
                try:
                    wait_http(f"{app_origin}/healthz", api, frontend_container)
                except RuntimeError:
                    raise PackagedDemoUnavailable("container_health") from None
                try:
                    wait_http(f"{app_origin}/api/health/ready", api, frontend_container)
                except RuntimeError:
                    raise PackagedDemoUnavailable("loopback_api") from None
                print(f"Packaged frontend image: {frontend_image}", flush=True)
            elif arguments.demo:
                # Build into private temporary storage; do not replace frontend/dist
                # or use Vite's normal configuration loader/operator root .env.
                build_directory = workspace / "frontend-build"
                public_environment["JOURNEY_BUILD_DIR"] = str(build_directory)
                subprocess.run([*frontend_command, "build", "--config", "journey/vite.config.ts",
                                "--outDir", str(build_directory), "--emptyOutDir"],
                               cwd=ROOT / "frontend", env=public_environment, check=True)
                frontend_command.append("preview")
            if not frontend_image:
                frontend = start("frontend", [*frontend_command, "--config", "journey/vite.config.ts",
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
                                    cwd=ROOT / "frontend", env=browser_environment,
                                    capture_output=True, text=True)
            if result.returncode:
                print("Browser journey contract failed; private browser diagnostics omitted.")
                failure_summary(workspace, processes)
                return result.returncode
            print("Browser journey contract passed.")
            if any(process.poll() is not None for process in processes):
                raise RuntimeError("A required application process exited during the journey")
            if frontend_container is not None and not containers_running(names):
                raise RuntimeError("A required packaged demo container exited during the journey")
            subprocess.run([sys.executable, str(runtime), "verify"],
                           cwd=ROOT / "backend", env=backend_environment, check=True)
            if arguments.demo:
                hold_demo(workspace, app_origin, mailpit_origin,
                          instructor_email, instructor_password, student_email, student_password,
                          processes, arguments.demo_minutes or 15,
                          names if frontend_container is not None else None)
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
            cleanup_containers(names)
            for name in reversed(networks):
                subprocess.run(["docker", "network", "rm", name], capture_output=True)
            remaining_networks = set(docker("network", "ls", "--format", "{{.Name}}").splitlines())
            if remaining_networks.intersection(networks):
                raise RuntimeError("Owned disposable journey networks could not be removed")
            print("Disposable journey processes, containers, data, fixture and generated credentials cleaned up.")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)
    except PackagedDemoUnavailable as failure:
        raise SystemExit(f"Packaged demo setup failed at {failure.stage}; no credential values were printed.") from None
    except (RuntimeError, OSError, subprocess.CalledProcessError):
        raise SystemExit("Journey regression command failed; no credential values were printed.")
