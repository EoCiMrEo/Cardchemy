"""New 0032 preparation: invented SQLite rows and immutable SQL guard roundtrip.

No retained database or provider is used. PostgreSQL enactment remains a
separate required disposable migration/authorization/retention gate.
"""
import re
import sqlite3

import pytest

from tests.test_visual_source_judgment_policy_migration import load, sample
from tests.test_visual_source_completion_migration import current as previous, definitions as before_v6


def current():
    return load("20261002_0032_literal_subject_context.py")


def job_sample(policy="related_knowledge_navigation_v7"):
    row = sample(policy)
    row.update(source_context_policy_version="literal_subject_admission_v1",
               source_context_admission_sha256="d" * 64,
               source_judge_contract_version="visual_source_id_v3",
               source_judge_max_output_tokens=4096, source_judge_timeout_seconds=120.0)
    if policy == "related_knowledge_navigation_v6":
        row.update(source_context_policy_version=None, source_context_admission_sha256=None,
                   source_judge_contract_version="visual_source_id_v2", source_judge_timeout_seconds=60.0)
    elif policy == "related_knowledge_navigation_v5":
        row.update(source_context_policy_version=None, source_context_admission_sha256=None,
                   source_judge_contract_version="visual_source_id_v1", source_judge_timeout_seconds=60.0,
                   source_judge_max_output_tokens=2048)
    return row


def context_sample(*, raw_clear=False, anchor=True, preceding=True):
    row = dict(job_id="job", thread_id="thread", user_id="owner", subject_id="subject",
        current_message_id="current", context_version="literal_subject_admission_v1",
        raw_question_clear=raw_clear, current_question_sha256="a" * 64,
        current_created_at="2026-01-02T12:00:00Z", current_expires_at="2026-01-03T12:00:00Z",
        captured_at="2026-01-02T12:00:00Z", admission_sha256="b" * 64,
        preceding_message_id="prior", preceding_question_sha256="c" * 64,
        preceding_created_at="2026-01-02T11:59:59Z", preceding_expires_at="2026-01-02T13:00:00Z",
        subject_start_offset=7, subject_end_offset=21, subject_start_byte_offset=7,
        subject_end_byte_offset=21, subject_sha256="d" * 64)
    if raw_clear or not anchor:
        for key in current().SUBJECT_COLUMNS:
            row[key] = None
    if raw_clear or not preceding:
        for key in current().PRECEDING_COLUMNS:
            row[key] = None
    return row


def insert(row, constraints):
    columns = ", ".join(name + " " + ("REAL" if isinstance(value, (int, float)) else "TEXT")
                        for name, value in row.items())
    checks = ", ".join("CHECK (" + value.replace(" ~ ", " REGEXP ") + ")" for value in constraints)
    with sqlite3.connect(":memory:") as db:
        db.create_function("regexp", 2, lambda pattern, value: value is not None and re.fullmatch(pattern, str(value)) is not None)
        db.execute("CREATE TABLE invented (" + columns + ", " + checks + ")")
        db.execute("INSERT INTO invented VALUES (" + ",".join("?" for _ in row) + ")", tuple(row.values()))


def insert_job(row):
    m = current()
    insert(row, (m.NEW_IDENTITY, m.NEW_RESULT, m.JUDGE_SNAPSHOT, m.NEW_RETRIEVAL_PAIR, m.JOB_CONTEXT_CHECK))


def definitions():
    state = before_v6()
    old = previous()
    for name, before, after in old._patches():
        assert state[name].count(before) == 1
        state[name] = state[name].replace(before, after)
    name = "enforce_rag_source_stage_parent_policy()"
    assert state[name].count(old.OLD_POLICIES) == 2
    state[name] = state[name].replace(old.OLD_POLICIES, old.NEW_POLICIES)
    return state


def test_additive_chain_constants_preserve_every_exact_installed_v6_guard():
    new, old = current(), previous()
    assert new.revision == "20261002_0032" and new.down_revision == old.revision
    assert new.OLD_POLICIES == old.NEW_POLICIES
    for oldname, previousname in (
        ("OLD_IDENTITY", "NEW_IDENTITY"), ("OLD_RESULT", "NEW_RESULT"),
        ("OLD_JUDGE_SNAPSHOT", "JUDGE_SNAPSHOT"), ("OLD_RETRIEVAL_PAIR", "NEW_RETRIEVAL_PAIR"),
        ("OLD_STAGE_POLICY", "NEW_STAGE_POLICY"), ("OLD_VISUAL_STAGE_CAP", "VISUAL_STAGE_CAP"),
        ("OLD_JOB_CLAUSE", "NEW_JOB_CLAUSE"), ("OLD_JOB_NULL_RESULT", "NEW_JOB_NULL_RESULT"),
        ("OLD_REFERENCE_PAIR", "NEW_REFERENCE_PAIR"), ("OLD_REFERENCE_POLICY", "NEW_REFERENCE_POLICY"),
        ("OLD_VISUAL_INDEX", "NEW_VISUAL_INDEX"),
    ):
        assert getattr(new, oldname) == getattr(old, previousname)
    assert "visual_source_id_v3" in new.JUDGE_SNAPSHOT
    assert "source_judge_timeout_seconds BETWEEN 1 AND 120" in new.JUDGE_SNAPSHOT
    assert "source_judge_timeout_seconds BETWEEN 1 AND 60" in new.JUDGE_SNAPSHOT


