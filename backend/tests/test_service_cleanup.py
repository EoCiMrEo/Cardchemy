"""Fail-closed cleanup and credential-safe service verification output."""
from pathlib import Path
import runpy
import subprocess

import pytest


def test_tls_smtp_cleanup_refuses_success_when_an_owned_container_remains(monkeypatch):
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    namespace = runpy.run_path(str(scripts / "test_services.py"))
    owned = "cardchemy-smtp-tls-starttls-test-owned"
    commands = []

    def run(arguments, **_options):
        commands.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, stdout=f"unrelated-service\n{owned}\n", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(RuntimeError, match="could not be removed"):
        namespace["cleanup_containers"]([owned])
    assert commands == [
        ["docker", "rm", "-f", owned],
        ["docker", "ps", "-a", "--format", "{{.Names}}"],
    ]


@pytest.mark.parametrize("duration", ["1.23s", "64.23s (0:01:04)"])
def test_service_failure_output_preserves_exit_and_identity_without_private_details(monkeypatch, capsys, duration):
    script = Path(__file__).resolve().parents[2] / "scripts/test_services.py"
    namespace = runpy.run_path(str(script))
    command = ["python", "-m", "pytest", "--tb=short"]
    private = "database-password smtp-password recipient@example.com private-message-body"

    def run(arguments, **_options):
        return subprocess.CompletedProcess(
            arguments, 1,
            stdout=(f"fixture_repr=({private})\n"
                    f"FAILED tests/integration/test_smtp_tls.py::test_authenticated_tls_delivers_and_commits_once[{private}] - {private}\n"
                    f"1 failed, 11 passed in {duration}\n"),
            stderr=private,
        )

    monkeypatch.setattr(subprocess, "run", run)
    assert namespace["run_service_tests"](command, cwd=script.parent, environment={}) == 1
    output = capsys.readouterr().out
    assert f"1 failed, 11 passed in {duration}" in output
    assert "tests/integration/test_smtp_tls.py::test_authenticated_tls_delivers_and_commits_once" in output
    assert "withheld" in output
    for sensitive in private.split():
        assert sensitive not in output


def test_tls_smtp_cleanup_refuses_absence_when_daemon_inventory_fails(monkeypatch):
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    namespace = runpy.run_path(str(scripts / "test_services.py"))
    owned = "cardchemy-smtp-tls-implicit-test-owned"
    commands = []

    def run(arguments, **_options):
        commands.append(arguments)
        return subprocess.CompletedProcess(
            arguments, 1, stdout="", stderr="private daemon permission/error detail",
        )

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(RuntimeError, match="Docker command failed") as error:
        namespace["cleanup_containers"]([owned])
    assert "private" not in str(error.value)
    assert commands == [
        ["docker", "rm", "-f", owned],
        ["docker", "ps", "-a", "--format", "{{.Names}}"],
    ]
