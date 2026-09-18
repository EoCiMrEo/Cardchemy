# Deployment and self-hosting

The base Compose stack is a production-shaped local installation: it builds the
frontend and backend, migrates PostgreSQL before starting the API, runs separate
generation and email workers, captures local mail in Mailpit, and exposes only
the frontend and Mailpit UI on IPv4 loopback. It has no source mounts, reload
mode, debug mode, public API port, or public database port.

## Clean-clone quick start

Prerequisites are listed in [Supported runtimes](RUNTIMES.md). Use
[Configuration](CONFIGURATION.md) for the single root environment file,
native-development routing, setting ranges, and update/rebuild rules. From the
repository root:

```text
python scripts/bootstrap_env.py
python scripts/check_config_migration.py
docker compose config --quiet
docker compose up -d --build --wait
docker compose exec backend python -m app.cli create-instructor --email instructor@example.com
```

The bootstrap command creates `.env` once, refuses to overwrite it, generates
the database password and two application keys independently, and never prints
their values. The application is at <http://127.0.0.1:8080>; Mailpit is at
<http://127.0.0.1:8025>. A provider key is optional for startup but required to
generate cards; set `FLASHCARD_AI_PROVIDER_ENABLED=true` only after configuring that key.
The API receives this non-secret switch while the credential remains isolated
to the generation worker. Stop the stack with `docker compose down`; do not add
`--volumes` unless destroying all local application data is intentional.

## Compose variants

Use exactly one override at a time:

```text
# Development: host DB/API ports, backend bind mounts, API reload
python scripts/check_config_migration.py
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile development up -d --build --wait

# Production: strict production settings, real encrypted SMTP, no Mailpit
python scripts/check_config_migration.py
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile production config --quiet
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile production up -d --build --wait
```

The development override publishes PostgreSQL and the API on loopback only. The
production override still publishes only the frontend on loopback, so an
operator-controlled TLS proxy on the same host is the sole public entry point.
Before production validation, set a public HTTPS `FRONTEND_BASE_URL`, HTTPS
`CORS_ORIGINS`, a real `SMTP_HOST` and `SMTP_FROM_EMAIL`, and explicit
`SMTP_STARTTLS`/`SMTP_IMPLICIT_TLS` values in `.env`. Exactly one SMTP TLS mode
must be true. Production validation rejects localhost origins, HTTP links,
debug mode, insecure cookies, Mailpit, cleartext authenticated SMTP, and weak
application secrets.

| Address | Local/default | Development override | Production |
|---|---|---|---|
| Browser application and `/api/*` | `127.0.0.1:8080` | `127.0.0.1:8080` | TLS proxy -> `127.0.0.1:8080` |
| Direct API | Compose network only | `127.0.0.1:8000` | Compose network only |
| PostgreSQL | Compose network only | `127.0.0.1:5432` | Compose network only |
| Mailpit Web UI | `127.0.0.1:8025` | `127.0.0.1:8025` | disabled |
| Mailpit SMTP | Compose network only | `127.0.0.1:1025` | disabled |

The frontend server strips `/api` before proxying to `backend:8000` and rewrites
the refresh-cookie path from `/auth` to `/api/auth`. `VITE_API_URL=/api` keeps
the image independent from a public domain. Do not publish the backend port in
production. `FORWARDED_ALLOW_IPS=*` is safe only while that API remains on the
private Compose network; deployments that expose it must replace the wildcard
with the exact trusted proxy addresses.

## TLS, proxy, and browser security

Point Caddy, Nginx, Traefik, or another maintained host proxy at
`127.0.0.1:8080`. Permit public TCP 80 only for ACME redirect/challenge traffic
and TCP 443 for the application; do not permit 5432 or 8000. A minimal Caddy
site is:

```caddyfile
cards.example.com {
    reverse_proxy 127.0.0.1:8080
    header Strict-Transport-Security "max-age=31536000; includeSubDomains"
}
```

Enable HSTS only after the domain and every included subdomain work reliably
over HTTPS; add `preload` only after separately meeting browser preload policy.
Preserve `Host`, `X-Forwarded-For`, and `X-Forwarded-Proto`. Never trust forwarded
headers from arbitrary public clients.

The frontend server applies a same-origin CSP, denies framing and MIME sniffing,
uses `strict-origin-when-cross-origin`, and disables unused browser capabilities.
Its CSP deliberately permits inline styles required by the current UI but no
inline scripts. TLS termination owns HSTS because the local container endpoint
is intentionally HTTP.

Production API docs are disabled by default. Set `API_DOCS_ENABLED=true` only
after deciding they are intended to be public; with the production proxy their
paths are `/api/docs`, `/api/redoc`, and `/api/openapi.json`.

## Health and graceful shutdown

`/api/health/live` is process liveness and `/api/health/ready` checks the
database. Container readiness uses the database-aware probe. The workers also
check their own scheduling-loop heartbeat and the database, so a stalled loop
cannot remain healthy merely because PostgreSQL answers. Disabled generation
workers continue pulsing; draining workers stop reporting readiness. See
[diagnostics and health](OBSERVABILITY.md) and [privacy controls](PRIVACY.md).

