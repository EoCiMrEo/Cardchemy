"""Inert seed14 controller; frozen v8 execution bodies with isolated globals.

Only the case denominator and separately pinned preparation/guard/custody
interfaces differ. No import, default or CLI reads a key or authorizes HTTP.
"""
from __future__ import annotations
import sys
from pathlib import Path
from types import FunctionType
REPO=Path(__file__).resolve().parents[2]
if Path("/app/app/__init__.py").is_file():
 sys.path.insert(0,"/app")
 import app
sys.path.insert(0,str(REPO/"scripts"))
import execute_private_visual_trial_v8 as base
# Copy ordinary imported types/utilities, never mutation of the v8 namespace.
for _name,_value in vars(base).items():
 if not _name.startswith("__") and (not isinstance(_value,FunctionType) or _value.__module__ != base.__name__):
  globals()[_name]=_value
import prepare_private_seed_visual_trial_v1 as preparation
import run_private_seed_visual_trial_v1 as custody
import private_seed_visual_dispatch_guard_v1 as guard
import rehearse_private_seed_visual_dispatch_v1 as rehearsal
SCHEMA="private_seed_visual_trial_v1_execution"
APPROVAL_SCHEMA=SCHEMA+"_approval"
LIVE_AUTHORIZED=False
EXECUTOR_PATH="backend/scripts/execute_private_seed_visual_trial_v1.py"
REHEARSAL_PATH="backend/scripts/rehearse_private_seed_visual_dispatch_v1.py"
def _shared(function):
 result=FunctionType(function.__code__,globals(),function.__name__,function.__defaults__,function.__closure__)
 result.__kwdefaults__=function.__kwdefaults__
 return result
for _name,_value in vars(base).items():
 if isinstance(_value,FunctionType) and _value.__module__==base.__name__ and _name not in ("execute_private_trial_v8","main"):
  globals()[_name]=_shared(_value)
class TrialLedger:
    """Append-only private receipts. A durable claim is never removed/replayed."""
    def __init__(self, directory: Path):
        self.directory, self.claimed, self.names = directory, False, set()
        self._directory()

    def _directory(self):
        require(isinstance(self.directory, Path) and self.directory.is_absolute()
            and self.directory.is_dir() and not self.directory.is_symlink()
            and not getattr(self.directory, "is_junction", lambda: False)()
            and self.directory.resolve() == self.directory, "ledger_directory_invalid")

    def write(self, name: str, value: dict):
        self._directory()
        allowed = {"claim.json", "summary.json", *{f"{cid}-{kind}.json"
            for cid in preparation.CASE_IDS for kind in ("intent", "usage", "result", "dispatch-guard", "selected-guard")}}
        require(name in allowed and name not in self.names
            and (self.claimed or name == "claim.json"), "ledger_record_invalid")
        raw = preparation.canonical(value)
        require(0 < len(raw) <= 64 * 1024, "ledger_record_invalid")
        try:
            with (self.directory / name).open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            raise ExecutionError("ledger_already_consumed") from None
        except OSError:
            raise ExecutionError("ledger_write_failed") from None
        self.names.add(name)
        if name == "claim.json":
            self.claimed = True

@dataclass(frozen=True, slots=True)
class Interfaces:
    session_factory: Callable = field(repr=False)
    quota: Callable = field(repr=False)
    transport: Callable = field(repr=False)
    current_selections: Callable = field(default=rehearsal.current_selections, repr=False)
    render: Callable = field(default=guard.prepare_dispatch_proof_seed_v1, repr=False)
    final: Callable = field(default=guard.verify_private_visual_dispatch_seed_v1, repr=False)
    validate_receipt: Callable = field(default=guard.require_dispatch_receipt_binding, repr=False)
    close: Callable | None = field(default=None, repr=False)
    clock: Callable = field(default=_now, repr=False)
    monotonic: Callable = field(default=time.monotonic, repr=False)
    sleep: Callable = field(default=asyncio.sleep, repr=False)
    synthetic: bool = False

