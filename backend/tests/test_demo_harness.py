import importlib
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import tarfile

import pytest


@pytest.fixture
def harness(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    return importlib.import_module("test_journey")


def test_demo_credentials_are_private_and_never_printed(harness, tmp_path, capsys):
    workspace = tmp_path / "private-demo"
    workspace.mkdir()
    harness.private_workspace(workspace)
    if os.name == "nt":
        permissions = subprocess.run(["icacls", str(workspace)], capture_output=True,
                                     text=True, check=True).stdout
        assert "(I)" not in permissions
        assert permissions.count("(F)") == 1
    else:
        assert workspace.stat().st_mode & 0o777 == 0o700

    class ExitedProcess:
        def poll(self):
            return 1

    with pytest.raises(RuntimeError, match="required demo process exited"):
        harness.hold_demo(workspace, "http://127.0.0.1:45678", "http://127.0.0.1:45679",
                          "private-instructor@example.com", "PRIVATE_INSTRUCTOR_PASSWORD",
                          "private-student@example.com", "PRIVATE_STUDENT_PASSWORD",
                          [ExitedProcess()], 1)
    output = capsys.readouterr().out
    assert "http://127.0.0.1:45678" in output
    for private_value in ("private-instructor@example.com", "private-student@example.com",
                          "PRIVATE_INSTRUCTOR_PASSWORD", "PRIVATE_STUDENT_PASSWORD"):
        assert private_value not in output
    credentials = workspace / "demo-sign-in.json"
    assert json.loads(credentials.read_text())["student"]["password"] == "PRIVATE_STUDENT_PASSWORD"
    if os.name != "nt":
        assert credentials.stat().st_mode & 0o777 == 0o600
    assert not (workspace / "frontend-build" / credentials.name).exists()


def test_demo_refuses_to_overwrite_an_existing_sign_in_file(harness, tmp_path):
    credentials = tmp_path / "demo-sign-in.json"
    credentials.write_text("PRESERVED_FILE")
    with pytest.raises(FileExistsError):
        harness.hold_demo(tmp_path, "http://127.0.0.1:45678", "http://127.0.0.1:45679",
                          "instructor@example.com", "password", "student@example.com", "password", [], 1)
    assert credentials.read_text() == "PRESERVED_FILE"


def test_failure_summary_rejects_raw_and_untrusted_log_fields(harness, tmp_path, capsys):
    records = [
        "PRIVATE_RAW_EXCEPTION_SENTINEL",
        json.dumps({"event": {"private": "PRIVATE_RAW_EXCEPTION_SENTINEL"}}),
        json.dumps({"event": "PRIVATE_DOCUMENT_SENTINEL"}),
        json.dumps({"event": "generation_failed", "error_code": "PRIVATE_EXCEPTION_SENTINEL",
                    "stage": ["PRIVATE_SOURCE_SENTINEL"], "message": "PRIVATE_RESPONSE_SENTINEL"}),
        json.dumps({"event": "generation_failed", "error_code": "pdf_resource_limit",
                    "stage": "extracting_text", "password": "PRIVATE_PASSWORD_SENTINEL"}),
    ]
    (tmp_path / "generation.log").write_text("\n".join(records), encoding="utf-8")
    harness.failure_summary(tmp_path, [])
    output = capsys.readouterr().out
    assert "PRIVATE_" not in output
    assert json.loads(output)["journey_failure"]["events"] == [
        {"process": "generation", "event": "generation_failed"},
        {"process": "generation", "event": "generation_failed", "error_code": "pdf_resource_limit",
         "stage": "extracting_text"},
    ]


def test_packaged_demo_requires_an_existing_local_image(harness, monkeypatch):
    calls = []

    def missing_image(*arguments):
        calls.append(arguments)
        raise RuntimeError("Docker command failed")

    monkeypatch.setattr(harness, "docker", missing_image)
    with pytest.raises(RuntimeError):
        harness.require_local_frontend_image("cardchemy-frontend:missing")
    assert calls == [("image", "inspect", "cardchemy-frontend:missing", "--format", "{{.Id}}")]


def test_packaged_demo_rejects_a_stale_configuration(harness, monkeypatch, tmp_path):
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend/nginx.conf").write_text("current configuration")
    monkeypatch.setattr(harness, "ROOT", tmp_path)
    image_id = "sha256:" + "a" * 64
    calls = []

    def inspect(*arguments):
        calls.append(arguments)
        return image_id if arguments[0] == "image" else "stale configuration"

    monkeypatch.setattr(harness, "docker", inspect)
    with pytest.raises(RuntimeError, match="packaged Nginx configuration differs"):
        harness.require_local_frontend_image("cardchemy-frontend:local")
    assert calls[1] == ("run", "--pull=never", "--rm", "--entrypoint", "cat", image_id,
                        "/etc/nginx/conf.d/default.conf")


def test_packaged_upstream_override_preserves_the_edge_contract(harness, tmp_path):
    original = (harness.ROOT / "frontend/nginx.conf").read_text(encoding="utf-8")
    target = tmp_path / "demo-nginx.conf"
    harness.packaged_frontend_config(target, 45678)
    modified = target.read_text(encoding="utf-8")
    assert modified.replace("server host.docker.internal:45678 resolve;",
                            "server backend:8000 resolve;") == original
    assert "proxy_cookie_path /auth /api/auth;" in modified
    assert "include /etc/nginx/security-headers.conf;" in modified
    assert "location ^~ /brand/" in modified
    assert "error_log /dev/null;" in modified


def test_packaged_demo_cannot_supply_docker_options_as_an_image(harness):
    with pytest.raises(harness.argparse.ArgumentTypeError):
        harness.local_image_reference("--privileged")
    with pytest.raises(harness.argparse.ArgumentTypeError):
        harness.local_image_reference("cardchemy-frontend:local --network host")


def test_packaged_demo_stops_when_a_container_exits(harness, monkeypatch, tmp_path):
    class RunningProcess:
        def poll(self):
            return None

    monkeypatch.setattr(harness, "containers_running", lambda _: False)
    with pytest.raises(RuntimeError, match="required demo container exited"):
        harness.hold_demo(tmp_path, "http://127.0.0.1:45678", "http://127.0.0.1:45679",
                          "instructor@example.com", "password", "student@example.com", "password",
                          [RunningProcess()], 1, ["cardchemy-journey-frontend-fixture"])


def test_packaged_config_copy_contains_only_root_owned_edge_config(harness, monkeypatch, tmp_path):
    configuration = tmp_path / "demo-nginx.conf"
    configuration.write_text("public upstream configuration", encoding="utf-8")
    (tmp_path / "demo-sign-in.json").write_text("PRIVATE_PASSWORD_SENTINEL")
    calls = []

    def copy(command, **arguments):
        calls.append((command, arguments))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(harness.subprocess, "run", copy)
    harness.copy_packaged_frontend_config(configuration, "cardchemy-journey-frontend-fixture")
    command, arguments = calls[0]
    assert command == ["docker", "cp", "-", "cardchemy-journey-frontend-fixture:/etc/nginx/conf.d"]
    assert b"PRIVATE_PASSWORD_SENTINEL" not in arguments["input"]
    with tarfile.open(fileobj=BytesIO(arguments["input"])) as copied:
        assert copied.getnames() == ["default.conf"]
        entry = copied.getmember("default.conf")
        assert (entry.uid, entry.gid, entry.mode) == (0, 0, 0o644)
        assert copied.extractfile(entry).read() == b"public upstream configuration"
