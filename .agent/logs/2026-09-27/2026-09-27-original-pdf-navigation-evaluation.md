# Original-PDF navigation evaluation — 2026-09-27

## Scope and starting context

Independent, read-only Lane 6 quality evaluation for the approved source-only Ask navigation design. The evaluation used local original lecture PDFs and the current `source_navigation_v8` selector. No production source, database, volumes, model settings, or runtime flags were changed. No provider requests or DB reads/writes were made. The developer/operator requested independent evaluation without further page-label questions to the operator.

The source-only policy displays up to three unverified related lecture page references. This investigation assessed whether the selected pages and the **exact displayed quote windows** are useful for the question, and whether existing relevance scores can remove filler.

## Private artifacts and method

Private question/page rosters, exact snippets, page renders, source hashes, and card-level grades are confined to the operating-system Temp directory `cardchemy-pdf-holdout-20260927`. This log contains only aggregate counts and artifact fingerprints; it does not reproduce private lecture content or questions.

- A 12-case prospective roster was authored from previously unused original PDF pages before the selector output was inspected: four direct, four paraphrase, and four follow-up questions from 12 distinct pages in three original PDFs. The roster SHA-256 is `24d25d1ed823797081d8f85ec36a82acc5e9a359b669c51391659216b44b336d`.
- Those 12 cases were run through an offline OR/IDF lexical candidate proxy and the actual selector, with local page/neighbor loading. The result SHA-256 is `2a41e9ecba01b10a3e46eda8c12bd08799797987b20a175c7a45fa621915b6fc`. The separately rendered page review SHA-256 is `d0550aefe71b119b62a7a97948881c337e656cbf0227c47a823685dc0660bc01`.
- A separate **development** diagnostic used only the 107 already exposed/published PDF pages and 11 previously operator-reviewed seed question IDs. Its roster/result/strict quote-and-page review SHA-256 values are `33b738fca4f2858cf3189d85ed88b3cb7bc14984bcbce642bc0488eef75c5eda`, `2614d5361cb0c8729f57c1decd9cc4183a0df46700cd882d3ddfa9ddd26c4075`, and `fdafa82de2c481c04f3f25886af8a3f9a0b44374011e56523c5bf3789a770507`. All 18 distinct selected original pages were rendered and visually checked against 33 displayed quote cards. Four partial cards were counted non-useful under the strict measure.
- The prospective 12-case roster/results/review hashes were rechecked unchanged after the development diagnostic. No selector tuning or threshold choice used that prospective set.

## Results

| Measure | Prospective 12-case offline proxy | Exposed 11-case development diagnostic |
|---|---:|---:|
| Source page in top-20 proxy candidates | 12/12 | 11/11 |
| Exact designated source page selected in top three | 10/12 | 10/11 |
| At least one visually useful original page in top three | 11/12 | 11/11 |
| Useful top-ranked page | 9/12 | 6/11 |
| Useful selected cards / all cards | 18/36 | 19/33 |

The prospective set's card grading was for **original pages**, not exact displayed quote windows; its 18/36 must not be presented as quote precision. The exposed development set graded both the exact quote and its original page: 19 useful, four partial, ten weak, for strict all-card usefulness of 57.6%. Useful cards by displayed rank were 6/11, 6/11, and 7/11. Five questions had a non-useful first card and a useful later card.

On the exposed development cards, useful navigation scores had min/median/max **0.726/1.119/1.534**; non-useful (partial or weak) scores had **0.792/1.006/1.542**. Useful topic-hit counts had min/median/max **1/2/4**; non-useful cards had **1/2.5/4**. Both groups reached a topic-hit fraction of 1.0. In eight of the eleven questions, useful and non-useful cards had the same tuple of topic-hit count, query-term count, and title-hit count **within the same question**. Thus a global navigation-score cutoff, topic/title overlap cutoff, top-one-only rule, or score-margin rule is not defensible as a general no-filler policy from these signals. The present scores measure relatedness, not whether the page contains the relation the question asks for.

## Checks, limits, and cleanup

- The original PDFs were visually inspected using rendered pages, not inferred solely from extracted text. The prospective sources were checked for exact and near-duplicate page text against previously exposed pages before evaluation.
- These are offline candidate/selector diagnostics. The OR/IDF proxy is **not** production SQL hybrid retrieval, real query embeddings, authorization, publication state, original-PDF open access, or live browser behavior. No release gate is claimed.
- Prospective labels are independent agent judgments, not operator labels; the exact displayed windows were not independently graded for that set. The exposed development labels use previously operator-reviewed seed sources but new card-level grades are independent agent judgments.
- No new numerical no-filler cutoff was chosen and no second prospective holdout was consumed. The existing 12-case prospective artifacts and source fingerprints remain immutable. A relation-aware sufficiency classifier would require its own separately frozen evaluation before product use.
- A proposed deterministic relation-aware filter was compared with the already rejected v7 implementation. v7 already parsed question roles, owned heading/bullet units, source-attested aliases, explicit relation labels and lexical qualifiers across the same relation families. It passed authored development contracts but failed independent public and supplied-gold private quality (see [v7 implementation](2026-09-27-structural-source-v7-implementation.md)). Extending that grammar using these exposed examples would repeat the failed architecture and violate its stop rule. The proposal was withdrawn before any runtime edit or new holdout measurement. No credible leave-document-out estimate can be claimed from 11 exposed cases and three highly overlapping documents.
- Private OS Temp evaluation files remain for reproducibility. No repository data or volumes were deleted. This evaluation changed only this dated aggregate log and its index entry.
