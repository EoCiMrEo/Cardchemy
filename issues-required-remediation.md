# Production and Open-Source Remediation Plan

This document tracks the work required to turn the current MVP into a secure,
reliable, self-hostable open-source product. Complete phases in order unless an
item is explicitly independent.

Priority labels:

- **P0**: release blocker or security/data-integrity risk.
- **P1**: required for a dependable v1.0.
- **P2**: important hardening, maintainability, or product polish.

## Current baseline

- The main flow exists: PDF upload -> AI generation -> instructor review ->
  publish -> student study -> spaced-repetition progress.
- Backend Docker configuration builds and the application imports successfully.
- Frontend production build currently fails with TypeScript errors.
- Frontend lint currently reports 48 errors and 7 warnings.
- The production npm dependency audit currently reports 5 advisories (4 high,
  1 moderate).
- The repository has no automated unit, integration, or end-to-end test suite.
- `frontend/src/services/api.ts` contains an existing uncommitted change and must
  be preserved while remediation work is performed.

---

## Phase 0 - Establish a clean, reproducible baseline

**Goal:** Make every later change measurable and avoid building v1.0 on an
unclear branch or dependency state.

- [x] **P0** Integrate the current feature branch into the intended release
  branch and verify all expected features are present.
- [x] **P0** Resolve the existing uncommitted `frontend/src/services/api.ts`
  change deliberately; keep its auth-refresh-loop fix and remove trailing
  whitespace.
- [x] **P0** Add an initial changelog and define the versioning strategy
  (Semantic Versioning is recommended).
- [x] **P0** Replace floating Python requirements (`>=`) with a reproducible
  lock/constraints file, including hashes where practical.
- [x] **P1** Confirm the supported Node.js, package-manager, Python, PostgreSQL,
  and Docker versions in one source of truth.
- [x] **P1** Remove or document unused dependencies, including currently unused
  backend packages and frontend packages such as the incomplete offline/PWA
  stack.
- [x] **P1** Separate optional AI integration tests from offline tests so normal
  test runs never spend API quota.
- [x] **P1** Remove API-key fragments from `backend/scripts/test_graph.py` logs.

**Phase complete when:** a clean checkout installs the same dependency versions
on two machines and both machines produce the same build/test result.

---

## Phase 1 - Fix authentication and authorization

**Goal:** Ensure every token and endpoint can perform only its intended action.

### Token security

- [x] **P0** Add an explicit `type=access` claim to access tokens.
- [x] **P0** Require the correct token type in separate access, refresh, and
  invitation verification functions.
- [x] **P0** Prevent refresh tokens from being accepted as Bearer access tokens.
- [x] **P0** Prevent access or invitation tokens from being accepted by the
  refresh endpoint.
- [x] **P0** Stop sending refresh tokens in URL query parameters.
- [x] **P0** Store refresh tokens in Secure, HttpOnly, SameSite cookies or adopt
  an equivalently protected design; avoid long-lived tokens in `localStorage`.
- [x] **P0** Implement refresh-token rotation, reuse detection, logout
  revocation, and server-side session tracking.
- [x] **P1** Add issuer, audience, token ID, issued-at, and not-before validation.
- [x] **P1** Convert malformed UUID/token payload errors into controlled 401/400
  responses rather than internal errors.
- [x] **P1** Add maximum password length and normalized email handling.
- [x] **P1** Add a password-reset flow; decide whether email verification is
  required for the target deployment model.

### Secrets and privileged access

- [x] **P0** Remove the hardcoded JWT secret and all production fallback secrets.
- [x] **P0** Remove the shared hardcoded instructor registration code.
- [x] **P0** Replace the instructor code with a one-time first-admin bootstrap
  command or single-use, auditable invitations.
- [x] **P0** Fail fast at startup when required production secrets are missing or
  use known-insecure defaults.
- [x] **P1** Make `.env` loading independent of the process working directory.
- [x] **P1** Document secret generation and rotation without printing secrets.

### Endpoint authorization

- [x] **P0** Add explicit instructor-only and student-only dependencies.
- [x] **P0** Protect subject, set, generation, review, publish, and study routes
  with the appropriate role checks.
- [x] **P0** Fix `/study/sync` so each card must belong to a published subject in
  which the student is actively enrolled, and the card must be approved.
- [x] **P0** Apply the same enrollment/publish/approval checks to every study and
  progress endpoint.
- [x] **P0** Validate invitation token type, subject, role, expiration, and
  single-use status before creating a user or enrollment.