@pytest.mark.parametrize("policy", ["related_knowledge_navigation_v5", "related_knowledge_navigation_v6", "related_knowledge_navigation_v7"])
def test_old_and_new_genuine_snapshots_remain_accepted(policy):
    insert_job(job_sample(policy))


@pytest.mark.parametrize(("field", "value"), [
    ("source_judge_timeout_seconds", 120.1), ("source_judge_timeout_seconds", 0),
    ("source_judge_timeout_seconds", None), ("source_judge_contract_version", "visual_source_id_v2"),
    ("source_judge_max_output_tokens", 4097), ("source_judge_max_input_tokens", 32769),
    ("source_judge_thinking_level", "low"), ("source_judge_model", "gemini-3.5-flash"),
    ("source_judge_base_url", "https://unapproved.invalid"), ("ai_model", "answer-model"),
    ("retrieval_policy", "hybrid_source_navigation_v8"), ("source_context_policy_version", None),
    ("source_context_policy_version", "legacy"), ("source_context_admission_sha256", None),
    ("source_context_admission_sha256", "A" * 64), ("source_context_admission_sha256", "short"),
])
def test_v7_malformed_profile_budget_or_context_snapshot_rejected(field, value):
    row = job_sample()
    row[field] = value
    with pytest.raises(sqlite3.IntegrityError):
        insert_job(row)


@pytest.mark.parametrize("mutation", ["long_timeout", "new_contract", "context_version", "context_sha"])
def test_old_v6_cannot_be_reinterpreted_as_v7(mutation):
    row = job_sample("related_knowledge_navigation_v6")
    if mutation == "long_timeout": row["source_judge_timeout_seconds"] = 120
    elif mutation == "new_contract": row["source_judge_contract_version"] = "visual_source_id_v3"
    elif mutation == "context_version": row["source_context_policy_version"] = "literal_subject_admission_v1"
    else: row["source_context_admission_sha256"] = "a" * 64
    with pytest.raises(sqlite3.IntegrityError):
        insert_job(row)


@pytest.mark.parametrize(("raw_clear", "anchor", "preceding"), [
    (True, False, False), (False, True, True), (False, False, True), (False, False, False),
])
def test_context_shape_supports_raw_clear_resolved_and_safe_clarification(raw_clear, anchor, preceding):
    insert(context_sample(raw_clear=raw_clear, anchor=anchor, preceding=preceding), (current().CONTEXT_SHAPE_CHECK,))


@pytest.mark.parametrize(("field", "value"), [
    ("context_version", "legacy"), ("current_question_sha256", "short"),
    ("admission_sha256", "x" * 64), ("preceding_message_id", "current"),
    ("preceding_question_sha256", None), ("preceding_created_at", None),
    ("preceding_created_at", "2026-01-02T12:00:00Z"),
    ("preceding_expires_at", "2026-01-02T12:00:00Z"),
    ("current_expires_at", "2026-01-02T12:00:00Z"),
    ("captured_at", "2026-01-02T11:59:58Z"), ("subject_start_offset", -1),
    ("subject_end_offset", 7), ("subject_end_offset", 168), ("subject_start_byte_offset", -1),
    ("subject_end_byte_offset", 7), ("subject_end_byte_offset", 648),
    ("subject_sha256", None), ("subject_sha256", "bad"), ("raw_question_clear", True),
])
def test_context_partial_shape_order_expiry_literal_and_clear_conflicts_rejected(field, value):
    row = context_sample()
    row[field] = value
    with pytest.raises(sqlite3.IntegrityError):
        insert(row, (current().CONTEXT_SHAPE_CHECK,))


def test_subject_character_and_utf8_byte_bounds_are_inclusive():
    row = context_sample()
    row.update(subject_start_offset=0, subject_end_offset=160,
               subject_start_byte_offset=0, subject_end_byte_offset=640)
    insert(row, (current().CONTEXT_SHAPE_CHECK,))


