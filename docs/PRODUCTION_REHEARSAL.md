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
The reserved `cards.rehearsal.test` name resolves inside the harness to loopback;
a generated CA issues a separate server certificate with explicit constraints,
key usages, identity extensions and SAN, including Python 3.13 strict TLS
verification support. That CA is trusted only by the harness. It does not change
host DNS, certificate trust, firewall, public hosting or a real installation.

Using the maintained operator CLI and real HTTPS APIs, it creates a disposable
instructor, two subjects, an approved manual card and publication, plus two
invitation-backed students. One student completes a server-graded study answer;
the other is enrolled only in the isolation-control subject. It verifies TLS
certificate validation, same-origin proxying, refresh/logout, secure cookie
attributes, SPA deep links, security headers and closed production API docs.

There is intentionally no provider-free public API that can manufacture a
completed embedding or model answer. With every AI enablement and provider
switch forced off, the harness therefore adds one fixed synthetic Knowledge/RAG
fixture directly through PostgreSQL. The fixture follows the database's guarded
processing transitions: captured page, pending then ready active index, 1536
dimension vector, owner review/publication, queued then claimed/completed answer
job, private messages and one exact grounded citation. It uses a reserved
`.invalid` endpoint only as immutable metadata and records zero provider
requests. This fixture contains no user document, model output, credential or
network call. The application APIs then verify the published Knowledge state,
enrolled student's private history/job/citation, instructor thread isolation,
other-student Subject isolation, and that new Ask AI work remains disabled.

The harness drains/stops all writers, creates a PostgreSQL custom archive, and
matches its SHA-256 on the host and inside both database containers. The archive
is restored into a second uniquely named project with a verified empty database
and separate volume. Before and after application startup it checks pgvector
0.8.6, the `vector(1536)` column, valid Knowledge indexes, the active published
revision, exact nearest-vector retrieval constrained by enrollment and Subject,
the negative other-student retrieval case, private RAG rows and the exact
citation provenance. `upgrade head`, `current --check-heads` and `alembic check`
must pass there. Representative instructor/student reads, progress, the original
answer receipt and all populated RAG state must survive; retrying the study
answer must leave the tracked counts unchanged.

Aggregate SQL checks compare schema revision and representative row counts.
Cleanup validates exact volume names, Compose ownership labels and image
ownership before removing only generated resources. The real root `.env`,
databases and Docker volumes remain outside the rehearsal.

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
AI is disabled, no generation/index/answer provider call is made, encrypted
SMTP is configured with a reserved offline `.test` host, and the outbox must
stay empty. The smaller [pgvector restore probe](../scripts/test_pgvector_restore.py)
separately restores into an empty ephemeral database and verifies the extension,
HNSW/GIN indexes, active/published filtering and enrolled/other-student query
isolation with three-dimensional synthetic vectors. Neither check claims paid-
provider success, external SMTP delivery, public DNS/ACME, a real deployment or
an operator's RPO/RTO. Those site-specific responsibilities remain in
[Deployment](DEPLOYMENT.md), [Database operations](DATABASE_OPERATIONS.md)
and [Email delivery](EMAIL_DELIVERY.md).
