# Approved source navigation and PDF implementation

Date: 2026-09-27. Starting branch `main`, HEAD `6c02d6c`; extensive existing
Lanes 0–6 work is preserved. The operator approved
[automatic unverified references and original-PDF viewing](2026-09-27-source-navigation-pdf-recommendation.md)
including plan/ADR updates and implementation. New ADR-023 explicitly
supersedes only ADR-022's source-sufficiency admission and extracted-page-only
viewer. No answer generation/verifier is restored. Ask stays disabled until
navigation quality and release checks pass; Lane 6 remains 3/7.

## Work allocation and intended changes

- Backend PDF archive: revision-bound authenticated encryption, byte quotas,
  canonical capture and exact-hash old-PDF attachment, current-access range API.
- Backend Ask navigation: immutable v2 job policy, bounded page ranking and
  neighbor inspection, local lexical fallback for embedding unavailability.
- Frontend: typed authenticated PDF.js page viewer and explicit unverified
  related-reading cards, unavailable-source/failure/loading accessibility.
- Root: approved plan/ADR/context, policy migration, integration and independent
  stagewise quality/security/release verification.

The first PDF and frontend subagent turns hit a usage limit before runtime
edits landed; their feasibility findings were retained, and continuations
were requested. No failed turn is counted as completed implementation.
No root `.env` bytes, retained database or volume were changed. Provider
spending, paid indexing and runtime activation require later explicit bounds.
Actual changes, tests, errors and limits will be appended as they occur.

## Implementation and isolated verification in this continuation

- `0026` adds immutable revision/SHA-bound original-PDF manifests and AES-256-GCM
  1 MiB blocks. Capture and exact-hash/page-count instructor reattachment use
  serialized Knowledge locks, 100 MiB/PDF, 256 MiB/Subject, 512 MiB/uploader and
  2 GiB/deployment caps. Temporary generation sources remain separate. The Ask
  HEAD and mandatory bounded (8 MiB maximum) Range routes reauthorize the
  complete current reference bundle on every call; bad/missing originals fail
  safely. Delete cascades blocks. JSON privacy export excludes archive bytes,
  ciphertext and keys. A missing archive key permits old installation startup
  but rolls back new capture safely. Its own focused backend suite passed 87/87.
- `0027` and the model checks admit the immutable navigation-v2/selector-v8
  pair while preserving old v1/v7 records; parent stage and at-most-one physical
  embedding/zero-retry/zero-answer guards continue. Bounded navigation examines
  eligible nearby pages, exact canonical cues and lexical-only fallback after
  transient embedding failure. Related cards are unverified and source-only.
- Frontend adds lazy PDF.js canvas/text viewing with authenticated serialized
  ranges, page reauthorization, adjacent exact cue and clear missing-original/
  fallback states. Browser and bundle gate remain in progress. Its deferred PDF
  display asset currently exceeds the old global raw/total JS budgets; no budget
  threshold has been changed. A measured proposal will be reviewed separately.
- The user-authorized root `.env` was **appended only** with an independent
  original-PDF key; no existing bytes were rewritten, and the value was never
  printed or logged. Settings validated its length and independence.
  `check_config_migration.py` and `docker compose config --quiet` passed.
- Targeted backend navigation/PDF/CORS/service checks: 100 passed.
  Guarded disposable PostgreSQL suite: 124 passed, 3 skipped, 1994 deselected;
  head `0027`, drift check, downgrade to base and re-upgrade passed. Its generated
  container and credential file were removed. No retained volume was touched.
- A first deterministic cross-stack journey stopped at a **stale test assertion**
  expecting the retired v1 profile on line 112 of its browser spec, before Ask
  work began. This is not a product-quality pass. The browser spec is being
  updated to v2 and original-PDF open before the next disposable rerun.
- Full backend offline suite and frontend full check are still running.
  No paid embedding/index request, retained DB migration, service recreation
  or Ask activation was performed. Lane 6 remains 3/7.

## Later checks and repaired deterministic journey

- The full offline backend suite first found three historical experiment tests
  asserting the retired v1 release-policy literal. Their active-policy
  assertions were updated to navigation v2; the focused rerun passed 93 with
  one skip. The first broad run was 1,976 passed, 5 skipped, 142 deselected,
  **3 failed** before that correction. A clean full-suite rerun remains due.
- The journey browser spec was updated from v1 to v2 and now waits for an
  authenticated HTTP 206 original-PDF range and a visible page 1 viewer.
  A second guarded disposable journey passed both `rag-off` and `rag-on`.
  The RAG-on database check proved generation, independent Knowledge capture/
  index/review/publication, source-only Ask references, enrollment, email and
  study progress. No assistant answer row was created. Both disposable
  containers, generated fixtures and credentials were removed.