- [x] **P0** Make registration plus enrollment one atomic transaction.
- [x] **P0** Consolidate the two competing invitation systems into one design.
- [x] **P0** Make invitation consumption and duplicate enrollment race-safe.
- [x] **P1** Bound invitation lifetime and reject zero/negative/extreme values.
- [x] **P1** Rate-limit login, registration, invitation, join, refresh, PDF
  upload, and AI-generation endpoints.

**Phase complete when:** automated tests prove that access, refresh, and invite
tokens are not interchangeable, and users cannot read or mutate another role's
or subject's resources.

---

## Phase 2 - Add database migrations and data integrity

**Goal:** Make schema upgrades and multi-step operations safe and predictable.

- [x] **P0** Create an Alembic baseline for the existing schema.
- [x] **P0** Stop using `Base.metadata.create_all()` as the production migration
  mechanism.
- [x] **P0** Replace the one-off `add_options.py` and `add_time_limit.py` scripts
  with versioned migrations; do not swallow migration failures.
- [x] **P0** Wrap registration/enrollment, invite consumption, generation
  creation, publication, and progress batches in proper transactions.
- [x] **P0** Add database-level foreign-key delete behavior and verify subject,
  invitation, set, card, enrollment, and progress deletion semantics.
- [x] **P0** Add or verify unique constraints for enrollments, progress records,
  invitations, and other get-or-create paths; handle conflict races cleanly.
- [x] **P0** Use timezone-aware UTC columns and datetimes consistently.
- [x] **P1** Add length/range constraints for names, titles, descriptions,
  `time_limit`, `card_count`, invitation lifetime, confidence, quality, and
  pagination limits.
- [x] **P1** Enforce flashcard invariants: non-empty front/back, valid card type,
  sensible option count, unique options, and exactly one correct answer when
  required.
- [x] **P1** Reject contradictory progress inputs such as `is_correct=true` with
  a failing quality grade, or derive correctness server-side.
- [x] **P1** Define one progress model so backend and frontend agree on `new`,
  `learning`, `review`, `mastered`, and completion percentage.
- [x] **P1** Query due cards with indexed filtering, deterministic ordering, and
  database limits instead of loading all cards and slicing in Python.
- [x] **P1** Allow nullable fields such as `time_limit` to be explicitly cleared
  during updates.
- [x] **P1** Prevent publishing an empty set or a subject with no approved cards.
- [x] **P2** Add migration rollback and backup/restore documentation.

**Phase complete when:** a production-like database upgrades from the baseline
to the latest schema, integrity tests pass, and failed multi-step operations
leave no partial records.

---

## Phase 3 - Make PDF generation durable and bounded

**Goal:** Ensure large, malformed, or concurrent uploads cannot block or exhaust
the API service.

- [x] **P0** Validate file signature and media type instead of trusting the
  filename extension.
- [x] **P0** Enforce configurable upload-byte, page-count, extracted-text,
  `card_count`, per-user, and per-deployment limits.
- [x] **P0** Handle encrypted, malformed, empty, and image-only PDFs with clear
  user-facing errors.
- [x] **P0** Move CPU-heavy PDF extraction off the async request event loop.
- [x] **P0** Replace in-request generation with a persistent background-job
  workflow and job states such as queued, running, completed, failed, and
  cancelled.
- [x] **P0** Add bounded worker concurrency, backpressure, timeouts, retries with
  jitter, and failure cleanup.
- [x] **P0** Do not create an empty flashcard set before extraction succeeds, or
  make creation and cleanup transactional.
- [x] **P0** Preserve intentional HTTP errors and never expose raw exceptions or
  stack traces to clients.
- [x] **P1** Add job polling or server-push progress, cancellation, and retry UI.
- [x] **P1** Add idempotency keys so retries cannot create duplicate jobs/sets.
- [x] **P1** Add configurable per-user generation quotas and cost controls.
- [x] **P1** Decide whether source files are retained; if retained, add secure
  storage, retention, deletion, and access-control policies.
- [x] **P2** Add optional OCR for scanned PDFs, with explicit dependency and cost
  documentation.

**Phase complete when:** concurrent large/invalid uploads stay within configured
resource limits, the API remains responsive, and every job reaches a recoverable
terminal state without orphaned data.

---

## Phase 4 - Improve AI output quality, safety, and portability

**Goal:** Produce traceable flashcards whose quality does not rely on the model's
self-reported confidence.

