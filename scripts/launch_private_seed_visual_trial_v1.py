"""Keyless seed14 staging and prospective isolated host; no implicit authority.

Shared v8 host function bodies use this adapter's isolated globals. The seed
stage has a separate namespace, exact review witness, code pins and one-use
registry. CLI execution stays inert; a separately authorized operator must
supply the SHA of an explicit transfer/envelope acknowledgement before stdin.
"""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import FunctionType
import launch_private_visual_trial_v8 as base
for _name, _value in vars(base).items():
    if not _name.startswith("__") and (not isinstance(_value, FunctionType) or _value.__module__ != base.__name__):
        globals()[_name] = _value
REPO = Path(__file__).resolve().parents[1]
SCHEMA = "private_seed_visual_trial_v1_host"
HOST_PATH = "scripts/launch_private_seed_visual_trial_v1.py"
ENTRY_PATH = "backend/scripts/private_seed_visual_trial_entry_v1.py"
EXECUTOR_PATH = "backend/scripts/execute_private_seed_visual_trial_v1.py"
REHEARSAL_PATH = "backend/scripts/rehearse_private_seed_visual_dispatch_v1.py"
LIVE_AUTHORIZED = False
MAX_SECONDS = 2400
WATCHDOG = base.WATCHDOG.replace("1800", "2400").replace("1795", "2395")

def _shared(function):
    result = FunctionType(function.__code__, globals(), function.__name__, function.__defaults__, function.__closure__)
    result.__kwdefaults__ = function.__kwdefaults__
    return result

for _name in ("require", "canonical", "digest", "_unique", "parse", "path_check", "bounded", "exclusive",
    "image_source_paths", "approval_payload", "validate_approval", "credential_message", "read_credential_stdin", "cli_env", "docker", "inspect_runtime"):
    globals()[_name] = _shared(getattr(base, _name))

def modules():
    sys.path.insert(0, str(REPO / "scripts")); sys.path.insert(0, str(REPO / "backend/scripts"))
    import prepare_private_seed_visual_trial_v1 as preparation
    import run_private_seed_visual_trial_v1 as custody
    import rehearse_private_seed_visual_dispatch_v1 as rehearsal
    import execute_private_seed_visual_trial_v1 as executor
    return preparation, custody, rehearsal, executor

def bind(prepared, directory, code):
    preparation, custody, rehearsal, _ = modules()
    packet = parse(dict(prepared.artifacts)["source"], 64 * 1024 * 1024)
    scope, pairs = rehearsal.bind_cases(prepared, packet, code)
    bound = custody.BoundTrial(scope, tuple(case for case, _ in pairs), tuple(pin for _, pin in pairs))
    custody._validate_bound(prepared, bound, custody.binding_identity(bound))
    return bound

def stage(directory):
    preparation, custody, _, _ = modules()
    prepared = preparation.preflight_directory(directory)
    source_paths = set(dict(prepared.code_sha256)) | custody.guard.REQUIRED_CODE_PATHS | set(preparation.SEED_CODE_PATHS)
    require(len(source_paths) <= 100, "guard_code_capacity_exceeded")
    image_paths = image_source_paths(source_paths)
    root = Path(tempfile.mkdtemp(prefix="cardchemy-private-seed-trial-v1-")).resolve(); root.chmod(0o700)
    (root / "workspace").mkdir(mode=0o700); (root / "output").mkdir(mode=0o700)
    inputs = {preparation.FILES[name]: preparation.FROZEN_PINS[name] for name in preparation.ARTIFACT_NAMES}
    for name in inputs:
        raw = bounded(directory / name, 64 * 1024 * 1024)
        require(digest(raw) == inputs[name], "artifact_changed"); exclusive(root / name, raw)
    code = {}
    for relative in sorted(source_paths | image_paths):
        require(preparation._code_path(relative), "code_path_invalid")
        target = root / "workspace" / relative; target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        raw = bounded(REPO / relative, 1024 * 1024, allow_empty=True)
        exclusive(target, raw); code[relative] = digest(raw)
    exclusive(root / "workspace/watchdog.py", WATCHDOG.encode())
    guard_code = {name: code[name] for name in source_paths}
    bound = bind(prepared, root, guard_code)
    runtime = parse(dict(prepared.artifacts)["runtime"], 2 * 1024 * 1024)
    manifest = {"schema": SCHEMA + "_stage", "image": runtime["image_sha256"], "inputs": inputs,
        "code": code, "guard_code": guard_code, "image_code": {name.removeprefix("backend/"): code[name] for name in image_paths},
        "watchdog_sha256": digest(WATCHDOG.encode()), "guards": preparation.guards(),
        "preflight_identity_sha256": preparation.report(prepared)["preflight_identity_sha256"], "binding_sha256": custody.binding_identity(bound)}
    exclusive(root / "manifest.json", canonical(manifest))
    return {"status": "staged", "directory": str(root), "stage_sha256": digest(canonical(manifest)),
        "cases": 14, "provider_calls": 0, "database_reads": 0, "database_writes": 0}

