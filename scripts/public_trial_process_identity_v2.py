"""Observe consumed public process identities without confusing reused PIDs.

Only stopped, hash-bound scopes with successful hard-supervisor completion may
provide a creation-time upper bound. Existing processes are never terminated.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
from types import FunctionType, SimpleNamespace


class IdentityError(ValueError):
    """Finite local observation error; no command line or content is retained."""


def require(ok: bool, code: str) -> None:
    if not ok:
        raise IdentityError(code)


def windows_identity(pid: int) -> dict:
    require(os.name == "nt" and type(pid) is int and pid > 0, "process_identity_unavailable")
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    kernel.OpenProcess.restype = w.HANDLE
    kernel.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    kernel.GetProcessTimes.argtypes = [w.HANDLE, ctypes.POINTER(w.FILETIME), ctypes.POINTER(w.FILETIME), ctypes.POINTER(w.FILETIME), ctypes.POINTER(w.FILETIME)]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    ctypes.set_last_error(0)
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        require(ctypes.get_last_error() == 87, "process_identity_unavailable")
        return {"state": "absent"}
    try:
        code = w.DWORD()
        require(bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))), "process_identity_unavailable")
        if code.value != 259:
            return {"state": "absent"}
        birth, end, kernel_time, user_time = w.FILETIME(), w.FILETIME(), w.FILETIME(), w.FILETIME()
        require(bool(kernel.GetProcessTimes(handle, ctypes.byref(birth), ctypes.byref(end), ctypes.byref(kernel_time), ctypes.byref(user_time))), "process_identity_unavailable")
        ticks = (birth.dwHighDateTime << 32) | birth.dwLowDateTime
        epoch_ms = (ticks - 116444736000000000) // 10000
        require(epoch_ms > 0, "process_identity_unavailable")
        return {"state": "running", "birth_epoch_ms": epoch_ms}
    finally:
        kernel.CloseHandle(handle)


def recorded_process_released(pid: int, upper_bounds: dict[int, int], read_identity=windows_identity) -> bool:
    require(type(pid) is int and pid > 0, "process_identity_unavailable")
    identity = read_identity(pid)
    require(type(identity) is dict, "process_identity_unavailable")
    if identity == {"state": "absent"}:
        return True
    require(set(identity) == {"state", "birth_epoch_ms"} and identity["state"] == "running" and
        type(identity["birth_epoch_ms"]) is int and identity["birth_epoch_ms"] > 0, "process_identity_unavailable")
    bound = upper_bounds.get(pid)
    if bound is None:
        return False
    require(type(bound) is int and bound > 0, "process_identity_bound_invalid")
    # The original process existed before its immutable first attempt/launch
    # claim. A newer birth proves a distinct OS process with the recycled PID.
    return identity["birth_epoch_ms"] > bound


def bind_completed_scopes(current) -> dict:
    """Read only pinned public terminal/claim/resource data for scopes v3-v7."""
    chain = {8: current}
    node = current.parent_trial
    for version in range(7, 0, -1):
        chain[version] = node
        if version > 1:
            node = getattr(node, "parent_trial", getattr(node, "previous_trial", None))
            require(node is not None, "process_identity_chain_invalid")
    bounds, scopes = {}, {}
    for version in range(3, 8):
        owner, successor = chain[version], chain[version + 1]
        if version == 7:
            report = current.read_bound(current.PARENT_REPORT_PATH, current.PARENT_REPORT_SHA)
            terminal = current.read_bound(current.PARENT_RESULT_PATH, current.PARENT_RESULT_SHA)
            controls = report["controls"]
            receipts = report["receipts"]
            resource_sha, complete_sha = report["resource_receipt_sha256"], report["supervisor_complete_sha256"]
            outer_sha = current.PARENT_REPORT_SHA
        else:
            outer = chain[version + 2]
            pinned = current.read_bound(outer.PARENT_RESULT_PATH, outer.PARENT_RESULT_SHA)
            binding = pinned["checkpoint_binding"]
            require(binding["parent_authorization_id"] == owner.AUTHORIZATION_ID and
                binding["parent_result_sha256"] == successor.PARENT_RESULT_SHA and
                binding["parent_approval_sha256"] == successor.PARENT_APPROVAL_SHA,
                "process_identity_scope_invalid")
            terminal = current.read_bound(successor.PARENT_RESULT_PATH, successor.PARENT_RESULT_SHA)
            controls, receipts = binding["parent_controls"], binding["receipt_bindings"]
            resource_sha, complete_sha = binding["parent_resource_sha256"], binding["parent_complete_sha256"]
            outer_sha = outer.PARENT_RESULT_SHA
        require(terminal["authorization_id"] == owner.AUTHORIZATION_ID and
            terminal["approval_sha256"] == successor.PARENT_APPROVAL_SHA and
            terminal["status"] == "stopped" and terminal["resume_permitted"] is False,
            "process_identity_scope_not_terminal")
        output, ledger = successor.PARENT_OUTPUT, successor.PARENT_LEDGER
        resource = current.read_bound(output.with_name(output.name + ".resource-process.json"), resource_sha)
        complete = current.read_bound(output.with_name(output.name + ".supervisor-complete.json"), complete_sha)
        require(complete == {"approval_sha256": successor.PARENT_APPROVAL_SHA, "exit_code": 0, "resume_permitted": False} and
            resource["approval_sha256"] == successor.PARENT_APPROVAL_SHA and resource["kill_tree_on_close"] is True,
            "process_identity_supervisor_invalid")
        gid = successor.PARENT_GROUPS[0]
        first = current.read_bound(ledger / f"{owner.AUTHORIZATION_ID}-{gid}.claim.json", receipts[gid]["claim_sha256"])
        first_receipt = current.read_bound(output / f"attempt-{gid}.json", receipts[gid]["receipt_sha256"])
        require(first["authorization_id"] == owner.AUTHORIZATION_ID and first["approval_sha256"] == successor.PARENT_APPROVAL_SHA and
            first["group_id"] == gid and first_receipt["attempt_claim_sha256"] == receipts[gid]["claim_sha256"] and
            first_receipt["group_id"] == gid and type(first["started_epoch_ms"]) is int and first["started_epoch_ms"] > 0,
            "process_identity_attempt_invalid")
        first_ms = first["started_epoch_ms"]
        recorded = []
        for role in ("launch", "execute", "run"):
            claim = current.read_bound(ledger / f"{owner.AUTHORIZATION_ID}.{role}-claim.json", controls[role]["sha256"])
            require(claim["authorization_id"] == owner.AUTHORIZATION_ID and claim["approval_sha256"] == successor.PARENT_APPROVAL_SHA,
                "process_identity_claim_invalid")
            if role == "launch":
                pid, upper = claim["supervisor_pid"], claim["created_epoch_ms"]
                require(type(upper) is int and 0 < upper <= first_ms, "process_identity_birth_bound_invalid")
            else:
                pid, upper = claim["pid"], first_ms
            require(type(pid) is int and pid > 0, "process_identity_pid_invalid")
            bounds[pid] = max(bounds.get(pid, 0), upper)
            recorded.append({"role": role, "pid": pid, "original_birth_upper_epoch_ms": upper, "claim_sha256": controls[role]["sha256"]})
        pid = resource["worker_pid"]
        require(type(pid) is int and pid > 0, "process_identity_pid_invalid")
        bounds[pid] = max(bounds.get(pid, 0), first_ms)
        recorded.append({"role": "resource_worker", "pid": pid, "original_birth_upper_epoch_ms": first_ms, "claim_sha256": resource_sha})
        scopes[str(version)] = {"authorization_id": owner.AUTHORIZATION_ID, "outer_binding_sha256": outer_sha,
            "terminal_sha256": successor.PARENT_RESULT_SHA, "resource_sha256": resource_sha,
            "complete_sha256": complete_sha, "first_attempt_claim_sha256": receipts[gid]["claim_sha256"], "recorded": recorded}
    binding = {"schema": "public_consumed_process_identity_v2", "scopes": scopes,
        "upper_bounds": {str(pid): upper for pid, upper in sorted(bounds.items())}}
    return {"binding": binding, "binding_sha256": current.digest(current.canonical(binding)), "upper_bounds": bounds}


def clone_admission_tree(module, observer, cache=None):
    """Clone only pure admission utilities; consumed modules/files are unchanged."""
    cache = {} if cache is None else cache
    if module.__name__ in cache:
        return cache[module.__name__]
    namespace = dict(vars(module))
    result = SimpleNamespace()
    cache[module.__name__] = result
    for parent_name in ("parent_trial", "previous_trial"):
        if parent_name in namespace:
            namespace[parent_name] = clone_admission_tree(namespace[parent_name], observer, cache)
    if "process_absent" in namespace:
        namespace["process_absent"] = observer
    for name in ("admit", "admit_checkpoint", "checkpoint_rows", "expected_approval", "validate_approval", "guards", "code_hashes"):
        value = namespace.get(name)
        if isinstance(value, FunctionType) and value.__module__ == module.__name__:
            clone = FunctionType(value.__code__, namespace, value.__name__, value.__defaults__, value.__closure__)
            clone.__kwdefaults__ = dict(value.__kwdefaults__) if value.__kwdefaults__ is not None else None
            namespace[name] = clone
    result.__dict__.update(namespace)
    return result