def test_guard_patches_round_trip_exact_prior_definitions_and_unknown_state_fails(monkeypatch):
    migration, original = current(), definitions()
    state = dict(original)
    class Bind:
        def scalar(self, statement):
            return state[statement.compile().params["name"]]
    monkeypatch.setattr(migration.op, "get_bind", lambda: Bind())
    def execute(statement):
        definition = str(statement)
        name = next(name for name in state if name.split("(")[0] in definition)
        state[name] = definition
    monkeypatch.setattr(migration.op, "execute", execute)
    for name, old, new in migration._patches():
        migration._replace_function(name, old, new)
    migration._patch_parent()
    assert "NEW.source_context_admission_sha256" in state["rag_answer_job_guard()"]
    assert "judged.answer_policy_version = 'related_knowledge_navigation_v7'" in state["rag_answer_job_guard()"]
    assert state["enforce_rag_source_stage_parent_policy()"].count(migration.NEW_POLICIES) == 2
    migration._patch_parent(reverse=True)
    for name, old, new in reversed(migration._patches()):
        migration._replace_function(name, new, old, reverse=True)
    assert state == original
    monkeypatch.setattr(migration.op, "get_bind", lambda: type("Unknown", (), {"scalar": lambda *_: "unknown"})())
    with pytest.raises(RuntimeError, match="Unexpected"):
        migration._replace_function(*migration._patches()[0])


def test_postgres_sql_checks_literal_exactness_latest_user_and_deferred_admission_without_cascade_job():
    m = current()
    guard = m._context_guard_sql()
    assert "FOR UPDATE" in guard and "FOR KEY SHARE" in guard
    assert "ORDER BY created_at DESC, id DESC LIMIT 1" in guard
    assert "created_at < current_question.created_at" in guard
    assert "AND expires_at > NEW.captured_at" not in guard
    assert "IF NOT NEW.raw_question_clear" not in guard
    assert "IF NEW.preceding_message_id IS NOT NULL THEN" in guard
    assert "current_question.expires_at <= clock_timestamp()" in guard
    assert "previous_question.expires_at <= clock_timestamp()" in guard
    assert "previous_question.created_at >= current_question.created_at" in guard
    assert "previous_question.role <> 'user'" in guard
    assert "encode(sha256(convert_to(literal_subject, 'UTF8')), 'hex')" in guard
    assert "subject_start_byte_offset" in guard and "subject_end_byte_offset" in guard
    assert all("NEW." + name in guard and "OLD." + name in guard for name in m.CONTEXT_COLUMNS)
    assert "IF TG_OP = 'UPDATE'" in guard and "RETURN NEW" in guard
    assert "DELETE FROM rag_answer_jobs" not in guard
    assert "SELECT * INTO current_job FROM rag_answer_jobs WHERE id = NEW.id" in m.CONTEXT_ADMISSION_GUARD
    assert "admission_sha256 = current_job.source_context_admission_sha256" in m.CONTEXT_ADMISSION_GUARD


def test_upgrade_operation_shape_scoped_retention_and_immutable_column_types(monkeypatch):
    m, created, calls = current(), {}, []
    monkeypatch.setattr(m, "_checks", lambda **_k: None)
    monkeypatch.setattr(m, "_replace_function", lambda *_a, **_k: None)
    monkeypatch.setattr(m, "_patch_parent", lambda **_k: None)
    monkeypatch.setattr(m, "_index", lambda **_k: None)
    monkeypatch.setattr(m.op, "add_column", lambda table, col: calls.append(("column", table, col)))
    monkeypatch.setattr(m.op, "create_check_constraint", lambda *args: calls.append(("check", args)))
    monkeypatch.setattr(m.op, "create_index", lambda *args, **kwargs: calls.append(("index", args, kwargs)))
    monkeypatch.setattr(m.op, "execute", lambda sql: calls.append(("sql", str(sql))))
    def create_table(name, *items):
        created["name"], created["items"] = name, items
    monkeypatch.setattr(m.op, "create_table", create_table)
    m.upgrade()
    assert created["name"] == "rag_answer_question_context"
    columns = {item.name: item for item in created["items"] if isinstance(item, m.sa.Column)}
    assert set(columns) == set(m.CONTEXT_COLUMNS)
    assert not any("content" in name or "body" in name or name == "subject" for name in columns)
    foreign = {item.name: item for item in created["items"] if isinstance(item, m.sa.ForeignKeyConstraint)}
    assert set(foreign) == {"fk_rag_question_context_job_scope", "fk_rag_question_context_current_scope", "fk_rag_question_context_preceding_scope"}
    assert all(item.ondelete == "CASCADE" for item in foreign.values())
    assert all(element.target_fullname.startswith("rag_messages.") for element in foreign["fk_rag_question_context_preceding_scope"].elements)
    added = [record[2].name for record in calls if record[0] == "column"]
    assert added == ["source_context_policy_version", "source_context_admission_sha256"]
    sql = "\n".join(record[1] for record in calls if record[0] == "sql")
    assert "AFTER INSERT ON rag_answer_jobs DEFERRABLE INITIALLY DEFERRED" in sql
    assert "BEFORE INSERT OR UPDATE ON rag_answer_question_context" in sql


def test_downgrade_refuses_v7_before_any_schema_or_snapshot_change(monkeypatch):
    m = current()
    class Bind:
        def scalar(self, statement):
            assert m.V7 in str(statement)
            return 1
    monkeypatch.setattr(m.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(m.op, "execute", lambda *_: pytest.fail("DDL before preservation guard"))
    with pytest.raises(RuntimeError, match="v7 literal-context job snapshots"):
        m.downgrade()
