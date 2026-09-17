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
    for key in ("SECRET_KEY", "DATABASE_URL", "SMTP_PASSWORD", "AI_API_KEY", "GEMINI_API_KEY", "GITHUB_TOKEN"):
        monkeypatch.setenv(key, "not-a-real-secret")
    filtered = rehearsal.environment()
    assert not {"SECRET_KEY", "DATABASE_URL", "SMTP_PASSWORD", "AI_API_KEY", "GEMINI_API_KEY", "GITHUB_TOKEN"} & filtered.keys()


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
    (b"failed to solve: password=sentinel-never-expose", "image_build_failed"),
    (b"container unhealthy token=sentinel-never-expose", "service_unhealthy"),
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
