# Retained v7 cutover and release recheck

## Scope and authority

The operator's standing Lane 6 implementation authority covers the matching
local stack and forward migration. Starting checkout: dirty `main` at
`6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`. Existing work, populated volumes,
root `.env`, original PDFs and earlier ignored backups are preserved. This
record supersedes retained-0031 and pending-backend statements in the earlier
[integration](2026-10-02-v7-context-runtime-integration.md) and
[UUID repair](2026-10-02-v7-postgresql-uuid-repair.md) records; their historical
bodies and failed results remain intact.

## Safe retained cutover

The root task verified no active generation, index or Ask claim, drained
writers, stopped application services, and created the ignored backup
`backups/cardchemy-before-0032-20261002-v7.dump` (**3,144,835 bytes**).
Its SHA-256 digest is:

```text
b6ce215142e734c797933bc0856343325ba2f3abd5a9bf01073222b205003f86
```

A separate disposable restore reproduced head `20261001_0031` and the retained
aggregate counts before migration. The restore target was then removed.
The retained database migrated forward to **`20261002_0032`** using Alembic;
`current --check-heads` and model drift checks passed. No retained downgrade,
stamp, volume replacement or provider request occurred in the cutover.

Matching API, generation/index/Ask/email workers and frontend were recreated.
The ignored `retained-0032-cutover.json` receipt verifies all eight services
healthy, API and frontend health HTTP 200, ten current backend code hashes
matching, root `.env` unchanged, and preserved counts of three original-PDF
manifests, three archive blocks, seventeen Ask jobs and four generation jobs.
The earlier backups and all three exact lecture originals remain available.

The effective required policy is `related_knowledge_navigation_v7`, with
`visual_source_id_v3`, 4,096 thinking-inclusive output tokens and a **120-second**
source-judge deadline. The release-policy fence remains
`two_request_local_support_v1`; **Ask, source judging and availability are
false**. New context/schema/code do not enable provider execution. A unique
literal subject may be projected only for an unresolved follow-up from its
strictly preceding user question, with immutable admission and repeated
authorization/context checks. Embedding remains the raw current question;
no generated answer, answer verifier, full history or automatic retry is added.

## Verification actually completed

These terminal results were observed by the root task on the current checkout:

| Check | Result |
| --- | --- |
| Focused admission/current worker contracts | 85 passed |
| Full backend offline suite | 4,289 passed, 209 skipped |
| Guarded disposable PostgreSQL harness | 187 passed, three skipped, 4,308 deselected; heads/drift/base/head passed |
| Full frontend check | Types, lint, coverage and build passed; 83 component, six Node and 84 Chromium tests passed, one separate opt-in live reset skipped |
| Bundle budget | 123,452 initial gzip bytes / 130,000; 756,471 total gzip / 780,000; 1,265,413 largest raw / 1,350,000 |
| Deterministic instructor/student journeys | RAG-on and RAG-off both passed; disposable resources cleaned |
| Current backend, frontend and OCR image smoke | Passed; OCR smoke used no network and invented runtime values |
| Real retained browser PDF check | Week 2 page 1 and keyboard next to page 2, Week 3 page 1 and Week 4 page 1 rendered; old PDF failure warning absent |
| Browser keyboard/dialog check | Escape dismissal and focus restoration passed in the logged-in mobile-width browser |

The browser check used authenticated original-PDF browsing, not Ask or a
provider request. No private lecture text, image, credentials or response is
included in tracked evidence. Spoken assistive-technology testing is not
established by the browser accessibility tree or keyboard checks.

The initial current security run found no HIGH/CRITICAL vulnerabilities in the
three images and no workspace secret findings, but three noncredential
Git-history scanner matches prevented that run from passing. Exact scoped
allowlists and the documented full scanner rerun subsequently passed; see the
[separate browser/security record](2026-10-02-v7-pdf-browser-and-security-verification.md).
Historical scan findings and reports remain preserved.

## Remaining gates and limits

Lane 6 remains **3/7**. The [latest public trial](2026-10-02-public-heldout-v6-terminal-result.md)
stopped after Q038 HTTP 503, with partial 49/50 useful cards across 38 evaluated
questions. Complete different-PDF public heldout availability and
quality, matching independent private displayed-window/page usefulness,
spoken assistive-technology and the final release gate remain open. Partial
public usefulness cannot substitute for a complete pass. Private Knowledge
transfer and every new provider trial still require their separate precise
approval. No Ask activation, hosted CI, protected merge, release publication
or production deployment is claimed here.

Documentation is reconciled to retained **0032/v7**, preserving older dated
snapshots as history. The populated installation stays healthy with Ask off.

## Documentation verification

A subsequent full backend offline run on the current checkout completed with
**4,381 passed / 209 skipped** in 346.84 seconds. This includes newly prepared
diagnostic contracts; changes made after collection retain their separate
targeted checks. No provider quota, operator environment or retained database
was used by the suite.

The documentation subtask read the aggregate retained preservation/cutover
receipts and relevant canonical guidance, maps, ADRs and dated records. It
updated current operating statements, maps and plan/ADR headers rather than
rewriting historical log bodies. No services, source/tests, provider caller,
root `.env` or private review artifact were modified by this subtask.

`python scripts/check_context.py` passed **37 required files, 79 active guides
and 2,002 local links** after reconciliation. Scoped standard
`git diff --check` passed; Git emitted only line-ending conversion notices.
An alternate check with an overridden `core.autocrlf=false` interpreted the
existing Windows CRLF as trailing whitespace; the repository's normal check
passed again without changing Git configuration or unrelated line endings.
An exact checklist recount confirmed **three checked/four unchecked** Lane 6
items. Link validation establishes documentation navigation, not product quality.
