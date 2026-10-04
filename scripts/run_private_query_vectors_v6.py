"""Dormant, one-use outer caller for twelve private current-question embeddings.

No arguments performs no input, credential, Settings, DB or provider access.
Preparation/preflight are keyless. A future exact provider approval must set
the separate live flag/UUID and process token before execution. Only the
embedding credential may be injected through the process environment; this
caller never loads root .env. The immutable audited Windows supervisor assigns
a suspended worker to a four-CPU/two-GiB kill-tree Job before resuming it and
enforces a hard 360-second worker deadline. Neither a profile nor a receipt is
authorization, and a consumed UUID cannot be reused with another output path.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
from types import FunctionType, SimpleNamespace
from uuid import UUID

import prepare_private_query_vectors_v6 as builder

REPO = Path(__file__).resolve().parents[1]
SCHEMA = 'cardchemy_private_query_vectors_v6_caller'
LIVE_AUTHORIZED = True
APPROVAL_ID: str | None = '4443160a-1319-4ad2-b498-f8635bb50125'
APPROVAL_ENV = builder.APPROVAL_ENV
EMBEDDING_KEY_ENV = 'RAG_EMBEDDING_API_KEY'
LEDGER = builder.LEDGER
MAX_SECONDS = builder.MAX_TOTAL_SECONDS
MAX_APPROVAL_BYTES = 128 * 1024
MAX_PROFILE_BYTES = 4096
PROFILE_SCHEMA = SCHEMA + '_profile'
PROFILE_FIELDS = {'schema', 'space_revision', 'quota_bucket', 'requests_per_minute',
                  'input_tokens_per_minute', 'rate_limit_safety_percent'}
CODE_PATHS = (
    'scripts/run_private_query_vectors_v6.py',
    'scripts/prepare_private_query_vectors_v6.py',
    'scripts/snapshot_private_source_gold_v4.py',
    'scripts/bridge_private_source_gold_v4.py',
    'scripts/score_source_judgment_display_v4.py',
    'scripts/prepare_visual_page_source_input_v1.py',
    'scripts/launch_visual_public_calibration_v5.py',
    'backend/scripts/build_private_query_vectors.py',
    'backend/scripts/diagnose_source_navigation.py',
    'backend/app/config.py', 'backend/app/database.py',
    'backend/app/models/knowledge.py', 'backend/app/models/vector.py',
    'backend/app/ai/embeddings.py', 'backend/app/ai/chunking.py',
    'backend/app/ai/providers/__init__.py', 'backend/app/ai/rate_limit.py',
    'backend/requirements.txt',
)
require, canonical = builder.require, builder.canonical


def uuid4(value: object) -> UUID:
    try:
        parsed = UUID(value) if type(value) is str else None
    except ValueError:
        parsed = None
    require(parsed is not None and parsed.version == 4 and str(parsed) == value,
            'fresh_authorization_required')
    return parsed


def require_authorization(value: object) -> UUID:
    parsed = uuid4(value)
    require(LIVE_AUTHORIZED is True and APPROVAL_ID == value
            and os.environ.get(APPROVAL_ENV) == value, 'fresh_authorization_required')
    return parsed


def _read(path: Path, expected_sha: str, maximum: int) -> bytes:
    return builder.snapshot._read_hashed(path, expected_sha, maximum=maximum, code='input_changed')


def _json(raw: bytes) -> dict:
    try:
        value = json.loads(raw, object_pairs_hook=builder.snapshot._unique_object,
                           parse_constant=lambda _: require(False, 'input_invalid'))
    except (ValueError, UnicodeError, RecursionError):
        raise builder.Refusal('input_invalid') from None
    require(type(value) is dict, 'input_invalid')
    return value


def _small_json(path: Path) -> dict:
    """Read only bounded regular local control receipts, never source content."""
    require(path.is_file() and not path.is_symlink(), 'control_receipt_invalid')
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        details = os.fstat(stream.fileno())
        require(stat.S_ISREG(details.st_mode) and 0 < details.st_size <= 4096, 'control_receipt_invalid')
        raw = stream.read(4097)
    require(0 < len(raw) <= 4096, 'control_receipt_invalid')
    return _json(raw)


def validate_profile(profile: dict, space_hash: str) -> dict:
    """Reproduce the production length-framed identity without importing Settings."""
    require(type(profile) is dict and set(profile) == PROFILE_FIELDS
            and profile['schema'] == PROFILE_SCHEMA
            and type(profile['space_revision']) is str
            and re.fullmatch(r'[A-Za-z0-9._-]{1,64}', profile['space_revision']) is not None
            and type(profile['quota_bucket']) is str
            and re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', profile['quota_bucket']) is not None,
            'profile_incompatible')
    for field, minimum, maximum in (
        ('requests_per_minute', 1, 100_000),
        ('input_tokens_per_minute', builder.MAX_INPUT_TOKENS, 100_000_000),
        ('rate_limit_safety_percent', 1, 100),
    ):
        require(type(profile[field]) is int and minimum <= profile[field] <= maximum,
                'profile_incompatible')
    require(profile['input_tokens_per_minute'] * profile['rate_limit_safety_percent'] // 100
            >= builder.MAX_INPUT_TOKENS, 'profile_incompatible')
    identity = ('gemini', 'https://generativelanguage.googleapis.com', builder.MODEL,
                profile['space_revision'], 'raw_text_v1', builder.DIMENSIONS,
                'float32', 'cosine', 'RETRIEVAL_DOCUMENT', builder.TASK)
    framed = ''.join(f'{len(str(v).encode("utf-8"))}:{v}' for v in identity).encode()
    require(sha256(framed).hexdigest() == space_hash, 'profile_incompatible')
    return dict(profile)


def code_hashes() -> dict:
    # The reused supervisor imports historical public modules. Pin its complete
    # existing dependency manifest too; none of those files is modified here.
    import launch_visual_public_calibration_v5 as supervisor
    paths = tuple(dict.fromkeys(CODE_PATHS + supervisor.caller.CODE_PATHS))
    result = {}
    for name in paths:
        path = REPO / name
        require(path.is_file() and not path.is_symlink(), 'code_changed')
        result[name] = sha256(path.read_bytes()).hexdigest()
    return result


def guards() -> dict:
    return {'endpoint': builder.ENDPOINT, 'model': builder.MODEL, 'task': builder.TASK,
            'dimensions': builder.DIMENSIONS, 'max_calls': 12, 'batch_size': 1,
            'max_input_tokens': 512, 'max_call_seconds': 30, 'max_total_seconds': MAX_SECONDS,
            'price_guard_per_million_usd': '0.20', 'max_cost_usd': '0.001',
            'max_cpus': 4, 'max_memory_bytes': 2147483648, 'automatic_retries': 0,
            'database_reads': 0, 'database_writes': 0, 'answer_calls': 0,
            'source_judge_calls': 0, 'root_env_read': False, 'release_gate_passed': False}


def _output_directory(path: Path, *, existing: bool = False) -> Path:
    # The worker creates this fresh child of OS Temp with owner-only mode.
    root = builder.snapshot._temp_root()
    require(path.is_absolute() and not path.is_symlink()
            and path.parent.resolve(strict=True) == root
            and path.resolve(strict=False) != root, 'private_directory_required')
    if existing:
        require(path.is_dir(), 'private_directory_required')
        if os.name != 'nt':
            require(path.stat().st_mode & 0o077 == 0, 'private_directory_required')
    else:
        require(not path.exists(), 'output_exists')
    return path.resolve(strict=False)


def prepare_approval(*, stage1: Path, source: Path, profile: Path, profile_sha: str,
                     approval_id: str, output_dir: Path) -> dict:
    uuid4(approval_id)
    inputs = builder.prepare(
        _read(stage1, builder.snapshot.FROZEN_STAGE1_SHA256, builder.snapshot.MAX_STAGE1_BYTES),
        _read(source, builder.SOURCE_SNAPSHOT_SHA, builder.snapshot.MAX_OUTPUT_BYTES))
    validated = validate_profile(_json(_read(profile, profile_sha, MAX_PROFILE_BYTES)),
                                 inputs.embedding_space_hash)
    output = _output_directory(output_dir)
    return {'schema': SCHEMA + '_approval', 'approval_id': approval_id,
            'live_authorized': LIVE_AUTHORIZED,
            'stage1': str(stage1), 'stage1_sha256': inputs.stage1_sha256,
            'source': str(source), 'source_sha256': inputs.source_snapshot_sha256,
            'profile': str(profile), 'profile_sha256': profile_sha,
            'embedding_space_hash': inputs.embedding_space_hash,
            'question_roster_sha256': builder.QUERY_ROSTER_SHA,
            'estimated_input_tokens': inputs.estimated_input_tokens,
            'output_dir': str(output), 'profile_contract': validated,
            'code_sha256': code_hashes(), 'guards': guards()}


def admit(approval_file: Path, approval_sha: str, *, output_dir: Path,
          worker: bool = False) -> tuple[dict, builder.PreparedQueries]:
    packet = _json(_read(approval_file, approval_sha, MAX_APPROVAL_BYTES))
    required = {'schema', 'approval_id', 'live_authorized', 'stage1', 'stage1_sha256',
                'source', 'source_sha256', 'profile', 'profile_sha256',
                'embedding_space_hash', 'question_roster_sha256', 'estimated_input_tokens',
                'output_dir', 'profile_contract', 'code_sha256', 'guards'}
    require(set(packet) == required and packet['schema'] == SCHEMA + '_approval', 'approval_invalid')
    # A worker's directory has been exclusively created after resource admission.
    output = _output_directory(output_dir, existing=worker)
    require(packet['output_dir'] == str(output), 'approval_invalid')
    inputs = builder.prepare(
        _read(Path(packet['stage1']), builder.snapshot.FROZEN_STAGE1_SHA256, builder.snapshot.MAX_STAGE1_BYTES),
        _read(Path(packet['source']), builder.SOURCE_SNAPSHOT_SHA, builder.snapshot.MAX_OUTPUT_BYTES))
    profile = validate_profile(_json(_read(Path(packet['profile']), packet['profile_sha256'], MAX_PROFILE_BYTES)),
                               inputs.embedding_space_hash)
    expected = {'schema': SCHEMA + '_approval', 'approval_id': packet['approval_id'],
                'live_authorized': LIVE_AUTHORIZED, 'stage1': packet['stage1'],
                'stage1_sha256': inputs.stage1_sha256, 'source': packet['source'],
                'source_sha256': inputs.source_snapshot_sha256, 'profile': packet['profile'],
                'profile_sha256': packet['profile_sha256'], 'embedding_space_hash': inputs.embedding_space_hash,
                'question_roster_sha256': builder.QUERY_ROSTER_SHA,
                'estimated_input_tokens': inputs.estimated_input_tokens, 'output_dir': str(output),
                'profile_contract': profile, 'code_sha256': code_hashes(), 'guards': guards()}
    uuid4(packet['approval_id'])
    require(packet == expected, 'approval_changed')
    return packet, inputs


def _marker(approval_id: str, suffix: str) -> Path:
    require(suffix in ('launch', 'worker'), 'claim_invalid')
    parsed = uuid4(approval_id)
    return LEDGER / ('.query-v6-' + sha256(parsed.bytes).hexdigest() + '.caller-' + suffix + '.used')


def claim(packet: dict, approval_sha: str, *, role: str) -> dict:
    require_authorization(packet['approval_id'])
    require(packet['live_authorized'] is True, 'fresh_authorization_required')
    require(not LEDGER.is_symlink() and not LEDGER.parent.is_symlink(), 'ledger_invalid')
    LEDGER.mkdir(mode=0o700, parents=True, exist_ok=True)
    parsed = uuid4(packet['approval_id'])
    require(not (LEDGER / ('.query-v6-' + sha256(parsed.bytes).hexdigest() + '.used')).exists(),
            'previous_attempt_not_replayable')
    body = {'schema': SCHEMA + '_claim', 'approval_id': packet['approval_id'],
            'approval_sha256': approval_sha, 'output_dir': packet['output_dir'],
            'stage1_sha256': packet['stage1_sha256'], 'source_sha256': packet['source_sha256'],
            'profile_sha256': packet['profile_sha256'], 'role': role}
    if role == 'worker':
        launch = _marker(packet['approval_id'], 'launch')
        require(launch.is_file() and not launch.is_symlink()
                and launch.read_bytes() == canonical(dict(body, role='launch')), 'launch_claim_missing')
    builder.snapshot._write_exclusive(_marker(packet['approval_id'], role), canonical(body))
    return body


def child_env(source: dict, *, approval_id: str) -> dict:
    """Called only after the durable launch claim; never read root configuration."""
    require_authorization(approval_id)
    marker = _marker(approval_id, 'launch')
    require(marker.is_file() and not marker.is_symlink(), 'launch_claim_missing')
    launch = _small_json(marker)
    require(launch.get('schema') == SCHEMA + '_claim' and launch.get('approval_id') == approval_id
            and launch.get('role') == 'launch', 'launch_claim_missing')
    key = source.get(EMBEDDING_KEY_ENV)
    require(type(key) is str and bool(key.strip()) and len(key) <= 4096
            and '\x00' not in key, 'embedding_credentials_unavailable')
    env = {k: source[k] for k in ('SystemRoot', 'WINDIR', 'TEMP', 'TMP') if source.get(k)}
    env.update(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1',
               PYTHONPATH=str(REPO / 'backend'), ENVIRONMENT='test',
               DATABASE_URL='sqlite+aiosqlite:///:memory:',
               SECRET_KEY=secrets.token_urlsafe(48),
               GENERATION_SOURCE_ENCRYPTION_KEY=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('='),
               RAG_ENABLED='false', RAG_ASK_ENABLED='false',
               FLASHCARD_AI_PROVIDER_ENABLED='false', RAG_AI_PROVIDER_ENABLED='false',
               RAG_SOURCE_JUDGE_PROVIDER_ENABLED='false')
    env[EMBEDDING_KEY_ENV], env[APPROVAL_ENV] = key, approval_id
    return env


def scoped_settings(profile: dict, inputs: builder.PreparedQueries):
    """Only the resource-admitted worker calls this embedding-only key loader."""
    require(os.environ.get('ENVIRONMENT') == 'test', 'isolated_environment_required')
    forbidden = builder.snapshot._AI_CREDENTIAL_NAMES - {EMBEDDING_KEY_ENV}
    require(not any(os.environ.get(k, '').strip() for k in forbidden), 'isolated_environment_required')
    from app.config import Settings
    # The isolated child whitelist is also enforced at this entry point, so a
    # manually invoked worker cannot make BaseSettings inspect unrelated roles.
    allowed = {'ENVIRONMENT', 'DATABASE_URL', 'SECRET_KEY', 'GENERATION_SOURCE_ENCRYPTION_KEY',
               'RAG_ENABLED', 'RAG_ASK_ENABLED', 'FLASHCARD_AI_PROVIDER_ENABLED',
               'RAG_AI_PROVIDER_ENABLED', 'RAG_SOURCE_JUDGE_PROVIDER_ENABLED', EMBEDDING_KEY_ENV}
    settings_names = {name.upper() for name in Settings.model_fields}
    require(not any(name.upper() in settings_names and name.upper() not in allowed and value.strip()
                    for name, value in os.environ.items()), 'isolated_environment_required')
    current = Settings(_env_file=None,
        environment='test', database_url='sqlite+aiosqlite:///:memory:',
        secret_key=os.environ['SECRET_KEY'],
        generation_source_encryption_key=os.environ['GENERATION_SOURCE_ENCRYPTION_KEY'],
        flashcard_ai_provider_enabled=False, flashcard_ai_api_key=None,
        rag_enabled=False, rag_ask_enabled=False, rag_ai_provider_enabled=False, rag_ai_api_key=None,
        rag_source_judge_provider_enabled=False, rag_source_judge_api_key=None,
        knowledge_pdf_encryption_key=None, rag_embedding_provider_enabled=True,
        rag_embedding_api_key=os.environ[EMBEDDING_KEY_ENV],
        rag_embedding_provider='gemini', rag_embedding_model=builder.MODEL,
        rag_embedding_base_url=None, rag_embedding_dimensions=builder.DIMENSIONS,
        rag_embedding_space_revision=profile['space_revision'], rag_embedding_format_version='raw_text_v1',
        rag_embedding_representation='float32', rag_embedding_metric='cosine',
        rag_embedding_batch_size=1, rag_embedding_provider_max_retries=0,
        rag_embedding_provider_timeout_seconds=30, rag_embedding_max_input_tokens=512,
        rag_embedding_input_cost_per_million_usd=builder.PRICE_GUARD,
        rag_embedding_max_estimated_cost_usd=builder.MAX_COST_USD,
        rag_embedding_concurrency=1, rag_embedding_quota_bucket=profile['quota_bucket'],
        rag_embedding_requests_per_minute=profile['requests_per_minute'],
        rag_embedding_input_tokens_per_minute=profile['input_tokens_per_minute'],
        rag_embedding_rate_limit_safety_percent=profile['rate_limit_safety_percent'])
    return builder.bounded_settings(current, inputs)


def supervise(approval_file: Path, approval_sha: str, output_dir: Path) -> None:
    packet, _ = admit(approval_file, approval_sha, output_dir=output_dir)
    require_authorization(packet['approval_id'])
    require(os.name == 'nt', 'resource_mode_unavailable')
    claim(packet, approval_sha, role='launch')
    import launch_visual_public_calibration_v5 as audited
    # Reuse the exact reviewed suspended-process/Job/kill-tree implementation
    # in isolated globals, without modifying its historical file or module.
    namespace = dict(audited.supervise.__globals__, caller=SimpleNamespace(LIVE_AUTHORIZED=True),
        CALLER=Path(__file__).resolve(), MAX_SECONDS=MAX_SECONDS,
        child_env=lambda source: child_env(source, approval_id=packet['approval_id']),
        write_new=lambda path, value: builder.snapshot._write_exclusive(path, canonical(value)))
    FunctionType(audited.supervise.__code__, namespace)(approval_file, approval_sha, output_dir)
    complete = _small_json(output_dir.with_name(output_dir.name + '.supervisor-complete.json'))
    require(complete.get('approval_sha256') == approval_sha and complete.get('exit_code') == 0,
            'resource_worker_failed')
    # A killed worker may have checkpoints but no aggregate; that absence must
    # be treated as unknown physical attempts/cost, never as zero attempts.
    require((output_dir / 'aggregate.json').is_file(), 'worker_aggregate_missing')


def resource_worker_pid_matches(recorded_pid: object) -> bool:
    """A Windows venv redirector can be the resource-assigned direct parent.

    The current interpreter must already pass the named Job/limit check.
    Accept only that current PID or its immediate Windows parent; never an
    arbitrary ancestor or a process found merely by executable name.
    """
    if type(recorded_pid) is not int or recorded_pid <= 0:
        return False
    return recorded_pid == os.getpid() or (os.name == 'nt' and recorded_pid == os.getppid())


async def worker(approval_file: Path, approval_sha: str, output_dir: Path, resource_job: str,
                 *, settings_factory=None, provider_factory=None) -> dict:
    require_authorization(APPROVAL_ID)
    import prepare_visual_page_source_input_v1 as resource
    resource_job = resource.validate_resource_job_name(resource_job)
    prior_name = resource.RESOURCE_JOB_NAME
    try:
        resource.RESOURCE_JOB_NAME = resource_job
        require(resource._inside_windows_job(), 'enforceable_resource_mode_required')
    finally:
        resource.RESOURCE_JOB_NAME = prior_name
    _output_directory(output_dir)
    # The supervisor's exclusive receipt exists before ResumeThread.
    receipt_path = output_dir.with_name(output_dir.name + '.resource-process.json')
    require(receipt_path.is_file() and not receipt_path.is_symlink(), 'resource_receipt_missing')
    receipt = _small_json(receipt_path)
    require(resource_worker_pid_matches(receipt.get('worker_pid')) and receipt.get('resource_job') == resource_job
            and receipt.get('approval_sha256') == approval_sha and receipt.get('cpus') == 4
            and receipt.get('memory_bytes') == 2147483648 and receipt.get('timeout_seconds') == MAX_SECONDS
            and receipt.get('kill_tree_on_close') is True, 'resource_receipt_invalid')
    output_dir.mkdir(mode=0o700)
    packet, inputs = admit(approval_file, approval_sha, output_dir=output_dir, worker=True)
    claim(packet, approval_sha, role='worker')
    # No Settings or embedding credential was read before these boundaries.
    current = (settings_factory or scoped_settings)(packet['profile_contract'], inputs)
    old = builder.LIVE_AUTHORIZED, builder.APPROVAL_ID, builder.LEDGER
    try:
        builder.LIVE_AUTHORIZED, builder.APPROVAL_ID, builder.LEDGER = True, packet['approval_id'], LEDGER
        report = await builder.build_packet(inputs, current, output=output_dir / 'vectors.json',
                                           approval_id=packet['approval_id'], provider_factory=provider_factory)
        builder.snapshot._write_exclusive(output_dir / 'aggregate.json', canonical(report))
        return report
    finally:
        builder.LIVE_AUTHORIZED, builder.APPROVAL_ID, builder.LEDGER = old


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(__doc__)
    modes = parser.add_mutually_exclusive_group()
    for mode in ('prepare-approval', 'preflight', 'execute', 'worker'):
        modes.add_argument('--' + mode, action='store_true')
    for name in ('stage1', 'source', 'profile', 'approval-file', 'output-dir'):
        parser.add_argument('--' + name, type=Path)
    for name in ('profile-sha', 'approval-id', 'approval-sha', 'resource-job'):
        parser.add_argument('--' + name)
    args = parser.parse_args(argv)
    if not any((args.prepare_approval, args.preflight, args.execute, args.worker)):
        print(json.dumps({'schema': SCHEMA, 'status': 'unexecuted', 'provider_calls': 0,
                          'database_reads': 0, 'database_writes': 0, 'live_authorized': False}))
        return 0
    try:
        require(args.approval_file is not None and args.output_dir is not None, 'arguments_invalid')
        if args.prepare_approval:
            require(all((args.stage1, args.source, args.profile, args.profile_sha, args.approval_id)),
                    'arguments_invalid')
            packet = prepare_approval(stage1=args.stage1, source=args.source, profile=args.profile,
                profile_sha=args.profile_sha, approval_id=args.approval_id, output_dir=args.output_dir)
            destination = builder.snapshot._temp_path(args.approval_file, existing=False)
            require(destination.parent != builder.snapshot._temp_root(), 'private_directory_required')
            raw = canonical(packet)
            builder.snapshot._write_exclusive(destination, raw)
            report = {'status': 'prospective_approval_prepared', 'approval_sha256': sha256(raw).hexdigest(),
                      'live_authorized': LIVE_AUTHORIZED, 'provider_calls': 0}
        elif args.preflight:
            packet, inputs = admit(args.approval_file, args.approval_sha, output_dir=args.output_dir)
            report = dict(builder.aggregate(inputs), status='preflight_passed',
                          pinned_code_files=len(packet['code_sha256']))
        elif args.execute:
            require_authorization(APPROVAL_ID)
            supervise(args.approval_file, args.approval_sha, args.output_dir)
            report = {'status': 'supervisor_completed', 'release_gate_passed': False}
        else:
            require(args.resource_job is not None, 'arguments_invalid')
            report = asyncio.run(worker(args.approval_file, args.approval_sha,
                                        args.output_dir, args.resource_job))
        print(json.dumps(report, sort_keys=True))
        return 0 if report.get('status') != 'stopped' else 1
    except Exception:
        # No traceback, question, vector, key, internal exception or path.
        print(json.dumps({'schema': SCHEMA, 'status': 'refused', 'release_gate_passed': False,
                          'failed_attempt_cost_unknown': bool(args.execute or args.worker)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