- [x] **P0** Move provider, model, temperature, token, timeout, retry, and
  concurrency settings into validated configuration.
- [x] **P0** Avoid a preview-model-only production dependency; document supported
  stable models and their minimum capabilities.
- [x] **P0** Use structured output with strict server-side validation and reject
  invalid cards rather than silently persisting them.
- [x] **P0** Stop auto-approving solely from model-generated confidence.
- [x] **P1** Chunk by tokens and document structure, retaining page/section
  metadata instead of using raw character windows.
- [x] **P1** Respect the requested target card count globally; do not generate
  3-5 cards for every chunk regardless of the target.
- [x] **P1** Replace first-30,000-character summarization with a hierarchical or
  map-reduce strategy for long documents.
- [x] **P1** Make summary-generation failure visible and recoverable instead of
  silently substituting `No summary available`.
- [x] **P1** Treat document text as untrusted data and add prompt-injection
  boundaries and instructions.
- [x] **P1** Verify every answer/source snippet against extracted content and
  attach a page or section reference.
- [x] **P1** Add a second validation pass or deterministic checks before marking
  a card ready for instructor review.
- [x] **P1** Improve near-duplicate detection beyond exact normalized fronts.
- [x] **P1** Add missing `options` typing to the agent state and align all agent,
  schema, and database card representations.
- [x] **P1** Track estimated tokens/cost and show operators why a job was limited
  or rejected.
- [x] **P2** Add a provider interface so self-hosters can choose Gemini, another
  hosted model, or a local OpenAI-compatible endpoint.
- [x] **P2** Remove pgvector/RAG claims and dependencies until implemented, or
  implement them behind an optional profile with migrations and tests.

**Phase complete when:** a fixed evaluation corpus produces schema-valid,
source-grounded cards with measured quality and bounded cost across supported
models.

---

## Phase 5 - Fix frontend correctness and API architecture

**Goal:** Make the web client build cleanly and behave predictably under errors,
concurrency, and different roles.

- [ ] **P0** Fix all TypeScript build errors and make the production build pass.
- [ ] **P0** Resolve all ESLint errors; document any intentionally retained
  warning with a narrow rule exception.
- [ ] **P0** Replace both hardcoded localhost API URLs with one validated
  `VITE_API_URL` configuration.
- [ ] **P0** Implement a single-flight token refresh flow so simultaneous 401s do
  not trigger competing refresh calls.
- [ ] **P0** Ensure failed refresh clears the session once and cannot enter an
  interceptor loop.
- [ ] **P0** Add role-aware route guards; students must not enter instructor edit
  views and instructors must not accidentally enter student study flows.
- [ ] **P0** Fix `/join` without a token so it never navigates to
  `/register?token=null`.
- [ ] **P0** Make join attempts abortable/idempotent and safe under React Strict
  Mode's repeated effects.
- [ ] **P1** Replace API `any` values with request/response types matching backend
  schemas.
- [ ] **P1** Use the existing query client consistently for caching, retries,
  invalidation, cancellation, and loading/error state, or remove it.
- [ ] **P1** Add useful error states and retry actions instead of blank screens or
  console-only errors.
- [ ] **P1** Add a not-found route and an application error boundary.
- [ ] **P1** Make set editing support multiple-choice options, validate empty
  fields, and stop edits from implicitly approving cards.
- [ ] **P1** Keep unrelated card controls available while one card is being
  edited, or clearly scope the editing lock.
- [ ] **P1** Align frontend progress calculations with the finalized backend
  model.
- [ ] **P2** Decide on localization support; centralize strings before adding
  another language.

**Phase complete when:** typecheck, lint, and production build pass, and all role,
join, error, and refresh flows pass automated browser tests.

---

## Phase 6 - Make study mode reliable, accessible, and responsive

**Goal:** Prevent lost progress and make every core flow usable by keyboard,
screen reader, mobile, and reduced-motion users.

### Study reliability

- [ ] **P0** Ensure every supported card type has a way to answer and advance;
  cards without options/timers must not trap the user.
- [ ] **P0** Add a submission lock/idempotency key so double-clicks and timer
  races cannot record the same answer multiple times.
- [ ] **P0** Fix the timer interval typing, off-by-one behavior, cleanup, and side
  effects currently performed inside state updates.
- [ ] **P0** Do not advance silently when progress saving fails; provide retry or
  queue the update durably.
- [ ] **P1** Either implement the advertised offline outbox/sync behavior or
  remove the PWA/offline claims and unused IndexedDB dependency.
