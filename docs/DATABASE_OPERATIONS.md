# Database migrations, backup, restore, and rollback

The database schema is owned by Alembic. The API never creates or alters tables
at startup; it refuses to start when the database revision is not at the current
head. The initial revision, `20260914_0001`, is a clean baseline and is not an
adoption migration for older development databases. The current head,
`20260915_0005`, adds the transactional email outbox and optional recipient
binding for emailed invitations. Revision `20260915_0004` adds durable
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

## Fresh local database

Phase 2 intentionally resets local data. To recreate the named Compose volume
and apply the baseline:

```powershell
docker compose down --volumes
docker compose up -d db
docker compose run --rm migrate
docker compose up -d backend worker email-worker
```

Starting the complete stack with `docker compose up` also runs the one-shot
`migrate` service before the backend and generation worker start.

## Upgrade and verify

Create a backup before every upgrade. Then run:

```powershell
docker compose run --rm migrate
docker compose run --rm backend alembic current --check-heads
docker compose run --rm backend alembic check
```

`current --check-heads` proves the database reached every configured head.
`alembic check` detects model changes that do not yet have a migration.

## Backup

Create the destination directory yourself and keep it outside source control.
The custom archive format supports selective inspection and restore:

```powershell
New-Item -ItemType Directory -Force backups
docker compose exec -T db pg_dump -U admin -d flashcard_gen --format=custom --no-owner --file=/tmp/flashcard_gen.dump
docker compose cp db:/tmp/flashcard_gen.dump backups/flashcard_gen.dump
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
docker compose cp backups/flashcard_gen.dump db:/tmp/flashcard_gen.dump
docker compose exec -T db createdb -U admin flashcard_gen_restore_test
docker compose exec -T db pg_restore -U admin -d flashcard_gen_restore_test --no-owner --no-privileges /tmp/flashcard_gen.dump
docker compose exec -T db psql -U admin -d flashcard_gen_restore_test -c "SELECT version_num FROM alembic_version;"
```

Verify expected table counts and a representative instructor/student journey
against the restored database before declaring the backup usable. After that
verification, explicitly remove only the rehearsal database:

```powershell
docker compose exec -T db dropdb -U admin flashcard_gen_restore_test
```

For an actual restore, stop application writers, create a fresh empty target
database, restore the archive, run `alembic upgrade head`, verify the revision
and counts, and only then point the application at the restored database.

The Phase 8 reference rehearsal copied a checksummed custom archive out of the
database container, restored it into a fresh database, matched the source and
restore at Alembic `20260915_0005` with representative user/session counts, and
then completed a `20260915_0005 -> 20260915_0004 -> 20260915_0005` migration
cycle on the restored copy. Repeat this rehearsal with release-specific data;
the historical result is not a substitute for testing a new backup.

## Downgrade and rollback

Inspect the history and downgrade exactly one revision only after confirming the
target revision's downgrade is safe for the data in use:

```powershell
docker compose run --rm backend alembic history
docker compose run --rm backend alembic downgrade -1
docker compose run --rm backend alembic current
```

Downgrading `20260915_0005` removes every email outbox row and emailed-invitation
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
