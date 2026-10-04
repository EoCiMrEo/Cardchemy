# Lane 6 source judge options after the groupwise calibration stop

Date: 2026-09-28 (America/Chicago). This is a recommendation for an owner
decision, not an approved change to the plan, ADR, runtime or AI budget.
No provider call, local model inference, fresh-holdout scoring, database write
or Knowledge indexing was performed for this review.

## Observed boundary

The measured exposed-course hybrid pool contained a useful original page in
top three for 11/11 questions, but only 19/33 displayed pages were useful.
The public calibration pool's raw pair-score top three contained a useful
cue and page for 36/36 positive questions. Three separate frozen Mixedbread
display selectors then failed their calibration gates, including the latest
groupwise count/per-page selector. These facts locate the observed failure in
**which candidate pages to display and when to display none** on the measured
pools. They do not prove recall on the unscored fresh two-PDF holdout or prove
that the cached model itself is the only cause.

The v3 source selector in `backend/app/ai/source_navigation.py` still returns
up to three pages by local token overlap/fusion rank whenever candidates
exist; the worker commits these only after current authorization, revision,
page and exact-offset checks. Replacing this selection rule must preserve the
same authoritative checks and a versioned policy snapshot. Current
`ADR-023` permits one query embedding and **zero answer-model/verifier calls**;
any remote source judge requires an explicit amendment and operator approval.

## Distinct next options

1. **Stronger local source judge.** Evaluate a materially different
   question-to-page model or fine-tuned relation signal on public original-PDF
   pages, including same-topic weak pages and no-useful questions. Keep all
   Knowledge local. A model that exceeds the self-hosted CPU/RAM/latency
   budget, or fails calibration, cannot be integrated. Repeating another
   threshold/head on the three consumed Mixedbread calibrations would not be
   independent evidence.
2. **Remote source-ID judge.** Test a structured-output Gemini call that sees
   only the current question and bounded, already authorized candidate page
   text, and returns zero to three candidate IDs. It would not draft a student
   answer. The server would ignore every unrecognized ID, derive all page
   links and exact cues from current local source records, and recheck the
   complete bundle at commit and read. This adds a **second paid remote
   request** after the one query embedding, sends published lecture excerpts
   to Google, changes provider disclosure/cost accounting and needs an
   explicit source-only policy/ADR amendment. A public-PDF-only trial should
   precede any private Knowledge transfer. Model judgments are not verified
   evidence; the result remains labeled unverified related reading.
3. **Keep Ask closed while browse/search remains available.** This is the
   safe operational state if neither automatic judge reaches the independent
   original-PDF usefulness gate or if the operator does not want the extra
   source transfer/cost.

Google documents structured JSON output for classification and lists
`gemini-3.6-flash` as supporting it. The official paid Standard list price
checked on this date is USD 0.75 per million input tokens and USD 3.75 per
million output/thinking tokens through 2026-12-31, with higher stated prices
after that date. These figures are **research, not authorization or a cost
envelope**: [model capability](https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash),
[structured outputs](https://ai.google.dev/gemini-api/docs/structured-output),
[pricing](https://ai.google.dev/gemini-api/docs/pricing). Current model
availability, prices and terms must be verified again before a paid run.

## Evaluation sequence if an option is approved

- Measure candidate recall separately on deployment-shaped, document-separated
  questions. If useful pages are absent from candidates, repair retrieval
  before judging pages; do not add query vectors unless independent recall
  evidence warrants them.
- Use the same bounded candidate IDs/pages for a new public calibration and
  separately frozen holdout, including no-useful and same-topic weak pages.
  Calibrate 0-3 selection without tuning on heldout. Count every displayed
  original page, not only whether one useful page appears in top three.
- Only after a public gate passes, score the already-frozen fresh two-PDF
  twelve-question release holdout once, plus the exposed retained-course
  regression. Require useful-page hit@3 at least 10/12 and at least 3/4 in
  each direct/paraphrase/follow-up group, at least 90% useful among **all**
  displayed pages, exposed hit at least 10/11, no unsupported no-match
  promotion, and zero fabricated/stale/cross-subject/wrong-page references.
- Keep Ask off until PDF open, authorization, privacy, request/cost,
  accessibility and operational release checks pass. A failed public gate
  does not authorize another tuning loop on the same calibration set.

The operator has been asked which direction to take. Until that preference
arrives, no plan/ADR amendment, new selector, local model audit, remote call
or runtime activation is authorized by this record.
