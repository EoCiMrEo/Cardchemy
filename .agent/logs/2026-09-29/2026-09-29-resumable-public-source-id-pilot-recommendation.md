# Proposal: checkpointed public source-ID evaluation after HTTP 503

Date: 2026-09-29 (America/Chicago). **Proposal only; no retry, continuation,
private transfer or Ask activation is authorized by this record.** The latest
[approved public calibration](2026-09-29-public-source-id-36-elevated-calibration-503-stop.md)
produced three valid source-ID/usage receipts then stopped on its fourth HTTP
503. The earlier one-shot ledger is consumed. The selected IDs have not been
inspected or scored; the independent public packet, labels, scorer and gate
remain frozen. Three successful physical calls had USD 0.007823 conservative
guard cost; the fourth and earlier failed attempts have unknown actual cost.

## Evidence and constraint

The fourth request passed the same local schema and size construction as the
successful requests and was smaller. Its 503 is a provider response, but the
specific service cause is unknown. [Google's API error guide](https://ai.google.dev/gemini-api/docs/api-errors)
classifies 503 as temporary unavailability, and its
[troubleshooting guide](https://ai.google.dev/gemini-api/docs/troubleshooting)
recommends bounded backoff for 503. A fresh all-or-nothing 48-call pilot would
replay three accepted public judgments and lose progress again at the next
transient error. The application Ask contract must still allow **at most one
source-ID call and zero automatic retries per Ask attempt**.

## Recommended evaluation-only change

1. Build a new versioned **public evaluation harness**, separate from the
   runtime and the two consumed one-shot runners. Validate the first three
   successful results against the original frozen request sequence, issued
   IDs, STOP and usage receipts; bind their file hashes and the fourth 503
   claim into a read-only checkpoint. Do not open or score heldout, inspect
   selected IDs for tuning, or rewrite any previous ledger.
2. A new approval starts at the first unresolved calibration group only. Keep
   one accepted response per frozen group. On an explicit HTTP 503 response
   alone, allow **one evaluation-only physical retry** after at least 20
   seconds. Count the failed call's full maximum token/cost reservation even
   without usage; record first-attempt availability separately. Any second
   503, timeout, network uncertainty, malformed response, access failure or
   non-503 HTTP error stops and preserves the accepted prefix. Further
   continuation then needs another explicit envelope. Never auto-replay a
   completed group or restart the whole pilot.
3. Only a complete 48-group calibration may be scored under the existing
   frozen gate. A calibration failure keeps heldout sealed. If it passes,
   prepare the existing separate-PDF heldout and continue with the same
   checkpoint/quality rules. Aggregate every physical attempt, accepted
   judgment, token receipt, uncertain cost and elapsed time; a provider
   availability miss is reported independently of source usefulness.
4. Keep the production v4 policy and its one-call/no-retry boundary unchanged.
   This public audit cannot enable Ask or justify a private Knowledge transfer.

## Proposed exact envelope for a new approval

Same endpoint `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent`,
model `gemini-3.6-flash`, low thinking, `store=false`. Only the frozen **public**
current question and four public page/cue candidates from two of the eight
already reviewed CC BY 4.0 PDFs are sent per request; only issued page IDs are
accepted. No private Knowledge, history, identity or raw PDF bytes. At most 45
remaining calibration groups plus, only after a calibration pass, 48 heldout
groups. At most two physical requests per unresolved group, hence **186 new
physical requests** total. At most 8,192 input and 1,024 combined output/
thinking tokens per physical request, and **1,523,712 input/190,464 output**
tokens over the new authorization. At most 30 seconds per call, at least 20
seconds between request starts and after an HTTP 503 before its sole retry,
and 150 minutes overall. Conservative guard prices remain USD 1.50 input and
USD 7.50 output per million tokens, so the maximum new reserved cost is
USD **3.714048**, rounded up to a USD **3.72** cap. Earlier failed-call actual
costs remain unknown and outside this new cap. No other automatic retry,
redirect, provider fallback, database write, private source transfer or Ask
enablement. A permitted-identity, credential-free, network-free preflight must
pass before any request. A failure stops without spending remaining allowance.

The current public pilot and release usefulness thresholds are **unchanged**:
calibration first; independently frozen heldout only on pass; every displayed
cue-plus-original-PDF page counted; at least 90% useful displayed cards plus
the separate hit/no-match/security gates. Success on these public two-PDF,
four-page slates cannot establish the larger private runtime pool or fix the
production model mismatch (`gemini-3.8-flash` versus this 3.6 candidate).

Approval would permit updating Lane 6/ADR-024, implementing/testing this
evaluation-only continuation, and then running **one** bounded public pilot
under the exact new envelope. Without approval, preserve the consumed ledgers
and Ask-off state. No Lane 6 checkbox changes from this proposal.
