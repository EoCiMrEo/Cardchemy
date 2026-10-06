# Subject Knowledge and source-navigation evaluation

## Current source-navigation release metrics

The released Ask contract is `related_knowledge_navigation_v8`,
`hybrid_source_navigation_v9`, `visual_source_id_v5` and immutable
`literal_subject_admission_v2` at Alembic head `20261002_0033`. It permits at
most one unchanged current-question embedding and one bounded issued-source-ID
judgment, zero generated answers/verifiers and zero automatic retries.
The learner sees 0–3 exact unverified original-PDF reading references.
Fresh installations remain default-off; the retained local installation passed
activation on 2026-10-04. See [ADR-023](../decisions/ADR-023-original-pdf-source-navigation.md),
[ADR-024](../decisions/ADR-024-gemini-source-id-judge.md) and the
[complete local closure](../../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md).

| Gate | Requirement |
| --- | --- |
| Independent private positive hit@3 | At least 10/12, and at least 3/4 in each direct/paraphrase/follow-up form |
| All displayed card usefulness | At least 80% in the complete evaluation; No/Unsure receives zero useful credit |
| Public ordinary no-match | At least 10/12 clear valid empty outcomes; provider failure earns no no-match credit |
| Complete public heldout | Keep all 60 cases; at least 58 valid outcomes, at most 2 failures, at least 40/48 positive hits and 14/16 per form |
| Source and access integrity | Zero fabricated, unauthorized, stale or wrong-page references; hide the whole bundle on any invalid member |
| Physical-call ceiling | At most 1 current-question embedding and 1 source-ID judgment per durable attempt; 0 answer/verifier/retry |

Useful-set/cardinality completeness and second/third useful-page recall are
diagnostics. Never fill three slots with weaker pages. Report candidate recall,
final selected-page usefulness, exact visible quote and opened original page
separately. Zero displayed cards alone cannot establish useful navigation.

The final complete public set had 94/99 useful cards, 48/48 positive hits,
58/60 valid outcomes and 10/12 clear no-match. The independent private set
had 21/24 useful cards (87.5%), 12/12 hits and 4/4 per form. Exposed seed/control
results remain separate: 25/25 useful cards, 11/11 seed hits, positive N12 and
empty restricted U01/U02. All three weak private cards remain in the denominator.
All historical physical failures, consumed claims and unknown charges remain
in the closure ledger; a manually replaced outcome does not erase a failed call.

## Authored corpus and deterministic nonregression

The maintained [v2 corpus](../../backend/tests/fixtures/rag_eval/subject_knowledge_v2.json)
contains only synthetic teaching material. It extends
[v1](https://github.com/EoCiMrEo/Cardchemy/blob/61b34ebda127b712bf22e36f84fb393f1343f707/backend/tests/fixtures/rag_eval/subject_knowledge_v1.json) with direct,
paraphrase, exact-technical-term, similar-concept, multi-page, overlapping-chunk
and bounded follow-up cases. Negative cases cover ambiguous/unsupported input,
empty eligible corpus, conflicting handouts, prompt injection, cross-Subject
and guessed source IDs, ready-but-unpublished Knowledge and invalid support
attached to a real unrelated citation. The
[Lane 0 corpus](../../backend/tests/fixtures/rag_eval/product_quality_lane0_v1.json)
preserves repeated-question and historical false-rejection regression shapes.

PostgreSQL cases exercise current owner/enrollment, selected-document,
publication, readiness, revision/corpus and active embedding-space predicates
inside both candidate SQL paths and on source reads. Revoke access, unpublish,
delete or reindex before/during execution; stale work must not commit, and
historical source bundles must redact on drift. Matching dimensions alone do
not prove embedding-space compatibility. No ANN index or separate reranker
ships without measured need and an accepted architecture change.

| Deterministic baseline | Required result |
| --- | ---: |
| Retrieval recall@5 | 1.00 |
| Mean reciprocal rank | At least 0.80 |
| Cross-Subject/private-source exposure | 0 |
| Duplicate overlap among returned chunks | At most 0.20 |
| Disposable exact-query p95 | At most 2,000 ms |
| Local indexing throughput | At least 1 chunk/second |
| Historical supported-claim/citation and unsupported-abstention checks | 1.00; retained data contracts do not reopen answer execution |

The [metric support](../../backend/tests/support/rag_evaluation.py) and
[PostgreSQL pipeline tests](../../backend/tests/postgres/test_postgres_rag_pipeline.py)
enforce these baselines. Run the full offline suite, guarded PostgreSQL and
RAG-on/off journeys through [testing](../development/TESTING.md). Offline
success is separate from current model quality, provider pricing/availability
and actual user-visible PDF fidelity.

## Source-only displayed-window gate

Freeze current source/model/policy, prompt/schema, source pool, window
construction, independent labels and calibration/holdout split before scoring.
Use source-separated unexposed PDFs and direct/paraphrase/follow-up forms;
exposed calibration and owner-reviewed seeds are regression sets, not an
independent holdout. Preserve every case and all shown-card denominators.
Wire-only input sufficiency, original-page usefulness and cue usefulness are
distinct reviews. Uncertain labels receive no positive credit.

Measure PDF/extraction fidelity, corpus/index coverage, authorized candidate
recall, nearby-page pool, final page/quote selection and authenticated original
PDF drawing separately. A canonical exact span is not proof that the browser
opened the correct authorized page. Missing originals need an explicit extracted
text fallback; exact-SHA/page attachment creates no revision or provider request.
Include wrong-owner/condition, no-source, ambiguous follow-up, embedding outage,
bounded lexical fallback, unavailable-judge/original and revoked-access controls.
Judge failure is distinct from a genuine empty no-match.

The released matching browser displayed 49 captured references across 30
distinct authenticated original pages. Controlled HTTP/auth/job replay validates
component quote/keyboard/drawing behavior; real SQL/PDF guards and disposable
journeys validate current association/access/persistence. It is not a live
persisted paid Ask submission or visual PDF-coordinate highlighting. Spoken
assistive-technology release checks remain separate human evidence.

## Live deployment-model boundary

Routine tests and CI spend no provider quota and load no research model weights.
The maintained opt-in [live RAG smoke](../../backend/tests/integration/test_live_rag_evaluation.py)
uses authored material and at most one Embedding 001 current-question request,
512 input tokens, 30 seconds/request, 45 seconds total and USD 0.001 conservative
admission at a USD 0.20/million input price floor. It makes zero answer/verifier
calls and has zero retries; it is not a private displayed-quality evaluation.
Before any live run, explicitly approve and freeze endpoint/model/current prices,
physical-call/token/time/cost limits, credentials/roles, source transfer and
private artifact custody. A configured key or an old consumed approval grants
no new authority. Unknown failed spend remains unknown; never silently replay.

The earlier answer/local-support, ranker and one-use source-judgment prototypes
are retired. Their failed and partial results remain historical in
[dated logs](../../.agent/logs/README.md), the
[archived tracker](../archive/PRODUCT-QUALITY-REMEDIATION-PLAN.md) and
[ADR-019](../decisions/ADR-019-two-request-local-support-ask.md). Historical 90%
and exact-set gates describe their original runs; they were not retroactively
regraded under the accepted 80% floor. Future evaluations need a fresh current
harness and exact authorization rather than reopening a consumed caller.
