# ADR-009: Stateful rotating sessions and explicit roles

## Status

Accepted; existing behavior verified 2026-09-16.

## Context

Instructor provisioning, student enrollment and browser-token handling need
clear security boundaries and revocable sessions.

## Decision

Instructor creation is operator-only; public registration creates invited
students atomically with enrollment. Access JWTs remain in browser memory;
refresh JWTs use an HttpOnly SameSite cookie and a database-backed rotating
JTI family with an absolute lifetime. Refresh reuse, logout and password
reset revoke server-side session state. Every request verifies the current
session/user; roles plus ownership/enrollment guard product actions.

## Rationale

This prevents public privilege escalation, avoids persistent browser access
token storage and lets revocation invalidate access before JWT expiry.

## Consequences

Requests depend on database availability. Clients must coordinate refresh
and handle session end. Additional instructors require an explicit CLI flag;
account email verification is not a supported workflow. Production requires
secure cookies/HTTPS and SMTP delivery validation in the email worker.

## Related Areas

[Auth flow](../architecture/AUTH-FLOW.md),
[auth service](../../backend/app/services/auth.py),
[role dependencies](../../backend/app/routers/auth.py),
[operator CLI](../../backend/app/cli.py), [ADR index](ADR-000-INDEX.md).
