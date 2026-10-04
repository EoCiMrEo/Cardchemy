# Changelog

## Current local Lane 6 result — 2026-10-04

Ask AI is enabled in the retained local installation (verified 2026-10-04). Lane 6 is **7/7 complete**, with default-off fresh
installations and Lane 7's three tasks still unchecked. See the
[actual source-only local closure](.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md), including public 94/99
and private 21/24 useful cards, actual PDF display, retained failures/unknown
costs and matching image/profile/health evidence. This is local activation of
unreleased work, not a new published version or production deployment.
The older dated updates below remain historical.

Current Lane 6 update (2026-10-02): matching dormant v7/visual-v3 and additive
0032 are installed after a restore-verified forward cutover, preserving data,
exact PDFs, configuration and backups. Full offline, PostgreSQL, frontend,
journey, image, browser-PDF and isolated security checks passed. Independent
quality/availability and spoken assistive-technology remain open; Ask and
source judging remain disabled, Lane 6 **3/7**. See the
[current cutover](.agent/logs/2026-10-02/2026-10-02-v7-retained-cutover-and-release-recheck.md)
and [browser/security evidence](.agent/logs/2026-10-02/2026-10-02-v7-pdf-browser-and-security-verification.md).

Earlier Lane 6 update (2026-10-01): matching visual source-navigation v6,
visual contract v2 and additive migration 0031 are implemented and retained
services are healthy with preserved data/configuration. Complete public
calibration reached 89.32% useful cards; independent heldout/private and
release gates remain open, and Ask stays disabled. See the
[verified cutover](.agent/logs/2026-10-01/2026-10-01-visual-v6-matching-contract-and-backup.md)
and [public result](.agent/logs/2026-10-01/2026-10-01-visual-calibration-v5-independent-result.md).

All notable changes are recorded here. This project follows Semantic Versioning
and the Keep a Changelog structure.

## [Unreleased]

- Completed source-only Lane 6 as **7/7 complete** and
  Ask AI is enabled in the retained local installation (verified 2026-10-04). Current v8/visual-v5/admission-v2 on additive head
  0033 returns up to three exact unverified published-PDF page references;
  it makes at most one current-question embedding and one text/PNG source-ID
  judgment, no generated answer/verifier or automatic retry. Fresh installations
  remain default-off. Exact-target generation and an encrypted smaller-target
  choice retain separate validation/privacy/fencing and no-extra-call confirmation.

- Added dormant visual source-navigation v5 and additive migration
  `20261001_0030`: authenticated PDF page rendering in a bounded child,
  published page text plus PNG source-ID input, thinking-inclusive usage
  validation and immutable judge snapshots. The retained installation was
  upgraded after a restore-verified backup; Ask remains disabled pending
  independent quality and release gates.
- Fixed flashcard cancellation arriving between a validated-card shortfall and
  staging the smaller-count choice. Cancellation immediately removes the
  temporary source; expired or replaced worker claims cannot stage cards,
  create a set or replay generation.
- Added dormant v4 source-ID judgment under migration `20260928_0029` for
  source-only Ask research. The completed public Flash-Lite calibration failed
  its no-useful-page gate; Ask remains disabled pending a new independent
  original-PDF quality evaluation and release approval.
- Earlier staged source-only Ask navigation v2 with up to three explicitly unverified
  published-Knowledge PDF page references, bounded local lexical fallback and
  no answer-model or answer-verifier calls. Added encrypted, revision-bound
  original-PDF archives, exact-SHA/page-count attachment for older Knowledge,
  and an authenticated in-app PDF page viewer. Ask remains disabled until the
  displayed-page, access, accessibility and operational release gates pass.
- Fixed the local original-PDF viewer's module-worker MIME response and
  refreshed its immutable worker URL so previously cached responses cannot
  keep the viewer on extracted-text fallback. The viewer now records only
  content-free failure codes.
- Added the staged v7 question/source structure selector and additive `0025`
  canonical-reference policy fence, preserving historical v6 reads. Independent
  sufficiency measurements failed; Ask remains disabled pending a quality pass.
- Added canonical-page references for source-only Ask, retaining exact owning
  headings and bullets that indexed chunks can omit. References distinguish
  page and chunk offsets and are checked against current access, publication
  and revision on commit and read. This remains behind the closed Ask release
  gate while displayed-source quality is evaluated.
- Added a separate, source-labeled **Related published Knowledge** view for
  failed or abstained Ask jobs. It reconstructs at most two exact current
  excerpts from private job-owned source offsets, with no extra provider call
  or change to the verified-answer gate. This behavior is staged pending local
  migration and release checks.
- Added content-free Ask failure, output-finish, retrieval-rank and local
  NLI/QA verdict diagnostics with safe abstention/provider-failure explanations;
  remote request caps and private source checks remain enforced.
- Made flashcard evidence allocation adapt to validated yield within the
  existing request/token/cost bounds. Generation now keeps per-attempt
  validation counts separate from cumulative rejections and cards actually
  persisted.
- Added a finite, encrypted, owner-private choice when a bounded run validates
  fewer distinct cards than requested. The instructor may confirm an exact
  smaller unpublished set without another AI call, or explicitly start a new
  cost-disclosed attempt toward the original count. Pending candidates are
  removed on completion, cancel or expiry; independently reviewed Knowledge
  survives generation cancellation.

- Added optional `gemini-embedding-2` staging with a distinct
  `gemini2_qa_section_v1` representation/task/space identity, ordered native
  content requests without `task_type`, strict vector validation, canonical-page
  reindex and reversible per-Subject cutover. `gemini-embedding-001` remains the
  default and historical spaces are retained without mixing or relabeling.
- Replaced the retired three-call Ask path with the default-off
  `two_request_local_support_v1` policy: at most one query embedding and one
  structured answer with zero automatic retries, followed by pinned local NLI
  and extractive-QA support in a dedicated nonroot distroless Debian 13
  answer-worker image.
  Added policy/cost snapshots, attempt-stage database caps, fail-closed artifact
  verification, subject-accurate profile disclosure and an accessible explicit
  cost confirmation before every manual Retry.

- Added the separate default-off Ask gate, terminal legacy three-call policy
  fence, safe answer-job diagnostics and operator shutdown/enablement procedure.
  Knowledge indexing and authorized private history/source reads retain their
  own access gates.
- Restricted new Flashcard and Ask text work to a versioned, verified five-model
  native Gemini catalog with model-aware thinking/output/context preflight and
  per-job catalog/schema-policy snapshots. Legacy provider/custom endpoint
  settings fail preflight; historical jobs and embedding spaces remain readable
  but are never silently reinterpreted.
- Added server-derived correct-card Progress, attempt Accuracy and distinct
  Attempted metrics beside status-based Mastery, retaining the older cumulative
  correct and attempted-completion API fields. Study shuffles a copy of options
  once per card display and keeps server grading and answer receipts canonical.
- Added a durable, owner-scoped duplicate choice after a bounded Knowledge PDF
  upload. A ready compatible same-Subject revision can be reused without another
  capture/index request; a separate copy follows private review. An unchanged
  explicit revision is a Knowledge no-op. Cancellation ends the entire job and
  retains any previously reused revision.

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
