# Public Flash-Lite calibration stopped on a timed-out call

Date: 2026-09-29 (America/Chicago). Branch `main`, starting HEAD
`6c02d6c`. Scope: record the one separately approved, public-only
Gemini 3.5 Flash-Lite synchronous source-ID calibration outcome. The owner
approved its exact endpoint/model/request/token/time/cost envelope and the
Lane 6/ADR-024 amendment. The eight CC BY 4.0 PDFs, 48 calibration and
48 conditionally sealed heldout groups, source-only product direction and
quality gates were frozen before the run.

## Admission and observed outcome

The operator added the separate source-judge key to root `.env`. The exact
approval-aware, zero-call preflight passed under the intended live calling
identity before the first physical request. The approved pilot then made
**11 calibration calls** to the synchronous Gemini 3.5 Flash-Lite endpoint.
Ten returned accepted safe source-ID and usage receipts. The eleventh timed
out at **30.006 seconds** and the harness recorded `provider_timeout` and
`stopped_no_retry`. It did not retry the timed-out item or switch model.
The one-use approval and calibration claim are consumed.

Across the ten accepted receipts, known usage is **13,046 input and 178
output tokens**. The conservative Paid-equivalent guard for those known
receipts is **USD 0.004363**; that is not an invoice. Actual cost for the
timed-out eleventh call is unknown, as are the separate costs of older
failed attempts. The partial ten-item result cannot score the frozen
48-case calibration, and the 48-case independent heldout was **not opened**.
No source-selection quality pass or failure follows from this transport stop.

## Preservation, checks and limits

This pilot was public-only: no private lecture text, PDF bytes, history,
identity or labels were in the permitted request body. No application DB
result or Ask policy was changed by the pilot. The populated volume, original
PDF attachments, prior ledgers and root `.env` were preserved; the operator's
dedicated-key entry was not inspected or copied into this log. Ask remains
**disabled**, the runtime v4 model remains pinned to Gemini 3.8 Flash, and
Lane 6 remains **3/7** with four quality/release items open. A new physical
provider attempt would need a fresh exact authorization and claim; this
record grants none.

Before live execution, the Flash-Lite harness passed 43 focused offline
tests and an exact frozen-public-packet provider-free preapproval check.
After documenting the stop, `git diff --check` and
`python scripts/check_context.py` checked documentation shape; their exact
results are reported in the task handoff. Neither offline tests nor a
partial public run establish private original-PDF usefulness, PDF citation
quality, provider reliability or a release pass.

The chronological status is reflected in
[Lane 6](../../../docs/development/PRODUCT-QUALITY-REMEDIATION-PLAN.md),
[ADR-024](../../../docs/decisions/ADR-024-gemini-source-id-judge.md),
[current state](../../../docs/development/CURRENT-STATE.md) and
[roadmap](../../../ROADMAP.md). The earlier
[approval amendment](2026-09-29-approved-flash-lite-public-pilot-amendment.md)
remains the historical authorization record, not a reusable approval.
