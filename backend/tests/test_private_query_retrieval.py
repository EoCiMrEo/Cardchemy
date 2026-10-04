"""No-quota contracts for the single-batch real-query diagnostic."""
import json
from dataclasses import replace
from pathlib import Path
import sys
from types import SimpleNamespace

import httpx
import pytest

scripts = Path(__file__).resolve().parents[2] / 'scripts'
sys.path.insert(0, str(scripts))
import evaluate_private_query_retrieval as diagnostic
from app.ai.providers import AIProviderError
from app.config import Settings
from app.models.knowledge import embedding_space_hash


def settings(**overrides):
    values = dict(environment='test', database_url='sqlite+aiosqlite:///:memory:',
        secret_key='test-only-secret-key-with-adequate-entropy-1234567890',
        generation_source_encryption_key='AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
        rag_enabled=True, rag_embedding_provider_enabled=True,
        rag_embedding_api_key='synthetic-test-key', rag_embedding_quota_bucket='test-project',
        rag_embedding_provider_max_retries=3)
    values.update(overrides)
    return Settings(_env_file=None, **values)


def authorize(monkeypatch):
    monkeypatch.setenv(diagnostic.AUTHORIZATION_ENV, diagnostic.APPROVAL_TOKEN)


@pytest.mark.asyncio
async def test_default_preflight_constructs_no_provider_or_transport(monkeypatch):
    context = SimpleNamespace()
    async def load(_settings):
        return context
    def forbidden(*args, **kwargs):
        raise AssertionError('preflight must not construct a provider')
    monkeypatch.setattr(diagnostic, 'load_context', load)
    monkeypatch.setattr(diagnostic, 'make_native_provider', forbidden)
    result = await diagnostic.evaluate(settings=settings())
    assert result['status'] == 'preflight_ready'
    assert result['provider_requests'] == result['answer_requests'] == result['database_writes'] == 0
    assert not result['knowledge_sent'] and not result['history_sent']
    assert result['estimated_input_tokens'] <= 512
    assert not any(question in json.dumps(result) for question in diagnostic.QUESTIONS)


@pytest.mark.asyncio
@pytest.mark.parametrize('argument,environment', [(None, None), (diagnostic.APPROVAL_TOKEN, None),
                                                ('wrong', diagnostic.APPROVAL_TOKEN)])
async def test_execute_missing_reviewed_process_authorization_precedes_context(monkeypatch, argument, environment):
    if environment is None:
        monkeypatch.delenv(diagnostic.AUTHORIZATION_ENV, raising=False)
    else:
        monkeypatch.setenv(diagnostic.AUTHORIZATION_ENV, environment)
    async def forbidden(_settings):
        raise AssertionError('authorization must precede context reads')
    monkeypatch.setattr(diagnostic, 'load_context', forbidden)
    with pytest.raises(diagnostic.Refusal, match='authorization_missing'):
        await diagnostic.evaluate(execute=True, approval_token=argument, settings=settings())


@pytest.mark.parametrize('overrides', [
    {'rag_embedding_model': 'legacy-model'}, {'rag_embedding_provider': 'openai_compatible'},
    {'rag_embedding_dimensions': 3072}, {'rag_embedding_base_url': 'https://unapproved.test'},
    {'rag_embedding_format_version': 'gemini2_qa_section_v1'}, {'rag_embedding_metric': 'dot'},
    {'rag_embedding_provider_enabled': False},
])
def test_bypassed_incompatible_profiles_are_rejected(overrides):
    with pytest.raises(diagnostic.Refusal, match='profile_incompatible'):
        diagnostic.bounded_profile(settings().model_copy(update=overrides))


