"""Prepare/current-question-only vector execution for the frozen private v6 gold.

The CLI is preparation-only: no credential/settings loader, DB or provider.
The inert execution component requires a new explicit authorization and an
externally resource-fenced, embedding-only process. It never uses old vectors
as substitutes for these twelve questions or sends previous chat/source text.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
from time import perf_counter
from uuid import UUID

import snapshot_private_source_gold_v4 as snapshot

SCHEMA = 'cardchemy_private_query_vectors_v6'
MODEL = 'gemini-embedding-001'
# The native SDK sends contents=[question] through the singleton batch route.
ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/models/' + MODEL + ':batchEmbedContents'
TASK = 'QUESTION_ANSWERING'
DIMENSIONS = 1536
MAX_CALLS = 12
MAX_INPUT_TOKENS = 512
MAX_CALL_SECONDS = 30
MAX_TOTAL_SECONDS = 360
PRICE_GUARD = Decimal('0.20')
MAX_COST_USD = Decimal('0.001')
LIVE_AUTHORIZED = False
APPROVAL_ID: str | None = None
APPROVAL_ENV = 'CARDCH_PRIVATE_QUERY_V6_APPROVAL_ID'
LEDGER = Path(__file__).resolve().parents[1] / '.agent/.verification/private-query-v6-ledger'
SOURCE_SNAPSHOT_SHA = '04e1e94768349cef32afeeec1a8d60110fca918f8a71db7b9f75614b1a7b782c'
QUERY_ROSTER_SHA = '6f1cc60e592045b248b785a0ee7e58881ae7debc4584293a52eb9f520fc69587'


class Refusal(ValueError):
    """Closed failure code only."""


def require(value: bool, code: str):
    if not value:
        raise Refusal(code)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


@dataclass(frozen=True)
class PreparedQueries:
    stage1_sha256: str
    source_snapshot_sha256: str
    embedding_space_hash: str
    questions: tuple[tuple[str, str], ...]
    estimated_input_tokens: int


def _validate_inputs(inputs: PreparedQueries) -> None:
    require(type(inputs) is PreparedQueries
            and inputs.stage1_sha256 == snapshot.FROZEN_STAGE1_SHA256
            and inputs.source_snapshot_sha256 == SOURCE_SNAPSHOT_SHA
            and type(inputs.embedding_space_hash) is str
            and snapshot._SHA.fullmatch(inputs.embedding_space_hash) is not None
            and type(inputs.questions) is tuple and len(inputs.questions) == MAX_CALLS
            and all(type(row) is tuple and len(row) == 2
                    and type(row[0]) is str and type(row[1]) is str
                    and 0 < len(row[1]) <= 4_000 and row[1].strip() == row[1]
                    and '\x00' not in row[1] for row in inputs.questions)
            and tuple(cid for cid, _ in inputs.questions)
                == tuple(f'T{i:02}' for i in range(1, MAX_CALLS + 1))
            and sha256(canonical(inputs.questions)).hexdigest() == QUERY_ROSTER_SHA,
            'input_changed')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
    from app.ai.chunking import estimate_tokens
    tokens = sum(estimate_tokens(question) for _, question in inputs.questions)
    require(type(inputs.estimated_input_tokens) is int
            and inputs.estimated_input_tokens == tokens and 0 < tokens <= MAX_INPUT_TOKENS
            and Decimal(tokens) * PRICE_GUARD / 1_000_000 <= MAX_COST_USD,
            'input_budget_invalid')


def prepare(stage1_raw: bytes, source_raw: bytes) -> PreparedQueries:
    require(type(stage1_raw) is bytes and type(source_raw) is bytes
            and sha256(stage1_raw).hexdigest() == snapshot.FROZEN_STAGE1_SHA256
            and sha256(source_raw).hexdigest() == SOURCE_SNAPSHOT_SHA, 'input_changed')
    gold, cases, documents = snapshot._stage1(stage1_raw, snapshot.FROZEN_STAGE1_SHA256)
    try:
        source = json.loads(source_raw, object_pairs_hook=snapshot._unique_object)
    except (ValueError, UnicodeError, RecursionError):
        raise Refusal('snapshot_invalid') from None
    require(type(source) is dict and source.get('schema') == snapshot.SCHEMA
            and source.get('stage1_sha256') == snapshot.FROZEN_STAGE1_SHA256
            and source.get('scope') == gold['scope']
            and snapshot._canonical_uuid(source.get('principal_id'))
            and snapshot._canonical_uuid(source.get('subject_id'))
            and type(source.get('authorized_pages')) is list
            and len(source['authorized_pages']) == MAX_CALLS, 'snapshot_invalid')
    pointers = {(row['document_id'], row['page_number']) for row in cases.values()}
    snapshot._validate_pages(source['authorized_pages'], cases, documents, None,
        pointers=pointers, corpus_revision=gold['scope']['corpus_revision'],
        embedding_space_hash=gold['scope']['embedding_space_hash'])
    # This imports only the production token estimator, never Settings().
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
    from app.ai.chunking import estimate_tokens
    questions = tuple((row['case_id'], row['question']) for row in cases.values())
    require(len(questions) == MAX_CALLS and all('\x00' not in question for _, question in questions),
            'question_invalid')
    tokens = sum(estimate_tokens(question) for _, question in questions)
    require(0 < tokens <= MAX_INPUT_TOKENS
            and Decimal(tokens) * PRICE_GUARD / 1_000_000 <= MAX_COST_USD, 'input_budget_invalid')
    inputs = PreparedQueries(snapshot.FROZEN_STAGE1_SHA256, SOURCE_SNAPSHOT_SHA,
        gold['scope']['embedding_space_hash'], questions, tokens)
    _validate_inputs(inputs)
    return inputs


def manifest(inputs: PreparedQueries) -> dict:
    """Private manifest: current questions only, no lecture/previous-turn data."""
    _validate_inputs(inputs)
    return {'schema': SCHEMA + '_inputs', 'stage1_sha256': inputs.stage1_sha256,
            'source_snapshot_sha256': inputs.source_snapshot_sha256,
            'embedding_space_hash': inputs.embedding_space_hash, 'endpoint': ENDPOINT,
            'model': MODEL, 'task': TASK, 'dimensions': DIMENSIONS,
            'queries': [{'case_id': cid, 'question': question,
                         'question_sha256': sha256(question.encode()).hexdigest()}
                        for cid, question in inputs.questions]}


def aggregate(inputs: PreparedQueries) -> dict:
    return {'schema': SCHEMA + '_preflight', 'status': 'inputs_prepared',
            'case_count': len(inputs.questions), 'estimated_input_tokens': inputs.estimated_input_tokens,
            'max_provider_calls': MAX_CALLS, 'max_input_tokens': MAX_INPUT_TOKENS,
            'max_call_seconds': MAX_CALL_SECONDS, 'max_total_seconds': MAX_TOTAL_SECONDS,
            'input_price_guard_per_million_usd': str(PRICE_GUARD), 'max_cost_usd': str(MAX_COST_USD),
            'provider_calls': 0, 'database_reads': 0, 'database_writes': 0,
            'live_authorized': LIVE_AUTHORIZED, 'release_gate_passed': False}


def bounded_settings(settings, inputs: PreparedQueries):
    _validate_inputs(inputs)
    from app.models.knowledge import embedding_space_hash
    require(settings.rag_embedding_provider_enabled is True
            and settings.rag_embedding_provider == 'gemini' and settings.rag_embedding_model == MODEL
            and settings.rag_embedding_endpoint_identity == 'https://generativelanguage.googleapis.com'
            and settings.rag_embedding_base_url is None and settings.rag_embedding_dimensions == DIMENSIONS
            and settings.rag_embedding_format_version == 'raw_text_v1'
            and settings.rag_embedding_representation == 'float32' and settings.rag_embedding_metric == 'cosine'
            and settings.rag_embedding_provider_task_modes == ('RETRIEVAL_DOCUMENT', TASK)
            and embedding_space_hash(settings.rag_embedding_space_identity) == inputs.embedding_space_hash,
            'profile_incompatible')
    bounded = settings.model_copy(update={
        'rag_embedding_provider_max_retries': 0, 'rag_embedding_provider_timeout_seconds': MAX_CALL_SECONDS,
        'rag_embedding_batch_size': 1, 'rag_embedding_max_input_tokens': MAX_INPUT_TOKENS,
        'rag_embedding_input_cost_per_million_usd': PRICE_GUARD,
        'rag_embedding_max_estimated_cost_usd': MAX_COST_USD})
    require(bounded.rag_embedding_space_identity == settings.rag_embedding_space_identity, 'profile_incompatible')
    return bounded


def _private_output(path: Path):
    resolved = snapshot._temp_path(path, existing=False)
    require(resolved.parent != Path(tempfile.gettempdir()).resolve(), 'private_directory_required')
    return resolved


async def build_packet(inputs: PreparedQueries, settings, *, output: Path,
                       approval_id: str, provider_factory=None) -> dict:
    """Inert until fresh approval; checkpoint every valid vector, no automatic replay.

    The outer approved caller supplies only embedding settings/credentials,
    pins these inputs/code, and enforces resource limits before this component.
    There is deliberately no CLI execution route or operator key loader here.
    """
    require(LIVE_AUTHORIZED, 'fresh_authorization_required')
    try:
        authorization = UUID(approval_id)
    except (ValueError, TypeError):
        raise Refusal('fresh_authorization_required') from None
    require(authorization.version == 4 and str(authorization) == approval_id
            and APPROVAL_ID == approval_id
            and os.environ.get(APPROVAL_ENV) == approval_id, 'fresh_authorization_required')
    _validate_inputs(inputs)
    output = _private_output(output)
    require(not any(output.parent.glob('query-v6-*-receipt.json')), 'previous_attempt_not_replayable')
    bounded = bounded_settings(settings, inputs)
    # A central exclusive marker survives a different private output directory.
    LEDGER.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(LEDGER.is_dir() and not LEDGER.is_symlink(), 'ledger_invalid')
    marker = LEDGER / ('.query-v6-' + sha256(authorization.bytes).hexdigest() + '.used')
    snapshot._write_exclusive(marker, canonical({'schema': SCHEMA + '_claim',
        'approval_id': approval_id, 'stage1_sha256': inputs.stage1_sha256,
        'source_snapshot_sha256': inputs.source_snapshot_sha256}))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend/scripts'))
    import build_private_query_vectors as native
    factory = provider_factory or native.make_native_query_provider
    provider = client = None
    rows, input_tokens = [], 0
    started = perf_counter()
    try:
        async with asyncio.timeout(MAX_TOTAL_SECONDS):
            provider, client = factory(bounded)
            native._check_provider(provider)
            for cid, question in inputs.questions:
                before = provider.telemetry_snapshot()
                require(before.request_count == len(rows) and before.retry_count == 0, 'attempt_invalid')
                response = await provider.embed_query(question)
                after = provider.telemetry_snapshot()
                require(after.request_count == len(rows) + 1 and after.retry_count == 0
                        and len(response.vectors) == 1 and native._valid_vector(response.vectors[0]),
                        'attempt_invalid')
                require(type(response.usage.input_tokens) is int and response.usage.input_tokens > 0,
                        'usage_invalid')
                input_tokens += response.usage.input_tokens
                require(input_tokens <= MAX_INPUT_TOKENS
                        and Decimal(input_tokens) * PRICE_GUARD / 1_000_000 <= MAX_COST_USD,
                        'usage_budget_exceeded')
                row = {'case_id': cid, 'question_sha256': sha256(question.encode()).hexdigest(),
                       'embedding': list(response.vectors[0])}
                snapshot._write_exclusive(output.parent / f'query-v6-{cid}-receipt.json', canonical({
                    'schema': SCHEMA + '_receipt', 'stage1_sha256': inputs.stage1_sha256,
                    'source_snapshot_sha256': inputs.source_snapshot_sha256,
                    'embedding_space_hash': inputs.embedding_space_hash, 'vector': row,
                    'input_tokens': response.usage.input_tokens, 'physical_requests': 1, 'retries': 0}))
                rows.append(row)
            body = canonical({'schema': SCHEMA, 'model': MODEL, 'task': TASK,
                'dimensions': DIMENSIONS, 'stage1_sha256': inputs.stage1_sha256,
                'source_snapshot_sha256': inputs.source_snapshot_sha256,
                'embedding_space_hash': inputs.embedding_space_hash, 'vectors': rows})
            snapshot._write_exclusive(output, body)
            return {'schema': SCHEMA + '_aggregate', 'status': 'completed_private_packet',
                'packet_sha256': sha256(body).hexdigest(), 'case_count': len(rows), 'provider_calls': len(rows),
                'input_tokens': input_tokens, 'cost_guard_usd': str(Decimal(input_tokens) * PRICE_GUARD / 1_000_000),
                'cost_provenance': 'estimated_input_tokens_times_guard_not_billing_receipt',
                'actual_provider_cost_unknown': True, 'retries': 0,
                'database_writes': 0, 'release_gate_passed': False}
    except Exception:
        calls = provider.telemetry_snapshot().request_count if provider is not None else 0
        return {'schema': SCHEMA + '_aggregate', 'status': 'stopped', 'provider_calls': calls,
                'valid_checkpoints': len(rows), 'known_input_tokens': input_tokens,
                'failed_attempt_cost_unknown': calls > len(rows), 'automatic_retries': 0,
                'database_writes': 0, 'release_gate_passed': False}
    finally:
        if client is not None:
            try:
                await asyncio.wait_for(client.aio.aclose(), timeout=max(.001, MAX_TOTAL_SECONDS - (perf_counter() - started)))
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--preflight-inputs', action='store_true')
    parser.add_argument('--stage1', type=Path)
    parser.add_argument('--source-snapshot', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not args.preflight_inputs:
        print(json.dumps({'schema': SCHEMA, 'status': 'unexecuted', 'provider_calls': 0,
                          'database_reads': 0, 'live_authorized': LIVE_AUTHORIZED}))
        return 0
    try:
        require(all((args.stage1, args.source_snapshot, args.output)), 'arguments_invalid')
        stage1 = snapshot._read_hashed(args.stage1, snapshot.FROZEN_STAGE1_SHA256,
            maximum=snapshot.MAX_STAGE1_BYTES, code='stage1_changed')
        source = snapshot._read_hashed(args.source_snapshot, SOURCE_SNAPSHOT_SHA,
            maximum=snapshot.MAX_OUTPUT_BYTES, code='snapshot_changed')
        inputs = prepare(stage1, source)
        output = _private_output(args.output)
        require(output.parent == args.stage1.resolve().parent == args.source_snapshot.resolve().parent,
                'private_directory_required')
        snapshot._write_exclusive(output, canonical(manifest(inputs)))
        print(json.dumps(aggregate(inputs)))
        return 0
    except Exception:
        print(json.dumps({'schema': SCHEMA, 'status': 'preflight_refused', 'provider_calls': 0,
                          'database_writes': 0, 'live_authorized': LIVE_AUTHORIZED}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
