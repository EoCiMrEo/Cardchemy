"""Synthetic, keyless contracts for the current-page snapshot boundary."""

from __future__ import annotations

import argparse
import asyncio
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from uuid import UUID

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
import bridge_private_source_gold_v4 as bridge
import snapshot_private_source_gold_v4 as snapshot


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False).encode("utf-8")).hexdigest()


def _bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _uuid(number: int) -> str:
    return str(UUID(int=number))


def _synthetic() -> tuple[dict, dict[tuple[str, int], dict]]:
    documents = {
        slot: {
            "document_id": _uuid(slot),
            "content_revision_id": _uuid(slot + 10),
            "index_revision_id": _uuid(slot + 20),
            "original_pdf_sha256": _digest(f"synthetic PDF {slot}"),
            "original_pdf_page_count": 20,
        } for slot in (1, 2, 3)
    }
    cases = []
    rows = {}
    for index in range(1, 13):
        slot = 1 + (index - 1) % 3
        document = documents[slot]
        page_text = f"Synthetic page {index}: exact canonical content."
        form = ("direct", "paraphrase", "followup")[(index - 1) // 4]
        cases.append({
            "case_id": f"T{index:02}", "form": form,
            "question": f"What does synthetic page {index} explain?",
            "previous_turn": "Which page is in view?" if form == "followup" else "",
            "document_slot": slot, "page_number": index, "page_useful": "Yes",
            "page_sha256": sha256(page_text.encode()).hexdigest(),
            "page_key": bridge._digest([document["document_id"], index]),
            **document,
        })
        rows[(document["document_id"], index)] = {
            **document, "page_number": index, "page_text": page_text,
            "original_pdf_byte_size": 120, "original_pdf_block_count": 1,
            "stored_block_count": 1, "stored_pdf_bytes": 120,
            "corpus_revision": 7, "active_embedding_space_hash": "e" * 64,
        }
    return {
        "schema": bridge.SCHEMA, "authored_input_sha256": "a" * 64,
        "reviewer_kind": "agent_self_review",
        "review_method": "authenticated_original_pdf_browser",
        "candidate_selection_seen": False,
        "frozen_at_utc": "2026-09-29T00:00:00Z",
        "scope": {"corpus_revision": 7, "embedding_space_hash": "e" * 64},
        "cases": cases,
    }, rows


class _Result:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class _FakeReadOnlyDb:
    def __init__(self, rows: dict[tuple[str, int], dict]):
        self.rows = rows
        self.calls: list[tuple[str, dict | None]] = []

    async def execute(self, statement, values=None):
        sql = str(statement)
        self.calls.append((sql, values))
        if sql.startswith("SET "):
            return _Result([])
        row = self.rows.get((values["document_id"], values["page_number"]))
        return _Result([] if row is None else [row])


def _arguments(directory: Path, digest: str, *, slates: list[dict] | None = None):
    stage1 = directory / "stage1-gold.json"
    packet, rows = _synthetic()
    stage1.write_bytes(_bytes(packet))
    slate_path = None
    slate_sha = None
    if slates is not None:
        slate_path = directory / "slates.json"
        slate_path.write_bytes(_bytes(slates))
        slate_sha = sha256(slate_path.read_bytes()).hexdigest()
    return argparse.Namespace(
        stage1=stage1, stage1_sha256=digest,
        slates=slate_path, slates_sha256=slate_sha,
        output=directory / "authorized-pages.json",
        principal_id=_uuid(100), subject_id=_uuid(101),
        corpus_revision=7, embedding_space_hash="e" * 64,
        expected_database="cardchemy",
    ), rows


def _environment(**overrides: str) -> dict[str, str]:
    return {
        "ENVIRONMENT": "development", "RAG_ASK_ENABLED": "false",
        "DATABASE_URL": "postgresql+asyncpg://reader:synthetic@db:5432/cardchemy",
        **overrides,
    }


def test_default_cli_preflight_ignores_credentials_and_private_input(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "snapshot_private_source_gold_v4.py"),
         "--stage1", str(tmp_path / "nonexistent.json")],
        env={**__import__("os").environ, "RAG_SOURCE_JUDGE_API_KEY": "synthetic_secret"},
        capture_output=True, text=True, check=True,
    )
    assert json.loads(result.stdout) == {
        "schema": snapshot.SCHEMA, "status": "preflight_unexecuted",
        "database_reads": 0, "database_writes": 0,
        "provider_requests": 0, "release_gate_passed": False,
    }
    assert "synthetic_secret" not in result.stdout + result.stderr


