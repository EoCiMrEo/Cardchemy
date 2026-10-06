# Changelog

All notable changes are recorded here. This project follows Semantic Versioning
and the Keep a Changelog structure. Dated implementation/evaluation chronology
is retained in the [agent log index](.agent/logs/README.md).

## [Unreleased]

### Fixed

- Frontend build/development lock resolves `source-map-js` 1.2.2 after a new
  full-scope npm advisory blocked post-publication CI. Application code and
  signed 0.2.0 release artifacts remain unchanged.

## [0.2.0] - 2026-10-05

### Added

- Revisioned Subject Knowledge with separate capture/index workers, explicit
  review/publication, scoped embedding spaces, encrypted original-PDF archives
  and authenticated in-app PDF page viewing. Students can browse/search current
  published lectures locally, independently of Ask.
- Source-only Ask with principal-private threads and immutable v8/visual-v5/
  admission-v2 jobs: at most one current-question Gemini embedding and one
  Gemini text/PNG source-ID judgment, up to three exact unverified PDF references,
  zero generated answers/verifiers and zero automatic retries. Transient
  embedding failure permits bounded local lexical retrieval; selected candidates
  still require source-ID judgment. Fresh installations remain default-off.
- Strictly bounded literal-subject context for unresolved follow-ups, current
  access/revision/lease checks before dispatch and source reauthorization on read.
- Same-Subject duplicate Knowledge reuse/separate-copy choice and unchanged
  explicit-revision no-op. Adaptive generation can retain fully validated cards
  for an encrypted, expiring exact smaller-count choice without another AI call.
- [Architecture diagrams](docs/diagrams/README.md) for the stack, models, account/
  email flows, generation, Knowledge, Ask, study, operations and signed rollout.

### Changed

- New flashcard text execution uses the native Gemini catalog. Embedding 001 is
  default; optional Embedding 2 remains a distinct staged space. Historical
  provider/job/space snapshots remain readable and execution-fenced.
- Student Progress measures approved cards correct at least once; Accuracy,
  Attempted and status-based Mastery retain separate meanings.
- Organized maintained guides by domain, archived completed trackers,
  consolidated current modules and retired consumed experimental scripts/tests.
  Removed obsolete local-verifier development dependencies; production behavior
  and existing migrations/configuration/data were preserved.

### Fixed

- Preserved cancellation and claim fencing around smaller-card staging, atomic
  results and source cleanup, plus durable retry identities and current PDF
  provenance checks.
- Updated PyJWT to 2.15.0 for the upstream payload-parser advisory while retaining
  verified purpose-scoped HS256 tokens and server-backed rotating sessions.

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

[Unreleased]: https://github.com/EoCiMrEo/Cardchemy/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/EoCiMrEo/Cardchemy/releases/tag/v0.2.0
[0.1.0]: https://github.com/EoCiMrEo/Cardchemy/releases/tag/v0.1.0
