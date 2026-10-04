# Per-page source verdict: public calibration failed

Date: 2026-09-30 (America/Chicago). One separately approved, one-use
public-only `gemini-3.5-flash-lite` pilot ran its full 66-group calibration
under the [pinned envelope](2026-09-30-per-page-verdict-pilot-approved-preflight.md).
No private Knowledge, PDF bytes, user identity, chat history or review labels
were sent. The output remained in the ignored local Temp area. No application
database write, Ask activation or heldout call occurred. The retained volume,
root `.env` and three original private PDFs were preserved.

## Physical execution and guard

- 66 physical POST claims were consumed. 65 returned schema-valid four-page
  verdicts; one timed out. The timeout was counted as a miss and was not
  retried. Availability passed its at-least-64/66 and at-most-two-error gate.
- Reported successful usage: 83,770 input and 8,119 output tokens. The
  conservative price-guard estimate for those receipts is **USD 0.045460**.
  Actual billing for the timeout is unknown, and Free-tier billing is not a
  provider receipt. No new cost was inferred as zero from the timeout.
- The canonical calibration receipt SHA begins `31be7ab6`; the one-use claim
  manifest SHA begins `19a213e9`. The consumed v3 ledger cannot authorize a
  second run. The 60-group different-PDF heldout was neither called nor opened.

## Frozen score

| Check | Measured result |
| --- | ---: |
| Valid responses | 65/66 |
| Positive questions with a useful page selected | 51/54 |
| Useful cue and original-PDF page among **all** displayed cards | 63/63 (100%) |
| False display in independently no-useful groups | 0/12 |
| Valid no-useful abstentions | 12/12 |
| Exact selection, one useful page available | 19/19 |
| Exact selection, two useful pages available | 4/17 |
| Exact selection, three useful pages available | 3/16 |
| Four-useful overflow selecting three useful pages | 0/2 |

The output passed availability, displayed-card precision and no-match checks
but **failed** the required exact multi-page/cardinality and overflow gates.
`calibration_passed=false`; `heldout_opened=false`; Lane 6 remains **3/7**
and Ask remains disabled. The fixed pre-heldout cardinality check prevented
the different-PDF split from opening on a high-precision but under-complete
selection.

## Read-only Boolean diagnosis on the exposed 66 groups

Only after the calibration completed, a read-only local script compared the
two returned Boolean fields with the independently reviewed **public**
cue-plus-page labels. No additional provider call or heldout read occurred.
Among 106 gold-useful candidates in completed groups, the model marked 80
`useful_reading_page=true`, but only 63 also had
`requested_relation_present=true`. The relation verdict was always a subset
of the useful verdict in this sample; it rejected 17 gold-useful candidates
that the useful verdict accepted. Of 154 gold-negative candidates, the useful
verdict accepted four and the relation verdict accepted none.

An offline, development-only counterfactual using only the useful Boolean
would have shown 79/83 useful cards, selected a useful page for 52/54
positive questions and kept zero false no-match displays on **these exposed
cases**. Yet exact selection would still be only 10/17 for two-useful,
5/16 for three-useful and 1/2 for overflow. Dropping the relation Boolean
alone therefore does not solve the approved 2–3-page behavior. These
counterfactuals are hypothesis diagnostics, not an independent gate pass or
permission to change the app policy.

The observed cause is under-selection of independently useful pages by both
per-page verdicts, amplified by the stricter relation conjunction. It does
not prove that the remote model cannot perform the task under a different
question contract or that private-course retrieval has adequate candidates.
The 66 groups are now exposed development data; any revised selector needs a
prospectively frozen rule and a separate public validation and private
original-PDF/access evaluation. Do not replay this ledger or weaken the
release gate to turn this result into a pass.
