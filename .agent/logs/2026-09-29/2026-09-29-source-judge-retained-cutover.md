# Lane 6 dormant v4 cutover on the retained local installation

Date: 2026-09-29 (America/Chicago). The broad pre-existing working tree was
preserved. The original `cardchemy_postgres_data` volume, root `.env`, three
encrypted original PDFs, existing jobs and prior backup were retained. The
operator had approved Lane 6 implementation and local cutover; the Ask quality
release gate was not approved as passed. No private Knowledge was transferred
to the source judge.

## Preflight and regression repairs

- Before the change, the running old image reported Alembic `20260927_0028`
  with no drift. Aggregate preview found zero queued/running/possibly remotely
  executed Ask jobs and zero active generation/index jobs.
- The first full disposable PostgreSQL run passed migration head/drift and
  downgrade/re-upgrade but had 30 application-test failures. Those tests
  still admitted historical v3 jobs through the new v4-only service fence.
  Test helpers now directly seed immutable historical v3 rows for read/guard
  coverage and use the v4 API profile for current admission/worker coverage.
  Production guards were not relaxed. A final full disposable run passed
  **131 tests**, skipped 3 and deselected 2,367; its container and generated
  credential file were removed.
- The post-edit backend offline run passed **2,323**, skipped 5 and deselected
  131. The backend/frontend built-image smoke tests passed without network,
  mounts or credentials. The frontend full check passed six unit, 65 component
  and 81 Chromium tests, with one opt-in live reset case skipped.
- The deterministic journey first passed RAG-off but its RAG-on setup still
  lacked a fake v4 source judge. The disposable settings and ID-only fake were
  aligned to v4; RAG-on then passed its full browser/database journey with
  zero provider traffic. Both disposable journeys cleaned up their resources.

## Backup and migration

The API, generation/index/answer/email workers and frontend were stopped.
The custom-format pre-0029 backup was saved in the ignored `backups/` directory
as `cardchemy-before-0029-20260929-v4.dump` (2,891,212 bytes, SHA-256
`1aef15ac0395976d690567b5d6b7c0a5974bea44a95388e290f6c542c700242d`).
The copied archive's container checksum matched. Restore into the separately
named empty `cardchemy_restore_0029_v4` database completed with
`--exit-on-error`; head `0028` and aggregate counts matched the live source:
3 PDF manifests, 3 blocks, 3 active published revisions, 17 Ask jobs and
4 generation jobs. The rehearsal database was removed after verification;
the backup remains available. No volume or root configuration was deleted.

Migration `20260927_0028` -> `20260928_0029` completed on the original
populated volume. The new backend image reported `0029 (head)` and Alembic
reported no model drift. Matching API, all four workers and frontend were
recreated healthy. Frontend `/healthz` and proxied API readiness both returned
HTTP 200. The retained aggregate counts stayed identical. Runtime settings
reported `ask_enabled=false`, `ask_available=false`, and the v4 release fence
closed. Post-restart Ask shutdown preview again found zero queued/running/
possibly remotely executed jobs.

On the retained enrolled browser, keyboard activation opened the exact Week 2
original PDF page 1 of 33 with canvas and readable text controls. Navigation
rendered page 2 of 33 while the adjacent extracted text remained labeled as
opened page 1. The previously reported original-PDF fallback did not occur in
this check. Pointer activation through the automation surface was inconclusive;
the earlier retained-browser repair log records independent pointer/browser
checks. No private lecture pixels or page text were saved in this log.

## Remaining gates

The read-only v4 exposed-case diagnostic put the designated gold page into
the four-page judge slate for 11/11 cases, but final page usefulness is
ungraded. The newly approved public calibration attempt returned HTTP 503
after one physical request and stopped without retry. It yielded no quality
score; the heldout remains sealed and failed-attempt cost is unknown. A new
paid call requires a fresh exact envelope. The independent original-PDF
holdout, at least 90% useful among all displayed pages, negative/no-match,
private transfer approval, spoken accessibility and final release gates remain
open. Ask remains disabled; Lane 6 remains **3/7**.
