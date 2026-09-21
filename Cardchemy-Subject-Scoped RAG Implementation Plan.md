# Cardchemy — Subject-Scoped RAG Implementation Plan

## Status, scope and objective

Updated 2026-09-21. The operator-approved
[source-grounded review and recommendations](.agent/logs/2026-09-17/2026-09-17-flashcard-prompts-and-rag-plan-review.md)
preceded implementation. Preparation A/B and Phases 12–21 are implemented with
the linked verification records below. The bounded live Gemini flashcard and
Subject RAG evaluations passed after explicit operator authorization. The
operator confirmed Cardchemy has no centralized production deployment: users
clone the repository and operate the production-shaped Docker stack themselves.
Release-specific Windows/browser/Narrator validation passed. Final closure is
therefore gated only on the protected-main hosted/rehearsal and clean-clone
evidence recorded below.

Add Subject-scoped RAG while preserving the existing grounded flashcard workflow,
and improve flashcard prompt yield through a separately measured workstream.

```text
Subject = Knowledge Boundary
```

Every retrieval must be authorized and filtered by the actual `subject_id`,
current Knowledge visibility and active corpus revision before results reach an
answer model or a user. Enrollment alone does not publish Knowledge.

### Verified pre-implementation context

- Review baseline: `main`, HEAD `e10f5839735379e4277d35600067835f53272a89`.
- Product version at review: 0.1.0; Phases 0–11 and the separate operational
  readiness gate were recorded complete. RAG/embeddings/pgvector had not shipped.
- Alembic head at review: `20260917_0008`; Phases 12–13 add `0009` and `0010`.
- PostgreSQL owns durable generation/email queues. Generation uses bounded PDF
  extraction, strict grounded output, leases/fencing and atomic complete results.
- Raw PDFs are temporary encrypted sources, not a permanent lecture archive.
- Root `.env` is the only user-managed configuration file.
- Fresh review checks: 376 backend offline passes, 50 service-gated skips, one
  live-AI deselection; focused AI suite 42 passes. These are existing-behavior
  evidence, not RAG or real-model prompt-quality validation.

### Approved decisions

| Decision | Contract |
| --- | --- |
| Knowledge publication | Instructor review/publication is separate from indexing readiness and flashcard-set publication; new Knowledge defaults to private. |
| Configuration migration | Hard rename `AI_*` to `FLASHCARD_AI_*`, mandatory migration guide, no compatibility aliases or deprecation period. Remove legacy `GEMINI_API_KEY` fallback. |
| Model responsibilities | Independent flashcard and Ask AI text-generation profiles plus a dedicated embedding profile; shared providers/keys require explicit configuration and quota policy. |
| Flashcard quality | Refine prompts and bounded refill context from measured evidence; preserve existing `insufficient_grounded_cards` handling and strict complete-result contract. |
| RAG boundaries | PostgreSQL 16 + reviewed pgvector support, worker-only provider credentials, Subject-scoped retrieval, persistent extracted text and no permanent raw PDFs. |
| Delivery | Separate quality/configuration workstreams, then Phases 12–21 with relevant verification at every phase; privacy design and evaluation corpus precede persistent writes/tuning. |

### Non-negotiable preservation

- [x] Preserve four-option multiple-choice rules, trusted chunk/quote/answer
  validation, duplicate rejection and instructor card approval.
- [x] Preserve exact requested count or atomic failure with no partial set.
- [x] Preserve full-document flashcard coverage, allocation/packing and source
  cleanup semantics after separately approved quality refinements.
- [x] Preserve one application retry owner: initial call plus at most three
  retries, delays of at least three seconds, usable longer `Retry-After`, no
  stacked SDK retries and no automatic expensive pipeline replay after a handled
  provider/pipeline failure or whole-job timeout.
- [x] Preserve source encryption, bounded PDF/OCR subprocesses, cancellation,
  admission/idempotency and lease/claim-token fencing.
- [x] Preserve root-only configuration, browser public allowlist, API ownership/
  enrollment checks, short-lived memory-only access tokens and session revocation.
- [x] Preserve existing data, secrets, volumes, used migrations and unrelated
  work. Reverify current source/consumers before each phase.

## Execution order and blocking design gates

Complete Preparation A, then Preparation B, then Phases 12–21. This retains the
original RAG phase numbering. Freeze a measured flashcard baseline before adding
shared Knowledge capture; RAG-disabled regression uses that approved baseline.

The recommendations are approved; the following product/operating choices remain
explicit decisions. Record outcomes in ADRs/domain contracts before dependent
implementation. Do not choose silent defaults or mark a gate satisfied merely
because it appears in this plan.

| Gate | Must decide and record | Required before |
| --- | --- | --- |
| G1: Installation support | Mandatory PostgreSQL-16-plus-pgvector runtime for all installs, or a deliberately supported optional schema/dependency profile; reviewed exact image/extension/package identities, privileges and restore/downgrade ownership. | Phase 12 runtime/schema implementation |
| G2: Privacy/history | Conversation retention; answer/citation read and invalidation/redaction or narrowly authorized version/tombstone policy after document deletion, unpublication and reindex; own-chat access, including instructor Ask AI scope. Instructor subject ownership does not grant access to student conversations. | Phase 13 persistent knowledge and Phase 17 chat writes |
| G3: Capture/cancellation | Whether cancelling generation after durable capture also removes/cancels Knowledge or leaves a private document; independent capture-failure outcome and recovery/reupload policy. No path may publish it automatically. | Phase 14 integration |
| G4: Upload/versioning | Knowledge-only upload in V1 versus an explicit requirement to regenerate a set; within-Subject duplicate/version policy, reupload UX and separate quota/storage ownership. | Phase 13 associations and Phase 14 upload integration |
| G5: Embedding/retrieval | Reviewed provider/model/task modes/dimensions/representation, embedding-space identity, index strategy, compatible migration/cutover and deterministic evaluation thresholds. | Phase 13 vector schema choices, Phase 15 persistence and Phase 16 tuning |
| G6: Worker/quota topology | Shared process or role-specific worker processes using existing primitives; independent lanes/credential lists, reserved capacity, actual account/project quota buckets and replica budget division or approved distributed governance. | Preparation B profile wiring and Phase 15 worker execution |

### Resolved choices for implementation through Phase 13

The operator approved G1/G2/G4/G6 and delegated G5 selection. Their contracts
are recorded in [ADR-012](docs/decisions/ADR-012-subject-knowledge-and-rag-boundaries.md).
Accepted design is not runtime or implementation evidence.

