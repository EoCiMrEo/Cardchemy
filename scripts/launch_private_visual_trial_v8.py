"""Inert host custody and isolated launch for the frozen private12 v8/v5 trial.

Default/CLI never obtains authority or reads a key. A future approved operator
must supply a fresh external approval SHA and explicitly activate this module.
Only an explicit bounded stdin message can deliver the judge key; root .env,
key files, argv and environment are never credential sources.
"""
from __future__ import annotations

import argparse
import ast
import base64
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import queue
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from uuid import uuid4

REPO = Path(__file__).resolve().parents[1]
LIVE_AUTHORIZED = False
SCHEMA = "private_visual_trial_v8_host"
HOST_PATH = "scripts/launch_private_visual_trial_v8.py"
ENTRY_PATH = "backend/scripts/private_visual_trial_entry_v8.py"
EXECUTOR_PATH = "backend/scripts/execute_private_visual_trial_v8.py"
HYBRID_SHA = "676b95a04e79ddcafef16049e6bc54566ded20885a51c67ed5cbb2affb6463bd"
MAX_STDIN_BYTES = 8192
MAX_CREDENTIAL_SECONDS = 5
MAX_AGGREGATE_BYTES = 128 * 1024
MAX_SECONDS = 1800
MEMORY_BYTES = 2147483648
PROFILE_NAMES = ("RAG_EMBEDDING_PROVIDER", "RAG_EMBEDDING_MODEL", "RAG_EMBEDDING_DIMENSIONS",
    "RAG_EMBEDDING_FORMAT_VERSION", "RAG_EMBEDDING_SPACE_REVISION", "RAG_EMBEDDING_REPRESENTATION", "RAG_EMBEDDING_METRIC")

# PID 1 owns the entire deadline, including credential forwarding. Its exit
# destroys the container namespace even if a renderer escapes the process group.
WATCHDOG = r'''
import json,os,select,signal,subprocess,sys,time
assert os.getpid()==1 and sys.argv[1]=='1800'
started=time.monotonic();worker=None
def stop(code,status):
    if worker is not None:
        try:os.killpg(worker.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    print(json.dumps({'status':status,'provider_usage_unknown':True,'release_gate_passed':False}),flush=True)
    os._exit(code)
signal.signal(signal.SIGALRM,lambda *_:stop(124,'hard_process_timeout'))
signal.alarm(1800)
raw=bytearray()
while True:
    if not select.select([sys.stdin.buffer],[],[],min(5,max(.001,1795-(time.monotonic()-started))))[0]:
        stop(2,'credential_stdin_timeout')
    part=os.read(sys.stdin.fileno(),8193-len(raw))
    if not part:break
    raw.extend(part)
    if len(raw)>8192:stop(2,'credential_stdin_oversize')
worker=subprocess.Popen(sys.argv[2:],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True)
worker.stdin.write(raw);worker.stdin.close();raw.clear()
out=bytearray()
while True:
    left=1795-(time.monotonic()-started)
    if left<=0:stop(124,'hard_process_timeout')
    if select.select([worker.stdout],[],[],min(1,left))[0]:
        part=os.read(worker.stdout.fileno(),4096)
        if not part:break
        out.extend(part)
        if len(out)>131072:stop(2,'aggregate_output_oversize')
try:code=worker.wait(timeout=max(.001,1795-(time.monotonic()-started)))
except subprocess.TimeoutExpired:stop(124,'hard_process_timeout')
sys.stdout.buffer.write(out);sys.stdout.buffer.flush()
os._exit(code if 0<=code<=255 else 2)
'''


class LaunchError(ValueError):
    """Only fixed content-free refusal codes leave this boundary."""


def require(ok, code):
    if not ok:
        raise LaunchError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(raw):
    return sha256(raw).hexdigest()


def _unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "json_duplicate_key")
        value[key] = item
    return value


def parse(raw, maximum):
    require(type(raw) is bytes and 0 < len(raw) <= maximum, "input_size_invalid")
    try:
        return json.loads(raw, object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(LaunchError("json_invalid")))
    except (ValueError, UnicodeError, RecursionError):
        raise LaunchError("json_invalid") from None


