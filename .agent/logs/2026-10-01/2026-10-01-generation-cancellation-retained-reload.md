# Generation cancellation repair: retained development reload

Date: 2026-10-01 (America/Chicago).

## Scope

Continued the authorized Lane 6 repair after the
[passing offline/disposable checks](2026-10-01-lane6-cancellation-and-release-recheck.md).
This record supersedes that record's runtime-not-reloaded limit only for the
four-line generation cancellation/lease-loss repair. It does not activate an
Ask candidate, change its release gates or authorize another provider trial.
Lane 6 remains 3/7, Ask off; the specific metric amendment remains pending.

The actual worker Compose labels identify the documented development override,
which mounts `backend` at `/app`. Its source file already matched the tested
repair, but the long-lived worker imports source only at process start. A new
image build was unnecessary; a controlled process reload was required.

## Controlled reload and evidence

1. Read only aggregate generation queue counts in a PostgreSQL read-only
   transaction: zero queued and zero running jobs. No private IDs, questions,
   source content, credential values or exception details were printed.
2. Gracefully stopped API admission using the actual base plus development
   Compose files. Rechecked the aggregate queue through the worker: still zero.
3. Gracefully stopped the idle generation worker with the documented 45-second
   container grace, then started the existing API and worker with a bounded
   health wait. No container, volume or retained record was deleted, and their
   environment was not changed.
4. Compose also ran its existing migration dependency. The configured source
   head is unchanged at `20260928_0029`; no new migration was introduced.
   Subsequent retained `alembic current --check-heads` showed that head and
   `alembic check` reported no new upgrade operations. No downgrade, stamp or
   retained-data restoration occurred.
5. Both restarted processes became healthy. All eight application services
   were healthy at final inspection. The restarted worker's mounted generation
   module matched the tested source SHA-256
   `cd5b974c048c7bde865efc06e0ad3eb22fa89bfa0b4757d13fa31289d64366d7`.
   The queue remained zero queued / zero running.
6. Retained API non-secret switches remained `ask_enabled=false` and
   `source_judge_enabled=false`. No provider invocation was initiated.

Root `.env`, populated volumes, attached original PDFs and ignored backups
were preserved. The temporary aggregate-reader script was removed after use;
other ignored evidence and frozen one-use ledgers remain intact.

## Limits and next dependency

The preceding 35 focused, 3,147 offline, 131 PostgreSQL and 83 Chromium tests,
plus both deterministic journeys, prove repair/contracts, not real reference
usefulness. No live generation job was created to test cancellation. No
retained browser action, spoken assistive-technology test, hosted CI or
packaged-image cutover was performed in this reload.

The visual source-selection prototype is still an experiment with consumed
authorization. The dormant v4 runtime remains a different text-only contract.
Do not enable Ask by changing flags. The pending
[metric amendment](2026-10-01-source-navigation-release-metric-alignment-recommendation.md),
any subsequent precise provider envelope, independent quality measurements and
matching successor runtime/release proof remain required.