def validate_stage(root, *, image=False):
    preparation, custody, _, _ = modules()
    path_check(root, directory=True)
    require(root == Path("/tmp/private") if image else root.parent == Path(tempfile.gettempdir()).resolve()
        and root.name.startswith("cardchemy-private-seed-trial-v1-"), "private_temp_required")
    raw = bounded(root / "manifest.json", 256 * 1024); manifest = parse(raw, 256 * 1024)
    require(set(manifest) == {"schema", "image", "inputs", "code", "guard_code", "image_code", "watchdog_sha256", "guards", "preflight_identity_sha256", "binding_sha256"}
        and manifest["schema"] == SCHEMA + "_stage" and canonical(manifest) == raw
        and manifest["guards"] == preparation.guards(), "stage_invalid")
    inputs = {preparation.FILES[name]: preparation.FROZEN_PINS[name] for name in preparation.ARTIFACT_NAMES}
    require(manifest["inputs"] == inputs and re.fullmatch(r"sha256:[0-9a-f]{64}", manifest["image"]), "stage_invalid")
    verified_inputs = {}
    for name, pin in inputs.items():
        raw = bounded(root / name, 64 * 1024 * 1024)
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
    require(digest(bounded(root / "workspace/watchdog.py", 32768)) == manifest["watchdog_sha256"] == digest(WATCHDOG.encode()), "watchdog_changed")
    # Reuse only bytes verified in this invocation, never a global cache.
    # Preparation still hashes the exact inputs and the exact required runtime
    # subset; unrelated staged image-closure files cannot widen that contract.
    runtime = parse(verified_inputs[preparation.FILES["runtime"]], 2 * 1024 * 1024)
    preparation_paths = {"backend/" + name for name in runtime["runtime_source_hashes"]} | set(preparation.EXTRA_CODE_PATHS)
    require(preparation_paths <= set(verified_code), "runtime_code_incomplete")
    prepared = preparation.prepare({name: verified_inputs[preparation.FILES[name]] for name in preparation.ARTIFACT_NAMES},
        current_code={name: verified_code[name] for name in preparation_paths})
    expected_guard = set(dict(prepared.code_sha256)) | custody.guard.REQUIRED_CODE_PATHS | set(preparation.SEED_CODE_PATHS)
    require(manifest["guard_code"] == {name: manifest["code"][name] for name in expected_guard}, "guard_code_invalid")
    required_image = image_source_paths(expected_guard)
    require(manifest["image_code"] == {name.removeprefix("backend/"): manifest["code"][name] for name in required_image}, "image_code_invalid")
    if image:
        for name, pin in manifest["image_code"].items():
            require(digest(bounded(Path("/app") / name, 1024 * 1024, allow_empty=True)) == pin, "image_code_changed")
    bound = bind(prepared, root, manifest["guard_code"])
    require(preparation.report(prepared)["preflight_identity_sha256"] == manifest["preflight_identity_sha256"]
        and custody.binding_identity(bound) == manifest["binding_sha256"]
        and parse(dict(prepared.artifacts)["runtime"], 2 * 1024 * 1024)["image_sha256"] == manifest["image"], "stage_binding_changed")
    path_check(root / "output", directory=True)
    return manifest, prepared, bound

def create_arguments(root, manifest, network, env, external_sha):
    command = ["create", "-i", "--name", "cardchemy-private-seed-trial-v1-" + uuid4().hex,
        "--network", network, "--cpus", "4", "--memory", "2g", "--memory-swap", "2g", "--pids-limit", "128",
        "--read-only", "--user", "0:0", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=536870912",
        "--mount", f"type=bind,source={root},target=/tmp/private,readonly",
        "--mount", f"type=bind,source={root / 'workspace'},target=/workspace,readonly",
        "--mount", f"type=bind,source={root / 'output'},target=/tmp/output", "--entrypoint", "python"]
    for name in env:
        require(not name.endswith("API_KEY"), "credential_environment_forbidden"); command += ["-e", name]
    return command + [manifest["image"], "/workspace/watchdog.py", "2400", "python", "/workspace/" + ENTRY_PATH,
        "--execute", "/tmp/private", "/tmp/output", external_sha]

def claim_registry():
    root = Path(tempfile.gettempdir()).resolve() / "cardchemy-private-seed-visual-v1-claims"
    if not root.exists(): root.mkdir(mode=0o700)
    path_check(root, directory=True); return root

# The execution body is copied below solely for 14 cases / 2400s constants.

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
            input=key_message, capture_output=True, timeout=2420, check=False)
        key_message = b""
        require(0 < len(process.stdout) <= MAX_AGGREGATE_BYTES, "aggregate_invalid")
        result = parse(process.stdout, MAX_AGGREGATE_BYTES)
        state = parse(command(["inspect", identity]), 2 * 1024 * 1024)[0]["State"]
        require(state["Running"] is False, "container_still_running")
        require(type(result) is dict and result.get("schema") == "private_seed_visual_trial_v1_execution"
            and result.get("provider_calls", 15) <= 14 and result.get("database_writes") == 0
            and result.get("embedding_calls") == result.get("answer_calls") == result.get("verifier_calls") == 0
            and result.get("automatic_retries") == 0 and result.get("release_gate_passed") is False,
            "aggregate_invalid")
        result.update(container_exit_code=state["ExitCode"], container_oom_killed=state["OOMKilled"],
            container_cpus=4, container_memory_bytes=MEMORY_BYTES, hard_process_seconds=2400,
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
    parser.add_argument("--stage", type=Path); parser.add_argument("--execute", type=Path)
    args = parser.parse_args(argv)
    if args.execute:
        result, code = {"schema": SCHEMA, "status": "fresh_external_authority_required", "live_authorized": False, "provider_calls": 0}, 2
    elif args.stage:
        try: result, code = stage(args.stage), 0
        except Exception: result, code = {"schema": SCHEMA, "status": "staging_refused", "provider_calls": 0}, 2
    else: result, code = {"schema": SCHEMA, "status": "unexecuted", "provider_calls": 0}, 0
    print(json.dumps(result, sort_keys=True)); return code

if __name__ == "__main__":
    raise SystemExit(main())
