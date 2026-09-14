# Phase 0 and Phase 1 remediation

Date: 2026-09-14

## Scope and operator decisions

This work completed only Phase 0 and Phase 1 of
`issues-required-remediation.md`. Later-phase findings were preserved as known
baseline debt rather than being silently folded into this change.

The operator approved these decisions before implementation:

- Treat local `main` as the release branch; do not push a remote branch.
- Remove public instructor signup. Create the first instructor with an
  operator-only command; require an explicit flag for additional instructors.
- Provide SMTP password reset and do not require email verification for the
  current self-hosted deployment model.
- Store shared rate-limit state in PostgreSQL; do not introduce Redis.

`.agent/AGENTS.md` was not present. The existing `.agent/logs/README.md` was
read before work began. Parallel subagent audits covered repository/baseline,
backend auth, and frontend auth surfaces; their early findings were reconciled
with direct inspection and verification by the primary agent.

## Project understanding used for the change

- Backend: FastAPI, SQLAlchemy async sessions, PostgreSQL, Pydantic settings,
  passlib, signed JWTs, PDF extraction, and a LangGraph/Gemini generation path.
- Frontend: React 19, Vite, TypeScript, Axios, React Router, Redux for study
  state, Radix-based UI primitives, and Tailwind styles.
- Main product flow: instructor subject creation -> PDF/card generation ->
  review/publish -> invitation -> student study -> spaced-repetition progress.
- Deployment baseline: Docker Compose starts PostgreSQL and the FastAPI API;
  the frontend is currently run separately. Production frontend/container work
  belongs to later phases.
- Existing data model: users, subjects, sets, cards, enrollments, study
  progress, and invitation rows. Phase 1 adds session, reset-token, and
  rate-limit rows; migrations remain intentionally tracked by Phase 2.

## Initial baseline evidence

- The starting branch was
  `student-features/progress-bar-and-join-course` at `641e987`.
- `origin/main` at `9a12013` is an ancestor of that commit. Local `main` was
  moved to the feature tip after the operator selected it as the release
  branch. `git branch -r --no-merged main` returned no remote feature tips.
- The pre-existing uncommitted `frontend/src/services/api.ts` refresh-loop fix
  was preserved in a stronger single-flight implementation; trailing
  whitespace was removed.
- Initial frontend build: failed with eight unused-symbol TypeScript errors.
- Initial frontend lint: 48 errors and 7 warnings.
- The original production dependency audit recorded 5 advisories. After the
  lockfile was refreshed, npm reports 19 total dependency advisories (1 low,
  4 moderate, 14 high); dependency remediation is explicitly Phase 8.
- Backend application compilation/import succeeded before remediation, but no
  automated unit test suite existed.

## Phase 0 implementation

- Established version `0.1.0` in backend settings, frontend package metadata,
  and the initial `CHANGELOG.md`.
- Defined Semantic Versioning in `docs/VERSIONING.md`.
- Replaced floating Python requirements with direct exact pins in
  `requirements.in` / `requirements-dev.in` and complete transitive,
  hash-locked `requirements.txt` / `requirements-dev.txt` files.
- Added `scripts/lock_dependencies.ps1`, including explicit hash generation,
  extras stripping, failure checking, and hashed lock-tool versions.
- Defined the supported runtime matrix in `docs/RUNTIMES.md` and pinned the
  frontend package-manager contract in `package.json` plus Node major in
  `.nvmrc`.
- Removed unused direct backend packages (`alembic`, `pgvector`, `python-docx`,
  the `langchain` meta-package, and runtime `httpx`) and unused frontend
  packages (`idb`, React Query, and `jwt-decode`). Rationale is recorded in
  `docs/DEPENDENCIES.md`.
- Replaced the quota-spending standalone graph script with an opt-in pytest
  integration test marked `ai_live`. Normal pytest runs deselect it and never
  import the live graph or expose API-key fragments.
- Added a backend `.dockerignore` after the first clean container context
  correctly exposed that local caches/virtual environments were entering the
  build context.

## Phase 1 implementation

### Tokens and sessions

- Every JWT now carries a strict token type, issuer, audience, subject, JTI,
  issued-at, not-before, and expiration. Access/refresh tokens also require a
  server-side session ID; invitation tokens require the student role and a
  matching subject claim.
- Separate access, refresh, invitation, and password-reset verifiers reject
  cross-use and convert malformed claims to controlled 401/400 responses.
- Access JWTs live only in frontend memory. Refresh JWTs are returned only in a
  SameSite, HttpOnly cookie (Secure is mandatory in production), never JSON,
  URL query parameters, local storage, or session storage.
- `auth_sessions` stores a hash of the current refresh JTI. Refresh rotates the
  JTI under a row lock; reuse revokes the token family. Logout and password
  reset revoke server-side sessions.
- The Axios client implements one shared refresh promise, one retry per
  request, and one session-ended notification, preventing refresh storms or
  loops.

