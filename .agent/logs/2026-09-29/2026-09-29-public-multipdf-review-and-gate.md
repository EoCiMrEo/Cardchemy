# Public multi-PDF source-ID review and pre-score gate

Date: 2026-09-29 (America/Chicago). Branch `main` at `6c02d6c`. This is a keyless public-PDF preparation and test record. The retained database remains at `20260927_0028`; the root `.env`, populated volume, private original PDFs and failed local-audit ledgers were preserved. Ask remains disabled. There was no provider request, private Knowledge transfer, indexing or heldout model score.

## Independent source review

The pinned 96-group candidate packet from [its preparation log](2026-09-29-public-multipdf-source-review-packet.md) supplies four exact pages per question from two CC BY 4.0 PDFs, with one newly selected cross-PDF page per group. `scripts/finalize_public_source_id_multipdf.py` now verifies the exact fourteen PDF hashes and physical page text against the pinned v4 public corpus manifest, all original candidate/label identities and two complete, distinct independent review files. Any disagreement, uncertainty or unverified source requires a third adjudication before the 96 labels can be frozen. The script writes only an exclusive OS Temp label file and hash receipt; it never scores a model. Four synthetic contract tests and the adjacent navigation/source-judge tests passed (36 total at the current focused run). The script cannot prove the semantic accuracy or independence of a reviewer; those remain documented judgments.

Two independent agents were assigned to read only `new-page-review.json` and original public PDFs, without access to each other's labels or model output. A task-path correction was sent promptly: the packet uses `cardchemy-reading-usefulness-public-v4-20260928`, whose manifest SHA-256 is `9978ad6fd2ca50f20d20ed8231e7434e2d8f91bbdc21b61e5e44ddcb76f0eae4`, rather than the earlier v3 acquisition folder. Both reviewers rechecked all 96 file/page/text/cue identities against v4. Reviewer A marked 15 pages and 13 exact cues useful; reviewer B marked 14 pages and 14 exact cues useful. Five group judgments differ; a third reviewer is assigned to those five without seeing the first two outputs. **No labels have yet been frozen or used to score a model.**

## Pre-registered public scorer

`scripts/evaluate_source_id_multipdf.py` prepares calibration-only model-facing requests from the pinned blind packet and frozen label/receipt hashes. The wire contains the current question plus exact page/cue and opaque IDs; it strips prior questions, locally derived antecedents, file names, document hashes and reviewer labels. An unresolved local referent yields a clarification without a rank call. The offline scorer accepts only one canonical ID-array response per callable group, counts malformed output as a failure, writes a one-shot score claim, and allows heldout preparation only after a passing calibration receipt with the same prompt/query/contract/harness/label fingerprint. It does not import provider credentials or call a network service. Its keyless synthetic tests cover wire egress, a passing perfect selector, false no-useful display and invalid output.

Before seeing any model response, the pass criteria for this changed-prevalence, two-PDF pilot are fixed as follows. Let `P` be groups with at least one independently reviewed page **and its displayed exact cue** useful; `N` be no-useful groups. A result with no displayed cards cannot pass the displayed-card metric.

| Stage | Frozen requirements |
|---|---|
| Both | Zero invalid outputs; zero displayed cards in every `N`; valid empty selections in every `N`; at least 90% of **all displayed** cards have both a useful exact cue and original page. |
| Calibration | Useful hit@3 at least `max(30, ceil(5P/6))`; per question form useful hit at least `ceil(5P_form/6)`. |
| Heldout, only after calibration pass | Useful hit@3 at least `max(33, ceil(11P/12))`; useful first at least `max(31, ceil(31P/36))`; at least 60 useful cue-plus-page cards displayed; correct 0–3 cardinality for at least `ceil(5P/6)` positive groups and at least `ceil(5N_bucket/6)` within every nonempty positive availability bucket; per question form useful hit at least `max(10, ceil(5P_form/6))`. |

These ratios retain or tighten the earlier 36-positive/12-negative public thresholds when a newly reviewed cross-PDF page turns an originally no-useful group positive. Correct cardinality is `min(number of useful pages, 3)`, because output is capped at three. All actual numerators and denominators must be reported. This gate is a **public pilot gate**, not Lane 6 release: fresh private original-PDF holdout, 90% usefulness among every displayed original page, authorization/no-match/browser/accessibility and operational checks remain separate.

## Open boundaries

The one-shot paid caller and fake transport checks are still being prepared. The [proposed exact cost envelope](2026-09-29-public-source-id-live-envelope-draft.md) remains a draft, **not user permission** for provider calls. A third review, freeze hashes, audited caller and explicit paid authorization are required before calibration execution. If public calibration fails, its heldout stays unscored and no runtime/Ask activation follows. The two-PDF public pool still does not prove the application's possible twelve-page pool across more documents. Lane 6 remains 3/7.