def test_bounded_execution_keeps_task_space_and_admission_rates_unchanged():
    original = settings()
    bounded = diagnostic.bounded_profile(original)
    assert bounded.rag_embedding_space_identity == original.rag_embedding_space_identity
    assert embedding_space_hash(bounded.rag_embedding_space_identity) == embedding_space_hash(original.rag_embedding_space_identity)
    assert bounded.rag_embedding_provider_task_modes == ('RETRIEVAL_DOCUMENT', 'QUESTION_ANSWERING')
    assert bounded.rag_embedding_provider_max_retries == 0
    assert bounded.rag_embedding_provider_timeout_seconds == 30
    assert bounded.rag_embedding_input_cost_per_million_usd == diagnostic.CONSERVATIVE_INPUT_PRICE
    assert bounded.rag_embedding_requests_per_minute == original.rag_embedding_requests_per_minute
    assert bounded.rag_embedding_input_tokens_per_minute == original.rag_embedding_input_tokens_per_minute
    assert original.rag_embedding_provider_max_retries == 3


@pytest.mark.asyncio
async def test_native_sdk_makes_one_batch_request_with_six_query_task_inputs():
    requests = []
    def handler(request):
        requests.append(request)
        assert request.method == 'POST'
        assert str(request.url) == diagnostic.ENDPOINT + '/v1beta/models/gemini-embedding-001:batchEmbedContents'
        body = json.loads(request.content)
        assert len(body['requests']) == 6
        assert tuple(row['content']['parts'][0]['text'] for row in body['requests']) == diagnostic.QUESTIONS
        assert all(row['taskType'] == 'QUESTION_ANSWERING' and row['outputDimensionality'] == 1536 for row in body['requests'])
        assert all(set(row['content']) == {'parts', 'role'} and row['content']['role'] == 'user' for row in body['requests'])
        assert all(len(row['content']['parts']) == 1 and set(row['content']['parts'][0]) == {'text'} for row in body['requests'])
        return httpx.Response(200, json={'embeddings': [{'values': [1.0] + [0.0] * 1535} for _ in range(6)]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        provider, client = diagnostic.make_native_provider(diagnostic.bounded_profile(settings()), http_client=transport)
        try:
            response = await diagnostic.embed_authored_queries(provider)
            assert len(response.vectors) == 6
            assert provider.telemetry_snapshot().request_count == 1
            assert provider.telemetry_snapshot().retry_count == 0
            with pytest.raises(diagnostic.Refusal, match='provider_envelope_invalid'):
                await diagnostic.embed_authored_queries(provider)
        finally:
            await client.aio.aclose()
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [429, 500, 503])
async def test_transient_errors_do_not_retry_at_sdk_or_application_layers(status):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={'error': {'code': status, 'message': 'synthetic private response must not print'}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        provider, client = diagnostic.make_native_provider(diagnostic.bounded_profile(settings()), http_client=transport)
        try:
            with pytest.raises(AIProviderError):
                await diagnostic.embed_authored_queries(provider)
            assert provider.telemetry_snapshot().request_count == 1
            assert provider.telemetry_snapshot().retry_count == 0
        finally:
            await client.aio.aclose()
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_private_failure_and_raw_errors_cannot_enter_preflight_output(monkeypatch, capsys):
    marker = 'private-source-question-secret-identifier-marker'
    async def unavailable(_settings):
        raise RuntimeError(marker)
    monkeypatch.setattr(diagnostic, 'load_context', unavailable)
    result = await diagnostic.evaluate(settings=settings())
    assert result['status'] == 'diagnostic_unavailable'
    assert result['provider_requests'] == 0
    assert marker not in json.dumps(result)
    assert capsys.readouterr().out == ''
    assert capsys.readouterr().err == ''


@pytest.mark.asyncio
async def test_failed_physical_attempt_preserves_unknown_cost_without_raw_error(monkeypatch):
    authorize(monkeypatch)
    async def load(_settings):
        return SimpleNamespace()
    monkeypatch.setattr(diagnostic, 'load_context', load)
    provider = SimpleNamespace(telemetry_snapshot=lambda: SimpleNamespace(request_count=1, retry_count=0))
    client = SimpleNamespace(aio=SimpleNamespace(aclose=lambda: asyncio_sleep()))
    monkeypatch.setattr(diagnostic, 'make_native_provider', lambda _settings: (provider, client))
    async def fail(_provider):
        raise RuntimeError('private response must not print')
    monkeypatch.setattr(diagnostic, 'embed_authored_queries', fail)
    result = await diagnostic.evaluate(execute=True, approval_token=diagnostic.APPROVAL_TOKEN, settings=settings())
    assert result['provider_requests'] == 1 and result['retry_count'] == 0
    assert result['previous_attempt_cost'] == 'unknown'
    assert 'private response' not in json.dumps(result)


async def asyncio_sleep():
    return None


def test_authored_questions_are_pinned_exactly():
    assert diagnostic.QUESTIONS == (
        'What does BLEU stand for?', 'What does BLEU measure against a reference translation?',
        'What does cosine similarity measure?', 'What information do Bag-of-Words and TF-IDF ignore?',
        'What function does logistic regression use to produce probabilities?',
        'What is an application of topic modeling in legal or medical domains?',
    )


def test_changed_authored_query_identity_refuses_before_provider(monkeypatch):
    monkeypatch.setattr(diagnostic, 'QUESTIONS', ('changed',) * 6)
    with pytest.raises(diagnostic.Refusal, match='probe_identity_invalid'):
        diagnostic.bounded_profile(settings())


@pytest.mark.asyncio
async def test_redirect_is_never_followed_with_credentials():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(307, headers={'Location': 'https://unapproved.test/collect'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False) as transport:
        provider, client = diagnostic.make_native_provider(diagnostic.bounded_profile(settings()), http_client=transport)
        try:
            with pytest.raises(AIProviderError):
                await diagnostic.embed_authored_queries(provider)
        finally:
            await client.aio.aclose()
    assert len(calls) == 1 and calls[0].url.host == 'generativelanguage.googleapis.com'


@pytest.mark.asyncio
@pytest.mark.parametrize('count,dimensions', [(5, 1536), (7, 1536), (6, 1535), (6, 1537)])
async def test_malformed_vector_count_or_dimension_rejects_without_retry(count, dimensions):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={'embeddings': [{'values': [1.0] * dimensions} for _ in range(count)]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        provider, client = diagnostic.make_native_provider(diagnostic.bounded_profile(settings()), http_client=transport)
        try:
            with pytest.raises(AIProviderError, match='wrong number|invalid vector'):
                await diagnostic.embed_authored_queries(provider)
        finally:
            await client.aio.aclose()
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('changes', [
    {'max_retries': 1}, {'max_input_tokens': 1024}, {'timeout_seconds': 31},
    {'query_task_mode': 'RETRIEVAL_QUERY'}, {'input_cost_per_million_usd': .01},
    {'max_estimated_cost_usd': .1}, {'dimensions': 3072},
])
async def test_per_call_envelope_rejects_tampering_before_admission(changes):
    from app.ai.embeddings import EmbeddingProfile
    profile = replace(EmbeddingProfile.from_settings(diagnostic.bounded_profile(settings())), **changes)
    provider = SimpleNamespace(profile=profile, telemetry_snapshot=lambda: SimpleNamespace(request_count=0))
    with pytest.raises(diagnostic.Refusal, match='provider_envelope_invalid'):
        await diagnostic.embed_authored_queries(provider)


def source(**overrides):
    from uuid import uuid4
    values = dict(chunk_id=uuid4(), document_id=uuid4(), content_revision_id=uuid4(), index_revision_id=uuid4(),
                  page_number=22, section='Synthetic section', content='Synthetic exact source.', token_count=10,
                  embedding_space_hash='a' * 64, corpus_revision=1)
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
@pytest.mark.parametrize('field,value', [('document_id', None), ('content_revision_id', None), ('index_revision_id', None),
                                      ('content', 'different'), ('corpus_revision', 2), ('embedding_space_hash', 'b' * 64)])
async def test_discovery_source_must_rebind_to_exact_authorized_current_source(field, value):
    original = source()
    current = SimpleNamespace(**{**vars(original), field: value})
    async def read(ids):
        assert ids == (original.chunk_id,)
        return (current,)
    with pytest.raises(diagnostic.Refusal, match='reviewed_sources_changed'):
        await diagnostic.validate_sources(SimpleNamespace(read_current_sources=read), (original,))


@pytest.mark.asyncio
async def test_missing_authorized_source_rejects_before_provider():
    async def missing(_ids):
        return ()
    with pytest.raises(diagnostic.Refusal, match='reviewed_sources_changed'):
        await diagnostic.validate_sources(SimpleNamespace(read_current_sources=missing), (source(),))


@pytest.mark.asyncio
async def test_database_disposal_failure_preserves_paid_attempt_report(monkeypatch):
    report = {'status': 'diagnostic_unavailable', 'provider_requests': 1, 'previous_attempt_cost': 'unknown'}
    async def evaluate(**kwargs):
        return report
    async def close():
        raise RuntimeError('private connection error')
    monkeypatch.setattr(diagnostic, 'evaluate', evaluate)
    monkeypatch.setattr(diagnostic, 'close_database', close)
    assert await diagnostic.run_diagnostic() == report


@pytest.mark.asyncio
async def test_native_client_disposal_failure_preserves_paid_attempt_report(monkeypatch):
    authorize(monkeypatch)
    async def load(_settings):
        return SimpleNamespace()
    async def close():
        raise RuntimeError('private client error')
    provider = SimpleNamespace(telemetry_snapshot=lambda: SimpleNamespace(request_count=1, retry_count=0))
    client = SimpleNamespace(aio=SimpleNamespace(aclose=close))
    monkeypatch.setattr(diagnostic, 'load_context', load)
    monkeypatch.setattr(diagnostic, 'make_native_provider', lambda _settings: (provider, client))
    async def fail(_provider):
        raise RuntimeError('private response')
    monkeypatch.setattr(diagnostic, 'embed_authored_queries', fail)
    result = await diagnostic.evaluate(execute=True, approval_token=diagnostic.APPROVAL_TOKEN, settings=settings())
    assert result['provider_requests'] == 1 and result['previous_attempt_cost'] == 'unknown'


@pytest.mark.asyncio
async def test_all_five_policy_comparisons_reuse_memory_vectors_and_emit_only_fixed_metrics(monkeypatch):
    from uuid import uuid4
    sources = tuple(source(content=f'Synthetic private source marker {index}') for index in range(6))
    context = diagnostic.Context(SimpleNamespace(id=uuid4()), uuid4(), tuple(item.document_id for item in sources), 1, 'a' * 64, sources)
    vectors = tuple((float(index),) for index in range(6))
    calls = []
    class Db:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_args):
            return None
        async def execute(self, statement):
            assert 'READ ONLY' in str(statement)
        async def rollback(self):
            return None
    async def authorize(db, **kwargs):
        index = diagnostic.QUESTIONS.index(kwargs['query'])
        async def retrieve(vector, *, embedding_space_hash):
            assert vector is vectors[index]
            assert embedding_space_hash == context.space_hash
            calls.append((kwargs['policy'].policy_id, index))
            return SimpleNamespace(subject_id=context.subject_id, corpus_revision=1,
                                   embedding_space_hash=context.space_hash, chunks=(sources[index],))
        return SimpleNamespace(scope=SimpleNamespace(embedding_space_hash=context.space_hash, corpus_revision=1), retrieve=retrieve)
    monkeypatch.setattr(diagnostic, 'async_session_maker', Db)
    monkeypatch.setattr(diagnostic.KnowledgeRetriever, 'authorize', authorize)
    result = await diagnostic.retrieve_metrics(context, vectors)
    assert len(calls) == 30 and len(set(calls)) == 30
    assert len(result['summaries']) == 5 and result['provider_calls_per_policy'] == 0
    assert all(row['confirmed_page_recall_at_5'] == 1 and row['confirmed_page_mrr'] == 1
               and row['candidate_retrieval_thresholds_met'] for row in result['summaries'])
    output = json.dumps(result)
    assert all(question not in output for question in diagnostic.QUESTIONS)
    assert 'Synthetic private source marker' not in output
    assert str(context.subject_id) not in output
    assert all(str(item.chunk_id) not in output for item in sources)


@pytest.mark.parametrize('stage', ('context', 'embedding', 'retrieval', 'scope_recheck'))
def test_failure_stage_is_fixed_and_exception_text_never_emitted(stage):
    marker = 'private-content-id-key-error-marker'
    result = diagnostic.safe_failure(RuntimeError(marker), stage)
    assert result == {'failure_stage': stage, 'failure_code': 'diagnostic_failed'}
    assert marker not in json.dumps(result)
    assert diagnostic.safe_failure(diagnostic.Refusal(marker), stage)['failure_code'] == 'diagnostic_failed'


def test_provider_failure_whitelists_code_reason_and_known_server_status_only():
    class ServerError(Exception):
        status_code = 503
    try:
        try:
            raise ServerError('private server details')
        except ServerError as cause:
            raise AIProviderError('embedding_provider_unavailable', 'private message', retryable=True,
                                  reason_code='http_server_error') from cause
    except AIProviderError as error:
        result = diagnostic.safe_failure(error, 'embedding')
    assert result == {'failure_stage': 'embedding', 'failure_code': 'embedding_provider_unavailable',
                      'provider_reason_code': 'http_server_error', 'provider_http_status': 503}
    unsafe = AIProviderError('private-code', 'private-body', retryable=False, reason_code='private-reason')
    output = json.dumps(diagnostic.safe_failure(unsafe, 'embedding'))
    assert 'private-' not in output and 'unclassified' in output


@pytest.mark.asyncio
@pytest.mark.parametrize('stage', ('embedding', 'retrieval', 'scope_recheck'))
async def test_post_attempt_stage_and_cost_survive_failure(monkeypatch, stage):
    authorize(monkeypatch)
    context = SimpleNamespace(identity=lambda: ('fixed',))
    loads = []
    async def load(_settings):
        loads.append(1)
        if len(loads) > 1 and stage == 'scope_recheck':
            raise RuntimeError('private reread')
        return context
    provider = SimpleNamespace(telemetry_snapshot=lambda: SimpleNamespace(request_count=1, retry_count=0))
    client = SimpleNamespace(aio=SimpleNamespace(aclose=asyncio_sleep))
    monkeypatch.setattr(diagnostic, 'load_context', load)
    monkeypatch.setattr(diagnostic, 'make_native_provider', lambda _settings: (provider, client))
    async def embed(_provider):
        if stage == 'embedding':
            raise AIProviderError('embedding_provider_timeout', 'private timeout', retryable=True, reason_code='transport_timeout')
        return SimpleNamespace(vectors=((),) * 6, usage=SimpleNamespace(input_tokens=100))
    async def retrieve(_context, _vectors):
        if stage == 'retrieval':
            raise RuntimeError('private SQL')
        return {}
    monkeypatch.setattr(diagnostic, 'embed_authored_queries', embed)
    monkeypatch.setattr(diagnostic, 'retrieve_metrics', retrieve)
    result = await diagnostic.evaluate(execute=True, approval_token=diagnostic.APPROVAL_TOKEN, settings=settings())
    assert result['failure_stage'] == stage
    assert result['embedding_response_validated'] is (stage != 'embedding')
    assert result['provider_requests'] == 1 and result['retry_count'] == 0
    assert result['previous_attempt_cost'] == 'unknown'
    assert 'private' not in json.dumps(result)
    if stage != 'embedding':
        assert result['estimated_input_tokens'] == 100
        assert result['cost_provenance'] == 'estimated_not_provider_receipt'
        assert result['estimated_cost_usd'] == '0.00002'
    else:
        assert 'estimated_input_tokens' not in result


@pytest.mark.asyncio
async def test_source_oracle_forbids_provider_and_cannot_qualify_as_real_queries(monkeypatch):
    context = SimpleNamespace(identity=lambda: ('fixed',))
    async def load(_settings):
        return context
    async def vectors(_context):
        return ((),) * 6
    async def metrics(_context, _vectors, *, mode):
        assert mode == 'source_chunk_oracle'
        return {'query_vector_status': 'stored_document_vectors_not_query_embeddings'}
    def forbidden(*args, **kwargs):
        raise AssertionError('oracle must never construct provider')
    monkeypatch.setattr(diagnostic, 'load_context', load)
    monkeypatch.setattr(diagnostic, 'oracle_vectors', vectors)
    monkeypatch.setattr(diagnostic, 'retrieve_metrics', metrics)
    monkeypatch.setattr(diagnostic, 'make_native_provider', forbidden)
    result = await diagnostic.evaluate(source_oracle=True, settings=settings())
    assert result['status'] == 'oracle_completed' and result['provider_requests'] == 0
    assert not result['release_gate_passed']
    assert result['estimated_cost_usd'] == '0'
    assert result['scope'] == 'offline_source_oracle_not_real_query_quality_or_prior_failure_diagnosis'


@pytest.mark.asyncio
async def test_oracle_cannot_be_combined_with_live_execution(monkeypatch):
    authorize(monkeypatch)
    with pytest.raises(diagnostic.Refusal, match='provider_envelope_invalid'):
        await diagnostic.evaluate(execute=True, source_oracle=True, approval_token=diagnostic.APPROVAL_TOKEN, settings=settings())


@pytest.mark.asyncio
async def test_context_does_not_keep_rollback_expired_closed_session_user(monkeypatch, session_factory):
    from uuid import uuid4
    from sqlalchemy.orm.exc import DetachedInstanceError
    from app.models.user import User, UserRole
    principal_id = uuid4()
    async with session_factory() as db:
        principal = User(id=principal_id, email='fixture@example.test', hashed_password='fixture', role=UserRole.INSTRUCTOR)
        db.add(principal)
        await db.commit()
        await db.refresh(principal)
        snapshot = diagnostic.Principal(principal.id, principal.role)
        # Exercise load_context itself with a DB wrapper that returns the real
        # attached ORM user and really rolls back the SQLite session.
        sources = tuple(source(embedding_space_hash=embedding_space_hash(settings().rag_embedding_space_identity)) for _ in range(6))
        sources = tuple(SimpleNamespace(**{**vars(item), 'page_number': probe.page}) for item, probe in zip(sources, diagnostic.PROBES))
        job = SimpleNamespace(subject_id=uuid4(), document_ids=[], corpus_revision=1,
                              embedding_space_hash=sources[0].embedding_space_hash)
        class QueryResults:
            def all(self):
                return [principal_id]
            def one_or_none(self):
                return job
        class Wrapper:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *_args):
                return None
            async def execute(self, _statement):
                return None
            async def scalars(self, _statement):
                return QueryResults()
            async def get(self, _model, _id):
                return principal
            async def rollback(self):
                await db.rollback()
        async def eligible(**kwargs):
            return sources, True, {}, {item.document_id: diagnostic.EXPECTED_DOCUMENT_SLOTS[probe.label] for item, probe in zip(sources, diagnostic.PROBES)}
        def select(probe, chunks):
            return 'selected', sources[diagnostic.LABELS.index(probe.label)], 'Synthetic exact source.'
        async def authorize(*args, **kwargs):
            async def read(ids):
                return tuple(item for item in sources if item.chunk_id in ids)
            return SimpleNamespace(scope=SimpleNamespace(embedding_space_hash=job.embedding_space_hash, corpus_revision=1), read_current_sources=read)
        monkeypatch.setattr(diagnostic, 'async_session_maker', Wrapper)
        monkeypatch.setattr(diagnostic, '_eligible_owner_chunks', eligible)
        monkeypatch.setattr(diagnostic, 'select_probe_source', select)
        monkeypatch.setattr(diagnostic.KnowledgeRetriever, 'authorize', authorize)
        context = await diagnostic.load_context(settings())
        assert isinstance(context.principal, diagnostic.Principal)
    with pytest.raises(DetachedInstanceError):
        _ = principal.id
    assert context.principal == snapshot and context.identity()[0] == principal_id
