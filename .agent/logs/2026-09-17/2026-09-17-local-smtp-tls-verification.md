# Local encrypted SMTP release-gate verification

Date: 2026-09-17. Scope: self-hosted production SMTP setup and recovery evidence.

## Context and authorization

The owner clarified that this project is intended for self-hosting with local
SMTP rather than an online provider. Verification therefore uses synthetic
messages captured by disposable local services, with no external mailbox,
provider quota, production configuration or database. Production encryption
and certificate-validation requirements remain intact.

Read the current email guide, testing command authority, SMTP transport,
outbox worker, PostgreSQL fixture guards, existing Mailpit integration tests
and disposable service harness. Mailpit's official SMTP configuration and
password-file documentation define the capture-server TLS and authentication
settings. Existing root `.env` and operator services/data were preserved.

## Implementation

- Added `scripts/test_smtp_tls.py`: unique temporary PostgreSQL plus pinned
  Mailpit v1.31.1 capture services for mandatory STARTTLS and implicit TLS;
  generated ephemeral credentials, one-day CA/server certificates, random
  loopback ports, scoped subprocess trust and verified container cleanup.
- Added `backend/tests/integration/test_smtp_tls.py`: real application SMTP
  transport, worker, transactional PostgreSQL outbox and operator retry logic,
  with validated production settings and synthetic recipient metadata.
- Added the opt-in `smtp_tls` pytest marker. Ordinary offline runs skip these
  cases; those skips are not TLS delivery evidence.
- Added `docs/SMTP-VERIFICATION.md` explaining the command, actual coverage,
  self-hosted relay responsibilities and evidence limits.

Database credentials are not mounted into the capture servers. Their TLS
directory is read-only, the client does not install host trust or disable
certificate checks, and the capture API guard allows only host loopback.
Application SMTP/worker runtime logic and production validation were unchanged.

## Actual verification

Final command from the repository root:

```powershell
backend\venv\Scripts\python.exe scripts/test_smtp_tls.py
```

Passed all twelve actual integration cases in 12.25 seconds after successful
Alembic upgrade/current-head and no-drift checks. Each transport mode verified:

1. Authenticated encrypted delivery captured once and committed `sent`.
2. Untrusted CA rejected as terminal `smtp_tls_failed`, no captured message.
3. Wrong certificate hostname rejected with the same safe terminal category.
4. Real SMTP 451 rejection persisted `pending`, then delivered once on attempt
   two after the server recovered, preserving the event and `Message-ID`.
5. Real authentication failure stayed terminal until corrected credentials and
   explicit operator retry restored delivery on the same event.
6. Actual SMTP acceptance followed by a controlled expired application-worker
   lease became terminal `smtp_delivery_ambiguous`; no automatic resend occurred,
   and operator retry refused without ambiguity acknowledgement.

The harness removed its uniquely named services and verified their absence;
temporary database data, certificate keys, credential files and synthetic
captures were deleted. Earlier successful full run: twelve passed in 18.17
seconds. Ordinary offline invocation of the dedicated test file: twelve
skipped in 1.63 seconds, intentionally non-evidence. Python compilation and
`git diff --check` passed.

## Initial failure and limits

The first harness run rejected its generated positive certificate because
Python 3.13 strict TLS verification requires Authority Key Identifier and
related X.509 extensions. Eight failed/four passed was not release evidence.
Corrected the ephemeral test CA/server certificates with AKI/SKI and KeyUsage;
no application or interpreter trust requirement was relaxed. Both subsequent
positive/negative full runs passed.

The lost-lease case controls the lease clock after a real accepted TLS message;
it rehearses worker interruption before the success commit, not every possible
wire-level SMTP acknowledgement loss. Mailpit is used only as a local test
capture and is not endorsed as a production relay. These results establish
local encrypted application transport and durable recovery; every deployment
operator still owns their actual relay routing, trust, mailbox delivery and
retention. No external DNS/provider/inbox deliverability is claimed.
