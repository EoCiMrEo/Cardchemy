# Failure-inclusive public gate approved and documented

Date: 2026-09-30 (America/Chicago). Branch `main`, starting HEAD `6c02d6c`.
Scope: record the owner's explicit approval to amend the **public evaluation
rule** after the prior Gemini 3.5 Flash-Lite transport stop. This record
grants no new provider request, private lecture transfer, runtime model
selection or Ask activation.

## Decision and implementation boundary

The owner chose to retain ten accepted public receipts, seal call 11's
30.006-second timeout as a failed calibration group, and never replay it.
The owner then approved the specific [proposal](2026-09-30-failure-inclusive-public-source-id-proposal.md):
48 groups remain in each split, at least 46/48 accepted responses are
required in each, a failed positive is a hit/cardinality miss, and a failed
no-useful group is an availability failure rather than a valid empty answer.
Completed no-useful groups must be valid empty selections. The previously
frozen ≥90% useful cue **and** original page among all displayed cards,
positive hit/form, heldout first/cardinality/useful-card and zero false-display
gates remain. An unresolved timeout does not become product `no_match`.

The historical one-shot approval and claim remain consumed. This amended
gate is prospective for a distinct continuation harness and new exact
endpoint/model/price/call/token/time/cost approval. The first ten selected
IDs are not treated as a complete quality score. The different-PDF heldout
remains sealed. The retained Ask path remains source-only and disabled.

## Documentation and verification

Updated Lane 6 in `docs/development/PRODUCT-QUALITY-REMEDIATION-PLAN.md`,
ADR-024, current state, roadmap and the Ask evaluation/shutdown guides to
keep operational wording aligned. Source code, DB, root `.env`, old Temp
ledgers, original PDFs and Ask flags were not changed by this documentation
slice. `python scripts/check_context.py` and `git diff --check` are the
applicable documentation checks; their exact outcome is recorded in the task
handoff. Offline harness and live evaluation are separate pending work.
Lane 6 remains **3/7**.
