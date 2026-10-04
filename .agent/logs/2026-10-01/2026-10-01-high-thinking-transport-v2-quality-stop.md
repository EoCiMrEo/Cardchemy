# High-thinking transport v2: early quality stop

Date: 2026-10-01 (America/Chicago). Terminal evidence for the
[approved public-only pilot](2026-10-01-high-thinking-transport-pilot-approved-scope.md)
after its [single pre-attempt startup recovery](2026-10-01-high-thinking-transport-v2-startup-recovery.md).
The supervised child has exited. No caller process remains. No code,
threshold, request or label was changed during the run.

## Physical execution

- Exactly **12** physical calibration attempts: **11** valid responses and
  **one timeout**, never retried. The real ledger contains the split claim
  and 12 group claims. The original detached launch reached zero provider
  attempts; the supervised recovery used this same unused approval.
- Terminal reason: `calibration_quality_unreachable`. The exact terminal
  receipt SHA-256 is
  `e337fe77689f95b9437253636c397194ef75ad42ac05ed18a6478172ce10a5b1`.
- The 64 KiB reader accepted the first three responses and did not stop
  on an oversized envelope in these 12 attempts. This resolves the
  observed pilot transport obstruction for this sample, not every possible
  provider response. The earlier discarded v1 response's shape is unknown.
- Reported successful usage: **14,187 input** and **12,888 combined output
  and thinking tokens**; conservative known cost **USD 0.036482**. The
  timeout's actual cost is unknown, as are earlier failed requests.
  Maximum attempt latency was **30,005 ms**, including the timeout.
- **Zero heldout attempts.** No full 66-case score exists. No private
  Knowledge, history, identity, gold labels or PDF bytes were transmitted;
  no database/runtime/Ask activation occurred. The one-use authorization
  and recovery claim are consumed and must not be replayed.

## Observed subset, not a full evaluation score

The frozen-label diagnostic counts all 12 observed cases, including the
timeout as a miss. It does not count the 54 unattempted cases as success.

| Observed measure | Result |
| --- | --- |
| Valid responses | 11/12 |
| Positive cases with a useful displayed page | 8/9 |
| Useful displayed cue-plus-page cards | 12/14 (85.7%) |
| Correct empty result on observed no-match cases | 3/3 |
| Exact useful selection, one-useful stratum | 5/5 |
| Exact useful selection, two-useful stratum | 0/3 |
| Exact useful selection, three-useful stratum | 1/1 |

The three two-useful cases have different causes: G004 and G012 each
returned three pages, including both useful pages and one frozen-label
weak page. G008 timed out and therefore returned no accepted selection.
This subset points to extra weak-page selection and availability, not a
failure to retrieve either useful candidate in the two successful cases.
It is too small to establish population accuracy or claim a release pass.

## Why the early stop was correct under the frozen rule

The calibration has **17** two-useful cases and requires the exact useful
ID set in `ceil(5 * 17 / 6) = 15` of them. Three already failed, so even a
perfect result for every unattempted case could achieve only **14/17**.
The optimistic calculation gives every remaining case all available
useful IDs up to three; it still cannot pass this predeclared gate.
That is the stop trigger. The observed 85.7% displayed-card usefulness
does not itself prove that the full-run 90% target was unreachable.

The diagnostic is stored locally as safe aggregate JSON at
`.agent/.verification/full-cue-high-thinking-v2-partial-quality.json`.
It is deliberately labeled partial and does not create a full scorer
receipt or authorize heldout admission. The frozen scorer and all old
receipts remain intact. Independent checks of the stopping math and the
original public pages are being performed before any next recommendation.

## Remaining boundary

This candidate did not pass its approved calibration gates. Do not tune
the prompt, raise request limits, relax exact selection/no-match/90% gates,
change its labels after seeing results, or open heldout under this approval.
The previous approved recommendation requires reassessing the selection
design after failure rather than trying unbounded prompt variants. Any
material new proposal needs the owner's plan decision; any new provider
attempt needs a separate exact envelope. Ask remains disabled and Lane 6
remains **3/7**. Current private/PDF/accessibility/release gates remain open.
