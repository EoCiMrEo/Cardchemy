# Lane 6 source-only Ask implementation and verification

## Scope and starting context

- Owner approved ADR-022 runtime implementation, then explicitly removed
  answer generation and answer verification from Ask AI. Students navigate
  published lecture evidence rather than receive generated answers.
- Working branch: `main`; starting HEAD:
  `6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`. Existing Lane 0–6 edits,
  logs, untracked work and installation secrets were preserved.
- Read current repository guidance, orientation, module maps, accepted
  decisions and relevant dated Lane 6 investigation evidence. Earlier memory
  served only as historical orientation.
- Development volume reset and root configuration changes are authorized.
  Reset is deferred until private quality evidence is measured: wiping now
  would remove the current reviewed Knowledge corpus.

## Implementation

- `rag_answer.py` now constructs only an embedding provider. New jobs snapshot
  `related_knowledge_v1`, complete as `related_knowledge` or `no_match`, and
  create no assistant message. At most one current-question embedding and
  zero automatic retries are permitted. Short acronym follow-ups resolve
  locally from bounded prior user turns; history never leaves the worker.
- References to at most three exact source windows (480 characters each)
  commit atomically under current claim/authorization/Knowledge locks.
  Reads recheck the whole bundle and current canonical page. Page highlighting
  requires an exact span; formatting differences use a separate quote view.
- New Alembic `20260926_0022` adds conditional source-only identity/result,
  stage/call and ordered-reference constraints without rewriting older rows.
- API/types/UI expose source-only availability, costs, references, page view,
  no-match and safe manual retry. Legacy generated assistant messages are
  hidden. Copy identifies stored extracted pages; original PDFs are not retained.
- Compose uses the standard backend image for Ask with embedding credentials
  only. Dedicated answer image/lock/build/CI/SBOM variants were removed.
  Offline historical model research files remain outside the Ask runtime path;
  no ONNX/tokenizers/numpy packages or verifier mounts ship in the backend.
- The former paid private answer comparison entry point now refuses
  `answer_generation_retired`; the maintained opt-in RAG smoke is embedding-only
  with fresh source-only authorization. No live calls were made in this work.
- Root `.env` changed only the nonsecret `RAG_ASK_ENABLED` switch to false.
  The source policy release fence remains closed pending measured private
  displayed-window/holdout quality. No production enablement is claimed.

## Verified results

- Targeted runtime/config/CI/release/harness tests: 191 passed.
- Disposable PostgreSQL: 97 passed, 3 skipped; migration upgrade/head/drift,
  empty downgrade/base/re-upgrade/head/drift passed. No operator DB was
  downgraded. Owned test containers/credentials were cleaned up.
- Full backend offline: first run exposed 12 stale old-live-harness failures;
  after retiring/changing those harness contracts: **1,368 passed, 117 skipped,
  2 live tests deselected**. Skips/deselections are not provider evidence.
- Frontend before clean dependency synchronization: 4 unit, 44 component and
  68 Chromium tests passed, 1 separately gated live-reset case skipped;
  types/lint/coverage/build passed. Host Vite differed from the lockfile/Docker
  build, so `npm ci` subsequently synchronized 400 packages; a final run on
  those dependencies remains required.
- Current backend/frontend Docker builds passed. Network-free backend runtime
  smoke passed, including absence of retired inference packages/model mount;
  frontend runtime smoke passed.
- Context check passed: 37 required files, 77 guides, 1,244 active links.
  CI source/protection/budget validator passed all four workflows.
- Deterministic journey RAG-off passed. New source-only RAG-on initially
  failed because the test expected availability before the first Knowledge
  publication/active-space activation. Expectation corrected; latest rerun
  is still in progress at this record's creation.

## Remaining evidence and operational state

- Lane 6 remains **3/7**. Existing reviewed source/claim pairs do not certify
  the exact windows selected by the new runtime. Private displayed-window
  usefulness, independent holdout, current-page opening, ranking thresholds,
  sparse whole-source quality and release gates remain outstanding.
- Retained application containers still use older built bytes with Ask off;
  newly built images have not yet been cut over. No reset, paid test, hosted
  CI, release publication or spoken screen-reader check occurred here.
- Subagents delivered bounded documentation/test work; their remaining turns
  hit the account usage limit. Root continued the verification/cleanup directly.

Subsequent checks and cutover will be appended with their actual outcomes.

## Subsequent verification and Ask-off cutover

- Final clean-lock frontend gate: 4 Node unit tests, 46 component tests and
  68 Chromium tests passed; 1 independently gated live-reset test skipped.
  Types, lint, coverage, bundle budgets and build passed. Whitespace-only
  canonical-page span differences now highlight the actual source substring;
  unrelated in-bounds spans remain unhighlighted.
- New additive `20260926_0023` binds each source-only stage's policy and current
  manual/worker attempt identity to its parent job. This prevents NULL or legacy
  stage snapshots from bypassing source-only stage/request guards. Its first
  disposable attempt exposed asyncpg's one-command prepared-statement rule;
  separate function/trigger executions fixed it before deployment.
- Full disposable PostgreSQL gate passed: **98 passed, 3 skipped**, with
  upgrade/head/drift, downgrade to base and re-upgrade. Full backend offline
  subsequently passed **1,406 tests, 118 skipped, 2 live deselected**.
  Additional private probe tests exercised only injected/mocked transport.
- Deterministic RAG-off and source-only RAG-on journeys passed. The latter
  created two source-only searches, opened a current extracted page and tested
  unrelated-question no-match, private history and cross-Subject rejection.
  Neither journey spent provider quota.
- Before real additive migration, aggregate queue inspection confirmed zero
  pending/running generation, index, Ask and email work. Two initial metadata
  commands used wrong role/session/table names; they failed read-only and made
  no changes. Source inspection corrected the reader; no private contents were
  queried. Writers were then stopped.
- A 1,314,578-byte owner-private custom PostgreSQL dump at head `0022` was
  restored successfully in a disposable, network-free database. Document,
  page, chunk, Ask-job counts and head matched. Restore container was removed;
  private backup is retained in the operator Temp directory. No backup contents
  or credentials entered logs.
- Retained migration **0023 applied successfully**. API, generation/index/Ask/
  email workers and frontend were recreated; all six use the current image IDs
  and are healthy. The parent-stage trigger is present. Ask remains false,
  source-only availability false and release-policy fence closed. Ask worker
  has no answer credential, ONNX/tokenizer/numpy dependency or verifier mount.
- Standard backend, OCR backend and frontend image smoke passed. A subsequent
  security run found five synthetic secret-pattern matches and one HIGH OCR
  package vulnerability; remediation and exact rescan outcomes are recorded
  separately. No security threshold was lowered.

These results complete implementation verification, not private excerpt
usefulness, manual spoken accessibility, a paid live run, clean-volume reset,
hosted CI or release publication. Lane 6 remains **3/7**.