| Gate | Selected contract |
| --- | --- |
| G1 | PostgreSQL 16 + reviewed pgvector is mandatory for all installs, including RAG off. Exact artifact/extension/native privileges/recovery are verified during Phase 12. |
| G2 | 90-day private own chats, including instructors; all Ask AI uses ready/published eligible Knowledge. Hide derived stored answers/citations after supporting content is unpublished, deleted or replaced, with current access rechecked. |
| G4 | Knowledge-only uploads; replay identical uploads within the same Subject only; changed content needs fresh review/publication. Document deletion preserves linked flashcards. |
| G5 | [ADR-014](docs/decisions/ADR-014-native-gemini-rag-profiles.md) supersedes the initial provider choice: native `gemini-embedding-001`, 1,536-dimensional normalized float32/cosine, `RETRIEVAL_DOCUMENT`/`QUESTION_ANSWERING` task modes, and native `gemini-3.5-flash` Ask AI. Exact authorized search, explicit incompatible spaces/cutover and corpus criteria remain required. |
| G6 | Separate flashcard/index/answer processes with explicit credentials, enabled-role capacity and operator division of shared account/project quotas across profiles and replicas. No distributed governor. |

G3 remains required before Phase 14, beyond the requested implementation endpoint.

---

## Preparation A — Flashcard quality baseline and prompt refinement

`insufficient_grounded_cards` is an expected quality outcome. Current source
shows possible prompt and pipeline bottlenecks; the review does not establish
that prompts are the dominant cause of any particular real-document failure.

### Baseline and diagnostic evidence

- [x] Establish authored feasible and intentionally insufficient-source cases:
  short/long documents, sparse facts, boilerplate, overlapping/repeated facts,
  same-chunk split batches, Unicode/OCR artifacts and prompt injection.
- [x] Include wrong chunk IDs, invented/stitched quotes, missing answer spans,
  malformed options, near duplicates, valid underproduction and successful
  nonduplicating refill.
- [x] Use realistic candidate fixtures without artificial uniqueness markers
  that disguise repeated facts; retain existing enforcement regressions.
- [x] Add bounded content-free diagnostics as needed: prompt version, raw/
  grounded/distinct counts, fixed rejection categories, accepted/missing counts
  per round and refill usage. Preserve existing telemetry field semantics.
- [x] Keep diagnostics free of prompts, document/card text, quotes, candidates,
  raw provider responses and private exception details.

### Prompt and refill contracts

- [x] Version generation, summary-map and summary-reduce prompts.
- [x] Request the assigned target when distinct evidence supports it; explicitly
  prohibit fabrication or cosmetic paraphrases to satisfy an impossible target.
- [x] Explain per-chunk quotas and allowed source IDs precisely.
- [x] Prefer one clear testable fact per card, an unambiguous question, compact
  options and plausible parallel distractors with one supported correct answer.
- [x] Choose a short exact answer span and copy a contiguous supporting quote
  from the named chunk; forbid stitched quotations, ellipses and paraphrased
  answers that cannot satisfy containment checks.
- [x] Treat summaries as navigation aids; raw trusted chunks remain evidence.
- [x] Supply bounded accepted question/answer/concept exclusions to refill as
  untrusted context, with fixed safe rejection guidance where useful.
- [x] Include added instructions/exclusions in rendered-token packing,
  conservative preflight, context checks and actual usage/cost enforcement.
- [x] Measure current output capacity: a ten-card batch currently caps output at
  5,376 tokens despite an 8,192 configured ceiling. Compact output precedes any
  evidence-based cap change.
- [x] Evaluate text-weight allocation and same-source request overlap separately.
  Reallocation, scheduling or larger budgets require measured rationale and a
  separately reviewed behavior change; a wording change alone cannot fix them.

### Acceptance

- [x] Compare exact-count success on feasible material, accepted/raw yield,
  rejection categories, duplicate rate, refill use, source coverage, instructor
  quality judgment, tokens/cost and latency against the baseline.
- [x] Retain clean failure for impossible-source cases, unchanged structural/
  grounding/security thresholds and atomic complete results.
- [x] Run focused AI contracts and the backend offline suite.
- [x] Update AI generation/evaluation guides and relevant context/evidence.
- [x] Any live A/B evaluation has separate explicit authorization and reviewed
  endpoint/model/price/call/token/time/cost guards. The current one-call pinned
  OpenAI smoke harness is not a general Gemini/refill comparison runner.

### Preparation A checkpoint

Implementation and offline verification are complete. The operator reviewed the
four-card authored sample and accepted its questions, answers, distractors and
evidence as "very good" on 2026-09-18. Review the sample and measured nine-case replay in the
[comparison record](.agent/logs/2026-09-17/2026-09-17-flashcard-quality-offline-comparison.md).
Focused quality/pipeline/grounding: 55 passes. Full backend: 413 passes,
50 service-gated skips, one live-AI deselection. The deterministic browser/API/
worker/PostgreSQL journey and context validation passed. The replay isolates
the old generation renderer with current enforcement; it is not real-model A/B.
No paid calls were authorized or made. The checked live-evaluation item records
the authorization/guard contract, not execution of a live comparison.

Checked preservation items reflect this checkpoint and were reverified in
subsequent work. Preparation A and Preparation B are accepted; Phase 12 passed
its runtime gate before Phase 13 was applied. See the
[implementation log](.agent/logs/2026-09-17/2026-09-17-rag-through-phase-13-implementation.md)
and [Phase 12–13 closure](.agent/logs/2026-09-18/2026-09-18-rag-foundation-and-knowledge-schema.md)
for decisions, exact changes, checks and limits.

---

## Preparation B — Definitive AI profile configuration migration

### Namespace ownership

| Namespace | Purpose |
| --- | --- |
| `FLASHCARD_AI_*` | Existing flashcard text-generation profile, request/retry/rate/cost budgets and generation-specific packing/quality settings |
| `RAG_AI_*` | Ask AI answer model, connection and answer-specific request/retry/rate/token/cost controls |
| `RAG_EMBEDDING_*` | Embedding provider/model/key/base URL/dimensions, document/query task compatibility and batch/request/rate/cost controls |
| `RAG_ENABLED` | Overall RAG product flag; default false |

Use `FLASHCARD_AI_PROVIDER_ENABLED` and `RAG_AI_PROVIDER_ENABLED`, not `ENABLE`.
Define embedding enablement with the same `ENABLED` convention. Three capabilities
do not require three different providers or keys. No implicit credential/model
fallback between profiles is permitted; deliberate sharing has an explicit quota
bucket contract. Do not copy flashcard-only card/refill/summary controls into RAG.

### Mandatory key mapping

All 29 current `AI_*` template settings migrate as follows. The table maps names,
not operator values; preserve existing values during authorized migration.

