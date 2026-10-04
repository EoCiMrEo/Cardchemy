# Retained v8 cutover and release checks

## Scope and preservation

Continue the authorized Lane 6 work on dirty `main`, HEAD
`6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`. Preserve existing changes, root
configuration, populated volume, exact original PDFs, all backups and every
provider attempt/result/failure. No live provider request is authorized here.

The initial backup preflight refused before changing anything because the
retained containers were stopped. Start only the exact existing database and
local mail sink, then repeat the backup workflow. Drain writers and create
`backups/cardchemy-before-0033-20261003-v8.dump`, 3,184,083 bytes, SHA-256
`9ef66883c7fce55612f3d270e55313dcca45d059e4be149b6d0b327450f5b98f`.
Restore into the separately named owned target, compare head and aggregate
counts, then remove only that rehearsal target. Earlier backups are intact.

## Retained forward cutover

Alembic migrated `20261002_0032` forward to **20261002_0033**. Retained
`current --check-heads` and `alembic check` passed. No retained downgrade,
stamp, volume replacement or secret regeneration occurred. The preservation
and cutover receipts are in ignored `.agent/.verification` storage.

Matching services use **related_knowledge_navigation_v8 / visual_source_id_v5**,
4,096 thinking-inclusive output tokens and a 120-second judge deadline.
All eight services are healthy; API readiness and frontend health returned
200. Root `.env` bytes are unchanged. Aggregate counts are preserved:
three original-PDF archives, three PDF blocks, seventeen Ask jobs and four
generation jobs. The release fence remains `two_request_local_support_v1`;
Ask and source judging are **disabled**.

Compose's first startup wait expired while the host ran parallel disposable
checks/scanners. The API subsequently returned 200; generation/email health
also recovered. No timeout was treated as proof of process completion or
reason to replace data. The later exact cutover receipt verifies all health.

## Verification actually completed

| Check | Result |
| --- | --- |
| Combined guarded PostgreSQL | 250 passed, three skipped; heads/drift and disposable base/head round-trip passed |
| Full frontend | Types/lint/coverage/build, six Node, 85 component and 84 Chromium tests passed; separate opt-in live reset skipped |
| Both real-app disposable journeys | RAG-on and RAG-off passed with deterministic providers; owned data/processes/credentials cleaned |
| Backend, OCR and frontend image smoke | All three credential-free/networkless probes passed |
| CI/protection definition checker | Passed; this is local configuration validation, not hosted CI or protected merge |

The first combined PostgreSQL run had eleven failures in new independent
fixtures (claim-token length and an invalid direct attempt rewrite). Preserve
that result; correcting those fixtures did not change runtime constraints.
The subsequent complete 250-test run passed, including all 63 new v8 cases.
Maintained RAG ablation metrics retained their existing acceptance.

Built immutable image identities:

- Backend: `sha256:7002fd38e80dbe3ac89e4ab64e305944848d4cdd594de2bf41d229237a30af41`.
- Backend OCR: `sha256:2dde663bb4104b38fc1336d85285e08c20789684f1aae907d51ff52fe1f9284d`.
- Frontend: `sha256:e672a910c14e69f68fcecd974fac4435c258c0d12fcdbefca2b46889767ef694`.

The initial isolated security run found two noncredential public-review-key
hashes; its images and worktree gates passed, but the full run is not a pass.
The [independent classification and final full rerun](2026-10-03-v8-secret-container-gates.md)
passed: zero Gitleaks/worktree secret findings and zero HIGH/CRITICAL findings
on all three exact image identities. The two public-key fingerprints receive
only an exact match/path allowlist; earlier failed reports remain intact.
The [reconciled full backend run](2026-10-03-v8-full-offline-reconciliation.md)
passed 5,298 tests, with 270 skipped and two live-AI tests deselected. All 448
hashed backend inputs remained unchanged throughout that run. Subsequent
private diagnostic pin binding is separate from the frozen runtime and passed
the complete 221-test helper suite.

## Actual read-only private preparation

Resource-fenced matching v8 diagnostics reused the previously authorized,
unchanged current-question vectors. There was no embedding, source-ID or other
provider call, no credential/root configuration mount and no database write.
Each diagnostic used four CPU, two GiB, a PID-1 300-second deadline, bounded
SQL and rollback, with owned container cleanup.

Independent holdout: twelve requests prepared, four candidates each; the gold
page is in the initial candidates and pool for **12/12**. Ten wires carry only
the current question; two also carry the eligible bounded literal subject.
Hybrid artifact SHA:
`676b95a04e79ddcafef16049e6bc54566ded20885a51c67ed5cbb2affb6463bd`.

Exposed seeds and restricted-source controls: fourteen requests, fifty
candidates; **11/11** seed gold pages are in the initial candidates and pool,
with no clarification miss. Three controls are separate; the two wrong-source
slates are not assertions of corpus-wide absence. Artifact SHA:
`4e57382d8bce23aac355968a07662814a935a04b91ef1a9f516b6157d1627380`.
The new candidates must retain exact existing independent labels or receive
fresh before-outcome review. Candidate recall is not displayed-card usefulness.

## Remaining release boundary

Ask remains disabled. Matching private source-ID transfer needs a fresh exact
provider envelope after the concrete inputs and guards are frozen. Actual
selected-card usefulness, selected physical PDF opening, spoken assistive
technology, and final release evidence remain required. No public/private
release completion, hosted CI, publication or whole Lane 6 closure is claimed.
