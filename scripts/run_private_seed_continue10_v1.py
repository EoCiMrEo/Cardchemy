"""Exact ten-case custody using unchanged v8 function bodies in isolated globals."""
from types import FunctionType
import run_private_seed_visual_trial_v1 as original
for _name, _value in vars(original).items():
    if not _name.startswith("__") and (not isinstance(_value, FunctionType) or _value.__module__ != original.__name__):
        globals()[_name] = _value
base = original
import prepare_private_seed_continue10_v1 as preparation
SCHEMA = "private_seed_continue10_v1_custody"
LIVE_AUTHORIZED = False
CALLER_PATH = "scripts/run_private_seed_continue10_v1.py"
# Guard behavior and every old scope/source/context invariant remain unchanged.
GUARD_PATH = base.GUARD_PATH
def _shared(function):
    result = FunctionType(function.__code__, globals(), function.__name__, function.__defaults__, function.__closure__)
    result.__kwdefaults__ = function.__kwdefaults__
    return result
for _name in ("require", "digest", "binding_identity", "_usage"):
    globals()[_name] = _shared(getattr(base, _name))

def _validate_bound(prepared, bound, expected_sha):
    require(type(prepared) is preparation.PreparedTrial and binding_identity(bound) == expected_sha
        and digest(preparation.canonical(bound.scope.identity())) == prepared.scope_sha256, "binding_invalid")
    rows = json.loads(dict(prepared.artifacts)["source"])["cases"][4:]
    verified_code = set()
    for frozen, case, pins, row in zip(prepared.cases, bound.cases, bound.pins, rows, strict=True):
        require(type(pins) is guard.GuardPins and isinstance(pins.code_sha256, Mapping)
            and guard.REQUIRED_CODE_PATHS <= set(pins.code_sha256) and len(pins.code_sha256) <= 100
            and all(type(value) is str and guard._SHA.fullmatch(value) for value in (
                pins.bridge_sha256, pins.runtime_sha256, pins.request_sha256, pins.admission_sha256, pins.guard_code_sha256))
            and all(type(name) is str and type(value) is str and guard._SHA.fullmatch(value)
                for name, value in pins.code_sha256.items()), "binding_code_invalid")
        require(case.case_id == frozen.case_id and case.request_bytes == frozen.request_bytes
            and pins.request_sha256 == frozen.request_sha256 and pins.admission_sha256 == frozen.admission_sha256
            and pins.bridge_sha256 == prepared.bridge_sha256 and pins.runtime_sha256 == prepared.runtime_sha256
            and preparation.scorer.admission_packet(case.snapshot) == row["question_context"]["admission"]
            and case.preceding_question == (row["previous_turn"] if case.snapshot.preceding is not None else None), "binding_case_invalid")
        code = dict(pins.code_sha256)
        require(all(code.get(name) == value for name, value in prepared.code_sha256)
            and CALLER_PATH in code and code.get(GUARD_PATH) == pins.guard_code_sha256, "binding_code_invalid")
        # Startup byte verification is once per identical complete code map.
        # Every case is still individually scope/wire/admission-bound; final
        # dispatch guards hash their own pins again AFTER quota and selection.
        code_identity = digest(preparation.canonical({"guard": pins.guard_code_sha256, "code": code}))
        if code_identity not in verified_code:
            guard.verify_code_pins(pins)
            verified_code.add(code_identity)
        require(case.question == row["question"] and len(case.candidates) == len(row["candidates"]), "binding_question_invalid")
        for expected, source, candidate in zip(row["candidates"], json.loads(frozen.sources_bytes), case.candidates, strict=True):
            require(str(candidate.document_id) == expected["document_id"] and str(candidate.content_revision_id) == expected["content_revision_id"]
                and str(candidate.index_revision_id) == expected["index_revision_id"]
                and candidate.page_number == expected["page_number"]
                and candidate.start_offset == expected["start_offset"] and candidate.end_offset == expected["end_offset"]
                and all(getattr(candidate, name) == source[name] for name in ("id", "pdf_sha256", "cue_sha256", "png_sha256", "page_text_sha256")), "binding_source_invalid")
