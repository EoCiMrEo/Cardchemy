# Authentication, invitations and transactional email

Operators create instructors through the CLI. Public registration creates only
invited students. The API owns normalized identities, session validation,
invitation consumption and role/access checks.

```mermaid
flowchart TD
  Operator["Operator CLI: create instructor"] --> Instructor["Instructor account"]
  Instructor --> Own["Own Subject"]
  Own --> Invite["Signed, expiring, database-backed invitation"]
  Invite --> Recipient{"Recipient email supplied?"}
  Recipient -->|"Yes"| Outbox["Atomic invitation + outbox enqueue"]
  Recipient -->|"No"| Share["Instructor receives shareable invitation"]
  Outbox --> Student["Invited student"]
  Share --> Student
  Student --> Registered{"Already registered?"}
  Registered -->|"No"| Register["Atomic student creation + invite consumption + enrollment"]
  Registered -->|"Yes"| Accept["Authenticated invitation acceptance"]
  Accept --> Enrollment["Single Subject enrollment"]
  Register --> Enrollment
  Enrollment --> Access["Published approved cards and eligible published Knowledge"]
```

An optional recipient binding must match the student's normalized email.
Expiry, row locks, single-use consumption and unique enrollment control races.
Additional instructor provisioning requires `--allow-additional`. No account
email-verification workflow is implemented.

## Browser sessions and recovery

```mermaid
sequenceDiagram
  participant B as Browser
  participant A as API
  participant D as PostgreSQL
  B->>A: Login credentials
  A->>D: Verify hash and create revocable session
  A-->>B: Access token in memory + HttpOnly refresh cookie
  B->>A: Protected request with access token
  A->>D: Validate active session, role and current access
  A-->>B: Authorized response
  B->>A: Refresh cookie on reload or shared 401 recovery
  A->>D: Lock session and rotate hashed refresh identity
  A-->>B: New access token and rotated cookie
  Note over A,D: Older refresh reuse revokes the session family
  B->>A: Logout or single-use password reset
  A->>D: Revoke session or all account sessions
  A-->>B: Clear cookie and sign in again when required
```

JWT purpose, issuer/audience, identity/JTI/time and session checks stay
server-owned. Refresh tokens never appear in JSON or browser storage.
Recovery responses are generic; reset consumption, password change, session
revocation and notification enqueue share one transaction.

## Outbox to SMTP

```mermaid
flowchart TD
  Event["Invitation, reset or password-change event"] --> Transaction["Domain mutation + unique outbox event in one transaction"]
  Transaction --> Response["API responds without waiting for SMTP"]
  Transaction --> Queue["PostgreSQL outbox"]
  Queue --> Worker["Email worker: claim lease and render at send time"]
  Worker --> SMTP["Mailpit locally / encrypted SMTP in production"]
  SMTP --> Outcome{"Delivery outcome"}
  Outcome -->|"Acknowledged"| Sent["Fenced sent status"]
  Outcome -->|"Unambiguous transient rejection"| Retry["Bounded delayed retry"]
  Retry --> Queue
  Outcome -->|"Permanent failure"| Failed["Safe terminal failure"]
  Outcome -->|"Disconnect/timeout during send or lease lost"| Ambiguous["Operator review; no automatic duplicate send"]
```

Outbox rows store event/template data, not rendered link-bearing message bodies.
The worker renders valid links at send time and uses a stable Message-ID.
Exactly-once SMTP delivery is not guaranteed: a relay can accept a message
before its acknowledgement is lost. Production uses verified STARTTLS or
implicit TLS; local Mailpit captures sensitive messages for local/test use only.
Logs omit recipients, bodies, credentials and invitation/reset URLs.

Sources: [auth contract](../architecture/AUTH-FLOW.md),
[auth router](../../backend/app/routers/auth.py),
[auth service](../../backend/app/services/auth.py),
[subject service](../../backend/app/services/subject.py),
[browser session](../../frontend/src/context/AuthContext.tsx),
[API refresh coordination](../../frontend/src/services/api.ts),
[email service](../../backend/app/services/email.py),
[email worker](../../backend/app/workers/email.py),
[email operations](../mail-server/EMAIL_DELIVERY.md).
