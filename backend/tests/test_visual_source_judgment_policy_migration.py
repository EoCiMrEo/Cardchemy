"""Offline dormant v5 schema contracts; invented rows and in-memory SQLite only."""
import importlib.util
from pathlib import Path
import sqlite3

import pytest

from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION, ASK_RUNTIME_POLICY_VERSION, ASK_SOURCE_ONLY_READ_POLICIES
from app.models.rag import RagAnswerJob, RagAnswerStageAttempt


def load(filename):
    path = Path(__file__).resolve().parents[1] / "alembic/versions" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def current():
    return load("20261001_0030_visual_source_judgment.py")


def checks(model):
    return {item.name: str(item.sqltext) for item in model.__table__.constraints
            if item.name and item.name.startswith("ck_")}


def sample(policy="related_knowledge_navigation_v5"):
    return dict(operation_key_hash="a" * 64, request_fingerprint="b" * 64,
        corpus_revision=1, embedding_space_hash="c" * 64, retrieval_policy="hybrid_source_navigation_v9",
        answer_policy_version=policy, ai_provider=None, ai_base_url=None, ai_model=None,
        ai_catalog_version=None, ai_schema_policy_version=None, support_policy_version=None,
        embedding_provider="gemini", embedding_base_url="https://generativelanguage.googleapis.com",
        embedding_model="gemini-embedding-001", source_judge_provider="gemini",
        source_judge_base_url="https://generativelanguage.googleapis.com", source_judge_model="gemini-3.5-flash-lite",
        source_judge_contract_version="visual_source_id_v1", source_judge_input_price_microusd_per_million=300000,
        source_judge_output_price_microusd_per_million=2500000, source_judge_max_input_tokens=32768,
        source_judge_max_output_tokens=2048, source_judge_thinking_level="high", source_judge_timeout_seconds=60.0,
        status="queued", result_kind=None, answer_message_id=None, error_code=None)


def insert(row):
    relevant = checks(RagAnswerJob)
    names = ("identity", "result", "source_judge_snapshot", "source_judge_retrieval_pair")
    sql_checks = ", ".join("CHECK (" + relevant["ck_rag_answer_jobs_" + name] + ")" for name in names)
    columns = ", ".join(name + " " + ("REAL" if isinstance(value, (int, float)) else "TEXT")
                        for name, value in sample().items())
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE TABLE invented_jobs (" + columns + ", " + sql_checks + ")")
        db.execute("INSERT INTO invented_jobs VALUES (" + ",".join("?" for _ in row) + ")", tuple(row.values()))


def definitions():
    prior = load("20260927_0027_source_navigation_policy.py")
    v3 = load("20260927_0028_source_navigation_v3.py")
    v4 = load("20260928_0029_source_judgment_policy.py")
    job = prior.NEW_JOB_GUARD.replace(v3.OLD_JOB_CLAUSE, v3.NEW_JOB_CLAUSE)
    for old, new in ((v4.OLD_JOB_CLAUSE, v4.NEW_JOB_CLAUSE),
                     (v4.OLD_JOB_NO_MATCH, v4.NEW_JOB_NO_MATCH),
                     (v4.OLD_JOB_NULL_RESULT, v4.NEW_JOB_NULL_RESULT),
                     (v4.OLD_JOB_NEW_SNAPSHOT, v4.NEW_JOB_NEW_SNAPSHOT),
                     (v4.OLD_JOB_OLD_SNAPSHOT, v4.NEW_JOB_OLD_SNAPSHOT)):
        assert job.count(old) == 1
        job = job.replace(old, new)
    reference = prior.NEW_REFERENCE_GUARD.replace(v3.OLD_REFERENCE_PAIR, v3.NEW_REFERENCE_PAIR)
    reference = reference.replace(v4.OLD_REFERENCE_PAIR, v4.NEW_REFERENCE_PAIR)
    reference = reference.replace(v4.OLD_REFERENCE_KIND, v4.NEW_REFERENCE_KIND)
    return {"rag_answer_job_guard()": job, "rag_related_evidence_guard()": reference,
            "enforce_rag_source_stage_parent_policy()": v4._stage_guard(v4.NEW_POLICIES)}


def test_current_release_policy_and_historical_read_identities_remain_distinct():
    assert ASK_REQUIRED_RELEASE_POLICY_VERSION == "related_knowledge_navigation_v8"
    assert "related_knowledge_navigation_v5" in ASK_SOURCE_ONLY_READ_POLICIES
    assert ASK_RUNTIME_POLICY_VERSION == "related_knowledge_navigation_v8"
    assert ASK_RUNTIME_POLICY_VERSION == ASK_REQUIRED_RELEASE_POLICY_VERSION
    assert "related_knowledge_navigation_v4" in ASK_SOURCE_ONLY_READ_POLICIES
    assert ASK_REQUIRED_RELEASE_POLICY_VERSION in ASK_SOURCE_ONLY_READ_POLICIES


