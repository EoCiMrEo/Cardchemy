# ADR-021: Related published Knowledge for unverified Ask jobs

## Status

Accepted by the operator on 2026-09-25 for product-quality Lane 6. The
retained local installation received schema revision `20260925_0021` and
matching API, worker and frontend images on 2026-09-26. The full Lane 6 Ask
quality gate remains open. This extends the private source-read boundary in
[ADR-012](ADR-012-subject-knowledge-and-rag-boundaries.md) and the two-request,
fail-closed answer policy in
[ADR-019](ADR-019-two-request-local-support-ask.md); it does not supersede their
verified-answer, authorization or provider-request rules.
The operator accepted [ADR-022](ADR-022-related-knowledge-primary-ask.md)
on 2026-09-26 as the only new-job source-only path. ADR-022 supersedes this
record's fallback-only presentation and two-excerpt cap. This record describes
the historical failed/abstained-job fallback and its source-read boundaries
until the approved development reset; existing job snapshots retain their
original behavior. The source-only release fence remains closed.

## Context

The owner reviewed six exact published-Knowledge quote/question/answer pairs.
The staged source-unit contract can bind all six, but the current local verifier
rejects all six positive claims. A wrong-claim control also received a high NLI
entailment score, so simply lowering a threshold would weaken the answer gate.
Some current Ask jobs instead fail at the answer provider. A relevant source
passage can still help the learner inspect the course material when the system
cannot safely verify an answer. Such a passage must never be presented as a
supported answer or a claim citation.

## Decision

- After the existing authorized exact-v1 retrieval, the worker may select at
  most two deterministic, contiguous windows from the retrieved top five,
  using distinct document pages. Each exact source slice is at most 480
  characters. Question-term overlap ranks windows only for browsing; it does
  not establish entailment, relevance or answer correctness. This selection
  makes no new provider request and does not change the one-embedding,
  one-answer maximum or the no-automatic-retry rule.
- Store job-owned source identifiers, current content/index revision and
  embedding-space context, excerpt order, attempt number, expiry and character
  offsets, rather than another copy of private quote text. The database limits
  count and length, ties records to the job and same-Subject chunk, and rejects
  insertion outside the current eligible published corpus after retrieval. A new manual
  attempt deletes its previous references; cancellation and a supported answer
  also clear them. Thread, Subject and account deletion cascade them.
- A job response may contain `related_excerpts` only when its terminal status
  is failed or completed with an abstained assistant message. It is a separate
  response field, not `RagMessage.sources` or a verified claim. Each item has
  server-derived document title, page, optional section and the exact current
  quote. A failed query embedding or retrieval with no selected source yields
  an empty list. The browser labels the group **Related published Knowledge**
  and explicitly says the excerpts have not been verified as an answer.
- Every read requires the requesting principal's own thread/job and current
  Subject access. The service rereads all selected chunks under the same
  owner/enrollment, publication, active revision, corpus and embedding-space
  predicates used for authorized Knowledge. It returns an empty bundle if any
  reference, offset, scope, expiry or current source fails. It does not return
  a partial bundle or let a historical quote survive unpublish, replacement,
  deletion or access loss.
- An excerpt expires no later than its question message. Bounded retention
  cleanup of expired question messages cascades the job and references;
  account export includes only the
  requester's own reference metadata and offsets, never a duplicate quote or
  another user's conversation. Canonical Knowledge remains governed by its
  independent retention and deletion policy. Logs, diagnostics and telemetry
  exclude source text.

## Rationale

An exact, source-labeled passage lets a user inspect relevant published
material while the answer gate remains strict. Job-level presentation also
works when a provider or transport failure produces no assistant message.
Keeping source references and offsets instead of copied text supports current
authorization and redaction. The browser's separate label prevents a related
passage from acquiring the visual or API meaning of a verified citation.

## Consequences and release gate

- Related excerpts are a browsing aid, not an answer, positive support result,
  retrieval-quality proof or reason to mark the Ask lane complete. No support
  threshold, answer policy, retrieval policy or provider-call budget changes.
- Verify deterministic bounds and exact slices; no extra provider calls;
  same-Subject ownership, enrollment, publication, revision, space and
  expiry across worker write and API read; full-bundle redaction; retry,
  cancellation, supported-answer cleanup, account export/deletion and
  retention; disposable PostgreSQL migration and constraints; and accessible
  failed/abstained, hidden, mobile and escaped-text browser states.
- The local installation migration, matching-image recreation, health and
  automated boundaries passed on 2026-09-26. Completing Lane 6 still requires
  a representative reviewed Ask corpus, safe negative controls, a measured
  retrieval/support decision and the integration gate. Local deployment and
  automated checks do not establish spoken assistive-technology behavior or
  general answer quality.

## Related areas

[Knowledge flow](../architecture/SUBJECT-KNOWLEDGE-FLOW.md),
[privacy guide](../security/PRIVACY.md),
[accessibility checks](../ui/ACCESSIBILITY.md),
[RAG evaluation](../ai/RAG_EVALUATION.md),
[answer service](../../backend/app/services/rag_answers.py),
[source selector](../../backend/app/ai/related_evidence.py),
[answer worker](../../backend/app/workers/rag_answer.py),
[Ask panel](../../frontend/src/components/rag/AskAiPanel.tsx),
[current state](../development/CURRENT-STATE.md),
[source-first successor](ADR-022-related-knowledge-primary-ask.md).
