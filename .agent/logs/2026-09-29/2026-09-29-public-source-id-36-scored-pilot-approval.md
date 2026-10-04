# Approved public Gemini 3.6 scored source-ID pilot envelope

Date: 2026-09-29 (America/Chicago). Scope: documentation of the operator's
separate, exact approval for **one** public-only scored candidate pilot. This
record is not a provider execution, quality result, private-Knowledge transfer
or Ask activation. The shared Lane 6 worktree and retained populated volume
were preserved; Ask remains disabled and Lane 6 remains 3/7 at this point.

## Starting evidence and approval

Three separately approved public Gemini 3.8 attempts each consumed one
physical request and yielded no calibration score; the last two returned
HTTP 503. All three actual failed-call costs are unknown. A later, separately
approved two-call public Gemini 3.6 transport diagnostic returned two valid
HTTP 200 source-ID responses, but discarded selected IDs and yielded no
usefulness score. Its guard-cost estimate was USD 0.004322. See the
[transport record](2026-09-29-public-source-id-36-transport-diagnostic.md).

The operator now approved the new exact eight-PDF scored pilot and the Lane 6
and ADR-024 update. The [keyless readiness record](2026-09-29-public-source-id-36-scored-pilot-readiness.md)
pins the reviewed public packet, labels and split. Eight distinct public
CC BY 4.0 lecture PDFs are involved: four calibration and four different
heldout PDFs. Each question's four candidate pages come from exactly two
PDFs. The frozen public quality criteria, including usefulness of at least
90% of **all displayed cue-plus-page cards**, are unchanged.

## Exact authorized limit

- Endpoint: `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent`; model `gemini-3.6-flash`, low thinking, `store=false`.
- Request/response: current **public** question and four public page/cue candidates with ephemeral IDs; model returns only zero to three issued IDs. No private Knowledge, chat history, user identity or PDF bytes.
- At most 48 calibration physical requests; at most 48 heldout requests **only after the frozen calibration gate passes**; 96 total. No automatic retry or redirect; at least six seconds between request starts.
- At most 8,192 input and 1,024 combined output/thinking tokens per request; 786,432 input and 98,304 output tokens total. At most 30 seconds per request and 90 minutes overall.
- Conservative admission prices USD 1.50 per million input tokens and USD 7.50 per million output tokens; maximum **new** spend USD 2.00. The three earlier failed-call costs are unknown and outside this new ceiling. Actual provider billing may differ from estimates.
- No application database write, private-source evaluation, indexing or Ask enablement. One consumed pilot ledger does not authorize a restart or another candidate.

## Documentation change, checks and remaining boundary

The [Lane 6 plan](../../../docs/development/PRODUCT-QUALITY-REMEDIATION-PLAN.md),
[ADR-024](../../../docs/decisions/ADR-024-gemini-source-id-judge.md) and
[ADR index](../../../docs/decisions/ADR-000-INDEX.md) now distinguish this
separate public pilot authorization from the earlier architecture decision,
failed 3.8 attempts and transport-only 3.6 check. No Lane 6 checkbox was
marked done. This documentation update made **zero provider calls** and did
not edit source, tests, root `.env`, private data, database or volumes.

The retained v4 worker still pins Gemini 3.8. Even if the public 3.6 pilot
passes, release requires an approved versioned model/policy change, separate
private-content/privacy and live-cost approval, independent original-PDF
measurement plus the remaining security, accessibility and operational gates.
The public four-page, two-PDF slates do not establish the larger runtime pool.
The exact results and request accounting must be recorded separately after
execution. `python scripts/check_context.py` passed: 37 required files,
79 active guides and 1,502 local links. This is a documentation/link check,
not model-quality or live-provider evidence.