| Removed name | New name |
| --- | --- |
| `AI_PROVIDER_ENABLED` | `FLASHCARD_AI_PROVIDER_ENABLED` |
| `AI_PROVIDER` | `FLASHCARD_AI_PROVIDER` |
| `AI_MODEL` | `FLASHCARD_AI_MODEL` |
| `AI_API_KEY` | `FLASHCARD_AI_API_KEY` |
| `AI_BASE_URL` | `FLASHCARD_AI_BASE_URL` |
| `AI_ALLOW_UNSTABLE_MODEL` | `FLASHCARD_AI_ALLOW_UNSTABLE_MODEL` |
| `AI_PROVIDER_MAX_RETRIES` | `FLASHCARD_AI_PROVIDER_MAX_RETRIES` |
| `AI_RETRY_BASE_SECONDS` | `FLASHCARD_AI_RETRY_BASE_SECONDS` |
| `AI_RETRY_MAX_SECONDS` | `FLASHCARD_AI_RETRY_MAX_SECONDS` |
| `AI_MAX_OUTPUT_TOKENS` | `FLASHCARD_AI_MAX_OUTPUT_TOKENS` |
| `AI_TEMPERATURE` | `FLASHCARD_AI_TEMPERATURE` |
| `AI_CONTEXT_WINDOW_TOKENS` | `FLASHCARD_AI_CONTEXT_WINDOW_TOKENS` |
| `AI_PROVIDER_TIMEOUT_SECONDS` | `FLASHCARD_AI_PROVIDER_TIMEOUT_SECONDS` |
| `AI_CONCURRENCY` | `FLASHCARD_AI_CONCURRENCY` |
| `AI_REQUESTS_PER_MINUTE` | `FLASHCARD_AI_REQUESTS_PER_MINUTE` |
| `AI_INPUT_TOKENS_PER_MINUTE` | `FLASHCARD_AI_INPUT_TOKENS_PER_MINUTE` |
| `AI_RATE_LIMIT_SAFETY_PERCENT` | `FLASHCARD_AI_RATE_LIMIT_SAFETY_PERCENT` |
| `AI_REQUEST_INPUT_TARGET_TOKENS` | `FLASHCARD_AI_REQUEST_INPUT_TARGET_TOKENS` |
| `AI_CARDS_PER_REQUEST` | `FLASHCARD_AI_CARDS_PER_REQUEST` |
| `AI_CHUNK_INPUT_TOKENS` | `FLASHCARD_AI_CHUNK_INPUT_TOKENS` |
| `AI_CHUNK_OVERLAP_TOKENS` | `FLASHCARD_AI_CHUNK_OVERLAP_TOKENS` |
| `AI_SUMMARY_OUTPUT_TOKENS` | `FLASHCARD_AI_SUMMARY_OUTPUT_TOKENS` |
| `AI_MAX_JOB_INPUT_TOKENS` | `FLASHCARD_AI_MAX_JOB_INPUT_TOKENS` |
| `AI_MAX_JOB_OUTPUT_TOKENS` | `FLASHCARD_AI_MAX_JOB_OUTPUT_TOKENS` |
| `AI_REFILL_ROUNDS` | `FLASHCARD_AI_REFILL_ROUNDS` |
| `AI_DUPLICATE_SIMILARITY_THRESHOLD` | `FLASHCARD_AI_DUPLICATE_SIMILARITY_THRESHOLD` |
| `AI_INPUT_COST_PER_MILLION_USD` | `FLASHCARD_AI_INPUT_COST_PER_MILLION_USD` |
| `AI_OUTPUT_COST_PER_MILLION_USD` | `FLASHCARD_AI_OUTPUT_COST_PER_MILLION_USD` |
| `AI_MAX_ESTIMATED_COST_USD` | `FLASHCARD_AI_MAX_ESTIMATED_COST_USD` |
| `GEMINI_API_KEY` | Remove fallback; an installation using only this key must explicitly migrate its credential to `FLASHCARD_AI_API_KEY`. Resolve dual-key ambiguity without printing values. |

### Settings, secrets and migration safety

- [x] Implement the hard rename in validated Settings and all consumers; no
  aliases or continued legacy fallback.
- [x] Detect nonempty removed names in supported root/process configuration
  sources and fail early with fixed migration guidance/key names only. Do not
  silently ignore old configuration or expose values in validation errors.
- [x] Test empty values, nonempty process-over-root precedence, unknown unrelated
  root keys and disabled-profile validation. Do not globally forbid unrelated
  extra keys in a shared root file.
- [x] Define the feature/provider flag matrix: RAG off admits/captures/retrieves
  no new RAG work and does not purge stored Knowledge/chat; RAG on still requires
  current authorization/publication. Provider disablement suspends affected
  model work without accidentally disabling another queue or exposing data.
- [x] Keep provider secrets out of API/email/frontend containers. API may share
  intended non-secret availability metadata. The existing generation worker
  receives only its flashcard key; native and future index/answer role injection
  limits are documented. Phase 15 enforces those limits on the new workers.
- [x] Define snapshot contracts for provider/model and embedding/corpus revisions
  on relevant jobs; preserve existing queued/manual-retry flashcard snapshots and
  API/DB `ai_provider`/`ai_model`. Phase 13 stores index-job snapshots and Phase
  17 stores answer-job snapshots when those tables are introduced.
- [x] Document admission pause, draining/cancelling incompatible queued/retryable
  work, private operator key migration, process restart/container recreation and
  verification. Changing endpoint/account can invalidate old model snapshots.
- [x] Preserve signing/source-encryption/database secrets; never regenerate or
  overwrite real `.env` through bootstrap. No component `.env` files.
- [x] Define independent generation/index/answer scheduling and reserved capacity
  under G6. Admission follows actual provider quota scope, including shared
  account/project limits and replicas; prefixes do not multiply provider quota.

### Consumer inventory and acceptance

- [x] Update `.env.example`, Settings/validators/safe errors, providers,
  pipeline/governor, generation service/worker and worker entry points.
- [x] Update Compose anchors/overrides and explicit secret lists, template/
  bootstrap consumers and native setup guidance.
- [x] Update offline/provider/configuration/PostgreSQL fixtures, live guard
  admission, journey/image/security/rehearsal settings and isolation assertions.
- [x] Update frontend public-loader secrecy regressions for all three profiles;
  only intentional public `VITE_*` data reaches the browser.
- [x] Update configuration/provider/evaluation/testing/deployment/setup docs and
  context navigation together. Preserve historical logs and used migrations.
- [x] Verify independent flag combinations, old-name fail-fast behavior, snapshot
  execution and credential isolation with no paid requests in normal tests.
- [x] Run offline backend checks, applicable Compose/runtime/CI checks and context
  validation; frontend changes use the complete frontend gate.

---

## Phase 12 — RAG foundation and pgvector readiness

### Architecture, privacy and evaluation prerequisites

- [x] Record RAG architecture/profile/data-boundary ADRs and G1/G2/G4/G6 outcomes.
  Explicitly revise affected existing support decisions/guides; do not present
  planned ADRs as already implemented architecture.
- [x] Define persistent text/chat lifecycle, provider transfer disclosure,
  capacity limits and export/delete ownership before the first persistent write.
- [x] Establish deterministic retrieval/answer corpus and acceptance criteria
  before embedding/index/retrieval tuning; extend it in Phase 19.
- [x] Reuse PostgreSQL queues, `SubjectService.check_subject_access()` and existing
  PDF/OCR/chunking/worker primitives with the additional publication checks.
- [x] Preserve the measured flashcard baseline with RAG disabled. No Redis,
  Celery or external vector database for V1.

### PostgreSQL 16 and pgvector support

