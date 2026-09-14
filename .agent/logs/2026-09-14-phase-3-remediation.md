# Phase 3 remediation - durable and bounded PDF generation

Date: 2026-09-14

## Scope and repository context

- Completed every item under Phase 3 in `issues-required-remediation.md`.
- The worktree was clean before implementation. Existing work was not
  overwritten or reset.
- `/.agent/AGENTS.md` was not present and `.agent/rules/` was empty, so neither
  supplied additional instructions. The Phase 0/1 and Phase 2 logs were read
  before design and implementation.
- Three read-only subagents independently audited backend/queue design,
  frontend recovery/UX, and operations/tests. Their findings converged on a
  PostgreSQL queue, separate worker, lease tokens, raw bounded uploads, and
  encrypted short-lived source storage. The implementation incorporated those
  recommendations.

## Architecture and API changes

- Replaced the synchronous multipart `/flashcards/generate` route with a
  two-step, owner-scoped API:
  - reserve metadata with `POST /flashcards/generation-jobs` and a required
    idempotency key;
  - stream-count the raw PDF at `PUT /flashcards/generation-jobs/{id}/source`;
  - list/get status, cancel, retry, and fetch current limits through dedicated
    routes.
- Added durable states: `awaiting_upload`, `queued`, `running`, `completed`,
  `failed`, and `cancelled`.
- Added migration `20260914_0002` for queue rows, encrypted source rows,
  append-only quota events, partial queue/lease indexes, constraints, and a
  unique generation-job/result-set link.
- Added a separate `python -m app.worker` Compose service. Claims use
  `FOR UPDATE SKIP LOCKED`, a unique claim token, worker identity, lease expiry,
  and heartbeats. Every state update and final commit revalidates the lease so a
  stale worker cannot create a duplicate set.
- Result persistence is atomic: validated cards, the set, source deletion, and
  completed status commit in one transaction. Failures cannot leave an empty
  set or partial card collection.

## Resource, failure, and cost controls

- Validates `application/pdf` (or `application/x-pdf`) plus the `%PDF-`
  signature; filename extensions are not trusted.
- Applies configurable upload-byte, page, extracted-character, requested-card,
  per-user active, deployment active/queue, daily job/card/upload, and retained
  source-byte limits.
- Admission/quota checks use a PostgreSQL transaction advisory lock so
  concurrent requests cannot race through configured caps.
- Rejects oversized `Content-Length` early and also counts every streamed chunk,
  including chunked requests. Empty and invalid lengths have stable errors.
- Runs parsing in a killable spawned process, reached from the worker through a
  thread, with a hard parent timeout and Linux CPU/address-space limits.
- Categorizes encrypted, malformed, zero-page, over-page, over-text, image-only,
  OCR dependency, OCR timeout, and parser resource failures into bounded public
  messages. Model/provider exceptions and stack traces are never returned.
- Bounds worker and graph concurrency, total job/provider/extraction time,
  automatic attempts, manual retries, and exponential backoff with full jitter.
  Lease recovery and periodic cleanup make interrupted work recoverable.
- Truncates model output to the requested card count before validation and
  persistence.

## Source-retention decision

- PDF bytes live only in `generation_job_sources`, never in status/list rows or
  a public download route.
- Bytes are encrypted with AES-256-GCM using a required key independent from
  `SECRET_KEY`, a random nonce, and request-fingerprint authenticated data.
- Success, cancellation, and permanent failure delete the source. A final
  retryable failure retains ciphertext for 24 hours by default, after which
  cleanup deletes it and disables retry. Upload reservations expire after 15
  minutes by default.
- Per-user and deployment retained-byte caps provide storage backpressure.
- Key rotation, database backup/WAL handling, access rules, deletion behavior,
  and disaster-recovery implications are documented in
  `docs/PDF_GENERATION.md` and `docs/DATABASE_OPERATIONS.md`.

## Frontend changes

- Added typed generation contracts and safe API-error extraction.
- Added non-overlapping, abortable recursive polling with bounded retry delay,
  `Retry-After` support, page-reload recovery, and completed-set refresh.
- The upload form now preserves one idempotency key across ambiguous retries,
  returns after the source is queued, displays live limits, and can stop an
  upload/cancel its reserved job.
- Job cards expose progress, attempt count, cancellation, safe errors, manual
  retry, and the completed set link. Retry keys are stable across ambiguous
  retry failures.
- Applied the React quality checklist: parallel independent reads, functional
  updates, complete effect cleanup/dependencies, accessible labels/live regions,
  link/button composition, and no inline component definitions.

## Optional OCR

- OCR is disabled by default. When `PDF_OCR_ENABLED=true`, the image build adds
  Poppler and Tesseract.
- OCR runs only when native extraction yields no text, renders one bounded page
  at a time, has a per-page timeout, and applies the extracted-character cap.
- Language, DPI, timeout, dependency, image-size, CPU/memory, latency, and cost
  considerations are documented in `docs/PDF_GENERATION.md`.

## Verification evidence

- Dependency locks regenerated with hashes; `cryptography==50.0.1` is now a
  direct runtime dependency.
- Python compilation and non-live/non-PostgreSQL suite: `58 passed, 1 skipped,
  11 deselected`.
- Isolated migrated PostgreSQL suite: `11 passed`, including concurrent
  idempotent reservation, distinct multi-worker claims, queue/retention indexes,
  source-payload separation, and stale-claim exactly-once finalization. The
  disposable test database was dropped afterward.
- Local application database upgraded from `20260914_0001` to
  `20260914_0002`; `alembic check` reported no new upgrade operations.
- `docker compose config --quiet` passed with validation-only required values.
- Default backend/worker image built successfully from the hashed lock.
- OCR image built successfully; runtime checks reported Tesseract 5.5.0 and
  Poppler `pdftoppm` 25.03.0.
- Frontend production build passed (`tsc -b` and Vite, 2,296 modules).
- ESLint passed for every Phase 3 frontend file. Repository-wide lint still
  reports 16 errors and 4 warnings in pre-existing Phase 5 files; none points to
  the Phase 3 files.
- Supervised browser test rendered the instructor upload form, live 40% running
  job, limits copy, progress, and cancel control. The cancellation action issued
  the expected successful POST. Browser page errors were empty. After correcting
  two contrast findings, axe WCAG 2 A/AA reported zero violations.
- `git diff --check` passed.

## Operational notes

- Before normal Compose startup, create a root `.env` from `.env.example` and
  configure strong `POSTGRES_PASSWORD`, `SECRET_KEY`, and an independently
  generated `GENERATION_SOURCE_ENCRYPTION_KEY`. The API and worker intentionally
  fail fast without valid values.
- No live Gemini generation was invoked during verification, avoiding an
  uncontrolled provider charge. Pipeline terminal behavior was exercised with
  deterministic worker failure/success tests.
- No passwords, API keys, PDF content, model prompts, or long-lived credentials
  were written to this log.
