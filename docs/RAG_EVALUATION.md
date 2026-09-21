# Subject Knowledge evaluation corpus

The current authored, deterministic evaluation corpus is
[`subject_knowledge_v2.json`](../backend/tests/fixtures/rag_eval/subject_knowledge_v2.json).
It extends the original Phase 12
[`subject_knowledge_v1.json`](../backend/tests/fixtures/rag_eval/subject_knowledge_v1.json)
before retrieval, prompt, ANN or reranker tuning. Both fixtures contain only
synthetic teaching material: no user lecture/chat content, credentials or paid
provider authorization.

## Phase 19 cases

The v2 corpus includes direct facts, semantic paraphrases, exact technical
terms, similar concepts across lectures, multi-page topics, overlapping chunks
and a bounded follow-up. Negative cases cover ambiguous or unsupported
questions, an empty eligible corpus, conflicting handouts, lecture/chat prompt
injection, cross-Subject and guessed source IDs, and ready-but-unpublished
Knowledge. Validation cases use a real but unrelated citation and an
unsupported claim attached to a valid source ID, because identifier membership
alone does not establish relevance or semantic support.

Lifecycle cases cover access revocation before and during work, corpus and
embedding-space mismatch, unpublish/delete/reindex while queued or running,
and history-source redaction after unpublish/delete. The PostgreSQL suites
exercise those states against current owner/enrollment, publication, active
revision, corpus and embedding-space predicates; source reads reauthorize the
same scope instead of trusting a stored citation.

## Reviewed thresholds

The checked-in policy fixes these gates. They are not weakened when a case
fails:

| Measurement | Required result |
| --- | ---: |
| Retrieval recall at top 5 | 1.00 |
| Mean reciprocal rank | at least 0.80 |
| Feasible-answer claim support | 1.00 |
| Unsupported-query abstention | 1.00 |
| Invalid-citation rejection | 1.00 |
| Cross-Subject/private-source exposure | 0 |
| Duplicate-overlap rate among returned chunks | at most 0.20 |
| Disposable exact-query p95 | at most 2,000 ms |
| Local indexing throughput | at least 1 chunk/second |
| Bounded history context | at most 8 messages |
| Physical provider stages per answered question | at most 3 |

The evaluator reports recall@K, reciprocal rank, support, abstention, citation
validity, forbidden-source exposure, overlap diversity, retrieval latency,
index throughput, history consumption and provider-stage bounds. Token and cost
ceilings are separately enforced by the snapshotted answer and embedding
profiles; local estimates and provider receipts are not a complete billing
ledger.

## Retrieval and support result

`hybrid_exact_v1` uses exact Subject-filtered cosine search and PostgreSQL
`simple` FTS, each capped at 20 candidates. It fuses with reciprocal-rank
fusion `k=60`, returns at most 5 chunks, requires vector similarity at least
0.5, deduplicates same-page term overlap at 0.8, and caps retained context at
8,192 estimated tokens. RRF is a rank score, not a probability or confidence.

The current disposable PostgreSQL run evaluated seven feasible direct,
paraphrase, technical, multi-page, overlap, injection and cross-lecture queries
against actual pgvector cosine plus FTS. All reviewed gates passed: recall was
1.00, MRR met the 0.80 floor, forbidden-source exposure was zero, overlap stayed
within 0.20, exact-query p95 stayed below 2 seconds and indexing exceeded one
chunk/second. An unrelated query returned empty evidence. The complete Phase 20
service run passed 81 PostgreSQL tests, with 3 intentionally gated skips, and also
completed head/drift, downgrade-to-base and re-upgrade-to-head checks.

The answer contract permits only one-to-five ordered claims, each linked to one
retrieved chunk and an exact contiguous quote. A separate structured support
pass receives the original question, candidate claims and all retrieved
context, and must affirm quote entailment, question relevance and absence of
contradiction for every claim. Unknown, duplicate, fabricated, stale,
irrelevant or unsupported citations fail closed. Empty retrieval, ambiguity,
conflicting evidence, model abstention or support rejection produces the fixed
server-issued abstention without citations.

No HNSW or IVFFlat index ships, so filtered ANN recall and iterative-scan tuning
are explicitly not applicable; the exact query is the baseline, not a silently
missing comparison. The evidence did not justify changing top-K, RRF,
similarity, shared page-aware chunking or the 8,192-token context cap. It also
did not justify a reranker. Any future ANN, reranker or RAG-specific chunk
version needs separately reviewed corpus-scale recall/latency evidence and must
preserve the flashcard regression baseline.

## Live deployment-model boundary

Normal tests make no remote calls. The guarded live harness in
[`test_live_rag_evaluation.py`](../backend/tests/integration/test_live_rag_evaluation.py)
requires both `RUN_LIVE_RAG_TESTS=1` and
`RAG_LIVE_EVAL_AUTHORIZED=I_ACCEPT_PROVIDER_CHARGES`, the official reviewed
endpoint, pinned answer/embedding snapshots, explicit quota buckets and current
price floors. It permits one query embedding, one answer call and one support
call; retries are zero, concurrency is one, total input is capped at 12,000
tokens, answer output at 1,024 tokens, wall time at 60 seconds and estimated
cost at USD 0.04. It accepts only native Gemini with the stable
`gemini-3.5-flash` answer model and `gemini-embedding-001` at 1,536 dimensions;
reported thinking tokens count toward the output bound and cost.

On 2026-09-20 the operator explicitly authorized the bounded live evaluation.
The final current-code run passed once in 27.25 seconds (`1 passed, 10
deselected`) using the pinned native Gemini answer and embedding profiles. Two
earlier bounded diagnostic runs made no automatic retry: one exposed a
truncated 512-token answer and one exposed a 30-second timeout under the
provider-default thinking effort. The final harness uses a 1,024-token answer
ceiling, a 60-second wall limit and explicit `minimal` thinking. This proves the
guarded sample at that time; it does not establish future availability, price,
provider billing completeness or quality for every production Subject. See
[AI evaluation](AI_EVALUATION.md), [testing](TESTING.md), the
[selected profile](decisions/ADR-014-native-gemini-rag-profiles.md)
and the [RAG plan](<../Cardchemy-Subject-Scoped RAG Implementation Plan.md>).
