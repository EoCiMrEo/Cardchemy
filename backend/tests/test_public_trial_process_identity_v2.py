"""Invented process identities; never terminate, inspect or spawn OS processes."""
from pathlib import Path
import sys
from types import ModuleType

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import public_trial_process_identity_v2 as identity


@pytest.mark.parametrize("birth,expected", [(999, False), (1000, False), (1001, True)])
def test_same_pid_is_released_only_for_demonstrably_later_birth(birth, expected):
    assert identity.recorded_process_released(7, {7: 1000}, lambda _: {"state": "running", "birth_epoch_ms": birth}) is expected


def test_absent_process_passes_and_unbound_running_process_refuses():
    assert identity.recorded_process_released(7, {}, lambda _: {"state": "absent"})
    assert not identity.recorded_process_released(7, {}, lambda _: {"state": "running", "birth_epoch_ms": 2000})


@pytest.mark.parametrize("state", [None, {}, {"state": "unknown"}, {"state": "running", "birth_epoch_ms": True},
    {"state": "running", "birth_epoch_ms": 0}, {"state": "absent", "extra": 1}])
def test_unknown_or_malformed_identity_is_never_released(state):
    with pytest.raises(identity.IdentityError, match="process_identity_unavailable"):
        identity.recorded_process_released(7, {7: 1000}, lambda _: state)


def test_os_observation_error_is_not_treated_as_absent():
    def fail(_):
        raise identity.IdentityError("process_identity_unavailable")
    with pytest.raises(identity.IdentityError, match="process_identity_unavailable"):
        identity.recorded_process_released(7, {7: 1000}, fail)


def test_only_admission_context_is_cloned_and_original_remains_intact():
    module = ModuleType("invented_public_scope")
    exec("def process_absent(pid): return False\ndef admit(*, pid=7): return process_absent(pid)\ndef execute(): raise RuntimeError('unused')", module.__dict__)
    original_admit, original_observer, original_execute = module.admit, module.process_absent, module.execute
    original_members = dict(module.__dict__)
    cloned = identity.clone_admission_tree(module, lambda pid: pid == 7)
    assert cloned.admit() is True and module.admit() is False
    assert module.admit is original_admit and module.process_absent is original_observer
    assert cloned.execute is original_execute
    assert module.__dict__ == original_members
    assert cloned.admit.__kwdefaults__ == original_admit.__kwdefaults__ == {"pid": 7}
    assert cloned.admit.__kwdefaults__ is not original_admit.__kwdefaults__
