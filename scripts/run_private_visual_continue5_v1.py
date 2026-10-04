"""Exact five-case custody using unchanged v8 function bodies in isolated globals."""
from types import FunctionType
import run_private_visual_trial_v8 as base
for _name, _value in vars(base).items():
    if not _name.startswith("__") and (not isinstance(_value, FunctionType) or _value.__module__ != base.__name__):
        globals()[_name] = _value
import prepare_private_visual_continue5_v1 as preparation
SCHEMA = "private_visual_continue5_v1_custody"
LIVE_AUTHORIZED = False
CALLER_PATH = "scripts/run_private_visual_continue5_v1.py"
# Guard behavior and every old scope/source/context invariant remain unchanged.
GUARD_PATH = base.GUARD_PATH
def _shared(function):
    result = FunctionType(function.__code__, globals(), function.__name__, function.__defaults__, function.__closure__)
    result.__kwdefaults__ = function.__kwdefaults__
    return result
for _name in ("require", "digest", "binding_identity", "_validate_bound", "_usage"):
    globals()[_name] = _shared(getattr(base, _name))
