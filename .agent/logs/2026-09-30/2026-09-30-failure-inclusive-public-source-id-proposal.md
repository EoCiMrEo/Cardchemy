# Failure-inclusive public source-ID evaluation proposal

Date: 2026-09-30 (America/Chicago). Branch `main`, starting HEAD `6c02d6c`.
Scope: record the operator's choice after the Gemini 3.5 Flash-Lite public
calibration stopped. This is an evaluation proposal, not a provider approval,
runtime policy switch, private-content transfer or Lane 6 completion.

## Evidence and operator choice

The one-use public-only calibration made 11 physical requests. The first ten
have accepted source-ID and usage receipts; the eleventh timed out after
30.006 seconds. Its execution and actual charge are uncertain. The original
pilot stopped by design and its claim is consumed, so there is no complete
48-case quality score and no heldout score. Known accepted usage was 13,046
input and 178 output tokens, with USD 0.004363 conservative Paid-equivalent
guard cost. See the [stop record](../2026-09-29/2026-09-29-flash-lite-public-calibration-timeout-stop.md).

The operator chose to **count that timeout as a failed calibration case and
not send it again**. Preserve the ten accepted receipts and all old claims
unchanged. A new, separately authorized continuation would attempt only
groups 12–48, then the sealed 48-group different-PDF heldout only if the
complete calibration passes. The previous 3.6 model's results cannot enter
the 3.5 Flash-Lite score.

## Proposed frozen scoring rule

Before any new provider request, version a composite scorer that checks the
exact old code, public packet, source labels, receipt hashes, approval and
claims, and the failed eleventh claim. It must distinguish a transport failure
from a valid empty selection and from malformed model output. Each of the 48
groups stays in the denominator. A failed positive group has zero useful hit
and zero correct cardinality. A failed no-useful group is an availability
failure, **not** a correct no-match; completed no-useful groups must return
valid empty IDs and no group may display a weak page as primary.

The proposed additional availability gate is at least **46/48** accepted
responses in each split. This permits at most two transport failures per
split and makes the already observed timeout count against calibration.
Retain the pre-registered 90% useful exact cue **and** original PDF page among
every displayed card, zero invalid IDs among accepted responses, zero false
display on no-useful groups, calibration and heldout useful hit@3/form gates,
heldout first-hit/cardinality/useful-card counts, and unchanged private
original-PDF and access gates. Fail or stop on permanent HTTP/schema/identity/
budget errors; only a bounded transient transport failure may be recorded as
a miss, with no retry. If availability cannot reach 46/48, stop early and keep
heldout sealed. A transport failure must never be converted to product
`no_match`.

This rule is disclosed as a **post-transport amendment** to calibration, not
an untouched preregistration. No partial selected IDs or labels were used to
choose it. The disjoint PDF heldout remains unopened and is required for a
confirmatory result. A public pass alone would not choose the retained
runtime model or permit private lecture transfer or Ask enablement.

## Draft bounded continuation, pending exact approval

The potential new scope is at most 37 remaining calibration POSTs plus 48
conditional heldout POSTs, **85 new physical calls**, with zero automatic
retry and at least 20 seconds between starts. At the existing 8,192 input
and 1,024 combined output/thinking token caps per call, the new maximum is
696,320 input and 87,040 output tokens. The official Gemini 3.5 Flash-Lite
[pricing](https://ai.google.dev/gemini-api/docs/pricing) lists synchronous
Standard use as Free on Free tier and Paid-equivalent guard rates of USD
0.30/2.50 per million input/output tokens. Those caps reserve at most USD
0.426496 before any separate higher operational ceiling, plus the ten known
receipts and uncertain cost of the old timeout and earlier failures. The
exact endpoint, timeout, total duration, cost ceiling and immutable script/
packet hashes must be reviewed in a later approval receipt. This log does
**not** authorize any of those calls. No private Knowledge, PDF bytes,
history, identity or reviewer labels may leave the local machine in this
public pilot. The Free tier's public content may be used by Google to improve
its products; private-content disclosure is a separate decision.

## Work and evidence still needed

Finish and independently test the provenance-aware continuation and scorer
with fake transport, including changed/missing/duplicate receipts, attempted
replay of group 11, transport errors, too many failures, all quality gates,
heldout admission and cost/time budgets. Run a keyless and later an exact
approval-aware zero-call preflight before any request. Record the full 48
numerators and denominators; do not infer source quality from the first ten
responses. Ask stays disabled and Lane 6 remains 3/7.
