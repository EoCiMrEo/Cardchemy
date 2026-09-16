# Production and Open-Source Remediation Plan

This document tracks the work required to turn the current MVP into a secure,
reliable, self-hostable open-source product. Complete phases in order unless an
item is explicitly independent.

Priority labels:

- **P0**: release blocker or security/data-integrity risk.
- **P1**: required for a dependable v1.0.
- **P2**: important hardening, maintainability, or product polish.

## Verified baseline and next work (2026-09-16)

- Phases 0-9 are recorded complete. Remaining work is operational hardening
  and open-source release in Phases 10-11.
- The application includes durable PDF-generation and email workers, versioned
  migrations, source-grounded AI generation, provider quota controls, request
  telemetry, and a production-shaped Compose deployment. Root `.env` is the
  sole supported user-managed configuration file.
- Phase 9 verification: 203 offline backend cases pass on hosted Python 3.11
  and 3.13; 21 PostgreSQL contracts plus full migration downgrade/re-upgrade,
  three Mailpit cases, and the real instructor/student journey pass.
- Frontend `npm run check` passes all typechecks/lint, four Node units,
  26 component contracts/coverage, production build and 47 Chromium cases.
  The separate live password-reset case and paid-provider evaluation remain
  explicitly opt-in; no paid AI call was made during Phase 9.
- Fresh full Python/npm dependency audits and Git/history/worktree secret scans
  report no findings. All three final runtime images pass native/auth/PDF/OCR
  probes and HIGH/CRITICAL OS/application scans, including unfixed advisories;
  CycloneDX SBOMs and checksums are retained.
- Browser-compatibility data is current. Emitted JavaScript measures 120,400
  bytes initial gzip, 360,202 bytes largest raw asset and 222,704 bytes total
  gzip, below enforced 130,000/400,000/240,000-byte budgets.
- GitHub main protection requires current-base `ci-required` from Actions app
  15368, including administrators. A controlled coverage failure blocked PR #1;
  repaired hosted run 35129468986 passed every mandatory gate. Full locked
  audits remain mandatory where private-repository native dependency review
  requires an additional GitHub entitlement. Evidence is recorded in
  `.agent/logs/2026-09-16-phase-9-remediation.md`.
- Preserve existing user changes and the real root `.env`. Updating this plan
  does not authorize deleting local environments, data, credentials, or volumes.

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

- [x] **P0** Fix all TypeScript build errors and make the production build pass.
- [x] **P0** Resolve all ESLint errors; document any intentionally retained
  warning with a narrow rule exception.
- [x] **P0** Replace both hardcoded localhost API URLs with one validated
  `VITE_API_URL` configuration.
- [x] **P0** Implement a single-flight token refresh flow so simultaneous 401s do
  not trigger competing refresh calls.
- [x] **P0** Ensure failed refresh clears the session once and cannot enter an
  interceptor loop.
- [x] **P0** Add role-aware route guards; students must not enter instructor edit
  views and instructors must not accidentally enter student study flows.
- [x] **P0** Fix `/join` without a token so it never navigates to
  `/register?token=null`.
- [x] **P0** Make join attempts abortable/idempotent and safe under React Strict
  Mode's repeated effects.
- [x] **P1** Replace API `any` values with request/response types matching backend
  schemas.
- [x] **P1** Use the existing query client consistently for caching, retries,
  invalidation, cancellation, and loading/error state, or remove it.
- [x] **P1** Add useful error states and retry actions instead of blank screens or
  console-only errors.
- [x] **P1** Add a not-found route and an application error boundary.
- [x] **P1** Make set editing support multiple-choice options, validate empty
  fields, and stop edits from implicitly approving cards.
- [x] **P1** Keep unrelated card controls available while one card is being
  edited, or clearly scope the editing lock.
- [x] **P1** Align frontend progress calculations with the finalized backend
  model.
- [x] **P2** Decide on localization support; centralize strings before adding
  another language.

**Phase complete when:** typecheck, lint, and production build pass, and all role,
join, error, and refresh flows pass automated browser tests.

---

