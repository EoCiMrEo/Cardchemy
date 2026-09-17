"""Real PostgreSQL initialization regression for the canonical Compose probe."""
from pathlib import Path
import runpy
import secrets
import subprocess
import tempfile
import time
from uuid import uuid4

import pytest
import yaml

pytestmark = [pytest.mark.postgres, pytest.mark.usefixtures("postgres_test_database_url")]


def test_compose_probe_waits_for_final_tcp_server_during_delayed_initialization():
    root = Path(__file__).resolve().parents[3]
    helpers = runpy.run_path(str(root / "scripts/test_services.py"))
    docker = helpers["docker"]
    cleanup_containers = helpers["cleanup_containers"]
    command = yaml.safe_load((root / "docker-compose.yml").read_text(encoding="utf-8"))["services"]["db"]["healthcheck"]["test"]
    assert command[0] == "CMD-SHELL" and len(command) == 2
    # This is the actual maintained health command, with only Compose's
    # documented escaping removed for execution in the container shell.
    health_command = command[1].replace("$$", "$")
    name = f"cardchemy-pg-startup-probe-{uuid4().hex[:12]}"
    owned = [name]

    def execute(*arguments):
        return subprocess.run(["docker", "exec", name, *arguments], capture_output=True)

    with tempfile.TemporaryDirectory(prefix="cardchemy-pg-startup-probe-") as temporary:
        directory = Path(temporary)
        environment_file = directory / "database.env"
        environment_file.write_text(
            "POSTGRES_USER=qa\nPOSTGRES_DB=startup_probe_test\n"
            f"POSTGRES_PASSWORD={secrets.token_urlsafe(36)}\n", encoding="utf-8",
        )
        environment_file.chmod(0o600)
        # Public executable-free init script. PostgreSQL creates the named DB
        # before sourcing this script, while its temporary server is socket-only.
        initialization = directory / "99-delayed-startup.sh"
        initialization.write_text(
            "#!/bin/sh\ntouch /tmp/cardchemy-startup-probe-ready\nsleep 20\n",
            encoding="utf-8", newline="\n",
        )
        initialization.chmod(0o644)
        try:
            docker(
                "run", "--rm", "-d", "--name", name, "--network", "none",
                "--env-file", str(environment_file),
                "--mount", f"type=bind,source={initialization},target=/docker-entrypoint-initdb.d/99-delayed-startup.sh,readonly",
                "postgres:16",
            )
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if execute("test", "-f", "/tmp/cardchemy-startup-probe-ready").returncode == 0:
                    break
                time.sleep(0.2)
            else:
                pytest.fail("Disposable PostgreSQL did not reach delayed initialization", pytrace=False)

            # Reproduce the previous false-positive: the temporary init server
            # answers socket pg_isready even though network clients cannot connect.
            assert execute("pg_isready", "-U", "qa", "-d", "startup_probe_test").returncode == 0
            assert execute("sh", "-c", health_command).returncode != 0

            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if execute("sh", "-c", health_command).returncode == 0:
                    break
                time.sleep(0.2)
            else:
                pytest.fail("Canonical Compose health command did not detect final TCP PostgreSQL", pytrace=False)
        finally:
            cleanup_containers(owned)
