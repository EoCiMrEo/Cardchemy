"""Synthetic/keyless admission, isolation and no-replay contracts for v6 caller."""
from __future__ import annotations

from hashlib import sha256
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import run_private_query_vectors_v6 as caller
import prepare_visual_page_source_input_v1 as resource
from test_private_query_vectors_v6 import fixture as vector_fixture


def synthetic(monkeypatch, tmp_path, *, live=False):
    stage_raw, source_raw, current = vector_fixture(monkeypatch)
    monkeypatch.setattr(caller.builder.snapshot, '_temp_root', lambda: tmp_path)
    folder = tmp_path / 'inputs'
    folder.mkdir(mode=0o700)
    stage, source, profile = (folder / name for name in ('gold.json', 'source.json', 'profile.json'))
    stage.write_bytes(stage_raw)
    source.write_bytes(source_raw)
    profile_contract = {'schema': caller.PROFILE_SCHEMA,
        'space_revision': current.rag_embedding_space_revision,
        'quota_bucket': current.rag_embedding_quota_bucket,
        'requests_per_minute': current.rag_embedding_requests_per_minute,
        'input_tokens_per_minute': current.rag_embedding_input_tokens_per_minute,
        'rate_limit_safety_percent': current.rag_embedding_rate_limit_safety_percent}
    profile_raw = caller.canonical(profile_contract)
    profile.write_bytes(profile_raw)
    token = str(uuid4())
    monkeypatch.setattr(caller, 'LIVE_AUTHORIZED', live)
    monkeypatch.setattr(caller, 'APPROVAL_ID', token if live else None)
    monkeypatch.setattr(caller, 'LEDGER', tmp_path / 'ledger')
    if live:
        monkeypatch.setenv(caller.APPROVAL_ENV, token)
    pins = {'synthetic-code.py': 'a' * 64}
    monkeypatch.setattr(caller, 'code_hashes', lambda: dict(pins))
    output = tmp_path / 'vectors'
    packet = caller.prepare_approval(stage1=stage, source=source, profile=profile,
        profile_sha=sha256(profile_raw).hexdigest(), approval_id=token, output_dir=output)
    approval = folder / 'approval.json'
    raw = caller.canonical(packet)
    approval.write_bytes(raw)
    return SimpleNamespace(packet=packet, approval=approval, sha=sha256(raw).hexdigest(), output=output,
                           stage=stage, source=source, profile=profile, token=token, pins=pins, current=current)


def rewrite(case):
    raw = caller.canonical(case.packet)
    case.approval.write_bytes(raw)
    case.sha = sha256(raw).hexdigest()


def forbidden(*_args, **_kwargs):
    pytest.fail('unexpected sensitive operation')


