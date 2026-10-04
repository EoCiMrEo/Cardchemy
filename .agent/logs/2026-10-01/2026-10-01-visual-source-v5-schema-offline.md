# Dormant visual source judgment v5: configuration and schema

## Scope and preservation

The operator authorized aligned offline v5 implementation. This bounded change
owns configuration, RAG models, the new `20261001_0030` migration and focused
configuration/schema tests. Parent work owns the worker, admission service,
deployment, frontend and maintained documentation. Starting branch was `main`
at `6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`; existing shared changes were
preserved. Used migration `0029` and historical v4 snapshots were not rewritten.

## Changes

- Distinct `related_knowledge_navigation_v5`, paired with
  `hybrid_source_navigation_v9`; historical v4 remains readable.
- Dormant defaults: Gemini 3.5 Flash-Lite, `visual_source_id_v1`, HIGH thinking,
  input/output ceilings 32768/2048, request timeout at most 60 seconds, zero
  retries, minimum input/output prices USD 0.30/2.50 per million tokens.
- New nullable immutable job fields `source_judge_thinking_level` and
  `source_judge_timeout_seconds`. V5 requires `high` and 1–60 seconds; historical
  rows require both fields absent. Activated worker startup additionally
  requires a valid original-PDF archive encryption key.
- `0030` extends source-only identity/result, snapshot, retrieval pairing,
  stage-parent and reference guards. V5 stages retain the one-physical-call
  limit, zero retries and uniqueness across worker claims for each logical
  manual attempt. V4 keeps its previous constraints.
- V5 clarification remains source-free. Before remote work it is permitted;
  after remote work it requires one successful, finished, certain judgment
  belonging to the current job policy, worker attempt and manual attempt.
  The historical v4 prohibition on post-provider clarification remains.
- Downgrade refuses retained v5 jobs before any schema or trigger mutation.

`ASK_RUNTIME_POLICY_VERSION` remains the historical closed fence. Changing the
required prospective policy to v5 does not activate Ask, including when raw
enablement flags are true.

## Verification and limits

From `backend`:

```text
venv/Scripts/python.exe -m pytest tests/test_config.py tests/test_source_judgment_policy_migration.py tests/test_visual_source_judgment_policy_migration.py tests/postgres/test_postgres_visual_source_judgment_policy.py -q
53 passed, 15 skipped in 2.17s
```

The passing checks cover invalid/null/nonfinite snapshots, portable database
checks, remote-call uniqueness, exact reversible trigger patches, current versus
stale/failed/uncertain clarification predicates, downgrade preservation and the
closed activation fence. A first new startup-key test inherited the test
harness's injected synthetic key; it was corrected to explicitly pass an absent
key and then passed. No application configuration or production key was read.
The expanded configuration/schema regression set, additionally including v3,
v2 navigation and canonical-page migration contracts, passed **65/65** in 1.34s.

The 15 PostgreSQL trigger regressions are saved for the next guarded disposable
service harness; they were skipped without its opt-in. SQLite predicate checks
and mock migration edits do not prove deployed PostgreSQL trigger execution.
No retained database migration, provider call, private PDF, heldout, root `.env`
read/change, runtime rebuild or activation was performed. No temporary service
or scratch artifact was created by this scoped work.