### Accounts, recovery, and secrets

- Email input is trimmed/lowercased and lookups remain compatible with legacy
  mixed-case rows. Password input is limited to 8 through 128 characters and
  uses `bcrypt_sha256`, while legacy bcrypt hashes remain verifiable.
- Public registration is student-only and requires the single invitation
  design. The unsafe default user role was changed from instructor to student.
- Added `python -m app.cli create-instructor --email ...`; the first instructor
  is one-time bootstrap, and subsequent creation requires
  `--allow-additional`. Passwords are prompted and never passed in argv.
- Added generic, non-enumerating forgot/reset endpoints, single-use reset rows,
  SMTP delivery, and frontend request/reset pages. Email verification is
  explicitly disabled for the approved self-hosted model.
- `DATABASE_URL` and `SECRET_KEY` have no fallback. Production rejects known
  sample/weak secrets, debug mode, insecure cookies, localhost CORS, and
  missing SMTP configuration. Empty optional environment variables are safely
  ignored. `.env` is resolved from the backend directory regardless of cwd.
- Secret generation/rotation and instructor operations are documented in
  `docs/AUTHENTICATION.md` without logging or displaying generated values.

### Authorization, invitations, and abuse control

- Added explicit current-instructor and current-student dependencies and
  applied them to all write/generation/study surfaces.
- Subject ownership/enrollment checks protect reads and mutations. Student
  flashcard reads and every study/progress/sync path require enrollment, a
  published set, and approved cards.
- The competing invitation endpoints were replaced by one signed,
  database-backed, student-only system. Creation enforces 1 through 720 hours.
  Consumption validates type/role/subject/expiry/status, locks the invitation,
  and relies on the unique enrollment constraint for race safety.
- New-student creation, invitation consumption, and enrollment occur in one
  transaction. A failed invitation rolls back the user row.
- PostgreSQL-backed fixed-window counters protect login, registration,
  invitation creation, invitation acceptance, refresh, password recovery, PDF
  upload, and AI generation. Rate-limit identifiers are hashed before storage.
- Frontend role guards prevent students from entering instructor set editing
  and prevent instructors from entering study mode. Join requests are
  single-flight per invitation token and `/join` without a token renders an
  error instead of navigating to `/register?token=null`.

## Verification evidence

### Reproducible environments

- Host: Python 3.13.7, Node 24.7.0, npm 11.5.1.
- Clean containers: Python 3.11 (`python:3.11-slim`), Node 24.21.0, npm 11.19.0,
  PostgreSQL 16.
- Production backend image installed `requirements.txt` with all hashes,
  built successfully, imported the final application, and `pip check` reported
  `No broken requirements found`.
- Development lock installed with `--require-hashes` in the disposable Python
  3.11 container.
- Backend offline suite on both Python runtimes: `30 passed, 1 deselected`.
  The deselected test is the explicitly opt-in live Gemini test.
- Frontend `npm ci` succeeded from the lock in a clean Node container.
- Host and clean-container production builds produced the same six known
  unused-symbol TypeScript failures in `PreviewDialog.tsx`, `slot.tsx`,
  `InstructorDashboard.tsx`, `SetView.tsx`, and `StudentDashboard.tsx`.
  This deterministic build debt is the first Phase 5 release blocker, not a
  Phase 0 or Phase 1 acceptance failure.
- Current lint baseline after scoped auth cleanup: 33 errors and 5 warnings.
  Remaining findings are tracked by Phase 5.

### Live PostgreSQL/HTTP smoke test

The documented Compose command built and started PostgreSQL and the API. Both
containers became healthy and `/health` returned `{"status":"healthy"}`.
The first startup attempt found two deterministic defects: an empty optional
SMTP email was being parsed as an invalid address, and the container health
check called an unavailable `curl`. `env_ignore_empty` and a standard-library
Python health check resolved both.

The operator CLI and HTTP flow then verified:

- instructor login and refresh responses contain an access token only;
- refresh cookie is HttpOnly and scoped to `/auth`;
- refresh changes the cookie/JTI;
- replaying the prior refresh cookie returns 401 and the rotated access token
  is then rejected with 401 because the session family was revoked;
- invitation-backed registration enrolled exactly one student subject;
- a student reading an un-enrolled subject receives 403;
- a student attempting instructor-only subject creation receives 403.

All disposable Compose containers, the network, and the test-only PostgreSQL
volume were removed after verification. No credentials or generated token
values are retained in this log.

## Known later-phase work deliberately not claimed here

- Phase 2: Alembic baseline/migrations and broader database constraints.
- Phase 3: timezone-aware database migration and model/data validation.
- Phase 4: durable PDF/AI jobs and error sanitization.
- Phase 5: the six TypeScript build failures and 33 lint errors/5 warnings.
- Phase 7: full production frontend/Compose topology and hardening.
- Phase 8: npm advisories and the larger CI/test matrix.

Those checkboxes remain open in `issues-required-remediation.md`.