A mandatory new Alembic head executing `CREATE EXTENSION vector` requires
pgvector binaries and suitable installation permissions even with
`RAG_ENABLED=false`. The flag disables product behavior, not schema installation.
G1 must settle installation support before migration/runtime work. Never branch
migration history or skip required heads based on environment flags.

- [x] Keep PostgreSQL 16 and choose a reviewed pgvector image/build with pinned
  extension version and immutable runtime identity. Preserve data paths/volumes
  and document native PostgreSQL installation as well as Compose support.
- [x] Inventory and update every PostgreSQL runtime consumer, including:
  `docker-compose.yml`, `scripts/test_services.py`, `scripts/test_journey.py`,
  `scripts/test_smtp_tls.py`,
  `backend/tests/postgres/test_postgres_startup_probe.py`, CI services and
  production recovery/demo/image consumers as applicable.
- [x] Maintain one reviewed runtime identity across consumers; verify supported
  container architecture, extension availability/version and existing-volume
  compatibility. Custom builds use portable compiler flags.
- [x] Pin the Python pgvector integration; update direct `.in` inputs and
  regenerate hash-locked dependencies with existing tooling. Verify supported
  Python versions, Alpine/musl images and asyncpg/SQLAlchemy integration.
- [x] Preserve offline SQLite fixture compatibility through deliberate portable
  model/test design; SQLite does not establish vector-query correctness.
- [x] Add new Alembic revisions for extension/schema work, explicit migration
  privilege/preinstalled-extension checks and safe failure diagnostics.
- [x] Define extension ownership and dependency-safe downgrade behavior; never
  drop another consumer's extension or use destructive downgrade on real data.
- [x] Include the exact DB image in security/SBOM/provenance expectations or
  document a reviewed external-image inventory contract; current app image
  scanning does not automatically cover a new database image.
- [x] Rehearse disposable upgrade/head/drift/downgrade/re-upgrade and populated
  backup/restore; validate extension version and indexes after restore.

### Acceptance

- [x] G1 support contract is documented; existing app works with RAG off on every
  declared supported installation profile.
- [x] Existing generation and affected service/startup suites remain green.
- [x] pgvector is verified in dev/test/production-shaped environments and native
  setup guidance; runtime/image/CI/context checks pass at this phase.

---

## Phase 13 — Persistent Subject Knowledge model

`GenerationJobSource` remains temporary. It is not the Knowledge store.

### Documents, pages and revisions

- [x] Add `subject_documents`: UUID, `subject_id`, uploader ownership, bounded
  filename/title, source SHA256 and timestamps, with page count, extraction/index
  state, fixed safe error pairs and extraction/chunker/embedding metadata on
  its separately versioned content/index records.
- [x] Add separate instructor review/publication metadata. New documents are
  private; indexing/reindexing never approves or publishes them. Specify reviewed
  revision identity so a new content revision cannot inherit approval silently.
- [x] Define capture/index lifecycle such as processing → pending_index → indexing
  → ready/index_failed, including cancellation and extraction failures. Upload
  reservation states are added only for the selected G4 upload flow.
- [x] Add `subject_document_pages` with canonical extracted text, original page
  number and unique document/revision/page identity. Retain empty-page numbering.
  These pages are rebuild/reindex sources; no permanent raw PDF bytes.
- [x] Add `subject_document_chunks`: UUID, subject/document/revision identity,
  chunk index, page/section, content, token count, embedding-space identity/vector
  and lexical representation; unique document/revision/chunk index.
- [x] Track active/staged document/corpus/index revisions, content/extraction/
  chunker versions and compatible embedding provider/model/version/dimensions.
- [x] Create a PostgreSQL indexing-job table or equivalent complete durable claim
  schema: stable operation identity, subject/document/revision, state, worker ID,
  random claim token, lease/heartbeat, attempts, available time, cancellation,
  safe errors and terminal timestamps. Phase 14 needs this durable enqueue target;
  Phase 15 implements its execution and recovery.
- [x] Bound permanent document/page/chunk/vector counts and bytes by document,
  Subject, user and deployment; current transient-source quotas are insufficient.

### Associations and integrity

- [x] Choose one authoritative generation-job/document association under G4;
  avoid redundant bidirectional ownership cycles. Job-history expiry must preserve
  durable Knowledge, matching existing result-content independence.
- [x] Add nullable document links to flashcard sets/jobs as required by the chosen
  association. Preserve `source_pdf_name`; historical jobs/sets need no document.
- [x] Define `ON DELETE` behavior: Subject/account ownership cascades Knowledge;
  document deletion removes its pages/chunks/index jobs and detaches surviving
  job/set links, preserving flashcards. Job-history deletion preserves Knowledge.
- [x] Enforce subject consistency across document↔page/chunk, document↔job/set,
  and later thread/message/answer/citation associations using DB contracts.
- [x] Add reviewed Subject/document/revision/vector/FTS indexes and check constraints.
- [x] Implement new migrations, portable offline models and PostgreSQL constraints/
  cascades/head/drift/upgrade/downgrade/re-upgrade checks on disposable data.

### Acceptance

- [x] Ready-but-unpublished Knowledge is excluded from the eligible-record
  predicate; later student retrieval/citation queries must enforce this and
  current principal/Subject authorization inside SQL.
- [x] Ownership/FK mismatch/deletion tests pass; historical flashcards still work.
- [x] Privacy disclosure/export/delete design and G2/G4 outcomes precede writes.

### Phase 12–13 checkpoint

The mandatory PostgreSQL 16.15/pgvector 0.8.6 image and `0009` extension
revision passed exact-image security/SBOM, disposable migration/head/drift,
RAG-off journey and legacy-volume logical-recovery checks. Phase 13 then added
private Knowledge models and the `0010` schema. Its offline backend suite
passed (620 tests), as did 66 PostgreSQL contracts, Mailpit and encrypted SMTP
checks, the deterministic browser/API/worker journey, image builds/smokes,
security scans, context and CI structure checks. The operator-authorized
legacy local database volume was replaced with an empty Compose-labeled volume;
the application was not deployed to it. The private root `.env` was migrated
from legacy AI key names without disclosing or changing configured values;
name-only preflight and Compose configuration validation passed. Full commands,
identities, skipped gates and limits are in the
[dated closure record](.agent/logs/2026-09-18/2026-09-18-rag-foundation-and-knowledge-schema.md).
Capture, indexing and internal retrieval are complete through Phase 16. Ask AI
jobs, chat/UI, full evaluation and release work remain Phases 17–21.

---

## Phase 14 — Integrate Knowledge capture into bounded PDF preparation

```text
Reserved/uploaded PDF → temporary encrypted source → bounded PDFProcessor
                                                   ↓
                                            ExtractedDocument
                                                   ↓
                                       shared page-aware preparation
                                           ┌───────┴────────┐
                                           ↓                ↓
                               fenced Knowledge capture   full-document
                               + durable indexing enqueue flashcard pipeline
```

### Shared preparation and identity

