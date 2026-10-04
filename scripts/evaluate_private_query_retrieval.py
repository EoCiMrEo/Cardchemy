"""Opt-in, read-only six-query embedding/retrieval diagnostic.

Default execution makes no provider calls. Live opt-in sends only the six
authored general-domain PROBES questions, never Knowledge or retained chat.
The installed QUESTION_ANSWERING task/space stays unchanged. Vectors remain
in memory; only fixed labels, ranks, aggregates and attempt counts are emitted.
This evaluates retrieval, not generated answers or semantic support quality.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sys
from time import perf_counter
from uuid import UUID

BACKEND = Path('/app') if Path('/app/app').is_dir() else Path(__file__).resolve().parents[1] / 'backend'
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select, text  # noqa: E402
from app.ai.chunking import estimate_tokens  # noqa: E402
from app.ai.embeddings import GeminiEmbeddingProvider  # noqa: E402
from app.ai.providers import AIProviderError  # noqa: E402
from app.config import Settings, get_settings  # noqa: E402
from app.database import async_session_maker, close_database  # noqa: E402
from app.models.knowledge import embedding_space_hash  # noqa: E402
from app.models.rag import RagAnswerJob, RagMessage  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.services.knowledge_retrieval import EXACT_V1_POLICY, KnowledgeRetriever  # noqa: E402
from app.time_utils import utcnow  # noqa: E402
from evaluate_private_ask_support_v2 import PROBES, _eligible_owner_chunks, select_probe_source  # noqa: E402
from evaluate_private_retrieval_ablation import EXPECTED_DOCUMENT_SLOTS, POLICIES, _SOURCE_VECTORS, _overlap_count, _rank, _summary, _vector  # noqa: E402
from compare_private_ask_once import _SAFE_PROVIDER_CODES, _safe_provider_reason_code, _safe_server_http_status  # noqa: E402

ENDPOINT = 'https://generativelanguage.googleapis.com'
MODEL = 'gemini-embedding-001'
TASK = 'QUESTION_ANSWERING'
MAX_INPUT_TOKENS = 512
MAX_CALL_SECONDS = 30
MAX_TOTAL_SECONDS = 45
MAX_COST_USD = Decimal('0.001')
CONSERVATIVE_INPUT_PRICE = Decimal('0.20')  # Admission bound, not a verified tariff.
APPROVAL_TOKEN = 'APPROVE_SIX_AUTHORED_QUERIES_ONE_BATCH_USD_0_001'
AUTHORIZATION_ENV = 'CARDCH_QUERY_RETRIEVAL_AUTHORIZATION'
QUESTIONS = tuple(probe.question for probe in PROBES)
QUESTIONS_SHA256 = 'd9f9752f96a4fe2c3da07c1eee702f84bf6fb9d3d4874e68c5aa9fba3386b07b'
LABELS = ('bleu_acronym', 'bleu_focus', 'cosine', 'bag_of_words', 'logistic', 'topic_modeling')
SAFE_REFUSALS = frozenset({
    'authorization_missing', 'profile_incompatible', 'probe_identity_invalid', 'input_budget_invalid',
    'space_changed', 'reviewed_sources_unavailable', 'reviewed_sources_changed', 'context_unavailable',
    'active_space_incompatible', 'embedding_credentials_unavailable', 'provider_envelope_invalid',
    'provider_attempt_invalid', 'scope_changed', 'oracle_vectors_unavailable',
})
SAFE_STAGES = frozenset({'context', 'embedding', 'retrieval', 'scope_recheck'})


class Refusal(RuntimeError):
    """Internal errors and private values must never be printed."""


def safe_failure(exc: BaseException, stage: str) -> dict:
    result = {'failure_stage': stage if stage in SAFE_STAGES else 'context', 'failure_code': 'diagnostic_failed'}
    if isinstance(exc, Refusal) and exc.args and exc.args[0] in SAFE_REFUSALS:
        result['failure_code'] = exc.args[0]
    elif isinstance(exc, AIProviderError):
        result['failure_code'] = exc.code if exc.code in _SAFE_PROVIDER_CODES else 'diagnostic_failed'
        result['provider_reason_code'] = _safe_provider_reason_code(exc)
        status = _safe_server_http_status(exc)
        if status is not None:
            result['provider_http_status'] = status
    elif isinstance(exc, TimeoutError):
        result['failure_code'] = 'total_time_budget_exceeded'
    return result


@dataclass(frozen=True)
class Principal:
    # A SQLAlchemy rollback expires attached ORM attributes. The read-only
    # retriever only needs the principal ID; keep no closed-session ORM object.
    id: UUID
    role: UserRole


@dataclass(frozen=True)
class Context:
    principal: Principal
    subject_id: UUID
    document_ids: tuple[UUID, ...]
    corpus_revision: int
    space_hash: str
    sources: tuple

    def identity(self):
        return (self.principal.id, self.subject_id, self.document_ids, self.corpus_revision,
                self.space_hash, tuple((source.chunk_id, source.content_revision_id,
                                       source.index_revision_id) for source in self.sources))


def require_authorization(*, execute: bool, approval_token: str | None) -> None:
    if execute and (approval_token != APPROVAL_TOKEN or os.getenv(AUTHORIZATION_ENV) != APPROVAL_TOKEN):
        raise Refusal('authorization_missing')


def bounded_profile(settings: Settings) -> Settings:
    if (not settings.rag_enabled or not settings.rag_embedding_provider_enabled
        or settings.rag_embedding_provider != 'gemini' or settings.rag_embedding_model != MODEL
        or settings.rag_embedding_endpoint_identity != ENDPOINT
        or settings.rag_embedding_base_url is not None
        or settings.rag_embedding_provider_task_modes != ('RETRIEVAL_DOCUMENT', TASK)
        or settings.rag_embedding_dimensions != 1536
        or settings.rag_embedding_format_version != 'raw_text_v1'
        or settings.rag_embedding_representation != 'float32'
        or settings.rag_embedding_metric != 'cosine' or not settings.rag_embedding_quota_bucket):
        raise Refusal('profile_incompatible')
    if (tuple(probe.label for probe in PROBES) != LABELS or len(QUESTIONS) != 6
        or tuple(probe.question for probe in PROBES) != QUESTIONS
        or hashlib.sha256(json.dumps(QUESTIONS, separators=(',', ':')).encode()).hexdigest() != QUESTIONS_SHA256):
        raise Refusal('probe_identity_invalid')
    tokens = sum(estimate_tokens(question) for question in QUESTIONS)
    if not 0 < tokens <= MAX_INPUT_TOKENS or Decimal(tokens) * CONSERVATIVE_INPUT_PRICE / 1_000_000 > MAX_COST_USD:
        raise Refusal('input_budget_invalid')
    bounded = settings.model_copy(update={
        'rag_embedding_provider_max_retries': 0,
        'rag_embedding_provider_timeout_seconds': MAX_CALL_SECONDS,
        'rag_embedding_batch_size': 6,
        'rag_embedding_max_input_tokens': MAX_INPUT_TOKENS,
        'rag_embedding_input_cost_per_million_usd': CONSERVATIVE_INPUT_PRICE,
        'rag_embedding_max_estimated_cost_usd': MAX_COST_USD,
    })
    if bounded.rag_embedding_space_identity != settings.rag_embedding_space_identity:
        raise Refusal('space_changed')
    return bounded


async def load_context(settings: Settings) -> Context:
    chunks, active, _pages, slots = await _eligible_owner_chunks(with_pages=True)
    selected = [select_probe_source(probe, chunks) for probe in PROBES]
    if not active or any(state != 'selected' or source is None or quote is None
                         for state, source, quote in selected):
        raise Refusal('reviewed_sources_unavailable')
    sources = tuple(source for _state, source, _quote in selected)
    if any(slots.get(source.document_id) != EXPECTED_DOCUMENT_SLOTS[probe.label]
           for probe, source in zip(PROBES, sources, strict=True)):
        raise Refusal('reviewed_sources_changed')
    async with async_session_maker() as db:
        await db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
        matching = (RagMessage.role == 'user', RagMessage.content.ilike('%BLEU%'), RagMessage.expires_at > utcnow())
        owners = (await db.scalars(select(RagAnswerJob.user_id).join(
            RagMessage, RagMessage.id == RagAnswerJob.question_message_id).where(*matching).distinct().limit(2))).all()
        if len(owners) != 1:
            raise Refusal('context_unavailable')
        job = (await db.scalars(select(RagAnswerJob).join(
            RagMessage, RagMessage.id == RagAnswerJob.question_message_id).where(*matching, RagAnswerJob.user_id == owners[0])
            .order_by(RagAnswerJob.created_at.desc(), RagAnswerJob.id.desc()).limit(1))).one_or_none()
        principal = await db.get(User, owners[0])
        if job is None or principal is None or principal.role != UserRole.INSTRUCTOR:
            raise Refusal('context_unavailable')
        document_ids = tuple(UUID(str(value)) for value in job.document_ids)
        retriever = await KnowledgeRetriever.authorize(db, principal=principal, subject_id=job.subject_id,
                                                     query=QUESTIONS[0], document_ids=document_ids)
        scope = retriever.scope
        configured = embedding_space_hash(settings.rag_embedding_space_identity)
        if (scope.embedding_space_hash != configured or job.embedding_space_hash != configured
            or scope.corpus_revision != job.corpus_revision or any(
                source.embedding_space_hash != configured or source.corpus_revision != scope.corpus_revision for source in sources)):
            raise Refusal('active_space_incompatible')
        await validate_sources(retriever, sources)
        context = Context(Principal(principal.id, principal.role), job.subject_id, document_ids,
                          scope.corpus_revision, configured, sources)
        await db.rollback()
        return context


async def validate_sources(retriever, sources):
    # Source discovery and latest-job selection are separate read snapshots.
    # Rebind every selected source under the new exact authorized scope before
    # spending, including Subject/document membership and all citation fields.
    unique = {source.chunk_id: source for source in sources}
    ids = tuple(unique)
    current = []
    for start in range(0, len(ids), 5):
        current.extend(await retriever.read_current_sources(ids[start:start + 5]))
    if len(current) != len(unique) or {source.chunk_id for source in current} != set(unique):
        raise Refusal('reviewed_sources_changed')
    fields = ('document_id', 'content_revision_id', 'index_revision_id', 'page_number',
              'section', 'content', 'token_count', 'embedding_space_hash', 'corpus_revision')
    current_by_id = {source.chunk_id: source for source in current}
    if any(any(getattr(source, field) != getattr(current_by_id[source.chunk_id], field) for field in fields)
           for source in sources):
        raise Refusal('reviewed_sources_changed')


def make_native_provider(settings: Settings, *, http_client=None):
    # Force the official developer endpoint, no Vertex routing, redirects or
    # stacked SDK retries. Tests supply a keyless HTTP mock through this hook.
    from google import genai
    from google.genai import types
    if settings.rag_embedding_api_key is None:
        raise Refusal('embedding_credentials_unavailable')
    options = dict(base_url=ENDPOINT, timeout=MAX_CALL_SECONDS * 1000,
                   retry_options=types.HttpRetryOptions(attempts=1),
                   async_client_args={'follow_redirects': False, 'trust_env': False})
    if http_client is not None:
        options['httpx_async_client'] = http_client
    client = genai.Client(vertexai=False, api_key=settings.rag_embedding_api_key_value,
                          http_options=types.HttpOptions(**options))
    return GeminiEmbeddingProvider(settings, client=client), client


async def embed_authored_queries(provider):
    if (provider.telemetry_snapshot().request_count != 0
        or provider.profile.model != MODEL or provider.profile.query_task_mode != TASK
        or provider.profile.max_retries != 0 or provider.profile.batch_size != 6
        or provider.profile.timeout_seconds != MAX_CALL_SECONDS or provider.profile.dimensions != 1536
        or provider.profile.max_input_tokens != MAX_INPUT_TOKENS
        or provider.profile.input_cost_per_million_usd != float(CONSERVATIVE_INPUT_PRICE)
        or provider.profile.max_estimated_cost_usd != float(MAX_COST_USD)):
        raise Refusal('provider_envelope_invalid')
    async with provider.attempt_scope() as attempt:
        response = await provider._embed(QUESTIONS, operation='embedding_query')
        telemetry = attempt.snapshot()
    if (len(response.vectors) != 6 or telemetry.request_count != 1 or telemetry.retry_count != 0
        or telemetry.request_counts_by_stage != {'embedding_query': 1}):
        raise Refusal('provider_attempt_invalid')
    return response


async def retrieve_metrics(context: Context, vectors, *, mode: str = 'real_authored_query') -> dict:
    if mode not in ('real_authored_query', 'source_chunk_oracle'):
        raise Refusal('provider_envelope_invalid')
    rows = []
    async with async_session_maker() as db:
        await db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
        for policy in POLICIES:
            for probe, source, vector in zip(PROBES, context.sources, vectors, strict=True):
                started = perf_counter()
                retriever = await KnowledgeRetriever.authorize(db, principal=context.principal, subject_id=context.subject_id,
                    query=probe.question, document_ids=context.document_ids, limit=5, policy=policy)
                if (retriever.scope.embedding_space_hash != context.space_hash
                    or retriever.scope.corpus_revision != context.corpus_revision):
                    raise Refusal('scope_changed')
                result = await retriever.retrieve(vector, embedding_space_hash=context.space_hash)
                if (result.subject_id != context.subject_id or result.corpus_revision != context.corpus_revision
                    or result.embedding_space_hash != context.space_hash or any(
                        chunk.corpus_revision != context.corpus_revision or chunk.embedding_space_hash != context.space_hash
                        or (context.document_ids and chunk.document_id not in context.document_ids) for chunk in result.chunks)):
                    raise Refusal('scope_changed')
                rows.append({'case': probe.label, 'policy': policy.policy_id, 'mode': mode,
                    'page_rank': _rank(result.chunks, source, page_level=True),
                    'source_chunk_rank': _rank(result.chunks, source, page_level=False),
                    'overlap_count': _overlap_count(result.chunks), 'selected_count': len(result.chunks),
                    'query_ms': round((perf_counter() - started) * 1000, 3), 'scope_violations': 0})
        await db.rollback()
    summaries = [_summary(rows, policy.policy_id, mode) for policy in POLICIES]
    baseline = summaries[0]
    for summary in summaries:
        summary['candidate_retrieval_thresholds_met'] = (
            mode == 'real_authored_query' and summary['case_count'] == 6 and summary['confirmed_page_recall_at_5'] == 1.0
            and summary['confirmed_page_mrr'] >= .8 and summary['overlap_rate'] <= .2
            and summary['p95_query_ms'] <= 2000 and summary['scope_violation_count'] == 0
            and summary['confirmed_page_recall_at_5'] >= baseline['confirmed_page_recall_at_5']
            and summary['confirmed_page_mrr'] >= baseline['confirmed_page_mrr'])
    return {'scope': 'authored_queries_owner_confirmed_pages_machine_selected_chunks',
            'query_vector_status': 'real_query_embeddings' if mode == 'real_authored_query' else 'stored_document_vectors_not_query_embeddings',
            'provider_calls_per_policy': 0, 'summaries': summaries, 'cases': rows}


async def oracle_vectors(context: Context):
    """Read eligible stored document vectors solely as an offline SQL oracle."""
    source_ids = {source.chunk_id for source in context.sources}
    async with async_session_maker() as db:
        await db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
        rows = (await db.execute(_SOURCE_VECTORS, {
            'principal_id': context.principal.id, 'subject_id': context.subject_id,
            'corpus_revision': context.corpus_revision, 'space_hash': context.space_hash,
            'filtered': bool(context.document_ids), 'document_ids': list(context.document_ids),
            'chunk_ids': list(source_ids),
        })).mappings().all()
        vectors = {row['chunk_id']: _vector(row['vector_text']) for row in rows}
        if set(vectors) != source_ids:
            raise Refusal('oracle_vectors_unavailable')
        await db.rollback()
    return tuple(vectors[source.chunk_id] for source in context.sources)


async def evaluate(*, execute: bool = False, approval_token: str | None = None, settings: Settings | None = None,
                   source_oracle: bool = False):
    started = perf_counter()
    require_authorization(execute=execute, approval_token=approval_token)
    if source_oracle and execute:
        raise Refusal('provider_envelope_invalid')
    provider, client, response = None, None, None
    stage, embedding_validated = 'context', False
    try:
        async with asyncio.timeout(MAX_TOTAL_SECONDS):
            settings = bounded_profile(settings or get_settings())
            context = await load_context(settings)
            base = {'endpoint': ENDPOINT, 'model': MODEL, 'query_task': TASK, 'query_count': 6,
                    'estimated_input_tokens': sum(estimate_tokens(question) for question in QUESTIONS),
                    'max_input_tokens': MAX_INPUT_TOKENS, 'max_call_seconds': MAX_CALL_SECONDS,
                    'max_total_seconds': MAX_TOTAL_SECONDS, 'max_cost_usd': str(MAX_COST_USD),
                    'conservative_input_price_per_million_usd': str(CONSERVATIVE_INPUT_PRICE),
                    'database_writes': 0, 'answer_requests': 0, 'runtime_policy_changed': False,
                    'knowledge_sent': False, 'history_sent': False, 'vectors_persisted': False}
            if not execute and not source_oracle:
                return {**base, 'status': 'preflight_ready', 'provider_requests': 0, 'retry_count': 0}
            if source_oracle:
                stage = 'retrieval'
                vectors = await oracle_vectors(context)
                metrics = await retrieve_metrics(context, vectors, mode='source_chunk_oracle')
            else:
                stage = 'embedding'
                provider, client = make_native_provider(settings)
                response = await embed_authored_queries(provider)
                embedding_validated = True
                stage = 'retrieval'
                metrics = await retrieve_metrics(context, response.vectors)
            stage = 'scope_recheck'
            if (await load_context(settings)).identity() != context.identity():
                raise Refusal('scope_changed')
            if source_oracle:
                return {**base, 'status': 'oracle_completed', 'provider_requests': 0, 'retry_count': 0,
                        'cost_provenance': 'no_provider_attempt', 'estimated_cost_usd': '0',
                        'retrieval': metrics, 'release_gate_passed': False,
                        'scope': 'offline_source_oracle_not_real_query_quality_or_prior_failure_diagnosis'}
            return {**base, 'status': 'completed', 'provider_requests': 1, 'retry_count': 0,
                    'embedding_response_validated': embedding_validated,
                    'cost_provenance': 'estimated_not_provider_receipt',
                    'estimated_cost_usd': str(Decimal(response.usage.input_tokens) * CONSERVATIVE_INPUT_PRICE / 1_000_000),
                    'retrieval': metrics, 'release_gate_passed': False}
    except Exception as exc:
        telemetry = provider.telemetry_snapshot() if provider is not None else None
        failure = {**safe_failure(exc, stage), 'status': 'diagnostic_unavailable',
                'embedding_response_validated': embedding_validated,
                'provider_requests': telemetry.request_count if telemetry else 0,
                'retry_count': telemetry.retry_count if telemetry else 0,
                'previous_attempt_cost': 'unknown' if telemetry and telemetry.request_count else 'no_provider_attempt',
                'database_writes': 0, 'answer_requests': 0, 'runtime_policy_changed': False,
                'release_gate_passed': False}
        if embedding_validated and response is not None:
            failure['estimated_input_tokens'] = response.usage.input_tokens
            failure['estimated_cost_usd'] = str(Decimal(response.usage.input_tokens) * CONSERVATIVE_INPUT_PRICE / 1_000_000)
            failure['cost_provenance'] = 'estimated_not_provider_receipt'
        return failure
    finally:
        if client is not None:
            try:
                async with asyncio.timeout(max(0, MAX_TOTAL_SECONDS - (perf_counter() - started))):
                    await client.aio.aclose()
            except Exception:
                pass  # Never replace aggregate attempt provenance with a cleanup error.


async def run_diagnostic(**kwargs):
    started = perf_counter()
    try:
        return await evaluate(**kwargs)
    finally:
        try:
            async with asyncio.timeout(max(0, MAX_TOTAL_SECONDS - (perf_counter() - started))):
                await close_database()
        except Exception:
            pass  # A disposal error must not erase provider/cost provenance.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    execution = parser.add_mutually_exclusive_group()
    execution.add_argument('--execute', action='store_true')
    execution.add_argument('--source-oracle', action='store_true', help='Zero-provider read-only stored-vector SQL oracle, not real-query quality')
    parser.add_argument('--approval-token')
    args = parser.parse_args()
    try:
        result = asyncio.run(run_diagnostic(execute=args.execute, approval_token=args.approval_token,
                                          source_oracle=args.source_oracle))
    except Exception:
        result = {'status': 'diagnostic_refused', 'provider_requests': 0, 'release_gate_passed': False}
    print(json.dumps(result, separators=(',', ':')))
    return 0 if result['status'] in ('preflight_ready', 'completed', 'oracle_completed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
