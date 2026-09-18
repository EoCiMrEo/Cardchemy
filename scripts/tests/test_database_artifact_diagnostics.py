"""Public scanner diagnostics are opt-in and bounded; other output stays private."""
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_database_artifact as artifact


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