- [x] Keep existing PDF/OCR subprocess/resource limits and `ExtractedDocument`.
- [x] Introduce the smallest preparation seam to chunk once and allow validated
  precomputed chunks into the existing graph/pipeline caller boundary.
- [x] Retain page/section/local server-issued chunk IDs and map them explicitly
  to persistent document-scoped UUIDs; do not replace flashcard candidate IDs
  with UUIDs that violate the current candidate contract.
- [x] Preserve chunk-size/overlap and flashcard allocation/packing/grounding against
  the quality-workstream baseline. Later RAG-specific tuning cannot silently
  change flashcard preparation.

### Independent transaction and recovery

- [x] After valid extraction/preparation, use a short transaction to recheck lease,
  cancellation, ownership and capture eligibility, persist complete pages/chunks
  and enqueue indexing atomically, before ordinary source cleanup.
- [x] Keep capture independent of exact-card-count success. Do not implement it
  only in flashcard `_finish_success()` or wait for embeddings inside its result
  transaction. Existing set/cards/status/telemetry/source cleanup remain atomic.
- [x] Replay an existing capture on retries/crash recovery using stable identity;
  stale workers cannot write, duplicate documents or resurrect deleted revisions.
- [x] Isolate RAG-specific capture/index failures from successful flashcard output.
  Persist a safe independent outcome where possible; if source cleanup removes
  the only uncaptured PDF, report the approved reupload/recovery limitation.
- [x] Flashcard failure after capture may leave valid private Knowledge. Invalid/
  unreadable PDFs never create usable Knowledge.
- [x] Apply G3 after-capture cancellation semantics explicitly; original temporary
  source cleanup/retention policy continues without permanent PDF retention.
- [x] Apply G4 knowledge-only upload or deliberate regeneration contract using
  bounded authorized admission, separate quotas and transient source cleanup.

### Acceptance

- [x] A normal instructor PDF upload can produce flashcards and private Knowledge
  through one extraction/preparation pass with no required embedding wait.
- [x] Test crash after capture/before generation, capture rollback/failure, manual
  retry, source cleanup, cancellation and lost lease/deletion races.
- [x] Verify PDF/OCR/generation contracts, offline backend and applicable PostgreSQL
  persistence plus deterministic journey checks for changed cross-stack behavior.

Phase 14 closed on 2026-09-19. The implementation and exact verification evidence
are recorded in the [Phase 14–16 closure record](.agent/logs/2026-09-19/2026-09-19-rag-capture-index-retrieval.md).

---

## Phase 15 — Embedding and durable Knowledge indexing

### Dedicated embedding contract

```text
EmbeddingProvider
  embed_documents(...)
  embed_query(...)
```

- [x] Keep embeddings separate from the structured-generation provider contract.
- [x] Implement the reviewed `RAG_EMBEDDING_*` profile and selected G5 provider,
  document/query task compatibility, dimensions and representation.
- [x] Snapshot embedding-space identity, including provider/model/version/task
  modes/dimensions; matching dimensions alone do not make vectors comparable.
- [x] Validate result count/order, finite numeric values, dimensions and metric
  suitability before persistence; bound payload/output size and batch limits.
- [x] Apply one bounded retry/error owner, timeout/rate/token/cost controls and
  content-free per-job telemetry. No provider credentials or calls in API.

### Durable indexing workflow

- [x] Implement claim/heartbeat/cancellation/recovery operations using the durable
  indexing-job schema created in Phase 13 and enqueued by Phase 14.
- [x] Race-protect queue/active/storage admission, hashed logical retry identity
  and changed-payload conflicts; one revision has one active logical indexing job.
- [x] Batch embeddings and persist staged vectors/lexical indexes with fencing.
  Mark the active revision ready only when complete indexing succeeds atomically.
- [x] Keep reindex/reembedding idempotent, revision-aware and rebuildable from
  canonical pages without PDF reupload. Stage a new compatible space/corpus and
  cut over atomically; failed reindex preserves the prior usable active revision.
- [x] Define manual retry versus bounded infrastructure/dead-lease recovery;
  handled provider failures/timeouts do not automatically replay expensive work.
- [x] Document deletion/unpublication/cancellation and corpus fences invalidate
  stale claims; no worker can resurrect removed data or publish it.
- [x] Choose cosine representation/index only after reviewing selected dimensions
  and current pgvector index limits; exact search remains an evaluation baseline.

### Execution and acceptance

- [x] Reuse existing worker lease/heartbeat/shutdown primitives with independent
  generation/index/answer lanes, reserved capacity and G6 credential/quota policy.
- [x] Add fixed worker kinds/health/table constraints and safe diagnostic codes.
- [x] Verify RAG runs when flashcard AI is disabled, flashcards run with RAG off,
  disabled lanes remain bounded/healthy and RAG cannot starve generation.
- [x] Test partial batch failure, crashes, duplicate retries, stale claim commits,
  deletion/cancellation, compatible cutover and actual PostgreSQL vector queries.

Phase 15 closed on 2026-09-19 with exact cosine search as the reviewed baseline;
Phase 19 subsequently measured the authored corpus and retained exact search
without ANN because no reviewed recall/latency evidence justified it. Reindexing
reconstructs bounded chunks from canonical stored pages, so no raw PDF is needed.

---

## Phase 16 — Authorized Subject-scoped hybrid retrieval

Create a reusable `KnowledgeRetriever` carrying a trusted principal/access context,
actual Subject, bounded query, optional authorized document IDs, active revision
and bounded limit. An LLM-generated or request-supplied Subject ID is not authority.

```text
Authorized question/context → worker query embedding
                                   ↓
                        Subject/visibility/revision filters
                          ┌────────┴─────────┐
                          ↓                  ↓
                     vector search      PostgreSQL FTS
                          └────────┬─────────┘
                                   ↓
                       bounded fusion/deduplication
                                   ↓
                         supported evidence chunks
```

- [x] Instructor must own Subject; student must be enrolled and may retrieve only
  reviewed/published, ready, active Knowledge. Apply current G2 access policy.
- [x] Apply Subject/document/publication/ready/active-space filters inside both SQL
  queries and any candidate CTE, never global application retrieval then filtering.
- [x] Query embeddings execute in the authorized worker; API-facing boundaries
  enqueue/poll and do not acquire provider keys to call a semantic retriever.
- [x] Use bounded vector and lexical candidate sets, explicit FTS configuration,
  safe parameterized query construction and deterministic tie ordering.
- [x] Fuse/rank and deduplicate candidates/overlap, bound top-K/context tokens and
  define calibrated relevance/insufficiency behavior from the corpus.
- [x] Compare approximate filtered recall against exact Subject-filtered queries.
  Document measured iterative-scan/fallback settings; index planner behavior
  never permits removing authorization predicates.
- [x] Return server-derived chunk/document/title/page/section/revision/content and
  defined score semantics; citation/source reads separately authorize access.
- [x] Reject incompatible query/document embedding spaces instead of comparing
  mixed vectors. Dedicated reranker remains deferred unless evaluation requires it.

### Acceptance

