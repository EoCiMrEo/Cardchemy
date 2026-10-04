"""Fresh read-only original-PDF/source guards for preserved four outcomes.

These are current association receipts, not new provider executions or browser
observations. Failure denies checkpoint credit and the new trial before HTTP.
"""
from __future__ import annotations
import json
from uuid import UUID, uuid4
import rehearse_private_seed_visual_dispatch_v1 as base
import private_seed_visual_dispatch_guard_v1 as guard
import prepare_private_seed_continue10_v1 as preparation

bind_cases, current_selections = base.bind_cases, base.current_selections

async def recheck_retained(full, bound, records, *, settings, interfaces, transaction, validate):
    checked = []
    trial = uuid4()
    old = json.loads(records["summary.json"])["cases"]
    for frozen, case, pins, observed in zip(full.cases[:4], bound.cases[:4], bound.pins[:4], old, strict=True):
        selected = tuple(observed["selected_ids"])
        selections = await transaction(interfaces,
            lambda db: interfaces.current_selections(db, bound.scope, case), 10)
        proof = await transaction(interfaces, lambda db: interfaces.render(db, settings=settings,
            scope=bound.scope, case=case, selections=selections, pins=pins), 30)
        nonce = uuid4()
        receipt = await transaction(interfaces, lambda db: interfaces.final(db, settings=settings,
            scope=bound.scope, case=case, selections=selections, pins=pins, proof=proof,
            trial_id=trial, dispatch_nonce=nonce, after_quota_wait=True, selected_ids=selected), 5)
        raw = preparation.canonical(receipt)
        interfaces.validate_receipt(raw, receipt_sha256=preparation.digest(raw), now=interfaces.clock(),
            trial_id=trial, dispatch_nonce=nonce, scope=bound.scope, case=case, pins=pins, selected_ids=selected)
        checked.append({"case_id": frozen.case_id, "request_sha256": frozen.request_sha256,
            "selected_ids": list(selected), "selected_guard_sha256": preparation.digest(raw),
            "backend_association_verified": not interfaces.synthetic,
            "browser_page_open_observed": False, "provider_replayed": False, "receipt": receipt})
    preparation.require(tuple(row["case_id"] for row in checked) == preparation.RETAINED_IDS,
        "retained_denominator_invalid")
    return checked
