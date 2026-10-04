# Lane 6 source-ID judgment persistence slice

Date: 2026-09-29 (America/Chicago). Branch `main` at `6c02d6c`. The existing working tree, populated database at migration `20260927_0028`, root `.env`, three retained original PDFs and Ask-disabled runtime were preserved. This implements only the approved, gated [ADR-024](../../../docs/decisions/ADR-024-gemini-source-id-judge.md) storage contract; it does not activate Ask or call a provider.

## Change and boundaries

- Added forward migration `backend/alembic/versions/20260928_0029_source_judgment_policy.py` and matching model constraints in `backend/app/models/rag.py`. Eight nullable fields capture the source judge provider, endpoint identity, model, contract, prices and token limits on a v4 job. Old v1–v3 jobs must keep those fields null. A v4 job requires the existing `hybrid_source_navigation_v9` retrieval snapshot, while its own source-selection policy is `related_knowledge_navigation_v4`.
- A v4 job remains source-only: no answer-model fields or generated answer message. Its result can be `related_knowledge`, `no_match`, or source-free `clarification_needed`. The latter is rejected if any query embedding or source-judgment stage exists for the job. Existing result contracts remain unchanged.
- The new `source_judgment` stage is v4-only, must match its parent job and attempt, permits at most one physical call and no retry, and is unique per manual attempt. Reference insertion is limited to exact canonical-page offsets after a completed, successful judgment stage. Existing v3 references and retrieval behavior remain valid. Immutable job snapshots are enforced by the installed database guard.
- The migration copies used `0028` expressions, checks the installed guard bodies before replacing them, and refuses downgrade while v4 job snapshots exist. No migration was run against the populated installation.

## Verification

- Focused offline migration/model checks: **4 passed**. The only Alembic head is `20260928_0029` in source.
- Required backend offline suite: **2,286 passed, 150 skipped, 2 deselected**. Skips include service-only cases without their disposable service process values; no live AI execution was enabled.
- Focused disposable PostgreSQL checks: **3 passed**. They cover old-job preservation, v4 stage/physical-call guards, canonical references, immutable judge snapshot, and source-free clarification.
- Full disposable PostgreSQL service suite: **130 passed, 3 skipped, 2305 deselected**. Fresh-schema upgrade, `current --check-heads`, drift check, downgrade to base and re-upgrade to head passed. The harness removed its loopback-only test container and generated credential file.
- An initial full-suite run had three failures in an older parameterized navigation test. The new synthetic v4 tests had left queued jobs in the shared disposable database, exhausting its admission cap. A per-test cascade teardown for their synthetic instructor/student rows fixed the interference; the repeated full suite passed. The test fixture does not touch the retained database.

## Remaining gate

This slice is a schema and contract prerequisite only. The runtime still admits v3 jobs under its closed Ask gate. The multi-PDF public pilot, independent source usefulness review, private heldout, access/release checks, and any separately authorized paid call remain outstanding. Do not migrate the populated database or enable v4 until the coordinated cutover gates are met.
