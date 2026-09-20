# Changelog

All notable changes are recorded here. This project follows Semantic Versioning
and the Keep a Changelog structure.

## [Unreleased]

- Aligned coupled frontend dependency upgrades (Vite 8/React plugin 6, ESLint 10
  and Vitest/coverage 5), with the declared npm resolver in the Docker builder.
  Route loaders cancel old requests and hide previous Subject/session data;
  generation polling preserves Subject scope through failures and late retries.

- Upgraded bcrypt to 5.0.0 and replaced Passlib with direct bcrypt while
  preserving current full-password v2 hashes, historic v1 wrappers and legacy
  raw bcrypt verification. Stored password records require no migration.

- Hard-renamed the flashcard profile to `FLASHCARD_AI_*`, rejected nonempty
  legacy names and added independent disabled-by-default answer/embedding
  profiles with explicit worker quota ownership. Existing operators must follow
  the [configuration migration guide](docs/AI_PROFILE_MIGRATION.md).
- Added mandatory PostgreSQL 16/pgvector 0.8.6 foundation with a reviewed,
  scanned Alpine build, fail-closed legacy-volume guard and separate ICU logical
  restore procedure. Existing installations must follow
  [database operations](docs/DATABASE_OPERATIONS.md) before migration.
- Added private Subject Knowledge document/content/index revisions, bounded
  page/chunk/vector storage, aggregate reservations, publication eligibility,
  durable index jobs and optional generation/set links.
- Added one-pass Knowledge capture to normal generation, a separately admitted
  Knowledge-only upload contract, explicit local-to-persistent chunk identity,
  safe independent capture outcomes and cancellation/source cleanup semantics.
- Added isolated embedding/index and answer workers with native Gemini
  `embedContent`/structured-answer support, role-specific task modes, strict vector
  validation, bounded retry/rate/token/cost ownership, fenced batch persistence,
  dead-lease recovery, rebuildable staged indexes and all-or-nothing embedding-
  space cutover.
- Added reusable worker-only Subject-authorized hybrid retrieval using exact
  cosine search plus PostgreSQL `simple` FTS, deterministic reciprocal-rank
  fusion, overlap/context bounds and separately reauthorized source reads.
- Added private per-user Subject Ask AI threads and durable answer jobs with
  separate race-safe quotas, hashed idempotency, bounded retry/cancel/lease
  lifecycle, query embedding in an isolated answer worker, course-only
  retrieval, strict claim/quote citations, a separate semantic support pass,
  server-derived source metadata and fixed abstention. Current access,
  publication, corpus and session state are rechecked before provider stages and
  atomic completion; 90-day retention and G2 reads hide answers whose evidence
  is no longer current.
- Added typed instructor Subject Knowledge management and private Subject Ask AI
  interfaces with explicit capture/index/review/publication states, persisted-
  page index retry versus PDF reupload guidance, accessible evidence dialogs,
  reload-safe job recovery, stable question retry identity, safe text rendering
  and responsive keyboard/mobile contracts.
- Added the authored RAG evaluation v2 corpus and reviewed recall/ranking,
  support/abstention/citation, exposure, overlap, exact-query latency, indexing
  throughput, history and provider-stage gates. Exact pgvector plus PostgreSQL
  FTS met the criteria, so top-5/RRF/shared chunking remain and no ANN index or
  reranker was added. A three-call, USD 0.04 live RAG harness is separately
  authorization-gated and was not run.
- Completed Phase 20/21 offline integration and operational controls: native
  Gemini profile disclosure, request/job correlation, Knowledge lifecycle audits,
  own-only export and guarded deletion, 90-day conversation cleanup, expanded
  content-free RAG metrics/health, and populated pgvector/conversation/citation
  recovery. Paid live AI, production enablement and release-specific spoken
  assistive-technology validation remain separately gated and are not claimed.
- Refined versioned flashcard and summary prompts with bounded untrusted
  refill exclusions, fixed content-free quality diagnostics and concurrent
  request-budget reservations. Strict grounding, duplicate rules, output caps
  and exact-count atomic results remain enforced; authored offline comparisons
  are separate from instructor judgment and real-model evaluation.