SIGTERM stops workers from claiming new work and gives active work 30 seconds
by default to finish. Compose allows 45 seconds before force-killing them. Tune
`WORKER_SHUTDOWN_GRACE_SECONDS` together with `stop_grace_period`; the Compose
grace must remain longer. An interrupted generation claim is recovered after
its lease expires. An email interrupted after SMTP delivery begins is marked
ambiguous on recovery and is not automatically duplicated. See
[Transactional email delivery](EMAIL_DELIVERY.md).

For planned maintenance, stop public admission first, inspect or drain pending
generation/email work, and then stop workers:

```text
docker compose exec backend python -m app.cli email-outbox-status
docker compose stop -t 45 backend
docker compose stop -t 45 worker email-worker
```

## Volumes, backup, upgrades, and disaster recovery

`postgres_data` contains all durable application records, outbox state, job
state, private Subject Knowledge after capture is implemented, and any
short-lived encrypted source PDFs. `mailpit_data` is local/test
capture only and must not be used or restored in production. The frontend, API,
and workers are replaceable images and have no durable filesystem state.

Before an upgrade:

The PostgreSQL 16/pgvector 0.8.6 Alpine transition needs a separate fresh ICU
target for any earlier Debian/libc cluster. The database entrypoint refuses a
populated unmarked or incompatible legacy volume before starting PostgreSQL.
Back up and restore logically into the new target, verify it, and keep the old
volume until the cutover decision. See the exact
[database operations](DATABASE_OPERATIONS.md#moving-the-prior-debian-installation-to-the-reviewed-alpine-build)
procedure. The operator's explicit approval to discard a particular local
legacy volume does not change this default for other installations.

Keep existing database/Compose project names and secrets while adopting new
images. The [configuration upgrade note](CONFIGURATION.md#existing-installations-and-cardchemy-defaults)
explains legacy authentication defaults and session continuity.

1. Record the current application version and Alembic revision.
2. Stop the API and gracefully drain/stop both workers so the dump is consistent.
3. Create, checksum, encrypt, and copy a PostgreSQL custom-format backup off host.
4. Preserve `.env` or equivalent deployment secrets separately in a secret
   manager. The source encryption key is required to recover retained PDFs.
5. Build/pull the intended immutable release, run `migrate`, verify every
   Alembic head, then start workers, API, and frontend.
6. Check readiness, login, an instructor/student read path, and queues before
   restoring public traffic.

Detailed commands and destructive-operation warnings are in
[Database operations](DATABASE_OPERATIONS.md). Prefer restoring the pre-upgrade
archive into a fresh database over downgrading a data-destructive migration.

Each operator must choose an RPO/RTO appropriate to their users. At minimum,
schedule encrypted off-host database backups, retain more than one generation,
monitor backup failures and free space, and rehearse a restore after schema
changes and at least quarterly. A recovery bundle needs the database archive,
application release identifier, Compose/environment configuration, signing and
source-encryption keys, SMTP/provider configuration, DNS/TLS ownership, archive
checksum, and a written recovery order. A backup that has not passed a separate
restore and representative application check is not considered recoverable.

## Image size and supported platforms

The supported container target is Linux/amd64. Windows and macOS hosts are
supported only through a current Docker Desktop Linux-container VM. Linux/arm64
is best effort until its images, OCR packages, and full runtime smoke test are
covered by release verification; do not advertise it as supported based only
on a successful cross-build.

The backend uses a dependency-builder stage and excludes compilers and headers
from its non-root runtime. OCR binaries are runtime-only and opt-in. The
frontend copies static build output into an unprivileged server image; Node,
npm, source, tests, and build caches are absent from runtime.

The 2026-09-16 Linux/amd64 Phase 9 reference build produced these uncompressed OCI image
sizes:

| Image | Bytes | Approximate decimal size | Runtime user |
|---|---:|---:|---|
| Default backend | 253,771,016 | 253.8 MB | `app` (UID/GID 10001) |
| OCR backend | 362,744,449 | 362.7 MB | `app` (UID/GID 10001) |
| Frontend | 33,806,859 | 33.8 MB | UID/GID 101 |

The previous single-stage backend image was 627 MB, so the measured default
multi-stage runtime is about 60% smaller. Treat these as reference values, not
hard limits: upstream base-image rebuilds can change byte counts without a
Dockerfile change. Re-record exact sizes and verify runtime contents for every
release:

```text
docker image inspect cardchemy-backend:0.1.0 --format "{{.Os}}/{{.Architecture}} {{.Size}} {{.Config.User}}"
docker image inspect cardchemy-frontend:0.1.0 --format "{{.Os}}/{{.Architecture}} {{.Size}} {{.Config.User}}"
docker history cardchemy-backend:0.1.0
docker run --rm cardchemy-backend:0.1.0 sh -c "! command -v gcc && ! command -v node"
```

The release image check should confirm that neither runtime contains build
toolchains or test material, and record the optional OCR image size separately.

The [clean-machine production rehearsal](PRODUCTION_REHEARSAL.md) verifies
this production profile with a trusted local HTTPS edge and a current-head
backup restored into a separate empty volume. Pair it with
[actual local encrypted SMTP verification](SMTP-VERIFICATION.md).
Deployment operators still verify their own TLS edge, relay and recovery goals.

The database healthcheck probes internal loopback TCP. The official PostgreSQL
image starts a temporary socket-only server during initialization; a Unix-socket
probe can release the migration service before the final TCP server is ready.
This healthcheck does not publish the database outside the Compose network.
