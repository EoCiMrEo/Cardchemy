# Approved checkpointed public source-ID pilot

Date: 2026-09-29 (America/Chicago). Scope: Lane 6 public-only evaluation
protocol and its documentation. Branch `main`, starting HEAD `6c02d6c` with
pre-existing uncommitted Lane 6 work preserved.

## Decision and starting evidence

The operator explicitly approved the [checkpoint proposal](2026-09-29-resumable-public-source-id-pilot-recommendation.md)
and exactly one public pilot within its new limits. The prior permitted-identity
Gemini 3.6 calibration returned three valid IDs with usage, then HTTP 503 on
the fourth physical request. Its one-shot approval is consumed. The accepted
IDs have not been scored or inspected for tuning; the heldout has not opened.
Three successful calls incurred USD 0.007823 at conservative guard prices.
The failed call and earlier failed attempts have unknown actual cost.

## Approved procedure and envelope

Use a new versioned evaluation harness, with a separate ledger, to validate
and hash-bind the three accepted responses/usage receipts and fourth 503
claim against the unchanged frozen public requests, labels and scorer. Resume
only at the first unresolved calibration group. Never replay a completed
group. One **evaluation-only** retry is allowed only after an explicit HTTP
503, with at least 20 seconds of waiting; reserve the full maximum token/cost
allowance even if that call has no usage receipt. A second 503, any other HTTP
error, timeout, network uncertainty, malformed response or access failure
stops and preserves the accepted prefix. Score calibration only after 48
complete groups; open the separate heldout only if calibration passes. Report
physical availability and uncertainty separately from selected-page quality.

The allowed endpoint is
`https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent`:
model `gemini-3.6-flash`, low thinking, `store=false`, an ID-only response,
public current question plus four public page/cue candidates from exactly two
of the eight reviewed CC BY 4.0 PDFs per group. At most 45 remaining
calibration groups plus 48 conditional heldout groups may execute, at most two
physical requests each and **186 new calls** in total. Maximum per call:
8,192 input tokens, 1,024 combined output/thinking tokens and 30 seconds.
Maximum across the new approval: 1,523,712 input/190,464 output tokens, 150
minutes, at least 20 seconds between call starts and after a 503. At the
conservative guard of USD 1.50 input/USD 7.50 output per million tokens, the
new maximum reservation is USD 3.72. The earlier failed-call actual costs
remain unknown and outside this new ceiling. A credential-free, network-free
preflight must pass under the same permitted command identity as live work.

No private Knowledge, account/history/identity or raw PDF bytes may be sent.
There is no application database write, Ask activation, answer generation,
runtime retry or relaxation of the frozen 90%-usefulness and other release
gates. The live run is still pending at the time of this approval record;
approval and documentation are not a pilot result or Lane 6 completion.

## Documentation and verification

Updated the [Lane 6 plan](../../../docs/development/PRODUCT-QUALITY-REMEDIATION-PLAN.md),
[ADR-024](../../../docs/decisions/ADR-024-gemini-source-id-judge.md) and
[ADR index](../../../docs/decisions/ADR-000-INDEX.md). No checklist box was
changed. Source implementation, provider requests and private data are outside
this documentation change. `python scripts/check_context.py` passed: 37
required files, 79 active guides and 1,513 local links. The arithmetic guard
was recalculated: 186 x 8,192 = 1,523,712 input tokens, 186 x 1,024 =
190,464 output tokens and USD 3.714048 reserved, rounded up to USD 3.72.
`git diff --check` exited 0 on the shared worktree; it reported only
line-ending conversion notices. No paid request was made by this
documentation task.
