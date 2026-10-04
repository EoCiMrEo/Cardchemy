"""Current diagnostic context boundaries with invented cases and no I/O."""
from __future__ import annotations

import asyncio
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prepare_private_navigation_v7 as prep


def test_default_cli_never_reads_missing_inputs_or_environment():
    result = subprocess.run([sys.executable, str(Path(prep.__file__)),
        "--stage1", "absent-file.json"], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == {"schema": prep.SCHEMA, "status": "unexecuted",
        "database_reads": 0, "database_writes": 0, "provider_calls": 0, "release_gate_passed": False}
    assert result.stderr == ""


def test_actual_execute_reaches_environment_guard_with_inherited_keyword_defaults():
    # Calling only args, as the isolated diagnostic does, must not fail with
    # a missing-keyword TypeError before the existing safety guard runs.
    with pytest.raises(prep.snapshot.Refusal, match="development_ask_off_required"):
        asyncio.run(prep.execute(SimpleNamespace(expected_database="invented"), environment={}))


@pytest.mark.parametrize("question,history,expected", [
    ("What is spectral index?", (("user", "What is unrelated concept?"),), "What is spectral index?"),
    ("How does it work?", (("user", "What is spectral index?"),), "How does it work? spectral index"),
    ("How does it work?", (("user", "What is spectral index?"), ("user", "Compare two methods?")), None),
    ("How does it work?", (("assistant", "spectral index"),), None),
])
def test_current_local_resolution_does_not_fall_back_to_older_or_assistant(question, history, expected):
    assert prep.local_resolution(question, history)[0] == expected


@pytest.mark.parametrize("question,previous,anchor", [
    ("What is spectral index?", "What is different subject?", None),
    ("How does it work?", "What is spectral index?", "spectral index"),
])
def test_diagnostic_binds_simulated_admission_and_preserves_previous_module(monkeypatch, question, previous, anchor):
    from app.services import source_visual_preparation_v3 as visual
    captured = {}
    async def prepare(db, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(request={"invented": True}, bindings=())
    monkeypatch.setattr(visual, "prepare_visual_sources_v3", prepare)
    case = {"case_id": "T01", "question": question, "previous_turn": previous}
    async def collect(db, *, runtime, **kwargs):
        prepared = await runtime.visual_prepare(db, question=question,
            settings=runtime.settings, retriever=object(), subject_id=UUID(int=2), selections=())
        return {"cases": [{"case_id": "T01", "request": prepared.request}]}, {}
    monkeypatch.setattr(prep.previous, "collect", collect)
    scope = SimpleNamespace(principal_id=str(UUID(int=1)), subject_id=str(UUID(int=2)),
        corpus_revision=3, embedding_space_hash="a" * 64)
    body, report = asyncio.run(prep.collect(object(), runtime=SimpleNamespace(settings=object()),
        scope=scope, gold={}, cases={"T01": case}, documents={}, embeddings={}))
    assert captured["question"] == question
    assert captured["preceding_question"] == (previous if anchor else None)
    assert (captured["anchor"].subject if captured["anchor"] else None) == anchor
    assert captured["snapshot"].current.content_sha256 == sha256(question.encode()).hexdigest()
    assert (captured["snapshot"].preceding is None) == (anchor is None)
    assert body["policy"] == prep.POLICY and body["contract"] == prep.CONTRACT
    assert body["admission_basis"] == "frozen_case_simulation_not_persisted_history"
    assert report["context_bound_requests"] == 1 and report["literal_context_requests"] == bool(anchor)
    assert prep.previous.POLICY == "related_knowledge_navigation_v6"
    assert prep.previous.CONTRACT == "visual_source_id_v2"
    assert prep.previous.collect is collect
    encoded = json.loads(prep.canonical(body))
    assert encoded["cases"][0]["question_context"]["admission"]["current"]["user_id"] == str(UUID(int=1))
