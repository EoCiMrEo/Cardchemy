"""Public scanner diagnostics are opt-in and bounded; other output stays private."""
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_database_artifact as artifact


def test_posix_scanner_matches_host_archive_and_cache_ownership(monkeypatch):
    monkeypatch.setattr(artifact.os, "getuid", lambda: 1001, raising=False)
    monkeypatch.setattr(artifact.os, "getgid", lambda: 127, raising=False)
    options = artifact.scanner_filesystem_options()
    assert options[:2] == ["--user", "1001:127"]
    assert all("uid=1001,gid=127,mode=0700" in mount
               for mount in (options[3], options[5]))


def test_windows_desktop_has_explicit_fallback_user(monkeypatch):
    monkeypatch.delattr(artifact.os, "getuid", raising=False)
    monkeypatch.delattr(artifact.os, "getgid", raising=False)
    assert artifact.scanner_filesystem_options()[:2] == ["--user", "0:0"]


def test_private_command_failure_does_not_emit_output(monkeypatch, capsys):
    monkeypatch.setattr(artifact.subprocess, "run", lambda *a, **k:
                        subprocess.CompletedProcess([], 1, "private output", "private error"))
    with pytest.raises(RuntimeError, match="details withheld"):
        artifact.docker("inspect", label="Inspect")
    assert capsys.readouterr().out == ""


def test_public_scanner_failure_retains_bounded_diagnostics(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(artifact, "ROOT", tmp_path)
    monkeypatch.setattr(artifact.subprocess, "run", lambda *a, **k:
                        subprocess.CompletedProcess([], 1, "x" * 70000, "scanner error"))
    diagnostic = tmp_path / "public.log"
    with pytest.raises(RuntimeError, match="public scanner diagnostics retained"):
        artifact.docker("exec", label="Scan", diagnostic_file=diagnostic)
    assert len(diagnostic.read_text()) == 65536
    assert diagnostic.read_text().endswith("scanner error")
    assert len(capsys.readouterr().out) < 8300
