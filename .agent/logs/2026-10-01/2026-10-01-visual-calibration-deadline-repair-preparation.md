# Visual calibration: bounded deadline repair preparation

Date: 2026-10-01. `main` at `6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`;
pre-existing changes preserved.

The operator preauthorized aligned Lane 6 technical/plan updates and accepted
80% complete displayed usefulness. `AGENTS.md` still requires a precise new
provider envelope. The [terminal v3 continuation](2026-10-01-visual-calibration-v3-result.md)
stopped after three 30-second timeouts and one new valid response; this is an
availability failure, without scores for the failed pages. Preserve its code,
result, consumed claims and unknown charges; never reclassify it as passing.

## Prepared distinct trial

[Caller](../../../scripts/run_visual_public_calibration_v4.py) and
[supervisor](../../../scripts/launch_visual_public_calibration_v4.py) retain the
same prompt/model/frozen inputs and use a 60-second deadline. Reuse exactly
five bound successes without resending. The prospective **62 calls** consist
of 59 unattempted groups and explicit manual reattempts of Q019/Q032/Q053;
this is a new deadline trial, not automatic retry or resumption of v3.
Historical failures remain in physical-attempt/cost reporting. All 67 groups
and Yes/No/Unsure labels remain; current complete 80%/hit/form/no-match/
availability gates are unchanged.

Proposed limits: 62 POSTs, zero retry, starts ≥20 seconds apart, 60 seconds
each, 90 minutes total, four CPUs/two GiB; 32,768 input/2,048 output including
thinking per call, aggregate 2,031,616/126,976. Maximum reserve USD 0.926962
inside a proposed USD 0.95 cap at USD 0.30/2.50 per million tokens. Prior
known guard USD 0.024413 plus three unknown charges remains separate.
`LIVE_AUTHORIZED=false`; no key or call allowed by this preparation.

## Checks and boundaries

**20 synthetic caller/supervisor tests pass**: native Windows resource ancestor,
45-second response, three new timeouts stopping, execute claim before key,
five success bindings, historical failures/costs and replay rejection.
Independent read-only review found no blocker. Actual keyless preflight
passed with zero provider calls, validating frozen receipt/claim/source/wire
and terminal result hashes in the intended execution environment.

Pure [application visual contract](../../../backend/app/ai/source_judgment_visual.py)
passed **46 synthetic tests** for exact cue/source/PNG bindings, closed
ID/status labels, request/token/thinking limits and frozen four-candidate wire
equivalence. [Complete archive read](../../../backend/app/services/knowledge_pdf.py)
passed **41 targeted tests**, including missing/reordered/corrupt blocks,
SHA/key mismatch and oversize. Neither helper grants authorization or connects
to an active Ask policy; caller source/revision rechecks remain necessary.

No provider call, private source read/transfer, heldout opening, DB write or
runtime activation occurred. Root `.env`, populated volumes, original private
PDFs and backups remain preserved. Lane 6 **3/7**, Ask off.
