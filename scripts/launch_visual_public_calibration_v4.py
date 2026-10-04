"""Hidden one-use supervisor for checkpoint-bound public visual calibration v4.

The launcher never reads credentials. It first performs a keyless preflight,
then starts a suspended worker inside a four-CPU/two-GiB Windows Job Object.
An external approval SHA travels unchanged through all process boundaries.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

import prepare_visual_page_source_input_v1 as visual
import run_visual_public_calibration_v4 as caller

REPO = Path(__file__).resolve().parents[1]
CALLER = Path(__file__).with_name("run_visual_public_calibration_v4.py")
AUTHORIZATION_ID = "20261001_public_visual_calibration_v4_deadline_once"
MAX_SECONDS = 5400


def child_env(source: dict) -> dict:
    env = {name: source[name] for name in ("SystemRoot", "WINDIR", "TEMP", "TMP") if source.get(name)}
    env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1",
               PYTHONPATH=str(REPO / "backend"))
    return env


def write_new(path: Path, value: dict) -> None:
    with path.open("xb") as stream:
        stream.write(visual.canonical(value))
        stream.flush()
        os.fsync(stream.fileno())


def ledger_dir() -> Path:
    root = REPO / ".agent/.verification/visual-public-calibration-v4-ledger"
    visual.require(not root.is_symlink() and not root.parent.is_symlink(), "ledger_invalid")
    root.mkdir(parents=True, exist_ok=True)
    return root


def check_arguments(approval: Path, sha: str, output: Path) -> None:
    visual.require(approval.is_absolute() and approval.is_file() and not approval.is_symlink()
                   and visual._sha(sha), "external_approval_required")
    visual.require(output.is_absolute() and not output.exists() and not output.is_symlink()
                   and output.resolve().parent == Path(tempfile.gettempdir()).resolve(), "fresh_temp_output_required")


def preflight(approval: Path, sha: str) -> bool:
    result = subprocess.run([sys.executable, str(CALLER), "--preflight", "--approval-file", str(approval),
                             "--approval-sha", sha], cwd=REPO, env=child_env(os.environ),
                            capture_output=True, timeout=600, check=False)
    try:
        return result.returncode == 0 and not result.stderr and json.loads(
            result.stdout, object_pairs_hook=visual._unique) == {
            "status": "preflight_passed", "provider_calls": 0}
    except (ValueError, UnicodeError):
        return False


def supervise(approval: Path, sha: str, output: Path) -> None:
    """Assign the complete process tree before any worker instruction runs."""
    visual.require(caller.LIVE_AUTHORIZED, "fresh_provider_authorization_required")
    visual.require(os.name == "nt", "resource_mode_unavailable")
    import ctypes
    from ctypes import wintypes as w
    size = ctypes.c_size_t

    class Basic(ctypes.Structure):
        _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                    ("flags", w.DWORD), ("min_ws", size), ("max_ws", size),
                    ("active", w.DWORD), ("affinity", size), ("priority", w.DWORD), ("scheduling", w.DWORD)]

    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in ("read_ops", "write_ops", "other_ops",
                                                         "read_bytes", "write_bytes", "other_bytes")]

    class Extended(ctypes.Structure):
        _fields_ = [("basic", Basic), ("io", IO), ("process_memory", size),
                    ("job_memory", size), ("peak_process_memory", size), ("peak_job_memory", size)]

    class Startup(ctypes.Structure):
        _fields_ = [("cb", w.DWORD), ("reserved", w.LPWSTR), ("desktop", w.LPWSTR),
                    ("title", w.LPWSTR), ("x", w.DWORD), ("y", w.DWORD),
                    ("x_size", w.DWORD), ("y_size", w.DWORD), ("x_chars", w.DWORD), ("y_chars", w.DWORD),
                    ("fill", w.DWORD), ("flags", w.DWORD), ("show", w.WORD), ("reserved_size", w.WORD),
                    ("reserved_bytes", ctypes.POINTER(ctypes.c_byte)),
                    ("stdin", w.HANDLE), ("stdout", w.HANDLE), ("stderr", w.HANDLE)]

    class Process(ctypes.Structure):
        _fields_ = [("process", w.HANDLE), ("thread", w.HANDLE), ("pid", w.DWORD), ("tid", w.DWORD)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    kernel.GetProcessAffinityMask.argtypes = [w.HANDLE, ctypes.POINTER(size), ctypes.POINTER(size)]
    kernel.CreateProcessW.argtypes = [w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
                                    w.BOOL, w.DWORD, ctypes.c_void_p, w.LPCWSTR,
                                    ctypes.POINTER(Startup), ctypes.POINTER(Process)]
    kernel.ResumeThread.argtypes = [w.HANDLE]
    kernel.ResumeThread.restype = w.DWORD
    kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    kernel.WaitForSingleObject.restype = w.DWORD
    kernel.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    kernel.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
    kernel.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    name = visual.RESOURCE_JOB_PREFIX + uuid.uuid4().hex
    job, info = kernel.CreateJobObjectW(None, name), Process()
    visual.require(bool(job), "resource_job_create_failed")
    try:
        visual.require(ctypes.get_last_error() != 183, "resource_job_collision")
        mask, system = size(), size()
        visual.require(bool(kernel.GetProcessAffinityMask(kernel.GetCurrentProcess(), ctypes.byref(mask),
                                                         ctypes.byref(system))), "resource_affinity_unavailable")
        bits = [1 << i for i in range(ctypes.sizeof(size) * 8) if mask.value & (1 << i)]
        visual.require(bool(bits), "resource_affinity_unavailable")
        limits = Extended()
        limits.basic.flags = 0x10 | 0x200 | 0x2000  # affinity, aggregate memory, kill on close
        limits.basic.affinity = sum(bits[:4])
        limits.job_memory = 2147483648
        visual.require(bool(kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits))),
                       "resource_limits_unavailable")
        command = subprocess.list2cmdline([sys.executable, str(CALLER), "--worker", "--approval-file", str(approval),
                                          "--approval-sha", sha, "--output-dir", str(output), "--resource-job", name])
        env = child_env(os.environ)
        block = ctypes.create_unicode_buffer("\0".join(f"{k}={v}" for k, v in sorted(env.items())) + "\0\0")
        startup = Startup()
        startup.cb = ctypes.sizeof(startup)
        visual.require(bool(kernel.CreateProcessW(sys.executable, ctypes.create_unicode_buffer(command), None, None,
                                                 False, 0x4 | 0x400 | 0x08000000, block, str(REPO),
                                                 ctypes.byref(startup), ctypes.byref(info))), "resource_worker_create_failed")
        visual.require(bool(kernel.AssignProcessToJobObject(job, info.process)), "resource_assignment_unavailable")
        receipt = {"worker_pid": info.pid, "resource_job": name, "cpus": 4, "memory_bytes": 2147483648,
                   "timeout_seconds": MAX_SECONDS, "approval_sha256": sha, "kill_tree_on_close": True,
                   "started_epoch_ms": int(time.time() * 1000)}
        write_new(output.with_name(output.name + ".resource-process.json"), receipt)
        visual.require(kernel.ResumeThread(info.thread) != 0xffffffff, "resource_worker_resume_failed")
        status = kernel.WaitForSingleObject(info.process, MAX_SECONDS * 1000)
        if status == 0x102:
            kernel.TerminateJobObject(job, 2)
            raise visual.PreparationError("pilot_supervisor_timeout")
        visual.require(status == 0, "resource_worker_wait_failed")
        code = w.DWORD()
        visual.require(bool(kernel.GetExitCodeProcess(info.process, ctypes.byref(code))), "resource_exit_unavailable")
        write_new(output.with_name(output.name + ".supervisor-complete.json"), {
            "exit_code": code.value, "approval_sha256": sha, "resume_permitted": False})
    finally:
        if info.process:
            kernel.TerminateProcess(info.process, 2)
        kernel.CloseHandle(job)
        for handle in (info.thread, info.process):
            if handle:
                kernel.CloseHandle(handle)


def detach(approval: Path, sha: str, output: Path) -> dict:
    visual.require(caller.LIVE_AUTHORIZED, "fresh_provider_authorization_required")
    visual.require(os.name == "nt", "detached_mode_unavailable")
    claim_path = ledger_dir() / f"{AUTHORIZATION_ID}.launch-claim.json"
    write_new(claim_path, {"authorization_id": AUTHORIZATION_ID, "approval_file": str(approval),
                          "approval_sha256": sha, "output_dir": str(output),
                          "launcher_sha256": visual.digest(Path(__file__).read_bytes()),
                          "created_epoch_ms": int(time.time() * 1000)})
    flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP |
             subprocess.CREATE_BREAKAWAY_FROM_JOB | subprocess.CREATE_NO_WINDOW)
    process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--supervisor", "--approval-file",
                                str(approval), "--approval-sha", sha, "--output-dir", str(output)],
                               cwd=REPO, env=child_env(os.environ), stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
                               creationflags=flags)
    receipt = {"status": "detached_one_use_started", "supervisor_pid": process.pid,
               "output_dir": str(output), "approval_sha256": sha, "spawned_epoch_ms": int(time.time() * 1000)}
    write_new(output.with_name(output.name + ".launch-process.json"), receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval-file", type=Path, required=True)
    parser.add_argument("--approval-sha", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--supervisor", action="store_true")
    args = parser.parse_args()
    try:
        visual.require(caller.LIVE_AUTHORIZED, "fresh_provider_authorization_required")
        check_arguments(args.approval_file, args.approval_sha, args.output_dir)
        visual.require(preflight(args.approval_file, args.approval_sha), "keyless_preflight_failed")
        if args.supervisor:
            raw = (ledger_dir() / f"{AUTHORIZATION_ID}.launch-claim.json").read_bytes()
            claim = json.loads(raw)
            visual.require(claim.get("approval_file") == str(args.approval_file)
                           and claim.get("approval_sha256") == args.approval_sha
                           and claim.get("output_dir") == str(args.output_dir)
                           and claim.get("launcher_sha256") == visual.digest(Path(__file__).read_bytes()),
                           "launch_claim_changed")
            supervise(args.approval_file, args.approval_sha, args.output_dir)
        else:
            print(json.dumps(detach(args.approval_file, args.approval_sha, args.output_dir)))
        return 0
    except Exception as error:
        code = str(error) if isinstance(error, visual.PreparationError) else "launcher_failed"
        try:
            write_new(args.output_dir.with_name(args.output_dir.name + ".launcher-failure.json"),
                      {"status": "stopped", "failure_code": code, "resume_permitted": False})
        except OSError:
            pass
        print(json.dumps({"status": "launcher_rejected", "failure_code": code}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
