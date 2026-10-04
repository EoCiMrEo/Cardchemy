"""Current v8 cannot replay v5/v6/v7 or under-account its completion budget."""
from types import SimpleNamespace

import pytest

from app.ai.providers.source_visual import VisualJudgeResponse
from app.models.knowledge import embedding_space_hash
from app.workers import rag_answer as module
from tests.test_source_visual_runtime_profile import settings
from tests.test_visual_source_completion_migration import current_sample
from tests.test_visual_source_judgment_policy_migration import sample
from tests.test_visual_source_judgment_worker import run, setup, verdict


def test_current_profile_requires_v8_v5_and_exact_thinking_inclusive_budget(monkeypatch):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", "related_knowledge_navigation_v8")
    configured = settings()
    worker = object.__new__(module.RagAnswerWorker)
    worker.settings = configured
    worker.space_hash = embedding_space_hash(configured.rag_embedding_space_identity)
    values = current_sample()
    values.update(embedding_space_hash=worker.space_hash,
                  answer_policy_version="related_knowledge_navigation_v8",
                  source_judge_contract_version="visual_source_id_v5",
                  source_judge_timeout_seconds=120,
                  source_context_policy_version="literal_subject_admission_v2",
                  source_context_admission_sha256="a" * 64)
    current = SimpleNamespace(**values)
    assert worker._profile_matches(current)
    old_values = sample()
    old_values["embedding_space_hash"] = worker.space_hash
    assert not worker._profile_matches(SimpleNamespace(**old_values))
    old_v7 = dict(values)
    old_v7.update(answer_policy_version="related_knowledge_navigation_v7",
                  source_judge_contract_version="visual_source_id_v3",
                  source_context_policy_version="literal_subject_admission_v1")
    assert not worker._profile_matches(SimpleNamespace(**old_v7))
    historical_v6 = current_sample()
    historical_v6["embedding_space_hash"] = worker.space_hash
    assert not worker._profile_matches(SimpleNamespace(**historical_v6))
    for name, invalid in (("source_judge_contract_version", "visual_source_id_v1"),
                          ("source_judge_max_output_tokens", 2048),
                          ("source_judge_max_output_tokens", 4097),
                          ("source_judge_thinking_level", "low"),
                          ("source_judge_timeout_seconds", 121),
                          ("source_judge_contract_version", "visual_source_id_v2"),
                          ("source_context_policy_version", None),
                          ("source_context_admission_sha256", "A" * 64)):
        changed = SimpleNamespace(**values)
        setattr(changed, name, invalid)
        assert not worker._profile_matches(changed)


@pytest.mark.asyncio
async def test_current_worker_accepts_exact_4096_thinking_inclusive_output(monkeypatch):
    response = VisualJudgeResponse(verdict(), "STOP", 100, 96, 4000)
    worker, _, _, selected, _, calls = setup(monkeypatch, response=response)
    result = await run(worker, selected)
    assert result[0] == (selected,)
    assert calls[-1][1].output_tokens == 4096
    assert calls[-1][1].request_count == 1 and calls[-1][1].retry_count == 0


@pytest.mark.asyncio
async def test_current_worker_rejects_4097_preserving_known_cost_without_retry(monkeypatch):
    response = VisualJudgeResponse(verdict(), "STOP", 100, 97, 4000)
    worker, _, _, selected, _, calls = setup(monkeypatch, response=response)
    with pytest.raises(module.visual_contract.VisualSourceJudgmentError, match="provider_token_limit_exceeded"):
        await run(worker, selected)
    assert calls[-1][1].output_tokens == 4097 and calls[-1][1].has_usage
    assert calls[-1][1].request_count == 1 and calls[-1][1].retry_count == 0
    assert calls[-1][2] == "invalid_ai_output" and calls[-1][3]["uncertain"]
