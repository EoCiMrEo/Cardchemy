# Transactional email delivery

The application sends only security-sensitive and transactional messages:
password-reset links, instructor-created invitations, and password-change
notifications. Marketing and optional notification campaigns are outside the
v1.0 scope. Account email verification is not a supported workflow and there
is no configuration switch that partially enables it.

Email is written to the PostgreSQL transactional outbox in the same database
transaction as the related application change. The separate email worker
claims pending rows, delivers them through SMTP, and records a sanitized
delivery result. API requests therefore do not wait for the SMTP provider.

## Local development with Mailpit

Start the local stack with the base Compose file:

```powershell
docker compose up -d --build --wait
```

Open the Mailpit UI at <http://127.0.0.1:8025>. Containers deliver to
`mailpit:1025` without authentication, STARTTLS, or implicit TLS. In the base
stack SMTP remains on the Compose network; only the Web UI and API bind to host
loopback.

For native development that needs host access to Mailpit's SMTP port, use the
development override:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile development up -d --build --wait
```

The override publishes SMTP only on host loopback, at MAILPIT_SMTP_PORT.

Mailpit retains at most 250 messages for at most seven days and rejects a
message larger than 2 MiB. Its SQLite database is stored in the
`mailpit_data` volume. Use the Mailpit UI or API to clear captured messages
between tests that require an empty inbox.

Mailpit captures messages for local development and CI. It contains password
reset and invitation links and must never be exposed publicly or used as the
production delivery service. Chaos injection is enabled locally so integration
tests can exercise temporary SMTP failures; its triggers are disabled by
default until a test configures them.

## Production SMTP

The email worker calls `require_email_delivery_config()` during startup.
Production startup requires a sender, a non-Mailpit SMTP host, and encrypted
transport. The frontend base URL must be an absolute HTTPS URL without
credentials, a query, or a fragment because it is the trusted origin for links
placed in messages.

Configure one, and only one, transport mode:

| Provider mode | Typical port | `SMTP_STARTTLS` | `SMTP_IMPLICIT_TLS` |
|---|---:|---:|---:|
| STARTTLS | 587 | `true` | `false` |
| Implicit TLS | 465 | `false` | `true` |
| Local Mailpit only | 1025 | `false` | `false` |

The application does not provide a certificate-verification bypass. A provider
that uses SMTP authentication must supply both `SMTP_USERNAME` and
`SMTP_PASSWORD`; credentials are rejected when neither encrypted mode is
enabled. Store the password in the deployment secret manager rather than an
image, repository file, or operator log.

Example for a standard STARTTLS provider:

```dotenv
ENVIRONMENT=production
FRONTEND_BASE_URL=https://cards.example.com
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=provider-account
SMTP_PASSWORD=<deployment-secret>
SMTP_FROM_EMAIL=no-reply@example.com
SMTP_FROM_NAME=Cardchemy
SMTP_REPLY_TO=support@example.com
SMTP_STARTTLS=true
SMTP_IMPLICIT_TLS=false
```

For a port 465 provider, set `SMTP_STARTTLS=false` and
`SMTP_IMPLICIT_TLS=true`. `SMTP_FROM_NAME` and `SMTP_REPLY_TO` are optional;
the application name is the sender-name fallback. Hostnames, sender and
reply-to addresses, authentication pairs, and all header display text are
validated before delivery. Control characters and URL-shaped SMTP hosts are
rejected.

## Timeouts, retries, and recovery

The defaults are conservative for a small self-hosted installation:

| Setting | Default | Purpose |
|---|---:|---|
| `SMTP_TIMEOUT_SECONDS` | 15 | Bounds one SMTP operation |
| `EMAIL_WORKER_CONCURRENCY` | 4 | Bounds concurrent deliveries per worker |
| `EMAIL_WORKER_POLL_SECONDS` | 1 | Delay between empty queue polls |
| `EMAIL_LEASE_SECONDS` | 240 | Recovers work abandoned by a stopped worker |
| `EMAIL_MAX_ATTEMPTS` | 5 | Caps automatic delivery attempts |
| `EMAIL_RETRY_BASE_SECONDS` | 5 | Initial exponential-backoff bound |
| `EMAIL_RETRY_MAX_SECONDS` | 300 | Maximum retry-delay bound |
| `EMAIL_CLEANUP_INTERVAL_SECONDS` | 3600 | Interval between retention cleanup passes |
| `EMAIL_SENT_RETENTION_DAYS` | 7 | Retains delivered status for diagnosis |
| `EMAIL_FAILED_RETENTION_DAYS` | 30 | Retains terminal sanitized failures |
| `EMAIL_SECURITY_NOTIFICATION_EXPIRE_HOURS` | 24 | Prevents stale security notifications |

Temporary disconnects, timeouts, and SMTP 4xx responses are retried with
bounded exponential backoff and jitter. Permanent recipient, authentication,
certificate, and SMTP 5xx failures become terminal rather than retrying
forever. Fix the provider configuration or recipient problem, restart the
email worker, and inspect the queue without exposing recipients or message
content:

```powershell
python -m app.cli email-outbox-status
python -m app.cli email-outbox-status --limit 50
```

After correcting the cause, requeue one unexpired failed event by ID:

```powershell
python -m app.cli retry-email --id <outbox-uuid>
```

The command grants at most one additional attempt at a time and preserves the
cumulative attempt counter, up to the database-enforced ten-attempt ceiling.
Do not manually edit outbox state or mark a row as sent.

Worker logs identify only the outbox event, safe error category, and attempt.
They must not contain SMTP credentials, recipient addresses, tokens, message
bodies, or reset/invitation URLs. Provider exception strings are not safe to
persist or log verbatim.

An expired lease is retried only when delivery had not started. If the worker
loses its lease after SMTP begins, the row becomes a terminal
`smtp_delivery_ambiguous` failure for operator review rather than knowingly
sending a duplicate. SMTP may already have accepted that message. A deliberate
operator retry therefore requires `--allow-ambiguous` and can cause duplicate
delivery; check the relay or Mailpit by the stable `Message-ID` first.

The outbox, row leases, unique event keys, and stable `Message-ID` values
prevent duplicate queueing and concurrent-worker sends. SMTP itself has no
portable idempotency contract: if a provider accepts a message but the
connection fails before its acknowledgement reaches the worker, an explicit
operator retry can produce a duplicate. Templates and downstream handling must
tolerate that narrow ambiguity.

## Sender-domain responsibility

The deployment operator owns deliverability and domain reputation. Before
sending production mail:

1. Authorize the chosen relay in the sender domain's SPF record.
2. Enable DKIM signing at the relay and publish its selector records.
3. Publish and monitor a DMARC policy aligned with the visible From domain.
4. Verify the sender identity/domain with the SMTP provider and configure
   bounce and complaint handling there.

The application supplies standards-compliant multipart messages, but SMTP
configuration alone cannot create or maintain these DNS and provider controls.
