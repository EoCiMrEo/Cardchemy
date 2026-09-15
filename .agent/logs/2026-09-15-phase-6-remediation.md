# Phase 6 remediation - reliable, accessible, responsive study

Date: 2026-09-15

## Scope and repository context

- Completed every item under Phase 6 in `issues-required-remediation.md` after
  reading the existing remediation logs and tracing the study request from the
  React controls through the API service, FastAPI route, transaction, models,
  Alembic migration, and PostgreSQL concurrency behavior.
- `/.agent/AGENTS.md` was not present. Existing Phase 0-5 working-tree changes
  were preserved; no reset, checkout, or destructive cleanup was used.
- Parallel agents audited the backend contract/concurrency, shared React UI,
  and browser coverage. The coordinating review then fixed the integration
  findings, extended the accessibility-state coverage, and ran the combined
  release gates.
- Product scope is explicitly an online-first responsive web client. Offline
  study was not partially simulated: the obsolete sync API/client and stale
  PWA/offline claims were removed.

## Durable study-answer handling

- Added `study_answer_submissions` in Alembic revision `20260915_0004` with a
  per-student unique SHA-256 idempotency-key hash, canonical request
  fingerprint, exact JSON response receipt, card/user foreign keys, and useful
  indexes. Only the hash is persisted; the client-visible key is not stored.
- `POST /study/progress` now requires a bounded visible-ASCII
  `Idempotency-Key`. A replay with the same logical answer returns the exact
  stored response, while reuse for another card or answer returns a typed 409.
- Receipt reservation, row-locked progress mutation, and receipt completion
  share one database transaction. PostgreSQL adversarial tests cover identical
  retries, mismatched simultaneous reuse, distinct-key races, rollback, and
  exactly-once progress counters.
- The study client creates one key per logical answer, locks synchronous click
  and timeout entry points, reuses the exact key/payload after an ambiguous
  failure, and rotates the key only for the next card. It cannot reveal feedback
  or advance until persistence succeeds; the retry action receives focus.
- Reworked countdown state around an exact deadline with numeric browser timer
  handles, `ceil` display semantics, interval/timeout cleanup, abort cleanup,
  and no side effects inside state-setter callbacks.
- Defensive optionless cards now offer an explicit `I don't know` submission;
  untimed cards never create countdown work. The supported server card type
  remains validated multiple choice.
- Added an explicit `review_all` session mode. `Review Again` requests approved
  cards regardless of due date in stable least-recently-reviewed order instead
  of opening an empty due-only session.

## Accessibility and responsive interaction

- Corrected form-label associations, accessible names for icon-only actions,
  dialog titles/descriptions, progress names/values, status announcements, and
  question/result/completion focus movement.
- The shared `Button` now delegates through Radix `Slot` for `asChild`, avoiding
  nested links/buttons. Preview cards are real keyboard buttons, expose their
  pressed state, and hide the inactive face from the accessibility tree.
- Added visible `focus-visible` indicators and verified the full two-card study
  session using only the keyboard at a 390 by 844 viewport.
- Added user-preference reduced-motion handling globally and in Framer Motion.
  Correct/incorrect/timeout and selected/correct answers have text cues and
  sufficient contrast rather than depending on color or motion alone.
- Core controls use at least 44 by 44 CSS-pixel targets. Dialogs are viewport
  bounded and scrollable; headers, long emails, subject/set actions, forms, and
  card content wrap without horizontal overflow at 320 CSS pixels. Full-page
  layouts use dynamic viewport units.
- A manual live browser accessibility-tree pass confirmed the login and
  password-recovery headings, form labels, control names, logical order, and
  keyboard focus sequence. The visible focus indicator was also inspected.
  `docs/ACCESSIBILITY.md` records the repeatable spoken-output pass for NVDA,
  Narrator, or VoiceOver on each production candidate; spoken audio itself is
  a human release check because it cannot be observed by this automated agent.

## Automated browser coverage

- Added `@axe-core/playwright` and tests that fail on serious or critical WCAG
  findings without broad exclusions. Covered states include login, dashboard,
  student progress, study question/feedback/save failure/completion, instructor
  set review, and the preview dialog.
- Added regression tests for idempotency-key reuse/rotation, rapid double
  activation at the timer boundary, visible failed-save retry, optionless and
  untimed cards, `review_all`, progress semantics, nested interactive controls,
  icon/dialog names, reduced motion, 320px overflow, touch targets, and the
  complete keyboard-only mobile study flow.
- The first axe run found two serious contrast failures in the student new-card
  count and approved-card status. Both were raised to AA-compatible darker
  colors and the suite was rerun successfully.

## Verification evidence

- Frontend release gate: `npm run check` passed.
  - application TypeScript: passed;
  - Playwright TypeScript: passed;
  - ESLint: passed with zero errors and zero warnings;
  - production Vite build: passed with 2,300 transformed modules;
  - Chromium suite: `44 passed` in 40.9 seconds.
- Full offline backend: `88 passed, 15 skipped, 1 deselected`. The deselected
  test is the opt-in live AI provider case, not a failure.
- Fresh disposable PostgreSQL 16 verification: all `15` PostgreSQL tests
  passed. Alembic migrated base to `20260915_0004`, downgraded to
  `20260914_0003`, and upgraded to head again. The no-volume container was
  stopped and automatically removed.
- Backend compile check and `git diff --check` passed. Repository scans found no
  shipped `/study/sync` route/client/schema, no IndexedDB dependency or service
  worker, no stale offline-capability claim, and no `h-screen`/`min-h-screen`
  layout remaining in application TSX.

## Final React and release review

- The final React review found no render-time side effects, nested component
  definitions, unstable study-card keys, missing async cleanup, or unguarded
  duplicate submission path in the changed code. Shared primitives own target,
  focus, reduced-motion, and semantics behavior instead of page-level copies.
- Vite still warns about a production chunk above 500 kB and stale Browserslist
  data. Dependency installation reports 19 advisories (1 low, 4 moderate, 14
  high). These existing dependency/performance concerns remain assigned to
  Phase 8 and do not invalidate the Phase 6 reliability/accessibility gate.
- No live AI provider call was made during Phase 6.
