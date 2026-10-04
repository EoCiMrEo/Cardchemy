"""Launcher isolation, durable claims and external pins; no real subprocess."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import launch_visual_public_calibration_v5 as launcher


def test_child_environment_excludes_all_provider_and_application_secrets():
    result = launcher.child_env({"SystemRoot": "C:/Windows", "TEMP": "C:/SyntheticTemp",
                                 "RAG_SOURCE_JUDGE_API_KEY": "forbidden", "JWT_SECRET": "forbidden",
                                 "RAG_EMBEDDING_API_KEY": "forbidden", "HTTP_PROXY": "forbidden"})
    assert not any("forbidden" == value for value in result.values())
    assert set(result) == {"SystemRoot", "TEMP", "PYTHONUTF8", "PYTHONDONTWRITEBYTECODE",
                           "PYTHONNOUSERSITE", "PYTHONPATH"}


@pytest.mark.parametrize("bad", ["duplicate", "changed", "stderr", "invalid_json", "exit"])
def test_keyless_preflight_requires_exact_clean_success(monkeypatch, bad):
    class Result:
        returncode = 0
        stdout = b'{"status":"preflight_passed","provider_calls":0}'
        stderr = b''
    result = Result()
    if bad == "duplicate":
        result.stdout = b'{"status":"wrong","status":"preflight_passed","provider_calls":0}'
    elif bad == "changed":
        result.stdout = b'{"status":"preflight_passed","provider_calls":1}'
    elif bad == "stderr":
        result.stderr = b'do not forward'
    elif bad == "invalid_json":
        result.stdout = b'not json'
    else:
        result.returncode = 2
    monkeypatch.setattr(launcher.subprocess, "run", lambda *a, **k: result)
    assert not launcher.preflight(Path("C:/synthetic/approval.json"), "a" * 64)


def test_external_pin_travels_to_keyless_child_with_scrubbed_environment(monkeypatch):
    calls = []
    class Result:
        returncode = 0
        stdout = b'{"status":"preflight_passed","provider_calls":0}'
        stderr = b''
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return Result()
    monkeypatch.setattr(launcher.subprocess, "run", run)
    monkeypatch.setenv("RAG_SOURCE_JUDGE_API_KEY", "forbidden")
    assert launcher.preflight(Path("C:/synthetic/approval.json"), "b" * 64)
    assert calls[0][0][-1] == "b" * 64
    assert "RAG_SOURCE_JUDGE_API_KEY" not in calls[0][1]["env"]


def test_exclusive_durable_launch_claim_cannot_be_overwritten(tmp_path):
    path = tmp_path / "claim.json"
    launcher.write_new(path, {"authorization_id": launcher.AUTHORIZATION_ID})
    with pytest.raises(FileExistsError):
        launcher.write_new(path, {"authorization_id": "changed"})
    assert path.read_bytes() == launcher.visual.canonical({"authorization_id": launcher.AUTHORIZATION_ID})


def test_source_fences_suspended_assignment_before_resume_and_no_worker_breakaway():
    # Contract against accidentally moving execution before resource assignment.
    import inspect
    source = inspect.getsource(launcher.supervise)
    assert source.index("AssignProcessToJobObject(job, info.process)") < source.index("ResumeThread(info.thread)")
    assert "0x4 | 0x400 | 0x08000000" in source
    assert "CREATE_BREAKAWAY_FROM_JOB" not in source
    assert "MAX_SECONDS * 1000" in source
    assert "limits.job_memory = 2147483648" in source


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native resource contract")
def test_native_worker_checks_named_resource_ancestor_before_its_first_work(tmp_path, monkeypatch):
    import json
    import textwrap
    child = tmp_path / "invented_worker.py"
    output = tmp_path / "output"
    child.write_text(textwrap.dedent('''
        import argparse, json, sys
        from pathlib import Path
        sys.path.insert(0, SCRIPTS_PATH)
        import prepare_visual_page_source_input_v1 as resource
        parser = argparse.ArgumentParser()
        parser.add_argument('--worker', action='store_true')
        parser.add_argument('--approval-file')
        parser.add_argument('--approval-sha')
        parser.add_argument('--output-dir', type=Path)
        parser.add_argument('--resource-job')
        args = parser.parse_args()
        resource.RESOURCE_JOB_NAME = resource.validate_resource_job_name(args.resource_job)
        resource.require(resource._inside_windows_job(), 'resource_fence_required')
        args.output_dir.mkdir()
        (args.output_dir / 'synthetic-proof.json').write_text(json.dumps({
            'fence_verified': True, 'approval_sha': args.approval_sha, 'provider_calls': 0}))
    ''').replace('SCRIPTS_PATH', repr(str(launcher.REPO / "scripts"))), encoding="utf-8")
    monkeypatch.setattr(launcher.caller, "LIVE_AUTHORIZED", True)
    monkeypatch.setattr(launcher, "CALLER", child)
    launcher.supervise(tmp_path / "invented_approval.json", "b" * 64, output)
    proof = json.loads((output / "synthetic-proof.json").read_text())
    assert proof == {"fence_verified": True, "approval_sha": "b" * 64, "provider_calls": 0}
    receipt = json.loads(output.with_name(output.name + ".resource-process.json").read_text())
    assert receipt["cpus"] == 4 and receipt["memory_bytes"] == 2147483648
    assert receipt["kill_tree_on_close"]
    assert json.loads(output.with_name(output.name + ".supervisor-complete.json").read_text())["exit_code"] == 0


def test_pending_authorization_blocks_detach_before_claim_or_process(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher.caller, "LIVE_AUTHORIZED", False)
    def forbidden(*args, **kwargs):
        pytest.fail("authorization must precede claims or process creation")
    monkeypatch.setattr(launcher, "ledger_dir", forbidden)
    monkeypatch.setattr(launcher.subprocess, "Popen", forbidden)
    with pytest.raises(launcher.visual.PreparationError, match="fresh_provider_authorization_required"):
        launcher.detach(tmp_path / "approval.json", "a" * 64, tmp_path / "output")


def test_pending_authorization_blocks_supervisor_before_native_process(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher.caller, "LIVE_AUTHORIZED", False)
    with pytest.raises(launcher.visual.PreparationError, match="fresh_provider_authorization_required"):
        launcher.supervise(tmp_path / "approval.json", "a" * 64, tmp_path / "output")