def path_check(path, *, directory=False):
    require(isinstance(path, Path) and path.is_absolute() and not path.is_symlink()
        and not getattr(path, "is_junction", lambda: False)()
        and path.resolve() == path.absolute()
        and (path.is_dir() if directory else path.is_file()), "path_invalid")


def bounded(path, maximum, *, allow_empty=False):
    path_check(path)
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    require(len(raw) <= maximum and (allow_empty or len(raw) > 0), "input_size_invalid")
    return raw


def exclusive(path, raw):
    path_check(path.parent, directory=True)
    require(not path.is_symlink() and not getattr(path, "is_junction", lambda: False)(), "path_invalid")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    except FileExistsError:
        raise LaunchError("one_use_already_claimed") from None
    except OSError:
        raise LaunchError("custody_write_failed") from None


def modules():
    # Lazy imports keep default startup independent from operator settings.
    sys.path.insert(0, str(REPO / "scripts"))
    sys.path.insert(0, str(REPO / "backend/scripts"))
    import prepare_private_visual_trial_v8 as preparation
    import run_private_visual_trial_v8 as custody
    import rehearse_private_visual_dispatch_v8 as rehearsal
    import execute_private_visual_trial_v8 as executor
    return preparation, custody, rehearsal, executor


def image_source_paths(seeds):
    """Static closure of every app import, including function-local imports."""
    queue = {path for path in seeds if path.startswith("backend/app/")}
    queue |= {"backend/app/__init__.py", "backend/app/models/__init__.py"}
    result = set()
    while queue:
        relative = queue.pop()
        if relative in result:
            continue
        result.add(relative)
        tree = ast.parse(bounded(REPO / relative, 1024 * 1024, allow_empty=True))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    parent = relative.removeprefix("backend/").removesuffix(".py").split("/")
                    parent = parent[:-1] if parent[-1] != "__init__" else parent[:-1]
                    base = ".".join(parent[:len(parent) - node.level + 1] + ([base] if base else []))
                names = [base] + [base + "." + alias.name for alias in node.names if alias.name != "*"]
            for name in names:
                if name == "app" or name.startswith("app."):
                    pieces = name.split(".")
                    for end in range(1, len(pieces) + 1):
                        stem = REPO / "backend" / Path(*pieces[:end])
                        for target in (stem.with_suffix(".py"), stem / "__init__.py"):
                            if target.is_file():
                                queue.add(target.relative_to(REPO).as_posix())
    result |= {path.relative_to(REPO).as_posix() for path in (REPO / "backend/alembic").rglob("*.py")}
    return result


def bind(prepared, directory, code):
    preparation, custody, rehearsal, _ = modules()
    packet = parse(dict(prepared.artifacts)["requests"], 48 * 1024 * 1024)
    raw = bounded(directory / "hybrid-preparation.json", 48 * 1024 * 1024)
    require(digest(raw) == HYBRID_SHA, "hybrid_changed")
    scope, pairs = rehearsal.bind_cases(prepared, packet, parse(raw, 48 * 1024 * 1024), code)
    bound = custody.BoundTrial(scope, tuple(case for case, _ in pairs), tuple(pin for _, pin in pairs))
    custody._validate_bound(prepared, bound, custody.binding_identity(bound))
    return bound