async def execute_private_seed_trial_v1(prepared, bound, *, settings, api_key: str,
    approval_bytes: bytes, approval_sha256: str, ledger: TrialLedger,
    interfaces: Interfaces | None = None) -> dict:
    """One approved seed14 trial, stopping on any error without automatic replay.

    A host must obtain a fresh explicit private-transfer/provider envelope and
    enforce the hard OS process-tree deadline. Supplying mock callbacks is an
    ENVIRONMENT=test-only seam and yields no physical/backend/release credit.
    """
    initial_clock = interfaces.clock if interfaces is not None else _now
    began = (interfaces.monotonic if interfaces is not None else time.monotonic)()
    require(type(began) in (float, int) and math.isfinite(began), "clock_invalid")
    approval = _approval(approval_bytes, approval_sha256, prepared=prepared, bound=bound, now=initial_clock())
    require(type(api_key) is str and 0 < len(api_key) <= 512 and not any(ch.isspace() for ch in api_key)
        and all(32 < ord(ch) < 127 for ch in api_key), "provider_key_invalid")
    require(type(ledger) is TrialLedger and not ledger.claimed, "ledger_already_consumed")
    if interfaces is not None:
        require(type(interfaces) is Interfaces and interfaces.synthetic is True
            and os.environ.get("ENVIRONMENT") == "test", "injected_interfaces_forbidden")
    else:
        _environment(settings, bound)
    try:
        interfaces = interfaces or production_interfaces(settings)
    except Exception:
        raise ExecutionError("controller_runtime_unavailable") from None
    require(_elapsed(interfaces, began) - began <= preparation.MAX_STARTUP_SECONDS, "startup_deadline")
    trial_id = UUID(approval["trial_id"])
    ledger.write("claim.json", {"schema": SCHEMA + "_claim", "trial_id": str(trial_id),
        "authorization_id": approval["authorization_id"], "approval_sha256": approval_sha256,
        "preflight_identity_sha256": approval["preflight_identity_sha256"],
        "binding_sha256": approval["binding_sha256"], "guards": preparation.guards()})
    result = {"schema": SCHEMA, "trial_id": str(trial_id), "status": "running",
        "synthetic_interfaces": interfaces.synthetic, "provider_calls": 0, "synthetic_transport_calls": 0,
        "embedding_calls": 0, "answer_calls": 0, "verifier_calls": 0, "automatic_retries": 0,
        "database_writes": 0, "case_denominator": preparation.MAX_CALLS, "completed_cases": 0, "cases": [],
        "known_guard_cost_microusd": 0, "usage_unknown_attempts": 0,
        "reserved_input_tokens": 0, "reserved_output_tokens": 0, "reserved_cost_usd": "0",
        "browser_page_open_observed": False, "actual_display_integrity_proved": False,
        "release_gate_passed": False}
    per_call = (Decimal(preparation.MAX_INPUT_TOKENS) * preparation.INPUT_PRICE_USD_PER_MILLION
        + Decimal(preparation.MAX_OUTPUT_TOKENS) * preparation.OUTPUT_PRICE_USD_PER_MILLION) / 1_000_000
    reserved, last_start, current = Decimal(0), None, None
    phase, failure = "startup", None
    try:
        async with asyncio.timeout(preparation.MAX_TOTAL_SECONDS):
            for frozen, case, pins in zip(prepared.cases, bound.cases, bound.pins, strict=True):
                phase = "current_anchor_lookup"
                current = {"schema": SCHEMA + "_request_receipt", "case_id": case.case_id,
                    "request_sha256": frozen.request_sha256, "body_sha256": frozen.body_sha256,
                    "trial_id": str(trial_id), "physical_attempted": False, "synthetic_attempted": False,
                    "http_status": None, "selected_ids": [], "input_tokens": None,
                    "output_tokens_including_thinking": None, "known_guard_cost_microusd": None,
                    "usage_cost_unknown": False, "browser_page_open_observed": False}
                selections = await _transaction(interfaces,
                    lambda db: interfaces.current_selections(db, bound.scope, case), MAX_ANCHOR_SECONDS)
                phase = "authenticated_render"
                proof = await _transaction(interfaces, lambda db: interfaces.render(db, settings=settings,
                    scope=bound.scope, case=case, selections=selections, pins=pins), MAX_RENDER_SECONDS)
                request = json.loads(frozen.request_bytes)
                body = preparation.canonical({key: value for key, value in request.items() if key != "model"})
                require(digest(body) == frozen.body_sha256, "request_body_changed")
                phase = "quota_wait"
                now = _elapsed(interfaces, began)
                if last_start is not None:
                    await interfaces.sleep(max(0, preparation.MIN_CALL_INTERVAL_SECONDS - (now - last_start)))
                reservation = await interfaces.quota()
                require(callable(getattr(reservation, "commit", None)), "quota_reservation_invalid")
                now = _elapsed(interfaces, began)
                require(last_start is None or now - last_start >= preparation.MIN_CALL_INTERVAL_SECONDS,
                    "quota_wait_incomplete")
                _approval_current(approval, interfaces.clock)
                nonce = uuid4()
                current["dispatch_nonce"] = str(nonce)
                phase = "fresh_dispatch_guard"
                receipt = await _transaction(interfaces, lambda db: interfaces.final(db, settings=settings,
                    scope=bound.scope, case=case, selections=selections, pins=pins, proof=proof,
                    trial_id=trial_id, dispatch_nonce=nonce, after_quota_wait=True), MAX_GUARD_SECONDS)
                guard_bytes = _receipt(receipt, interfaces=interfaces, prepared=prepared, bound=bound,
                    case=case, pins=pins, trial_id=trial_id, nonce=nonce)
                require(reserved + per_call <= preparation.MAX_COST_USD, "cost_reservation_failed")
                reserved += per_call
                result["reserved_input_tokens"] += preparation.MAX_INPUT_TOKENS
                result["reserved_output_tokens"] += preparation.MAX_OUTPUT_TOKENS
                result["reserved_cost_usd"] = str(reserved)
                ledger.write(case.case_id + "-dispatch-guard.json", receipt)
                ledger.write(case.case_id + "-intent.json", {**current, "status": "dispatch_intent",
                    "guard_receipt_sha256": digest(guard_bytes), "reserved_cost_usd": str(per_call)})
                _receipt(receipt, interfaces=interfaces, prepared=prepared, bound=bound,
                    case=case, pins=pins, trial_id=trial_id, nonce=nonce)
                _approval_current(approval, interfaces.clock)
                last_start = _elapsed(interfaces, began)
                current.update(physical_attempted=not interfaces.synthetic,
                    synthetic_attempted=interfaces.synthetic, usage_cost_unknown=True)
                counter = "synthetic_transport_calls" if interfaces.synthetic else "provider_calls"
                result[counter] += 1
                phase = "provider_transport"
                async with asyncio.timeout(preparation.MAX_CALL_SECONDS):
                    response = await interfaces.transport(preparation.ENDPOINT, body, api_key=api_key,
                        timeout_seconds=preparation.MAX_CALL_SECONDS)
                require(type(response) is custody.SuppliedHTTPResponse and type(response.status) is int
                    and 100 <= response.status <= 599, "transport_response_invalid")
                current["http_status"] = response.status
                require(response.status == 200, "provider_http_failure")
                phase = "strict_response"
                require(type(response.body) is bytes and 0 < len(response.body) <= preparation.MAX_HTTP_RESPONSE_BYTES,
                    "response_size_invalid")
                # Native usage is captured even if finish/schema/verdict/token
                # validation fails later. Neither raw HTTP nor thinking is saved.
                current.update(custody._usage(response.body))
                ledger.write(case.case_id + "-usage.json", {**current, "status": "usage_observed"})
                phase = "usage_reconciliation"
                async with asyncio.timeout(MAX_GUARD_SECONDS):
                    await reservation.commit(current["input_tokens"])
                phase = "strict_response"
                projected = preparation.parse_supplied_response(frozen, response.body)
                selected = tuple(projected["selected_ids"])
                current.update(selected_ids=list(selected), question_status=projected["question_status"],
                    excluded_cue_conflicts=projected["excluded_cue_conflicts"])
                phase = "post_selection_guard"
                selected_receipt = await _transaction(interfaces, lambda db: interfaces.final(db, settings=settings,
                    scope=bound.scope, case=case, selections=selections, pins=pins, proof=proof,
                    trial_id=trial_id, dispatch_nonce=nonce, after_quota_wait=True,
                    selected_ids=selected), MAX_GUARD_SECONDS)
                selected_bytes = _receipt(selected_receipt, interfaces=interfaces, prepared=prepared, bound=bound,
                    case=case, pins=pins, trial_id=trial_id, nonce=nonce, selected=selected)
                ledger.write(case.case_id + "-selected-guard.json", selected_receipt)
                observation = {"case_id": case.case_id, "selected_ids": list(selected),
                    "question_status": projected["question_status"], "request_sha256": frozen.request_sha256,
                    "admission_sha256": frozen.admission_sha256,
                    "dispatch_guard_sha256": digest(guard_bytes), "selected_guard_sha256": digest(selected_bytes),
                    "backend_association_verified": not interfaces.synthetic,
                    "browser_page_open_observed": False,
                    "unverified_references": True}
                current.update(status="completed", **{key: value for key, value in observation.items()
                    if key not in ("case_id", "selected_ids", "question_status", "request_sha256")})
                ledger.write(case.case_id + "-result.json", current)
                result["cases"].append(observation)
                result["completed_cases"] += 1
                result["known_guard_cost_microusd"] += current["known_guard_cost_microusd"]
                current = None
                _elapsed(interfaces, began)
        result["status"] = "completed"
    except asyncio.CancelledError:
        failure = "cancelled"
    except TimeoutError:
        failure = phase + "_timeout"
    except (ExecutionError, custody.TrialError, preparation.Refusal, guard.DispatchGuardError,
            preparation.contract.VisualSourceJudgmentError):
        failure = phase + "_refused"
    except Exception:
        failure = phase + "_failed"
    finally:
        if interfaces.close is not None:
            try:
                await interfaces.close()
            except Exception:
                failure = failure or "cleanup_failed"
    if failure:
        result.update(status="stopped", failure_phase=phase, failure_code=failure)
        if current is not None:
            current.update(status="stopped", failure_code=failure)
            ledger.write(current["case_id"] + "-result.json", current)
            if current["known_guard_cost_microusd"] is not None:
                result["known_guard_cost_microusd"] += current["known_guard_cost_microusd"]
            elif current["physical_attempted"] or current["synthetic_attempted"]:
                result["usage_unknown_attempts"] += 1
    ledger.write("summary.json", result)
    if failure == "cancelled":
        raise asyncio.CancelledError
    return result

def main(argv=None):
 print(json.dumps({"schema":SCHEMA,"status":"external_host_required","live_authorized":False,"provider_calls":0,"database_writes":0}))
 return 2
if __name__=="__main__":raise SystemExit(main())
