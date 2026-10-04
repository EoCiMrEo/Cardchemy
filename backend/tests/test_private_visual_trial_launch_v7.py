"""Synthetic launch/entry custody; no Docker, provider, operator env or key reads."""
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import sys
import builtins
import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest

from test_private_visual_trial_v7_caller import synthetic_bound
from test_private_source_display_v7_score import NOW

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import launch_private_visual_trial_v7 as host
import private_visual_trial_entry_v7 as entry


@pytest.fixture
def bound_launch(monkeypatch, tmp_path):
    prepared, bound = synthetic_bound(monkeypatch)
    executor = host.modules()[-1]
    code = dict(bound.pins[0].code_sha256)
    for name in (executor.EXECUTOR_PATH, executor.REHEARSAL_PATH, host.HOST_PATH, host.ENTRY_PATH):
        code[name] = host.digest((host.REPO / name).read_bytes())
    bound = replace(bound, pins=tuple(replace(pin, code_sha256=code) for pin in bound.pins))
    manifest = {"schema": host.SCHEMA + "_stage", "image": "sha256:" + "b" * 64,
        "inputs": {}, "code": code, "guard_code": code, "image_code": {"app/config.py": "c" * 64},
        "watchdog_sha256": host.digest(host.WATCHDOG.encode()), "guards": host.modules()[0].guards(),
        "preflight_identity_sha256": host.modules()[0].report(prepared)["preflight_identity_sha256"],
        "binding_sha256": host.modules()[1].binding_identity(bound)}
    raw = host.approval_payload(manifest, prepared, bound, trial_id=uuid4(),
        authorization_id="invented_private_launch_authority", approved_at=NOW, expires_at=NOW + timedelta(hours=1),
        private_transfer_approved=True, provider_envelope_approved=True,
        free_tier_transfer_acknowledged=True, region_transfer_allowed=True)
    (tmp_path / "approval.json").write_bytes(raw)
    (tmp_path / "output").mkdir()
    registry = tmp_path / "registry"
    registry.mkdir()
    monkeypatch.setattr(host, "claim_registry", lambda: registry)
    monkeypatch.setattr(host, "validate_stage", lambda *a, **k: (manifest, prepared, bound))
    actual_validate = host.validate_approval
    monkeypatch.setattr(host, "validate_approval", lambda *a, **k: actual_validate(*a, **k, now=NOW))
    return manifest, prepared, bound, raw


def test_default_and_execute_cli_refuse_before_any_credential_or_docker_read(monkeypatch, capsys):
    def forbidden(*a, **k):
        pytest.fail("default startup cannot read credentials or Docker")
    monkeypatch.setattr(host, "stage", forbidden)
    monkeypatch.setattr(host, "docker", forbidden)
    assert host.LIVE_AUTHORIZED is False and entry.LIVE_AUTHORIZED is False
    assert host.main([]) == 0
    assert host.main(["--execute", "invented", "--approval-sha256", "a" * 64]) == 2
    assert entry.main([]) == 2
    assert all(json.loads(row)["provider_calls"] == 0 for row in capsys.readouterr().out.splitlines())


