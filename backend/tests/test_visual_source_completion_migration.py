"""V6 preserves v5 history while independently fencing its 4,096-token contract."""
import sqlite3

import pytest

from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION, ASK_RUNTIME_POLICY_VERSION, ASK_SOURCE_ONLY_READ_POLICIES
from app.models.rag import RagAnswerJob, RagAnswerStageAttempt
from tests.test_visual_source_judgment_policy_migration import checks, current as v5, definitions as before_v5, insert, load, sample


def current():
    return load("20261001_0031_visual_source_completion.py")


def current_sample():
    row = sample("related_knowledge_navigation_v6")
    row.update(source_judge_contract_version="visual_source_id_v2", source_judge_max_output_tokens=4096)
    return row


def definitions():
    state = before_v5()
    old = v5()
    for name, before, after in old._patches()[:-1]:
        assert state[name].count(before) == 1
        state[name] = state[name].replace(before, after)
    name = "enforce_rag_source_stage_parent_policy()"
    assert state[name].count(old.OLD_POLICIES) == 2
    state[name] = state[name].replace(old.OLD_POLICIES, old.NEW_POLICIES)
    return state


def test_exact_additive_chain_and_current_model_checks_preserve_v5():
    newest, old = current(), v5()
    assert newest.down_revision == old.revision
    assert newest.OLD_POLICIES == old.NEW_POLICIES
    for before, after in (("OLD_IDENTITY", "NEW_IDENTITY"), ("OLD_RESULT", "NEW_RESULT"),
                          ("OLD_JUDGE_SNAPSHOT", "JUDGE_SNAPSHOT"),
                          ("OLD_RETRIEVAL_PAIR", "NEW_RETRIEVAL_PAIR"),
                          ("OLD_STAGE_POLICY", "NEW_STAGE_POLICY"),
                          ("OLD_VISUAL_STAGE_CAP", "VISUAL_STAGE_CAP"),
                          ("OLD_JOB_NULL_RESULT", "NEW_JOB_NULL_RESULT"),
                          ("OLD_REFERENCE_PAIR", "NEW_REFERENCE_PAIR")):
        assert getattr(newest, before) == getattr(old, after)
    jobs, stages = checks(RagAnswerJob), checks(RagAnswerStageAttempt)
    head = load("20261002_0033_visual_clarity_policy.py")
    for name, value in (("identity", newest.NEW_IDENTITY), ("result", newest.NEW_RESULT),
                        ("source_judge_snapshot", newest.JUDGE_SNAPSHOT),
                        ("source_judge_retrieval_pair", newest.NEW_RETRIEVAL_PAIR)):
        assert jobs["ck_rag_answer_jobs_" + name] == getattr(head, {
            "identity": "NEW_IDENTITY", "result": "NEW_RESULT",
            "source_judge_snapshot": "JUDGE_SNAPSHOT",
            "source_judge_retrieval_pair": "NEW_RETRIEVAL_PAIR",
        }[name])
    assert stages["ck_rag_answer_stage_source_judgment_policy"] == head.NEW_STAGE_POLICY
    assert stages["ck_rag_answer_stage_visual_judge_cap"] == head.VISUAL_STAGE_CAP
    assert old.V5_JUDGE_SNAPSHOT in newest.JUDGE_SNAPSHOT
    assert ASK_REQUIRED_RELEASE_POLICY_VERSION == head.V8
    assert newest.V6 in ASK_SOURCE_ONLY_READ_POLICIES
    assert "related_knowledge_navigation_v5" in ASK_SOURCE_ONLY_READ_POLICIES
    assert ASK_RUNTIME_POLICY_VERSION == ASK_REQUIRED_RELEASE_POLICY_VERSION


def test_old_and_new_snapshots_cannot_be_reinterpreted():
    insert(sample())
    insert(current_sample())
    old = sample()
    old.update(source_judge_max_output_tokens=4096)
    with pytest.raises(sqlite3.IntegrityError):
        insert(old)
    old.update(source_judge_max_output_tokens=2048, source_judge_contract_version="visual_source_id_v2")
    with pytest.raises(sqlite3.IntegrityError):
        insert(old)
    new = current_sample()
    new.update(source_judge_contract_version="visual_source_id_v1")
    with pytest.raises(sqlite3.IntegrityError):
        insert(new)


@pytest.mark.parametrize("field,value", [
    ("source_judge_max_output_tokens", 4097), ("source_judge_max_output_tokens", 0),
    ("source_judge_max_input_tokens", 32769), ("source_judge_timeout_seconds", 61),
    ("source_judge_thinking_level", "low"), ("source_judge_model", "gemini-3.5-flash"),
    ("source_judge_base_url", "https://unapproved.invalid"),
    ("retrieval_policy", "hybrid_source_navigation_v8"), ("ai_model", "forbidden-answer-model"),
])
def test_v6_snapshot_rejects_budget_profile_and_answer_execution(field, value):
    row = current_sample()
    row[field] = value
    with pytest.raises(sqlite3.IntegrityError):
        insert(row)


def test_trigger_changes_round_trip_exact_v5_and_unknown_definitions_fail(monkeypatch):
    migration, original = current(), definitions()
    state = dict(original)
    class Bind:
        def scalar(self, statement):
            return state[statement.compile().params["name"]]
    monkeypatch.setattr(migration.op, "get_bind", lambda: Bind())
    def execute(statement):
        value = str(statement)
        name = next(name for name in state if name.split("(")[0] in value)
        state[name] = value
    monkeypatch.setattr(migration.op, "execute", execute)
    for name, old, new in migration._patches():
        migration._replace_function(name, old, new)
    migration._patch_parent()
    assert state["enforce_rag_source_stage_parent_policy()"].count(migration.NEW_POLICIES) == 2
    assert "judged.answer_policy_version = 'related_knowledge_navigation_v5'" in state["rag_answer_job_guard()"]
    assert "judged.answer_policy_version = 'related_knowledge_navigation_v6'" in state["rag_answer_job_guard()"]
    migration._patch_parent(reverse=True)
    for name, old, new in reversed(migration._patches()):
        migration._replace_function(name, new, old, reverse=True)
    assert state == original
    monkeypatch.setattr(migration.op, "get_bind", lambda: type("Unknown", (), {"scalar": lambda *_: "unknown"})())
    with pytest.raises(RuntimeError, match="Unexpected"):
        migration._replace_function(*migration._patches()[0])


def test_downgrade_refuses_v6_before_modifying_guards_or_indexes(monkeypatch):
    migration = current()
    class Bind:
        def scalar(self, statement):
            assert migration.V6 in str(statement)
            return 1
    monkeypatch.setattr(migration.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(migration, "_patch_parent", lambda **_k: pytest.fail("DDL before preservation guard"))
    with pytest.raises(RuntimeError, match="v6 visual source-judgment job snapshots"):
        migration.downgrade()
