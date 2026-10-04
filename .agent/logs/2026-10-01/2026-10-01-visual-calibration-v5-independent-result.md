# Independent public visual calibration v5 result

Date: 2026-10-01 (America/Chicago).

## Scope and preservation

This independent review used read-only local checks after the operator-approved
47-question continuation completed. It made no provider requests, changed no
frozen pilot code, inputs, labels, receipts or claims, and did not read private
Knowledge or application credentials. The retained database, root `.env`,
original PDFs and volumes were outside this review's mutation scope.

The approved scope is recorded in
[the v5 approval log](2026-10-01-visual-calibration-v5-approved.md).
The result is public calibration evidence only. Heldout, private-source
usefulness and application release are separate gates.

## Immutable evidence and reproduction

- Approval file: Temp
  `cardchemy-visual-public-approval-v5-pfm6zro6/approval.json`.
  SHA-256: `71c88d0a613a4b7c0865e0fb2b14dd8f6eb9edf0175e87fad79664630555e48b`.
- Result file: Temp
  `cardchemy-visual-public-calibration-v5-20261001-71c88d0a/result.json`.
  SHA-256: `ab7de74a34811bc2c8bdef2abbd634a7d751b59540f2b0232008fbdedefddb4e`.
- Recomputed admission and exact approval comparison verified all 18 frozen
  code files and the public PDF, image, request and checkpoint hash chain.
- All 47 new request/receipt/attempt-claim bindings matched. The complete
  receipt roster matched the exclusive ledger roster. The ledger contains
  exactly 50 files: launch, execute and run claims plus 47 per-question claims.
- The 20 inherited valid receipts matched their frozen bindings. All six
  historical failed physical attempts remain preserved, including three older
  attempts with unknown cost. No inherited successful group was dispatched
  again by this continuation.
- The canonical score and optimistic ceiling reproduced exactly. A separate
  arithmetic implementation reproduced displayed-card usefulness, positive
  hits by question form, unknown-card count and no-match count.
- The resource receipt binds four CPU and two GiB process-tree memory,
  5,400-second supervisor limit and termination on Job Object close. The frozen
  worker checks membership and configured limits in the named resource job
  before provider execution. The supervisor completion receipt records exit
  code 0 and no resume permission.

An initial sandboxed read could not access an older approval file. The review
continued through normal approval with a read-only local audit; this did not
start or repeat the provider trial.

## Measured results

| Measure | Result |
| --- | --- |
| New physical provider attempts | 47, exactly the approved maximum |
| Retained valid results | 20 |
| Complete question denominator | 67 |
| Valid responses | 65/67 |
| New failed outcomes | 2/47 |
| Positive questions with a useful page | 52/54 |
| Direct / paraphrase / follow-up hits | 18/18, 16/18, 18/18 |
| Useful cards across all displayed cards | 92/103, 89.32% |
| Ordinary no-match controls with a valid clear empty result | 12/12 |
| Displayed cards with uncertain source labels | 0 |
| New reported input / output tokens | 315,401 / 77,057 |
| Minimum measured call-start spacing | 20.101 seconds |
| Maximum measured request latency | 43.344 seconds |
| Continuation elapsed time | 992.605 seconds |
| New known cost under the approved guard | USD 0.287286 |
| Cumulative known historical plus continuation guard cost | USD 0.418156 |
| New attempts with unknown cost | 0 |
| Historical attempts with unknown cost | 3, retained separately |

Q054 and Q055 failed strict local verdict validation with
`provider_verdict_invalid`. Their reported usage and known guard costs were
retained; they remain failed outcomes in the denominator. The audit does not
infer their malformed response contents, which are not persisted in the
sanitized receipt.

All per-call, aggregate token, cost, spacing, elapsed-time and configured
resource bounds were met. Cost figures are guard estimates from reported
usage, not provider billing receipts. Historical unknown charges remain
unknown.

The exact-set and cardinality metrics remain diagnostic: exact sets were
10/17, 10/21, 10/14 and 2/2 for the one-, two-, three- and four-useful-page
strata. At least two useful pages were returned in 28/37 eligible groups and
at least three in 12/16. The 17 omitted historically useful page pairs remain
in the report; no difficult case or older failed trial was removed or regraded.

