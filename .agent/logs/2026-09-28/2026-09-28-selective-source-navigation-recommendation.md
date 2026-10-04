# Lane 6 selective source-navigation recommendation after calibration stop

Date: 2026-09-28 (America/Chicago). Status: **recommendation only**. Branch
`main` at `6c02d6c`; the large existing working tree, retained `0028`
database, root `.env`, three attached original PDFs and backups were
preserved. Ask remains disabled. This record does not amend the plan or
ADR-023, authorize a second model run, or change application behavior.

## What the one-shot result establishes

The approved public Mixedbread audit passed its runtime bounds but returned
`calibration_rejected_no_heldout`. The fixed one-shot ledger is consumed;
heldout was never scored. The raw pair-logit top three contained at least one
independently useful page/cue in all 36 positive calibration groups and 68 of
72 useful candidates in those slots. The specific train-only pointwise
logistic classifier plus **one global display threshold** could not find a
calibration rule with all of zero displays in twelve no-useful groups, at
least 90% useful displayed cards, and useful hit@3 in at least 30/36 positive
groups. The output's zero displayed cards is a rejection sentinel, not an
observed deployed behavior. The aggregate does not identify a failing
threshold frontier or prove heldout model quality. It is evidence against
that decision rule, not proof that ranking or every model is wrong.

The current published v3/v9 selector checks a bounded hybrid/neighbor pool
and then fills up to three distinct pages when an exact window shares a query
term. On eleven exposed, published, independently graded questions, at least
one useful page was displayed for 11/11, but only 19/33 displayed cards were
useful. Returning all three pages is structurally incompatible with the
owner's at-least-90%-useful-per-card target when a question has fewer than
three useful pages. On the public calibration positive groups, even perfect
top-three recall with all three shown would cap useful precision at 72/108,
or 66.7%. The task is **selective display and a true no-match decision** in
addition to candidate recall and ranking.

## Proposed architecture and scope for approval

Keep Ask source-only: at most one current-question query embedding, no answer
model, answer verifier, drafted answer or remote reranker. Keep the current
authorized Subject/publication/revision/embedding-space SQL retrieval and
bounded ±2-page inspection. For each distinct current PDF page, choose the
best exact visible cue under the existing 480-character limit. Add two
separate local decisions after candidate collection:

1. A **question-level null/any-useful decision** evaluates whether the
   inspected pool merits any navigation card. Unknown, unresolved follow-up,
   contradictory source, stale access or scorer failure must not be reported
   as a confident match; distinguish unavailable from genuine no-match.
2. A **per-card page-and-cue qualification** evaluates each exact page/cue
   pair against the question relation and conditions. Rank only qualified
   distinct pages and display zero to three. Show two or three when two or
   three individually qualify; never add a related but weak page to fill a
   slot. Retain the visible `related published Knowledge, unverified` label
   and original-PDF page link. A single useful page may produce one card.

The first experimental implementation may reuse the already hash-verified
public Mixedbread pair scorer, but its decision architecture must be new and
pre-registered: a small fixed train-only binary null classifier on pooled
score/lexical/relation features, and a separate fixed train-only per-card
classifier. Calibration may choose at most one null threshold and one card
threshold using a frozen deterministic search. No other data-dependent
features, policy variants, model weights or threshold changes after the
heldout is opened. This is a **new proposal after a failed candidate**, not a
claim that the consumed approval permits tuning it. The previously frozen
public heldout remains unopened; train/calibration aggregates are exposed,
so that split is development data for this second candidate. The later
source-separated original-PDF release set remains the independent gate.

## Proposed one-shot offline experiment

Only after explicit operator approval and plan/ADR amendment, implement the
two decisions in a separate offline harness using the existing 14 public
CC BY 4.0 PDFs, 192 independently reviewed groups and pinned Mixedbread
bundle. Before any score, freeze the new feature list, null/card training
and threshold algorithm, exact fixture, harness, Docker image and scripts;
write the freeze digest outside the attempt folder. Use a **new** fixed
one-shot ledger; never clear or reuse the consumed prior ledger. Train on
96 groups, choose the two thresholds on the 48 calibration groups under the
same zero-no-useful, at-least-90%-combined-cue/page-card and at-least-30/36
positive-hit guard, then open the still-blind 48 heldout groups once only if
calibration passes. Keep the prior stricter public heldout gate unchanged:
at least 33/36 positive hit@3, at least 10/12 per question form, 31/36
useful first, at least 90% of **all displayed cue-plus-page cards** useful,
60/72 available useful cards shown, correct displayed count in at least
10/12 of each one/two/three-useful stratum, and zero displays in all twelve
no-useful groups. Report the raw pool, null and card confusion counts,
original-page-only versus exact-cue usefulness, displayed numerator and
denominator, no-match and first-card errors, and resource limits. Unknown or
failed controls count as failure. A calibration failure stops before heldout;
a heldout failure stops the candidate without retry or private rescue.

No additional download or provider request is proposed for that public
audit. Run one time in a disposable networkless, credential-free container
with the cached immutable image/model, no retained database or private mounts,
at most four CPUs, 2 GiB RAM, 20 seconds startup, p95 five seconds per 30
windows, 256 pair tokens without silent truncation and 600 seconds total.
The public pass would authorize only the next separately reviewed development
assessment. It would **not** make a runtime policy live or satisfy the owner
approved release target of at least 90% useful **original PDF pages** across
all displayed cards on a fresh published, document-separated holdout.

## Separate release work after a public pass

The fresh two-PDF, twelve-question original-PDF source packet is reviewed but
not published/indexed or scored. It needs a separately authorized bounded
document and query embedding envelope, real authorized hybrid retrieval,
actual exact displayed cues, enrolled PDF-open behavior and independent
grading before release. Require useful-page hit@3 of at least 10/12 overall
and 3/4 in each direct/paraphrase/follow-up group, exposed regression at
least 10/11, at least 90% useful original pages among **all shown cards**,
and explicit no-match, access, publication, revision, outage and malformed
embedding controls. Fabricated or wrong-page/private/stale references,
answer assertions and extra remote calls remain zero tolerance. Complete
spoken assistive-technology and operational release evidence as separate
gates. Ask stays disabled until all gates pass.

## Alternatives rejected by current evidence

- Showing all three current hybrid pages gave only 19/33 useful displayed
  cards on the exposed source set.
- Showing only the current first page gave 9/11 useful first pages on that
  exposed set, below the 90% target and without fresh no-match evidence.
- Replaying the global-threshold Mixedbread run would violate its consumed
  one-shot approval and would not make its calibration failure disappear.
- Lowering the public gate or claiming unverified related pages as verified
  answers would not meet the owner-approved release contract.

No plan checkbox should be marked complete on this proposal alone.
