# Lane 6 current hybrid source display: original-PDF review

## Scope and preservation

This independent review graded the frozen, read-only current v3/v9 hybrid
source-navigation diagnostic on the eleven previously reviewed questions in
the published local Subject. It did not call an AI provider, change the
database, index a document, alter Ask policy, or open an Ask job. The retained
volume, three attached original PDFs, root `.env`, backups, and disabled Ask
admission were preserved. This is an **exposed regression set**, not a new
source-independent holdout or release approval.

## Frozen inputs and method

- Diagnostic observation SHA-256:
  `eabecc3a82c4e7fefbcf84467d5c2ca45cb933e65cd12649f6249a9e5896e6fd`.
  It used eleven precomputed current-question embeddings from the separately
  approved, one-shot provider envelope. The reviewer did not run that call.
- Private label packet SHA-256:
  `737fdb6f206333d7b741680470ba49c46c3d9fe3bb37f3c1cc96beee79007211`.
  It remains only under operating-system Temp alongside the private
  observations; no question, excerpt, source identity, or PDF content was
  copied into this log.
- Reviewed all 33 exact displayed excerpts against rendered physical pages
  from the original local lecture PDFs. A local PDF text cross-check mapped
  every selected excerpt/page pair to exactly one original file at the cited
  page, with full excerpt-token overlap and no ambiguous next-best file.
  The diagnostic independently reported 33/33 exact current source slices
  and 33/33 current original-PDF manifests.
- Each card received separate binary labels for whether its displayed excerpt
  contains the requested question relation/condition and whether the opened
  original page is useful for that question. A mere same-topic mention was
  graded insufficient. The reviewer had seen the earlier lexical **aggregate**
  but not its per-card labels. The same reviewer graded both the excerpt and
  page; this is independent of the diagnostic implementation, not a second
  human adjudication.

## Result

| Measure | Current hybrid v3/v9 | Earlier lexical fallback on the same exposed roster |
| --- | ---: | ---: |
| Useful original page somewhere in displayed top three | 11/11 | 11/11 |
| Strictly sufficient displayed excerpt somewhere in top three | 11/11 | not separately recorded |
| Useful first page | 9/11 | 6/11 |
| Strict useful pages/excerpts among all displayed cards | 19/33 | 17/33 |
| Direct useful-page hit@3 | 6/6 | not separately reported |
| Paraphrase useful-page hit@3 | 4/4 | not separately reported |
| Follow-up useful-page hit@3 | 1/1 | 1/1 |

Two first cards still led to a related page without the specific requested
relation. Fourteen of 33 displayed cards failed the strict relation/condition
label despite being exact citations. This supports a modest ordering gain
from current hybrid retrieval on the exposed corpus; it does not establish
robust usefulness for new sources or justify treating all three cards as
verified evidence.

## Limits and release status

The PDF was rendered from the operator's local original files for review; the
authenticated in-app PDF range route was **not** exercised here. The eleven
questions and source pages have been exposed during development, and there is
only one follow-up case. A fresh published, source-separated direct/paraphrase/
follow-up holdout and no-match/access controls remain necessary. The
diagnostic recorded `quality_labels_independent=false` and
`release_gate_passed=false` before this separate review; this log supplies a
label packet, not a policy switch or an automated release-gate pass. Keep
`RAG_ASK_ENABLED=false` until the approved holdout, product, accessibility,
and security gates actually pass.
