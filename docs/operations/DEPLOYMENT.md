# Deployment and self-hosting

## Current local Lane 6 closure â€” 2026-10-04

The local source-only v8/visual-v5/admission-v2 installation on head `0033`
is enabled after its measured quality, PDF/display and release gates. Fresh
installations remain default-off. See the
[closure and activation evidence](../../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md). Earlier installation
checkpoints below remain historical snapshots; the linked closure supersedes
their off/pending status, while default-off and upgrade safeguards still apply.

The base Compose stack is a production-shaped local installation: it builds the
frontend and backend, migrates PostgreSQL before starting the API, runs separate
generation, Knowledge-index, Subject-answer and email workers, captures local mail in Mailpit, and exposes only
the frontend and Mailpit UI on IPv4 loopback. It has no source mounts, reload
mode, debug mode, public API port, or public database port.

## Clean-clone quick start

Prerequisites are listed in [Supported runtimes](../development/RUNTIMES.md). Use
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
to the generation worker. The API never receives the embedding credential;
`index-worker` receives only `RAG_EMBEDDING_API_KEY`; `answer-worker` receives
only the query `RAG_EMBEDDING_API_KEY`, while the generation worker receives
the non-secret RAG capture profile. The source-only Ask worker uses the normal
backend image and does not mount a local answer-verifier bundle. Keep both RAG flags false
until retention/provider terms and current prices have been reviewed. Stop the
stack with `docker compose down`; do not add
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
index and answer workers continue pulsing; draining workers stop reporting readiness. See
[diagnostics and health](OBSERVABILITY.md) and [privacy controls](../security/PRIVACY.md).

SIGTERM stops workers from claiming new work and gives active work 30 seconds
by default to finish. Compose allows 45 seconds before force-killing them. Tune
`WORKER_SHUTDOWN_GRACE_SECONDS` together with `stop_grace_period`; the Compose
grace must remain longer. An interrupted generation claim is recovered after
its lease expires. An index claim is automatically requeued only if it dies
before its first provider call; post-provider ambiguity fails terminally and
needs explicit operator action. An email interrupted after SMTP delivery begins is marked
ambiguous on recovery and is not automatically duplicated. See
[Transactional email delivery](../mail-server/EMAIL_DELIVERY.md).

For planned maintenance, stop public admission first, inspect or drain pending
generation/index/email work, and then stop workers:

```text
docker compose exec backend python -m app.cli email-outbox-status
docker compose stop -t 45 backend
docker compose stop -t 45 worker index-worker answer-worker email-worker
```

## Volumes, backup, upgrades, and disaster recovery

`postgres_data` contains all durable application records, outbox state, job
state, private Subject Knowledge pages/chunks/vectors, encrypted original-PDF
archives, any pending encrypted validated-card choices, and short-lived
encrypted generation source PDFs. `mailpit_data` is local/test
capture only and must not be used or restored in production. The frontend, API,
and workers are replaceable images and have no durable filesystem state.

Before an upgrade:

