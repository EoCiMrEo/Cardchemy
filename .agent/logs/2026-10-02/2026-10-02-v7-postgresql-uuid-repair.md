# Production UUID hydration repair and v7 regression checks

## Scope and diagnosis

Standing Lane 6 authority covers this integration repair. The current checkout
is dirty `main` at `6c02d6c`; the retained installation, root `.env`, populated
volume, original PDFs and backups are preserved. No provider request, retained
migration or Ask activation occurs in this repair.

The initial full PostgreSQL run failed nine current-worker tests although
queued profiles and claim identities matched. `asyncpg` hydrates PostgreSQL
UUIDs as a subclass of the standard-library UUID. The admission service used
exact-type checks, so the pure immutable admission contract rejected otherwise
valid persisted identities. SQLite and newly constructed Python UUIDs did not
expose this issue.

## Change

`backend/app/services/rag_question_context.py` now normalizes trusted ORM UUID
objects to exact standard-library UUIDs before constructing admission messages
or stored snapshots. It still rejects strings, nulls, zero UUIDs and unrelated
types. The pure v3 contract remains strict; canonical bytes and admission
digests are identical before and after normalization. Authorization, timestamp,
predecessor, expiry, hash and transaction guards are unchanged.

New regression tests exercise the actual asyncpg UUID subtype for both current
and preceding messages and verify unchanged admission digests. Existing
PostgreSQL tests exercise enqueue, commit, fresh-session rehydration and worker
completion. Four outdated test expectations were aligned with the new required
policy; the historical unshipped query candidate remains unshipped. Its worker
spy now admits a real invented prior user turn and checks the v7 literal subject
while retaining exactly one raw-current-question embedding and no history read.

## Actual verification

- Focused context/current-worker contracts: **85 passed**.
- Other experiment-isolation/context contracts: **177 passed, one skipped**
  before repairing the remaining runtime-fence fixture; the current focused
  rerun above includes that repaired fixture.
- Documented full disposable PostgreSQL harness: **187 passed, three skipped,
  4,308 deselected**. Current head/drift and downgrade/re-upgrade passed. The
  harness cleaned disposable services and generated credential files.
- Full offline and current instructor/student journey checks are running;
  their terminal results require a later evidence record.

This supersedes the failed-suite status of the earlier integration record for
PostgreSQL only. It does not establish independent source quality, private
provider consent, a retained cutover or spoken assistive-technology success.
Ask remains off; Lane 6 remains **3/7**.
