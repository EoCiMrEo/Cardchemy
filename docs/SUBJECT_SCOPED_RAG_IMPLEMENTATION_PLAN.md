# Cardchemy — Subject-Scoped RAG Implementation Plan

Revision: 2026-09-17 — incorporates all twelve approved review recommendations and all three approved V1 decisions.

## Objective

Add Subject-scoped RAG **without regressing the existing flashcard-generation pipeline**.

**Subject = Knowledge Boundary.** Authorize every retrieval and apply the authorized `subject_id` inside every vector and lexical SQL query.

This is an implementation plan, not evidence of completed implementation. All implementation/acceptance checkboxes remain unchecked.

## Baseline and approved V1 decisions

The reviewed baseline is [`EoCiMrEo/Cardchemy` main at `a9461b7`](https://github.com/EoCiMrEo/Cardchemy/commit/a9461b712e043def32228b3b111474b1fe1ec383), after the Phase 9 merge. Alembic head is `20260916_0007`. Recheck the current head before implementation; append migrations rather than rewriting existing revisions.

Existing generation uses encrypted temporary PDF sources, bounded PDF/OCR extraction, page-aware logical chunks, grounded generation and lease-fenced finalization. Phase 4 intentionally removed earlier pgvector/RAG claims; this plan introduces a new implementation on the current architecture. Phase 10 privacy/operations work remains unfinished and must be coordinated with RAG.

| Decision | Approved V1 behavior |
|---|---|
| Ingestion | Capture knowledge from the existing `Generate Set → Upload PDF` flow only. No separate Knowledge-only upload in V1. Current `AI_PROVIDER_ENABLED` generation-admission behavior remains applicable. |
| Document removal and citations | Ordinary removal immediately excludes a document from retrieval. Historical answers and citation provenance remain visible, labelled `Source removed`. Reindexing also preserves historical citations. Explicit hard deletion and retention cleanup follow the privacy policy below. |
| Embedding configuration | Keep domain contracts provider-neutral. Select and pin one deployment-wide provider/model/version and `EMBEDDING_DIMENSIONS` before Phase 15 implementation and before any dimensioned vector DDL. This revision does not select a provider, model or numeric dimension. |

## Execution order and blocking gates

Keep Phases 12–21, with the following dependencies:

1. Phase 12 foundation **and early privacy/deletion design gate**.
2. Phase 13 knowledge schema → Phase 14 capture → Phase 15 indexing.
3. Phase 16 retrieval **and deterministic retrieval/security evaluation gate**.
4. Phase 17 asynchronous Ask AI backend → Phase 18 Subject frontend.
5. Phase 19 complete RAG evaluation → Phase 20 regression/security/CI → Phase 21 operational rollout.

Tests and operational documentation accompany their owning phase; Phases 20–21 consolidate the final evidence. Phase 17 must not depend on retrieval that has failed or skipped the Phase 16 gate.

---

# Phase 12 — RAG Foundation & pgvector Readiness

### Preserve existing architecture and flag semantics

* [ ] Add `RAG_ENABLED=false` to the sole supported root `.env.example` and configuration reference; keep it separate from `AI_PROVIDER_ENABLED`.
* [ ] With RAG disabled, preserve the current PDF-generation path and temporary-source cleanup. **Do not persist extracted lecture pages/chunks**, enqueue new RAG work, claim indexing/answer jobs, or expose usable RAG endpoints/UI.
* [ ] Disabling RAG is a kill switch, not deletion of previously stored knowledge; authorized retention/deletion maintenance remains possible.
* [ ] Define flag handling for in-flight work: fence knowledge/answer commits and stop new RAG provider calls after disablement is observed; do not disrupt successful flashcard finalization.
* [ ] Keep AI/embedding credentials worker-only; FastAPI and frontend receive only required non-secret configuration.
* [ ] Reuse `SubjectService.check_subject_access()`, PDF/OCR/chunking/grounding primitives and current PostgreSQL-backed durable job patterns.
* [ ] Keep PostgreSQL 16; do not introduce Redis, Celery, Pinecone, Qdrant or another infrastructure stack for V1.

### Early privacy/deletion design gate — before Phase 13 schema is finalized

Persisting extracted lecture text changes the current ephemeral-text behavior. Resolve this gate with Phase 10 work before choosing irreversible deletion/FK behavior.

* [ ] Document what is stored: canonical pages, versioned chunks/vectors, conversation messages and citation snapshots; raw PDFs remain encrypted and temporary.
* [ ] Define configurable retention and cleanup rules for knowledge, inactive/cited index versions, conversations and answer/index jobs. Numeric retention values are implementation/product inputs, not assumed values in this plan.
* [ ] Define account/Subject deletion and export, instructor removal, explicit hard deletion, student conversation deletion and retention expiry.
* [ ] Ordinary document removal preserves historical answer text and minimum citation metadata/excerpts under authorized conversation access; show `Source removed`. It is distinct from explicit erasure.
* [ ] Define how hard deletion erases canonical pages, chunks/vectors and derived citation excerpts/sensitive content, while retaining only policy-permitted tombstone metadata. Historical traceability must not override an explicit erasure requirement.
* [ ] Subject deletion erases its associated knowledge, conversations, source snapshots and pending jobs; document removal/hard deletion does not delete existing flashcards.
* [ ] Define backup retention and deletion-reconciliation after restore so erased/removed sources cannot silently reappear as active knowledge.
* [ ] Document provider data handling, privacy disclosure, export authorization and content redaction; do not log lecture text, full prompts, embedding payloads or unnecessary student chat content.
* [ ] Record the policy and map each deletion path to source references, snapshots and cleanup behavior before approving Phase 13 migrations.

### PostgreSQL + pgvector readiness

* [ ] Select a PostgreSQL 16 pgvector-capable image/build, pin reviewed versions and an immutable image digest, and record PostgreSQL/extension compatibility.
* [ ] Update every PostgreSQL runtime/test reference and verify the **effective merged** dev/prod Compose configuration, including `docker-compose.yml` and its overrides.
* [ ] Update `scripts/test_services.py`, `scripts/test_journey.py`, `scripts/test_security.py`, CI/release image gates and relevant runtime/backup documentation.
* [ ] Treat the database image as a first-class runtime artifact: vulnerability scan, CycloneDX SBOM, immutable image identity and checksums under existing security gates.
* [ ] Add pinned Python `pgvector`; regenerate existing hash-locked dependencies with canonical project tooling.
* [ ] Add a new Alembic revision for `CREATE EXTENSION vector` and subsequent schema; validate extension installation privileges using the migration role, without granting routine API/worker roles unnecessary elevated privileges.
* [ ] Rehearse on a disposable copy of the current database: backup → deploy pgvector-capable PostgreSQL 16 runtime → verify database health and extension binaries → run extension/schema migrations → verify readiness.
* [ ] Test fresh installation, upgrade, downgrade and restore into an extension-capable target. Do not drop a shared extension or use destructive `DROP EXTENSION ... CASCADE` as an automatic downgrade strategy.

### Acceptance

* [ ] Flag-off generation regression passes, with database assertions proving no new persisted knowledge or RAG jobs.
* [ ] pgvector works in dev, disposable tests and production-shaped runtime/restore targets.
* [ ] Database image scan/SBOM gates and migration privilege/order checks pass.
* [ ] Early privacy/deletion policy is recorded; unresolved retention/model choices are visible implementation gates rather than invented defaults.

---

# Phase 13 — Persistent Subject Knowledge Model

Do **not** reuse `GenerationJobSource` as the knowledge store; it remains temporary.

### `subject_documents`

* [ ] UUID `id`, `subject_id`, `uploaded_by`, `filename`, `title`, `source_sha256`, `page_count` and timestamps.
* [ ] Nullable **unique** `generation_job_id` as the capture idempotency anchor. The originating job's cleanup must not delete valid knowledge; define safe reference detachment according to retention policy.
* [ ] `status`, bounded/redacted `index_error_code`/`index_error_message`, `active_index_version_id` and removal/tombstone metadata.
* [ ] Snapshot embedding provider/model/version/dimension for the active index; preserve metadata on each index version rather than overwriting history.
* [ ] Persist a usable document only after successful validated extraction/chunking. Existing generation-job upload/extraction stages remain the source of pre-capture progress; no usable knowledge for unreadable PDFs.

Document states: `pending_index`, `indexing`, `ready`, `index_failed`, `removed`. Version/job states track a rebuild independently; a failed rebuild may leave the old active version ready. Removal is a lifecycle state, not an indexing failure.

### `subject_document_pages`

* [ ] Persist canonical extracted page text: `document_id`, `page_number`, `content`, unique `(document_id, page_number)`.
* [ ] Retain extraction/page/section provenance needed to reproduce page-aware chunking; validate rebuild equivalence.
* [ ] Use these pages as the rebuild source, never flashcard snippets or retained raw PDF bytes.

### Index versioning and durable indexing work

* [ ] Add explicit version metadata, e.g. `subject_document_index_versions`: UUID `id`, `document_id`, `subject_id`, monotonic `index_version`, state/timestamps, chunker settings/version and embedding provider/model/version/dimension.
* [ ] Unique `(document_id, index_version)`; a document's active-version reference must belong to that same document/Subject.
* [ ] Represent indexing/rebuild work in a durable PostgreSQL queue, e.g. `subject_document_index_jobs`, with claim token, lease/heartbeat, retries, errors and a unique logical operation/version key.
* [ ] Publish only a completely indexed version; keep the prior active version during rebuild.
* [ ] Preserve old cited chunk versions while their references/retention require it; reclaim uncited inactive versions only under the privacy policy.

### `subject_document_chunks`

* [ ] UUID primary key `id` is the **persistent identity** used for RAG citations.
* [ ] Separate `chunk_key` retains the current **logical runtime identity**, such as `chunk-0001-p1`; do not replace generation `DocumentChunk.chunk_id` with a database UUID.
* [ ] Include `subject_id`, `document_id`, `index_version_id`, `chunk_index`, `page_number`, `section`, `content`, `token_count`, `embedding` and lexical-search representation.
* [ ] Unique `(document_id, index_version_id, chunk_index)` and `(document_id, index_version_id, chunk_key)`; chunks and provenance are immutable within a published version.
* [ ] Scope embeddings to the deployment dimension contract; version metadata records which model produced them. Phase 13 establishes document/version/chunk identities and text; **defer the dimensioned embedding-column/vector-index DDL to a Phase 15 migration after the provider/model/dimension contract is pinned**. Do not guess a dimension in Phase 13.

### Existing models and database integrity

* [ ] Add nullable `subject_document_id` to `GenerationJob` and `FlashcardSet`; retain existing `source_pdf_name`. Historical rows remain valid with no linked document.
* [ ] Add `subject_documents UNIQUE(id, subject_id)` and composite chunk FK `(document_id, subject_id) REFERENCES subject_documents(id, subject_id)`.
* [ ] Enforce the same document/Subject consistency for pages where duplicated, index versions/jobs and nullable document links on sets/generation jobs. Enforce chunk/version/document consistency with composite parent keys.
* [ ] Ensure index-job/generation-job links remain in the same Subject; plan nullable cyclic references and insertion order explicitly.
* [ ] For detached nullable references, clear **only** the optional document/chunk link; never null a required `subject_id` as a side effect of composite-FK deletion. Verify PostgreSQL 16 behavior in migrations/tests.
* [ ] Physical document erasure cascades to pages/index versions/chunks/jobs; retained citation references detach and snapshots follow erasure policy. Subject erasure cascades to all its knowledge/chat records.
* [ ] Add appropriate Subject/document/version/queue/FTS indexes and constraints; ANN index is evidence-gated in Phase 15/19.

### Acceptance

* [ ] PostgreSQL rejects mismatched Subject/document/version relationships, including direct SQL writes.
* [ ] Historical jobs/sets migrate without fabricated documents; document deletion preserves flashcards and required Subject identities.
* [ ] Version/deletion schema preserves citations through rebuild/removal and supports policy-compliant hard deletion.

---

# Phase 14 — Integrate Knowledge Capture Into Existing PDF Flow

### Reuse and preserve existing generation contracts

* [ ] Keep `PDFProcessor`, subprocess/resource limits, optional OCR, `ExtractedDocument` and current page-aware `chunk_document()`.
* [ ] Preserve current flashcard chunk defaults **1200 input tokens / 120 overlap**, logical chunk IDs, allocation, evidence packing, coverage, grounding and validation.
* [ ] Introduce the smallest shared preparation seam: extract once and chunk once per attempt; allow the existing generation pipeline to consume those precomputed `DocumentChunk` objects unchanged.
* [ ] Persist the same initial logical chunks for RAG with separate UUID identities. RAG evaluation must not silently alter generation chunking; any later RAG-specific variant is versioned and separately regression-tested.

### Independent, idempotent capture transaction

Immediately after validated extraction/chunking, **before AI flashcard generation**, when RAG is enabled:

* [ ] Open an independent, bounded DB transaction; recheck the unexpired generation lease/claim, cancellation, authorized Subject ownership/existence, RAG enablement and document lifecycle.
* [ ] Atomically persist document + canonical pages + initial chunk/index version + durable indexing job, and link the generation job. Commit this independently of Set/Card creation.
* [ ] Use unique `subject_documents.generation_job_id` plus version/job operation keys to make capture safe after crash, lease recovery, automatic retry and manual retry of the same generation job.
* [ ] If capture already committed, reuse/validate that document rather than duplicating pages/chunks; never resurrect a document removed during a later generation retry.
* [ ] Invalid/unreadable PDFs create no usable knowledge; stale/cancelled workers cannot commit capture.
* [ ] Do not defer capture to `_finish_success()`. Keep existing Set + Cards + source deletion + generation-completion transaction intact, apart from the validated optional document link.

### Failure and cleanup isolation

* [ ] Successful capture survives subsequent AI-generation failure or cancellation; already captured knowledge is managed separately in Knowledge.
* [ ] Indexing failure must not change successful flashcard generation to failure.
* [ ] A capture-specific failure rolls back only the capture transaction, produces bounded non-content diagnostics/status and lets the existing generation path continue where its own DB/lease remains healthy. After source cleanup, missing capture may require re-upload; do not promise reconstruction from flashcards.
* [ ] Preserve current encrypted temporary-source cleanup/expiry even if knowledge capture/indexing fails; do not retain raw PDFs longer solely for RAG.
* [ ] When RAG is disabled, skip this persistence seam completely and preserve current generation behavior.

### Acceptance

* [ ] One existing upload can produce flashcards and independent reusable knowledge.
* [ ] Crash after capture/before card finalization, same-job retries and concurrent/stale claims never duplicate documents.
* [ ] Generated output and source cleanup remain unchanged; capture/index failure and generation failure are independently represented.
* [ ] Removal/cancellation/Subject-deletion races cannot recreate or reactivate forbidden knowledge.

---

# Phase 15 — Embedding & Knowledge Indexing

### Embedding contract and pinned configuration

Add a dedicated provider-neutral `EmbeddingProvider` with `embed_documents(...)` and `embed_query(...)`, separate from the structured-generation provider.

* [ ] **Before implementation or dimensioned vector DDL:** select/review one embedding provider/model/version and pin deployment-wide `EMBEDDING_DIMENSIONS`; record availability, document/query compatibility, limits and pricing/configuration inputs. Add the deferred embedding column and any evaluated vector index in a new Phase 15 migration.
* [ ] Make schema `vector(n)`, adapter output and configured dimensions agree; reject absent/mismatched/non-finite embeddings before persistence or retrieval.
* [ ] Validate non-secret configuration at startup; workers additionally validate required credentials and provider compatibility. FastAPI never instantiates a credentialed embedding provider.
* [ ] Record provider/model/version/dimension and chunker/index-version metadata for every indexed generation and its active-document summary.
* [ ] Same-dimension model changes require a compatible query/document model rollout and complete rebuild with a controlled switch; never mix incompatible model spaces in one retrieval pool.
* [ ] Different dimensions require an explicit schema/vector-index migration and rebuild procedure. Do not treat a dimension change as an ordinary retry.

### Indexing and version activation

* [ ] Batch embedding calls with bounded payloads, retries/timeouts, telemetry and validated output ordering/counts; reuse existing provider conventions where appropriate.
* [ ] Persist vectors and PostgreSQL FTS representation idempotently per chunk/version; never mark a partial index ready.
* [ ] Rebuild/re-embed into a **new** version without deleting old cited chunks; atomically switch the active pointer only after validation, while holding/checking the current claim and non-removed document state.
* [ ] Failed reindex retains the prior compatible active index. Retry the same unfinished logical version safely; prevent duplicate queue operations.
* [ ] Rebuild from canonical pages without re-uploading; test page/section/chunk provenance equivalence.
* [ ] Begin with exact cosine retrieval and a PostgreSQL lexical index. Add an ANN vector index only if measurements justify it; prefer evaluated HNSW cosine, with subject-filter recall/security tests and documented memory/build costs.

### Worker and quota isolation

Use the same backend image and PostgreSQL infrastructure, with **separate durable queues and worker processes**:

| Process | Work | Required isolation |
|---|---|---|
| `generation-worker` | Existing flashcard jobs | Preserve current admission, concurrency, leases, heartbeat, provider governor and shutdown behavior. |
| `knowledge-index-worker` | Embeddings, indexing, rebuilds | Dedicated queue, concurrency, deployment bounds and provider budget. |
| `rag-answer-worker` | Query embedding, retrieval, grounded answers | Dedicated queue, concurrency, Ask-AI quotas and provider budget. |

* [ ] Reuse existing lease/heartbeat/fencing and graceful-drain patterns; stop claims when disabled and validate authorization/lifecycle again before activation.
* [ ] Bound DB connections, batches and active work so RAG cannot exhaust generation capacity. Separate processes alone do not guarantee shared DB/provider capacity.
* [ ] Allocate per-workload/deployment provider RPM/TPM/cost budgets; do not assume the current process-local governor coordinates multiple processes or replicas. Use reserved provider quota/credentials or PostgreSQL-backed shared admission where needed.
* [ ] No API-side provider calls, Redis/Celery or unbounded retry loops.

### Acceptance

* [ ] Embedding configuration/schema/output agree; malformed or incompatible embeddings fail safely.
* [ ] Reindex activation is atomic, removal wins activation races, and historical citations retain original version provenance.
* [ ] Saturated RAG queues remain bounded and do not consume reserved generation job/provider capacity.

---

# Phase 16 — Subject-Scoped Retrieval Service

Create one reusable `KnowledgeRetriever` taking authorized `subject_id`, query text, optional `document_ids` and bounded `limit`. Query embedding/retrieval runs in a credentialed worker context; API access checks do not require provider secrets.

### Authorization and query boundary

* [ ] Reuse Subject access checks: instructor owns the Subject; student is enrolled. Recheck current access in queued workers, after revocation races and on history/source endpoints.
* [ ] Backend owns Subject/document scope. Never trust an LLM-generated `subject_id` or let query rewriting expand the authorized boundary.
* [ ] Every vector **and** FTS SQL query includes `WHERE subject_id = :authorized_subject_id`, active compatible index version and non-removed/ready document conditions, with optional document filters conjunctively applied.
* [ ] Validate selected document IDs inside that Subject; never run global retrieval and filter results afterward.
* [ ] Exclude partial/failed initial indexes, removed documents and inactive versions from new retrieval.

### Deterministic hybrid retrieval

* [ ] Retrieve independently bounded vector top-N and lexical top-N candidates within the authorized scope.
* [ ] Fuse with **Reciprocal Rank Fusion (RRF)**: for each candidate, sum `1 / (rrf_k + rank)` across lists containing it; ranks are 1-based. Configure/evaluate `rrf_k` and candidate limits.
* [ ] Deduplicate by persistent chunk UUID/version and use deterministic tie-breaking, then select bounded top-K/context.
* [ ] Do not add raw cosine and `ts_rank` scores directly. Return explicit component rank/score information where needed for non-content diagnostics.
* [ ] Apply evaluated evidence thresholds before answering; an RRF score alone is not proof that a source supports a query.
* [ ] Evaluate PostgreSQL FTS configuration (`simple` vs language-specific stemming) on actual technical/multilingual corpus; record the choice.
* [ ] Return structured provenance: persistent `chunk_id`, logical `chunk_key`, document ID/title, index version, page, section, content and explicit score/rank metadata.
* [ ] Defer a dedicated reranker until evaluation demonstrates a need.

### Blocking retrieval/security evaluation gate — before Phase 17

* [ ] Build a deterministic corpus/provider fixture using the guarded disposable API/worker/PostgreSQL test infrastructure; no paid provider in normal CI.
* [ ] Cover direct facts, paraphrases, exact technical terms, overlapping concepts across lectures, multi-page evidence, unsupported queries, hostile lecture content and cross-Subject/document-ID attacks.
* [ ] Freeze expected source/page results and measurable retrieval thresholds before tuning; record hit quality, empty retrieval, provenance correctness, latency and vector-filter recall if ANN is used.
* [ ] Require **zero cross-Subject sources** and correct active-version/removal behavior; fail closed on missing authorization or incompatible index metadata.
* [ ] Record a passing retrieval/security gate before Phase 17 depends on the service. Full conversational/answer evaluation follows in Phase 19.

---

# Phase 17 — Subject Ask AI Backend

Keep Ask AI asynchronous and gated by Phase 16. Credentials remain worker-only.

### Conversation and citation persistence

Add `rag_threads`, `rag_messages`, `rag_message_sources` and `rag_answer_jobs`.

* [ ] Each thread belongs to one user and one Subject; enforce thread/message/job Subject consistency and owner access, not enrollment alone for another student's private thread.
* [ ] Keep messages separate from shared knowledge; never embed conversation history into `subject_document_chunks`.
* [ ] Sources store a real nullable chunk reference plus immutable snapshots of document title, page, section, chunk/index identity and minimum citation excerpt/provenance allowed by policy.
* [ ] Keep citations traceable through reindexing; preserve historical metadata/excerpts on ordinary removal with `Source removed`. Detach nullable chunk links and erase/redact snapshots on explicit hard deletion/retention as required.
* [ ] Authorize conversation, source and export endpoints; a guessed chunk/message/source ID must not reveal data.

### Durable question idempotency and bounded context

* [ ] Require an `Idempotency-Key` or equivalent durable client message ID; scope a unique logical question operation to authenticated user/thread/Subject.
* [ ] In one transaction, authorize ownership/Subject access, check a fingerprint of semantic request inputs, persist the user message and one answer job, and charge applicable quota once.
* [ ] Replay of the same key/payload returns the same operation/message/job; same key with different payload returns an explicit conflict. Double click, timeout, reload and concurrent retries create no duplicate logical jobs.
* [ ] Uniquely map each user question to its answer job and committed assistant message. Retry UI reuses the same logical operation; genuine new questions use a new key.
* [ ] Bound history by max turns, input tokens and retrieved context; do not replay unlimited threads. Serialize or explicitly order concurrent turns so follow-up context is deterministic.
* [ ] Optional model query rewriting changes only bounded query text; it cannot select Subject IDs or expand document access.

### Request execution and grounding

* [ ] API authorizes and persists work; `rag-answer-worker` rechecks current enrollment/ownership, feature flag and thread/document lifecycle before retrieval and before answer commit.
* [ ] Default to course materials only. Treat PDF/context content as untrusted data; keep prompt-injection protections.
* [ ] Generate strict structured output: `answer`, `citation_chunk_ids[]`, where IDs are persistent UUIDs from the retrieved authorized evidence set.
* [ ] Validate every citation against retrieved chunks, Subject, document and index-version provenance; reject fabricated/unknown/out-of-scope IDs. IDs alone do not prove semantic support; evaluate answer evidence quality.
* [ ] Return a clear insufficient-material response if retrieval/evidence is inadequate; do not silently use unrestricted general knowledge.
* [ ] Commit answer + validated source snapshots + completed job atomically with a current claim and lifecycle checks. If a source was removed during generation, discard/retrieve again under bounded policy rather than publishing newly invalid evidence.
* [ ] Convert validated provenance into citation labels such as `Lecture 05 · Page 17` in the backend.

### Limits and provider retry semantics

* [ ] Separate student Ask-AI quotas/rate limits from instructor generation quotas; bound per-user/deployment active/queued work, token use, provider calls and cost.
* [ ] Use bounded retries/timeouts, leases, heartbeat/fencing and graceful shutdown; preserve cancellation/deletion behavior.
* [ ] Record usage/cost and retry telemetry without content; label estimates and count retries, including query embedding.
* [ ] Persist logical operation/call state and use provider idempotency where supported. Durable app idempotency prevents duplicate submits, but a crash after external provider success and before DB commit can still cause an at-least-once provider retry; do not promise exactly-once billing without provider support.

### Acceptance

* [ ] Duplicate/conflicting submissions, lease recovery and concurrent turns produce the specified durable results and one quota charge per logical question.
* [ ] Revocation/removal/deletion races do not publish unauthorized answers or leak another user's history.
* [ ] Fabricated citations and unsupported answers fail safely; ordinary removal/reindex retains authorized historical citation provenance.

---

# Phase 18 — Subject Ask AI Frontend

Use current role-aware `/subjects/:id`: instructor `SubjectDetails`, student `StudentSubjectDetails`. Do not redesign navigation or create an unrelated knowledge app.

### Instructor Knowledge

* [ ] Add a Subject Knowledge area listing captured lecture documents; keep **Generate Set → Upload PDF** as the only V1 upload workflow.
* [ ] Show capture/indexing/ready/failed/rebuild states, safe errors, retry indexing and document removal. Pre-capture progress comes from the existing generation job; capture failure remains distinguishable from successful cards.
* [ ] Show knowledge captured even when flashcard generation later fails; rebuild failure can leave the previous compatible version ready.
* [ ] Removal stops future retrieval, preserves flashcards and displays the approved historical-source behavior; hard deletion follows the earlier policy.
* [ ] Explain concisely that extracted lecture text persists when RAG is enabled; feature-off UI matches existing behavior.

### Student Ask AI

* [ ] Add Subject-level thread/message UI, job/loading state, bounded follow-ups, quota/error/insufficient-material state and retry with stable logical message IDs.
* [ ] Show backend-validated citation chips with document title/page/section and a clear `Source removed` state on historical citations.
* [ ] Preserve responsive layout and accessible keyboard/focus/live status behavior; handle revoked enrollment safely.
* [ ] No PDF viewer in V1: raw PDFs are not retained permanently.

---

# Phase 19 — Retrieval & RAG Evaluation

Extend the Phase 16 deterministic retrieval corpus into complete conversational and answer evaluation; do not postpone retrieval/security validation until this phase.

### Cases and measurements

* [ ] Direct facts, paraphrases, exact terms, similar lecture concepts, multi-page topics and bounded follow-up questions.
* [ ] Unsupported queries, empty knowledge, prompt injection in lecture content, cross-Subject attacks, access revocation, source removal/reindex and user-history isolation.
* [ ] Measure retrieval hit quality, source/page correctness, unsupported-answer rate, semantic grounding, citation validity, empty-retrieval rate and latency.
* [ ] Measure indexing/query embedding and answer-model calls/tokens/cost separately; include retries and label actual versus estimated usage.
* [ ] Freeze acceptance thresholds and reviewed expected sources before tuning; record corpus/config/model/index-version identities and results. No invented numeric quality target in this revision.

### Tune from evidence

* [ ] Candidate top-N/top-K, RRF constant, lexical configuration, evidence thresholds and context size.
* [ ] Compare exact cosine against ANN latency/recall inside Subject filtering before adopting ANN; use HNSW only when supported by results.
* [ ] Revisit RAG chunk settings only if current chunking demonstrably underperforms; preserve generation defaults/IDs/contracts and explicitly version any alternative.
* [ ] Add a reranker only if measured hybrid retrieval remains inadequate.
* [ ] Normal CI uses deterministic fake embeddings/answers. Any live-provider evaluation is explicitly gated by reviewed budget and credentials; do not mistake fake-provider performance for real semantic/model quality.

---

# Phase 20 — Regression, Security & CI

### Existing behavior

* [ ] Keep existing offline backend, AI generation, PDF/OCR, PostgreSQL, frontend, instructor/student journey, dependency/security and SBOM gates green.
* [ ] Preserve current coverage/bundle budgets and mandatory hosted `ci-required` behavior. Do not weaken gates to accommodate RAG.

### New persistence/runtime tests

* [ ] PostgreSQL 16 pgvector availability; migration upgrade/downgrade/`alembic check`, schema drift and backup/restore compatibility.
* [ ] Direct SQL rejection of mismatched document/Subject/index/chunk links; nullable-link detachment and physical document/Subject cascades.
* [ ] Flag-off database proof: no extracted knowledge persistence, no new RAG jobs/claims, unchanged temporary PDF cleanup and generated output.
* [ ] Independent capture rollback/commit, generation failure after capture, crash/retry idempotency, lost lease/cancellation and removed-document retry behavior.
* [ ] Complete-version activation, partial/rebuild failures, active-version filtering, citation history after reindex/removal and policy-compliant hard deletion.
* [ ] Embedding count/order/dimension/finite-value checks, incompatible-model exclusion and cosine/lexical/RRF behavior.
* [ ] Durable Ask-AI idempotency/conflicts, quota accounting, bounded context and provider retry telemetry.
* [ ] Separate queue saturation, reserved generation capacity and multi-process/deployment provider-budget enforcement.
* [ ] Pinned database image vulnerability/SBOM gates alongside existing runtime images; effective Compose and extension privilege/order checks.

### Security tests

* [ ] Student cannot query an unenrolled Subject; instructor cannot query another instructor's Subject.
* [ ] Both vector/FTS SQL queries enforce Subject scope; no cross-Subject source reaches context or responses.
* [ ] Guessed document/chunk/message/thread/source IDs do not bypass authorization or expose another student's conversation.
* [ ] Recheck access for queued work, history/source/export endpoints and before answer commit; cover enrollment revocation and Subject deletion.
* [ ] Fabricated citations fail validation; prompt injection remains untrusted source data.
* [ ] No lecture text, full prompts, payloads, credentials or unnecessary chat content in logs/telemetry/errors.

### Deterministic RAG-enabled journey

* [ ] Real API + generation/index/answer workers + disposable pgvector-capable PostgreSQL + frontend: instructor uploads once → flashcards generated → knowledge indexed → publishes/invites → enrolled student asks → grounded answer → correct page citation.
* [ ] Follow-up, duplicate submit, indexing retry, reindex/removal with historical citation visibility, and unenrolled-Subject denial are verified in the appropriate journey/service layers.
* [ ] Guard deterministic test providers, isolate configuration and clean disposable services/accounts/artifacts. No paid provider call in normal CI.

---

# Phase 21 — Privacy, Operations & Rollout

Enforce the early Phase 12 policy and coordinate with unfinished Phase 10 work; this phase must not discover deletion requirements after the schema has shipped.

### Privacy and operations

* [ ] Publish extracted-text persistence, provider handling and retention/deletion/export disclosures; implement and verify configurable cleanup and snapshot erasure.
* [ ] Confirm Subject/account/conversation deletion and flashcard preservation on document removal, including in-flight jobs and restored backups.
* [ ] Add content-free health/readiness signals for extension/schema/dimension compatibility and all required workers; feature-off RAG readiness must not make the existing application unhealthy.
* [ ] Track queue depth/age, indexing latency/failures, retrieval/answer latency/errors, empty retrieval, invalid citations and embedding/provider usage/cost by workload.
* [ ] Document queue recovery, lease expiry, failed rebuilds, inactive-version cleanup, same/different-dimension model changes and rollback limits.
* [ ] Update root `.env.example`, `docs/CONFIGURATION.md`, deployment/testing/CI/database-operation docs and backup/restore procedures; provider secrets remain worker-only.
* [ ] Restore into a compatible PostgreSQL 16/pgvector target, validate extension/vector metadata/indexes and reconcile deletion state before serving retrieval.

### Deployment order and rollout

* [ ] Ship application with `RAG_ENABLED=false`; capture a verified backup and rehearse rollback/restore on disposable data.
* [ ] Deploy pinned pgvector-capable PostgreSQL runtime **before** `CREATE EXTENSION vector`/schema migrations; verify database health, extension binaries and migration-role privileges.
* [ ] Apply migrations and validate schema/dimensions/runtime; deploy worker entry points and required configuration with bounded dedicated budgets.
* [ ] Run required regression/security/CI and Phase 16/19 evaluation gates; enable RAG first in a controlled environment on several real Subjects.
* [ ] Validate real-provider quality/cost, source cleanup, removal/reindex history and capacity isolation before production enablement.
* [ ] Production enablement requires all acceptance gates and privacy/operations controls. Turning RAG off stops new work/serving/capture but does not erase data or require a destructive database downgrade.

---

# Existing Data / Backfill Policy

Historical PDFs cannot automatically become full RAG knowledge: temporary sources were intentionally deleted after generation.

* [ ] Do not reconstruct lectures from flashcard snippets or fabricate historical corpora.
* [ ] Existing sets/cards/jobs work unchanged and may retain null document links.
* [ ] Instructors may re-upload old lectures through the existing Generate Set workflow if they want that knowledge; no separate upload/backfill endpoint in V1.
* [ ] New enabled uploads become knowledge only after successful capture. Index readiness is independent from flashcard completion.
* [ ] Identical PDF content in different Subjects remains independently scoped. Source hash is not a global retrieval identity or substitute for job idempotency.

# Explicitly Not Part of RAG V1

* No dedicated vector database, Redis/Celery or unrelated infrastructure stack.
* No separate Knowledge-only upload flow.
* No permanent raw-PDF retention or PDF source viewer.
* No vector-search rewrite of flashcard generation; no casual changes to its chunking behavior.
* No chat-history embeddings, automatic historical PDF backfill or global cross-Subject knowledge search.
* No reranker or ANN requirement without evaluation evidence.
* No guarantee of exactly-once external provider billing without provider support.

# Final Target Architecture

Existing upload → encrypted temporary source → bounded PDF/OCR extraction → shared page-aware logical chunks.

When RAG is enabled, an independent fenced transaction captures Subject pages/versioned chunks and indexing work **before** the existing flashcard pipeline continues. Existing Set/Card finalization and temporary PDF cleanup retain their own transaction and behavior. Capture/index failures and flashcard failures remain independently represented.

| Path | Owner | Output |
|---|---|---|
| Current full-document generation | `generation-worker` | Existing grounded flashcards; temporary PDF removed under current policy. |
| Knowledge indexing/rebuild | `knowledge-index-worker` | Complete active version in PostgreSQL + pgvector/FTS; old cited versions preserved under policy. |
| Subject Ask AI | API durable submission + `rag-answer-worker` | Authorized Subject-filtered hybrid retrieval, grounded answer and validated citation snapshots. |

All three use the same backend image and PostgreSQL infrastructure with separate queues/processes and explicit capacity/provider budgets.

# Definition of Done

* [ ] Existing generation output/contracts and temporary encrypted PDF retention/cleanup are preserved; flag-off persists no extracted knowledge.
* [ ] One existing upload can become flashcards and independent Subject knowledge via fenced, idempotent capture.
* [ ] Privacy/deletion/export policy and compatible PostgreSQL 16 pgvector runtime, image scan/SBOM, migration/restore order are verified.
* [ ] Logical generation chunk IDs remain unchanged; persistent UUID/version identities provide durable RAG provenance.
* [ ] Database-enforced Subject/document/version invariants and SQL-level Subject predicates prevent cross-Subject retrieval.
* [ ] Pinned embedding model/dimension and compatible active versions are enforced; rebuilds switch atomically and preserve historical citations.
* [ ] Separate durable workers/budgets preserve generation capacity under RAG load.
* [ ] Phase 16 retrieval/security gate passes before Ask AI; Phase 19 real-quality evaluation and final CI/journey/security gates pass before rollout.
* [ ] Ask AI requires current enrollment/ownership, private-thread authorization, durable question idempotency and bounded context/cost.
* [ ] Answers are grounded in Subject materials, unsupported queries fail clearly, and backend-validated citations survive ordinary removal/reindex with explicit source state.
* [ ] Hard deletion/retention/Subject deletion erase associated content as required; conversations never pollute shared knowledge.
* [ ] RAG capture/indexing/answer failures cannot convert successful flashcard generation into failure.

# Approved Recommendation Traceability

| Review item | Where addressed |
|---|---|
| R1 — independent capture transaction/idempotency | Phases 13–14, 20 |
| R2 — logical chunk key versus persistent UUID | Phases 13–14, 20 |
| R3 — versioned chunks and citation snapshots | Phases 12–13, 15, 17–18, 20–21 |
| R4 — database Subject integrity and scoped SQL | Phases 13, 16–17, 20 |
| R5 — separate worker queues/processes/capacity | Phases 15, 17, 20–21 |
| R6 — strict flag-off persistence behavior | Phases 12, 14, 20–21 |
| R7 — pgvector runtime/security/restore rollout | Phases 12, 20–21 |
| R8 — pinned embedding model/dimension contract | Phases 13, 15–16, 20–21 |
| R9 — RRF, FTS selection, evidence-gated ANN | Phases 15–16, 19 |
| R10 — durable Ask-AI idempotency/bounded history | Phases 17–20 |
| R11 — early privacy/deletion policy | Phase 12 blocking gate, Phases 13, 17, 21 |
| R12 — retrieval evaluation before Ask AI | Execution order, Phase 16 blocking gate, Phases 17, 19–21 |

Approved decisions and follow-up verification are recorded in `.agent/logs/2026-09-17-subject-rag-plan-review.md` in the repository.
