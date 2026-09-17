# Clean-machine production and recovery rehearsal

The manually dispatched **Production recovery rehearsal** workflow runs on a
new GitHub-hosted Ubuntu 24.04 Linux/amd64 machine from protected `main`. It
executes [the guarded harness](../scripts/test_production_rehearsal.py) using
the exact committed source, without repository secrets or operator settings.
This is the repeatable release check for a fresh production-profile install
and a recoverable current-head database backup.

The harness creates a private temporary clone, runs the maintained environment
bootstrap, and builds the unchanged application Dockerfiles. It starts the
base Compose plus the production override, with the API/database unpublished,
Mailpit excluded, debug/docs disabled, independent generated keys, and secure
refresh cookies. A temporary TLS edge publishes only on IPv4 loopback. The
edge retains the frontend image's real healthcheck using a dedicated
container-loopback-only `/healthz` listener; that HTTP listener has no published
port. This avoids disabled inherited healthchecks failing older Compose wait
contracts. Application requests still use certificate-validating HTTPS.
reserved `cards.rehearsal.test` name resolves inside the harness to loopback;
a generated CA issues a separate server certificate with explicit constraints,
key usages, identity extensions and SAN, including Python 3.13 strict TLS
verification support. That CA is trusted only by the harness. It does not change
host DNS, certificate trust, firewall, public hosting or a real installation.

Using the maintained operator CLI and real HTTPS APIs, it creates a disposable
instructor, subject, approved manual card, publication, invitation-backed
student and server-graded study answer. It verifies TLS certificate validation,
same-origin proxying, refresh/logout, secure cookie attributes, SPA deep links,
security headers and closed production API docs. It then drains/stops writers,
creates a PostgreSQL custom archive, and matches its SHA-256 on the host and
inside both database containers. The archive is restored into a second
uniquely named project with a verified empty database and separate volume.
`upgrade head`, `current --check-heads` and `alembic check` must pass there.
Representative instructor/student reads, progress and the original answer
receipt must survive; retrying that answer must leave the counts unchanged.

All API interactions use fixtures; no direct database mutation seeds records.
Read-only aggregate SQL checks compare schema revision and representative row
counts. Cleanup validates exact volume names, Compose ownership labels and
image ownership before removing only generated resources. The real root
`.env`, databases and Docker volumes remain outside the rehearsal.

The workflow retains one content-free JSON summary for 90 days, containing
the source SHA, Compose version, schema head, archive checksum, aggregate counts, completed
checks and verified cleanup. It never uploads the environment, certificates,
backup archive, credentials, cookies, tokens or raw service/build logs. A
failed run provides no passing evidence.

On another clean Linux/amd64 Docker host with Python 3.11+, Git and OpenSSL:

```text
python scripts/test_production_rehearsal.py --evidence /tmp/cardchemy-rehearsal-result.json
```

The source checkout must be clean and committed. The result is release
evidence only for the exact recorded source SHA. The normal PostgreSQL
regression harness additionally tests the complete historical migration
chain and reversal; see [Testing](TESTING.md).

This check proves strict production settings, local TLS and database recovery.
AI is disabled, encrypted SMTP is configured with a reserved offline `.test`
host, and the outbox must stay empty. It does not claim paid-provider success,
external SMTP delivery, public DNS/ACME, a real deployment or an operator's
RPO/RTO. Those site-specific responsibilities remain in
[Deployment](DEPLOYMENT.md), [Database operations](DATABASE_OPERATIONS.md)
and [Email delivery](EMAIL_DELIVERY.md).
