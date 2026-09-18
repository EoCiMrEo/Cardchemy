# Subject Knowledge evaluation corpus

This is the authored, deterministic V1 corpus fixed before embedding, indexing
or ranking is tuned. Its machine-readable cases are in
[`subject_knowledge_v1.json`](../backend/tests/fixtures/rag_eval/subject_knowledge_v1.json).
The fixture is synthetic teaching material. It contains no user data and does
not authorize provider calls. Phase 12 establishes the cases and criteria;
Phases 15–19 must implement and measure them. Until those phases, this guide
does not claim retrieval or answers work.

The corpus deliberately has two Subjects, an eligible astronomy document, an
eligible botany document, an unpublished same-Subject document, and a staged
replacement revision. Each page has an authored stable evidence ID, original
page number and text. Positive questions cover direct facts, paraphrases and
technical terms. Negative questions cover absent facts, tempting unpublished
evidence, cross-Subject evidence and an instruction embedded in source text.
Invalid-citation cases separately test a real but unrelated page, a foreign
Subject page and a replaced revision. These are different failures: a valid
source identifier alone does not establish claim support.

The first exact Subject-filtered retrieval baseline uses top-K=5. For all
authored positive cases, the expected eligible page must appear in the first
five candidates. No unpublished, staged, replaced or foreign-Subject page may
appear for a student query. An answer must cite an eligible active revision and
support every material factual claim from the cited excerpt. All authored
unsupported queries must abstain; all known-invalid citations must be rejected.
The fixture's expected evidence is the review authority, not an invitation to
copy its answer text into a model prompt. A deterministic local embedding stub
may test ordering and fencing, but cannot prove remote semantic quality.

Report numerator/denominator and query IDs for recall@5, forbidden-source
exposure, unsupported-query abstention, invalid-citation rejection and
unsupported-claim rejection. Record exact-search latency on the tested database,
hardware and corpus size, and local token/cost estimates separately from any
provider-reported usage. An empty eligible corpus must yield no evidence and an
abstention. Fail closed on incompatible embedding-space identity; comparing
equal-length vectors from different spaces is not a passing retrieval result.
No threshold may be weakened because a fixture case fails. Phase 19 extends
this corpus before ANN, reranking, rank fusion or source-support tuning.

Live model evaluation, including embedding calls, remains separately gated by
explicit user authorization with endpoint, model, price, call, token, time and
cost limits. See [AI evaluation](AI_EVALUATION.md), [selected profile](decisions/ADR-012-subject-knowledge-and-rag-boundaries.md)
and the [RAG plan](<../Cardchemy-Subject-Scoped RAG Implementation Plan.md>).