The PostgreSQL 16/pgvector 0.8.6 Alpine transition needs a separate fresh ICU
target for any earlier Debian/libc cluster. The database entrypoint refuses a
populated unmarked or incompatible legacy volume before starting PostgreSQL.
Back up and restore logically into the new target, verify it, and keep the old
volume until the cutover decision. See the exact
[database operations](../database/DATABASE_OPERATIONS.md#moving-the-prior-debian-installation-to-the-reviewed-alpine-build)
procedure. The operator's explicit approval to discard a particular local
legacy volume does not change this default for other installations.

Keep existing database/Compose project names and secrets while adopting new
images. The [configuration upgrade note](CONFIGURATION.md#existing-installations-and-cardchemy-defaults)
explains legacy authentication defaults and session continuity.

1. Record the current application version and Alembic revision.
2. Stop the API and gracefully drain/stop all four workers so the dump is consistent.
3. Create, checksum, encrypt, and copy a PostgreSQL custom-format backup off host.
4. Preserve `.env` or equivalent deployment secrets separately in a secret
   manager. Both the temporary-source key and the independent
   `KNOWLEDGE_PDF_ENCRYPTION_KEY` are required to recover their respective PDF
   ciphertext; restoring only the database cannot decrypt the original archive.
5. Build/pull the intended immutable release, run `migrate`, verify every
   Alembic head, then start workers, API, and frontend.
6. Check readiness, login, an instructor/student read path, and queues before
   restoring public traffic.

For historical Lane 6 upgrades to Alembic `20260925_0019`, include pending card choices
in the pre-upgrade job inventory and keep the original source-storage key
available. Drain generation and Ask claims before migrating. Recreate the API,
generation/answer workers and frontend together so they share the new response
types and statuses. Verify an authorized pending choice after reload, exact
card-count confirmation without a provider request, expiry/cancel cleanup and
Knowledge publication survival. Separately confirm safe Ask outcome copy,
stage diagnostics and the one-embedding/one-answer cap. Revert new Ask
admission with `RAG_ASK_ENABLED=false` if the measured quality gate fails;
leave stored Knowledge and private history intact. A schema rollback with
retained Lane 6 rows is refused; restore a validated pre-upgrade backup into a
separate target after an explicit product rollback decision.

Detailed commands and destructive-operation warnings are in
[Database operations](../database/DATABASE_OPERATIONS.md). Prefer restoring the pre-upgrade
archive into a fresh database over downgrading a data-destructive migration.

For the `20260925_0021` related-Knowledge upgrade, drain answer claims,
restore-verify a pre-upgrade backup and migrate before recreating the API,
answer worker and frontend together. Verify failed and abstained job responses
show at most two exact, page-labeled current excerpts; supported answers show
none. Revoke publication or enrollment in a controlled check and confirm the
entire related bundle disappears on the next authorized read. The excerpt aid
does not make a failed Ask answer valid or authorize a new answer policy. An
operational rollback must account for retained excerpt rows; the schema refuses
to downgrade while they exist.

For the source-only `20260926_0022` upgrade, keep Ask admission off, drain
old answer-policy claims, verify a backup and apply the new migration with
writers stopped. Recreate matching backend/Ask-worker/frontend images only
after code and schema preflight. Verify the job result discriminant, at most
three exact current excerpts, open-page authorization and whole-bundle hiding
on publication/access/revision loss. The author approved a clean development
volume reset, but that operator choice is separate from migration/rollback
instructions for installations with data. Do not treat the current source
checkout as a completed release.

For the original-PDF/navigation `20260927_0026`, `20260927_0027` and
`20260927_0028` upgrade,
keep Ask admission off and all writers stopped while verifying the backup and
applying all three revisions. Preserve and restore-test the independent PDF archive
key. Revision `0026` introduces immutable encrypted blocks and per-document,
Subject, user and deployment quotas; revision `0027` admits the historical
v2/v8 navigation pair, and `0028` admits the corrected historical v3/v9 pair
while retaining valid old snapshots. Recreate matching API,
workers and frontend images, verify current Alembic heads/drift and that
older Ask jobs retain their recorded policy. An instructor may attach an
original PDF to an active legacy Knowledge revision only after the server
matches its exact source SHA-256 and page count; this attachment creates no
revision and triggers no provider call. Test authorized PDF metadata and
bounded byte ranges, then verify revoking enrollment or publication hides
the entire reference bundle and PDF. A missing original remains an explicit
extracted-text fallback. Downgrading `0028` with a retained v3 job, `0027`
with a retained v2 job, or `0026` with an archived PDF is refused; restore a
validated backup into a separate
target for a product rollback. Neither migration nor a successful image build
opens Ask admission by itself.

The current source head is `20261002_0033`. New Ask jobs use `related_knowledge_navigation_v8` / `visual_source_id_v5`, bound to `literal_subject_admission_v2`. Historical jobs retain their policy and cannot execute or retry as v8. Fresh installations remain default-off; installation activation requires explicit Ask/judge flags, matching active embedding space, current prices and local release evidence. The retained local installation passed those gates; see [closure](../../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md).

The answer worker authenticates complete current original-PDF archives before isolated bounded page rendering. Only that worker receives the source-judge key. Archive encryption keys remain isolated to API, generation and answer roles. Keep Ask paused during a populated upgrade, drain writers, restore-verify a backup, apply all Alembic heads, check drift, recreate matching services and verify authorized original pages before restoring traffic. Use [database operations](../database/DATABASE_OPERATIONS.md) and [Ask maintenance](../ai/ASK_AI_SHUTDOWN.md) for the exact procedure.

## Controlled RAG rollout and reversal

Ask AI is separately default-off from Knowledge. The current target is the
fenced visual v8 policy on source head `20261002_0033`; use the current
backup/migration procedure above and retain all independent release gates.
The historical v4/0029 details above remain for old-job interpretation.
Follow the
[Ask maintenance procedure](../ai/ASK_AI_SHUTDOWN.md) to terminally resolve old
answer-policy jobs and prepare any separately approved installation upgrade to
the current head `20261002_0033`. Verify current nonzero query-embedding and source-judge
prices, worker-only credentials/quota labels and an exact Subject active-space
match. The multi-PDF public pilot, later separately approved and disclosed
real published-Knowledge transfer, independent original-PDF displayed-card,
page-open, access and accessibility gates must pass before an approved release
enables Ask under a separately validated, immutable source-only policy. The
first approved public calibration produced no score after one attempted
provider request; a later 48-case Flash-Lite calibration returned 47 accepted
responses but failed the zero-false-no-useful-display gate. Neither approval
can be reused, and failed-attempt cost remains uncertain. Any new paid pilot needs a
fresh exact endpoint/model/price/call/token/time/cost envelope. The prospective
Ask worker makes at most one current-question query-embedding and one
source-ID judgment request, zero answer/verifier calls and zero automatic
retries. Any failed release gate keeps
Ask off. Knowledge capture/indexing continues under its independent RAG and
embedding flags.

Release defaults keep `RAG_ENABLED=false`. First validate configuration and
backup recovery, drain all four worker lanes, apply every Alembic head and
restore normal flashcard admission with RAG still off. In a controlled
environment, enable capture and the RAG embedding profile only after the
privacy notice, provider terms, current prices and divided quota buckets are
approved. Use several authorized Subjects to verify private capture, explicit
Knowledge publication, enrolled-user retrieval, own-thread access, capacity and
quota fairness. Paid external evaluation remains a separately authorized gate.

To reverse the feature without deleting durable data, stop new admission, set
`RAG_ENABLED=false`, gracefully drain or explicitly cancel index/answer work,
restart API/workers and verify the RAG lanes report disabled while normal
flashcard generation remains healthy. This preserves pages, chunks, vectors,
original-PDF archives and private history for a later reviewed restart. Schema
downgrade or data/volume
deletion is a separate destructive decision requiring a verified recovery path.

Each operator must choose an RPO/RTO appropriate to their users. At minimum,
schedule encrypted off-host database backups, retain more than one generation,
monitor backup failures and free space, and rehearse a restore after schema
changes and at least quarterly. A recovery bundle needs the database archive,
application release identifier, Compose/environment configuration, signing,
temporary-source and original-PDF encryption keys, SMTP/provider configuration,
DNS/TLS ownership, archive
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
source-only Ask worker uses the same non-root backend image and has no ONNX
answer-verifier dependency or model mount. The
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
docker image inspect cardchemy-backend:0.2.0 --format "{{.Os}}/{{.Architecture}} {{.Size}} {{.Config.User}}"
docker image inspect cardchemy-frontend:0.2.0 --format "{{.Os}}/{{.Architecture}} {{.Size}} {{.Config.User}}"
docker history cardchemy-backend:0.2.0
docker run --rm cardchemy-backend:0.2.0 sh -c "! command -v gcc && ! command -v node"
```

The source-only Compose layout uses backend, optional OCR backend and frontend
application images; the Ask service reuses backend. Reconcile release-image
checks and signatures against the exact source-only build before claiming its
release gate. Confirm no forbidden build/test material and record every size.

The [clean-machine production rehearsal](PRODUCTION_REHEARSAL.md) verifies
this production profile with a trusted local HTTPS edge and a current-head
backup restored into a separate empty volume. Pair it with
[actual local encrypted SMTP verification](../mail-server/SMTP-VERIFICATION.md).
Deployment operators still verify their own TLS edge, relay and recovery goals.

The database healthcheck probes internal loopback TCP. The official PostgreSQL
image starts a temporary socket-only server during initialization; a Unix-socket
probe can release the migration service before the final TCP server is ready.
This healthcheck does not publish the database outside the Compose network.