def stage(bridge: Path, hybrid: Path):
    require(HYBRID_SHA != "0" * 64, "matching_v8_freeze_required")
    preparation, custody, _, executor = modules()
    prepared = preparation.preflight_directory(bridge)
    artifact_pins = {preparation.FILES[name]: preparation.FROZEN_PINS[name] for name in preparation.ARTIFACT_NAMES}
    artifact_pins["hybrid-preparation.json"] = HYBRID_SHA
    source_paths = set(dict(prepared.code_sha256)) | custody.guard.REQUIRED_CODE_PATHS | {
        custody.CALLER_PATH, custody.GUARD_PATH, executor.REHEARSAL_PATH, EXECUTOR_PATH, ENTRY_PATH, HOST_PATH}
    require(len(source_paths) <= 100, "guard_code_capacity_exceeded")
    image_paths = image_source_paths(source_paths)
    root = Path(tempfile.mkdtemp(prefix="cardchemy-private-trial-v8-")).resolve()
    root.chmod(0o700)
    workspace, output = root / "workspace", root / "output"
    workspace.mkdir(mode=0o700); output.mkdir(mode=0o700)
    for name, pin in artifact_pins.items():
        raw = bounded(hybrid if name == "hybrid-preparation.json" else bridge / name, 48 * 1024 * 1024)
        require(digest(raw) == pin, "artifact_changed")
        exclusive(root / name, raw)
    code = {}
    for relative in sorted(source_paths | image_paths):
        require(preparation._code_path(relative), "code_path_invalid")
        target = workspace / relative
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        raw = bounded(REPO / relative, 1024 * 1024, allow_empty=True)
        exclusive(target, raw); code[relative] = digest(raw)
    exclusive(workspace / "watchdog.py", WATCHDOG.encode())
    guard_code = {name: code[name] for name in source_paths}
    bound = bind(prepared, root, guard_code)
    runtime = parse(dict(prepared.artifacts)["runtime"], 2 * 1024 * 1024)
    manifest = {"schema": SCHEMA + "_stage", "image": runtime["image_sha256"],
        "inputs": artifact_pins, "code": code, "guard_code": guard_code,
        "image_code": {name.removeprefix("backend/"): code[name] for name in image_paths},
        "watchdog_sha256": digest(WATCHDOG.encode()), "guards": preparation.guards(),
        "preflight_identity_sha256": preparation.report(prepared)["preflight_identity_sha256"],
        "binding_sha256": custody.binding_identity(bound)}
    exclusive(root / "manifest.json", canonical(manifest))
    return {"status": "staged", "directory": str(root), "stage_sha256": digest(canonical(manifest)),
        "cases": 12, "provider_calls": 0, "database_reads": 0, "database_writes": 0}


def stage_location(root, *, image=False, temp_root=None):
    parent = temp_root or Path(tempfile.gettempdir()).resolve()
    require(root.parent == parent and (root == Path("/tmp/private") if image else
        root.name.startswith("cardchemy-private-trial-v8-")), "private_temp_required")


