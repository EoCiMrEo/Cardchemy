# Matching visual source-only contract and retained backup

Date: 2026-10-01 (America/Chicago). Scope follows the operator's standing
authorization for aligned Lane 6 implementation after the complete public
calibration passed. Source judging and Ask remain disabled; this record does
not authorize another provider call or private Knowledge transfer.

## Preserved installation

Read-only queue checks found no queued/running generation, index or Ask jobs
and no sending email. API and all five application workers were stopped
normally before new source/migration edits. The populated database stayed at
`20261001_0030`; no volume was removed or real downgrade performed.

The ignored backup `backups/cardchemy-before-0031-20261001-v6.dump` is
3,066,260 bytes, SHA-256
`4e156d1b897bc37388e687be0cf8f1288cd1b8b851aaaab3f188b36faae7c824`.
Host and container hashes matched. Restore with exit-on-error into the
newly created `cardchemy_restore_0031_v6` database reproduced head 0030,
three PDF manifests, three PDF blocks, seventeen Ask jobs and four generation
jobs. Only the disposable rehearsal database was removed. The original
volume, backups, PDFs and root `.env` were preserved; root bytes matched.

There is no explicit source-output override in root `.env`; the new validated
4,096 default can take effect without editing configuration or secrets.

## Immutable historical contracts

Comparison against the pre-change immutable local backend image
`sha256:b73791614cfc41f34b3042cc81762396e961e5768bae26c1496827a774356e3f`
proved exact historical file preservation:

- Installed 0030 migration: SHA
  `662c066cb7d5d16e75430c373a60fa469144bf9ee86e11ae23b8b2b05d956055`.
- Visual source contract v1: SHA
  `d74f2e15315725adbf5c8e78b50e1ae13c2fe171f8f2a3edae7d302c5fbe740e`.

The comparison ran networkless without DB access. New `0031` and v6/v2
contracts preserve historical reads while fencing old execution/manual retry.
Thinking-inclusive output rises to 4,096; prompt, current-question scope,
image/request/verdict limits and single-call/no-answer policy remain bounded.

## Verification to date

- Full frontend check: six Node units, 74 component tests and 83 Chromium
  tests passed; the separate opt-in live reset test was skipped. Types, lint,
  build, coverage and bundle checks passed. New tests retain old v5 references
  and reject an available-but-stale v5 profile for new work/manual retry.
- Guarded disposable PostgreSQL: 161 passed, three skipped, 3,534 deselected;
  complete head/drift and selected downgrade/re-upgrade checks passed.
  Disposable services and their generated credential file were cleaned.
- Independent read-only backend audit found exact model/0031 checks and
  remote-attempt index parity; final adaptive-render review is pending.

## Newly observed image limit

Different-PDF offline preparation stopped after 64/86 pages because one
1,600-pixel whole-page PNG exceeded 1 MiB. No provider call occurred. A
separate bounded successor rendered all 86 pages: 84 at 1,600 pixels and two
at 1,400, preserving full pages and actual scale metadata. Its maximum PNG
was 906,621 bytes; final readability/qualification review is still required.
The matching not-yet-deployed v6 renderer is being prepared with finite size
fallback and one cumulative page deadline. Historical v1 stays unchanged.

No retained 0031 migration, independent heldout score, private-source
measurement, actual spoken accessibility or Ask enablement is claimed here.

## Completed forward cutover and real checks (later on 2026-10-01)

The preceding preparation snapshot is superseded by this actual cutover.
The retained installation was migrated forward from 0030 to `20261001_0031`
after the verified backup. Alembic current/head and drift checks passed.
Matching API, generation/index/Ask/email workers and frontend were recreated
under the documented development profile; all services are healthy. Loopback
API health and frontend health both returned HTTP 200. Read-only counts
remain three PDF manifests, three PDF blocks, seventeen historical Ask jobs
and four generation jobs. Root `.env` and backup bytes remain identical.

Effective non-secret settings confirm Ask=false, available=false,
source-judge=false, required policy `related_knowledge_navigation_v6`,
runtime fence `two_request_local_support_v1`, `visual_source_id_v2`,
32,768 input / 4,096 output tokens. In-container hashes of the v2 contract,
adaptive renderer and 0031 migration match the working tree. Actual running
image identities are backend
`sha256:cc8b320c642682aadeebda089aca00f5736dff065c3336486190bbcfece1d5fb`
and frontend
`sha256:137ec39c9b5fea1937f5422b03a83555abd2dd9d166727d05392649da68869ec`.

- Complete backend offline suite: 3,552 passed, 181 skipped, two deselected.
- Current real instructor/student journeys both passed, RAG disabled and
  enabled, using only deterministic providers and disposable services. The
  enabled journey proves exact original-PDF reads, source-only outcomes,
  no-match, enrollment/history boundaries, generation and Study transactions.
  Both scenarios cleaned processes, containers, fixture data and credentials.
- A networkless, read-only 4-CPU/2-GiB native Linux probe rendered the already
  cached public lecture 13 pages 5 and 7 with the current production renderer.
  Both definitively oversized 1,600-pixel PNGs were safely reduced to 1,400
  pixels, retaining complete pages: 837,367 and 906,621 bytes, 1,400×1,082,
  3.701 seconds total. Binding scale and the 4,096 thinking-inclusive usage
  contract passed. Initial probe import/setup failures produced no provider
  requests and were repaired without mounting application secrets.
- Actual in-app browser inspection on the retained authenticated student
  session displayed the original Week 2 and Week 3 page 1 PDFs; Week 2
  navigation opened page 2 and retained its original citation page separately.
  Week 4 and final browser evidence continue below when complete.

Later actual browser inspection also displayed the original Week 4 page 1
in the retained authenticated student session. Week 2, Week 3 and Week 4
original PDFs therefore all rendered successfully; Week 2 page navigation
was also exercised. No Ask request or provider call was made in this check.

Independent heldout/private usefulness and actual spoken accessibility remain
open. These implementation and preservation checks do not enable Ask or close
the four outstanding Lane 6 quality/release checklist items.
