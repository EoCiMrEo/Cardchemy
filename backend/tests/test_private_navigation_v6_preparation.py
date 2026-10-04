"""Synthetic, keyless contracts for the separate private v6 hybrid preparer."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import prepare_private_navigation_v6 as prep
from test_private_query_vectors_v6 import fixture as vector_fixture
from test_private_source_gold_v4_snapshot import _bytes, _synthetic, _FakeReadOnlyDb, _uuid


def fixture(monkeypatch):
    gold, source, settings = vector_fixture(monkeypatch)
    decoded = json.loads(gold)
    rows = [{'case_id': case['case_id'],
             'question_sha256': sha256(case['question'].encode()).hexdigest(),
             'embedding': [1.] + [0.] * 1535} for case in decoded['cases']]
    packet = {'schema': prep.vectors.SCHEMA, 'model': prep.vectors.MODEL,
        'task': prep.vectors.TASK, 'dimensions': 1536,
        'stage1_sha256': sha256(gold).hexdigest(), 'source_snapshot_sha256': sha256(source).hexdigest(),
        'embedding_space_hash': decoded['scope']['embedding_space_hash'], 'vectors': rows}
    scope = prep.Scope(_uuid(100), _uuid(101), decoded['scope']['corpus_revision'],
                       decoded['scope']['embedding_space_hash'])
    return gold, source, _bytes(packet), scope, settings


def validate(inputs, vector=None, scope=None):
    gold, source, packet, original_scope, _ = inputs
    packet = packet if vector is None else _bytes(vector)
    return prep.prepare(gold, source, packet, vector_sha256=sha256(packet).hexdigest(),
                        scope=original_scope if scope is None else scope)


def test_default_invocation_is_inert_even_with_credentials_and_missing_inputs(tmp_path):
    result = subprocess.run([sys.executable, str(Path(prep.__file__)), '--stage1',
        str(tmp_path / 'not-present.json')], env={**os.environ, 'RAG_SOURCE_JUDGE_API_KEY': 'synthetic'},
        capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == {'schema': prep.SCHEMA, 'status': 'unexecuted',
        'database_reads': 0, 'database_writes': 0, 'provider_calls': 0, 'release_gate_passed': False}
    assert result.stderr == ''


def test_valid_packet_preserves_twelve_current_questions_and_forms(monkeypatch):
    gold, cases, documents, embeddings = validate(fixture(monkeypatch))
    assert tuple(cases) == tuple(f'T{i:02}' for i in range(1, 13))
    assert len(documents) == 3
    assert [case['form'] for case in cases.values()] == ['direct'] * 4 + ['paraphrase'] * 4 + ['followup'] * 4
    assert all(len(row) == 1536 and row[0] == 1 for row in embeddings.values())


@pytest.mark.parametrize('field,value', [
    ('schema', 'cardchemy_private_query_vectors_v1'), ('model', 'different-model'),
    ('task', 'RETRIEVAL_QUERY'), ('dimensions', True), ('dimensions', 768),
    ('stage1_sha256', 'a' * 64), ('source_snapshot_sha256', 'b' * 64),
    ('embedding_space_hash', 'c' * 64), ('vectors', []),
])
def test_packet_profile_and_pins_refuse(monkeypatch, field, value):
    inputs = fixture(monkeypatch)
    packet = json.loads(inputs[2]); packet[field] = value
    with pytest.raises(prep.Refusal, match='vector_packet_invalid'):
        validate(inputs, packet)


@pytest.mark.parametrize('change', [
    lambda packet: packet.update({'extra': True}),
    lambda packet: packet['vectors'].reverse(),
    lambda packet: packet['vectors'][0].update({'case_id': 'T99'}),
    lambda packet: packet['vectors'][0].update({'question_sha256': 'f' * 64}),
    lambda packet: packet['vectors'][0].update({'embedding': [0.] * 1536}),
    lambda packet: packet['vectors'][0].update({'embedding': [2.] + [0.] * 1535}),
    lambda packet: packet['vectors'][0].update({'embedding': [True] + [0.] * 1535}),
    lambda packet: packet['vectors'][0].update({'embedding': [1.] + [0.] * 1534}),
    lambda packet: packet['vectors'][0].update({'embedding': [1e308] + [0.] * 1535}),
    lambda packet: packet['vectors'][0].update({'previous_turn': 'must not appear'}),
])
def test_vector_rows_and_norm_refuse(monkeypatch, change):
    inputs = fixture(monkeypatch)
    packet = json.loads(inputs[2]); change(packet)
    with pytest.raises(prep.Refusal, match='vector_packet_invalid'):
        validate(inputs, packet)


@pytest.mark.parametrize('replacement', ['NaN', 'Infinity', '-Infinity'])
def test_nonfinite_json_numbers_refuse(monkeypatch, replacement):
    gold, source, packet, scope, _ = fixture(monkeypatch)
    packet = packet.replace(b'"embedding":[1.0,', ('"embedding":[' + replacement + ',').encode(), 1)
    with pytest.raises(prep.Refusal, match='vector_packet_invalid'):
        prep.prepare(gold, source, packet, vector_sha256=sha256(packet).hexdigest(), scope=scope)


def test_duplicate_json_keys_refuse(monkeypatch):
    gold, source, packet, scope, _ = fixture(monkeypatch)
    packet = packet.replace(b'{', b'{"schema":"forged",', 1)
    with pytest.raises(prep.Refusal, match='vector_packet_invalid'):
        prep.prepare(gold, source, packet, vector_sha256=sha256(packet).hexdigest(), scope=scope)


@pytest.mark.parametrize('field,value', [('principal_id', _uuid(102)), ('subject_id', _uuid(103)),
    ('corpus_revision', 99), ('embedding_space_hash', 'a' * 64)])
def test_explicit_authorized_scope_cannot_be_substituted(monkeypatch, field, value):
    inputs = fixture(monkeypatch)
    scope = prep.Scope(**{**vars(inputs[3]), field: value})
    with pytest.raises(prep.Refusal, match='scope_changed'):
        validate(inputs, scope=scope)


def environment(**updates):
    return {'ENVIRONMENT': 'development', 'RAG_ASK_ENABLED': 'false',
        'RAG_SOURCE_JUDGE_PROVIDER_ENABLED': 'false',
        'DATABASE_URL': 'postgresql+asyncpg://reader:synthetic@db:5432/cardchemy', **updates}


@pytest.mark.parametrize('name', sorted(prep.snapshot._AI_CREDENTIAL_NAMES))
def test_every_ai_credential_is_rejected_before_runtime_loading(name):
    with pytest.raises(prep.snapshot.Refusal, match='ai_credentials_present'):
        prep.guard_runtime(environment(**{name: 'synthetic'}), 'cardchemy')


@pytest.mark.parametrize('updates', [{'ENVIRONMENT': 'production'}, {'RAG_ASK_ENABLED': 'true'},
    {'RAG_SOURCE_JUDGE_PROVIDER_ENABLED': 'true'}, {'RAG_SOURCE_JUDGE_PROVIDER_ENABLED': ''},
    {'DATABASE_URL': 'postgresql+asyncpg://reader:synthetic@localhost:5432/cardchemy'}])
def test_runtime_guard_requires_exact_disabled_development_target(updates):
    with pytest.raises((prep.Refusal, prep.snapshot.Refusal)):
        prep.guard_runtime(environment(**updates), 'cardchemy')


@pytest.mark.parametrize('cpu,memory', [('max 100000', str(2**31)), ('500000 100000', str(2**31)),
    ('400000 100000', 'max'), ('400000 100000', str(2**31 + 1)), ('-1 100000', str(2**31)),
    ('400000 0', str(2**31)), ('bad', str(2**31))])
def test_unbounded_or_excess_resources_refuse(tmp_path, cpu, memory):
    (tmp_path / 'cpu.max').write_text(cpu); (tmp_path / 'memory.max').write_text(memory)
    with pytest.raises(prep.Refusal, match='resource_fence_required'):
        prep.guard_resources(cgroup_root=tmp_path)


def test_actual_finite_resource_limits_are_accepted(tmp_path):
    (tmp_path / 'cpu.max').write_text('400000 100000'); (tmp_path / 'memory.max').write_text(str(2**31))
    prep.guard_resources(cgroup_root=tmp_path)


def test_mounted_operator_env_refuses_before_settings(monkeypatch, tmp_path):
    import app.config as config
    (tmp_path / '.env').write_text('synthetic-not-read')
    monkeypatch.setattr(config, 'ROOT_DIR', tmp_path)
    monkeypatch.setattr(config, 'Settings', lambda **kw: pytest.fail('Settings must not be constructed'))
    with pytest.raises(prep.Refusal, match='operator_env_mount_forbidden'):
        prep.load_runtime()


class Db(_FakeReadOnlyDb):
    def __init__(self, rows):
        super().__init__(rows); self.rollbacks = 0
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        return False
    async def rollback(self):
        self.rollbacks += 1
    async def commit(self):
        pytest.fail('read-only preparation cannot commit')


@dataclass
class Binding:
    document_id: UUID
    content_revision_id: UUID
    subject_id: UUID
    source_sha256: str
    page_count: int


def runtime_for(cases, rows, scope, *, failure=None, query=None, source_change=None):
    from app.ai.source_navigation import navigation_query_v4
    calls = {'authorize': [], 'retrieve': [], 'query': [], 'visual': []}
    by_case = list(cases.values())
    class Retriever:
        @staticmethod
        async def authorize(db, **kwargs):
            case = by_case[len(calls['authorize'])]
            calls['authorize'].append(kwargs)
            return Bound(case)
    class Bound:
        def __init__(self, case):
            self.case = case
            self.scope = SimpleNamespace(corpus_revision=scope.corpus_revision,
                                         embedding_space_hash=scope.embedding_space_hash)
            if failure == 'scope':
                self.scope.corpus_revision += 1
        async def retrieve(self, embedding, **kwargs):
            calls['retrieve'].append((embedding, kwargs))
            if failure == 'retrieve':
                raise RuntimeError('sensitive internal value not printable')
            return SimpleNamespace(chunks=(SimpleNamespace(document_id=UUID(self.case['document_id']),
                page_number=self.case['page_number']),))
        async def retrieve_lexical(self):
            pytest.fail('fresh vectors must use actual hybrid path')
    def navigation(question, history):
        calls['query'].append((question, history))
        return navigation_query_v4(question, history) if query is None else query(question, history)
    async def pool(question, chunks, bound):
        case = bound.case
        source = SimpleNamespace(document_id=UUID(case['document_id']),
            content_revision_id=UUID(case['content_revision_id']), index_revision_id=UUID(case['index_revision_id']),
            page_number=case['page_number'], corpus_revision=scope.corpus_revision,
            embedding_space_hash=scope.embedding_space_hash)
        if source_change:
            source_change(source)
        content = rows[(case['document_id'], case['page_number'])]['page_text']
        return SimpleNamespace(selections=(SimpleNamespace(source=source, source_kind='canonical_page',
            page_content=content, start_offset=0, end_offset=len(content), quote=content),))
    async def visual(db, **kwargs):
        calls['visual'].append(kwargs)
        if failure == 'visual':
            raise RuntimeError('private response detail')
        item = kwargs['selections'][0]; case = by_case[len(calls['visual']) - 1]
        return SimpleNamespace(request={'question': kwargs['question'], 'id': 'S01'},
            bindings=(Binding(item.source.document_id, item.source.content_revision_id, UUID(scope.subject_id),
                case['original_pdf_sha256'], case['original_pdf_page_count']),))
    return SimpleNamespace(space_hash=scope.embedding_space_hash, settings=object(), navigation_query=navigation,
        retriever=Retriever, retrieval_policy=SimpleNamespace(max_results=5), candidate_pool=pool,
        visual_prepare=visual), calls


def execution_fixture(monkeypatch, tmp_path, **runtime_updates):
    inputs = fixture(monkeypatch)
    gold, source, packet, scope, _ = inputs
    parsed_gold, cases, _, _ = validate(inputs)
    _, rows = _synthetic()
    for row in rows.values():
        row['active_embedding_space_hash'] = scope.embedding_space_hash
    private = tmp_path / 'private'; private.mkdir(mode=0o700)
    paths = [private / name for name in ('gold.json', 'source.json', 'vectors.json')]
    for path, raw in zip(paths, (gold, source, packet), strict=True):
        path.write_bytes(raw); path.chmod(0o600)
    args = argparse.Namespace(stage1=paths[0], source_snapshot=paths[1], vectors=paths[2],
        stage1_sha256=sha256(gold).hexdigest(), source_sha256=sha256(source).hexdigest(),
        vectors_sha256=sha256(packet).hexdigest(), output=private / 'prepared.json',
        expected_database='cardchemy', **vars(scope))
    runtime, calls = runtime_for(cases, rows, scope, **runtime_updates)
    db = Db(rows)
    return args, runtime, db, calls


@pytest.mark.asyncio
async def test_read_only_hybrid_preparation_preserves_complete_roster_and_local_history(monkeypatch, tmp_path):
    args, runtime, db, calls = execution_fixture(monkeypatch, tmp_path)
    report = await prep.execute(args, environment=environment(), root=tmp_path,
                                runtime=runtime, session_factory=lambda: db)
    packet = json.loads(args.output.read_bytes())
    assert report['case_count'] == report['gold_in_pool'] == report['gold_in_initial'] == 12
    assert report['forms'] == {'direct': 4, 'paraphrase': 4, 'followup': 4}
    assert report['provider_calls'] == report['database_writes'] == report['automatic_retries'] == 0
    assert report['release_gate_passed'] is False
    assert report['snapshot_sha256'] == sha256(args.output.read_bytes()).hexdigest()
    assert packet['policy'] == prep.POLICY and packet['contract'] == prep.CONTRACT
    assert packet['vectors_sha256'] == args.vectors_sha256 and len(packet['cases']) == 12
    assert len(calls['authorize']) == len(calls['retrieve']) == len(calls['visual']) == 12
    assert all(vector == (1.,) + (0.,) * 1535 for vector, _ in calls['retrieve'])
    assert all(call['principal'].id == UUID(args.principal_id)
               and call['subject_id'] == UUID(args.subject_id) for call in calls['authorize'])
    assert all(history == () for _, history in calls['query'][:8])
    assert all(history == (('user', 'Which page is in view?'),) for _, history in calls['query'][8:])
    assert all(call['question'] == row['question'] for call, row in zip(calls['visual'], packet['cases'], strict=True))
    assert 'Which page is in view?' not in json.dumps([row['request'] for row in packet['cases']])
    assert all(row['candidates'][0]['runtime_id'] == 'S01' for row in packet['cases'])
    assert 'Synthetic page' not in json.dumps(report) and args.subject_id not in json.dumps(report)
    assert db.rollbacks == 1
    assert db.calls[0][0] == 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'
    assert all(sql.startswith(('SET ', '\nWITH authorized_subject')) for sql, _ in db.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['scope', 'retrieve', 'visual'])
async def test_failures_rollback_without_partial_output_or_retry(monkeypatch, tmp_path, failure):
    args, runtime, db, calls = execution_fixture(monkeypatch, tmp_path, failure=failure)
    with pytest.raises((prep.Refusal, RuntimeError)):
        await prep.execute(args, environment=environment(), root=tmp_path,
                           runtime=runtime, session_factory=lambda: db)
    assert db.rollbacks == 1 and not args.output.exists()
    assert len(calls['authorize']) == 1


@pytest.mark.asyncio
async def test_gold_page_change_in_current_sql_snapshot_refuses(monkeypatch, tmp_path):
    args, runtime, db, calls = execution_fixture(monkeypatch, tmp_path)
    next(iter(db.rows.values()))['page_text'] = 'changed canonical text'
    with pytest.raises(prep.snapshot.Refusal, match='gold_page_changed'):
        await prep.execute(args, environment=environment(), root=tmp_path,
                           runtime=runtime, session_factory=lambda: db)
    assert db.rollbacks == 1 and not args.output.exists() and not calls['authorize']


@pytest.mark.asyncio
@pytest.mark.parametrize('field,value', [('document_id', UUID(int=500)),
    ('content_revision_id', UUID(int=501)), ('index_revision_id', UUID(int=502)),
    ('corpus_revision', 100), ('embedding_space_hash', 'f' * 64)])
async def test_candidate_revision_subject_scope_cannot_drift(monkeypatch, tmp_path, field, value):
    args, runtime, db, calls = execution_fixture(monkeypatch, tmp_path,
        source_change=lambda source: setattr(source, field, value))
    with pytest.raises(prep.Refusal, match='candidate_binding_invalid'):
        await prep.execute(args, environment=environment(), root=tmp_path,
                           runtime=runtime, session_factory=lambda: db)
    assert not calls['visual'] and not args.output.exists() and db.rollbacks == 1


@pytest.mark.asyncio
async def test_unresolved_followup_is_retained_without_retrieval_or_visual_request(monkeypatch, tmp_path):
    args, runtime, db, calls = execution_fixture(monkeypatch, tmp_path, query=lambda q, h: None)
    result = await prep.execute(args, environment=environment(), root=tmp_path,
                                runtime=runtime, session_factory=lambda: db)
    rows = json.loads(args.output.read_bytes())['cases']
    assert result['clarification_needed'] == len(rows) == 12
    assert not calls['authorize'] and all(row['request'] is None and row['candidates'] == [] for row in rows)


@pytest.mark.asyncio
async def test_whole_run_deadline_rolls_back_and_never_writes_output(monkeypatch, tmp_path):
    args, runtime, db, _ = execution_fixture(monkeypatch, tmp_path)
    monkeypatch.setattr(prep, 'MAX_SECONDS', .02)
    async def slow(*args, **kwargs):
        await asyncio.sleep(1)
    runtime.visual_prepare = slow
    with pytest.raises(TimeoutError):
        await prep.execute(args, environment=environment(), root=tmp_path,
                           runtime=runtime, session_factory=lambda: db)
    assert db.rollbacks == 1 and not args.output.exists()


@pytest.mark.asyncio
async def test_cancellation_rolls_back_and_leaves_no_partial_artifact(monkeypatch, tmp_path):
    args, runtime, db, _ = execution_fixture(monkeypatch, tmp_path)
    entered = asyncio.Event()
    async def pending(*args, **kwargs):
        entered.set()
        await asyncio.Future()
    runtime.visual_prepare = pending
    task = asyncio.create_task(prep.execute(args, environment=environment(), root=tmp_path,
                                            runtime=runtime, session_factory=lambda: db))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert db.rollbacks == 1 and not args.output.exists()


@pytest.mark.asyncio
async def test_input_swap_during_preparation_refuses_output(monkeypatch, tmp_path):
    args, runtime, db, _ = execution_fixture(monkeypatch, tmp_path)
    original = runtime.visual_prepare
    async def swapped(*items, **kwargs):
        result = await original(*items, **kwargs)
        args.vectors.write_bytes(b'changed input bytes')
        return result
    runtime.visual_prepare = swapped
    with pytest.raises(prep.snapshot.Refusal, match='input_changed'):
        await prep.execute(args, environment=environment(), root=tmp_path,
                           runtime=runtime, session_factory=lambda: db)
    assert not args.output.exists() and db.rollbacks == 1


@pytest.mark.asyncio
async def test_oversized_output_refuses_after_rollback(monkeypatch, tmp_path):
    args, runtime, db, _ = execution_fixture(monkeypatch, tmp_path)
    monkeypatch.setattr(prep, 'MAX_OUTPUT_BYTES', 100)
    with pytest.raises(prep.Refusal, match='output_too_large'):
        await prep.execute(args, environment=environment(), root=tmp_path,
                           runtime=runtime, session_factory=lambda: db)
    assert db.rollbacks == 1 and not args.output.exists()


@pytest.mark.asyncio
async def test_encoding_cannot_publish_a_result_after_the_deadline(monkeypatch, tmp_path):
    args, runtime, db, _ = execution_fixture(monkeypatch, tmp_path)
    clock = [0.]
    monkeypatch.setattr(prep, 'perf_counter', lambda: clock[0])
    original = prep.canonical
    def late_encode(body):
        encoded = original(body)
        clock[0] = prep.MAX_SECONDS + 1
        return encoded
    monkeypatch.setattr(prep, 'canonical', late_encode)
    with pytest.raises(prep.Refusal, match='time_budget_exceeded'):
        await prep.execute(args, environment=environment(), root=tmp_path,
                           runtime=runtime, session_factory=lambda: db)
    assert db.rollbacks == 1 and not args.output.exists()


@pytest.mark.asyncio
async def test_late_fsync_result_is_removed_instead_of_reported(monkeypatch, tmp_path):
    args, runtime, db, _ = execution_fixture(monkeypatch, tmp_path)
    clock = [0.]
    monkeypatch.setattr(prep, 'perf_counter', lambda: clock[0])
    original = prep.write_exclusive
    def late_write(path, body):
        original(path, body)
        clock[0] = prep.MAX_SECONDS + 1
    monkeypatch.setattr(prep, 'write_exclusive', late_write)
    with pytest.raises(prep.Refusal, match='time_budget_exceeded'):
        await prep.execute(args, environment=environment(), root=tmp_path,
                           runtime=runtime, session_factory=lambda: db)
    assert db.rollbacks == 1 and not args.output.exists()


def test_exclusive_output_cannot_overwrite_an_existing_artifact(tmp_path):
    output = tmp_path / 'existing.json'; output.write_bytes(b'preserved')
    with pytest.raises(FileExistsError):
        prep.write_exclusive(output, b'new')
    assert output.read_bytes() == b'preserved'