- The clean full backend offline rerun passed **1,979**, skipped 5 and
  deselected 142 live/service cases. A contract mismatch then surfaced in
  original-PDF capture: configured `PDF_MAX_PAGES` permits up to 2,000, while
  the new archive initially capped pages at the default 100. Before any
  retained migration, the uncommitted `0026` model/migration/service cap was
  aligned to the existing validated setting (maximum 2,000) and tested with
  101-page metadata. Focused PDF/migration tests passed 34/34. A fresh
  guarded disposable PostgreSQL run passed **125**, skipped 3 and deselected
  1,999, with head `0027`, drift and downgrade/re-upgrade checks. No retained
  schema/data was modified.
- Current lazy PDF.js build exceeded the old global JS gate: initial 130,013
  versus 130,000 bytes gzip, largest 436,321 versus 400,000 raw, and total
  373,839 versus 240,000 gzip. The new viewer is deferred, but the existing
  total cap counts deferred assets. A separate independent frontend review is
  seeking a smaller package; no threshold was relaxed and release remains
  unproved.

## Independent offline PDF-page diagnostic (not a release result)

An independent reviewer froze a private, source/document-separated 12-question
roster across three previously unreviewed local PDFs (122 pages total), with
four direct, four paraphrase and four follow-up cases. The private roster and
page-level assessments are confined to an owner-private OS Temp folder; its
roster SHA-256 is `24d25d1ed823797081d8f85ec36a82acc5e9a359b669c51391659216b44b336d`.
There were no exact page-text duplicates against the four previously exposed
PDFs. Selector/retrieval/chunking file hashes were frozen and unchanged during
the single local lexical-proxy run. Gold exact-page hit@3 was 10/12; visually
assessed useful-page hit@3 was 11/12, top-one 9/12. Across all 36 displayed
cards, 18 were useful, 2 partial and **16 unhelpful**; one follow-up had no
useful displayed page. Oracle supplied-page selection was 12/12. This shows
over-filling with weak pages. It is an offline proxy on unpublished, unindexed
documents: it does not prove real SQL/vector retrieval, current-source access,
quote/window fidelity or PDF open and cannot satisfy the release gate.
The frozen cases will not be used for tuning. Improvements must use separate
development evidence and then a fresh independent holdout.

## Retained installation preflight (read only)

The existing local Compose DB/API/frontend/Ask-worker containers were healthy
when inspected; the installed images still predate `0026`/`0027`, and Ask is
off. A read-only digest comparison against the operator's supplied lecture
directory found **3 active published revisions and 3 exact original-PDF SHA
matches** among 7 local PDF files, with 0 unmatched published revisions.
No filenames, hashes, PDF contents or database rows were printed or stored.
This makes exact legacy attachment feasible after a backup, guarded migration
and compatible image cutover; it does not claim any originals are archived yet.

## Later frontend and documentation integration

- The instructor Knowledge view now has a separate **Attach exact original
  PDF** action for a ready active revision. It checks configured byte limits
  before upload, keeps revision upload and attachment mutually exclusive, and
  reports safe success/error states. The backend still independently checks
  exact SHA-256 and page count. Frontend typecheck, lint and E2E typecheck
  passed; focused Chromium attachment tests passed 2/2, including mismatch,
  retry, oversize and unavailable-revision controls. No provider or retained
  database call was made for these tests.
- The operator approved the measured PDF.js budget: count `.js` and `.mjs`,
  retain initial JS gzip <=130,000 bytes, set total JS gzip <=780,000 and
  largest raw JS <=1,350,000. The previous checker omitted the `.mjs` worker
  (376,093 gzip bytes), so its 373,839-byte total was not the actual total.
  The English copy catalog was split so initial routes eagerly load only
  common/routing strings. A subsequent local build/checker measured initial
  123,431/130,000, largest 1,265,413/1,350,000 and total
  751,438/780,000 bytes; full frontend checks were still running at this
  point. The worker remains deferred and same-origin.
- Updated Ask maintenance, self-hosted deployment, AI provider, privacy,
  current-state, architecture and changelog context for navigation v2,
  migrations `0026`/`0027`, original-PDF backup/recovery, exact legacy
  attachment and the closed Ask gate. The measured budget amendment is in
  the plan; passing an enlarged bundle limit does not establish product
  quality.

## Exposed development-case navigation diagnostic

An independent reviewer used only the already exposed, currently published
107-page development corpus and eleven owner-reviewed seed questions. An
offline lexical proxy and the actual v8 selector yielded useful-page hit@3
11/11 but top-one 6/11. Across all 33 displayed cards, 19 were useful,
4 partial and 10 weak. All 18 distinct selected original pages and their
exact displayed cue windows were visually inspected. Useful and weak score
ranges overlapped (0.726–1.534 versus 0.792–1.542); in 8/11 questions they
shared the same tuple of topic hits, query-term count and title hits. A
global score/topic cutoff, top-one-only rule or rank margin therefore cannot
honestly eliminate filler from this development set. This diagnosis is not
real SQL/vector, publication/access, original-PDF-open or release proof. The
separate frozen 12-case new-PDF holdout and its recorded hashes were not used
for tuning; Ask remains off.