- [x] Cross-Subject, unpublished, not-ready, guessed document/chunk and inactive
  revision queries cannot expose content. Bound document-selection validation.
- [x] Retrieval/FTS/filtered-recall and empty-evidence corpus checks pass with
  deterministic offline embeddings and real disposable PostgreSQL.

Phase 16 closed on 2026-09-19. Both exact-vector and FTS channels keep access and
eligibility predicates inside SQL. Because the approved G5 execution choice ships
no approximate index, approximate-versus-exact recall and iterative-scan tuning are
not applicable to this baseline. Phase 19 confirmed that decision and preserves
exact search as the required comparison baseline before any future ANN use.

---

## Phase 17 — Subject Ask AI backend and durable answer jobs

### Conversations and authorization

- [x] Add `rag_threads`, `rag_messages`, `rag_message_sources`, `rag_answer_jobs`.
- [x] Each thread belongs to one user and Subject; messages/history are private
  under G2. Never embed chat history into shared document chunks.
- [x] Enforce same-Subject/thread/message/job/source integrity in the database;
  citations relate to exact document/chunk revisions with approved deletion rules.
- [x] Authorize every create/read/history/poll/retry/cancel/delete/source endpoint
  using authenticated user, actual thread owner and current Subject access.
- [x] Recheck enrollment/role/session-related authorization, current publication
  and active corpus eligibility before costly work and final commit. Revoked/
  unpublished/deleted state cancels or refuses stale results.
- [x] Recheck current principal access and resolved G2 visibility/revision policy
  on every history/source read, including any narrowly authorized retained
  historical version; retention alone never grants access.
- [x] Bound question/answer/message/thread/history lengths and assemble only
  authorized context within token limits; follow-up resolution is bounded and
  cannot choose a different Subject or treat chat as trusted instructions.

### Answer flow and support validation

```text
Question → current authorization + bounded durable admission
         → answer job → valid fenced worker claim
         → bounded follow-up context → authorized hybrid retrieval
         → grounded structured answer → support/citation checks
         → fenced atomic answer + sources + terminal job status
```

- [x] Default to course materials only; abstain clearly when evidence is insufficient.
  Do not silently substitute unrestricted general knowledge.
- [x] Use strict structured output with explicit answer/abstention outcome and
  bounded claim/evidence associations or supporting quote spans, alongside cited
  chunk IDs. Final field design is reviewed with the corpus before implementation.
- [x] Validate citations against the exact retrieved, authorized active revision;
  reject unknown/unretrieved/fabricated IDs, duplicate/over-limit references and
  quotes absent from the trusted chunk. Derive titles/pages/sections server-side.
- [x] Evaluate semantic claim support and unsupported answers separately. Valid
  IDs/quote containment do not prove arbitrary prose semantically true.
- [x] Treat PDF text, summaries, questions, chat and model output as untrusted data;
  preserve system boundaries and no model-directed configuration/tools/access.

### Admission, fencing and lifecycle

- [x] Separate student Ask AI quotas from flashcard quotas; define shared provider
  bucket usage for answer and query-embedding calls.
- [x] Race-protect per-user/deployment queue, active-job, permanent chat storage,
  daily usage and token/time/cost caps; stable hashed idempotency and payload
  conflicts cover reservation and retries.
- [x] Use complete durable states, leases/heartbeat/claim tokens, cancellation,
  attempts/deadlines and safe errors; one logical answer job commits at most one
  answer with sources/status atomically, not exactly one remote execution.
- [x] Keep handled provider/timeouts manually retryable under bounds, separate
  infrastructure/dead-lease recovery and graceful shutdown guarantees.
- [x] Implement G2 answer/history invalidation/redaction or tightly authorized
  version/tombstone policy; FK cleanup alone is not content deletion. Corpus
  fences prevent stale indexing/answer writes after deletion/unpublication.

### Acceptance

- [x] Test own-thread/access controls on every endpoint, revoked access while
  queued/running, visibility races, prompt injection, abstention and citation support.
- [x] Test reservation/retry conflicts, quota races, stale claims, crash/deadline/
  cancellation and atomic rollback with no duplicate logical answer.

Phase 17 closed on 2026-09-19. Private Subject-scoped conversations, API
admission/lifecycle, a separate query/answer worker, strict grounded claims,
separate semantic-support validation, exact active citations, G2 redaction and
90-day retention are implemented at Alembic head `20260919_0012`. Admission
also enforces per-user and deployment thread/message storage bounds while
reserving future answer rows. Offline and
disposable PostgreSQL suites cover every endpoint, access revocation, provider
boundaries, concurrent admission, migration reversal and stale-claim fencing.
That Phase 17 closure did not claim live provider calls or frontend Ask AI UI;
Phase 18 subsequently completed the frontend while live calls remain separately
authorization-gated.

---

## Phase 18 — Subject Knowledge and Ask AI frontend

### Instructor Knowledge area

- [x] Add a Knowledge area while retaining normal Generate Set → Upload PDF flow.
- [x] Show independent capture/index/revision and review/publication states, with
  fixed safe errors and recovery limitations.
- [x] Add instructor review/publish/unpublish, failed indexing retry and removal;
  indexing never publishes automatically and document deletion preserves cards.
- [x] Apply the chosen knowledge-only reupload/version UX; distinguish rebuilding
  persisted pages from reuploading a lecture whose raw source no longer exists.

### Student Ask AI and citations

- [x] Add Subject-level own thread/message UI with bounded follow-ups and history.
- [x] Show queued/running/completed/abstained/failed/cancelled/unavailable states,
  including no published Knowledge and access/revision changes.
- [x] Recover jobs/history on reload; nonoverlapping cancellable polling and stable
  retry operation identity prevent duplicate questions/answers and stale UI writes.
- [x] Render model text safely; no raw HTML or unsafe links become trusted UI.
- [x] Use accessible citation chips with server-derived document/page/section and
  authorized extracted-evidence access, for example `Lecture 05 · p.17`.
- [x] No PDF viewer: raw PDFs are not retained. Deleted/unpublished/history sources
  follow G2, with clear unavailable/redacted states rather than leaked snippets.
- [x] Put English copy in `frontend/src/i18n/en.ts`; keep typed API services without
  `any`, focus/keyboard/dialog/live regions, reduced motion, mobile targets and
  no horizontal overflow. Instructor Ask AI scope follows G2.

### Acceptance

- [x] Complete frontend gate, accessibility/responsive/keyboard/reload/retry/error/
  abstention and unsafe-content contracts pass with deterministic fixtures.
- [x] Cross-stack journey independently publishes Knowledge before student Ask AI;
  flashcard publication alone cannot unlock it.

Phase 18 closed on 2026-09-19. Instructor Knowledge management and principal-
private Ask AI are implemented with typed services, safe model-text rendering,
current authorized evidence dialogs, reload-safe durable job recovery, stable
logical retry identity, abortable nonoverlapping polling, accessibility and
mobile contracts. The complete frontend gate passed 56 Chromium cases with one
separately gated live-password skip, and the disposable real journey proved
that set publication alone leaves Ask AI unavailable before independent
Knowledge review/publication.

