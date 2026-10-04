"""Keyless private-v6 current-question vector preparation and native transport."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import prepare_private_query_vectors_v6 as builder
from test_private_source_gold_v4_snapshot import _bytes, _synthetic, _uuid
from test_private_query_vector_builder import settings
from app.models.knowledge import embedding_space_hash


def fixture(monkeypatch, *, source_change=None):
    current = settings(rag_embedding_requests_per_minute=1000)
    gold, rows = _synthetic()
    gold['scope']['embedding_space_hash'] = embedding_space_hash(current.rag_embedding_space_identity)
    raw = _bytes(gold)
    pages = []
    for row in rows.values():
        pages.append({key: row[key] for key in (
            'document_id', 'content_revision_id', 'index_revision_id', 'page_number',
            'page_text', 'original_pdf_sha256', 'original_pdf_page_count', 'corpus_revision',
        )} | {'embedding_space_hash': gold['scope']['embedding_space_hash'],
             'current_authorized': True, 'published': True, 'index_ready': True})
    source = {'schema': builder.snapshot.SCHEMA, 'stage1_sha256': sha256(raw).hexdigest(),
              'principal_id': _uuid(100), 'subject_id': _uuid(101),
              'scope': gold['scope'], 'authorized_pages': pages}
    if source_change:
        source_change(source)
    source_raw = _bytes(source)
    monkeypatch.setattr(builder.snapshot, 'FROZEN_STAGE1_SHA256', sha256(raw).hexdigest())
    monkeypatch.setattr(builder, 'SOURCE_SNAPSHOT_SHA', sha256(source_raw).hexdigest())
    questions = tuple((row['case_id'], row['question']) for row in gold['cases'])
    monkeypatch.setattr(builder, 'QUERY_ROSTER_SHA', sha256(builder.canonical(questions)).hexdigest())
    return raw, source_raw, current


def approved(monkeypatch, directory):
    token = str(uuid4())
    monkeypatch.setattr(builder, 'LIVE_AUTHORIZED', True)
    monkeypatch.setattr(builder, 'APPROVAL_ID', token)
    monkeypatch.setenv(builder.APPROVAL_ENV, token)
    monkeypatch.setattr(builder, 'LEDGER', directory / 'ledger')
    return token


def test_default_cli_has_no_settings_input_or_provider_access():
    result = subprocess.run([sys.executable, str(Path(builder.__file__))],
                            capture_output=True, text=True, check=True)
    report = json.loads(result.stdout)
    assert report == {'schema': builder.SCHEMA, 'status': 'unexecuted',
                      'provider_calls': 0, 'database_reads': 0, 'live_authorized': False}
    assert not result.stderr


def test_no_execute_cli_route():
    result = subprocess.run([sys.executable, str(Path(builder.__file__)), '--execute'],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert 'unrecognized arguments' in result.stderr


def test_prepared_manifest_omits_previous_turn_source_and_identity(monkeypatch):
    raw, source, _ = fixture(monkeypatch)
    inputs = builder.prepare(raw, source)
    packet = builder.manifest(inputs)
    assert packet['endpoint'].endswith(':batchEmbedContents')
    assert len(packet['queries']) == 12
    assert packet['task'] == 'QUESTION_ANSWERING' and packet['dimensions'] == 1536
    assert not {'principal_id', 'subject_id', 'authorized_pages', 'previous_turn'} & packet.keys()
    text = json.dumps(packet)
    assert 'Which page is in view?' not in text and 'exact canonical content' not in text
    report = builder.aggregate(inputs)
    assert 0 < report['estimated_input_tokens'] <= 512
    assert report['provider_calls'] == report['database_reads'] == report['database_writes'] == 0
    assert report['release_gate_passed'] is False
    assert not any(question in json.dumps(report) for _, question in inputs.questions)


@pytest.mark.parametrize('kind', ['gold', 'source'])
def test_changed_pinned_bytes_refuse(monkeypatch, kind):
    raw, source, _ = fixture(monkeypatch)
    if kind == 'gold':
        raw += b' '
    else:
        source += b' '
    with pytest.raises(builder.Refusal, match='input_changed'):
        builder.prepare(raw, source)


@pytest.mark.parametrize('field,value', [
    ('current_authorized', False), ('published', False), ('index_ready', False),
    ('corpus_revision', 8), ('page_text', 'changed page'),
    ('original_pdf_sha256', 'a' * 64), ('index_revision_id', _uuid(50)),
])
def test_source_integrity_required_before_preparing(monkeypatch, field, value):
    raw, source, _ = fixture(monkeypatch,
        source_change=lambda s: s['authorized_pages'][0].update({field: value}))
    with pytest.raises((builder.Refusal, builder.snapshot.Refusal)):
        builder.prepare(raw, source)


@pytest.mark.parametrize('change', [
    lambda q: replace(q, estimated_input_tokens=True),
    lambda q: replace(q, estimated_input_tokens=q.estimated_input_tokens + 1),
    lambda q: replace(q, questions=q.questions[:-1]),
    lambda q: replace(q, questions=q.questions[::-1]),
    lambda q: replace(q, questions=(('T01', 'Injected private source'),) + q.questions[1:]),
    lambda q: replace(q, embedding_space_hash='invalid'),
    lambda q: replace(q, questions=((True, q.questions[0][1]),) + q.questions[1:]),
])
def test_forged_prepared_objects_refuse_before_dispatch(monkeypatch, change):
    raw, source, current = fixture(monkeypatch)
    inputs = change(builder.prepare(raw, source))
    with pytest.raises(builder.Refusal):
        builder.bounded_settings(current, inputs)


@pytest.mark.parametrize('change', [
    {'rag_embedding_provider_enabled': False}, {'rag_embedding_provider': 'openai_compatible'},
    {'rag_embedding_model': 'gemini-embedding-2'}, {'rag_embedding_dimensions': 3072},
    {'rag_embedding_base_url': 'https://other.example'},
    {'rag_embedding_format_version': 'gemini2_qa_section_v1'},
])
def test_active_profile_must_match(monkeypatch, change):
    raw, source, current = fixture(monkeypatch)
    with pytest.raises(builder.Refusal, match='profile_incompatible'):
        builder.bounded_settings(current.model_copy(update=change), builder.prepare(raw, source))


@pytest.mark.asyncio
@pytest.mark.parametrize('missing', ['live', 'id', 'environment'])
async def test_each_fresh_authorization_binding_is_required(monkeypatch, tmp_path, missing):
    raw, source, current = fixture(monkeypatch)
    token = approved(monkeypatch, tmp_path)
    if missing == 'live':
        monkeypatch.setattr(builder, 'LIVE_AUTHORIZED', False)
    elif missing == 'id':
        monkeypatch.setattr(builder, 'APPROVAL_ID', str(uuid4()))
    else:
        monkeypatch.delenv(builder.APPROVAL_ENV)
    with pytest.raises(builder.Refusal, match='fresh_authorization_required'):
        await builder.build_packet(builder.prepare(raw, source), current,
            output=tmp_path / 'vectors.json', approval_id=token,
            provider_factory=lambda _: pytest.fail('provider construction prohibited'))
    assert not (tmp_path / 'ledger').exists()


@pytest.mark.asyncio
async def test_native_sdk_exact_endpoint_one_current_question_each(monkeypatch, tmp_path):
    raw, source, current = fixture(monkeypatch)
    inputs = builder.prepare(raw, source)
    token = approved(monkeypatch, tmp_path)
    import build_private_query_vectors as native
    calls = []

    def handler(request):
        calls.append(request)
        assert request.method == 'POST' and str(request.url) == builder.ENDPOINT
        body = json.loads(request.content)
        assert len(body['requests']) == 1
        row = body['requests'][0]
        assert row['taskType'] == builder.TASK and row['outputDimensionality'] == 1536
        assert row['content']['parts'] == [{'text': inputs.questions[len(calls) - 1][1]}]
        assert 'Which page is in view?' not in request.content.decode()
        return httpx.Response(200, json={'embeddings': [{'values': [1.0] + [0.0] * 1535}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        output = tmp_path / 'vectors.json'
        report = await builder.build_packet(inputs, current, output=output, approval_id=token,
            provider_factory=lambda bounded: native.make_native_query_provider(bounded, http_client=transport))
    assert report['status'] == 'completed_private_packet', report
    assert report['provider_calls'] == len(calls) == 12 and report['retries'] == 0
    assert report['actual_provider_cost_unknown'] is True
    assert len(json.loads(output.read_bytes())['vectors']) == 12
    assert len(list(tmp_path.glob('query-v6-*-receipt.json'))) == 12
    assert report['packet_sha256'] == sha256(output.read_bytes()).hexdigest()
    assert not any(q in json.dumps(report) for _, q in inputs.questions)
    other = tmp_path / 'new-output'
    other.mkdir()
    with pytest.raises(builder.snapshot.Refusal, match='output_exists'):
        await builder.build_packet(inputs, current, output=other / 'vectors.json', approval_id=token,
            provider_factory=lambda _: pytest.fail('used approval cannot dispatch'))


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['http', 'shape', 'zero', 'nan'])
async def test_partial_failure_keeps_checkpoints_and_never_retries(monkeypatch, tmp_path, failure):
    raw, source, current = fixture(monkeypatch)
    token = approved(monkeypatch, tmp_path)
    import build_private_query_vectors as native
    calls = []

    def handler(request):
        calls.append(request)
        values = [1.0] + [0.0] * 1535
        if len(calls) == 3:
            if failure == 'http':
                return httpx.Response(429, json={'error': {'code': 429, 'message': 'private detail'}})
            if failure == 'shape':
                values = [1.0]
            elif failure == 'zero':
                values = [0.0] * 1536
            elif failure == 'nan':
                # JSON-safe nonnumeric values are also rejected by the native float boundary.
                values[0] = 'not-a-number'
        return httpx.Response(200, json={'embeddings': [{'values': values}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        output = tmp_path / 'vectors.json'
        report = await builder.build_packet(builder.prepare(raw, source), current,
            output=output, approval_id=token,
            provider_factory=lambda bounded: native.make_native_query_provider(bounded, http_client=transport))
    assert report['status'] == 'stopped'
    assert report['provider_calls'] == len(calls) == 3
    assert report['valid_checkpoints'] == 2 and report['automatic_retries'] == 0
    assert report['failed_attempt_cost_unknown'] is True
    assert not output.exists() and len(list(tmp_path.glob('query-v6-*-receipt.json'))) == 2
    assert len(list((tmp_path / 'ledger').glob('*.used'))) == 1
    assert 'private detail' not in json.dumps(report)


def test_cli_preflight_creates_only_private_current_question_manifest(monkeypatch, tmp_path, capsys):
    raw, source, _ = fixture(monkeypatch)
    gold_path, source_path = tmp_path / 'gold.json', tmp_path / 'sources.json'
    gold_path.write_bytes(raw)
    source_path.write_bytes(source)
    output = tmp_path / 'input-manifest.json'
    monkeypatch.setattr(sys, 'argv', [str(builder.__file__), '--preflight-inputs',
        '--stage1', str(gold_path), '--source-snapshot', str(source_path), '--output', str(output)])
    assert builder.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report['case_count'] == 12 and report['provider_calls'] == 0
    assert output.exists() and not list(tmp_path.glob('query-v6-*-receipt.json'))
    assert builder.main() == 2  # Existing private artifacts are preserved.
    assert json.loads(capsys.readouterr().out)['status'] == 'preflight_refused'
