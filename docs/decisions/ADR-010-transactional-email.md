# ADR-010: Deliver transactional email through a durable outbox

## Status

Accepted. Current implementation verified on 2026-09-16.

## Context

Password recovery, password-change notices, and optional recipient-bound
invitations must survive relay/API failures without blocking an API request or
committing an application change separately from its delivery event. SMTP has
no portable exactly-once delivery contract.

## Decision

Enqueue the domain event in PostgreSQL in the initiating database transaction.
A separate email worker claims with `FOR UPDATE SKIP LOCKED`, random fencing
tokens, bounded concurrency, leases, expiry, retention, and capped attempts.
Render messages and derive links only after a valid claim. Store recipient,
domain references, delivery metadata, hashed event keys, stable `Message-ID`,
and sanitized errors; do not persist tokens, URLs, or rendered message bodies
in the outbox.

Retry unambiguous transient failures with bounded exponential backoff/full
jitter. Delivery-stage disconnects/timeouts and expired leases after delivery
starts become terminal `smtp_delivery_ambiguous`; an operator retry requires
explicit duplicate-risk acknowledgement and remains capped. Use local Mailpit
for capture and validated STARTTLS/implicit TLS for production SMTP.

## Rationale

Atomic enqueue preserves the relationship between domain state and delivery
intent. Separate delivery isolates relay latency and credentials. Conservative
ambiguous-delivery handling avoids automatically resending an email the relay
may already have accepted.

## Consequences

API responses confirm acceptance, not SMTP delivery. Stable event keys prevent
duplicate enqueueing and leases fence claims; a stable `Message-ID` does not
guarantee relay deduplication. Operators must resolve ambiguous sends and own
sender-domain deliverability. Logs omit recipients, secrets, tokens, URLs,
message bodies, and raw relay exception text. Account email verification and
marketing mail are outside the accepted product workflow.

## Related areas

- [System overview](../architecture/SYSTEM-OVERVIEW.md),
  [authentication flow](../architecture/AUTH-FLOW.md), [email operations](../EMAIL_DELIVERY.md)
- [Email service/templates/transport](../../backend/app/services/email.py),
  [email worker](../../backend/app/workers/email.py),
  [outbox models](../../backend/app/models/email.py),
  [operator CLI](../../backend/app/cli.py)
- [Delivery regressions](../../backend/tests/test_email_delivery.py),
  [PostgreSQL outbox tests](../../backend/tests/postgres/test_email_outbox.py),
  [ADR index](ADR-000-INDEX.md)