---

## Phase 19 — Retrieval and RAG evaluation

Extend the deterministic corpus established in Phase 12; its criteria precede
retrieval/index/prompt tuning. Use authored materials, no private lecture/chat
content in repository fixtures and no paid call in normal CI.

### Cases

- [x] Direct facts, semantic/paraphrased questions, exact technical terms, similar
  concepts across lectures, multi-page topics and overlapping chunks.
- [x] Bounded follow-ups, ambiguous/unsupported queries, empty evidence and
  conflicting/insufficient materials with explicit abstention.
- [x] Lecture/chat prompt injection, cross-Subject IDs and guessed source IDs.
- [x] Ready-but-unpublished documents, access revocation, corpus/model mismatch,
  document unpublish/delete/reindex while queued or running and safe history reads.
- [x] Real but unrelated citations and unsupported claims that pass ID checks.

### Measurements and tuning

- [x] Set reviewed corpus-specific thresholds for recall@K/ranking, source/claim
  support, unsupported-answer/abstention behavior, citation validity, latency and
  embedding/answer usage/cost. Cross-Subject/private-content exposure must be zero.
- [x] Measure empty retrieval, filtered ANN recall against exact search, overlap
  diversity, batch/index throughput and answer history-context consumption.
- [x] Tune top-K, fusion, threshold and context only from measured evidence.
- [x] Change chunk settings only if evaluation demonstrates underperformance;
  isolate/version any RAG-specific change and preserve flashcard regression baseline.
- [x] Add a reranker only with evaluation evidence and a separately reviewed scope.
- [x] Live deployment-model evaluation has separate explicit authorization and
  endpoint/model/price/call/token/time/cost bounds; offline results do not establish
  current remote model behavior or provider billing completeness.

### Acceptance

- [x] Deterministic retrieval/support/security corpus passes reviewed criteria;
  feasible queries answer with traceable support and unsupported queries abstain.
- [x] Record measured choices and limits; no quality/coverage/security budgets are
  weakened simply to obtain a pass.

Phase 19 closed on 2026-09-19. The v2 authored corpus, deterministic metric
evaluator and actual PostgreSQL exact pgvector plus `simple` FTS evaluation
passed the reviewed recall/ranking, support/abstention/citation, exposure,
overlap, latency, throughput, history and provider-stage bounds. No ANN index
ships, so filtered ANN recall remains explicitly not applicable; exact search
is the comparison baseline. The evidence retained top-5/RRF/similarity/context/
shared chunking and did not justify a reranker. The bounded three-call live
harness is implemented and guard-tested, but no paid live run was authorized.
See [evaluation evidence](docs/RAG_EVALUATION.md) and the
[dated closure log](.agent/logs/2026-09-19/2026-09-19-rag-frontend-and-evaluation.md).

---

## Phase 20 — Integrated regression, security and CI gate

Every preceding phase runs applicable checks from [TESTING.md](docs/TESTING.md).
This phase is final integration verification, not the first time tests are added.

### Existing gates

- [x] Offline backend, AI/provider/governor and PDF/OCR suites.
- [x] Disposable PostgreSQL head/drift/constraints/races, full upgrade/downgrade/
  re-upgrade; affected Mailpit/TLS SMTP/startup suites with reviewed DB runtime.
- [x] Complete frontend check, existing instructor/student journey and accessibility.
- [x] Runtime/images/dependency/security/secret/SBOM/CI contracts, including the
  reviewed database artifact; context links and migration history preserved.

### New contracts

- [x] Hard rename/removed-key fail-fast, empty/process/root precedence, independent
  feature/provider combinations and worker/browser credential boundaries.
- [x] Actual vector/lexical queries, dimension/task/model-space validation,
  filtered recall, revision cutover and portable offline fixture contracts.
- [x] Subject/owner/enrollment/thread/source authorization, independent Knowledge
  publication, guessed IDs, stale access and exact retrieved-citation membership.
- [x] Claim support/abstention/injection/unsafe rendering, without overstating
  deterministic semantic verification.
- [x] Capture/index/answer idempotency, changed-key payload conflicts, queue/quota/
  storage races, lease fencing, cancellation, atomic rollback and bounded recovery.
- [x] Document/job/set/chat/source integrity and cascades; history retention,
  unpublish/delete/reindex races, private exports/deletion draining and safe diagnostics.

### Deterministic RAG-enabled journey

```text
Instructor → bounded PDF upload → flashcards generated normally
           → private Knowledge indexed → Knowledge reviewed/published separately
           → cards approved/set published → invited/enrolled student
           → Subject Ask AI → grounded answer + verified document/page evidence
```

- [x] Prove data outcomes and source cleanup in a disposable real API/worker/DB
  journey with deterministic answer/embedding providers and no paid calls.
- [x] Include negative ready-but-unpublished and cross-Subject journeys, plus
  independent RAG-off flashcard baseline. Verify fixture/resource cleanup.

---

## Phase 21 — Privacy, operations, recovery and controlled rollout

Privacy design gates precede persistence; this phase verifies actual operator
controls and rollout evidence against Phase 10 contracts.

### Privacy and content lifecycle

- [x] Disclose persistent extracted text/vectors and question/history transfers to
  selected answer/embedding providers before enabled uploads/questions.
- [x] Implement G2 retention/history decisions and bounded operator cleanup;
  explicitly describe deletion limits for backups/provider copies/private exports.
- [x] Never log document/chat/card content, full prompts, embedding payloads,
  model responses, credentials or private exceptions. No conditional chat exception.
- [x] Extend allowlisted consistent-snapshot account exports: instructor-owned
  Knowledge and only a user's own conversations; exclude other students' chats.
- [x] Extend account/Subject/document deletion locks/refusal/cascades and writer/
  worker drain instructions to active capture/index/answer work. Verify deletion
  cannot resurrect content or unintentionally delete surviving flashcards.
- [x] Apply permanent Knowledge/chat capacity and count limits plus transactional
  fixed-field audits for publication/unpublication/removal and privileged operations.

### Diagnostics and recovery

- [x] Extend safe allowlisted error/event enums, worker kinds/table constraints/
  health probes, request/job correlation and operator-only metrics.
- [x] Track queue depth, capture/index failures, throughput/latency, retrieval/
  answer latency, rejection/abstention outcomes and per-profile physical calls/
  retries/tokens/cost with documented billing/retention limitations.
- [x] Define healthy disabled lanes and stalled/dead workers without claiming
  provider availability from a heartbeat.
- [x] Update backup/restore guidance and rehearsal with populated page/chunk/vector/
  conversation/citation data; verify active revisions, extension version/indexes,
  retrieval and access isolation after restore on a separate empty volume.
- [x] Update context/maps/MOCs/architecture/ADRs, configuration/privacy/AI/DB/
  deployment/testing/runtime/accessibility guides and dated evidence with actual
  implemented behavior. Update milestone/changelog status only when achieved.

### Rollout