def test_migration_chain_model_constraints_and_immutable_snapshots_match():
    m, v4 = current(), load("20260928_0029_source_judgment_policy.py")
    assert m.down_revision == v4.revision
    assert m.OLD_POLICIES == v4.NEW_POLICIES
    assert m.OLD_IDENTITY == v4.NEW_IDENTITY
    assert m.OLD_RESULT == v4.NEW_RESULT
    assert m.OLD_JUDGE_SNAPSHOT == v4.JUDGE_SNAPSHOT
    assert m.OLD_REFERENCE_PAIR == v4.NEW_REFERENCE_PAIR
    assert m.OLD_JOB_NULL_RESULT == v4.NEW_JOB_NULL_RESULT
    job, stage = checks(RagAnswerJob), checks(RagAnswerStageAttempt)
    newest = load("20261002_0033_visual_clarity_policy.py")
    assert job["ck_rag_answer_jobs_identity"] == newest.NEW_IDENTITY
    assert job["ck_rag_answer_jobs_result"] == newest.NEW_RESULT
    assert job["ck_rag_answer_jobs_source_judge_snapshot"] == newest.JUDGE_SNAPSHOT
    assert job["ck_rag_answer_jobs_source_judge_retrieval_pair"] == newest.NEW_RETRIEVAL_PAIR
    assert stage["ck_rag_answer_stage_source_judgment_policy"] == newest.NEW_STAGE_POLICY
    assert stage["ck_rag_answer_stage_visual_judge_cap"] == newest.VISUAL_STAGE_CAP
    for name in m.VISUAL_COLUMNS:
        assert RagAnswerJob.__table__.columns[name].nullable
        assert "NEW." + name in m.NEW_JOB_NEW_SNAPSHOT
        assert "OLD." + name in m.NEW_JOB_OLD_SNAPSHOT


def test_valid_visual_snapshot_and_historical_v4_snapshot_are_separately_accepted():
    insert(sample())
    old = sample("related_knowledge_navigation_v4")
    old.update(source_judge_model="gemini-3.8-flash", source_judge_contract_version="source_id_only_public_v1",
               source_judge_max_input_tokens=8192, source_judge_max_output_tokens=1024,
               source_judge_input_price_microusd_per_million=1500000,
               source_judge_output_price_microusd_per_million=7500000,
               source_judge_thinking_level=None, source_judge_timeout_seconds=None)
    insert(old)
    old["source_judge_thinking_level"] = "high"
    with pytest.raises(sqlite3.IntegrityError):
        insert(old)


@pytest.mark.parametrize("field,value", [
    ("source_judge_model", "gemini-3.8-flash"), ("source_judge_model", None),
    ("source_judge_base_url", "https://unapproved.invalid"),
    ("source_judge_contract_version", "source_id_only_public_v1"),
    ("source_judge_input_price_microusd_per_million", 299999),
    ("source_judge_output_price_microusd_per_million", 2499999),
    ("source_judge_max_input_tokens", 32769), ("source_judge_max_output_tokens", 2049),
    ("source_judge_thinking_level", "low"), ("source_judge_thinking_level", None),
    ("source_judge_timeout_seconds", 61), ("source_judge_timeout_seconds", 0),
    ("source_judge_timeout_seconds", None), ("source_judge_timeout_seconds", float("nan")),
    ("source_judge_timeout_seconds", float("inf")),
    ("retrieval_policy", "hybrid_source_navigation_v8"), ("ai_model", "forbidden-answer-model"),
])
def test_invalid_visual_snapshot_fails_closed_in_actual_portable_checks(field, value):
    row = sample()
    row[field] = value
    with pytest.raises(sqlite3.IntegrityError):
        insert(row)


def test_remote_attempt_caps_and_cross_worker_uniqueness_keep_v4_and_v5_separate():
    constraints = checks(RagAnswerStageAttempt)
    required = ("ck_rag_answer_stage_source_judgment_policy", "ck_rag_answer_stage_source_judge_cap",
                "ck_rag_answer_stage_visual_judge_cap")
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE TABLE rag_answer_stage_attempts (job_id TEXT, manual_retry_number INTEGER, "
                   "worker_attempt_number INTEGER, stage TEXT, answer_policy_version TEXT, "
                   "physical_request_count INTEGER, retry_count INTEGER, " +
                   ",".join("CHECK (" + constraints[name] + ")" for name in required) + ")")
        for index in RagAnswerStageAttempt.__table__.indexes:
            if index.name in ("uq_rag_answer_stage_visual_remote_attempt", "uq_rag_answer_stage_source_judge_remote_attempt"):
                predicate = str(index.dialect_options["postgresql"]["where"])
                db.execute("CREATE UNIQUE INDEX " + index.name + " ON rag_answer_stage_attempts "
                           "(job_id,manual_retry_number,stage) WHERE " + predicate)
        for policy in ("related_knowledge_navigation_v4", "related_knowledge_navigation_v5"):
            row = [policy, 0, 1, "source_judgment", policy, 1, 0]
            db.execute("INSERT INTO rag_answer_stage_attempts VALUES (?,?,?,?,?,?,?)", row)
            for field, bad in ((2, 2), (3, "answer"), (5, 2), (6, 1)):
                changed = list(row)
                changed[field] = bad
                if field != 2:
                    changed[0] += "-invalid-" + str(field)
                with pytest.raises(sqlite3.IntegrityError):
                    db.execute("INSERT INTO rag_answer_stage_attempts VALUES (?,?,?,?,?,?,?)", changed)


