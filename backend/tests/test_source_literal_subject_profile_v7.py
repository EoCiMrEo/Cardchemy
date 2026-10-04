"""Synthetic public v7 disclosure contracts; no provider, operator env or DB."""
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
import pytest

from app.config import Settings
from app.routers import rag as router
from tests.test_source_visual_runtime_profile import ProfileDb, profile, settings


@pytest.fixture
def v7_policy(monkeypatch):
    monkeypatch.setattr(router, "ASK_REQUIRED_RELEASE_POLICY_VERSION", "related_knowledge_navigation_v7")
    monkeypatch.setattr(Settings, "rag_source_judge_contract_version", property(lambda _self: "visual_source_id_v3"))
    # This prospective profile test cannot open the real release fence.
    monkeypatch.setattr(Settings, "rag_ask_effective_enabled", property(lambda _self: False))


async def test_v7_discloses_only_possible_literal_subject_transfer_while_paused(monkeypatch, v7_policy):
    result = await profile(monkeypatch, settings())
    assert result.ask_policy == "related_knowledge_navigation_v7"
    assert result.source_judge_contract_version == "visual_source_id_v3"
    assert result.source_judge_transfers_literal_subject_context is True
    assert result.source_judge_transfers_page_images is True
    assert result.source_judge_thinking_level == "HIGH"
    assert not result.ask_enabled and not result.ask_available and not result.source_judge_available
    assert not result.answer_available and result.answer_provider is result.answer_model is None
    keys = result.model_dump()
    assert not set(keys) & {"literal_subject", "preceding_question", "history", "message_id", "content_sha256"}
    assert "secret" not in result.model_dump_json() and "api_key" not in result.model_dump_json()


@pytest.mark.parametrize("policy", ["related_knowledge_v1", *[f"related_knowledge_navigation_v{n}" for n in range(2, 7)]])
async def test_historical_policies_never_claim_literal_subject_transfer(monkeypatch, v7_policy, policy):
    monkeypatch.setattr(router, "ASK_REQUIRED_RELEASE_POLICY_VERSION", policy)
    result = await profile(monkeypatch, settings())
    assert not result.source_judge_transfers_literal_subject_context
    assert not result.ask_enabled


async def test_v7_with_old_wire_contract_cannot_claim_context_transfer(monkeypatch, v7_policy):
    monkeypatch.setattr(Settings, "rag_source_judge_contract_version", property(lambda _self: "visual_source_id_v2"))
    result = await profile(monkeypatch, settings())
    assert not result.source_judge_transfers_literal_subject_context
    assert not result.ask_enabled


async def test_even_prospective_available_profile_stays_closed_for_wrong_space(monkeypatch, v7_policy):
    monkeypatch.setattr(Settings, "rag_ask_effective_enabled", property(lambda _self: True))
    configured = settings()
    matching = await profile(monkeypatch, configured)
    assert matching.ask_enabled and matching.source_judge_available
    mismatching = await profile(monkeypatch, configured, matches=False)
    assert not mismatching.active_embedding_space_matches
    assert not mismatching.ask_enabled and not mismatching.ask_available and not mismatching.source_judge_available
    assert mismatching.source_judge_transfers_literal_subject_context


async def test_unauthorized_subject_cannot_read_or_disclose_v7_capability(monkeypatch, v7_policy):
    async def denied(*_args):
        raise HTTPException(status_code=404, detail="Subject not found")

    monkeypatch.setattr(router.SubjectService, "check_subject_access", denied)
    db = ProfileDb("not-read")
    with pytest.raises(HTTPException) as caught:
        await router.get_rag_profile(uuid4(), SimpleNamespace(id=uuid4()), db, settings())
    assert caught.value.status_code == 404 and db.reads == 0
