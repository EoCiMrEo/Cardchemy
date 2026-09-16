# Phase 8 remediation: deployment and self-hosting

Date: 2026-09-15

## Scope and orientation

Phase 8 required a clean clone to become a safe, production-shaped full stack
without source edits or default credentials. Before implementation, the agent
reviewed the root remediation roadmap and every prior remediation log. The
requested `.agent/AGENTS.md` file was absent. Separate subagents audited backend
runtime behavior, frontend production serving, and Compose/operator
documentation; their work was reviewed and verified together in the shared
checkout. Existing Phase 7 work was preserved.

## What changed

- Added root, backend, and frontend Docker ignore rules covering secrets,
  dependency trees, virtual environments, caches, tests, reports, and build
  output.
- Replaced the backend's single-stage image with a dependency-builder stage and
  a non-root runtime containing only runtime packages, migrations, and
  application code. OCR remains an explicit, separately measured build option.
- Added a multi-stage frontend image that compiles with pinned Node and serves
  only the built SPA from unprivileged Nginx. Deep links fall back to
  `index.html`; `/api/*` stays same-origin and is forwarded to the API.
- Added dynamic Docker DNS resolution at the frontend edge so backend container
  replacement does not leave Nginx pinned to a stale service address.
- Added CSP, frame denial, MIME-sniffing prevention, a strict referrer policy,
  a permissions policy, immutable asset caching, and non-cacheable application
  entry HTML. HSTS is deliberately owned by the documented TLS terminator.
- Added a production-shaped base Compose stack and explicit development and
  production profiles. The production profile has no bind mounts, reload,
  debug mode, direct API publication, public database port, or Mailpit service.
- Added a one-time environment bootstrap that independently generates the
  PostgreSQL password, JWT signing secret, and PDF-source encryption key,
  prints no values, and refuses to overwrite an existing `.env`.
- Added exact credentialed CORS origin validation and limited methods/headers
  to the browser contract. Production rejects HTTP, localhost, and loopback
  origins.
- Added process-only liveness and bounded database-aware readiness probes for
  the API and direct database probes for both workers. All pooled engines are
  disposed during process shutdown and health probes.
- Added configurable API root-path/docs behavior. Docs remain convenient in
  local development and default closed in production.
- Added SIGTERM-aware generation/email worker draining. Workers stop claiming
  new work, wait a bounded grace period for active tasks, and cancel only work
  that exceeds it; Compose stop grace remains longer than application grace.
- Added complete self-hosting guidance for clean-clone startup, internal/public
  URLs, production TLS/proxying, health, shutdown, volumes, backups, restore,
  upgrade, rollback, disaster recovery, image sizes, and supported platforms.
- Added unit, PostgreSQL regression, and frontend URL-validation coverage for
  the new runtime contracts.

## Issues found during live verification

1. A clean PostgreSQL worker initially crashed in startup cleanup because an
   unqualified `FOR UPDATE` attempted to lock the nullable side of a left join.
   Cleanup now locks only `GenerationJob` on PostgreSQL with `SKIP LOCKED`, and
   a PostgreSQL regression test covers the formerly failing empty-queue path.
2. Recreating the backend changed its container address while the frontend
   proxy retained the old address. The Nginx upstream now uses Docker's embedded
   resolver and was proven to recover after backend replacement without
   restarting the frontend.
3. The first development profile exposed Mailpit's UI but not its SMTP port,
   preventing host-run integration tests. The development-only loopback SMTP
   publication was added; base/production networking remains private.

## Verification evidence

### Automated gates

- Backend project virtual environment: `160 passed, 1 deselected in 26.88s`
  with isolated PostgreSQL 16 and real Mailpit SMTP/API enabled. The one
  deselection is the intentionally opt-in live AI-provider test.
- Frontend authority `npm run check`: type checks, ESLint, two Node unit tests,
  production build, and Chromium acceptance all passed; browser result was
  `46 passed, 1 skipped`. The skipped case is the separately configured live
  password-reset/Mailpit browser journey.
- Base, development, and production Compose configurations passed schema
  validation. Rendered production invariants were `ENVIRONMENT=production`,
  `DEBUG=false`, `API_DOCS_ENABLED=false`, zero published API/database ports,
  zero backend bind mounts, and a frontend port bound to `127.0.0.1`.

### Clean-stack and browser checks

- Ran the one-time bootstrap from an absent `.env`, verified three independently
  generated non-empty secrets without displaying them, and verified a second
  run refused to overwrite the file.
- Built and started the complete isolated stack. PostgreSQL migration completed
  first; frontend, API, generation worker, email worker, database, and Mailpit
  all reached healthy state.
- Verified SPA root and deep-link fallback, JSON API 404 isolation, local API
  docs, same-origin API routing, asset caching, every configured security
  header, allowed CORS preflight, rejected method preflight, refresh-cookie path
  rewriting, login, refresh, and logout.
- Used a real Chromium session against the built containers. Anonymous deep-link
  protection redirected to the accessible login page; a disposable instructor
  logged in, reached the dashboard, and logged out with no retained browser
  cookie. No CSP or routing error appeared.
- With PostgreSQL stopped, the edge remained available, process liveness
  returned 200, and database readiness returned 503. After PostgreSQL restarted,
  readiness returned 200 and both workers recovered healthy. Recreating the API
  then returned readiness 200 through the unchanged frontend proxy.

### Backup, migration, and images

- Created a PostgreSQL custom-format backup, copied it out of the database
  container, and matched its SHA-256 checksum before restoring it to a new
  database.
- Source and restored databases both reported Alembic `20260915_0005`, one
  representative user, and two representative auth-session records.
- On the restored copy, downgrade to `20260915_0004` and re-upgrade to
  `20260915_0005` both succeeded with representative records preserved.
- Linux/amd64 image inspection reported: default backend 390,255,035 bytes,
  OCR backend 531,672,448 bytes, and frontend 21,560,780 bytes. The default
  backend is about 38% smaller than the 627 MB Phase 7 single-stage reference.
- Default runtime smoke checks found no compiler, Node runtime, tests, or broken
  Python packages. The OCR runtime reported working `pdftotext 22.12.0` and
  `tesseract 5.3.0` while still excluding compiler, Node, and tests.

## Cleanup and residual notes

Both isolated Compose projects, their volumes, the restored database, temporary
backup artifact, generated QA `.env`, disposable account/session data, and
browser session artifacts were deleted after verification. No credential or
token value is recorded here. The frontend build still reports an existing
stale Browserslist-data notice and a bundle-size warning; neither changes the
Phase 8 deployment contract, and both remain suitable for Phase 9 dependency
and performance gates.
