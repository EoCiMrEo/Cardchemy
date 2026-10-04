"""Keyless five-case staging, separate one-use host and exact parent checkpoint.

The old stage/output remain untouched. A prospective stage copies the complete
parent evidence and code, plus this narrow continuation. External authority is
required before credential lookup or provider execution.
"""
from __future__ import annotations
from dataclasses import replace
from types import FunctionType
import launch_private_visual_trial_v8 as base
for _name, _value in vars(base).items():
    if not _name.startswith("__") and (not isinstance(_value, FunctionType) or _value.__module__ != base.__name__):
        globals()[_name] = _value
SCHEMA = "private_visual_continue5_v1_host"
HOST_PATH = "scripts/launch_private_visual_continue5_v1.py"
ENTRY_PATH = "backend/scripts/private_visual_continue5_entry_v1.py"
EXECUTOR_PATH = "backend/scripts/execute_private_visual_continue5_v1.py"
LIVE_AUTHORIZED = False
def _shared(function):
    result = FunctionType(function.__code__, globals(), function.__name__, function.__defaults__, function.__closure__)
    result.__kwdefaults__ = function.__kwdefaults__
    return result
for _name in ("require", "canonical", "digest", "_unique", "parse", "path_check", "bounded", "exclusive",
    "image_source_paths", "approval_payload", "validate_approval", "credential_message", "read_credential_stdin",
    "cli_env", "docker", "inspect_runtime", "create_arguments"):
    globals()[_name] = _shared(getattr(base, _name))

def modules():
    sys.path.insert(0, str(REPO / "scripts")); sys.path.insert(0, str(REPO / "backend/scripts"))
    import prepare_private_visual_continue5_v1 as preparation
    import run_private_visual_continue5_v1 as custody
    import rehearse_private_visual_continue5_v1 as rehearsal
    import execute_private_visual_continue5_v1 as executor
    return preparation, custody, rehearsal, executor

def bindings(full, prepared, inputs, code):
    preparation, custody, rehearsal, _ = modules()
    scope, pairs = rehearsal.bind_cases(full, parse(inputs["request-packet-reviewed-v3.json"], 48 * 1024 * 1024),
        parse(inputs["hybrid-preparation.json"], 48 * 1024 * 1024), code)
    whole = custody.BoundTrial(scope, tuple(c for c, _ in pairs), tuple(p for _, p in pairs))
    bound = custody.BoundTrial(scope, whole.cases[7:], whole.pins[7:])
    custody._validate_bound(prepared, bound, custody.binding_identity(bound))
    return bound, whole

def stage(parent):
    preparation, custody, _, _ = modules()
    manifest, _, _ = base.validate_stage(parent)
    manifest_raw = bounded(parent / "manifest.json", 256 * 1024)
    approval_raw = bounded(parent / "approval.json", 64 * 1024)
    require(digest(manifest_raw) == preparation.PARENT_STAGE_SHA, "parent_stage_changed")
    records = {p.name: bounded(p, 128 * 1024) for p in (parent / "output").glob("*.json")}
    inputs = {name: bounded(parent / name, 48 * 1024 * 1024) for name in manifest["inputs"]}
    paths = set(manifest["code"]) | set(preparation.CODE_PATHS)
    verified = {name: bounded(REPO / name, 1024 * 1024, allow_empty=True) for name in paths}
    full, prepared = preparation.prepare({name: inputs[preparation.FILES[name]] for name in preparation.ARTIFACT_NAMES},
        current_code=verified, manifest_raw=manifest_raw, approval_raw=approval_raw, records=records)
    root = Path(tempfile.mkdtemp(prefix="cardchemy-private-continue5-v1-")).resolve(); root.chmod(0o700)
    for name in ("workspace", "output", "parent-output"): (root / name).mkdir(mode=0o700)
    for name, raw in inputs.items(): exclusive(root / name, raw)
    exclusive(root / "parent-manifest.json", manifest_raw)
    exclusive(root / "parent-approval.json", approval_raw)
    for name, raw in records.items(): exclusive(root / "parent-output" / name, raw)
    code = {}
    for name, raw in verified.items():
        target = root / "workspace" / name; target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        exclusive(target, raw); code[name] = digest(raw)
    exclusive(root / "workspace/watchdog.py", WATCHDOG.encode())
    guard_paths = set(manifest["guard_code"]) | set(preparation.CODE_PATHS)
    guard_code = {name: code[name] for name in guard_paths}
    require(len(guard_code) <= 100, "guard_code_capacity_exceeded")
    bound, _ = bindings(full, prepared, inputs, guard_code)
    value = {"schema": SCHEMA + "_stage", "image": manifest["image"], "inputs": manifest["inputs"],
        "code": code, "guard_code": guard_code, "image_code": manifest["image_code"],
        "watchdog_sha256": digest(WATCHDOG.encode()), "guards": preparation.guards(),
        "preflight_identity_sha256": preparation.report(prepared)["preflight_identity_sha256"],
        "binding_sha256": custody.binding_identity(bound), "parent_stage_sha256": preparation.PARENT_STAGE_SHA,
        "parent_approval_sha256": preparation.PARENT_APPROVAL_SHA,
        "parent_output_pins": {name: digest(raw) for name, raw in records.items()}}
    exclusive(root / "manifest.json", canonical(value))
    return {"status": "staged", "directory": str(root), "stage_sha256": digest(canonical(value)),
        "cases": 5, "preserved_cases": 7, "provider_calls": 0, "database_reads": 0, "database_writes": 0}