def validate_stage(root, *, image=False):
    path_check(root, directory=True)
    stage_location(root, image=image)
    preparation, custody, _, _ = modules()
    raw = bounded(root / "manifest.json", 256 * 1024)
    manifest = parse(raw, 256 * 1024)
    require(type(manifest) is dict and set(manifest) == {"schema", "image", "inputs", "code", "guard_code",
        "image_code", "watchdog_sha256", "guards", "preflight_identity_sha256", "binding_sha256"}
        and manifest["schema"] == SCHEMA + "_stage" and canonical(manifest) == raw
        and manifest["guards"] == preparation.guards(), "stage_invalid")
    expected_inputs = {preparation.FILES[name]: preparation.FROZEN_PINS[name] for name in preparation.ARTIFACT_NAMES}
    expected_inputs["hybrid-preparation.json"] = HYBRID_SHA
    require(manifest["inputs"] == expected_inputs and re.fullmatch(r"sha256:[0-9a-f]{64}", manifest["image"]), "stage_invalid")
    verified_inputs = {}
    for name, pin in manifest["inputs"].items():
        raw = bounded(root / name, 48 * 1024 * 1024)
        require(digest(raw) == pin, "artifact_changed")
        verified_inputs[name] = raw
    require(type(manifest["code"]) is dict and 0 < len(manifest["code"]) <= 200, "code_set_invalid")
    verified_code = {}
    for name, pin in manifest["code"].items():
        require(preparation._code_path(name) and re.fullmatch(r"[0-9a-f]{64}", pin), "code_path_invalid")
        raw = bounded(REPO / name, 1024 * 1024, allow_empty=True)
        require(digest(bounded(root / "workspace" / name, 1024 * 1024, allow_empty=True)) == pin
            and digest(raw) == pin, "code_changed")
        verified_code[name] = raw
    require(digest(bounded(root / "workspace/watchdog.py", 32 * 1024)) == manifest["watchdog_sha256"]
        == digest(WATCHDOG.encode()), "watchdog_changed")
    # Reuse only bytes just verified in this startup invocation. The pure
    # preparation still checks all input pins, signed labels and runtime code;
    # no process/global cache survives to a later dispatch or selection guard.
    runtime = parse(verified_inputs[preparation.FILES["runtime"]], 2 * 1024 * 1024)
    preparation_paths = {"backend/" + name for name in runtime["runtime_source_hashes"]} | set(preparation.EXTRA_CODE_PATHS)
    require(preparation_paths <= set(verified_code), "runtime_code_incomplete")
    prepared = preparation.prepare(
        {name: verified_inputs[preparation.FILES[name]] for name in preparation.ARTIFACT_NAMES},
        current_code={name: verified_code[name] for name in preparation_paths})
    expected_guard = set(dict(prepared.code_sha256)) | custody.guard.REQUIRED_CODE_PATHS | {
        custody.CALLER_PATH, custody.GUARD_PATH, EXECUTOR_PATH, ENTRY_PATH, HOST_PATH,
        "backend/scripts/rehearse_private_visual_dispatch_v8.py"}
    require(manifest["guard_code"] == {name: manifest["code"][name] for name in expected_guard}, "guard_code_invalid")
    required_image = image_source_paths(expected_guard)
    require(manifest["image_code"] == {name.removeprefix("backend/"): manifest["code"][name] for name in required_image},
        "image_code_invalid")
    if image:
        for name, pin in manifest["image_code"].items():
            require(digest(bounded(Path("/app") / name, 1024 * 1024, allow_empty=True)) == pin, "image_code_changed")
    bound = bind(prepared, root, manifest["guard_code"])
    require(preparation.report(prepared)["preflight_identity_sha256"] == manifest["preflight_identity_sha256"]
        and custody.binding_identity(bound) == manifest["binding_sha256"]
        and parse(dict(prepared.artifacts)["runtime"], 2 * 1024 * 1024)["image_sha256"] == manifest["image"], "stage_binding_changed")
    path_check(root / "output", directory=True)
    return manifest, prepared, bound


def approval_payload(manifest, prepared, bound, *, trial_id, authorization_id, approved_at, expires_at,
    private_transfer_approved=False, provider_envelope_approved=False, free_tier_transfer_acknowledged=False,
    region_transfer_allowed=False):
    require(all(value is True for value in (private_transfer_approved, provider_envelope_approved,
        free_tier_transfer_acknowledged, region_transfer_allowed)), "external_authority_required")
    _, _, _, executor = modules()
    raw = executor.approval_payload(prepared, bound, trial_id=trial_id, authorization_id=authorization_id,
        approved_at=approved_at, expires_at=expires_at)
    return canonical({"schema": SCHEMA + "_approval", "stage_sha256": digest(canonical(manifest)),
        "inner_approval": parse(raw, 32 * 1024), "inner_approval_sha256": digest(raw),
        "private_transfer_approved": True, "provider_envelope_approved": True,
        "free_tier_transfer_acknowledged": True, "region_transfer_allowed": True})


def validate_approval(raw, external_sha, manifest, prepared, bound, *, now=None):
    require(type(external_sha) is str and re.fullmatch(r"[0-9a-f]{64}", external_sha)
        and digest(raw) == external_sha, "approval_unbound")
    value = parse(raw, 64 * 1024)
    require(type(value) is dict and canonical(value) == raw, "approval_invalid")
    try:
        inner = value["inner_approval"]
        from uuid import UUID
        expected = approval_payload(manifest, prepared, bound, trial_id=UUID(inner["trial_id"]),
            authorization_id=inner["authorization_id"], approved_at=datetime.fromisoformat(inner["approved_at_utc"]),
            expires_at=datetime.fromisoformat(inner["expires_at_utc"]),
            **{name: value[name] for name in ("private_transfer_approved", "provider_envelope_approved",
                "free_tier_transfer_acknowledged", "region_transfer_allowed")})
        current = now or datetime.now(timezone.utc)
        require(raw == expected and current.utcoffset().total_seconds() == 0
            and datetime.fromisoformat(inner["approved_at_utc"]) <= current
            < datetime.fromisoformat(inner["expires_at_utc"]), "approval_expired_or_changed")
    except (KeyError, TypeError, ValueError, AttributeError):
        raise LaunchError("approval_invalid") from None
    return canonical(inner), value["inner_approval_sha256"]


