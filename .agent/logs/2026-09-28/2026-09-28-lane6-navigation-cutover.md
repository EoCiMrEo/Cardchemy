# Lane 6 source-navigation cutover and regression repair

## Scope and starting state

This record covers the approved source-only navigation/PDF implementation, its
disposable regression repair, and the retained local installation cutover. The
checkout began this continuation with code head `20260927_0028` but the retained
database and running images at `20260927_0027`. Three current published
Knowledge revisions already had exact encrypted original PDFs. A post-attachment
database backup had been restored and checked in a separate database. The
populated volume and root `.env` were preserved. Ask admission was disabled.

The operator approved source-only, explicitly unverified original-PDF
navigation under ADR-023, implementation, the local cutover and offline/
disposable verification. The failed one-shot public GTE listwise audit was not
repeated or retuned. No paid AI request was made in this continuation.

## Changes and diagnosis

- Added an independent enrolled-student published-Knowledge catalog, bounded
  local page search, extracted-page read and authenticated original-PDF range
  route. Each read checks the current enrollment, publication, revision and
  active embedding space. Search groups distinct pages before its SQL limit.
- Added typed frontend browse/search and the original-PDF viewer path when Ask
  is disabled or returns no match. Cleared stale search results on access
  changes and restored focus to a stable region when a result trigger unmounts.
- Corrected a self-contained non-acronym follow-up query in the v3 navigation
  selector. These implementation changes did not enable Ask.
- Full disposable PostgreSQL initially failed four source-only tests although
  each passed alone. A historical canonical-reference test temporarily installed
  an older trigger, then restored the fixed `0027` definition into a shared
  `0028` test database. Its subsequent v3 references were rejected by the
  canonical-page policy guard. The test now saves and restores the installed
  function definition and asserts exact restoration. Temporary, content-free
  diagnostic printing was removed from runtime and tests after the cause was
  established; no DB constraint or runtime source guard was weakened.
- Updated database and Ask shutdown runbooks for head `0028`, v3/v9, student
  browsing while Ask is off, and the guarded downgrade boundary. Current-state
  and plan status text now distinguish technical cutover from the still-failed
  usefulness gate; the four open Lane 6 checkboxes remain open.

## Verification and retained installation

- Backend offline suite: **2,009 passed, 147 skipped, 2 live deselected**.
- Guarded disposable PostgreSQL: **127 passed, 3 skipped** after the fixture
  repair. It passed migration head/drift and empty-schema downgrade/re-upgrade;
  the runner removed its generated container and credential file.
- Deterministic browser journeys passed with RAG off and RAG on. The RAG-on
  path exercised generation, independent Knowledge index/review/publication,
  source-only Ask/page references, enrollment, email, cards and progress.
  Disposable databases, processes, files and credentials were removed.
- Frontend `npm run check -- --workers=2` passed: **6 unit, 59 component and
  80 Chromium tests**, with one separately gated live-reset case skipped.
  Coverage was 96.66% statements and 85.71% branches. The new browse/search,
  PDF-open and revocation browser cases passed. Explicit bundle check passed:
  initial JS 123,453/130,000 gzip bytes, largest JS 1,265,413/1,350,000 raw
  bytes, and total JS 754,971/780,000 gzip bytes.
- `check_ci.py`, `check_release.py --version 0.1.0`, and `check_context.py`
  passed. Backend/frontend built-image smoke checks passed without credentials,
  mounts or network.
- On the retained database, the old image reported head `0027` with no drift;
  shutdown preview found zero queued, running or possibly remotely executed Ask
  jobs. All application writers were stopped. Matching backend/frontend images
  were built, migration `0027` -> `0028` completed, and the new image reported
  head `0028` with no model drift. API, generation/index/answer/email workers,
  frontend, database and Mailpit were recreated/running healthy. Frontend
  `/healthz` and API readiness both returned HTTP 200. Running API settings
  reported `ask_enabled=false`. A post-restart shutdown preview still found
  zero queued/running/uncertain Ask jobs. Aggregate retained counts remained
  three encrypted PDF manifests, three blocks and three published revisions.
- The restore-verified backup, PDF encryption key, populated volume, root
  `.env` and attached original PDFs were retained. No destructive volume
  operation or paid provider call was made.

## Open quality and release limits

The approved public listwise audit had raw useful rank but its frozen displayed
rule produced **0/16 useful pages**. This technical cutover does not reverse
that result or justify Ask activation. Lane 6 remains **3/7** checked. A fresh
source-separated original-PDF holdout, displayed-window/page-open usefulness,
negative/access controls, genuine sparse-source flashcard behavior, and manual
spoken accessibility/release evidence remain open. The three published lecture
sources have 42, 32 and 33 pages; a one-page subset is only an offline sparse
control. A new ranker experiment, paid embedding/index call, plan expansion or
Ask activation requires a separate approved proposal/envelope under the plan
and ADR-023. Keep `RAG_ASK_ENABLED=false` and the release fence closed.
