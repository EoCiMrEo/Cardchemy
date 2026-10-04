# Public Flash-Lite failure-inclusive calibration result

Date: 2026-09-30 (America/Chicago). Starting checkout: `main` at `6c02d6c`
with in-progress Lane 6 changes preserved. The owner separately approved one
exact public-only Gemini 3.5 Flash-Lite continuation after approving the
failure-inclusive scoring rule. The model endpoint, 85-call maximum (37
remaining calibration plus 48 conditional heldout), 8,192/1,024 token
per-call caps, 696,320/87,040 aggregate token caps, 20-second spacing,
90-second call limit, 180-minute total limit, zero retry and USD 0.50 new
Paid-equivalent guard were fixed before execution. No private Knowledge,
original PDF bytes, history, user identity or labels were sent.

## Admission and observed result

The 62 focused keyless tests passed after the owner authorization identifier
was set. A hash-bound approval receipt pinned the continuation core, HTTP
adapter, source-ID parser, frozen public packet/labels and old checkpoint.
The approved zero-call preflight passed under the same command identity as
the live run, with the dedicated key present. The exact one-use claim was
consumed by the subsequent run. Old accepted groups 1–10 were retained;
the old group-11 timeout remained a failed case and was not called again.

The continuation made **37 new calibration calls**. All 37 returned accepted
source-ID and usage receipts, with no new unreceipted call. Across the full
48-case calibration, availability was **47/48** (the one old timeout), above
the amended 46/48 floor. Useful-page hit@3 was **35/36** positive groups:
direct 12/12, paraphrase 12/12 and follow-up 11/12. Among **55 displayed
cards**, **54** had both a useful exact cue and useful original PDF page
(98.18%). The observed no-useful groups had **11/12** valid empty selections
and **one false display**. That violates the frozen zero-false-display
no-match gate. Consequently `source_quality_passed=false` and
`calibration_passed=false`; this public candidate did **not** pass.

The pilot stopped after calibration. The 48-case different-PDF heldout was
**not opened**, and no heldout score exists. The one-use approval and claim
are consumed. These results must not be converted into a pass by excluding
the timeout or changing the no-match threshold after seeing the score.
The application still pins its dormant Gemini 3.8 source judge, Ask remains
disabled and Lane 6 remains **3/7**. No runtime model/policy, database,
original PDF attachment, volume or root `.env` change was made by this
evaluation.

## Bounded usage and evidence

The 37 new accepted receipts report 50,520 input and 634 output tokens;
their conservative Paid-equivalent guard cost is USD 0.016758, compared
with USD 0.185666 reserved for the 37 calls. Together with the ten prior
accepted receipts, known guard usage is 63,566 input and 812 output tokens,
or USD 0.021121. The older timed-out request and other historical failed
requests still have unknown actual provider cost; these guard values are
not an invoice. The Free-tier public-content disclosure remains applicable.

The aggregate score artifact SHA-256 is
`ab051951155ff185491d47a2eb31719a8356ef55d33e52abce18392889b189f6`;
the terminal result artifact SHA-256 is
`4cf256a168b63d2dae2666947c46f455e0dc902507f82081a940f2cbd2b1630c`.
These artifacts remain in ignored OS Temp; the log records counts only,
not question text, selected IDs, pages or raw model responses. A read-only
post-run check found exactly 37 new calibration claim files, no heldout
directory and no heldout score. Independent diagnosis may inspect only
the public calibration material; no further live call or policy change is
authorized by this record.