- [ ] **P1** Make `Review Again` start a valid session rather than returning an
  unexpected `All Caught Up` state.

### Accessibility and interaction semantics

- [ ] **P0** Associate all visible labels with their form controls; the login
  password field currently has no accessible label.
- [ ] **P0** Fix the shared Button `asChild` implementation so links and buttons
  are not nested interactive elements.
- [ ] **P1** Give every icon-only action an accessible name.
- [ ] **P1** Replace clickable non-interactive containers in preview/study views
  with keyboard-operable controls.
- [ ] **P1** Add visible focus states and verify complete keyboard navigation.
- [ ] **P1** Respect `prefers-reduced-motion` and avoid essential information that
  depends only on animation or color.
- [ ] **P1** Use mobile-safe viewport sizing and sufficient touch targets.
- [ ] **P1** Make header, email, subject actions, and dialog layouts wrap correctly
  on narrow screens.
- [ ] **P2** Run automated accessibility checks and a manual screen-reader pass in
  CI/release testing.

**Phase complete when:** the full study flow works with keyboard only at a mobile
viewport, accessibility checks have no serious/critical violations, and a
network failure cannot silently lose progress.

---

## Phase 7 - Complete deployment and self-hosting support

**Goal:** Let a new user clone the repository and run a safe, production-like
deployment without editing source code.

- [ ] **P0** Add `.dockerignore` files so local virtual environments, node
  modules, caches, secrets, tests, and build output are not copied into images.
- [ ] **P0** Add a production frontend image/server with SPA fallback routing.
- [ ] **P0** Add the frontend service to Compose and connect it through documented
  internal/public URLs.
- [ ] **P0** Separate development and production Compose profiles.
- [ ] **P0** Disable reload/debug mode and public database ports by default in the
  production profile.
- [ ] **P0** Remove default database passwords and require generated secrets.
- [ ] **P0** Make CORS origins environment-driven; avoid permissive methods and
  headers combined with credentials unless required.
- [ ] **P1** Use multi-stage backend/frontend builds and remove compilers/dev
  packages from runtime images.
- [ ] **P1** Add container health checks that verify database readiness, not only
  that the HTTP process responds.
- [ ] **P1** Decide whether API docs are public in production and make the setting
  configurable.
- [ ] **P1** Add reverse-proxy/TLS guidance and security headers, including CSP,
  frame protection, MIME sniffing protection, and a referrer policy.
- [ ] **P1** Add graceful shutdown and worker/job-draining behavior.
- [ ] **P1** Document data volumes, database backup, restore, upgrade, and disaster
  recovery.
- [ ] **P2** Target a smaller image and publish supported architecture/platform
  information.

**Phase complete when:** `docker compose up` from a fresh clone starts the full
application with no source edits, no insecure default credentials, and a tested
upgrade/backup path.

---

## Phase 8 - Add tests, CI, and supply-chain checks

**Goal:** Prevent security and behavior regressions before merging or releasing.

### Automated tests

- [ ] **P0** Add backend unit tests for token types, token expiry, malformed
  claims, password/auth behavior, invitations, permissions, scheduling, and
  progress calculations.
- [ ] **P0** Add PostgreSQL integration tests for migrations, constraints,
  transactions, cascades, duplicate enrollments, and concurrent updates.
- [ ] **P0** Add PDF tests for valid, empty, encrypted, malformed, oversized,
  scanned, and high-page-count inputs.
- [ ] **P0** Mock the model for normal tests and cover retry, invalid JSON,
  timeout, partial failure, and cancellation paths.
- [ ] **P0** Add frontend component tests for route guards, token refresh, joins,
  card editing, timers, submission locking, and error recovery.
- [ ] **P0** Add end-to-end tests for instructor creation -> generation -> review
  -> publish -> invitation -> student study -> progress.
- [ ] **P1** Add an optional live-model evaluation suite with a strict budget and
  explicit opt-in.

### Continuous integration and dependency safety

- [ ] **P0** Add CI gates for backend tests, frontend typecheck/lint/test/build,
  migration checks, and Docker builds.
- [ ] **P0** Update vulnerable frontend dependencies and make the production audit
  pass or document narrowly accepted exceptions.
- [ ] **P0** Audit fresh locked Python dependencies; assess replacing the
  `python-jose`/`ecdsa` chain if the advisory cannot be remediated.
- [ ] **P1** Add secret scanning, dependency review, container scanning, and a
  generated SBOM for releases.
