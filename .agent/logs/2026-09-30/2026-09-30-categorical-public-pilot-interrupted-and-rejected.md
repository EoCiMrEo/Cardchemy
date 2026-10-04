# Categorical public page judge: interrupted run and unrecoverable quality miss

Date: 2026-09-30 (America/Chicago). Scope: the one separately approved,
public-only Gemini 3.5 Flash-Lite categorical calibration. This is a
failure-inclusive **partial diagnostic**, not an official 66-case score or a
release result. No private Knowledge, chat history, identity or PDF bytes were
sent. Ask remained disabled.

## Starting context and authorization

The approved [frozen envelope and preflight](2026-09-30-categorical-public-pilot-approved-preflight.md)
allowed at most 66 calibration calls, with 60 different-PDF heldout calls only
after every calibration gate passed. The one-use receipt bound code, packet,
model, price, request body, cost and time. It allowed no automatic retry. The
pilot aimed to improve useful multi-page selection while preserving zero false
no-match and at least 90% usefulness across every displayed cue and page.

## Observed execution and interruption

The caller made 58 contiguous public calibration attempt claims, G001–G058,
and wrote 58 paired valid response/usage receipts and zero error receipts.
After the session boundary, the command session handle was unavailable.
An elevated OS process inventory found no surviving Python caller. The output
has neither `run-complete.json`, `score.json` nor `run-stop.json`; eight groups
were not claimed. The exact interruption cause is unverified. The consumed
one-use ledger and receipt files were preserved; no restart, replay or heldout
call was made. A missing terminal receipt cannot be promoted to completion.

Read-only validation checked the frozen **calibration** packet/labels, all 58
request hashes, paired response/usage receipts and the categorical parser. It
did not read the sealed heldout. Safe aggregate findings from the 58 observed
groups:

| Measure | Observed |
| --- | ---: |
| Positive groups with a useful shown page | 44/46 |
| No-useful groups with a false display | 0/12 |
| Displayed cue-plus-page cards independently useful | 65/70 (92.86%) |
| Exact selection when 1 page was useful | 16/18 |
| Exact selection when 2 pages were useful | 10/16 |
| Exact selection when 3 pages were useful | 2/10 |
| Three useful selections in 4-useful overflow | 0/2 |
| Valid response/usage pairs; invalid parsed output | 58; 0 |

Successful receipts reported 75,065 input and 4,394 output tokens, or about
USD 0.033505 at the approved conservative Paid price guard. The account's
actual Free-tier billing is not independently receipted; this is not a bill.
There were no failed HTTP receipts in these 58 calls. No cost is inferred for
the unclaimed final eight groups.

The 58 observed groups already make the **frozen calibration gate
mathematically unreachable**: both four-useful overflow cases were scored
0/2 but require 2/2, and 3-page exact selection was 2/10, which eight
remaining groups could not raise to a 5/6 ratio. Therefore the candidate is
rejected for quality even apart from the interruption and incomplete score.
The apparently favorable 65/70 displayed-card usefulness does not override
the multi-page or completion gates. This is exposed development evidence,
not an independent holdout pass.

A second read-only root-cause pass compared each of the 232 issued public
pages in these 58 groups with its independently reviewed cue-plus-page label:

| Model label | Useful | Not useful |
| --- | ---: | ---: |
| `DIRECT_RELATION` | 52 | 0 |
| `USEFUL_BRIDGE` | 13 | 5 |
| `TOPIC_ONLY` | 20 | 40 |
| `IRRELEVANT` | 3 | 99 |

All **23** missed useful pages came from the model's `TOPIC_ONLY` or
`IRRELEVANT` labels; none was dropped by the three-card cap or issued order.
Blindly promoting `TOPIC_ONLY` would add 40 weak pages for 20 useful ones,
so it cannot safely fix cardinality under the 90% displayed-card gate. This
diagnosis identifies per-page false negatives as the main failure mode; it
does not validate any replacement policy.

## Consequences and next boundary

Do not resume or reuse this one-use approval, tune its frozen scorer, open the
60-case heldout, transfer private Knowledge or activate the dormant runtime.
The categorical design needs a new evidence-backed proposal before changing
Lane 6/ADR-024 or running another public/provider comparison. Any new live
pilot requires its own exact endpoint/model/price/call/token/time/cost approval.
Lane 6 remains **3/7**; Ask remains disabled. The populated local database,
root `.env`, encrypted original PDFs and retained Docker volume were not
changed by this public pilot.