## Phase 6 - Make study mode reliable, accessible, and responsive

**Goal:** Prevent lost progress and make every core flow usable by keyboard,
screen reader, mobile, and reduced-motion users.

### Study reliability

- [x] **P0** Ensure every supported card type has a way to answer and advance;
  cards without options/timers must not trap the user.
- [x] **P0** Add a submission lock/idempotency key so double-clicks and timer
  races cannot record the same answer multiple times.
- [x] **P0** Fix the timer interval typing, off-by-one behavior, cleanup, and side
  effects currently performed inside state updates.
- [x] **P0** Do not advance silently when progress saving fails; provide retry or
  queue the update durably.
- [x] **P1** Either implement the advertised offline outbox/sync behavior or
  remove the PWA/offline claims and unused IndexedDB dependency.
- [x] **P1** Make `Review Again` start a valid session rather than returning an
  unexpected `All Caught Up` state.

### Accessibility and interaction semantics

- [x] **P0** Associate all visible labels with their form controls; the login
  password field currently has no accessible label.
- [x] **P0** Fix the shared Button `asChild` implementation so links and buttons
  are not nested interactive elements.
- [x] **P1** Give every icon-only action an accessible name.
- [x] **P1** Replace clickable non-interactive containers in preview/study views
  with keyboard-operable controls.
- [x] **P1** Add visible focus states and verify complete keyboard navigation.
- [x] **P1** Respect `prefers-reduced-motion` and avoid essential information that
  depends only on animation or color.
- [x] **P1** Use mobile-safe viewport sizing and sufficient touch targets.
- [x] **P1** Make header, email, subject actions, and dialog layouts wrap correctly
  on narrow screens.
- [x] **P2** Run automated accessibility checks and a manual screen-reader pass in
  CI/release testing.

**Phase complete when:** the full study flow works with keyboard only at a mobile
viewport, accessibility checks have no serious/critical violations, and a
network failure cannot silently lose progress.

---

## Phase 7 - Complete transactional email and SMTP delivery

**Goal:** Deliver security-sensitive and transactional emails reliably, test
them locally with Mailpit, and remain compatible with standard SMTP providers
in production.

### Local SMTP and configuration

- [x] **P0** Add a pinned Mailpit container to the development/test Compose
  profile with a health check and bounded message storage.
- [x] **P0** Configure local delivery through `mailpit:1025` without SMTP auth or
  TLS; expose only the Mailpit Web UI on loopback port `8025` and keep SMTP
  internal to the Docker network.
- [x] **P0** Pass `SMTP_STARTTLS` through Compose and make SMTP security explicit:
  none for local Mailpit, STARTTLS or implicit TLS for production providers.
- [x] **P0** Validate SMTP host, port, sender, authentication, TLS mode, and
  frontend base URL at startup without logging credentials.
- [x] **P1** Add configurable sender name and reply-to address with validated
  email headers.

### Delivery architecture and templates

- [x] **P0** Refactor the password-reset-only email service into an injectable
  SMTP transport and reusable typed message/template layer.
- [x] **P0** Provide multipart plain-text and accessible HTML templates with
  consistent branding and absolute HTTPS links in production.
- [x] **P0** Queue email through a durable transactional outbox/background worker
  so API requests do not wait for SMTP and database changes cannot succeed
  without the related email being queued.
- [x] **P0** Add bounded delivery timeouts, exponential-backoff retries, maximum
  attempts, idempotency, and duplicate-send protection.
- [x] **P0** Track pending, sent, and failed delivery state plus attempt count and
  timestamps; retain only sanitized provider errors.
- [x] **P0** Preserve account-enumeration resistance while making internal
  delivery failures observable and recoverable.
- [x] **P1** Add retention and cleanup rules for delivered, failed, and expired
  outbox records.

### Transactional email flows

- [x] **P0** Send password-reset messages through the durable delivery path and
  preserve single-use expiration and session revocation behavior.
- [x] **P0** Fully implement optional email verification, including single-use
  expiring tokens and resend limits, or remove the unused configuration flag.
