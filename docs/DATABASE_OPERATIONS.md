# Database migrations, backup, restore, and rollback

The database schema is owned by Alembic. The API never creates or alters tables
at startup; it refuses to start when the database revision is not at the current
head. The initial revision, `20260914_0001`, is a clean baseline and is not an
adoption migration for older development databases. Current head
`20260918_0010` creates private Subject Knowledge storage, revision/capacity
integrity and durable index-job schema. Revision `20260918_0009` requires
PostgreSQL 16 and pgvector 0.8.6 in `public`, even with RAG disabled.
The [runtime inventory](../runtime-artifacts.json) pins the supported container
image/platform; [native prerequisites](RUNTIMES.md#database-runtime-and-native-installation)
apply before migration or restore. Revision `20260917_0008` adds content-free operational tables, generation request
correlation, retention indexes and the transactional role-change audit trigger.
The preceding `20260916_0007` stores the per-stage request map as PostgreSQL JSONB so schema
drift checks remain comparable. Revision `20260916_0006` adds durable AI
provider request, retry, quota-wait, cache, and per-stage telemetry. Revision
`20260915_0005` adds the transactional email
outbox and optional recipient binding for emailed invitations. Revision
`20260915_0004` adds durable
study-answer idempotency receipts. Revision `20260914_0003` adds AI
provider/model snapshots, bounded usage/cost telemetry, and verified flashcard
page/section provenance; `20260914_0002` adds durable generation jobs,
encrypted temporary sources, quotas, and the exactly-once job/result link.

Before using Compose, define strong `POSTGRES_PASSWORD`, `SECRET_KEY`, and
`GENERATION_SOURCE_ENCRYPTION_KEY` values in the root `.env`. Generate the two
application keys independently. Compose intentionally refuses to start when a
required value is missing; do not place real values in source-controlled
examples.

For a clean clone, `python scripts/bootstrap_env.py` creates those three values
independently, without displaying them, and refuses to overwrite an existing
`.env`.

## Fresh installation

On a new installation, create the root `.env` with the non-overwriting bootstrap
script, then start the stack. The migration service applies the complete Alembic
chain before the API and workers start:

```powershell
python scripts/bootstrap_env.py
docker compose up -d --build --wait
```

Never remove a populated Compose volume as part of an upgrade; follow the backup
and migration steps below instead.

## Upgrade and verify

Create a backup before every upgrade. Preserve the existing database name,
Compose project and data-volume path. Drain all writers before changing the
PostgreSQL 16 image. A patch-level image replacement does not authorize a major
version upgrade or volume recreation. Validate a restore into a separately
named empty target first; the tested source/target must have the reviewed
pgvector binaries installed. Then run:

```powershell
docker compose run --rm migrate
docker compose run --rm backend alembic current --check-heads
docker compose run --rm backend alembic check
```

`current --check-heads` proves the database reached every configured head.
`alembic check` detects model changes that do not yet have a migration.

The vector foundation migration checks the installed/available extension version
and schema. A compatible preinstalled extension does not require the application
role to create it. Otherwise a database administrator must preinstall
`CREATE EXTENSION vector WITH SCHEMA public VERSION '0.8.6'` or authorize an
appropriately privileged migration role. The application does not automatically
upgrade an incompatible existing extension. Fixed migration errors omit SQL
exception details; do not stamp past them. Verify `extversion` and its namespace
from `pg_extension` after migration and restore.

Downgrading revision `20260918_0009` deliberately leaves the extension installed:
it can have other consumers, and Alembic cannot infer ownership from its presence.
Application-schema downgrades must remove dependent application objects first.
Never use `DROP EXTENSION ... CASCADE` or downgrade a populated operator database
as a test. The disposable [vector recovery harness](../scripts/test_pgvector_restore.py)
checks infrastructure dump/restore with synthetic vectors and indexes; actual
Knowledge-table recovery is verified separately by the guarded
[PostgreSQL Knowledge restore test](../backend/tests/postgres/test_postgres_knowledge_recovery.py)
with a populated 1,536-dimensional vector and two disposable child databases.
Downgrading `20260918_0010` removes all Subject Knowledge documents, pages,
chunks, vectors, indexing jobs and counters, and detaches its job/set links.
Use it only in disposable verification or after an explicitly authorized,
verified backup and product rollback decision; a real recovery normally
restores the pre-upgrade archive into a separate target.

## Moving the prior Debian installation to the reviewed Alpine build

This runtime change requires a logical restore into a **separate empty volume**.
Do not start the Alpine database container on the old Debian/libc data volume:
its data-directory path and PostgreSQL major version alone do not establish
locale or text-index compatibility. Fresh reviewed clusters use UTF-8 and ICU
`en-US`; restore recreates text indexes under the target's collation.

Drain all application writers/workers using the existing source runtime, take
and checksum its custom-format backup, and preserve the original volume and
source encryption key. Build/verify the reviewed database recipe, initialize
a separately named empty target, restore the archive, then apply the new
Alembic heads. Verify extension schema/version, heads/drift, expected rows,
valid indexes, representative Unicode uniqueness/order and application behavior
before pointing traffic at that target. Keep the old volume available for an
explicit rollback decision; never fix a failed restore by stamping a head or
deleting that volume. A real cutover remains an operator deployment action.

Native installations retaining compatible libc/ICU binaries and locale may
follow their supported platform's normal extension installation procedure;
a platform/locale change needs the same separate logical-target rehearsal.
After a collation library upgrade, identify and rebuild affected indexes before
refreshing recorded collation versions. See the PostgreSQL 16
[locale contract](https://www.postgresql.org/docs/16/locale.html) and
[collation-version guidance](https://www.postgresql.org/docs/16/sql-altercollation.html).
The disposable [prior-installation harness](../scripts/test_database_volume_upgrade.py)
exercises this source/target contract with generated data; it is not an
operational migration command.

## Backup

Create the destination directory yourself and keep it outside source control.
The custom archive format supports selective inspection and restore:

```powershell
New-Item -ItemType Directory -Force backups
docker compose exec -T db pg_dump -U admin -d cardchemy --format=custom --no-owner --file=/tmp/cardchemy.dump
docker compose cp db:/tmp/cardchemy.dump backups/cardchemy.dump
```

Record the application version, Alembic revision, UTC timestamp, and archive
checksum next to the backup. Store production archives encrypted with access
restricted to database operators. Preserve the source encryption key separately
in protected disaster-recovery material if queued/retryable jobs must survive a
restore. Never commit either artifact.

## Restore rehearsal

Test every important backup in a separately named database; do not overwrite the
active database during a rehearsal:

```powershell
docker compose cp backups/cardchemy.dump db:/tmp/cardchemy.dump
docker compose exec -T db createdb -U admin cardchemy_restore_test
docker compose exec -T db pg_restore -U admin -d cardchemy_restore_test --no-owner --no-privileges /tmp/cardchemy.dump
docker compose exec -T db psql -U admin -d cardchemy_restore_test -c "SELECT version_num FROM alembic_version;"
```

Verify expected table counts and a representative instructor/student journey
against the restored database before declaring the backup usable. After that
verification, explicitly remove only the rehearsal database:

```powershell
docker compose exec -T db dropdb -U admin cardchemy_restore_test
```

For an actual restore, stop application writers, create a fresh empty target
database, restore the archive, run `alembic upgrade head`, verify the revision
and counts, and only then point the application at the restored database.

Repeat this rehearsal with release-specific data and record the result in the
release evidence. Prior development rehearsals are recorded in `.agent/logs/`.

## Downgrade and rollback

Inspect the history and downgrade exactly one revision only after confirming the
target revision's downgrade is safe for the data in use:

```powershell
docker compose run --rm backend alembic history
docker compose run --rm backend alembic downgrade -1
docker compose run --rm backend alembic current
```

Downgrading `20260917_0008` drops request/heartbeat/audit history, origin request
correlation and the role audit trigger. Stop writers/workers and preserve
required audit evidence before an explicitly authorized operational rollback;
ordinary rehearsal uses only disposable databases. [Privacy controls](PRIVACY.md)
define account/export/metadata cleanup separately from schema rollback.
Downgrading `20260916_0007` changes the per-stage request map back to JSON.
Downgrading `20260916_0006` removes AI request-efficiency telemetry but leaves
generation jobs and their earlier token/cost telemetry intact. Downgrading
`20260915_0005` removes every email outbox row and emailed-invitation
recipient binding. Stop the email worker and drain, inspect, or intentionally
discard all pending and failed email before that downgrade. Downgrading
`20260915_0004` removes study-answer idempotency receipts. Downgrading
`20260914_0003` removes AI telemetry/provenance fields and restores
the legacy confidence/source column names. Downgrading `20260914_0002` removes generation jobs, temporary sources, quota
history, and job/result links. Stop the API and worker and drain or cancel jobs
before doing so. Downgrading the `20260914_0001` baseline to `base` drops the
entire schema and all application data, so it is only appropriate for an empty
test database or after a verified backup. Production recovery should normally
restore the pre-upgrade archive into a fresh database instead.

## Failed migration recovery

PostgreSQL runs these migrations in a transaction. If an upgrade fails, preserve the
error output, confirm `alembic current`, correct the migration or environment,
and retry. Do not use `alembic stamp` to bypass a failed migration. If a change
was non-transactional in a future revision, follow that revision's explicit
recovery notes or restore the pre-upgrade backup.

The [production recovery rehearsal](PRODUCTION_REHEARSAL.md) automates the
current-head custom backup/checksum, separate empty-volume restore, upgrade,
head/drift and representative instructor/student receipt/progress checks on a
fresh runner. It uses generated fixtures and removes only resources whose
rehearsal ownership is verified.
