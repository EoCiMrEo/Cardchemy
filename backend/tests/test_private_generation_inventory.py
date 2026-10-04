"""Keyless privacy, scope and no-provider contracts for source inventory."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.ai.contracts import ExtractedDocument, ExtractedPage
from app.config import Settings
from scripts.evaluate_private_generation import EvaluationRefused, PrivateSource
from scripts import inventory_private_generation_sources as inventory


def settings(**overrides):
    values = {
        "environment": "test",
        "database_url": "sqlite+aiosqlite:///:memory:",
        "secret_key": "test-only-secret-key-with-adequate-entropy-1234567890",
        "generation_source_encryption_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "flashcard_ai_provider_enabled": True,
        "flashcard_ai_provider": "gemini",
        "flashcard_ai_model": "gemini-3.5-flash-lite",
        "flashcard_ai_thinking_level": "minimal",
        "flashcard_ai_api_key": "offline-test-key",
        "flashcard_ai_quota_bucket": "offline-test-bucket",
        "flashcard_ai_input_cost_per_million_usd": "0.30",
        "flashcard_ai_output_cost_per_million_usd": "2.50",
    }
    return Settings(_env_file=None, **(values | overrides))


def source(*, text: str = "Photosynthesis converts light into chemical energy. "):
    return PrivateSource(
        owner_id=uuid4(), subject_id=uuid4(), document_id=uuid4(),
        content_revision_id=uuid4(), index_revision_id=uuid4(),
        document=ExtractedDocument(pages=[ExtractedPage(page_number=1, text=text)]),
    )


class SelectDB:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return SimpleNamespace(all=lambda: self.rows)


async def test_document_selector_uses_owner_subject_publication_revision_and_active_space():
    selected = uuid4()
    db = SelectDB([(selected,)])
    assert await inventory.select_current_document_ids(
        db, owner_id=uuid4(), subject_id=uuid4(),
    ) == [selected]
    assert db.statement.is_select
    compiled = str(db.statement)
    for predicate in (
        "subjects.instructor_id", "subject_documents.uploader_id",
        "subject_document_content_revisions.uploader_id",
        "subject_document_content_revisions.is_active",
        "subject_document_content_revisions.reviewed_at IS NOT NULL",
        "subject_document_content_revisions.published_at IS NOT NULL",
        "subject_document_index_revisions.is_active",
        "subject_document_index_revisions.uploader_id",
        "subject_document_index_revisions.embedding_space_hash = subjects.active_embedding_space_hash",
    ):
        assert predicate in compiled
    assert db.statement._limit_clause.value == inventory.MAX_DOCUMENTS + 1


@pytest.mark.parametrize("count", [0, 4])
async def test_document_selector_refuses_empty_or_over_cap(count):
    db = SelectDB([(uuid4(),) for _ in range(count)])
    with pytest.raises(EvaluationRefused):
        await inventory.select_current_document_ids(
            db, owner_id=uuid4(), subject_id=uuid4(),
        )


def test_source_metrics_are_aggregate_only_and_do_not_establish_sparsity(monkeypatch):
    from app.ai import pipeline as pipeline_module

    def forbidden_provider(*_args, **_kwargs):
        raise AssertionError("A provider was constructed")

    monkeypatch.setattr(pipeline_module, "get_ai_provider", forbidden_provider)
    private_text = "Photosynthesis converts light into chemical energy. " * 15
    item = source(text=private_text)
    result = inventory.source_metrics(item, inventory.bounded_settings(settings()), slot=2)
    encoded = json.dumps(result)
    assert result["slot"] == 2
    assert result["canonical_page_count"] == 1
    assert result["prepared_chunk_count"] >= 1
    assert result["preflight_status"] in {"admissible", "budget_refused"}
    assert result["sparsity_unproven"] is True
    assert private_text not in encoded
    for private_id in (
        item.owner_id, item.subject_id, item.document_id,
        item.content_revision_id, item.index_revision_id,
    ):
        assert str(private_id) not in encoded


def test_empty_source_has_no_usable_text_and_never_claims_capacity():
    result = inventory.source_metrics(source(text=""), inventory.bounded_settings(settings()), slot=1)
    assert result["preflight_status"] == "no_usable_text"
    assert result["estimated_requests"] is None
    assert result["within_reference_caps"] is False
    assert result["sparsity_unproven"] is True


class FakeSession:
    def __init__(self):
        self.read_only_started = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def begin(self):
        return self

    async def execute(self, statement):
        assert str(statement) == "SET TRANSACTION READ ONLY"
        self.read_only_started = True


async def test_inspect_scans_only_selected_subject_with_ordinals_and_reauthorization(monkeypatch):
    owner_id, subject_id = uuid4(), uuid4()
    sources = [source() for _ in range(3)]
    document_ids = [item.document_id for item in sources]
    db = FakeSession()
    calls = []

    async def select_failed(session):
        assert session is db and session.read_only_started
        return owner_id, subject_id, document_ids[0], uuid4()

    async def select_documents(session, **kwargs):
        assert session is db and kwargs == {"owner_id": owner_id, "subject_id": subject_id}
        return document_ids

    async def load_pages(session, **kwargs):
        assert session is db and session.read_only_started
        assert kwargs["owner_id"] == owner_id and kwargs["subject_id"] == subject_id
        calls.append(("load", kwargs["document_id"]))
        return sources[document_ids.index(kwargs["document_id"])]

    async def identity(session, **kwargs):
        assert session is db and session.read_only_started
        calls.append(("reauthorize", kwargs["document_id"]))
        item = sources[document_ids.index(kwargs["document_id"])]
        return item.content_revision_id, item.index_revision_id

    monkeypatch.setattr(inventory, "async_session_maker", lambda: db)
    monkeypatch.setattr(inventory, "get_settings", settings)
    monkeypatch.setattr(inventory, "select_latest_failed_source", select_failed)
    monkeypatch.setattr(inventory, "select_current_document_ids", select_documents)
    monkeypatch.setattr(inventory, "load_authorized_pages", load_pages)
    monkeypatch.setattr(inventory, "current_source_identity", identity)

    result = await inventory.inspect()
    assert result["provider_requests"] == 0
    assert result["document_count"] == 3
    assert result["failed_20_source_slot"] == 1
    assert result["sparsity_unproven"] is True
    assert [item["slot"] for item in result["sources"]] == [1, 2, 3]
    assert [name for name, _ in calls] == ["load", "reauthorize"] * 3
    rendered = json.dumps(result)
    assert all(str(document_id) not in rendered for document_id in document_ids)


async def test_inspect_refuses_source_drift_without_partial_output(monkeypatch):
    owner_id, subject_id = uuid4(), uuid4()
    item = source()
    db = FakeSession()

    async def select_failed(_session):
        return owner_id, subject_id, item.document_id, uuid4()

    async def select_documents(_session, **_kwargs):
        return [item.document_id]

    async def load_pages(_session, **_kwargs):
        return item

    async def changed_identity(_session, **_kwargs):
        return uuid4(), uuid4()

    monkeypatch.setattr(inventory, "async_session_maker", lambda: db)
    monkeypatch.setattr(inventory, "get_settings", settings)
    monkeypatch.setattr(inventory, "select_latest_failed_source", select_failed)
    monkeypatch.setattr(inventory, "select_current_document_ids", select_documents)
    monkeypatch.setattr(inventory, "load_authorized_pages", load_pages)
    monkeypatch.setattr(inventory, "current_source_identity", changed_identity)
    with pytest.raises(EvaluationRefused):
        await inventory.inspect()


def test_main_suppresses_private_exception_and_any_printed_content(monkeypatch, capsys):
    async def broken_inspect():
        print("private source output")
        raise RuntimeError("private source exception")

    async def close():
        return None

    monkeypatch.setattr(inventory, "inspect", broken_inspect)
    monkeypatch.setattr(inventory, "close_database", close)
    assert inventory.main() == 1
    captured = capsys.readouterr()
    assert "private source" not in captured.out + captured.err
    result = json.loads(captured.out)
    assert result["provider_requests"] == 0
    assert result["sparsity_unproven"] is True


def test_main_success_emits_only_aggregate_json(monkeypatch, capsys):
    async def noisy_inspect():
        print("private source output")
        return {"provider_requests": 0, "sparsity_unproven": True}

    async def close():
        return None

    monkeypatch.setattr(inventory, "inspect", noisy_inspect)
    monkeypatch.setattr(inventory, "close_database", close)
    assert inventory.main() == 0
    captured = capsys.readouterr()
    assert "private source" not in captured.out + captured.err
    assert json.loads(captured.out) == {"provider_requests": 0, "sparsity_unproven": True}