- [ ] **P1** Configure Dependabot or Renovate with grouped, tested updates.
- [ ] **P1** Add branch protection and require CI before merge.
- [ ] **P2** Add coverage reporting with meaningful thresholds rather than a
  vanity 100% target.

**Phase complete when:** a pull request cannot merge if it breaks the full build,
security boundaries, migrations, or critical user journey.

---

## Phase 9 - Add observability, privacy, and operational controls

**Goal:** Make failures diagnosable without exposing user documents or secrets.

- [ ] **P1** Replace `print` and raw tracebacks with structured logging and log
  levels.
- [ ] **P1** Add request/job correlation IDs and safe error codes returned to the
  client.
- [ ] **P1** Add centralized exception handling and sanitize all client-facing
  error messages.
- [ ] **P1** Record latency, error rate, queue depth, job duration, generated-card
  count, model usage, and estimated cost.
- [ ] **P1** Add readiness/liveness endpoints and database/worker health signals.
- [ ] **P1** Define log redaction rules for tokens, emails, document contents,
  prompts, model responses, and API keys.
- [ ] **P1** Document that extracted document content is sent to Gemini, including
  the provider's role and the deployment operator's responsibilities.
- [ ] **P1** Define retention/deletion/export behavior for accounts, subjects,
  generated cards, progress, jobs, and any retained source files.
- [ ] **P1** Add configurable request, job, and database retention policies.
- [ ] **P2** Add an audit trail for privileged actions such as invitations,
  publication, card approval, and account-role changes.
- [ ] **P2** Add optional error reporting/telemetry that is disabled by default for
  self-hosters and never uploads document content.

**Phase complete when:** operators can diagnose a failed generation from an ID
and metrics without seeing secrets or unnecessary user content.

---

## Phase 10 - Finish the open-source product and rebrand

**Goal:** Publish a trustworthy repository that users can understand, operate,
and contribute to.

- [ ] **P0** Choose and add a license. Consider Apache-2.0 for broad adoption or
  AGPL-3.0 if hosted derivatives should publish their changes.
- [ ] **P0** Add a root README containing product scope, screenshots, architecture,
  prerequisites, quick start, configuration, upgrades, backups, limitations,
  privacy notes, and troubleshooting.
- [ ] **P0** Add complete root/backend/frontend `.env.example` files with safe
  placeholders and comments.
- [ ] **P1** Add `CONTRIBUTING.md`, `SECURITY.md`, Code of Conduct, pull-request
  template, and issue templates.
- [ ] **P1** Document a responsible vulnerability-reporting channel and supported
  release versions.
- [ ] **P1** Rewrite or remove stale `idea.md` claims about Instructor Toolkits,
  RAG/pgvector, Redis/Celery, OCR, PWA/offline, testing, and CI; move unfinished
  ideas into an explicit roadmap.
- [ ] **P1** Replace the Vite template README, favicon, document title, package
  name/version, API metadata, and generic login branding.
- [ ] **P1** Use the selected standalone name consistently in application config,
  Compose, image names, UI, docs, examples, and repository metadata.
- [ ] **P1** Current naming candidate: **Cardchemy**, with the tagline
  **“Turn documents into memory.”** Verify repository/package handles, domains,
  social handles, and trademarks before adopting it.
- [ ] **P1** Add sample data or a demo path that does not require spending real AI
  quota.
- [ ] **P1** Publish signed/tagged releases with release notes, checksums, images,
  and SBOMs.
- [ ] **P2** Add a public roadmap that clearly distinguishes shipped features
  from planned work.

**Phase complete when:** an unfamiliar user can discover, install, secure,
operate, upgrade, and contribute to the project using only repository
documentation.

---

## v1.0 release gate

Do not publish v1.0 until all of the following are true:

- [ ] All P0 items are complete.
- [ ] No known critical/high vulnerability is reachable without a documented,
  time-bounded exception.
- [ ] Authentication and cross-subject authorization tests pass.
- [ ] Database migration, backup, restore, and upgrade tests pass.
- [ ] PDF jobs are bounded, durable, cancellable, and recoverable.
- [ ] Frontend typecheck, lint, tests, accessibility checks, and production build
  pass.
- [ ] A fresh-clone production deployment has been tested on a clean machine.
- [ ] Documentation, license, privacy disclosure, security policy, and release
  artifacts are complete.
- [ ] The end-to-end instructor/student journey passes without manual database or
  source-code changes.