@pytest.mark.parametrize("kind", ["local", "valid", "unfinished", "failed", "uncertain", "no_call", "retry", "stale_worker", "stale_manual"])
def test_post_provider_clarification_accepts_only_current_successful_judgment(kind):
    # Execute the migration's rejection predicate with invented stage rows.
    m = current()
    v5_clause = m.NEW_JOB_NULL_RESULT.split(" OR (NEW.answer_policy_version = 'related_knowledge_navigation_v5'", 1)[1]
    expression = "(job.answer_policy_version = 'related_knowledge_navigation_v5'" + v5_clause
    expression = expression.removesuffix(" OR NEW.result_kind IS NULL").replace("NEW.", "job.")
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE TABLE job (id TEXT, answer_policy_version TEXT, result_kind TEXT, manual_retry_count INTEGER, attempt_count INTEGER)")
        db.execute("INSERT INTO job VALUES ('synthetic','related_knowledge_navigation_v5','clarification_needed',0,1)")
        db.execute("CREATE TABLE rag_answer_stage_attempts (job_id TEXT, answer_policy_version TEXT, manual_retry_number INTEGER, "
                   "worker_attempt_number INTEGER, stage TEXT, completed_at TEXT, physical_request_count INTEGER, retry_count INTEGER, "
                   "error_category TEXT, failure_reason TEXT, execution_uncertain BOOLEAN)")
        if kind != "local":
            row = ["synthetic", m.V5, 0, 1, "source_judgment", "finished", 1, 0, None, None, False]
            if kind == "unfinished": row[5] = None
            if kind == "failed": row[8] = "invalid_ai_output"
            if kind == "uncertain": row[10] = True
            if kind == "no_call": row[6] = 0
            if kind == "retry": row[7] = 1
            if kind == "stale_worker": row[3] = 2
            if kind == "stale_manual": row[2] = 1
            db.execute("INSERT INTO rag_answer_stage_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?)", row)
        rejected = db.execute("SELECT " + expression + " FROM job").fetchone()[0]
        assert bool(rejected) is (kind not in ("local", "valid"))


def test_trigger_patches_round_trip_exact_prior_definitions(monkeypatch):
    m = current()
    original = definitions()
    state = dict(original)
    class Bind:
        def scalar(self, statement):
            return state[statement.compile().params["name"]]
    monkeypatch.setattr(m.op, "get_bind", lambda: Bind())
    def execute(statement):
        value = str(statement)
        name = next(name for name in state if name.split("(")[0] in value)
        state[name] = value
    monkeypatch.setattr(m.op, "execute", execute)
    for name, old, new in m._patches()[:-1]:
        m._replace_function(name, old, new)
    m._patch_parent()
    assert "OR (NEW.result_kind IN ('no_match','clarification_needed') AND source_total <> 0)" in state["rag_answer_job_guard()"]
    assert "judged.worker_attempt_number = NEW.attempt_count" in state["rag_answer_job_guard()"]
    assert "judged.worker_attempt_number = answer_job.attempt_count" in state["rag_related_evidence_guard()"]
    assert state["enforce_rag_source_stage_parent_policy()"].count(m.NEW_POLICIES) == 2
    m._patch_parent(reverse=True)
    for name, old, new in reversed(m._patches()[:-1]):
        m._replace_function(name, new, old, reverse=True)
    assert state == original
    monkeypatch.setattr(m.op, "get_bind", lambda: type("Unknown", (), {"scalar": lambda *_: "unknown definition"})())
    with pytest.raises(RuntimeError, match="Unexpected"):
        m._replace_function(*m._patches()[0])


def test_downgrade_refuses_v5_rows_before_any_ddl(monkeypatch):
    m = current()
    class Bind:
        def scalar(self, statement):
            assert m.V5 in str(statement)
            return 1
    monkeypatch.setattr(m.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(m.op, "drop_column", lambda *_a, **_k: pytest.fail("DDL before preservation fence"))
    monkeypatch.setattr(m, "_patch_parent", lambda **_k: pytest.fail("Trigger edit before preservation fence"))
    with pytest.raises(RuntimeError, match="v5 visual source-judgment job snapshots"):
        m.downgrade()
