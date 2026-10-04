"""Prepare frozen private v6 hybrid candidates; never dispatch a provider.

Default invocation reads nothing. Explicit execution is a development-only,
credential-free, Ask-off read-only diagnostic in a resource-fenced container.
Inputs and output belong in an owner-private directory under OS Temp, not the
repository. The caller supplies a newly obtained exact vector-packet SHA.
The caller must enforce a hard 300-second process wall limit as well as the
4-CPU/2-GiB container fence. Async timeouts are cooperative; safe renderer
termination and synchronous encoding/fsync cannot enforce a hard process limit.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import sys
from time import perf_counter
from types import SimpleNamespace
from uuid import UUID


SCRIPT_ROOT = Path(__file__).resolve().parent
# The outer container may mount this file with the pure support scripts in
# /diagnostics; native checkout layout keeps them in repository/scripts.
SUPPORT_ROOT = (SCRIPT_ROOT if (SCRIPT_ROOT / 'snapshot_private_source_gold_v4.py').is_file()
                else SCRIPT_ROOT.parent.parent / 'scripts')
BACKEND_ROOT = Path('/app') if (Path('/app') / 'app').is_dir() else SCRIPT_ROOT.parent
sys.path.insert(0, str(SUPPORT_ROOT))
sys.path.insert(0, str(BACKEND_ROOT))
import bridge_private_source_gold_v4 as bridge
import prepare_private_query_vectors_v6 as vectors
import snapshot_private_source_gold_v4 as snapshot

SCHEMA = 'private_hybrid_visual_v6_preparation_v1'
POLICY = 'related_knowledge_navigation_v6'
CONTRACT = 'visual_source_id_v2'
MAX_VECTOR_BYTES = 2 * 1024 * 1024
MAX_OUTPUT_BYTES = 48 * 1024 * 1024
MAX_SECONDS = 300
MAX_CPU = 4
MAX_MEMORY_BYTES = 2 * 1024 * 1024 * 1024


class Refusal(ValueError):
    """Fixed safe code, never private data or exception details."""


def require(value: bool, code: str) -> None:
    if not value:
        raise Refusal(code)


def canonical(value: object) -> bytes:
    def uuid_only(item):
        if isinstance(item, UUID):
            return str(item)
        raise TypeError('unsupported_output_type')
    return json.dumps(value, default=uuid_only, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


@dataclass(frozen=True)
class Scope:
    principal_id: str
    subject_id: str
    corpus_revision: int
    embedding_space_hash: str


def prepare(stage1_raw: bytes, source_raw: bytes, vector_raw: bytes, *,
            vector_sha256: str, scope: Scope) -> tuple[dict, dict, dict, dict]:
    """Pure byte/schema validation. Source authorization is proved later in SQL."""
    require(type(scope) is Scope and snapshot._canonical_uuid(scope.principal_id)
            and snapshot._canonical_uuid(scope.subject_id)
            and type(scope.corpus_revision) is int and scope.corpus_revision >= 1
            and type(scope.embedding_space_hash) is str
            and snapshot._SHA.fullmatch(scope.embedding_space_hash) is not None,
            'scope_invalid')
    queries = vectors.prepare(stage1_raw, source_raw)
    gold, cases, documents = snapshot._stage1(stage1_raw, snapshot.FROZEN_STAGE1_SHA256)
    source = json.loads(source_raw, object_pairs_hook=snapshot._unique_object)
    require(gold['scope'] == {'corpus_revision': scope.corpus_revision,
                             'embedding_space_hash': scope.embedding_space_hash}
            and source['principal_id'] == scope.principal_id
            and source['subject_id'] == scope.subject_id
            and all(len(case['previous_turn']) <= 4_000 and '\x00' not in case['previous_turn']
                    for case in cases.values()), 'scope_changed')
    require(type(vector_raw) is bytes and 0 < len(vector_raw) <= MAX_VECTOR_BYTES
            and type(vector_sha256) is str and snapshot._SHA.fullmatch(vector_sha256) is not None
            and sha256(vector_raw).hexdigest() == vector_sha256, 'vector_packet_changed')
    try:
        packet = json.loads(vector_raw, object_pairs_hook=snapshot._unique_object)
    except (ValueError, UnicodeError, RecursionError):
        raise Refusal('vector_packet_invalid') from None
    require(type(packet) is dict and set(packet) == {
        'schema', 'model', 'task', 'dimensions', 'stage1_sha256',
        'source_snapshot_sha256', 'embedding_space_hash', 'vectors'}
        and packet['schema'] == vectors.SCHEMA and packet['model'] == vectors.MODEL
        and packet['task'] == vectors.TASK and type(packet['dimensions']) is int
        and packet['dimensions'] == vectors.DIMENSIONS
        and packet['stage1_sha256'] == queries.stage1_sha256
        and packet['source_snapshot_sha256'] == queries.source_snapshot_sha256
        and packet['embedding_space_hash'] == scope.embedding_space_hash
        and type(packet['vectors']) is list and len(packet['vectors']) == 12,
        'vector_packet_invalid')
    validated = {}
    for row, (case_id, question) in zip(packet['vectors'], queries.questions, strict=True):
        require(type(row) is dict and set(row) == {'case_id', 'question_sha256', 'embedding'}
                and row['case_id'] == case_id
                and row['question_sha256'] == sha256(question.encode('utf-8')).hexdigest()
                and type(row['embedding']) is list and len(row['embedding']) == vectors.DIMENSIONS,
                'vector_packet_invalid')
        try:
            require(all(type(value) in (int, float) and math.isfinite(value)
                        for value in row['embedding']), 'vector_packet_invalid')
            norm = math.sqrt(math.fsum(value * value for value in row['embedding']))
        except (OverflowError, ValueError):
            raise Refusal('vector_packet_invalid') from None
        require(math.isfinite(norm) and abs(norm - 1.0) <= .001, 'vector_packet_invalid')
        validated[case_id] = tuple(row['embedding'])
    return gold, cases, documents, validated


def guard_runtime(environment: dict[str, str], expected_database: str) -> str:
    url = snapshot._guard_runtime(environment, expected_database)
    require(environment.get('RAG_SOURCE_JUDGE_PROVIDER_ENABLED', '').lower() == 'false',
            'development_judge_off_required')
    return url


def guard_resources(*, cgroup_root: Path = Path('/sys/fs/cgroup')) -> None:
    """Require actual finite cgroup v2 limits; the outer caller owns the fence."""
    try:
        quota, period = (cgroup_root / 'cpu.max').read_text().split()
        memory = (cgroup_root / 'memory.max').read_text().strip()
        require(quota != 'max' and memory != 'max'
                and 0 < int(quota) <= MAX_CPU * int(period) and int(period) > 0
                and 0 < int(memory) <= MAX_MEMORY_BYTES, 'resource_fence_required')
    except (OSError, ValueError):
        raise Refusal('resource_fence_required') from None


def load_runtime():
    """Only called after environment/input guards; no root .env is permitted."""
    sys.path.insert(0, str(BACKEND_ROOT))
    from app.config import ROOT_DIR, Settings, ASK_REQUIRED_RELEASE_POLICY_VERSION
    require(not (ROOT_DIR / '.env').exists(), 'operator_env_mount_forbidden')
    settings = Settings(_env_file=None)
    require(settings.environment == 'development' and settings.rag_ask_enabled is False
            and settings.rag_source_judge_provider_enabled is False
            and ASK_REQUIRED_RELEASE_POLICY_VERSION == POLICY
            and settings.rag_source_judge_contract_version == CONTRACT
            and settings.rag_source_judge_max_input_tokens == 32_768
            and settings.rag_source_judge_max_output_tokens == 4_096
            and settings.rag_source_judge_provider_timeout_seconds == 60
            and settings.rag_source_judge_provider_max_retries == 0
            and all(getattr(settings, name) is None for name in (
                'flashcard_ai_api_key', 'rag_ai_api_key', 'rag_embedding_api_key',
                'rag_source_judge_api_key')), 'runtime_not_closed')
    from app.models.knowledge import embedding_space_hash
    from app.ai.source_navigation import navigation_query_v4
    from app.services.knowledge_retrieval import KnowledgeRetriever, SOURCE_NAVIGATION_RETRIEVAL_POLICY
    from app.services.source_visual_preparation import prepare_visual_sources
    from app.workers.rag_answer import _v4_candidate_pool
    return SimpleNamespace(settings=settings, space_hash=embedding_space_hash(settings.rag_embedding_space_identity),
        navigation_query=navigation_query_v4, retriever=KnowledgeRetriever,
        retrieval_policy=SOURCE_NAVIGATION_RETRIEVAL_POLICY, candidate_pool=_v4_candidate_pool,
        visual_prepare=prepare_visual_sources)


async def collect(db, *, runtime, scope: Scope, gold: dict, cases: dict,
                  documents: dict, embeddings: dict) -> tuple[dict, dict]:
    """One current authorized REPEATABLE READ READ ONLY snapshot, no commits."""
    require(runtime.space_hash == scope.embedding_space_hash, 'profile_incompatible')
    pointers = {(case['document_id'], case['page_number']) for case in cases.values()}
    pages = await snapshot._collect_pages(db, principal_id=scope.principal_id,
        subject_id=scope.subject_id, corpus_revision=scope.corpus_revision,
        embedding_space_hash=scope.embedding_space_hash, pointers=pointers,
        documents=documents, cases=cases)
    snapshot._validate_pages(pages, cases, documents, None, pointers=pointers,
        corpus_revision=scope.corpus_revision, embedding_space_hash=scope.embedding_space_hash)
    rows, counts = [], Counter()
    for case in cases.values():
        history = (('user', case['previous_turn']),) if case['previous_turn'] else ()
        query = runtime.navigation_query(case['question'], history)
        candidates, initial, prepared = [], (), None
        if query is not None:
            bound = await runtime.retriever.authorize(db,
                principal=SimpleNamespace(id=UUID(scope.principal_id)), subject_id=UUID(scope.subject_id),
                query=query, document_ids=[UUID(doc) for doc in documents],
                limit=runtime.retrieval_policy.max_results, policy=runtime.retrieval_policy)
            require(bound.scope.corpus_revision == scope.corpus_revision
                    and bound.scope.embedding_space_hash == scope.embedding_space_hash,
                    'scope_changed')
            retrieval = await bound.retrieve(embeddings[case['case_id']],
                                            embedding_space_hash=scope.embedding_space_hash)
            initial = retrieval.chunks
            pool = await runtime.candidate_pool(query, initial, bound)
            require(len(pool.selections) <= 4, 'candidate_binding_invalid')
            for ordinal, item in enumerate(pool.selections, 1):
                source = item.source
                require(str(source.document_id) in documents
                        and str(source.content_revision_id) == documents[str(source.document_id)]['content_revision_id']
                        and str(source.index_revision_id) == documents[str(source.document_id)]['index_revision_id']
                        and source.corpus_revision == scope.corpus_revision
                        and source.embedding_space_hash == scope.embedding_space_hash
                        and type(source.page_number) is int
                        and 1 <= source.page_number <= documents[str(source.document_id)]['original_pdf_page_count']
                        and item.source_kind == 'canonical_page' and type(item.page_content) is str
                        and 0 <= item.start_offset < item.end_offset <= len(item.page_content)
                        and item.end_offset - item.start_offset <= 480
                        and item.page_content[item.start_offset:item.end_offset] == item.quote,
                        'candidate_binding_invalid')
                candidates.append({'runtime_id': f'S{ordinal:02}',
                    'document_id': str(source.document_id), 'content_revision_id': str(source.content_revision_id),
                    'index_revision_id': str(source.index_revision_id), 'page_number': source.page_number,
                    'page_key': bridge._digest([str(source.document_id), source.page_number]),
                    'page_text': item.page_content, 'page_sha256': sha256(item.page_content.encode()).hexdigest(),
                    'start_offset': item.start_offset, 'end_offset': item.end_offset,
                    'cue_sha256': sha256(item.quote.encode()).hexdigest()})
            require(len({row['page_key'] for row in candidates}) == len(candidates), 'candidate_binding_invalid')
            if candidates:
                prepared = await runtime.visual_prepare(db, settings=runtime.settings, retriever=bound,
                    subject_id=UUID(scope.subject_id), question=case['question'], selections=pool.selections)
        rows.append({'case_id': case['case_id'], 'form': case['form'], 'question': case['question'],
            'local_retrieval_query': query, 'candidates': candidates,
            'request': prepared.request if prepared else None,
            'bindings': [asdict(binding) for binding in prepared.bindings] if prepared else []})
        counts['gold_in_initial'] += any(str(chunk.document_id) == case['document_id']
                                       and chunk.page_number == case['page_number'] for chunk in initial)
        counts['gold_in_pool'] += any(item['page_key'] == case['page_key'] for item in candidates)
        counts['candidate_pages'] += len(candidates)
        counts['visual_inputs_prepared'] += prepared is not None
        counts['clarification_needed'] += query is None
    body = {'schema': SCHEMA, 'policy': POLICY, 'contract': CONTRACT,
        'retrieval_mode': 'current_question_vector_hybrid', 'scope': gold['scope'],
        'principal_id': scope.principal_id, 'subject_id': scope.subject_id,
        'stage1_sha256': snapshot.FROZEN_STAGE1_SHA256,
        'source_snapshot_sha256': vectors.SOURCE_SNAPSHOT_SHA,
        'cases': rows, 'release_gate_passed': False}
    report = {'schema': SCHEMA, 'status': 'hybrid_inputs_prepared', 'case_count': len(rows),
        'forms': dict(Counter(row['form'] for row in rows)), **counts,
        'provider_calls': 0, 'automatic_retries': 0, 'database_writes': 0, 'release_gate_passed': False}
    return body, report


def write_exclusive(path: Path, body: bytes) -> None:
    require(0 < len(body) <= MAX_OUTPUT_BYTES, 'output_too_large')
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        path.chmod(0o600)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


async def execute(args, *, environment=None, root=None, runtime=None, session_factory=None):
    """Injection hooks are for synthetic contracts; CLI uses actual fenced services."""
    started = perf_counter()
    env = dict(os.environ) if environment is None else environment
    url = guard_runtime(env, args.expected_database)
    require(args.stage1_sha256 == snapshot.FROZEN_STAGE1_SHA256
            and args.source_sha256 == vectors.SOURCE_SNAPSHOT_SHA, 'input_changed')
    paths = [snapshot._temp_path(path, existing=True, root=root)
             for path in (args.stage1, args.source_snapshot, args.vectors)]
    output = snapshot._temp_path(args.output, existing=False, root=root)
    require(len({path.parent for path in (*paths, output)}) == 1
            and output.parent != (root or snapshot._temp_root()), 'private_directory_required')
    raw = [snapshot._read_hashed(path, digest, maximum=limit, code=code, root=root)
        for path, digest, limit, code in zip(paths,
            (args.stage1_sha256, args.source_sha256, args.vectors_sha256),
            (snapshot.MAX_STAGE1_BYTES, snapshot.MAX_OUTPUT_BYTES, MAX_VECTOR_BYTES),
            ('stage1_changed', 'source_changed', 'vector_packet_changed'), strict=True)]
    scope = Scope(args.principal_id, args.subject_id, args.corpus_revision, args.embedding_space_hash)
    gold, cases, documents, embeddings = prepare(*raw, vector_sha256=args.vectors_sha256, scope=scope)
    engine = None
    if runtime is None:
        guard_resources()
        runtime = load_runtime()
    require(runtime.space_hash == scope.embedding_space_hash, 'profile_incompatible')
    if session_factory is None:
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy.pool import NullPool
        engine = create_async_engine(url, echo=False, hide_parameters=True, poolclass=NullPool)
        session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    try:
        async with asyncio.timeout(max(.001, MAX_SECONDS - (perf_counter() - started))):
            async with session_factory() as db:
                try:
                    body, report = await collect(db, runtime=runtime, scope=scope,
                        gold=gold, cases=cases, documents=documents, embeddings=embeddings)
                finally:
                    await db.rollback()
            # Refuse an input swap during the diagnostic before publishing output.
            for path, digest, limit, original in zip(paths,
                (args.stage1_sha256, args.source_sha256, args.vectors_sha256),
                (snapshot.MAX_STAGE1_BYTES, snapshot.MAX_OUTPUT_BYTES, MAX_VECTOR_BYTES), raw, strict=True):
                require(snapshot._read_hashed(path, digest, maximum=limit, code='input_changed', root=root)
                        == original, 'input_changed')
            body['vectors_sha256'] = args.vectors_sha256
            encoded = canonical(body)
            require(perf_counter() - started < MAX_SECONDS, 'time_budget_exceeded')
            write_exclusive(output, encoded)
            if perf_counter() - started >= MAX_SECONDS:
                # This invocation owns the exclusive file; publish no late result.
                output.unlink(missing_ok=True)
                raise Refusal('time_budget_exceeded')
            return {**report, 'snapshot_sha256': sha256(encoded).hexdigest()}
    finally:
        if engine is not None:
            await asyncio.wait_for(engine.dispose(), timeout=max(.001, min(5, MAX_SECONDS - (perf_counter() - started))))


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--execute', action='store_true')
    for name in ('stage1', 'source-snapshot', 'vectors', 'output'):
        parser.add_argument('--' + name, type=Path)
    for name in ('stage1-sha256', 'source-sha256', 'vectors-sha256', 'principal-id',
                 'subject-id', 'embedding-space-hash', 'expected-database'):
        parser.add_argument('--' + name)
    parser.add_argument('--corpus-revision', type=int)
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({'schema': SCHEMA, 'status': 'unexecuted', 'database_reads': 0,
                          'database_writes': 0, 'provider_calls': 0, 'release_gate_passed': False}))
        return 0
    try:
        require(all(getattr(args, key) is not None for key in vars(args) if key != 'execute'),
                'arguments_invalid')
        result = asyncio.run(execute(args))
    except Exception:
        # Exception text/type, IDs, questions, raw requests and DB details stay private.
        result = {'schema': SCHEMA, 'status': 'refused_or_failed', 'provider_calls': 0,
                  'database_writes': 0, 'release_gate_passed': False}
    print(json.dumps(result))
    return 0 if result['status'] == 'hybrid_inputs_prepared' else 2


if __name__ == '__main__':
    raise SystemExit(main())
