# Public five-request successor: repeated Q056 strict-verdict stop

The [exact five-request scope](2026-10-02-public-heldout-5-approved-scope.md)
made **one** new physical request. Manual Q056 again failed strict verdict
validation with `cue_without_useful_page`, after **5,387 ms**. Reported usage and
guard cost were retained. Q057–Q060 remain untouched. The caller stopped because
another failed case makes the >=58/60 availability gate unreachable; there was
no automatic retry or replay of a valid inherited result.

The finite diagnostic means the response gave a located-cue flag to a page
whose category was not useful under the unchanged contract. This is a schema
consistency failure, not HTTP 503 or timeout. It does not establish whether the
underlying page would have been useful: raw responses are not persisted, and no
failed result is credited or retrospectively accepted. Both Q056 physical
failures remain in history. This record makes no parser change or successor
proposal.

## Independent terminal and process verification

The observer validated existing public inputs and metadata through normal
approved read-only access. It loaded no provider key, made zero provider/network
calls, read no private Knowledge, launched no worker and changed no DB/runtime.

Terminal result SHA:
`e01245c3c247baef93cb3cd1d98bad88cbb09ade02c3ce0f73ae159d4e508e65`.
Read-only reconciliation SHA:
`a2921593d26c6285a71698584e37f6e21c1a803f51f533b1ffd00ae94e6836d6`.

Exact operator approval, frozen code/source/question/label bytes, complete
immutable ancestry, the new receipt and exclusive claim, strict parsing,
reported usage/cost/reservation and the fixed sixty-question score and ceiling
all reconciled. The one-call scope met time/byte/token/resource limits. Its
four-CPU/two-GiB/9,000-second kill-tree supervisor completed with exit zero.
All recorded original process identities are released; numeric PIDs were
absent at observation. Handled terminal failure is not a quality pass.

| Measurement | Independently verified result |
| --- | --- |
| Evaluated questions / fixed denominator | 56 / 60 |
| Valid / active failed outcomes | 53 / 3 |
| Active failures | Q013, Q014, Q056 |
| Untouched questions | Q057–Q060 |
| Useful / all displayed cards | 81 / 86 (94.19%) |
| Reviewer-Unsure displayed cards, zero useful credit | 2 |
| Positive useful hits | 43 |
| Direct / follow-up / paraphrase hits | 14 / 14 / 15 |
| Valid empty no-match outcomes | 10 |
| New / cumulative physical requests | 1 / 65 |

Displayed usefulness, positive/per-form hits and conclusive no-match gates are
true. Completeness, response availability and error-budget gates remain false.
The current result is `stopped`, `quality_unreachable`, `heldout_passed=false`
and `resume_permitted=false`. Even all four untouched questions succeeding
would give only 57/60 valid responses. This is not a complete public quality
gate and does not authorize private transfer or Ask activation. Ask remains off;
Lane 6 remains **3/7**.

## Preserved physical history and guard spending

Physical-history reconciliation SHA:
`4fae3333484ec90347f42623b0c3b10b5439a03eb3f7d4a20a22bcdf80ecd555`.
All **65** historical heldout requests remain represented: **53/65 valid
(81.54%)** and **12/65 failed (18.46%)**. Eight failed charges are unknown; four
strict-invalid failures have reported usage costs. Latest manually replaced
case outcomes and physical request reliability remain separate measures.

The one new request reported **6,898 input/1,371 output tokens**, guard cost
**USD0.005497**, and no new unknown-cost attempt. Combined heldout known guard
cost is **USD0.327896**. Adding the hash-bound calibration lineage's
**USD0.418156** gives **USD0.746052** across those two recorded lineages.
Uncertain heldout/older charges remain uncertain; unrelated earlier pilots are
not a complete billing ledger, and guard estimates are not invoices.

All old results, claims, receipts, strict failures, timeout/HTTP 503 evidence,
costs, source hashes and labels remain unchanged. No consumed scope may resume;
any further provider execution or policy change needs its applicable fresh
authority and prospective evidence.
