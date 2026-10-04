# Source contract audit: partial review progress

Date: 2026-10-01 (America/Chicago). Continuation of the
[approved offline audit](2026-10-01-source-contract-audit-approved.md).
No Gemini/provider call, download, private Knowledge read, heldout opening,
database/environment mutation or Ask activation occurred.

## Verified progress, not a model score

The first two independent reviews of batch 1 are complete and hash-bound.
Each covers 22 groups / 88 candidate pairs and reports visual inspection of
all 53 distinct original pages across four PDFs. Reviewer a classified 33
page/cue pairs useful, while reviewer b classified 30. The deterministic
combiner verified all four sealed review files against their packet and
seal hashes. Wire judgments were preserved after PDF inspection.

For batch 1, the reviewers agree on **85/88** labels separately for wire
input sufficiency, original-page usefulness and cue navigation. Three pairs
disagree in all three dimensions. These are partial inter-reviewer
statistics, not model accuracy, an adjudicated corpus or a release result.
No disagreements have been converted to positives or silently dropped.

Batch 2 reviewer a also completed 88 wire/page/cue judgments and reported
55/55 distinct original pages visually inspected. The other three reviews
are continuing from their own artifacts after intermittent account usage
limits. Existing seals and source packets are preserved. The final audit
must still contain all six reviews and blind adjudication; the current
partial result must not open heldout or any provider pilot.

## Tooling and checks

- The packet/seal helper passed 46 synthetic tests. The combined annotation
  and aggregation suite now passes **57 tests**, including complete-roster
  finalization, old/new label mapping, vote-free dispute packets, immutable
  wire-before-PDF sequence, tamper/partial-state rejection and tri-state
  preservation.
- `scripts/summarize_source_usefulness_contract_v1.py` is a separate
  networkless combiner. Its finalization verifies every original review hash,
  reads only the pinned exposed calibration labels for old/new comparison,
  and never reads historical model outcomes or heldout. It reports prospective
  input-bound feasibility under idealized selection separately from measured
  behavior. Every such report fixes `quality_pass=false` and
  `provider_trial_ready=false`.
- A synthetic feasibility control preserves all 66 groups and demonstrates
  that three missing observable links in a 17-case two-useful stratum leave
  a maximum 14/17 exact selections against 15 required. This is validation of
  arithmetic, not evidence about real annotation outcomes.
- Context validation passed 37 required files, 79 active guides and 1,696
  links before adding this record; whitespace validation passed. Final
  documentation validation will run after the review evidence is complete.

The retained installation is unchanged; Lane 6 remains **3/7**, Ask off.
