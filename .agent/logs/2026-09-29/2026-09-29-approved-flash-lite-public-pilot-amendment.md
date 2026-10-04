# Approved Free-tier public Flash-Lite pilot amendment

Date: 2026-09-29 (America/Chicago). Branch `main`, starting HEAD
`6c02d6c`. Scope: document the operator's explicit approval of **one**
Gemini 3.5 Flash-Lite synchronous source-ID evaluation using public PDF
material only. This record does not claim provider admission, a quality score,
private-content permission, runtime model selection, Ask activation or a
Lane 6 checklist completion.

## Starting context and decision

The retained local application has Ask disabled, source schema head `0029`,
three exact original-PDF attachments and a populated database volume. The
earlier public Gemini 3.6 Batch creation returned HTTP 400 and consumed its
one-use claim without a quality score. The operator chose to retain Google
AI Studio Free tier, chose to create a distinct source-judge API key and enter
it into root `.env` personally, and approved the exact public synchronous
pilot plus a Lane 6/ADR-024 update. The three accepted 3.6 source-ID results
are not combined with the new model's score.

Only the current public question and four public page/cue snippets from
exactly two of eight frozen CC BY 4.0 PDFs per group may be sent to
`https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`.
The model is `gemini-3.5-flash-lite`, with low thinking, `store=false`,
structured output restricted to 0–3 distinct issued page IDs, no tools or
model fallback. No private lecture, history, identity, labels or raw PDF
bytes are submitted. The user-confirmed product audience is age 18+.

The one-use envelope permits at most 48 calibration calls, then 48
different-PDF heldout calls only if complete calibration passes: 96 physical
calls total, zero retries, at least 20 seconds between request starts,
30 seconds per call and 120 minutes overall. The per-call input/output plus
thinking caps are 8,192/1,024 tokens, and total caps are 786,432/98,304.
Current Free-tier list price is USD 0; conservative Paid Standard guards are
USD 0.30/2.50 per million input/output tokens and USD 0.50 maximum **new**
spend. Earlier failed-call charges remain unknown. Free-tier public content
may be used by Google to improve its products; private-content evaluation
requires a separate privacy and provider/cost decision. If a request fails,
the run stops without replay. A zero-call approval-aware preflight under the
actual calling identity is required after the separate key is entered.

## Documentation and verification boundary

The approved envelope was added to
`docs/development/PRODUCT-QUALITY-REMEDIATION-PLAN.md` and
`docs/decisions/ADR-024-gemini-source-id-judge.md`; current state and roadmap
now distinguish this pending public evaluation from the consumed Batch. The
[proposal](2026-09-29-free-tier-public-synchronous-source-id-proposal.md),
[keyless harness readiness](2026-09-29-flash-lite-public-pilot-keyless-readiness.md)
and [frozen packet preflight](2026-09-29-flash-lite-public-exact-packet-preapproval.md)
contain the previous provider-free checks. This amendment changes no
runtime, DB, root `.env`, provider claim, stored PDF or Ask gate. The retained
application remains pinned to Gemini 3.8 Flash; even a public Flash-Lite pass
would need a separately approved versioned runtime/policy selection, private
transfer decision and independent original-PDF release measurement. Lane 6
remains **3/7** with four quality/release items open.

After approval, the operator supplied the separate judge key in the existing
root `.env`; the task root confirmed the exact approval-aware, zero-call
preflight passed under the intended live calling identity. Neither the key
nor its value was read into this log. The pilot has no live result yet.

This documentation edit was checked with `git diff --check` and
`python scripts/check_context.py`; the exact results are reported in the
task handoff. Neither check establishes live model availability or source
usefulness.