## Capacity correction and frontend gate retry

- A cross-contract review found that the new original-PDF archive had been
  widened to 2,000 pages based only on `PDF_MAX_PAGES`. Existing Subject
  Knowledge is bounded to **100** pages by ADR-012, capture preflight and
  canonical page/chunk database constraints. This wider archive setting was
  inconsistent. Before any retained migration, the uncommitted `0026` model,
  migration and encryption preflight were corrected to 100 pages, with a
  regression asserting that raising `PDF_MAX_PAGES` does not bypass the
  Knowledge limit. Focused PDF units passed 30/30. This supersedes the earlier
  log statement claiming 2,000 pages was the right archive bound. The
  configured PDF extraction upper range may exceed Knowledge capture's
  separately enforced 100-page limit; the latter returns a safe unsupported
  capture result.
- The first full frontend `npm run check` passed types, lint, six Node units,
  54 component tests/coverage and build, then had two unrelated accessibility
  Chromium timeouts on pages still showing Loading under eight workers
  (73 passed, 1 skipped, 2 failed). The six accessibility cases passed on a
  focused two-worker rerun. A four-worker full E2E run had one timing-sensitive
  pre-existing card-save test failure (74 passed, 1 skipped, 1 failed): its
  300 ms artificial response completed before the pending-state assertion.
  The test now holds the mock response until its pending controls have been
  asserted; its focused three-case run passed. A clean full browser rerun is
  still required, so the frontend gate is not yet counted as passed.
- Release metadata check initially failed because canonical/backend/frontend
  NOTICE bytes differed after PDF.js attribution was added. The canonical
  notice was synchronized to both redistributed copies and the upstream
  Apache-2.0 text was copied to `frontend/public/legal/PDFJS-LICENSE`.
  `python scripts/check_release.py --version 0.1.0` then passed local release
  metadata validation; this is not signature, image or hosted-release proof.
- Disposable PostgreSQL migration/integration was restarted with the project
  venv after a first launcher attempt used system Python lacking Alembic. The
  first attempt stopped before migration and cleaned its disposable resources.
  The venv run is still in progress at this log checkpoint. No retained
  database or volume was modified.

## Completed disposable and browser verification checkpoint

- `backend/venv/Scripts/python.exe scripts/test_services.py postgres` passed
  on guarded disposable PostgreSQL: **125 passed, 3 skipped, 1,999 deselected**.
  It exercised migration through `0027`, head/drift detection,
  downgrade/re-upgrade and PostgreSQL integration; disposable services were
  cleaned. This is not evidence of a migration on the retained installation.
- `backend/venv/Scripts/python.exe scripts/test_journey.py` passed both
  `rag-off` and `rag-on` deterministic offline-provider journeys. The latter
  covered generation, capture/index, review/publication, source-only Ask
  references, original-PDF HTTP 206, browser, mail and study without paid AI.
  Disposable resources were cleaned.
- `backend/venv/Scripts/python.exe -m pytest -q` from `backend` passed
  **1,980 passed, 145 skipped, 2 deselected**. Skips/deselections do not prove
  live provider, retained database or production success.
- After the test timing correction, `npm run check -- --workers=2` from
  `frontend` passed typecheck, E2E/component typecheck, lint, six Node units,
  54 component tests, coverage (96.66% statements, 85.71% branches), build and
  **75 Chromium passed, 1 live-reset skipped**. The earlier high-concurrency
  loading timeouts and pending-state race did not recur in this full rerun.
- The bundle checker passed with initial JavaScript **123,431/130,000** gzip
  bytes, largest raw JavaScript **1,265,413/1,350,000** bytes and total
  JavaScript including `.mjs` **751,438/780,000** gzip bytes. Local CI and
  release-metadata checkers passed; neither represents hosted CI or a signed
  release.
- Ask remains disabled. Original-PDF attachment and the new migrations have
  not been applied to the retained Compose installation. The independent
  navigation quality diagnostic remains below release quality because weak
  filler appears among the displayed pages.

## Retained local backup and pre-cutover checkpoint

- Read-only preflight found the retained local stack at `20260926_0023`, with
  healthy DB/API/frontend and an answer worker reporting disabled. Aggregate
  operations showed no queued generation, indexing, email or Ask work; prior
  terminal Ask records remained. The root configuration/Compose preflights
  passed without printing secret values.