- [x] **P1** Allow instructors to send student invitations by email while keeping
  copyable invitation links available.
- [x] **P1** Send a password-changed security notification that contains no reset
  token or other secret.
- [x] **P1** Keep marketing and non-essential notification email outside the v1.0
  transactional email scope.

### Email testing and documentation

- [x] **P0** Add unit tests for SMTP configuration, address/header safety,
  template rendering, absolute links, and sanitized failures.
- [x] **P0** Add Mailpit API integration tests that verify recipient, subject,
  plain-text/HTML bodies, and reset/invitation links.
- [x] **P0** Add an end-to-end password-reset test: request -> captured email ->
  reset page -> new password succeeds -> old password and reused token fail.
- [x] **P0** Test SMTP timeout, disconnect, authentication/TLS failure, retries,
  terminal failure, and duplicate suppression; use Mailpit fault injection where
  practical.
- [x] **P1** Test the no-email-verification configuration decision and invitation
  delivery, including expired, consumed, malformed, and rate-limited tokens.
- [x] **P1** Verify that credentials, tokens, reset URLs, and message bodies never
  appear in application logs.
- [x] **P1** Document local Mailpit usage separately from production SMTP setup,
  including common port/TLS examples and operator-owned SPF, DKIM, and DMARC
  responsibilities.
- [x] **P1** State clearly that Mailpit captures mail for development/CI and must
  not be used as the production delivery service.

**Phase complete when:** local Compose captures transactional mail in Mailpit,
password reset passes end to end, SMTP failures retry without blocking requests
or sending duplicates, sensitive values stay out of logs, and a self-hoster can
connect a standard production SMTP provider using configuration only.

---

## Phase 8 - Complete deployment and self-hosting support

**Goal:** Let a new user clone the repository and run a safe, production-like
deployment without editing source code.

- [x] **P0** Add `.dockerignore` files so local virtual environments, node
  modules, caches, secrets, tests, and build output are not copied into images.
- [x] **P0** Add a production frontend image/server with SPA fallback routing.
- [x] **P0** Add the frontend service to Compose and connect it through documented
  internal/public URLs.
- [x] **P0** Separate development and production Compose profiles.
- [x] **P0** Disable reload/debug mode and public database ports by default in the
  production profile.
- [x] **P0** Remove default database passwords and require generated secrets.
- [x] **P0** Make CORS origins environment-driven; avoid permissive methods and
  headers combined with credentials unless required.
- [x] **P1** Use multi-stage backend/frontend builds and remove compilers/dev
  packages from runtime images.
- [x] **P1** Add container health checks that verify database readiness, not only
  that the HTTP process responds.
- [x] **P1** Decide whether API docs are public in production and make the setting
  configurable.
- [x] **P1** Add reverse-proxy/TLS guidance and security headers, including CSP,
  frame protection, MIME sniffing protection, and a referrer policy.
- [x] **P1** Add graceful shutdown and worker/job-draining behavior.
- [x] **P1** Document data volumes, database backup, restore, upgrade, and disaster
  recovery.
- [x] **P2** Target a smaller image and publish supported architecture/platform
  information.

**Phase complete when:** `docker compose up` from a fresh clone starts the full
application with no source edits, no insecure default credentials, and a tested
upgrade/backup path.

---

## Phase 9 - Clean the repository, consolidate tests, and add CI/security gates

**Goal:** Remove verified unused/stale material, establish one root environment
configuration, and protect the maintained product with reproducible test and
release gates.

**Required order:** complete Phase 9A before expanding the test/CI work in 9B/9C
or proceeding to Phases 10-11. Cleanup is a behavior-preserving change, not an
opportunity to remove useful regression coverage.

### Phase 9A - Repository hygiene and one root environment file

#### Inventory and cleanup rules

- [x] **P0** Review the current code, recent AI changes, entry points, imports,
  test discovery, scripts, Docker builds, and documentation before deleting
  anything. Classify each candidate as keep, rename, consolidate, archive, or
  remove, with evidence of its consumers or lack of consumers.