def test_imports_are_inert_with_operator_env_open_forbidden():
    code = """
import pathlib,sys
sys.path[:0]=sys.argv[1:]
def audit(event,args):
    if event=='open' and isinstance(args[0],(str,bytes)) and pathlib.Path(args[0]).name=='.env':
        raise RuntimeError('operator env forbidden')
sys.addaudithook(audit)
import launch_private_visual_trial_v7,private_visual_trial_entry_v7
assert 'app.database' not in sys.modules
assert not launch_private_visual_trial_v7.LIVE_AUTHORIZED
assert not private_visual_trial_entry_v7.LIVE_AUTHORIZED
print('imports_inert')
"""
    result = subprocess.run([sys.executable, "-I", "-c", code,
        str(host.REPO / "scripts"), str(host.REPO / "backend/scripts")],
        capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "imports_inert" and not result.stderr


@pytest.mark.parametrize("raw", [b"", b"{}", b'{"api_key":true}', b'{"api_key":"invented key"}',
    b'{"api_key":"invented","api_key":"replacement"}', b'{"api_key":"invented","file":".env"}', b"x" * 8193])
def test_credential_stdin_rejects_ambiguity_and_non_key_fields(raw):
    with pytest.raises(host.LaunchError):
        host.credential_message(raw)


def test_stdin_lookup_is_bounded_and_preserves_private_exception_details(monkeypatch):
    unblock = threading.Event()
    class Blocked:
        def read(self, maximum):
            assert maximum == 8193
            unblock.wait()
            return b'{"api_key":"invented-late-key"}'
    monkeypatch.setattr(host, "MAX_CREDENTIAL_SECONDS", .005)
    try:
        with pytest.raises(host.LaunchError, match="credential_stdin_timeout"):
            host.read_credential_stdin(Blocked())
    finally:
        unblock.set()
    class Failed:
        def read(self, maximum): raise RuntimeError("invented-private-key-never-log")
    with pytest.raises(host.LaunchError, match="credential_stdin_failed") as error:
        host.read_credential_stdin(Failed())
    assert "invented-private-key" not in str(error.value)


@pytest.mark.parametrize("change", ["sha", "stage", "region", "transfer", "expired", "code", "cost"])
def test_fresh_approval_binds_scope_stage_code_guards_and_transfer_flags(bound_launch, change):
    manifest, prepared, bound, raw = bound_launch
    # The fixture wraps current time only; mutate the exact external approval.
    payload = host.parse(raw, 64 * 1024)
    if change == "sha":
        pin = "0" * 64
    else:
        if change == "stage": payload["stage_sha256"] = "d" * 64
        elif change == "region": payload["region_transfer_allowed"] = False
        elif change == "transfer": payload["private_transfer_approved"] = False
        elif change == "expired": payload["inner_approval"]["expires_at_utc"] = NOW.isoformat()
        elif change == "code": payload["inner_approval"]["executor_sha256"] = "e" * 64
        elif change == "cost": payload["inner_approval"]["guards"]["max_cost_usd"] = "50"
        raw = host.canonical(payload); pin = host.digest(raw)
    with pytest.raises((host.LaunchError, host.modules()[-1].ExecutionError)):
        host.validate_approval(raw, pin, manifest, prepared, bound)


def test_exact_fresh_approval_roundtrips_bound_controller_payload(bound_launch):
    manifest, prepared, bound, raw = bound_launch
    inner, pin = host.validate_approval(raw, host.digest(raw), manifest, prepared, bound)
    assert host.digest(inner) == pin
    assert host.parse(inner, 32 * 1024)["guards"] == host.modules()[0].guards()


class DockerHarness:
    def __init__(self, manifest):
        self.manifest, self.commands, self.attached = manifest, [], []
        self.identity = "f" * 64
        self.env = {name: "invented-value" for name in host.PROFILE_NAMES}
        self.env.update(DATABASE_URL="postgresql+asyncpg://invented:invented@127.0.0.1:1/isolated_test",
            KNOWLEDGE_PDF_ENCRYPTION_KEY="invented-memory-only-archive-key")
        self.backend = {"Image": manifest["image"], "State": {"Running": True, "Health": {"Status": "healthy"}},
            "Config": {"Env": [name + "=" + value for name, value in self.env.items()]},
            "NetworkSettings": {"Networks": {"invented-private-network": {}}}}
        self.observed = {"code": manifest["image_code"], "heads": ["20261002_0032"], "database_heads": ["20261002_0032"], "ask": False,
            "judge": False, "required": "related_knowledge_navigation_v7", "contract": "visual_source_id_v3",
            "thinking": "high", "output": 4096, "timeout": 120.0}
        self.limits = {"NanoCpus": 4_000_000_000, "Memory": host.MEMORY_BYTES, "MemorySwap": host.MEMORY_BYTES,
            "ReadonlyRootfs": True, "PidsLimit": 128, "RestartPolicy": {"Name": "no"}}
        self.running = False
    def docker(self, args, **kwargs):
        self.commands.append((args, kwargs))
        if args[0] == "ps": return b"inventedbackend\n"
        if args[0] == "exec": return host.canonical(self.observed)
        if args[0] == "create": return self.identity.encode()
        if args[0] == "inspect":
            if args[1] == "inventedbackend": return host.canonical([self.backend])
            return host.canonical([{"HostConfig": self.limits, "Image": self.manifest["image"], "Config": {"Env": []},
                "State": {"Running": self.running, "ExitCode": 2, "OOMKilled": False}}])
        if args[0] == "rm": return b"removed"
        pytest.fail("unexpected synthetic Docker command")
    def attach(self, args, **kwargs):
        self.attached.append((args, kwargs))
        result = {"schema": "private_visual_trial_v7_execution", "status": "synthetic_inert_result",
            "provider_calls": 0, "database_writes": 0, "embedding_calls": 0, "answer_calls": 0,
            "verifier_calls": 0, "automatic_retries": 0, "release_gate_passed": False}
        return SimpleNamespace(stdout=host.canonical(result), stderr=b"", returncode=2)


def test_mock_launch_key_only_enters_bounded_stdin_and_durable_host_claim_blocks_replay(bound_launch, tmp_path, monkeypatch):
    manifest, _, _, approval = bound_launch
    harness = DockerHarness(manifest)
    monkeypatch.setattr(host, "LIVE_AUTHORIZED", True)
    key = b'{"api_key":"invented-explicit-stdin-key"}'
    result = host.execute(tmp_path, approval_sha256=host.digest(approval), stdin=io.BytesIO(key),
        command=harness.docker, attach=harness.attach)
    assert result["provider_calls"] == 0 and not result["release_gate_passed"]
    assert (tmp_path / "output/host-claim.json").exists()
    assert (tmp_path / "output/host-result.json").exists()
    assert harness.attached[0][1]["input"] == host.credential_message(key)
    assert harness.attached[0][1]["timeout"] == 1820
    create, kwargs = next(row for row in harness.commands if row[0][0] == "create")
    assert "-i" in create and create.count("--mount") == 3
    assert sum("readonly" in arg for arg in create) == 2
    assert "1800" in create and "--execute" in create
    assert not any("API_KEY" in name for name in kwargs["env"])
    assert "invented-explicit-stdin-key" not in str(harness.commands)
    assert "invented-explicit-stdin-key" not in str(harness.attached[0][0])
    assert "invented-explicit-stdin-key" not in str(harness.attached[0][1]["env"])
    assert not any(key in path.read_bytes() for path in (tmp_path / "output").iterdir())
    with pytest.raises(host.LaunchError, match="one_use_already_claimed"):
        host.execute(tmp_path, approval_sha256=host.digest(approval), stdin=io.BytesIO(key),
            command=harness.docker, attach=harness.attach)
    assert len(harness.attached) == 1


def test_copying_stage_cannot_replay_consumed_approval_from_host_registry(bound_launch, tmp_path, monkeypatch):
    manifest, _, _, raw = bound_launch
    harness = DockerHarness(manifest)
    monkeypatch.setattr(host, "LIVE_AUTHORIZED", True)
    host.execute(tmp_path, approval_sha256=host.digest(raw), stdin=io.BytesIO(b'{"api_key":"invented-key"}'),
        command=harness.docker, attach=harness.attach)
    copy = tmp_path / "copied-stage"
    copy.mkdir(); (copy / "output").mkdir(); (copy / "approval.json").write_bytes(raw)
    class Stdin:
        def read(self, *args): pytest.fail("copied consumed stage read a key")
    with pytest.raises(host.LaunchError, match="one_use_already_claimed"):
        host.execute(copy, approval_sha256=host.digest(raw), stdin=Stdin(), command=harness.docker,
            attach=harness.attach)
    assert len(harness.attached) == 1 and not (copy / "output/host-claim.json").exists()


@pytest.mark.parametrize("change", ["ask", "judge", "head", "database_head", "code", "contract"])
def test_mismatched_retained_profile_refuses_before_key_lookup(bound_launch, tmp_path, monkeypatch, change):
    manifest, _, _, approval = bound_launch
    harness = DockerHarness(manifest)
    if change == "ask": harness.observed["ask"] = True
    elif change == "judge": harness.observed["judge"] = True
    elif change == "head": harness.observed["heads"] = ["20261002_0031"]
    elif change == "database_head": harness.observed["database_heads"] = ["20261002_0031"]
    elif change == "code": harness.observed["code"] = {}
    else: harness.observed["contract"] = "visual_source_id_v4"
    monkeypatch.setattr(host, "LIVE_AUTHORIZED", True)
    class Stdin:
        def read(self, *args): pytest.fail("key lookup preceded profile verification")
    with pytest.raises(host.LaunchError, match="retained_profile_changed"):
        host.execute(tmp_path, approval_sha256=host.digest(approval), stdin=Stdin(), command=harness.docker,
            attach=harness.attach)
    assert not harness.attached and not (tmp_path / "output/host-claim.json").exists()


def test_invalid_approval_refuses_before_docker_or_key_lookup(bound_launch, tmp_path, monkeypatch):
    monkeypatch.setattr(host, "LIVE_AUTHORIZED", True)
    class Stdin:
        def read(self, *args): pytest.fail("unapproved key lookup")
    def command(*a, **k): pytest.fail("unapproved Docker access")
    with pytest.raises(host.LaunchError, match="approval_unbound"):
        host.execute(tmp_path, approval_sha256="a" * 64, stdin=Stdin(), command=command)


@pytest.mark.parametrize("failure", ["memory", "restart", "attach_timeout"])
def test_launch_failure_retains_claim_records_unknown_usage_and_removes_container(
    bound_launch, tmp_path, monkeypatch, failure,
):
    manifest, _, _, approval = bound_launch
    harness = DockerHarness(manifest)
    monkeypatch.setattr(host, "LIVE_AUTHORIZED", True)
    if failure == "memory": harness.limits["Memory"] = 4 * host.MEMORY_BYTES
    elif failure == "restart": harness.limits["RestartPolicy"]["Name"] = "always"
    def attach(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 1820)
    with pytest.raises(host.LaunchError, match="isolated_launch_failed"):
        host.execute(tmp_path, approval_sha256=host.digest(approval),
            stdin=io.BytesIO(b'{"api_key":"invented-failure-key"}'), command=harness.docker,
            attach=attach if failure == "attach_timeout" else harness.attach)
    saved = json.loads((tmp_path / "output/host-failure.json").read_bytes())
    assert saved["provider_usage_unknown"] and not saved["release_gate_passed"]
    assert (tmp_path / "output/host-claim.json").exists()
    assert harness.commands[-1][0] == ["rm", "-f", harness.identity]
    assert "invented-failure-key" not in json.dumps(saved)
    assert not harness.attached


def test_watchdog_has_namespace_exit_stdin_cap_and_hard_deadline():
    import ast
    ast.parse(host.WATCHDOG, feature_version=(3, 11))
    assert "os.getpid()==1" in host.WATCHDOG and "signal.alarm(1800)" in host.WATCHDOG
    assert "os.killpg(worker.pid,signal.SIGKILL)" in host.WATCHDOG and "os._exit" in host.WATCHDOG
    assert "len(raw)>8192" in host.WATCHDOG and "worker.stdin.write(raw)" in host.WATCHDOG
    assert "stderr=subprocess.DEVNULL" in host.WATCHDOG and "len(out)>131072" in host.WATCHDOG


def test_exact_docker_mount_path_is_accepted_only_by_container_stage_mode():
    # This is the literal argv/mount pair used by create_arguments, not the
    # differently named host Temp child.
    command = host.create_arguments(Path("/invented-stage"), {"image": "sha256:" + "b" * 64},
        "invented-network", {}, "a" * 64)
    container_input = Path(command[-3])
    assert str(container_input).replace("\\", "/") == "/tmp/private"
    assert "target=/tmp/private,readonly" in command[command.index("--mount") + 1]
    host.stage_location(container_input, image=True, temp_root=Path("/tmp"))
    with pytest.raises(host.LaunchError, match="private_temp_required"):
        host.stage_location(container_input, image=False, temp_root=Path("/tmp"))


@pytest.mark.asyncio
async def test_entry_invalid_authority_never_reads_stdin_or_settings(monkeypatch):
    class Stdin:
        def read(self, *args): pytest.fail("entry read key without external authority")
    with pytest.raises(host.LaunchError, match="private_execution_not_authorized"):
        await entry.execute(Path("/invented"), Path("/tmp/output"), None, stdin=Stdin())


def test_existing_file_or_redirecting_path_never_overwrites_claim(tmp_path):
    target = tmp_path / "claim.json"
    host.exclusive(target, b"original")
    with pytest.raises(host.LaunchError, match="one_use_already_claimed"):
        host.exclusive(target, b"replacement")
    assert target.read_bytes() == b"original"


def test_code_closure_reads_relative_and_from_alias_imports_only(tmp_path, monkeypatch):
    app = tmp_path / "backend/app"
    (app / "models").mkdir(parents=True)
    (tmp_path / "backend/alembic").mkdir()
    for name, text in {"__init__.py": "", "models/__init__.py": "from . import selected\n",
        "models/selected.py": "from app import dependency\n", "dependency.py": "VALUE=1\n"}.items():
        (app / name).write_text(text)
    monkeypatch.setattr(host, "REPO", tmp_path)
    paths = host.image_source_paths({"backend/app/models/__init__.py"})
    assert "backend/app/models/selected.py" in paths and "backend/app/dependency.py" in paths


@pytest.mark.asyncio
async def test_entry_checks_claim_and_profile_before_ram_key_and_preserves_no_replay(bound_launch, tmp_path, monkeypatch):
    manifest, _, _, raw = bound_launch
    output = tmp_path / "output"
    host.exclusive(output / "host-claim.json", host.canonical({"schema": host.SCHEMA + "_claim",
        "approval_sha256": host.digest(raw), "stage_sha256": host.digest(host.canonical(manifest)), "one_use": True}))
    events = []
    executor = host.modules()[-1]
    def settings(directory, bound):
        assert (output / "entry-claim.json").exists()
        events.append("profile")
        return object()
    monkeypatch.setattr(entry, "keyless_settings", settings)
    class Stdin:
        def read(self, maximum):
            assert maximum == 8193 and events == ["profile"]
            events.append("key")
            return b'{"api_key":"invented-entry-ram-key"}'
    async def controller(*args, **kwargs):
        assert executor.LIVE_AUTHORIZED is True and events == ["profile", "key"]
        assert kwargs["api_key"] == "invented-entry-ram-key"
        assert host.digest(kwargs["approval_bytes"]) == kwargs["approval_sha256"]
        assert kwargs["ledger"].directory == output
        events.append("controller")
        return {"status": "synthetic_inert_result", "provider_calls": 0}
    monkeypatch.setattr(executor, "execute_private_trial_v7", controller)
    result = await entry.execute(tmp_path, output, host.digest(raw), stdin=Stdin())
    assert result["provider_calls"] == 0 and not executor.LIVE_AUTHORIZED
    assert "invented-entry-ram-key" not in (output / "entry-claim.json").read_text()
    with pytest.raises(host.LaunchError, match="one_use_already_claimed"):
        await entry.execute(tmp_path, output, host.digest(raw), stdin=Stdin())
    assert events == ["profile", "key", "controller"]


@pytest.mark.asyncio
async def test_entry_missing_host_claim_cannot_load_settings_or_key(bound_launch, tmp_path, monkeypatch):
    def forbidden(*a, **k): pytest.fail("entry loaded settings without durable host claim")
    monkeypatch.setattr(entry, "keyless_settings", forbidden)
    class Stdin:
        def read(self, *args): pytest.fail("entry read key without durable host claim")
    with pytest.raises(host.LaunchError, match="path_invalid"):
        await entry.execute(tmp_path, tmp_path / "output", host.digest(bound_launch[-1]), stdin=Stdin())


@pytest.mark.parametrize("scenario", ["success", "deadline", "input_oversize", "output_oversize"])
def test_pid1_watchdog_forwards_stdin_without_logging_and_kills_namespace_on_failure(scenario):
    class Exit(BaseException):
        pass
    output, forwarded, kills, alarms = io.BytesIO(), [], [], []
    payload = b'{"api_key":"invented-watchdog-stdin-key"}'
    reads = {0: [b"x" * 8193 if scenario == "input_oversize" else payload, b""],
        10: [b"x" * 131073 if scenario == "output_oversize" else b'{"status":"synthetic"}', b""]}
    moments = iter([0, 0, 0, 1800 if scenario == "deadline" else 0, 0, 0, 0])
    def now(): return next(moments, 0)
    def exit_(code): raise Exit(code)
    worker = SimpleNamespace(pid=77, stdout=SimpleNamespace(fileno=lambda: 10),
        stdin=SimpleNamespace(write=lambda data: forwarded.append(bytes(data)), close=lambda: None),
        wait=lambda timeout: 0)
    modules = {"json": json,
        "os": SimpleNamespace(getpid=lambda: 1, read=lambda fd, maximum: reads[fd].pop(0),
            killpg=lambda pid, signal: kills.append((pid, signal)), _exit=exit_),
        "signal": SimpleNamespace(SIGKILL=9, SIGALRM=14, signal=lambda *a: None, alarm=lambda value: alarms.append(value)),
        "subprocess": SimpleNamespace(Popen=lambda *a, **k: worker, PIPE=-1, DEVNULL=-3,
            TimeoutExpired=subprocess.TimeoutExpired),
        "sys": SimpleNamespace(argv=["watchdog.py", "1800", "python", "inert-entry.py"],
            stdin=SimpleNamespace(buffer=object(), fileno=lambda: 0), stdout=SimpleNamespace(buffer=output)),
        "select": SimpleNamespace(select=lambda reads_, *a: (reads_, [], [])),
        "time": SimpleNamespace(monotonic=now)}
    real_import = builtins.__import__
    builtins_map = dict(vars(builtins))
    builtins_map["__import__"] = lambda name, *a, **k: modules[name] if name in modules else real_import(name, *a, **k)
    builtins_map["print"] = lambda value, **kwargs: output.write((value + "\n").encode())
    with pytest.raises(Exit) as stopped:
        exec(host.WATCHDOG, {"__builtins__": builtins_map})
    assert alarms == [1800] and payload not in output.getvalue()
    if scenario == "success":
        assert stopped.value.args == (0,) and forwarded == [payload] and not kills
        assert json.loads(output.getvalue())["status"] == "synthetic"
    elif scenario == "input_oversize":
        assert stopped.value.args == (2,) and not forwarded and not kills
        assert json.loads(output.getvalue())["status"] == "credential_stdin_oversize"
    else:
        assert forwarded == [payload] and kills == [(77, 9)]
        assert json.loads(output.getvalue())["release_gate_passed"] is False
