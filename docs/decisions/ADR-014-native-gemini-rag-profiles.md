# ADR-014: Native Gemini profiles for Subject Knowledge and Ask AI

## Status

Accepted 2026-09-20. This supersedes only the initial G5 provider/model
selection in [ADR-012](ADR-012-subject-knowledge-and-rag-boundaries.md). All
Subject authorization, publication, revision, worker, privacy, exact-search and
rollout boundaries in ADR-012 remain in force.

## Context

The operator selected native Gemini for both the RAG answer and embedding roles.
The previously implemented G5 profile used OpenAI-compatible answer and
embedding APIs. Treating the new values as configuration alone would be unsafe:
Gemini embeddings have explicit retrieval task types, a provider-native wire
contract and a normalization requirement when `gemini-embedding-001` emits
fewer than 3,072 dimensions. Matching dimensions do not make the old and new
spaces compatible.

## Decision

The default, disabled RAG profiles are:

| Role | Selected contract |
| --- | --- |
| Answer and support | Native Gemini Developer API, stable `gemini-3.5-flash`, strict structured output, application-owned retries and worker-only credentials. |
| Document/query embeddings | Native Gemini Developer API, stable `gemini-embedding-001`, 1,536 float32 dimensions, cosine search, `RETRIEVAL_DOCUMENT` for stored chunks and `QUESTION_ANSWERING` for queries. |
| Endpoint identity | `https://generativelanguage.googleapis.com`; credentials are excluded from every snapshot and hash. |
| Retrieval | Authorized exact cosine plus PostgreSQL `simple` FTS and bounded RRF remain unchanged. No ANN index or reranker is introduced. |

The embedding adapter batches ordered inputs through the native async SDK,
requests exactly 1,536 output dimensions, validates count/order/finite nonzero
vectors, converts to float32 and L2-normalizes each vector before cosine
persistence or query use. The SDK retry layer is fixed to one attempt; the
existing application loop owns at most three retries, delay, `Retry-After`,
rate admission, timeout and cost accounting.

Gemini 3 text calls omit sampling parameters and carry an explicit thinking
level. The bounded factual RAG answer/support role pins `minimal`; billable
thinking remains included in output usage and cost. This avoids depending on a
provider-default effort level that can change latency and cost independently of
application code.

Embedding-space identity now includes provider, canonical endpoint, model,
operator-controlled space revision, representation/metric/dimensions and both
physical task modes. Existing OpenAI-compatible `shared_input` spaces remain
valid historical spaces. They are never relabeled or mixed with Gemini vectors;
a provider change creates a new space and uses the existing staged reindex and
atomic Subject cutover procedure.

The root template uses the prices reviewed on 2026-09-20: USD 1.50 input and
USD 9.00 output per million tokens for `gemini-3.5-flash`, and USD 0.15 per
million input tokens for `gemini-embedding-001`. These are operator planning
inputs, not a billing ledger. They must be refreshed before live evaluation or
production rollout. Configuration and credentials do not authorize spending.

## Rationale

This implements the operator's selected provider without weakening the RAG
trust boundary. Native task types preserve the provider's retrieval semantics;
explicit normalization makes 1,536-dimensional cosine comparisons well-defined;
and task-mode-aware identity makes incompatible vector mixing impossible. The
selected dimensions remain compatible with the current pgvector schema and
portable exact-search baseline.

## Consequences

- RAG remains disabled by default and the API/browser/email/generation worker do
  not receive RAG credentials.
- Index and answer workers may share a provider account only when the operator
  divides real RPM/TPM budgets across roles and replicas.
- Changing provider/model/task modes requires a new embedding space, reindex,
  corpus evaluation and explicit cutover; it is never an in-place reinterpretation.
- The browser discloses the selected non-secret answer/embedding provider and
  model before an enabled upload or question.
- Paid live checks and actual production enablement remain separately authorized
  rollout gates.

## Related areas

[ADR-012](ADR-012-subject-knowledge-and-rag-boundaries.md),
[configuration](../CONFIGURATION.md), [AI providers](../AI_PROVIDERS.md),
[RAG evaluation](../RAG_EVALUATION.md),
[Subject Knowledge flow](../architecture/SUBJECT-KNOWLEDGE-FLOW.md).

Primary provider references:
[Gemini embeddings](https://ai.google.dev/gemini-api/docs/embeddings),
[Gemini 3.5 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash),
[Gemini thinking](https://ai.google.dev/gemini-api/docs/thinking),
[structured output](https://ai.google.dev/gemini-api/docs/structured-output),
[pricing](https://ai.google.dev/gemini-api/docs/pricing).