- [x] **P0** Preserve runtime behavior, public contracts, database records,
  migration revision IDs/chains, lockfiles, authored AI-evaluation fixtures, and
  test safety boundaries. Do not rewrite/drop migrations or regenerate secrets
  merely to make filenames cleaner.
- [x] **P1** Inspect unused compatibility modules
  `backend/app/agents/nodes.py` and `state.py`, the unused frontend UI Slot
  wrapper, and the React scaffold asset; remove them only after confirming no
  shipped code, test, script, or documented workflow needs them.
- [x] **P1** Review `backend/app/agents/graph.py` separately: the generation worker
  and live test still use this facade. If retiring it, migrate consumers to the
  AI pipeline first and preserve timeout, telemetry, and provider-governor
  behavior before removing the compatibility package.
- [x] **P1** Remove remaining scaffold assets only after replacing active
  references; `frontend/public/vite.svg` is still the configured favicon.
- [x] **P1** Review duplicate Tailwind configuration/theme definitions and
  Vite/PostCSS processing. Consolidate only after verifying the generated CSS
  and accessibility/responsive behavior remain equivalent.
- [x] **P1** Review dependencies and ignore rules for unused scaffolding. Keep
  legitimate dynamic/CLI/build/test dependencies and all secret/cache/data
  exclusions; ignored `venv` and `node_modules` are not tracked source cleanup.
- [x] **P1** Archive the obsolete `idea.md` design and replace the frontend Vite
  README with a useful entry point. Update maintained docs/comments to describe
  current architecture and behavior, not remediation phases, retired tools, or
  superseded per-job concurrency/retry policies. Preserve historical evidence
  in development logs or an explicitly labelled archive.
- [x] **P1** Update renamed paths in imports, scripts, test commands, docs, and
  CI configuration; do not leave references to removed files or old phase names.

#### Keep regression tests; name them by product behavior

- [x] **P0** Keep `test_ai_chunking.py`, `test_ai_evaluation.py`,
  `test_ai_grounding.py`, `test_ai_pipeline.py`, and the other maintained AI
  tests. A completed remediation phase does not make its tests disposable.
- [x] **P0** Rename or split phase-labelled tests by domain using the map below.
  Remove a test only when its behavior is retired or equivalent retained
  coverage is demonstrated; never delete it solely because its phase is done.
- [x] **P1** Consolidate shared PostgreSQL/test fixtures and resolve the current
  repeated hardcoded Alembic-head assertions through one maintained schema-head
  check. Validate disposable database identity before any mutation or cleanup.
- [x] **P1** Rename phase-labelled helpers, fixtures, test descriptions, and
  `PHASE7_*` live-test variables consistently. Preserve explicit opt-in,
  disposable-account/database restrictions, and no-secret logging.

| Original test/helper | Maintained domain name or split |
| --- | --- |
| `backend/tests/test_phase2_integrity.py` | `test_flashcard_validation.py` and `test_study_progress.py` |
| `backend/tests/test_phase6_study.py` | `test_study_sessions.py` and `test_study_idempotency.py` |
| `backend/tests/test_phase7_email.py` | `test_email_delivery.py`; split outbox/worker coverage if useful |
| `backend/tests/test_phase8_runtime.py` | `test_runtime.py`; split security, health, and shutdown if useful |
| `backend/tests/postgres/test_phase2_postgres.py` | `test_database_integrity.py`; split concurrency by domain |
| `backend/tests/postgres/test_phase3_generation_jobs.py` | `test_generation_job_persistence.py` (avoids the unit-module name collision) |
| `backend/tests/postgres/test_phase4_ai_quality.py` | `test_ai_schema.py` |
| `backend/tests/postgres/test_phase7_email_outbox.py` | `test_email_outbox.py` |
| `backend/tests/integration/test_live_graph.py` | `test_live_ai_pipeline.py` after facade migration |
| `backend/tests/support/phase7_browser_user.py` | `password_reset_browser_user.py` |
| `frontend/e2e/phase5-coverage.spec.ts` | Split auth recovery, subject mutations/recovery, study recovery, and generation telemetry |
| `frontend/e2e/phase6-accessibility.spec.ts` | `accessibility.spec.ts` |
| `frontend/e2e/phase6-responsive.spec.ts` | `responsive.spec.ts` |
| `frontend/e2e/phase6-study-reliability.spec.ts` | `study-reliability.spec.ts` |
| `frontend/e2e/phase7-invitation-email.spec.ts` | `invitation-email.spec.ts` |
| `frontend/e2e/phase7-live-password-reset.spec.ts` | `password-reset.live.spec.ts` |

