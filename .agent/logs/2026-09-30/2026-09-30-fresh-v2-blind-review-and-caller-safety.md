# Fresh public v2 blind review and caller safety

Date: 2026-09-30 (America/Chicago). Checkout: `main` at `6c02d6c`, with
pre-existing local changes preserved. This record supersedes the earlier
same-day browser audit's statement that the 96-group public packet had not
yet been authored; that statement described its earlier point in time.

## Scope and decisions

The owner approved the new public-PDF acquisition and an offline v2
source-ID candidate. The eight public PDFs were already acquired under their
one-use envelope. This pass used no provider key, Gemini request, private
Knowledge transfer, database write, Ask activation, or paid quota. Ask remains
disabled, and Lane 6 remains 3/7.

The immutable authored public input contains 96 groups (48 calibration and
48 different-PDF heldout), with four page/cue candidates from two PDFs per
group. Its SHA-256 is
`8969b9b3dff4dd7e4f5970a8cd6af77dfbb6e3cf99990cfa64c13ce064c145bb`.
The blind review packet SHA-256 is
`cc57023458f6f96e350747f70bb39931b541774e7af738086b6482c60ee03436`.
Neither split has a quality result. Two independent reviewers completed
384/384 original-PDF page/cue judgments each. The blind bridge found exactly
24 disputed candidate decisions spanning 20 original PDF pages; a separate
third reviewer resolved all 24 after checking those 20 original pages.
The root agent did not adjudicate any source label. No labels are
silently inferred from the author's intended strata.

The first keyless freeze **correctly rejected** the 96-group slate: the
independent final page-and-cue labels yielded calibration strata of 18 with
one useful card, 12 with two and 6 with three, and heldout strata of 12, 15
and 9 respectively. All 12 no-useful groups per split were truly empty and
every positive had one to three useful cards, but the pre-registered exact
12/12/12 balance was not met. No scorer, model or heldout result was opened.
The original inputs/reviews/adjudication stay immutable. An additional public
reserve slate and independent reviews are being prepared keylessly; its
eventual admission must be explicit and must not silently discard the nine
original groups that account for the balancing shortfall. No plan threshold
has been weakened here.

## Caller and regression work

Added and checked a keyless-by-default, approval-fenced public v2 caller at
`scripts/run_fresh_public_source_id_v2.py`. It stays inert because the
authorization identity and model are deliberately pending. A later paid
evaluation needs a separate exact approval receipt and a code-hash-bound
preflight. It never selects a generated answer; it accepts only issued page
IDs. The frozen packet and public PDF hashes are revalidated before key
access. At most one physical call is claimed per group, with no same-group
retry; a transient failure is an explicit failed case and at most two such
cases can continue before the public availability gate becomes impossible.

Read-only independent review caught mismatched approval/request output limits,
an 8,192-token scorer vs 16,384-token caller limit, transient failures that
could not reach the failure-inclusive scorer, response buffering before its
size check, and a spacing sleep that could overrun the total time allowance.
These were corrected. The caller now fixes the request output limit to its
approved limit, caps input at 8,192, streams at most 8,192 response bytes,
reserves worst-case cost for uncertain failed calls, records safe error codes
without response bodies, and checks remaining time before spacing sleeps.
It binds completed response/error receipts to the persisted physical attempt
claims and writes the approval-receipt and claim-manifest hashes to the
completion receipt. Claims live in the ignored workspace `.agent/.verification`
directory rather than environment-selected Temp. This guards accidental
replay in this checkout; copied checkouts still require an operator-wide
approval ledger. No claim has been consumed for a real provider call here.

An offline read of the authored public request bodies measured 96/96 valid
four-page wires; the largest REST body was 6,286 bytes (6,798 including the
caller reserve), below the 8,192-token admission ceiling. This is a
conservative byte-based admission, not a provider token count or live result.

`backend/tests/test_run_fresh_public_source_id_v2.py` now covers approval
limits, matching frozen content, 48 fake responses, one scored HTTP 503 miss
without retry, three consecutive timeout stop, invalid IDs, heldout sealing,
and changed physical claims. The six relevant acquisition, prototype,
review, freeze, scorer and caller modules passed **66/66** keyless tests,
including a simulated oversized HTTP response rejected during streaming.
`python scripts/check_context.py` passed (37 required files, 79 active guides,
1,592 links). An initially mistyped test filename was corrected before the
66-test run. No live model-quality assertion follows from fake transport.

The Knowledge-flow, deployment, testing and changelog guides were corrected
where they described the old `0023` checkpoint or unscored first pilot as
current. The retained runtime is at `0029` with Ask off; the later public
Flash-Lite calibration was scored and failed the no-useful-display gate.

## Remaining gates

The owner approved a prospective balance amendment after the keyless freeze
rejection: preserve and score all 96 original questions; independently review
up to 30 additional public-PDF questions, keep every valid admitted reserve
question including hard or zero-useful cases, and require at least twelve
one/two/three-useful groups per split. All admitted no-useful groups must
abstain, and every displayed cue plus opened original page remains in the
90% denominator. The proportional hit/cardinality gates and at most two
transport misses per split remain; `N - 2` valid responses are needed for a
split of `N`. This was added to the Lane 6 plan and ADR-024 before a new
provider score. The original 96 and both reviewer receipts are immutable;
no group was removed, no label was changed, and no Gemini request was made.

Finish the separate reserve authorship, blind independent review and dispute
adjudication, then adapt and freeze the augmented packet, scorer and caller
keylessly without opening heldout scores. A reserve failure to establish all
three minimum strata rejects the freeze rather than weakening the gate.
The public v2 trial needs
a fresh exact endpoint/model/price/call/token/time/cost approval; this record
provides none. A public pass would still require an immutable matching runtime
policy, independent private original-PDF displayed-card and access tests,
manual spoken accessibility evidence, and the full integrated release gate.
Keep Ask disabled until those gates pass.
