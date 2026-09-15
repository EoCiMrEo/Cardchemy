# Phase 5 remediation - frontend correctness and API architecture

Date: 2026-09-15

## Scope and repository context

- Completed every item under Phase 5 in `issues-required-remediation.md`.
- `/.agent/AGENTS.md` was not present. All existing `.agent/logs/` entries and
  the backend/frontend contracts established in Phases 0-4 were read before
  implementation.
- The root `.env.example` deletion was already present when this phase began.
  It was treated as user-owned work and left untouched. No reset, checkout, or
  destructive cleanup was used.
- Three subagents independently audited backend contracts, frontend behavior,
  and browser coverage. A second adversarial review exposed authentication and
  per-card concurrency cases that were fixed and added to the browser suite.
- The product decision for this phase is English-only v1. The catalog structure
  is ready for future locales, but Phase 5 does not ship a language selector or
  another translation.

## API architecture, types, and configuration

- Replaced frontend API `any` values with shared request/response types aligned
  to backend schemas. Route-only create schemas no longer duplicate IDs already
  supplied in the URL, and invitation acceptance has a dedicated typed response.
- Centralized the runtime API origin behind a required, validated
  `VITE_API_URL`. Missing values, relative URLs, and non-HTTP(S) schemes now
  fail immediately instead of silently falling back to localhost.
- Removed the unused query-client dependency and configuration. The existing
  service/state approach now owns loading, cancellation, error, retry, and
  refresh behavior consistently.
- Added reusable safe API-error extraction so server details are presented to
  users without leaking opaque response objects or relying on console output.

## Authentication, refresh, and routing

- Added single-flight refresh: simultaneous expired protected requests share
  one refresh call and retry once with the resulting access token.
- A failed refresh clears the matching session exactly once, emits one session
  event, and cannot recursively refresh the refresh endpoint or retry protected
  requests in a loop.
- Login and registration abort and settle an older bootstrap refresh before the
  explicit auth request. This prevents a stale successful refresh response and
  its HttpOnly cookie from overwriting a newly established session.
- Logout waits for any refresh already in flight. A failed server logout keeps
  the client session active, presents the failure, and allows an exact retry;
  successful logout then clears the session.
- Added student/instructor route guards for edit and study routes, kept the
  shared subject route role-aware, added a not-found page, and wrapped the app
  in a recoverable error boundary.

## Join, editing, progress, and user feedback

- `/join` treats missing or whitespace-only tokens safely and never constructs
  `token=null`. New-student registration and existing-student sign-in preserve
  the invitation token through authentication.
- Join effects are abortable. Server-side acceptance is idempotent for the same
  student/subject, including a PostgreSQL concurrency regression test, while a
  different student still receives the intended conflict.
- Set editing supports the canonical four multiple-choice options, rejects
  blank question/answer/options and duplicate options, and never changes
  approval implicitly. Approval remains an explicit action.
- Card mutation state and errors are keyed per card, so editing or saving one
  card does not hide or corrupt unrelated card controls. Approve-all and
  individual operations also exclude unsafe overlap.
- Student subject progress renders the finalized server-owned completion and
  mastery percentages instead of recalculating a competing model in the UI.
- Load and mutation failures across auth, dashboards, subjects, sets,
  invitations, card review, and study progress now have visible, actionable
  retry paths. Retry operations preserve the intended payload or answer.
- Centralized user-facing copy in `frontend/src/i18n/en.ts` and documented the
  English-only v1 decision in `docs/LOCALIZATION.md`.

## Browser coverage

The Playwright suite covers the Phase 5 completion paths and the race/failure
cases found during review:

- role guards and role-aware subject rendering;
- missing-token, instructor-blocked, new-student, existing-student, retry, and
  repeated-effect invitation flows;
- simultaneous 401 single-flight refresh, failed refresh without loops, stale
  successful refresh versus login, and failed/successful logout;
- not-found and error-boundary recovery;
- page/form loading and mutation errors with exact retry counts and payloads;
- all local multiple-choice edit validation branches, explicit approval,
  server failures, per-card concurrent controls, and approve-all behavior;
- server-authoritative completion/mastery percentages and study load/save
  retries that retain the selected answer.

The test runner owns its Vite child process directly so browser runs terminate
reliably on Windows after success or failure.

## Verification evidence

- Frontend release gate: `npm run check` passed.
  - application TypeScript check: passed;
  - Playwright fixture/spec TypeScript check: passed;
  - ESLint: passed with zero errors and zero warnings;
  - production Vite build: passed with 2,300 modules;
  - Chromium browser suite: `31 passed` in 20.3 seconds.
- Full offline backend suite: `82 passed, 13 skipped, 1 deselected` in 13.04
  seconds. The deselected case is the opt-in live provider test, not a failure.
- A disposable PostgreSQL 16 database was migrated from empty through Alembic
  revision `20260914_0003`; the focused concurrent invitation replay test
  passed (`1 passed` in 1.01 seconds). The container used no permanent volume
  and was stopped with automatic removal afterward.
- Generated OpenAPI uses `InvitationAcceptResponse`,
  `FlashcardSetCreateRequest`, and `FlashcardCreateRequest` for the corrected
  invitation, set-create, and card-create contracts.
- Repository scans found no explicit API-layer `any`, no query-client package or
  source reference, and no localhost runtime URL in `frontend/src`.
- `git diff --check` passed. Line-ending notices are Git's existing Windows
  normalization behavior, not whitespace errors.

## React review and deferred release work

- The final React review confirmed module-scoped component definitions,
  complete effect cleanup/dependencies, functional state updates for
  concurrency-sensitive paths, typed boundaries, parallel independent loads,
  stable card IDs, and visible async states. ESLint and all browser tests back
  these checks.
- Vite still reports a bundle chunk above 500 kB and stale Browserslist data.
  Dependency installation also reports 19 advisories (1 low, 4 moderate, 14
  high). These are pre-existing dependency/performance release concerns and
  remain assigned to Phase 8; they do not invalidate the Phase 5 correctness
  gate.
- No live AI provider call was made during Phase 5.