#### Configuration decision: exactly one user-managed `.env` at repository root

There must be one supported configuration file: `<repository-root>/.env`, with
one documented template: `<repository-root>/.env.example`. Backend/frontend
`.env` files must not be required, loaded as fallbacks, or recommended in docs.
Docker and isolated tests may inject process environment values without a file.

- [x] **P0** Merge root and backend `.env.example` into the root template, retain
  all supported settings, reconcile conflicting defaults, and remove the
  component-specific examples after updating every consumer/reference.
- [x] **P0** Change backend configuration from `backend/.env` to an absolute,
  working-directory-independent root `.env` location for native development,
  CLI commands, migrations, and workers. Support Docker process injection
  without copying or mounting secrets into runtime images.
- [x] **P0** Make frontend development/build configuration use the same root
  source or its explicitly injected public settings. Resolve local API/proxy
  routing deliberately; deleting `frontend/.env.example` alone is insufficient.
- [x] **P0** Define precedence as explicit process environment -> root `.env` ->
  validated defaults. Keep tests isolated from the user's real `.env` through
  injected test settings and `_env_file=None` where appropriate.
- [x] **P0** Preserve least-privilege Compose injection: provider keys reach only
  the generation worker, SMTP credentials only the email worker, and frontend
  build variables are public `VITE_*` values only. Do not add a blanket
  `env_file: .env` to every service.
- [x] **P0** Document/derive Docker database host `db` versus host-development
  `localhost` from this same configuration. Explain Compose-only ports,
  `DATABASE_URL`, frontend URLs, and build-time API configuration without
  requiring a second environment file.
- [x] **P0** Fix fresh-local-bootstrap SMTP defaults: the current root template
  can select Compose's `mailpit` host while explicitly retaining port `587`.
  Local Mailpit must use port `1025` with both TLS flags false; production must
  require a real relay and the correct encrypted mode.
- [x] **P1** Reconcile the root example's daily per-user job quota `20` with the
  backend example/default `10`; preserve the intended operator decision and
  document it instead of silently overriding it during the merge.
- [x] **P1** Group the root example into basic setup and optional advanced
  settings. Explain each variable's purpose, default, units/range, required
  conditions, consuming process, and security implications; clarify whether
  an empty value means fallback, disabled, or invalid.
- [x] **P1** Document when root `.env` edits require container recreation,
  process restart, or frontend rebuild. Keep bootstrap non-overwriting and
  provide a safe settings-update path for existing installations.
- [x] **P1** Add root-loader tests from different working directories, environment
  precedence/isolation tests, and configuration-template completeness/default
  checks covering application and Compose-only settings.

**9A complete when:** the reviewed cleanup inventory is resolved, maintained
tests have domain names and equivalent coverage, migrations/data/secrets are
preserved, no active reference points to removed files or component `.env`
files, and fresh-clone Compose plus supported native workflows configure the
app from root `.env` only. Backend/frontend gates and isolated PostgreSQL,
Mailpit, and browser regressions must pass; paid AI calls remain opt-in.

### Phase 9B - Consolidated test coverage and commands

Audit existing coverage first and add only missing cases; tests already added
in Phases 0-8 and subsequent AI changes are the starting suite, not disposable
implementation artifacts.

- [x] **P0** Verify/add backend unit tests for token types, token expiry, malformed
  claims, password/auth behavior, invitations, permissions, scheduling, and
  progress calculations.
- [x] **P0** Verify/add PostgreSQL integration tests for migrations, constraints,
  transactions, cascades, duplicate enrollments, and concurrent updates.