def credential_message(raw):
    value = parse(raw, MAX_STDIN_BYTES)
    require(type(value) is dict and set(value) == {"api_key"} and type(value["api_key"]) is str
        and 0 < len(value["api_key"]) <= 512 and all(32 < ord(c) < 127 for c in value["api_key"]),
        "credential_stdin_invalid")
    return canonical(value)


def read_credential_stdin(stdin):
    """Bound a binary stdin lookup without exposing reader exception details.

    A blocked reader is a daemon only: it cannot dispatch, persist its bytes or
    keep a failed host process alive. The durable approval claim stays consumed.
    """
    completion = queue.Queue(maxsize=1)
    def read():
        try:
            raw = stdin.read(MAX_STDIN_BYTES + 1)
            completion.put((True, raw))
        except BaseException:
            completion.put((False, None))
    threading.Thread(target=read, daemon=True).start()
    try:
        ok, raw = completion.get(timeout=MAX_CREDENTIAL_SECONDS)
    except queue.Empty:
        raise LaunchError("credential_stdin_timeout") from None
    require(ok, "credential_stdin_failed")
    return credential_message(raw)


def cli_env(extra=None):
    allowed = ("SystemRoot", "WINDIR", "TEMP", "TMP", "PATH", "PATHEXT", "USERPROFILE", "APPDATA", "LOCALAPPDATA")
    result = {name: os.environ[name] for name in allowed if os.environ.get(name)}
    result.update(extra or {})
    return result


def docker(args, *, env=None, timeout=30):
    result = subprocess.run(["docker", *args], cwd=REPO, env=env or cli_env(), capture_output=True,
        timeout=timeout, check=False)
    require(result.returncode == 0 and len(result.stdout) <= 2 * 1024 * 1024, "docker_refused")
    return result.stdout