## Conclusion and limits

The continuation **passes its prospectively approved calibration gates**:
at least 80% across every displayed card, at least 45/54 positive hits,
at least 15/18 per form, at least 65/67 valid results with no more than two
failed outcomes, and at least 10/12 ordinary no-match controls. The observed
no-match result is 12/12. This review found no blocking result-binding or
provider-envelope violation.

This is a mixed retained calibration sample: 20 earlier valid results used
the preceding 2,048-output-token contract, while the 47 new attempts used the
approved 4,096-output-token contract. The independent heldout must measure
the final contract directly. Historical trials remain failed under their
original gates; this result does not retroactively make them pass.

The result explicitly records `heldout_opened=false`,
`release_gate_passed=false` and `ask_enabled=false`. It does not establish
private lecture transfer approval, current application runtime equivalence,
original-PDF browser success for a new runtime, spoken assistive-technology
release evidence, hosted CI or Lane 6 completion.

## Separate immutable application-file comparison

During the later read-only v6 contract review, root extracted comparison
digests without network access from the previously built immutable backend
image `sha256:b73791614cfc41f34b3042cc81762396e961e5768bae26c1496827a774356e3f`.
This reviewer independently hashed the current local files and confirmed exact
matches to that older image evidence:

- Installed migration `20261001_0030_visual_source_judgment.py`:
  `662c066cb7d5d16e75430c373a60fa469144bf9ee86e11ae23b8b2b05d956055`.
- Original `source_judgment_visual.py` contract:
  `d74f2e15315725adbf5c8e78b50e1ae13c2fe171f8f2a3edae7d302c5fbe740e`.

This establishes byte preservation against the prior image rather than
inferring preservation from an untracked working-tree diff. It does not
activate v6 or extend the completed public provider envelope.

## Subsequent application contract review

The bounded read-only frontend review found no blocking mismatch. The active
admission and manual retry paths require the current v6 policy and visual-v2
profile; historical v5 results remain readable. A fresh processor-profile
comparison includes the source contract and transfer fields, and a changed
profile requires renewed disclosure review. The review inspected the two new
history/admission tests and the existing changed-profile test; it did not
duplicate root's complete frontend verification.

The bounded read-only backend review also found no concrete blocker. A pure
comparison verified the new 0031 migration's predecessor, all eight retained
old-policy expressions, six current model CHECK expressions and the visual
remote-attempt partial unique index. No database or migration was executed by
this reviewer. The current v6 worker, source provider, profile and schema agree
on visual-v2, HIGH thinking and the 4,096-token thinking-inclusive output cap.
Old v5/v1 jobs retain their own snapshots and read support but cannot execute
or manually retry under the new policy. The worker retains its stage/lease,
current access, publication, revision and exact-reference checks; references
and the terminal outcome remain atomic. Downgrade refuses existing v6 rows
before changing the schema.

The prospective adaptive renderer keeps the fixed renderer as its default.
Only v6 preparation explicitly enables full-page 1,600/1,400/1,200/1,000-pixel
attempts after a definitive owned regular-file byte oversize. Other failures
do not reduce resolution. The attempts share one 30-second page deadline and
the existing 120-second rendering-call ceiling; process-group reaping,
cancellation and exclusive temporary-source cleanup remain enforced. Visual-v2
validates the actual scale/dimensions and copies the local provenance when
projecting into the unchanged v1 request builder; it does not mutate candidate
bindings or old v1 constants. This is a static contract review, not live
renderer, retained-cutover or provider evidence.

## Manual accessibility scope clarification

No spoken assistive-technology pass was performed by this reviewer. The
accessibility guide explicitly requires that pass before release on the
production candidate, then again on the packaged release candidate. Lane 7
also explicitly requires the pass for a released lane or Ask policy. The
maintained Lane 6 acceptance retains spoken-accessibility and operational
release gates and separate enablement gates. Therefore development-local
testing and packaged release are different evidence scopes, but these texts
do not support declaring every Lane 6/release requirement satisfied without
the required spoken evidence or an explicitly resolved release-scope decision.
Automated browser, component, axe and accessibility-tree checks cannot be
recorded as a spoken pass.
