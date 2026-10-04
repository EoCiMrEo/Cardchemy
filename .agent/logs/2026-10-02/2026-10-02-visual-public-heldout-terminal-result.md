# Independent public visual heldout terminal result

## Authorized attempt and terminal proof

The [exact new 60-public-question envelope](2026-10-02-visual-public-heldout-approved.md)
was explicitly approved. Fresh same-environment zero-call preflight passed.
The one-use launcher returned supervisor PID 20556, and its suspended child
PID 25376 was assigned to a four-CPU/two-GiB Windows Job Object before dispatch.
Both were observed live; later both were absent and `result.json` plus terminal
progress confirmed the run had stopped. No restart, automatic retry, private
transfer or application DB write occurred.

Approval SHA:
`f12dcf219569b0571d3dbe50591c75f08e1a04018aec6350617bc6fa04372396`.
Result SHA:
`41dd9c287206046c6bdc7ca7c3e247405b674400ab57f1aeb7232915c1f82095`.
Result remains in OS Temp
`cardchemy-visual-public-heldout-v1-20261002-f12dcf21/result.json`;
exclusive launch/execute/run and six physical group claims remain consumed.

## Complete-denominator interpretation

The run made **six physical requests** in 250.692 seconds:

- Q001/Q002 completed with one useful source each.
- Q003 timed out, Q004 returned HTTP 503.
- Q005 completed with a valid empty no-match outcome.
- Q006 timed out.

Three valid responses / two useful displayed cards / one valid empty result
are insufficient evidence for a complete heldout quality result. The original
60-case denominator remains: 54 unattempted cases were not silently omitted.
At the third failure, at most 57/60 valid responses remained possible against
the approved >=58/60 availability and <=2-error gates. The scorer therefore
stopped with `quality_unreachable` for **availability/error budget**, rather
than claiming that the model's relevance quality had failed or passed.

Reported usage from valid replies: **20,450 input / 3,323 output tokens**.
Known usage-times-guard cost is **USD0.014444**; the two timeouts/503 have
unknown charges. Earlier calibration guard USD0.418156 and older unknown
charges remain separate. These estimates are not provider billing receipts.
All failures remain visible and the trial's `resume_permitted` is false.

## Preserved release boundary

The calibration pass (92/103 useful cards) remains calibration-only. This
independent trial did **not** pass. Do not replay its approval or mutate its
code, labels, gates or failed result to turn it into a pass. Any subsequent
provider attempt needs a new exact envelope; any changed gate needs an
explicit prospective operator decision. Current source-only policy and
zero source-integrity requirements remain intact.

After Docker reopened, eight local services were healthy and the retained
DB verified current head 0031. Ask, answer availability and source-judge
provider execution remain false. Root `.env`, populated volume, original
PDFs and restore-verified backup were preserved. No private provider result,
spoken assistive-technology pass, Ask activation or Lane 6 closure is claimed.
Lane 6 remains **3/7**; the goal is incomplete.