- Added actual authenticated local STARTTLS/implicit-TLS email verification
  and a clean-machine production-profile installation/backup/restore rehearsal.
- Made the database healthcheck use internal TCP so the official PostgreSQL
  image's temporary socket-only initialization server cannot release migrations early.
- Kept a real internal health probe on the rehearsal TLS edge for older Compose
  wait compatibility, while preserving certificate-validating HTTPS checks.
- Completed all eleven v1.0 operational readiness checks, including deployment
  on a clean machine with the production profile and separate-volume backup recovery.
  The published version remains 0.1.0.

## [0.1.0] - 2026-09-17

First published release, with keyless-signed GHCR image digests and a signed
checksum inventory covering source, provenance, notes, audits and SBOMs.
The earlier prototype date did not identify a published Git tag or release.

### Cardchemy identity and release readiness

- Added consistent standalone Cardchemy branding, shared accessible wordmark,
  supplied ICO favicon and optimized exports with separate artwork/trademark terms.
- Added Apache-2.0 code licensing, contribution/security/conduct policies,
  issue/PR templates, public roadmap, product screenshots and operating guidance.
- Added a disposable no-quota demonstration and guarded release packaging for
  GitHub Releases and GHCR: scanned Linux/amd64 images, CycloneDX SBOMs,
  source provenance, checksums and keyless Sigstore signatures.
- New installations use Cardchemy names. Existing operators must retain their
  Compose project/database identity, secrets and explicit JWT/cookie settings;
  changing authentication defaults invalidates existing sessions.

### Phase 10 - observability and privacy controls

- Added content-free JSON logs, server-generated request/job correlation,
  centralized safe client errors, private request/queue/job/usage/cost metrics
  and per-worker loop/database health probes.
- Added transactional fixed-field audits for invitations, approval,
  publication, instructor provisioning, account deletion and database role
  changes in Alembic revision `20260917_0008`.
- Added provider-transfer disclosure, configurable bounded metadata retention,
  private account exports and explicit drained-writer account deletion.
  Optional HTTPS aggregate reporting is disabled by default and operator-run.

### Fixed

- Added an explicit non-secret `AI_PROVIDER_ENABLED` admission switch so the
  API can enable PDF generation without receiving provider credentials; the
  generation worker retains the key, validates enabled Gemini configuration at
  startup, and treats the switch as a no-claim cost-control kill switch.
- Made Gemini structured-output schemas use the provider-supported subset,
  preserved clear provider/model failure categories, and bounded transient
  failures to three retries with three-second waits, stage canaries,
  fail-fast sibling cancellation, and worker-wide provider concurrency.

### AI request efficiency

- Kept page/section-grounded logical chunks while packing them into larger
  provider requests, added a one-pack direct-generation fast path, and generated
  up to ten cards per request to reduce RPM pressure without weakening source
  provenance or omitting zero-quota evidence from direct context. Summary
  coverage is server-owned rather than repeated in model output.
- Added a shared worker-wide RPM/input-TPM safety governor that accounts for
  every physical attempt, reconciles successful token usage, and keeps retries
  inside the same quota and delay policy. Whole-job timeouts stop with telemetry
  and manual Retry instead of automatically replaying provider work.
- Persisted estimated and actual provider requests, retries, wait time, cached
  input tokens, and per-stage request counts on durable generation jobs and
  exposed compact request telemetry in the instructor UI.

### Phase 8 - deployment and self-hosting

- Added a generated-secret clean-clone bootstrap, production-shaped Compose
  stack, explicit development/production profiles, private database/API
  networking, and a separately built SPA frontend edge.
- Added multi-stage non-root backend/frontend images, database-aware readiness,
  bounded worker draining, production-closed API docs, strict credentialed CORS,
  dynamic proxy service discovery, and browser security headers.
- Added TLS/reverse-proxy, volume, backup/restore, upgrade, disaster-recovery,
  platform, and image-size guidance with clean-stack, outage, restore, and
  PostgreSQL/Mailpit verification.

