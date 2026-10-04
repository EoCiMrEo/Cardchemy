"""The mock executor cannot spend quota or overrun its physical-call bounds."""

import pytest

from scripts import execute_public_knowledge_disposable as executor


def test_disposable_guard_refuses_retained_or_paid_target(monkeypatch):
    monkeypatch.setenv("CARDCH_PUBLIC_HOLDOUT_MODE", "mock")
    monkeypatch.setenv("CARDCH_PUBLIC_HOLDOUT_RUN_ID", "test-run")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("RAG_ASK_ENABLED", "false")
    monkeypatch.setenv("RAG_AI_PROVIDER_ENABLED", "false")
    monkeypatch.setenv("FLASHCARD_AI_PROVIDER_ENABLED", "false")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://qa:unused@127.0.0.1:5432/cardchemy")
    with pytest.raises(executor.Refusal, match="database_target_invalid"):
        executor.require_disposable_target("mock")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://qa:unused@127.0.0.1:5432/public_holdout_test")
    with pytest.raises(executor.Refusal, match="database_target_invalid"):
        executor.require_disposable_target("paid")
    executor.require_disposable_target("mock")


@pytest.mark.asyncio
async def test_mock_gate_allows_only_two_document_batches_and_twelve_synthetic_queries():
    provider = executor.MockEmbeddingProvider()
    gate = executor.OneShotEmbeddingGate(provider, (2, 1))
    await gate.embed_documents(["first document chunk", "second document chunk"])
    await gate.embed_documents(["third document chunk"])
    with pytest.raises(executor.Refusal, match="document_call_envelope_exceeded"):
        await gate.embed_documents(["fourth document chunk"])
    for number in range(12):
        await gate.embed_query(f"Synthetic plumbing query {number}")
    with pytest.raises(executor.Refusal, match="query_call_envelope_exceeded"):
        await gate.embed_query("Synthetic plumbing query 13")
    assert (gate.document_calls, gate.query_calls) == (2, 12)
    assert provider.telemetry_snapshot().request_count == 14
    assert provider.telemetry_snapshot().retry_count == 0


@pytest.mark.asyncio
async def test_failed_provider_attempt_consumes_slot_without_retry():
    class UncertainProvider(executor.MockEmbeddingProvider):
        async def embed_documents(self, texts, *, titles=None):
            self.requests += 1
            raise TimeoutError("do not expose the raw provider failure")

    provider = UncertainProvider()
    gate = executor.OneShotEmbeddingGate(provider, (1, 1))
    with pytest.raises(executor.Refusal, match="provider_outcome_uncertain"):
        await gate.embed_documents(["synthetic"])
    assert gate.document_calls == 1
    assert provider.requests == 1
