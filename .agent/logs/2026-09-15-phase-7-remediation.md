# Phase 7 remediation - durable transactional email and SMTP delivery

Date: 2026-09-15

## Scope and repository context

- Completed every Phase 7 item in `issues-required-remediation.md` after
  reviewing the Phase 0-6 implementation logs and tracing password recovery and
  invitation creation from React through FastAPI transactions, PostgreSQL domain
  records, the outbox worker, SMTP, and Mailpit capture.
- `/.agent/AGENTS.md` was not present. Existing uncommitted work, including the
  user's Phase 7 roadmap edits, was preserved. No repository reset or checkout
  was used.
- Parallel agents audited authentication/email flows, outbox tests, and
  SMTP/Compose concerns. The coordinating review integrated their useful
  findings, added the missing live reset-page journey, and ran the combined
  release gates. A final follow-up audit agent became unavailable at its service
  limit, so its absence was not treated as verification evidence.
- Product scope remains transactional only: password recovery, password-change
  security notices, and instructor-created student invitations. Marketing mail
  is outside v1.0. The unused email-verification flag was removed; account email
  verification is deliberately not a supported or partially enabled workflow.

## SMTP configuration and local capture

- Added pinned `axllent/mailpit:v1.31.1` development/test capture with a health
  check, a 250-message/seven-day/2-MiB bound, local chaos injection, and a
  persistent capture volume. Only the combined UI/API port `8025` is published
  on IPv4 loopback; SMTP port `1025` stays inside the Compose network.
- Local email delivery uses `mailpit:1025` without authentication or encryption.
  Production supports explicit STARTTLS or implicit TLS and rejects cleartext
  credentials, simultaneous TLS modes, Mailpit, or an unencrypted production
  transport.
- SMTP host, port, authentication pairs, sender, sender name, reply-to address,
  header text, frontend link origin, timeouts, concurrency, lease duration,
  retry bounds, and retention values are validated. Production message links
  require an absolute HTTPS frontend origin with no credentials, query, or
  fragment.
- SMTP credentials are available only to the dedicated email-worker service;
  the API and migration services do not receive them. Delivery configuration is
  fail-fast at email-worker startup, so API startup does not require relay
  access.

## Durable delivery architecture

- Added Alembic revision `20260915_0005` with the `email_outbox_messages` table,
  recipient-bound invitations, status/timestamp/attempt constraints, domain
  foreign keys, hashed idempotency keys, stable message IDs, claim fencing, and
  partial queue, lease, expiry, and retention indexes.
- Password reset token creation plus outbox enqueue, invitation creation plus
  outbox enqueue, and password mutation plus security-notification enqueue each
  share one caller-owned database transaction. SMTP never runs in an API
  request.
- Outbox rows contain normalized recipients, event/domain references, delivery
  metadata, and sanitized error codes only. Reset/invitation tokens, rendered
  message bodies, and URLs are derived only after a worker owns a valid lease
  and are never persisted in the outbox.
- The dedicated worker uses PostgreSQL `FOR UPDATE SKIP LOCKED`, bounded local
  concurrency, random fencing tokens, a lease longer than the SMTP timeout,
  bounded exponential backoff with full jitter, automatic-attempt ceilings, and
  cleanup for expired/sent/failed records.
- Stable event idempotency and `Message-ID` values prevent duplicate enqueueing
  and concurrent-worker sends. A crash or disconnect after delivery begins is
  classified as terminal `smtp_delivery_ambiguous` instead of being
  automatically resent. Explicit operator retry requires acknowledgement of
  the possible duplicate and is database-capped at ten cumulative attempts.
- Added recipient-free queue status and guarded single-event retry commands.
  Worker/operator output exposes only event IDs, type, attempt count, and safe
  error category.

## Templates and application flows

- Replaced the reset-only helper with an injectable transport, a typed composer,
  and escaped plain-text/HTML templates for password reset, password changed,
  and student invitation events. Messages carry validated headers, UTC dates,
  accessible visible links, and stable IDs.
- Password recovery continues to return the same delayed `202` payload for
  known and unknown accounts while internal queue failures remain observable.
  Reset links stay short-lived and single-use; successful reset revokes every
  existing session and queues a token-free security notice.
- Invitations may now be bound and emailed to an optional normalized recipient.
  The UI still displays the server-generated absolute invitation URL and keeps
  it copyable for operator-controlled sharing. Recipient-bound tokens cannot be
  consumed by a different student.

## Verification evidence

- Full offline backend: `115 passed, 22 skipped, 1 deselected` in 21.63 seconds.
  Skips are the explicitly environment-gated PostgreSQL/Mailpit suites; the one
  deselected test is the opt-in live AI-provider test, not a failure.
- Full backend with disposable PostgreSQL 16 and Mailpit enabled: `137 passed,
  1 deselected` in 32.56 seconds. This covered all PostgreSQL concurrency and
  Mailpit API tests, including temporary SMTP rejection fault injection.
- Phase 7 targeted unit/config/invitation regression: `40 passed`.
- Alembic verification reached head `20260915_0005`; offline SQL generation,
  `alembic current --check-heads`, `alembic check`, and live downgrade to
  `20260915_0004` followed by upgrade to head all passed. A model/migration ID
  default mismatch found by `alembic check` was corrected before closure.
- The final Compose email worker was healthy and the safe operator status command
  reported zero pending/sending/sent/failed rows before the journey tests.
- Mailpit integration verified recipient, subject, text and HTML bodies, reset
  and invitation links, password-change content, token consumption, and a 451
  chaos response followed by a successful retry.
- A dedicated live Chromium journey passed in 7.7 seconds: the browser requested
  recovery, Mailpit captured the email, the captured link opened the real reset
  page, the new password succeeded, the same token was rejected on reuse, the
  old password failed, and the new password reached the dashboard.
- Frontend release gate `npm run check` passed: application and E2E TypeScript,
  ESLint, production Vite build, and Chromium tests. Normal results were `46
  passed, 1 skipped`; the skip is the deliberately opt-in live Mailpit browser
  journey, which was also executed separately and passed once.
- Backend bytecode compilation and `git diff --check` passed. Unit assertions
  proved logs omit recipient addresses, provider detail, message bodies, reset
  paths, and tokens. Source review found no application log statement that
  emits credentials, token-bearing URLs, or rendered messages.
- Manual browser inspection at a 390 by 844 viewport confirmed the reset page's
  safe invalid-token state and the Mailpit UI's captured multipart message. The
  browser session and generated inspection artifacts were removed afterward.
- The disposable verification account, Compose project, containers, network,
  PostgreSQL/Mailpit volumes, temporary port override, and Vite process were all
  removed after the tests. The user's pre-existing `flashcardgenerator` Compose
  resources were not changed.

## Operational documentation and residual notes

- `docs/EMAIL_DELIVERY.md` now separates local Mailpit from production SMTP,
  documents ports/security modes, worker/retry/retention settings, safe status
  and recovery commands, ambiguous-delivery handling, and operator ownership of
  SPF, DKIM, DMARC, sender verification, bounces, and complaints.
- Authentication, database operations, example environment values, and the
  changelog reflect the no-verification decision, outbox migration, dedicated
  worker, and production SMTP requirements.
- Vite still reports the pre-existing stale Browserslist dataset and a generated
  JavaScript chunk above 500 kB. These Phase 8 dependency/performance concerns
  do not invalidate the Phase 7 delivery gate. No live AI-provider call was made.