- [x] **P0** Verify/add PDF tests for valid, empty, encrypted, malformed, oversized,
  scanned, and high-page-count inputs.
- [x] **P0** Mock the model for normal tests and cover retry, invalid JSON,
  timeout, partial failure, and cancellation paths.
- [x] **P0** Verify/add frontend component tests for route guards, token refresh, joins,
  card editing, timers, submission locking, and error recovery.
- [x] **P0** Verify/add end-to-end tests for instructor creation -> generation -> review
  -> publish -> invitation -> student study -> progress.
- [x] **P1** Verify/add an optional live-model evaluation suite with a strict budget and
  explicit opt-in.
- [x] **P1** Document one authoritative command per offline, PostgreSQL, Mailpit,
  browser, and opt-in live-AI suite, including disposable-environment setup and
  expected gating; ensure renames do not silently reduce test discovery.

### Phase 9C - Continuous integration and dependency safety

- [x] **P0** Add CI gates for backend tests, frontend typecheck/lint/test/build,
  migration checks, and Docker builds.
- [x] **P0** Update vulnerable frontend dependencies and make the production audit
  pass or document narrowly accepted exceptions.
- [x] **P0** Audit fresh locked Python dependencies; assess replacing the
  `python-jose`/`ecdsa` chain if the advisory cannot be remediated.
- [x] **P1** Add secret scanning, dependency review, container scanning, and a
  generated SBOM for releases.
- [x] **P1** Configure Dependabot or Renovate with grouped, tested updates.
- [x] **P1** Add branch protection and require CI before merge.
- [x] **P1** Refresh stale browser-compatibility data and define a measured
  frontend bundle budget; address the current warning with verified splitting
  where appropriate, rather than hiding it by raising the warning threshold.
- [x] **P2** Add coverage reporting with meaningful thresholds rather than a
  vanity 100% target.

**Phase complete when:** 9A cleanup/root configuration is verified, test discovery
and required coverage are maintained, and a pull request cannot merge if it
breaks the full build, security boundaries, migrations, or critical user journey.

---

## Phase 10 - Add observability, privacy, and operational controls

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

## Phase 11 - Finish the open-source product and rebrand

**Goal:** Publish a trustworthy repository that users can understand, operate,
and contribute to.

- [ ] **P0** Choose and add a license. Consider Apache-2.0 for broad adoption or
  AGPL-3.0 if hosted derivatives should publish their changes.
- [ ] **P0** Add a root README containing product scope, screenshots, architecture,
  prerequisites, quick start, configuration, upgrades, backups, limitations,
  privacy notes, and troubleshooting.
- [ ] **P0** Publish and verify the single root `.env.example` and configuration
  guidance completed in Phase 9A; do not reintroduce backend/frontend examples
  or a second user-managed `.env` file.
- [ ] **P1** Add `CONTRIBUTING.md`, `SECURITY.md`, Code of Conduct, pull-request
  template, and issue templates.
- [ ] **P1** Document a responsible vulnerability-reporting channel and supported
  release versions.
- [ ] **P1** remove stale `idea.md` claims about Instructor Toolkits,
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
- [x] Phase 9A repository cleanup is verified with no lost regression coverage,
  and root `.env` is the sole documented file-based configuration source.
- [ ] No known critical/high vulnerability is reachable without a documented,
  time-bounded exception.
- [ ] Authentication and cross-subject authorization tests pass.
- [ ] Database migration, backup, restore, and upgrade tests pass.
- [ ] PDF jobs are bounded, durable, cancellable, and recoverable.
- [ ] Transactional email passes Mailpit integration and end-to-end tests;
  production SMTP setup and failure recovery are documented and verified.
- [ ] Frontend typecheck, lint, tests, accessibility checks, and production build
  pass.
- [ ] A fresh-clone production deployment has been tested on a clean machine.
- [ ] Documentation, license, privacy disclosure, security policy, and release
  artifacts are complete.
- [ ] The end-to-end instructor/student journey passes without manual database or
  source-code changes.
