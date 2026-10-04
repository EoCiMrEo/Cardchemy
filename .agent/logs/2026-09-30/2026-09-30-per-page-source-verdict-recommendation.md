# Recommendation after failed 66-case public calibration

Date: 2026-09-30 (America/Chicago). This is an **unapproved prospective
change** to Lane 6/ADR-024. The measured outcome and spending are recorded
in the [calibration result](2026-09-30-augmented-public-calibration-result.md).
No heldout result was opened; Ask remains disabled.

## What the frozen test shows

The source-ID candidate returned valid results for 66/66 public questions.
It found at least one useful page for 53/54 positive questions, and 81/84
displayed cards were useful. However, it displayed a page for one of twelve
no-useful questions and often omitted other useful pages: two-useful exact
selection 11/17, three-useful 4/16 and four-useful overflow 1/2. A useful
page in top three and high displayed precision therefore do **not** establish
the requested 0–3 page behavior. The independent reserve groups had a higher
under-selection rate (12/18) than the original groups (6/48). The false
no-useful display was related to the general subject but lacked the specific
requested quantitative result. This is a relation/condition error, not a
network or parser error.

## Proposed single new candidate

Keep one current-question embedding and **one** bounded source-judge call,
zero answer/verifier calls and zero automatic retries. Replace the direct
0–3-ID selection request with one *independent verdict per issued page ID*:
`useful_reading_page` and `requested_relation_present` booleans for each of
the four candidate pages. The request reminds the judge to preserve entity,
relationship and question conditions, especially reported quantities;
shared topic alone is false. The model returns only issued IDs and boolean
verdicts, never an answer, explanation, quotation, confidence or new citation.
The local parser requires exactly one verdict for every issued ID, rejects
duplicates/foreign IDs/malformed output, and emits at most three IDs where
both booleans are true. If all are false, emit no-match. For four qualifying
pages, choose the first three in deterministic issued order; that cap remains
explicit. The existing authorization/revision/PDF source derivation, source-
only disclosure and per-card labels are unchanged.

This tests a *general* relation-aware decision representation, without adding
a one-off batch-size keyword rule or weakening the 90% useful-card gate.
The 66 failed calibration questions are now development data; do not call
them unseen evidence. The frozen 60 different-PDF heldout groups were never
scored and may be opened **once** only after a separately frozen version of
this candidate passes all calibration gates. Preserve every question and
independent label, the 2/2 overflow rule, no-useful zero-display, per-form/
stratum thresholds, availability/cost guards and all displayed-card counting.
If the new calibration fails, stop; do not tune and rescore the heldout. A
public pass still does not transfer private Knowledge or activate Ask; the
runtime needs a separate immutable version matching the tested wire and
independent private original-PDF display/access gates.

## Approval boundary

Ask the operator before changing Lane 6 or ADR-024, implementing this
candidate, or making a new provider call. An approval to update the plan and
build keyless tests does **not** authorize live Gemini spending. Before any
new public request, provide a fresh exact endpoint/model/price/call/token/
time/cost envelope with a new one-use ledger and source hashes. Keep Ask off
throughout.