- [x] Ship with `RAG_ENABLED=false`; verify off-path preserves flashcards and
  does not accidentally capture/retrieve new RAG content or erase existing data.
- [x] Verify backup, approved installation support and definitive config migration;
  drain writers/workers, migrate and verify all heads before restoring admission.
- [x] Run complete offline/service/frontend/journey/security and populated recovery
  gates; label skipped/aborted/gated checks as non-evidence.
- [x] Enable in a controlled environment, verify publication/access boundaries,
  capacity/quota fairness and evaluate several authorized Subjects under separately
  approved live spending limits if external providers are used.
- [x] Confirm the self-hosted production contract: Cardchemy has no centralized
  production deployment; each operator enables RAG only after their applicable
  evaluation/operator gates and follows the documented reversible feature-disable/
  drain procedure that preserves durable data. Schema/data rollback still needs
  explicit authorization and verified recovery.
- [x] Record the operator-reported release-specific Windows/browser/Narrator
  assistive-technology validation as passed; exact version identifiers were not
  supplied and are not inferred.

Phase 20 and the Phase 21 implementation/offline-controlled-environment scope,
including separately authorized bounded live Gemini evaluation, closed on
2026-09-20. On 2026-09-21 the operator resolved the remaining rollout decisions:
there is no centrally operated production target, and the release-specific human
Windows/browser/Narrator validation passed. This records a self-hosted release
contract and human result; it does not infer a central deployment from local or
provider-test evidence. See the
[release closure record](.agent/logs/2026-09-21/2026-09-21-rag-release-closure.md).

---

## Existing data and backfill policy

Historical PDFs cannot automatically become full Knowledge because temporary
sources are intentionally deleted after generation.

- [x] Existing cards/sets continue to work with nullable document links.
- [x] Do not reconstruct lecture corpora from card snippets or fabricate old pages.
- [x] Instructor reuploads an old lecture only when they want Knowledge; G4 states
  explicitly whether this is knowledge-only or also creates a new generation job.
- [x] Define within-Subject duplicate/version handling without exposing another
  Subject's hashes/existence or deduplicating across authorization boundaries.
- [x] New enabled uploads may capture private Knowledge automatically; students
  gain access only after independent instructor review/publication and ready state.
- [x] Reindex captured pages without reupload; uncaptured/deleted raw sources cannot
  be recovered by implying they remain archived.

## Explicitly outside RAG V1

- No dedicated vector database, Redis/Celery or unrelated infrastructure stack.
- No permanent raw-PDF retention or PDF source viewer.
- No vector-search replacement of full-document flashcard generation.
- No chat-history embeddings in shared Subject Knowledge.
- No automatic old-PDF backfill or global cross-Subject Knowledge search.
- No dedicated reranker without measured need and approved scope.
- No implicit model/key fallback, unrestricted general-knowledge answer mode or
  instructor access to student chats merely through Subject ownership.

## Final target architecture

```text
Instructor PDF → temporary encrypted source → bounded extraction/preparation
                                                │
                        ┌───────────────────────┴────────────────────┐
                        ↓                                            ↓
              full-document flashcard pipeline          fenced private Knowledge
              FLASHCARD_AI_*                            pages/chunks + index job
                        ↓                                            ↓
              validated complete draft set              RAG_EMBEDDING_* worker
                        ↓                                            ↓
              card approval/set publication             PostgreSQL + pgvector/FTS
                                                                     │
                                                        Knowledge review/publication
                                                                     │
Enrolled user's own Subject conversation → durable authorized answer job
                                                                     ↓
                                      worker query embedding + filtered hybrid retrieval
                                                                     ↓
                                                   RAG_AI_* grounded answer
                                                                     ↓
                                        support/revision/access checks + atomic answer/sources
```

## Definition of done

- [x] Quality baseline/refined prompts are measured; legitimate insufficient-card
  failure, exact target and strict atomic flashcard contracts are preserved.
- [x] Definitive configuration migration covers all old names/consumers with safe
  fail-fast behavior, operator instructions and unchanged installation secrets.
- [x] One new generation upload can become flashcards and independently persistent
  private Knowledge; capture/index failure cannot break successful flashcards.
- [x] Temporary PDF lifecycle remains intact; no permanent raw storage is introduced.
- [x] PostgreSQL/pgvector support and exact artifacts are verified across every
  declared runtime/test/recovery consumer, including the RAG-off installation contract.
- [x] Independent profile/worker lanes respect actual provider quota boundaries;
  snapshots, bounded retries/deadlines/idempotency/fencing/cancellation are verified.
- [x] New retrieval/answers/citations use authorized published active revisions;
  history/source reads enforce current Subject/principal access and resolved G2
  visibility/revision policy. Knowledge readiness alone never grants student access.
- [x] Answers have backend-validated evidence relationships and measured support/
  abstention behavior; fabricated or unrelated citations cannot establish success.
- [x] Conversations remain separate/private; deletion/unpublish/reindex/history,
  permanent quotas and operator export/delete/retention contracts are implemented.
- [x] Existing gates, new RAG corpus/security/race tests, deterministic journeys and
  populated recovery pass; live checks require their separate explicit authorization.
- [ ] All blocking gates are resolved, relevant context/evidence is current and
  planned/implemented/offline/live/production claims remain distinct.
- [x] `docker compose up` from a fresh clone starts the full application with no source edits, no insecure default credentials, and a tested upgrade/backup path.
- [x] All tests pass including live AI tests.

The remaining definition-of-done gate is intentionally not marked complete
until the merged protected-main source passes hosted Linux CI/rehearsal and its
own clean-clone Compose start. The two operator-owned rollout items are resolved:
the product is distributed for self-hosted Docker operation rather than a central
production deployment, and release-specific Windows/browser/Narrator validation
passed. The bounded live Gemini evaluations and complete offline/service/frontend/
journey suites passed, along with populated pgvector and conversation/citation
restore and deterministic RAG-off/RAG-on journeys.

## Source and command authority

Follow [AGENTS.md](AGENTS.md) and [Start Here](docs/00-START-HERE.md), then the
[project map](PROJECT-MAP.md), [backend MOC](backend/MOC.md) and
[frontend MOC](frontend/MOC.md). Existing architecture and decisions remain
implementation authority until explicitly revised:
[AI flow](docs/architecture/AI-GENERATION-FLOW.md),
[data model](docs/architecture/DATA-MODEL.md),
[ADR index](docs/decisions/ADR-000-INDEX.md),
[configuration](docs/CONFIGURATION.md), [AI evaluation](docs/AI_EVALUATION.md),
[privacy](docs/PRIVACY.md), [observability](docs/OBSERVABILITY.md),
[database operations](docs/DATABASE_OPERATIONS.md),
[runtimes](docs/RUNTIMES.md) and [testing](docs/TESTING.md).
Implementation-time vector/FTS choices must be checked against primary
[pgvector](https://github.com/pgvector/pgvector),
[pgvector Python](https://github.com/pgvector/pgvector-python) and
[PostgreSQL 16 documentation](https://www.postgresql.org/docs/16/index.html).