- Stopped the API, frontend and application workers while keeping PostgreSQL
  and its existing volume. Created a custom-format dump under ignored
  `backups/lane6-navigation-pre0027-20260927/`, recorded a SHA-256 and size in
  its local manifest, then restored **that copied file** into a separately
  named rehearsal database with `pg_restore --exit-on-error`. The source and
  rehearsal both reported `20260926_0023`, 36 tables and identical aggregate
  counts across 18 representative tables, including Knowledge pages/chunks,
  generations, Ask jobs and cards. The rehearsal database was removed after
  verification; the dump, manifest, real database and volume remain.
- A read-only security review found one reliability defect before migration:
  idempotent original-PDF reattachment could report success without proving
  the retained archive decrypts under the configured key, and a mismatched
  parseable key could make HEAD report available while GET fails. A focused
  fix and wrong/missing-key tests are in progress. Do not count a retained
  image/schema cutover or PDF attachment as complete at this checkpoint.

## PDF-key correction, local migration and approval-review interruption

- The PDF-key defect was fixed before the new backend image was built:
  idempotent reattachment authenticates all stored encrypted blocks in
  bounded batches and checks the original SHA-256; HEAD checks archive shape
  and authenticates the first and last complete blocks (at most 2 MiB), while
  every GET authenticates each served block. HEAD does not prove untouched
  interior bytes; an interior defect fails the corresponding GET. Wrong or
  missing keys and damaged archives yield a safe unavailable result. Focused
  PDF tests passed 34/34.
- Repeated full backend offline after this correction: **2,000 passed, 145
  skipped, 2 deselected**. Guarded disposable PostgreSQL: **125 passed, 3
  skipped, 2,019 deselected**, including head/drift and downgrade/re-upgrade;
  both deterministic RAG-off/on cross-stack journeys passed and cleaned their
  disposable resources. These are distinct from retained-instance checks.
- Built matching new frontend and backend Compose images. With application
  writers stopped and the restore-verified backup retained, `docker compose
  run --rm migrate` completed `0023`→`0024`→`0025`→`0026`→`0027` on the
  retained local database. The command exited zero and printed all four
  migration steps. No volume deletion or provider request occurred.
- The next `docker compose run --rm --no-deps backend alembic current
  --check-heads` was **not executed**: automatic approval review rejected the
  escalation because the account hit its usage limit. This was a review
  failure, not an unsafe-command finding. Do not bypass it. Retained head/
  drift verification, old-job resolution preview, container recreation,
  health/profile checks and original-PDF attachment remain outstanding. The
  API/worker/frontend services are stopped; PostgreSQL and its populated
  volume remain. Ask remains disabled. Once tool approval is available,
  resume from head/drift verification rather than rerunning migration blindly.

The operator asked to resume once automatic command review is available.
An hourly, quiet-until-actionable heartbeat was attached to this task for that
purpose. It will retry the normal reviewed path, not a bypass, and disable
itself when Lane 6 is complete. Until then, the retained app stays stopped
and Ask remains off. Local documentation and public audit preflight continued
without Docker or provider access; the one-shot model inference has not run.

## Resumed retained local cutover and exact PDF attachment

- Automatic command approval became available again. The retained database
  passed `alembic current --check-heads` at `20260927_0027` and `alembic check`
  reported no upgrade operations. The shutdown-resolution preview had zero
  queued/running/uncertain Ask jobs; no mutation was needed.
- Matching backend, frontend and workers were recreated without a rebuild;
  Compose reported all application services healthy, `/healthz` returned 200,
  and safe configuration checks reported Ask disabled, source-only unavailable
  for admission, and the PDF encryption key configured. No provider call was
  made and the original populated volume was preserved.
- The first attempt to mount the local lecture directory read-only in Docker
  failed before a container started because Docker Desktop could not create
  its E: host mount path. The seven local PDFs were instead copied into the
  backend container temporarily. A one-off script called the existing
  instructor-authorized attachment service within one database transaction.
  All three active published revisions matched exact file SHA; three encrypted
  original-PDF archives were attached, with zero prior archives. The temporary
  PDFs and script were removed from the container afterward. No file names,
  PDF content, database identifiers or digest values are retained in this log.
- A new ignored custom-format backup was written under
  `backups/lane6-navigation-postpdf-20260927/` with a local size/checksum
  manifest. The **copied host backup** restored with `--exit-on-error` into a
  separately named database. Both retained and restored databases reported
  three PDF manifests, three PDF blocks, three published revisions and head
  `20260927_0027`; the restore-test database and temporary container dumps
  were removed. The backup and existing PDF key must both be preserved for a
  future restore. This establishes local backup/restore integrity, not Ask
  ranking quality or browser PDF access.
- The approved listwise audit has still not run; Ask remains off. Independent
  review also identified follow-up resolution, selector budget ordering,
  transient viewer transport, and student no-match browse gaps. Focused
  repairs and a new immutable policy revision are in progress before another
  retained cutover. The earlier interruption paragraph above is historical.
