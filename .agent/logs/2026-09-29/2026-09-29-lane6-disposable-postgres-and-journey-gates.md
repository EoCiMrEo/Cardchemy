# Lane 6 disposable PostgreSQL and browser journey gates

Date: 2026-09-29

## Scope and starting boundary

Rechecked the current Lane 6 source-only implementation against the documented disposable PostgreSQL and deterministic cross-stack journey harnesses. The checkout was `main` at `6c02d6c` with extensive pre-existing uncommitted Lane 6 work. Read the root `AGENTS.md`, project orientation/maps, `docs/TESTING.md`, `scripts/test_services.py`, and `scripts/test_journey.py` before execution. The retained installation and root `.env` were outside test scope. The public source-ID quality pilot and independent private usefulness gate are separate and remain open.

## Commands and results

1. `backend\venv\Scripts\python.exe scripts/test_services.py postgres`, using the approved Docker-capable execution context: **exit 0**. On a randomly named loopback PostgreSQL test container and `regression_test` database, Alembic upgraded to current head `20260928_0029`, passed `current --check-heads` and drift check, downgraded the empty schema to base, re-upgraded to head, and repeated head/drift checks. PostgreSQL suite: **131 passed, 3 skipped, 2464 deselected in 107.87 seconds**. This includes the disposable source-only, original-PDF, schema, migration, transaction and authorization contracts selected by the maintained `postgres` marker. The harness reported deletion of its container and generated credential file.
2. `backend\venv\Scripts\python.exe scripts/test_journey.py`, using the same Docker-capable context: **exit 0**. The deterministic local provider and two isolated disposable application/database scenarios passed. RAG-off proved ordinary PDF flashcards with no Knowledge/index/Ask/provider records. RAG-on proved generation, independent Knowledge capture/index/review/publication, source-only Ask/page references, enrollment, email, cards and progress. Both browser contracts passed, and the harness reported cleanup of processes, containers, temporary data, fixture and generated credentials.
3. Independent Docker inventories after both commands found **no** containers with `flashcard-regression-*` or `cardchemy-journey-*` names. The eight pre-existing `cardchemy-*` services remained running and healthy.

The first PostgreSQL invocation in the default restricted shell exited before a result because Docker access was denied. It was not a test failure and did not create a disposable database; the normal approved Docker-capable run above completed. No command used real root `.env`, retained PostgreSQL, populated volumes, live Gemini, or paid provider credentials.

## Evidence boundary

This proves disposable schema and deterministic local browser contracts against this checkout. It does **not** establish quality of real source-ID ranking, usefulness of displayed references on an independent lecture holdout, live provider success, retained-data migration rehearsal in this run, hosted CI, or manual spoken assistive-technology acceptance. Ask remains disabled and no Lane 6 quality or release checkbox is advanced by this log alone.