@pytest.mark.parametrize("change,code", [
    ({"ENVIRONMENT": "production"}, "development_ask_off_required"),
    ({"RAG_ASK_ENABLED": "true"}, "development_ask_off_required"),
    ({"RAG_SOURCE_JUDGE_API_KEY": "synthetic"}, "ai_credentials_present"),
    ({"GOOGLE_API_KEY": "synthetic"}, "ai_credentials_present"),
    ({"DATABASE_URL": "postgresql+asyncpg://reader:synthetic@prod.example:5432/cardchemy"},
     "database_target_invalid"),
    ({"DATABASE_URL": "postgresql+asyncpg://reader:synthetic@db:5432/other"},
     "database_target_invalid"),
])
def test_execute_runtime_guard_fails_closed(change, code):
    with pytest.raises(snapshot.Refusal, match=code):
        snapshot._guard_runtime(_environment(**change), "cardchemy")


def test_synthetic_snapshot_binds_gold_and_optional_slate_pages_without_provider(
    tmp_path, monkeypatch, capsys,
):
    packet, rows = _synthetic()
    digest = sha256(_bytes(packet)).hexdigest()
    monkeypatch.setattr(snapshot, "FROZEN_STAGE1_SHA256", digest)
    first = packet["cases"][0]
    extra_page = 13
    extra_text = "Synthetic candidate page outside the twelve gold pages."
    slates = [
        {"case_id": case["case_id"], "candidates": ([{
            "runtime_id": "S01", "document_id": first["document_id"],
            "page_number": extra_page, "start_offset": 0,
            "end_offset": len(extra_text),
        }] if case is first else [])}
        for case in packet["cases"]
    ]
    args, rows = _arguments(tmp_path, digest, slates=slates)
    rows[(first["document_id"], extra_page)] = {
        **rows[(first["document_id"], first["page_number"])],
        "page_number": extra_page, "page_text": extra_text,
    }
    db = _FakeReadOnlyDb(rows)
    report = asyncio.run(snapshot._execute(args, environment=_environment(),
                                           root=tmp_path, connect=db))
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
    assert report["gold_pages_bound"] == 12
    assert report["current_pages_written"] == 13
    assert report["provider_requests"] == report["database_writes"] == 0
    assert "Synthetic page" not in json.dumps(report)
    assert db.calls[0][0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    assert db.calls[1][0].startswith("SET LOCAL statement_timeout")
    assert len(db.calls) == 15
    page_sql = db.calls[2][0]
    for required in ("principal.role = 'INSTRUCTOR'", "principal.role = 'STUDENT'",
                     "content.published_at IS NOT NULL", "index_revision.status = 'ready'",
                     "eligible_subject_knowledge_chunks", "subject_document_pdfs"):
        assert required in page_sql
    output = json.loads(args.output.read_text(encoding="utf-8"))
    assert output["authorized_pages"][0]["page_text"].startswith("Synthetic page")
    assert len(output["authorized_pages"]) == 13
    assert any(page["page_text"] == extra_text for page in output["authorized_pages"])
    assert output["release_gate_passed"] is False


def test_refuses_changed_gold_before_writing(tmp_path, monkeypatch):
    packet, rows = _synthetic()
    digest = sha256(_bytes(packet)).hexdigest()
    monkeypatch.setattr(snapshot, "FROZEN_STAGE1_SHA256", digest)
    args, rows = _arguments(tmp_path, digest)
    first = packet["cases"][0]
    rows[(first["document_id"], first["page_number"])]["page_text"] = "changed"
    with pytest.raises(snapshot.Refusal, match="gold_page_changed"):
        asyncio.run(snapshot._execute(args, environment=_environment(),
                                      root=tmp_path, connect=_FakeReadOnlyDb(rows)))
    assert not args.output.exists()


@pytest.mark.parametrize("changed_field,changed_value,code", [
    ("content_revision_id", _uuid(999), "source_changed"),
    ("index_revision_id", _uuid(999), "source_changed"),
    ("original_pdf_sha256", "0" * 64, "source_changed"),
    ("active_embedding_space_hash", "0" * 64, "source_changed"),
    ("stored_block_count", 0, "source_unavailable"),
])
def test_refuses_drift_or_incomplete_pdf_archive_before_writing(
    tmp_path, monkeypatch, changed_field, changed_value, code,
):
    packet, rows = _synthetic()
    digest = sha256(_bytes(packet)).hexdigest()
    monkeypatch.setattr(snapshot, "FROZEN_STAGE1_SHA256", digest)
    args, rows = _arguments(tmp_path, digest)
    first = packet["cases"][0]
    rows[(first["document_id"], first["page_number"])][changed_field] = changed_value
    with pytest.raises(snapshot.Refusal, match=code):
        asyncio.run(snapshot._execute(args, environment=_environment(),
                                      root=tmp_path, connect=_FakeReadOnlyDb(rows)))
    assert not args.output.exists()


def test_wrong_frozen_sha_is_rejected_before_private_read_or_database(tmp_path):
    args = argparse.Namespace(
        stage1=tmp_path / "missing.json", stage1_sha256="0" * 64,
        slates=None, slates_sha256=None, output=tmp_path / "out.json",
        principal_id=_uuid(100), subject_id=_uuid(101), corpus_revision=7,
        embedding_space_hash="e" * 64, expected_database="cardchemy",
    )
    with pytest.raises(snapshot.Refusal, match="invalid_arguments"):
        asyncio.run(snapshot._execute(args, environment=_environment(),
                                      root=tmp_path, connect=_FakeReadOnlyDb({})))


def test_existing_output_is_preserved(tmp_path, monkeypatch):
    packet, rows = _synthetic()
    digest = sha256(_bytes(packet)).hexdigest()
    monkeypatch.setattr(snapshot, "FROZEN_STAGE1_SHA256", digest)
    args, rows = _arguments(tmp_path, digest)
    args.output.write_bytes(b"existing")
    with pytest.raises(snapshot.Refusal, match="output_exists"):
        asyncio.run(snapshot._execute(args, environment=_environment(),
                                      root=tmp_path, connect=_FakeReadOnlyDb(rows)))
    assert args.output.read_bytes() == b"existing"


def test_slate_cannot_request_an_unfrozen_document(tmp_path, monkeypatch):
    packet, _ = _synthetic()
    digest = sha256(_bytes(packet)).hexdigest()
    monkeypatch.setattr(snapshot, "FROZEN_STAGE1_SHA256", digest)
    slates = [{"case_id": case["case_id"], "candidates": []}
              for case in packet["cases"]]
    slates[0]["candidates"] = [{
        "runtime_id": "S01", "document_id": _uuid(999), "page_number": 1,
        "start_offset": 0, "end_offset": 3,
    }]
    args, rows = _arguments(tmp_path, digest, slates=slates)
    db = _FakeReadOnlyDb(rows)
    with pytest.raises(snapshot.Refusal, match="slates_invalid"):
        asyncio.run(snapshot._execute(args, environment=_environment(),
                                      root=tmp_path, connect=db))
    assert db.calls == []