def test_default_cli_is_inert():
    result = subprocess.run([sys.executable, str(Path(caller.__file__))],
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == {'schema': caller.SCHEMA, 'status': 'unexecuted',
        'provider_calls': 0, 'database_reads': 0, 'database_writes': 0, 'live_authorized': False}
    assert not result.stderr


def test_default_main_ignores_unspecified_input_without_reading(monkeypatch, capsys):
    monkeypatch.setattr(caller, '_read', forbidden)
    monkeypatch.setattr(caller, 'scoped_settings', forbidden)
    monkeypatch.setattr(caller, 'supervise', forbidden)
    assert caller.main(['--stage1', 'not-a-real-private-path']) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'unexecuted'


def test_keyless_admission_binds_all_twelve_and_omits_questions(monkeypatch, tmp_path):
    case = synthetic(monkeypatch, tmp_path)
    monkeypatch.setattr(caller, 'scoped_settings', forbidden)
    monkeypatch.setattr(caller, 'child_env', forbidden)
    packet, inputs = caller.admit(case.approval, case.sha, output_dir=case.output)
    assert len(inputs.questions) == 12
    assert packet['estimated_input_tokens'] <= 512
    assert packet['live_authorized'] is False
    for _, question in inputs.questions:
        assert question not in caller.canonical(packet).decode()
    assert set(packet['guards']) >= {'max_calls', 'batch_size', 'automatic_retries', 'root_env_read'}
    assert packet['guards'] == caller.guards()
    assert not case.output.exists()
    assert not caller.LEDGER.exists()


def test_keyless_cli_preflight_reports_aggregates_only(monkeypatch, tmp_path, capsys):
    case = synthetic(monkeypatch, tmp_path)
    assert caller.main(['--preflight', '--approval-file', str(case.approval),
                        '--approval-sha', case.sha, '--output-dir', str(case.output)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'preflight_passed'
    assert report['provider_calls'] == report['database_reads'] == 0
    assert report['case_count'] == 12
    assert str(case.approval) not in json.dumps(report)


@pytest.mark.parametrize('field,value', [
    ('schema', 'unknown'), ('live_authorized', True), ('stage1_sha256', 'a' * 64),
    ('source_sha256', 'b' * 64), ('embedding_space_hash', 'c' * 64),
    ('question_roster_sha256', 'd' * 64), ('estimated_input_tokens', 1),
    ('guards', {}), ('code_sha256', {}), ('extra', 'forbidden'),
])
def test_changed_approval_refuses_before_credentials(monkeypatch, tmp_path, field, value):
    case = synthetic(monkeypatch, tmp_path)
    case.packet[field] = value
    rewrite(case)
    monkeypatch.setattr(caller, 'scoped_settings', forbidden)
    with pytest.raises((caller.builder.Refusal, caller.builder.snapshot.Refusal)):
        caller.admit(case.approval, case.sha, output_dir=case.output)


@pytest.mark.parametrize('name', ['stage', 'source', 'profile', 'code', 'approval'])
def test_changed_bound_input_or_code_refuses(monkeypatch, tmp_path, name):
    case = synthetic(monkeypatch, tmp_path)
    if name == 'code':
        case.pins['synthetic-code.py'] = 'b' * 64
    else:
        getattr(case, name).write_bytes(b'{}')
    with pytest.raises((caller.builder.Refusal, caller.builder.snapshot.Refusal)):
        caller.admit(case.approval, case.sha, output_dir=case.output)


@pytest.mark.parametrize('field,value', [
    ('schema', 'bad'), ('space_revision', 'other'), ('space_revision', ''),
    ('quota_bucket', ''), ('quota_bucket', 'secret\nvalue'), ('api_key', 'never-allowed'),
    ('requests_per_minute', True), ('requests_per_minute', 0),
    ('input_tokens_per_minute', 511), ('rate_limit_safety_percent', 0),
    ('rate_limit_safety_percent', 101),
])
def test_profile_closed_identity_and_budget(monkeypatch, tmp_path, field, value):
    case = synthetic(monkeypatch, tmp_path)
    profile = dict(case.packet['profile_contract'], **{field: value})
    with pytest.raises(caller.builder.Refusal, match='profile_incompatible'):
        caller.validate_profile(profile, case.packet['embedding_space_hash'])


def test_profile_hash_matches_production_identity(monkeypatch, tmp_path):
    case = synthetic(monkeypatch, tmp_path)
    from app.models.knowledge import embedding_space_hash
    assert caller.validate_profile(case.packet['profile_contract'],
        embedding_space_hash(case.current.rag_embedding_space_identity)) == case.packet['profile_contract']


@pytest.mark.parametrize('missing', ['flag', 'uuid', 'token'])
def test_fresh_authorization_requires_all_three(monkeypatch, tmp_path, missing):
    case = synthetic(monkeypatch, tmp_path, live=True)
    if missing == 'flag':
        monkeypatch.setattr(caller, 'LIVE_AUTHORIZED', False)
    elif missing == 'uuid':
        monkeypatch.setattr(caller, 'APPROVAL_ID', str(uuid4()))
    else:
        monkeypatch.delenv(caller.APPROVAL_ENV)
    with pytest.raises(caller.builder.Refusal, match='fresh_authorization_required'):
        caller.claim(case.packet, case.sha, role='launch')
    assert not caller.LEDGER.exists()


def test_central_launch_claim_cannot_replay_in_another_directory(monkeypatch, tmp_path):
    case = synthetic(monkeypatch, tmp_path, live=True)
    caller.claim(case.packet, case.sha, role='launch')
    case.packet['output_dir'] = str(tmp_path / 'different-output')
    with pytest.raises(caller.builder.snapshot.Refusal, match='output_exists'):
        caller.claim(case.packet, case.sha, role='launch')


def test_worker_claim_requires_exact_launch_approval(monkeypatch, tmp_path):
    case = synthetic(monkeypatch, tmp_path, live=True)
    with pytest.raises(caller.builder.Refusal, match='launch_claim_missing'):
        caller.claim(case.packet, case.sha, role='worker')
    caller.claim(case.packet, case.sha, role='launch')
    with pytest.raises(caller.builder.Refusal, match='launch_claim_missing'):
        caller.claim(case.packet, 'a' * 64, role='worker')
    caller.claim(case.packet, case.sha, role='worker')
    with pytest.raises(caller.builder.snapshot.Refusal, match='output_exists'):
        caller.claim(case.packet, case.sha, role='worker')


def test_previous_component_claim_blocks_new_caller(monkeypatch, tmp_path):
    case = synthetic(monkeypatch, tmp_path, live=True)
    caller.LEDGER.mkdir()
    old = caller.LEDGER / ('.query-v6-' + sha256(caller.uuid4(case.token).bytes).hexdigest() + '.used')
    old.write_bytes(b'old-attempt')
    with pytest.raises(caller.builder.Refusal, match='previous_attempt_not_replayable'):
        caller.claim(case.packet, case.sha, role='launch')


def test_key_is_not_read_before_launch_claim(monkeypatch, tmp_path):
    case = synthetic(monkeypatch, tmp_path, live=True)
    class NoKeyRead(dict):
        def get(self, key, default=None):
            if key == caller.EMBEDDING_KEY_ENV:
                pytest.fail('key read before claim')
            return super().get(key, default)
    with pytest.raises(caller.builder.Refusal, match='launch_claim_missing'):
        caller.child_env(NoKeyRead(), approval_id=case.token)


def test_scrubbed_child_injects_only_embedding_role_and_ephemeral_prerequisites(monkeypatch, tmp_path):
    case = synthetic(monkeypatch, tmp_path, live=True)
    caller.claim(case.packet, case.sha, role='launch')
    source = {'RAG_EMBEDDING_API_KEY': 'synthetic-embedding-key', 'RAG_SOURCE_JUDGE_API_KEY': 'never',
              'FLASHCARD_AI_API_KEY': 'never', 'RAG_AI_API_KEY': 'never', 'SMTP_PASSWORD': 'never',
              'SECRET_KEY': 'operator-never', 'HTTP_PROXY': 'never', 'PYTHONPATH': 'never',
              'SystemRoot': 'C:\\Windows', 'TEMP': str(tmp_path), 'TMP': str(tmp_path)}
    env = caller.child_env(source, approval_id=case.token)
    assert env[caller.EMBEDDING_KEY_ENV] == 'synthetic-embedding-key'
    assert env[caller.APPROVAL_ENV] == case.token
    assert env['SECRET_KEY'] != source['SECRET_KEY']
    assert env['ENVIRONMENT'] == 'test'
    assert env['DATABASE_URL'] == 'sqlite+aiosqlite:///:memory:'
    assert not {'RAG_SOURCE_JUDGE_API_KEY', 'FLASHCARD_AI_API_KEY', 'RAG_AI_API_KEY',
                'SMTP_PASSWORD', 'HTTP_PROXY'} & env.keys()


def test_scoped_loader_uses_no_root_file_and_exact_bounded_native_profile(monkeypatch, tmp_path):
    case = synthetic(monkeypatch, tmp_path, live=True)
    caller.claim(case.packet, case.sha, role='launch')
    env = caller.child_env({'RAG_EMBEDDING_API_KEY': 'synthetic-embedding-key'}, approval_id=case.token)
    monkeypatch.setattr(os, 'environ', env)
    from app.config import Settings
    monkeypatch.setattr(Settings, 'model_config', dict(Settings.model_config, env_file=tmp_path / 'forbidden.env'))
    _, inputs = caller.admit(case.approval, case.sha, output_dir=case.output)
    current = caller.scoped_settings(case.packet['profile_contract'], inputs)
    assert current.rag_embedding_provider_enabled
    assert not current.rag_ask_enabled and not current.rag_source_judge_provider_enabled
    assert current.flashcard_ai_api_key is current.rag_ai_api_key is current.rag_source_judge_api_key is None
    assert current.rag_embedding_provider_max_retries == 0
    assert current.rag_embedding_batch_size == 1 and current.rag_embedding_provider_timeout_seconds == 30
    assert current.rag_embedding_max_input_tokens == 512
    assert current.rag_embedding_api_key.get_secret_value() == 'synthetic-embedding-key'


@pytest.mark.parametrize('name', ['RAG_AI_API_KEY', 'RAG_SOURCE_JUDGE_API_KEY', 'SMTP_PASSWORD', 'POSTGRES_PASSWORD'])
def test_scoped_loader_rejects_other_settings_roles_before_key_read(monkeypatch, tmp_path, name):
    case = synthetic(monkeypatch, tmp_path)
    _, inputs = caller.admit(case.approval, case.sha, output_dir=case.output)
    monkeypatch.setattr(os, 'environ', {'ENVIRONMENT': 'test', name: 'synthetic-forbidden'})
    with pytest.raises(caller.builder.Refusal, match='isolated_environment_required'):
        caller.scoped_settings(case.packet['profile_contract'], inputs)


def test_supervisor_reuses_immutable_assignment_and_hard_deadline(monkeypatch, tmp_path):
    case = synthetic(monkeypatch, tmp_path, live=True)
    import launch_visual_public_calibration_v5 as audited
    original = audited.CALLER, audited.MAX_SECONDS, audited.child_env
    captured = {}
    class Bound:
        def __init__(self, code, namespace):
            captured['code'], captured['namespace'] = code, namespace
        def __call__(self, approval, digest, output):
            assert caller._marker(case.token, 'launch').is_file()
            assert (approval, digest, output) == (case.approval, case.sha, case.output)
            output.mkdir()
            (output / 'aggregate.json').write_bytes(b'{"status":"synthetic_completed"}')
            output.with_name(output.name + '.supervisor-complete.json').write_bytes(
                caller.canonical({'approval_sha256': digest, 'exit_code': 0}))
    monkeypatch.setattr(caller.os, 'name', 'nt')
    monkeypatch.setattr(caller, 'FunctionType', Bound)
    caller.supervise(case.approval, case.sha, case.output)
    assert captured['code'] is audited.supervise.__code__
    assert captured['namespace']['MAX_SECONDS'] == 360
    assert captured['namespace']['CALLER'] == Path(caller.__file__).resolve()
    assert (audited.CALLER, audited.MAX_SECONDS, audited.child_env) == original
    source = inspect.getsource(audited.supervise)
    assert source.index('AssignProcessToJobObject(job, info.process)') < source.index('ResumeThread(info.thread)')
    assert '0x4 | 0x400 | 0x08000000' in source
    assert 'WaitForSingleObject(info.process, MAX_SECONDS * 1000)' in source
    assert 'kernel.TerminateJobObject(job, 2)' in source and 'kernel.CloseHandle(job)' in source


def resource_receipt(case, *, job=None, **changes):
    job = job or resource.RESOURCE_JOB_PREFIX + uuid4().hex
    receipt = {'worker_pid': os.getpid(), 'resource_job': job, 'cpus': 4, 'memory_bytes': 2147483648,
               'timeout_seconds': 360, 'approval_sha256': case.sha, 'kill_tree_on_close': True}
    receipt.update(changes)
    case.output.with_name(case.output.name + '.resource-process.json').write_bytes(caller.canonical(receipt))
    return job


def test_resource_pid_accepts_only_current_or_direct_windows_wrapper(monkeypatch):
    monkeypatch.setattr(caller.os, 'getpid', lambda: 200)
    monkeypatch.setattr(caller.os, 'getppid', lambda: 100)
    monkeypatch.setattr(caller.os, 'name', 'nt')
    assert caller.resource_worker_pid_matches(200)
    assert caller.resource_worker_pid_matches(100)
    for unrelated in (99, 201, -1, 0, True, '100', None):
        assert not caller.resource_worker_pid_matches(unrelated)
    monkeypatch.setattr(caller.os, 'name', 'posix')
    assert not caller.resource_worker_pid_matches(100)


@pytest.mark.skipif(os.name != 'nt', reason='Windows venv redirector contract')
def test_native_venv_redirector_pid_is_current_or_direct_parent():
    import subprocess
    code = ('import json,os,sys;sys.path.insert(0,sys.argv[1]);'
            'from run_private_query_vectors_v6 import resource_worker_pid_matches;'
            'print(json.dumps({"pid":os.getpid(),"parent":os.getppid(),'
            '"current_ok":resource_worker_pid_matches(os.getpid()),'
            '"parent_ok":resource_worker_pid_matches(os.getppid()),'
            '"unrelated_ok":resource_worker_pid_matches(-1)}))')
    process = subprocess.Popen([sys.executable, '-c', code, str(Path(caller.__file__).parent)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    stdout, stderr = process.communicate(timeout=15)
    assert process.returncode == 0 and not stderr
    receipt = json.loads(stdout)
    assert process.pid in (receipt['pid'], receipt['parent'])
    assert receipt['current_ok'] and receipt['parent_ok'] and not receipt['unrelated_ok']


@pytest.mark.asyncio
async def test_worker_claim_resource_and_source_gates_precede_factory(monkeypatch, tmp_path):
    case = synthetic(monkeypatch, tmp_path, live=True)
    caller.claim(case.packet, case.sha, role='launch')
    job = resource_receipt(case)
    monkeypatch.setattr(resource, '_inside_windows_job', lambda: True)
    seen = []
    def settings_factory(profile, inputs):
        assert caller._marker(case.token, 'worker').is_file()
        assert resource.RESOURCE_JOB_NAME is None
        assert inputs.embedding_space_hash == case.packet['embedding_space_hash']
        seen.append('factory')
        return case.current
    async def fake_build(inputs, settings, **kwargs):
        assert caller.builder.LIVE_AUTHORIZED and caller.builder.APPROVAL_ID == case.token
        assert caller.builder.LEDGER == caller.LEDGER
        assert len(inputs.questions) == 12 and kwargs['output'] == case.output / 'vectors.json'
        assert settings is case.current
        seen.append('build')
        return {'status': 'synthetic_completed', 'provider_calls': 0}
    monkeypatch.setattr(caller.builder, 'build_packet', fake_build)
    previous = caller.builder.LIVE_AUTHORIZED, caller.builder.APPROVAL_ID, caller.builder.LEDGER
    result = await caller.worker(case.approval, case.sha, case.output, job, settings_factory=settings_factory)
    assert result == {'status': 'synthetic_completed', 'provider_calls': 0}
    assert json.loads((case.output / 'aggregate.json').read_bytes()) == result
    assert seen == ['factory', 'build']
    assert (caller.builder.LIVE_AUTHORIZED, caller.builder.APPROVAL_ID, caller.builder.LEDGER) == previous


@pytest.mark.asyncio
async def test_worker_native_mock_transport_uses_twelve_exact_singleton_queries(monkeypatch, tmp_path):
    case = synthetic(monkeypatch, tmp_path, live=True)
    caller.claim(case.packet, case.sha, role='launch')
    job = resource_receipt(case)
    monkeypatch.setattr(resource, '_inside_windows_job', lambda: True)
    env = caller.child_env({'RAG_EMBEDDING_API_KEY': 'synthetic-only'}, approval_id=case.token)
    monkeypatch.setattr(os, 'environ', env)
    calls = []
    _, prepared = caller.admit(case.approval, case.sha, output_dir=case.output)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
    import build_private_query_vectors as native
    def handler(request):
        calls.append(request)
        assert request.method == 'POST' and str(request.url) == caller.builder.ENDPOINT
        wire = json.loads(request.content)
        assert len(wire['requests']) == 1
        row = wire['requests'][0]
        assert row['taskType'] == 'QUESTION_ANSWERING' and row['outputDimensionality'] == 1536
        assert row['content']['parts'] == [{'text': prepared.questions[len(calls) - 1][1]}]
        return httpx.Response(200, json={'embeddings': [{'values': [1.0] + [0.0] * 1535}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        report = await caller.worker(case.approval, case.sha, case.output, job,
            provider_factory=lambda settings: native.make_native_query_provider(settings, http_client=transport))
    assert report['status'] == 'completed_private_packet', report
    assert report['provider_calls'] == len(calls) == 12 and report['retries'] == 0
    assert json.loads((case.output / 'aggregate.json').read_bytes()) == report
    assert len(json.loads((case.output / 'vectors.json').read_bytes())['vectors']) == 12
    assert all(question not in json.dumps(report) for _, question in prepared.questions)
    assert len(list(caller.LEDGER.glob('*.used'))) == 3


@pytest.mark.asyncio
async def test_worker_native_failure_persists_only_safe_aggregate(monkeypatch, tmp_path):
    case = synthetic(monkeypatch, tmp_path, live=True)
    caller.claim(case.packet, case.sha, role='launch')
    job = resource_receipt(case)
    monkeypatch.setattr(resource, '_inside_windows_job', lambda: True)
    monkeypatch.setattr(os, 'environ', caller.child_env(
        {'RAG_EMBEDDING_API_KEY': 'synthetic-only'}, approval_id=case.token))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
    import build_private_query_vectors as native
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(503, json={'error': {'message': 'synthetic-do-not-persist-secret'}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        report = await caller.worker(case.approval, case.sha, case.output, job,
            provider_factory=lambda settings: native.make_native_query_provider(settings, http_client=transport))
    assert report['status'] == 'stopped' and report['provider_calls'] == len(calls) == 1
    assert report['failed_attempt_cost_unknown'] is True and report['automatic_retries'] == 0
    raw = (case.output / 'aggregate.json').read_bytes()
    assert json.loads(raw) == report
    assert b'synthetic-only' not in raw and b'do-not-persist' not in raw and b'embedding' not in raw
    assert not (case.output / 'vectors.json').exists()


@pytest.mark.parametrize('fault', ['job', 'pid', 'approval', 'memory', 'time', 'claim', 'source'])
@pytest.mark.asyncio
async def test_worker_failure_gates_never_read_credentials(monkeypatch, tmp_path, fault):
    case = synthetic(monkeypatch, tmp_path, live=True)
    if fault != 'claim':
        caller.claim(case.packet, case.sha, role='launch')
    receipt_changes = {'pid': {'worker_pid': -1}, 'approval': {'approval_sha256': 'f' * 64},
                       'memory': {'memory_bytes': 3 * 1024**3}, 'time': {'timeout_seconds': 361}}
    job = resource_receipt(case, **receipt_changes.get(fault, {}))
    monkeypatch.setattr(resource, '_inside_windows_job', lambda: fault != 'job')
    if fault == 'source':
        case.source.write_bytes(b'{}')
    with pytest.raises((caller.builder.Refusal, caller.builder.snapshot.Refusal)):
        await caller.worker(case.approval, case.sha, case.output, job, settings_factory=forbidden)
    assert resource.RESOURCE_JOB_NAME is None


def test_unapproved_execute_refuses_before_input_or_supervisor(monkeypatch, capsys):
    monkeypatch.setattr(caller, 'admit', forbidden)
    monkeypatch.setattr(caller, 'supervise', forbidden)
    assert caller.main(['--execute', '--approval-file', 'invalid', '--output-dir', 'invalid']) == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'refused'


def test_refusal_stdout_never_contains_internal_error(monkeypatch, capsys):
    def fail(*_args, **_kwargs):
        raise ValueError('synthetic-private-question/credential')
    monkeypatch.setattr(caller, 'admit', fail)
    assert caller.main(['--preflight', '--approval-file', 'invalid', '--output-dir', 'invalid']) == 1
    output = capsys.readouterr()
    assert 'synthetic-private' not in output.out and not output.err
