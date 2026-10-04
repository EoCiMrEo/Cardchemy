# Fresh public v2 reserve: four-useful overflow recommendation

Date: 2026-09-30 (America/Chicago). Checkout: `main` at `6c02d6c`; existing
working tree preserved. This is a public-only, keyless diagnostic and a
proposal, **not** a passing quality result or authority for a Gemini call.

## Starting contract

The operator approved keeping all 96 independently reviewed original public
questions and adding at most 30 independently reviewed questions from the
same admitted, split-disjoint public PDFs. Every admitted question remains in
the score. Each split must contain at least twelve groups with exactly one,
two and three useful page-plus-cue cards; all displayed cards count toward
the at-least-90%-useful gate; all no-useful groups must display zero cards;
availability, hit and cardinality thresholds preserve their earlier ratios.
Ask remains disabled, and no new provider pilot has been approved.

## Independent evidence and safe stop

The reserve authored slate has 30 groups and 120 original-PDF candidate
pages, SHA-256 `22c641d3aa59cb7e4d64a25a1f5d263634a51bc5970cad154295d3f92c9234b0`.
The separate blind packet SHA-256 is
`2db0c295aa7cde17b749a206004ae0fb18bb41953cfd28b33efe012305ff1d1f`.
Two independent reviewers completed 120/120 labels each; their raw review
hashes are `3e2459fa4ffd6e8025480131ad525d6fb440d37be97dc9a7043168852b5de9ff`
and `ceeccef7f7d6d8cfcfcb23042a80b952f037ad0b23b01f95c7e0227aa9044357`.
A separate third reviewer resolved exactly five disagreements, raw SHA-256
`e40536b26491aff10190a214524955812654e27d205c01ec564162d8c3a3a3a0`.
Reviewers did not receive the authored mapping, each other's labels, model
output or target balance. No label was altered by the author/root.

After adjudication, reserve useful-card counts were calibration
`{1:1, 2:5, 3:10, 4:2}` and heldout `{2:1, 3:11}`. Combined with **all**
original questions, calibration becomes `{1:19, 2:17, 3:16, 4:2}` and heldout
`{1:12, 2:16, 3:20, 4:0}`. There are still twelve original no-useful groups
per split and no new zero-useful reserve group. The minimum twelve each for
one/two/three is satisfied. The keyless augmented freezer nevertheless
**refused** the two four-useful calibration groups because the current rule
requires at most three independently useful candidates per group. It wrote
no frozen packet, opened no heldout model results and made no provider call.
This is a pre-inference task-definition mismatch, not measured model quality.

## Recommended prospective scoring rule

Preserve the full 126-group slate, every original and reserve label, both
split assignments, all four candidates in each group, and the max-three
**display** contract. Treat the two four-useful groups as an explicit
`overflow_4` stratum. A correct saturated selection there contains **exactly
three distinct issued IDs, all independently page-and-cue useful**; fewer,
more, foreign or duplicate IDs fail that group's cardinality. Require **2/2
overflow groups** correct in calibration. Continue to score their positive
hit, first-card, availability and every displayed-card usefulness normally.
Do not credit an overflow case toward the existing one/two/three-specific
cardinality rates or dilute those rates; retain their exact useful-ID-set
definition and all existing rounded-up thresholds. Keep zero false display
on every no-useful group. The heldout split currently has no overflow groups,
so report that boundary explicitly rather than claiming heldout overflow
generalization. The complete augmented calibration still gates any heldout
opening; all 126 groups remain in the denominators.

The operator approved this capped-three rule after this proposal and before
any provider inference. Lane 6 and ADR-024 now record it. Implement the
overflow rule in a versioned freezer/scorer/caller and test it keylessly
before a new exact paid-call approval. A new approval must state
endpoint, model, price, physical calls, tokens, time and cost and bind the
frozen packet/code SHA. Until the revised contract passes its keyless freeze,
the strict freezer rejection remains the outcome; Ask remains disabled and
Lane 6 stays 3/7.
