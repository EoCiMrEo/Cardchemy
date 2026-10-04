# Lane 6 source-selection root-cause review after three calibration stops

Date: 2026-09-28 (America/Chicago). This is a read-only diagnosis and
recommendation, not an approved plan amendment, runtime policy or new model
request. Preserve branch `main` at `6c02d6c`, the shared worktree, retained
`0028` database, root `.env`, three encrypted original PDFs, consumed audit
ledgers and Ask-off state. No provider request, model inference, database
write or new PDF download was made for this review.

## What the receipts establish

- The exposed 11-question retained-course hybrid retrieval found at least
  one useful original PDF page in displayed top three for **11/11**, while
  only **19/33** displayed cards were useful (useful first 9/11). This is
  an exposed diagnostic, not the independent release gate.
- In the 48-group public Mixedbread calibration split, raw pair-logit top
  three contained a useful exact cue and page for **36/36 positive groups**.
  All 72 independently useful original pages in that split also had useful
  exact cues. It does not establish candidate recall for the unscored fresh
  two-PDF release holdout.
- Three separately approved, one-shot public display decisions all stopped
  at calibration with their heldouts unscored: one global threshold, separate
  train-only question-null/card heads, and a four-way groupwise count cap
  plus per-card head. The third's frozen risk sweep had no joint operating
  point: risk `0.0` showed 30/37 useful cards with five no-useful groups
  promoted and 21/36 positive hits; risk `1.75` showed 11/12 useful with
  one false no-useful display and 10/36 hits; risk `4.0` showed 7/7 useful
  and zero false no-useful displays but only 7/36 hits. All resource bounds
  passed. None is a passing selector or evidence for Ask activation.

On these measured pools, the concrete failure is **deciding which candidate
pages to display and when to display none**, rather than an observed absence
of useful candidates. The aggregate receipts do not expose label-stratified
model-score distributions, so they cannot distinguish an intrinsically weak
cached xsmall pair model from inadequate shallow heads, features or
calibration priors. Reusing the exposed 48 calibration groups for another
threshold/head would not be an independent test. Extra query vectors target
candidate generation; these results do not justify them.

## Source representation check without model scoring

To test the suggestion that short cues alone lose decisive context, the
review re-extracted **only the fourteen public CC BY 4.0 PDFs** in the
frozen fixture and counted characters, without printing or retaining text.
All 768 exact candidate cues were found in their page. The 768 candidate
pages cover 159 unique physical pages; median extracted page length is 346
characters, p90 583 and maximum 938. Only 166/768 candidate page instances
exceed 480 characters, and the median cue-to-page character ratio is 1.0.
Within train/calibration only, 257/384 train and 123/192 calibration cues
already equal the entire extracted page. In calibration, this holds for
45/72 useful and 78/120 insufficient candidate pairs. The code did not
read heldout usefulness labels for this check.

Longer page context may help the minority with truncated cues, but simply
feeding a full page to the same scorer is **not established as the repair**:
most public cues already contain all extracted page text. Some cues are
strict subspans even on pages shorter than 480 characters, so the character
cap alone does not explain missing context. A stronger
question-to-source relation/no-match signal and a more deployment-shaped
multi-PDF candidate pool need independent evaluation. The current public
fixture uses four pages from one PDF per question and balanced 0/1/2/3
useful counts; runtime can select from up to 30 chunks/12 pages across PDFs
with unknown no-match prevalence.

## Recommended next decision boundary

Keep Ask strictly source-only: one current-question query embedding at most,
no answer drafting/verification, zero to three individually useful original
PDF links, no weak filler and clarification for unresolved follow-ups. Do
not integrate or retune any of the three failed selectors. Build a **new
source-usefulness evaluation path** that first measures candidate recall on
deployment-shaped, source/document-separated questions, then evaluates a
semantically stronger question-to-page/structured-section source judge with
an explicit no-match decision and independently reviewed same-topic weak
negatives. Model choice (local-only versus one bounded remote source-ranking
request) is an architectural/privacy/cost decision awaiting owner preference;
neither is assumed to work. The existing fresh two-PDF 12-question packet
must remain unscored until a candidate and rule are frozen. Any new public
model run, data acquisition, Gemini egress/indexing or policy change requires
a separate approved scope and, for paid calls, an exact endpoint/model/price/
call/token/time/cost envelope.

Success still requires the unchanged independent original-PDF release gate:
useful page in top three at least 10/12 overall and 3/4 per direct,
paraphrase and follow-up form, at least 90% of **all actually displayed**
pages useful, exposed regression at least 10/11, and zero fabricated,
unauthorized, stale or wrong-page references. No-match, PDF-open,
accessibility and operational gates remain. A failed new holdout would
falsify that candidate, not authorize tuning on heldout. Until these pass,
Ask stays disabled; the independent lecture browse/search and PDF viewer
remain available as the educational navigation path.
