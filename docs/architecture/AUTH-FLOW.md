# Authentication and Authorization Flow

Current truth verified against code: 2026-09-16.

## Purpose and scope

Explain instructor provisioning, invited student enrollment, browser sessions
and recovery. There is no public instructor signup or supported account email
verification workflow.

## Key components

- [Auth router](../../backend/app/routers/auth.py): register/login/refresh/logout,
  `/me`, recovery and role dependencies.
- [Auth service](../../backend/app/services/auth.py) and
  [user schemas](../../backend/app/schemas/user.py): normalized identity,
  password hashing, typed JWT validation, sessions and invitation/reset consumption.
- [Subject router](../../backend/app/routers/subjects.py) and
  [subject service](../../backend/app/services/subject.py): invitation creation/
  acceptance and owner/enrollment authorization.
- [User models](../../backend/app/models/user.py),
  [rate limiting](../../backend/app/services/rate_limit.py),
  [operator CLI](../../backend/app/cli.py),
  [frontend auth context](../../frontend/src/context/AuthContext.tsx) and
  [API client](../../frontend/src/services/api.ts).

## Primary flow

1. An operator bootstraps the first instructor through `python -m app.cli
   create-instructor`; subsequent instructor creation requires
   `--allow-additional`. Passwords are prompted, not passed in argv.
2. An owning instructor creates a signed database-backed student invitation
   lasting 1–720 hours. A recipient email optionally binds it to that address
   and queues delivery in the same transaction.
3. Registration creates a student, consumes the invitation and enrolls them
   atomically. Existing students use `/subjects/invitations/accept`. Invitation
   row locking and unique enrollment constrain races. A same-student repeat
   with the still-existing enrollment is accepted by the consumption service;
   an already consumed invitation otherwise returns a conflict.
4. Login creates `auth_sessions`, returns only an access token and sets the
   refresh cookie. The browser keeps access tokens in memory. Defaults are
   15-minute access, 7-day refresh and a 30-day absolute session lifetime.
5. Refresh locks session state, compares the hashed current refresh JTI,
   rotates it and sets a new cookie. Reusing an older refresh token revokes
   the session family, invalidating associated access tokens too.
6. Authenticated requests validate access claims, active database session and
   current user email/role. Instructor writes also check subject ownership;
   student study checks enrollment, publication and card approval.
7. Logout revokes the session and clears the cookie. Recovery atomically queues
   a single-use reset link; resetting consumes the token, changes the password,
   revokes all sessions and queues a security notification.

## Important invariants

- Access, refresh, invitation and password-reset JWT types cannot be cross-used.
  Verifiers check signature, issuer, audience, UUID subjects/JTIs, times and
  required session or invitation claims.
- Refresh tokens are cookie-only: HttpOnly, SameSite `lax`/`strict`, path
  `/auth`; Secure is required in production. They are absent from response JSON.
- Emails are trimmed/lowercased; the database enforces normalized uniqueness.
  Password inputs are 8–128 characters; hashing uses `bcrypt_sha256` and can
  verify legacy bcrypt hashes.
- Forgot-password replies are generic and SMTP runs in a separate worker.
  PostgreSQL-backed rate limits protect sensitive endpoints; identifiers are hashed.
- Root `.env` is the sole user-managed configuration file. Production rejects
  insecure signing keys, debug mode, insecure refresh cookies, non-HTTPS frontend
  URLs and insecure/loopback CORS origins. SMTP delivery validation belongs to
  the email worker.

## Failures and limits

Invalid/expired/revoked access or refresh state yields 401; role/ownership/
enrollment violations yield 403. Invitation expiry/type errors and reset errors
are controlled responses; enrollment/consumption races can return 409.
New-student registration rolls back if enrollment fails. Recovery queue errors
remain non-enumerating and are logged without recipient secrets.

The study-session response omits answers; the general student-authorized card
read endpoints currently return `FlashcardResponse`, including `back_content`.
This is a known answer-disclosure limitation, not an exam-security guarantee.

## Sources, verification and related decisions

Read [auth operations](../AUTHENTICATION.md),
[email delivery](../EMAIL_DELIVERY.md),
[auth session tests](../../backend/tests/test_auth_sessions.py),
[authorization tests](../../backend/tests/test_authorization.py),
[invitation tests](../../backend/tests/test_invitations.py) and
[backend map](../../backend/MOC.md).
Decisions: [session/role boundaries](../decisions/ADR-009-session-and-role-boundaries.md)
and [deletion ownership](../decisions/ADR-005-deletion-cascades.md).
Continue with [system overview](SYSTEM-OVERVIEW.md) and [data model](DATA-MODEL.md).