def validate_stage(root, *, image=False):
    preparation, custody, _, _ = modules()
    path_check(root, directory=True)
    require(root == Path("/tmp/private") if image else root.parent == Path(tempfile.gettempdir()).resolve()
        and root.name.startswith("cardchemy-private-continue5-v1-"), "private_temp_required")
    raw = bounded(root / "manifest.json", 256 * 1024); manifest = parse(raw, 256 * 1024)
    require(set(manifest) == {"schema", "image", "inputs", "code", "guard_code", "image_code", "watchdog_sha256",
        "guards", "preflight_identity_sha256", "binding_sha256", "parent_stage_sha256", "parent_approval_sha256",
        "parent_output_pins"} and manifest["schema"] == SCHEMA + "_stage" and canonical(manifest) == raw
        and manifest["guards"] == preparation.guards() and manifest["parent_stage_sha256"] == preparation.PARENT_STAGE_SHA
        and manifest["parent_approval_sha256"] == preparation.PARENT_APPROVAL_SHA, "stage_invalid")
    parent_raw = bounded(root / "parent-manifest.json", 256 * 1024)
    parent = parse(parent_raw, 256 * 1024)
    require(digest(parent_raw) == preparation.PARENT_STAGE_SHA and manifest["inputs"] == parent["inputs"]
        and manifest["image"] == parent["image"] and manifest["image_code"] == parent["image_code"], "parent_stage_changed")
    inputs = {name: bounded(root / name, 48 * 1024 * 1024) for name in manifest["inputs"]}
    require(all(digest(raw) == manifest["inputs"][name] for name, raw in inputs.items()), "artifact_changed")
    require(type(manifest["code"]) is dict and set(manifest["code"]) == set(parent["code"]) | set(preparation.CODE_PATHS)
        and len(manifest["code"]) <= 200, "code_set_invalid")
    verified = {}
    for name, pin in manifest["code"].items():
        require(preparation._code_path(name) and re.fullmatch(r"[0-9a-f]{64}", pin), "code_path_invalid")
        raw = bounded(REPO / name, 1024 * 1024, allow_empty=True)
        require(digest(raw) == pin == digest(bounded(root / "workspace" / name, 1024 * 1024, allow_empty=True)), "code_changed")
        verified[name] = raw
    require(type(manifest["parent_output_pins"]) is dict
        and digest(canonical(manifest["parent_output_pins"])) == preparation.PARENT_OUTPUT_PINS_SHA
        and all(type(name) is str and re.fullmatch(r"[A-Za-z0-9-]+\.json", name)
            for name in manifest["parent_output_pins"]), "parent_receipts_changed")
    records = {name: bounded(root / "parent-output" / name, 128 * 1024) for name in manifest["parent_output_pins"]}
    require(all(digest(raw) == manifest["parent_output_pins"][name] for name, raw in records.items()), "parent_receipts_changed")
    full, prepared = preparation.prepare({name: inputs[preparation.FILES[name]] for name in preparation.ARTIFACT_NAMES},
        current_code=verified, manifest_raw=parent_raw,
        approval_raw=bounded(root / "parent-approval.json", 64 * 1024), records=records)
    expected = set(parent["guard_code"]) | set(preparation.CODE_PATHS)
    require(manifest["guard_code"] == {name: manifest["code"][name] for name in expected}
        and manifest["watchdog_sha256"] == digest(WATCHDOG.encode())
        == digest(bounded(root / "workspace/watchdog.py", 32768)), "guard_code_invalid")
    if image:
        for name, pin in manifest["image_code"].items():
            require(digest(bounded(Path("/app") / name, 1024 * 1024, allow_empty=True)) == pin, "image_code_changed")
    bound, whole = bindings(full, prepared, inputs, manifest["guard_code"])
    require(preparation.report(prepared)["preflight_identity_sha256"] == manifest["preflight_identity_sha256"]
        and custody.binding_identity(bound) == manifest["binding_sha256"], "stage_binding_changed")
    path_check(root / "output", directory=True)
    return manifest, prepared, bound, (full, whole, records)

def claim_registry():
    root = Path(tempfile.gettempdir()).resolve() / "cardchemy-private-continue5-v1-claims"
    if not root.exists(): root.mkdir(mode=0o700)
    path_check(root, directory=True)
    return root

def execute(root, *, approval_sha256, stdin, command=docker, attach=subprocess.run):
    require(LIVE_AUTHORIZED is True, "private_execution_not_authorized")
    manifest, prepared, bound, _ = validate_stage(root)
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
        require(type(result) is dict and result.get("schema") == "private_visual_continue5_v1_execution"
            and result.get("provider_calls", 6) <= 5 and result.get("database_writes") == 0
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
    args = parser.parse_args(argv)
    if args.stage:
        try: result, code = stage(args.stage), 0
        except Exception: result, code = {"status": "staging_refused", "provider_calls": 0}, 2
    else: result, code = {"status": "fresh_external_authority_required", "provider_calls": 0}, 0
    print(json.dumps(result, sort_keys=True)); return code

if __name__ == "__main__":
    raise SystemExit(main())
