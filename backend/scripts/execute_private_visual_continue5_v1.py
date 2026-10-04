"""Separate five-case controller; unchanged guarded execution loop, new claim.

Only its denominator/profile namespace is different. Retained outcomes are
freshly authorized before new execution, without provider replay. This module
never mutates the old module globals or restores old claims.
"""
from __future__ import annotations
from types import FunctionType
import execute_private_visual_trial_v8 as base
for _name, _value in vars(base).items():
    if not _name.startswith("__") and (not isinstance(_value, FunctionType) or _value.__module__ != base.__name__):
        globals()[_name] = _value
import prepare_private_visual_continue5_v1 as preparation
import run_private_visual_continue5_v1 as custody
import rehearse_private_visual_continue5_v1 as rehearsal
SCHEMA = "private_visual_continue5_v1_execution"
APPROVAL_SCHEMA = SCHEMA + "_approval"
LIVE_AUTHORIZED = False
EXECUTOR_PATH = "backend/scripts/execute_private_visual_continue5_v1.py"
REHEARSAL_PATH = "backend/scripts/rehearse_private_visual_continue5_v1.py"
def _shared(function):
    result = FunctionType(function.__code__, globals(), function.__name__, function.__defaults__, function.__closure__)
    result.__kwdefaults__ = function.__kwdefaults__
    return result
for _name, _value in vars(base).items():
    if isinstance(_value, FunctionType) and _value.__module__ == base.__name__ and _name not in ("execute_private_trial_v8", "main"):
        globals()[_name] = _shared(_value)
class TrialLedger:
    __init__ = _shared(base.TrialLedger.__init__)
    _directory = _shared(base.TrialLedger._directory)
    write = _shared(base.TrialLedger.write)
Interfaces = base.Interfaces
async def _execute_new_five(prepared, bound, *, settings, api_key: str,
    approval_bytes: bytes, approval_sha256: str, ledger: TrialLedger,
    interfaces: Interfaces | None = None) -> dict:
    """One approved private12 trial, stopping on any error without automatic replay.

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


async def execute_private_continue5(prepared, bound, *, retained_context, settings, api_key,
    approval_bytes, approval_sha256, ledger, interfaces=None):
    _approval(approval_bytes, approval_sha256, prepared=prepared, bound=bound,
        now=interfaces.clock() if interfaces is not None else _now())
    full, full_bound, records = retained_context
    require(tuple(c.case_id for c in full.cases) == base.preparation.CASE_IDS,
        "retained_context_invalid")
    fresh = interfaces or production_interfaces(settings)
    require(interfaces is None or fresh.synthetic is True and os.environ.get("ENVIRONMENT") == "test",
        "injected_interfaces_forbidden")
    if interfaces is None: _environment(settings, bound)
    try:
        async with asyncio.timeout(preparation.MAX_TOTAL_SECONDS):
            checked = await rehearsal.recheck_retained(full, full_bound, records, settings=settings,
                interfaces=fresh, transaction=_transaction, validate=_receipt)
    finally:
        if interfaces is None and fresh.close is not None: await fresh.close()
    # Exact old selections survive; this receipt only refreshes access/context,
    # and never promotes it to a PDF opened by a browser.
    path = ledger.directory / "retained-recheck.json"
    from launch_private_visual_continue5_v1 import exclusive
    exclusive(path, preparation.canonical({"schema": SCHEMA + "_retained_recheck",
        "parent_stage_sha256": preparation.PARENT_STAGE_SHA,
        "parent_output_pins_sha256": preparation.PARENT_OUTPUT_PINS_SHA,
        "cases": checked, "provider_calls": 0, "database_writes": 0,
        "browser_page_open_observed": False}))
    result = await _execute_new_five(prepared, bound, settings=settings, api_key=api_key,
        approval_bytes=approval_bytes, approval_sha256=approval_sha256, ledger=ledger, interfaces=interfaces)
    result.update(preserved_completed_cases=7, full_quality_denominator=12,
        historical_provider_calls=8, historical_known_guard_cost_microusd=38077,
        historical_unknown_attempts=1, retained_sources_rechecked=len(checked))
    return result
