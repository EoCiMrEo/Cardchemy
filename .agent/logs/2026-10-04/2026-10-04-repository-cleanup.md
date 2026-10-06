# Repository cleanup and fresh-clone verification

## Scope and starting context

The owner authorized repository cleanup, domain-based documentation folders,
retirement of the two engineering plans and removal of stale implementation
versions and experiments, with full-stack fresh-clone verification. Starting
`main` was clean at `61b34ebda127b712bf22e36f84fb393f1343f707`; work is on
`codex/repository-cleanup`. No unrelated work needed to be moved or reset.

Orientation covered AGENTS, Start Here, project/module maps, current architecture,
ADRs 023/024, current state/roadmap, agent governance, the final Lane 6 activation
record and the subsequent source-publication record. Three bounded independent
audits covered runtime dependencies, documentation ownership and experimental
tool/test consumers. Historical logs and migrations remain evidence, rather than
being treated as the current runtime specification.

## Cleanup decisions and preservation

- Consolidate released source-only Ask behavior into descriptive unversioned
  modules. Filename predecessors were actual import dependencies; current logic
  must be flattened before deleting them. Persisted policy/contract identifiers,
  historical read paths, failure fences and Alembic revisions remain immutable.
- Retire consumed one-use public/private trials and obsolete experimental
  verifier/ranker scripts with their paired tooling tests and unused fixtures.
  Runtime, Compose, image, CI and retained Python consumers were audited first.
  Historical source is recoverable from starting commit `61b34eb`; old trial
  receipts, charges, approvals and dated log bodies are not rewritten.
- Move 26 root guides into `ai`, `ci-cd`, `mail-server`, `operations`, `security`,
  `database`, `ui` and `development`; keep orientation and the guide index at
  `docs/`. Archive both requested plans with retirement banners and historical
  references. Maintain current contracts rather than repeated dated prefixes.
- Archive retirement does not complete adjacent work. The product-quality
  tracker's Lane 7 status and missing item-detail discrepancy are retained in
  the maintained roadmap; no unchecked task is silently marked complete.
- Preserve the operator root `.env`, database volumes/backups, original PDFs,
  history, optional runtime flags, provider/credential boundaries and budgets.
  A private content-free hash baseline records root configuration and all 35
  migration/configuration files. No paid-provider evaluation is authorized or
  necessary for this cleanup.

## Verification

The following checks passed on the cleanup candidate. Python commands used
`backend/venv/Scripts/python.exe`; service tests used generated disposable
settings, databases and credentials rather than the operator configuration.

| Check | Actual result |
| --- | --- |
| Backend offline coverage, Python 3.13.7 | 1,740 passed, 268 service/live cases deselected, 202.14 seconds; 111 fixture/resource warnings, no failures |
| Clean Python 3.11.16 Linux dependencies and offline suite | Hashed lock install and `pip check` passed; `numpy`, `onnxruntime` and `tokenizers` absent; networkless container: 1,740 passed, 268 deselected, 180.35 seconds |
| `scripts/check_coverage.py` on both reports | All unchanged global and critical-file floors passed. Python 3.13: 75.95% combined, 79.68% lines, 61.50% branches; Python 3.11: 75.94%, 79.67%, 61.47% |
| `scripts/test_services.py postgres` | 251 passed, 3 Mailpit cases skipped in this PostgreSQL-only run; disposable head/drift and full downgrade/base/re-upgrade checks passed |
| `scripts/test_services.py mailpit` | The 3 separate Mailpit integration cases passed; owned services and generated credential file removed |
| `scripts/test_journey.py` | Both deterministic RAG-off and RAG-on browser journeys passed, including generation, Knowledge/indexing, approval/publication, source-PDF Ask, invitation/enrollment, email and study |
| Frontend `npm run check -- --workers=2` | Types, lint, 6 Node tests, 85 component tests with coverage, production build and 84 Chromium tests passed; 1 separately opted-in live password-reset case skipped |
| `scripts/check_bundle.mjs` | Unchanged budgets passed: 123,457 initial gzip, 756,476 total gzip and 1,265,413 largest raw JavaScript bytes |
| `scripts/check_images.py` | Fresh backend, frontend and optional OCR images passed native imports/workers, PDF/page rendering, frontend routing/security and OCR smoke checks without provider credentials |
| `scripts/test_security.py --image-tag cleanup-df234d3648c4` | Candidate Git/worktree secret gates and all three exact-image vulnerability gates passed; SBOMs, checksums and scanner/image identities retained |
| Original Git history Gitleaks | 95 commits scanned, no leaks; read-only, redacted, networkless scan of an owned bare history export |
| Context/CI/release/notices | Final `check_context.py`: 37 required files, 85 active guides, 1,594 local links; `check_ci.py`, `check_release.py --version 0.1.0`, `prepare_release_notices.py --check` and normal `git diff --check` passed |

Independent runtime review retained nine AST-equivalent worker/provider functions
after canonical identifier changes, current access/context/lease rechecks,
source-ID-only output and no automatic retries. The runtime and tooling audits
also passed 535 and 123 targeted tests respectively. Final retained-Python AST
inspection, including `ImportFrom` aliases, found zero imports of the 17 deleted
application modules. Final backend collection passed: 2,006 of 2,008 cases,
with the 2 paid AI cases excluded by the normal default. A separate byte check
matched all 228 final application/test/lock/coverage-config files against the
clean Python 3.11 test image. Current migration/fence tests remain necessary for old data;
versioned database identities are not stale filenames.