def inspect_runtime(manifest, command=docker):
    ids = command(["ps", "--filter", "label=com.docker.compose.service=backend", "--format", "{{.ID}}"]).decode().split()
    require(len(ids) == 1, "retained_runtime_ambiguous")
    backend = parse(command(["inspect", ids[0]]), 2 * 1024 * 1024)[0]
    require(backend["Image"] == manifest["image"] and backend["State"]["Running"] is True
        and backend["State"]["Health"]["Status"] == "healthy", "retained_runtime_changed")
    probe = """import asyncio,hashlib,json,sys
from pathlib import Path
from app.config import Settings,ASK_REQUIRED_RELEASE_POLICY_VERSION
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
s=Settings(_env_file=None)
async def deployed_heads():
    engine=create_async_engine(s.database_url,echo=False,hide_parameters=True,poolclass=NullPool,
        connect_args={'server_settings':{'statement_timeout':'5000','lock_timeout':'1000','idle_in_transaction_session_timeout':'15000'}})
    try:
        async with asyncio.timeout(5):
            async with engine.connect() as db:
                txn=await db.begin()
                try:
                    await db.execute(text('SET TRANSACTION READ ONLY'))
                    return sorted((await db.execute(text('SELECT version_num FROM alembic_version'))).scalars().all())
                finally:await txn.rollback()
    finally:await engine.dispose()
print(json.dumps({'code':{p:hashlib.sha256((Path('/app')/p).read_bytes()).hexdigest() for p in json.loads(sys.argv[1])},
'heads':ScriptDirectory('/app/alembic').get_heads(),'database_heads':asyncio.run(deployed_heads()),'ask':s.rag_ask_enabled,'judge':s.rag_source_judge_provider_enabled,
'required':ASK_REQUIRED_RELEASE_POLICY_VERSION,'contract':s.rag_source_judge_contract_version,
'thinking':s.rag_source_judge_thinking_level,'output':s.rag_source_judge_max_output_tokens,'timeout':s.rag_source_judge_provider_timeout_seconds}))"""
    observed = parse(command(["exec", ids[0], "python", "-c", probe, json.dumps(sorted(manifest["image_code"]))]), 256 * 1024)
    require(observed == {"code": manifest["image_code"], "heads": ["20261002_0033"], "database_heads": ["20261002_0033"], "ask": False, "judge": False,
        "required": "related_knowledge_navigation_v8", "contract": "visual_source_id_v5", "thinking": "high",
        "output": 4096, "timeout": 120.0}, "retained_profile_changed")
    configured = dict(row.split("=", 1) for row in backend["Config"]["Env"] if "=" in row)
    env = {name: configured[name] for name in ("DATABASE_URL", "KNOWLEDGE_PDF_ENCRYPTION_KEY", *PROFILE_NAMES)}
    env.update(ENVIRONMENT="development", SECRET_KEY=secrets.token_urlsafe(48),
        GENERATION_SOURCE_ENCRYPTION_KEY=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("="),
        RAG_ENABLED="true", RAG_ASK_ENABLED="false", RAG_SOURCE_JUDGE_PROVIDER_ENABLED="false",
        RAG_SOURCE_JUDGE_CONTRACT_VERSION="visual_source_id_v5", RAG_SOURCE_JUDGE_THINKING_LEVEL="high",
        RAG_SOURCE_JUDGE_MAX_OUTPUT_TOKENS="4096", RAG_SOURCE_JUDGE_PROVIDER_TIMEOUT_SECONDS="120",
        RAG_SOURCE_JUDGE_REQUESTS_PER_MINUTE="5", RAG_SOURCE_JUDGE_INPUT_TOKENS_PER_MINUTE="250000",
        RAG_SOURCE_JUDGE_RATE_LIMIT_SAFETY_PERCENT="80", RAG_EMBEDDING_PROVIDER_ENABLED="false",
        RAG_AI_PROVIDER_ENABLED="false", FLASHCARD_AI_PROVIDER_ENABLED="false",
        PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", PYTHONUTF8="1", LOG_LEVEL="ERROR")
    require(not any(name.endswith("API_KEY") for name in env), "credential_environment_forbidden")
    networks = list(backend["NetworkSettings"]["Networks"])
    require(len(networks) == 1, "retained_network_ambiguous")
    return networks[0], env


def create_arguments(root, manifest, network, env, external_sha):
    command = ["create", "-i", "--name", "cardchemy-private-trial-v8-" + uuid4().hex,
        "--network", network, "--cpus", "4", "--memory", "2g", "--memory-swap", "2g",
        "--pids-limit", "128", "--read-only", "--user", "0:0", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=536870912",
        "--mount", f"type=bind,source={root},target=/tmp/private,readonly",
        "--mount", f"type=bind,source={root / 'workspace'},target=/workspace,readonly",
        "--mount", f"type=bind,source={root / 'output'},target=/tmp/output",
        "--entrypoint", "python"]
    for name in env:
        require(not name.endswith("API_KEY"), "credential_environment_forbidden")
        command += ["-e", name]
    return command + [manifest["image"], "/workspace/watchdog.py", "1800", "python",
        "/workspace/" + ENTRY_PATH, "--execute", "/tmp/private", "/tmp/output", external_sha]


def claim_registry():
    """A copied stage cannot restore an approval already consumed on this host."""
    root = Path(tempfile.gettempdir()).resolve() / "cardchemy-private-visual-v8-claims"
    if not root.exists():
        root.mkdir(mode=0o700)
    path_check(root, directory=True)
    return root


def execute(root, *, approval_sha256, stdin, command=docker, attach=subprocess.run):
    require(LIVE_AUTHORIZED is True, "private_execution_not_authorized")
    manifest, prepared, bound = validate_stage(root)
    approval_raw = bounded(root / "approval.json", 64 * 1024)
    validate_approval(approval_raw, approval_sha256, manifest, prepared, bound)
    network, env = inspect_runtime(manifest, command)
    # Host claim outlives container removal/restarts and is consumed before any
    # credential lookup. All local/provider failure attempts retain it.
    claim = canonical({"schema": SCHEMA + "_claim",
        "approval_sha256": approval_sha256, "stage_sha256": digest(canonical(manifest)),
        "claimed_at_utc": datetime.now(timezone.utc).isoformat(), "one_use": True})
    exclusive(claim_registry() / (approval_sha256 + ".json"), claim)
    exclusive(root / "output/host-claim.json", claim)
    key_message = read_credential_stdin(stdin)
    validate_approval(approval_raw, approval_sha256, manifest, prepared, bound)
    identity = None
    try:
        identity = command(create_arguments(root, manifest, network, env, approval_sha256), env=cli_env(env)).decode().strip()
        require(re.fullmatch(r"[0-9a-f]{12,64}", identity), "container_identity_invalid")
        created = parse(command(["inspect", identity]), 2 * 1024 * 1024)[0]
        limits = created["HostConfig"]
        require(created["Image"] == manifest["image"]
            and not any(row.split("=", 1)[0].endswith("API_KEY") for row in created["Config"]["Env"])
            and limits["NanoCpus"] == 4_000_000_000 and limits["Memory"] == limits["MemorySwap"] == MEMORY_BYTES
            and limits["ReadonlyRootfs"] is True and limits["PidsLimit"] == 128
            and limits.get("RestartPolicy", {}).get("Name") in ("no", ""), "container_fence_changed")
        began = time.monotonic()
        process = attach(["docker", "start", "-a", "-i", identity], cwd=REPO, env=cli_env(),
            input=key_message, capture_output=True, timeout=1820, check=False)
        key_message = b""
        require(0 < len(process.stdout) <= MAX_AGGREGATE_BYTES, "aggregate_invalid")
        result = parse(process.stdout, MAX_AGGREGATE_BYTES)
        state = parse(command(["inspect", identity]), 2 * 1024 * 1024)[0]["State"]
        require(state["Running"] is False, "container_still_running")
        require(type(result) is dict and result.get("schema") == "private_visual_trial_v8_execution"
            and result.get("provider_calls", 13) <= 12 and result.get("database_writes") == 0
            and result.get("embedding_calls") == result.get("answer_calls") == result.get("verifier_calls") == 0
            and result.get("automatic_retries") == 0 and result.get("release_gate_passed") is False,
            "aggregate_invalid")
        result.update(container_exit_code=state["ExitCode"], container_oom_killed=state["OOMKilled"],
            container_cpus=4, container_memory_bytes=MEMORY_BYTES, hard_process_seconds=1800,
            elapsed_seconds=round(time.monotonic() - began, 3), image_sha256=manifest["image"],
            stage_sha256=digest(canonical(manifest)), approval_sha256=approval_sha256)
        exclusive(root / "output/host-result.json", canonical(result))
        return result
    except Exception:
        exclusive(root / "output/host-failure.json", canonical({"schema": SCHEMA + "_failure",
            "status": "isolated_launch_stopped", "provider_usage_unknown": True,
            "approval_sha256": approval_sha256, "release_gate_passed": False}))
        raise LaunchError("isolated_launch_failed") from None
    finally:
        key_message = b""
        if identity:
            command(["rm", "-f", identity])


def main(argv=None):
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--hybrid", type=Path)
    parser.add_argument("--execute", type=Path)
    parser.add_argument("--approval-sha256")
    args = parser.parse_args(argv)
    if args.execute:
        # The CLI has no implicit activation or credential source.
        result = {"schema": SCHEMA, "status": "fresh_external_authority_required", "live_authorized": False,
            "provider_calls": 0, "database_reads": 0, "database_writes": 0}
        code = 2
    elif args.stage and args.hybrid:
        try:
            result = stage(args.stage, args.hybrid); code = 0
        except Exception:
            result = {"schema": SCHEMA, "status": "staging_refused", "provider_calls": 0}; code = 2
    else:
        result = {"schema": SCHEMA, "status": "unexecuted", "live_authorized": False, "provider_calls": 0}; code = 0
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
