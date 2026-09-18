# Phase 2 remediation: migrations and data integrity

Date: 2026-09-14

## Scope and approved reset decisions

Phase 2 was completed as a development-only schema reset. No legacy data or
compatibility path was retained. The final local PostgreSQL volume was recreated
from scratch and left at Alembic revision `20260914_0001` with zero application
rows.

The implementation follows the approved product rules:

- every flashcard is multiple-choice with exactly four trimmed, non-empty,
  case-insensitively unique options;
- `back_content` matches exactly one option and is canonicalized to that stored
  option by API validation;
- the server determines correctness from the selected option or option index
  and assigns quality 5 for correct or 1 for incorrect;
- status thresholds are `new` before an attempt, `learning` below 7 days,
  `review` from 7 through 20 days, and `mastered` from 21 days;
- completion is studied cards divided by total cards, while mastery is review
  plus mastered cards divided by total cards;
- owned/dependent records cascade on account or subject deletion, while an
  invitation consumer uses `ON DELETE SET NULL` and retains `used_at`.

## Migration and startup architecture

- Added Alembic configuration, async migration environment, revision template,
  and clean PostgreSQL baseline migration.
- Added Alembic 1.20.0 to the direct requirements and regenerated both hashed
  production and development lock files.
- Removed the one-off `add_options.py` and `add_time_limit.py` scripts.
- Removed production `Base.metadata.create_all()` startup behavior. SQLite unit
  tests retain it only for their disposable in-memory fixture.
- Added startup revision verification. The API refuses to start unless the
  database is at every configured Alembic head.
- Added a one-shot Compose migration service and made the API wait for its
  successful completion.

The baseline creates all application tables, PostgreSQL UUID/TIMESTAMPTZ/JSONB
types, explicit foreign-key delete actions, uniqueness constraints, bounds,
foreign-key indexes, due-card indexes, and publication integrity triggers.

## API, service, and database integrity

- Added trimmed request schemas and the approved length/range bounds for names,
  titles, descriptions, card text, time limits, card count, invitation lifetime,
  confidence, and pagination/batch sizes.
- Added database checks for persisted bounds and multiple-choice invariants.
- Nullable descriptions and time limits can be cleared explicitly without
  conflating omitted fields with `null`.
- Moved commit ownership to route-level units of work for subject, set, card,
  generation, publication, and progress workflows. Generation validates the
  full AI batch before persistence and creates the set plus cards atomically.
- Added PostgreSQL UPSERT plus deterministic row locking for progress creation
  and updates, preventing duplicate rows and lost concurrent answers.
- Study sync authorizes and locks the full batch before applying it and commits
  once, so any invalid item rolls back the batch.
- Due cards are filtered, deterministically ordered, indexed, and limited by the
  database rather than loaded and sliced in Python.
- Publishing is protected in both service logic and PostgreSQL triggers. A set
  cannot be published without an approved card, and the final approved card
  cannot be removed while the set remains published.
- Standardized application datetimes on timezone-aware UTC and persisted them
  as PostgreSQL `TIMESTAMPTZ`.

The PostgreSQL index and transaction choices were cross-checked against the
Supabase PostgreSQL best-practices guidance: foreign-key indexes, composite and
partial indexes for the due-card path, database uniqueness, short transactions,
UPSERT conflict handling, and deterministic locks.

## Frontend contract alignment

- Added typed study-card, answer, progress, and flashcard contracts.
- Student study payloads no longer receive the answer before submission.
- Study mode sends the selected option and waits for server-derived correctness,
  quality, canonical answer, and index before revealing feedback.
- Student subject details consume backend completion and show mastery separately.
- Set editing now maintains exactly four options and an explicit correct-option
  selection; time-limit inputs use the approved 5-3600 second range.
- Removed six unused imports/state reads that blocked TypeScript's no-unused
  build gate. The production frontend build now succeeds.

## Tests and operational proof

Final evidence:

- `pytest -q` with the disposable PostgreSQL URL: 47 passed, 1 explicitly
  deselected live-AI test.
- PostgreSQL integration subset: 8 passed. It verifies TIMESTAMPTZ and indexes,
  bounds, flashcard checks, publication triggers, account and direct-subject
  cascades, invitation `used_by` nulling, auth-record cascades, enrollment races,
  lossless concurrent progress updates, and all-or-nothing failed batches.
- Alembic `downgrade base` followed by `upgrade head`: passed.
- `alembic current --check-heads`: `20260914_0001 (head)`.
- `alembic check`: no new upgrade operations detected.
- Compose one-shot migration image/build and migration command: passed.
- Compose API startup against the migrated database: `/health` returned healthy.
- Backup/restore rehearsal: custom dump restored into an isolated database at
  revision `20260914_0001` with all 11 application tables; rehearsal database
  and temporary dump were then removed.
- `corepack pnpm --dir frontend build`: passed. Browserslist emitted only its
  informational stale-data notice.
- Python `compileall`: passed.
- `git diff --check`: passed; Git emitted only platform line-ending notices.

## Final local state

The disposable Compose volume was reset once more after testing. The migration
dependency bootstrapped an empty database to `20260914_0001`, the aggregate row
count across user/subject/set/card/enrollment/progress/invitation tables was
verified as zero, and the backend was left running healthy.