### Phase 7 - transactional email delivery

- Replaced request-bound password-reset SMTP with a PostgreSQL transactional
  outbox, lease-based email worker, bounded retries, sanitized delivery state,
  guarded operator recovery, and retention cleanup.
- Added validated SMTP none, STARTTLS, and implicit-TLS modes; safe multipart
  reset, password-change, and student-invitation templates; and recipient-bound
  emailed invitations while preserving copyable invitation links.
- Added a pinned, bounded, loopback-only Mailpit development/test service plus
  PostgreSQL concurrency, Mailpit API, fault-injection, and browser coverage.
- Removed the unused email-verification switch so the documented no-verification
  account contract cannot be partially enabled.

### Phase 6 - reliable and accessible study

- Added durable, per-student idempotency receipts for study answers so rapid
  activation, ambiguous retries, and timer races cannot record one logical
  answer more than once.
- Added deliberate review-all sessions, reliable save retry behavior, exact
  timer cleanup/boundaries, keyboard focus management, reduced-motion support,
  semantic progress values, higher-contrast text cues, and mobile-safe layouts.
- Added automated axe, keyboard, touch, timer, responsive, and accessibility
  browser gates plus the manual assistive-technology release procedure.
- Retired the unused offline-sync endpoint/client and removed PWA/offline claims;
  the responsive web client is explicitly online-first.

### Security

- Added typed JWTs, rotating server-side refresh sessions, reuse detection, and logout revocation.
- Moved refresh tokens to Secure-capable HttpOnly SameSite cookies.
- Consolidated student invitations into a signed, database-backed, single-use flow.
- Added explicit role and study-resource authorization checks.
- Removed reusable instructor registration secrets and added an operator CLI.
- Added a single-use SMTP password-reset flow and shared rate limits.
- Added media/signature validation, hard PDF resource bounds, safe error
  categories, and AES-256-GCM temporary source encryption.

### Added

- Added role-aware frontend routing, recoverable page and mutation error states,
  a wildcard not-found page, and an application error boundary.
- Added a typed English UI catalog with a documented English-only v1
  localization policy.
- Added a Playwright Chromium acceptance suite for authentication races, role
  routing, invitation joins, error recovery, card editing, and progress display.
- Added PostgreSQL-backed generation jobs with leases, bounded workers,
  cancellation, retries with jitter, idempotency keys, quotas, and cleanup.
- Added reload-safe job polling, progress, cancellation, retry, and completed-set
  navigation to the instructor UI.
- Added optional Poppler/Tesseract OCR with explicit build and capacity controls.
- Added strict source-grounded AI contracts with page/section citations,
  hierarchical summaries, deterministic quality checks, near-duplicate
  rejection, exact global card targets, and a fixed offline evaluation corpus.
- Added Gemini and OpenAI-compatible provider adapters with validated model,
  retry, context, concurrency, token, and operator-supplied cost limits.
- Added persisted per-job provider/model, estimated and actual token/cost,
  accepted/rejected card counts, and visible limit reasons.

### Changed

- Replaced untyped frontend API payloads with backend-aligned request and
  response contracts and a validated `VITE_API_URL` client configuration.
- Made refresh, logout, and invitation acceptance safe under concurrent requests
  and React Strict Mode, including existing-student invite sign-in continuity.
- Expanded multiple-choice editing with complete validation, explicit approval,
  and per-card concurrent action state; progress now renders server-owned metrics.
- Added hashed Python lockfiles and documented supported runtime versions.
- Removed unused PWA, query-client, vector, document, and migration dependencies.
- Replaced synchronous request-bound PDF generation with a two-step upload and
  separately deployed generation worker.
- Replaced model confidence approval with deterministic server validation;
  generated cards always require explicit instructor review.
- Replaced character-window processing and the LangChain/LangGraph runtime with
  structure-aware token chunks and a small provider-neutral pipeline.

[Unreleased]: https://github.com/EoCiMrEo/Cardchemy/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/EoCiMrEo/Cardchemy/releases/tag/v0.1.0