## Fresh-clone full-stack proof

An ignored bounded harness exported only the 934 Git-visible candidate files,
created a temporary local Git snapshot and used `git clone --no-local` into a
separate directory. All file hashes matched before bootstrap. This tests the
unpublished cleanup candidate, not a claim that remote `main` already includes it.
The clone received only normal root configuration bootstrap, independent test
secrets and loopback ports; no application source edits or Compose override.

The unchanged base stack command was:

```powershell
docker compose --project-name cardchemy-cleanup-df234d3648c4 up -d --build --wait --wait-timeout 240
```

All eight services became healthy: PostgreSQL, API, generation worker, index
worker, answer worker, email worker, Mailpit and frontend. Migration exited 0.
Alembic current-head and no-drift checks, Nginx SPA and API readiness passed.
The harness provisioned a synthetic instructor with the supported CLI, created
and published a valid four-option card, registered an invited student, and
verified server-derived correct grading/quality 5 and idempotent answer replay.
Git status and source hashes stayed clean throughout the clone run.

Snapshot `c3700226498beccda9dbd92c161d2d1065cb959f` had manifest SHA-256
`2ae5a72d2b5eac4fd0d1c229fc525f42a15b7dff4d8b21230a6d73147c865dd1`.
The tested backend image was
`sha256:2eb27885a6b0e9647b4373485e2086f75be0d5b2f5682f55643a6fdbcabfc362`;
frontend was
`sha256:e996bb35cff2c8a23ed6a7b07453b484a024ebd8bea8ecab989949c8b51d0baf`.
Subsequent final edits affect the historical-v4 regression and documentation/
evidence only; application, dependencies and build inputs remain byte-identical
to the tested snapshot. Fresh installation Ask flags retain their default-off
behavior; the retained operator installation configuration was not changed.

## Failures investigated and corrected

- Initial collection exposed four stale test consumers of retired modules/
  tooling, including imports expressed through `ImportFrom` aliases. Retired
  the paired consumed-experiment tests after consumer inspection, widened the
  static audit and repeated full collection/services/offline suites successfully.
- Both initial full offline runs reported eight failures in one historical-v4
  execution test. That test forcibly reopened an obsolete contract. Replaced
  its eight old execution scenarios with one historical-read/fence regression:
  zero claim/provider/stage/reference/result, immutable old snapshot, readable
  authorized history and rejected retry. Current visual selection, provenance,
  timeout and fallback tests were retained. No runtime fence was weakened;
  final full suites pass on both Python versions.
- One first PostgreSQL run had an image-identity assertion failure while fresh
  Compose was concurrently rebuilding the shared database recipe tag. A
  bounded immutable-image probe passed; current tag labels established the
  Compose rebuild. Concurrent tag replacement is the supported explanation,
  but redacted first-run output did not retain both original image IDs. The
  complete serial rerun passed 251 cases without changing the image guard,
  database recipe or migrations.
- First fresh-stack run reached healthy services and valid heads, then the
  synthetic instructor address ending in `example.invalid` was rejected by
  EmailStr. Corrected only the disposable harness address to `example.com` and
  repeated a fresh untouched clone successfully. The failed receipt is retained.
- A final Python 3.11 successor Dockerfile initially used a digest
  directly in `FROM`, which Docker interpreted as a registry name. Used the
  verified local task image tag instead; the offline run then passed. Dependency
  and application bytes did not change.
- A final collection command was first invoked from root instead of the
  documented `backend` directory and failed collection. Repeated from `backend`
  with bytecode/cache writing disabled; the final collection passed.

## Result, cleanup and limits

Git-visible files decreased from 1,299 to 934. Seventeen application predecessor/
unused modules and 196 consumed experimental scripts were removed. The five
current source/context/provider implementations now have canonical unversioned
paths, linked from [backend MOC](../../../backend/MOC.md). Unused paired tests/
fixtures were retired while migration, current runtime and historical-data
fence coverage remain. The old local-verifier execution modules and installer
were removed; three obsolete direct development dependencies and nine resolved
packages were removed through normal hashed-lock regeneration. Production
requirements and their pins did not change. Historical legal attribution stays
because retained notices/ADRs still reference it.

The [guide index](../../../docs/README.md), eight domain indexes, project/module
maps, relevant architecture/ADRs, current state, roadmap, command consumers and
changelog reflect the layout. Both requested plans are in the archive. Lane 7's
unresolved historical scope is preserved on the roadmap rather than implemented
or declared complete during cleanup.

Final hash comparison passed for the unchanged operator `.env` and all 35
Alembic/configuration files. No operator database, volume, backup or private
evaluation receipt was deleted. Owned Compose containers/networks/volumes,
generated clone credentials, clone/export/bare-history directories, Linux test
context/images, temporary native test directories and one-use cleanup helpers
were removed after receipt copies were verified. Existing Docker images/volumes
and shared build caches were preserved. Sixteen regenerable source Python cache
directories and the pytest caches were cleared after verification; the virtual
environment and existing private verification artifacts were preserved.
Content-free receipts and security
reports remain ignored under `.agent/.verification/repository-cleanup/`; the
durable record is this log and its index entry. Historical log bodies are intact.

No paid provider call, hosted CI, remote push/merge, deployment, version release
or new manual spoken assistive-technology review was performed. Changes remain
reviewable on `codex/repository-cleanup`. These limitations do not replace the
passing local/offline/disposable/fresh-clone evidence above.
