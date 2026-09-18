# Subject-scoped RAG foundation and Knowledge schema continuation

Scope: complete the authorized plan through Phase 13. Preparation A/B acceptance
and evidence remain in the [earlier implementation record](../2026-09-17/2026-09-17-rag-through-phase-13-implementation.md).
Phases 14–21, paid provider calls and production enablement are outside this
implementation endpoint. Checkboxes require actual implementation/verification.

## Starting context and preservation

Resumed 2026-09-18 on `codex/subject-rag-through-phase-13`, based on
`e10f5839735379e4277d35600067835f53272a89`. The existing substantial working tree,
historical log moves, untracked approved plan and authored artifacts were
preserved. No real root `.env` was read or rewritten; no installation keys,
populated volumes or used migrations were changed. The previous agents were
inactive, so bounded runtime/security/recovery, consumer verification and
schema assignments resumed from their saved work instead of restarting it.

Read/reused root AGENTS, canonical orientation, source/maps/ADRs/domain guides
and relevant dated logs from the ongoing task. Applied the installed PostgreSQL
best-practices skill for foreign-key prefix indexes and consistent lock ordering.
No Supabase service or replacement queue/persistence architecture is introduced.

## Approved contract and current work

G1/G2/G4/G6 choices and delegated G5 model selection remain in ADR-012. The
review/publication boundary belongs to an immutable content revision; staged
index revisions can change chunker/embedding identity without granting approval
to changed content. Every retained private/staged/failed revision counts against
bounded permanent capacity. Trigger-backed reservations protect direct database
inserts as well as future service writes. Knowledge upload/indexing/retrieval/
chat/API/UI execution remains assigned to later phases.

The pinned PG16/pgvector runtime, Python integration/hash locks, unconditional
0009 extension migration and portable offline vector type are saved. Initial
disposable service attempts reached migration head/no drift but did not execute
tests because of importlib and duplicate-basename collection errors. The
importlib loader is fixed; the PG vector test was renamed to
`test_postgres_vector_foundation.py`. Those aborted attempts are not passing
service evidence.

Docker Desktop was absent on resume (no process/engine pipe). It was launched
hidden through approved local execution to run authorized disposable tests.
This starts the existing engine; it does not delete or replace operator data.
The runtime security scan previously failed before scanning because a 1GiB
ephemeral cache could not hold the fresh advisory database. That cache failure
is not a vulnerability result. A larger isolated cache is being used for the
actual scan/SBOM. The synthetic infrastructure dump/restore harness is separate
from later actual Knowledge-table recovery proof.

Updated privacy guidance before capture writes: persistent text/vector transfer,
separate publication, own-message 90-day retention, stored-answer hiding on
unpublication/deletion/replacement, consistent-snapshot export ownership and
writer-fenced deletion prerequisites. Updated migration guide for mandatory
PG16/pgvector, admin preinstallation/privileges and shared-extension-safe
downgrade. This design documentation does not claim future exporter/chat/write
paths have already been implemented.

## Verification and limits

Current resumed checks: authored corpus identity/eligible-positive validation
passed (8 queries, 4 invalid citations); targeted vector/harness checks passed
(16); runtime/harness/rehearsal guards passed (66); runtime identity drift
tests passed (7); context validation passed (37 required files, 65 guides,
843 local links; later runtime-owned check reported 849 links). Structural
CI/actionlint checks passed. These do not establish real service or image
security success.

Docker Desktop processes started, and `docker desktop start --timeout 45`
reported already running. Its Linux engine pipe is still absent, and the
Docker WSL distribution is not running. Read-only status/engine CLI calls did
not return a usable state promptly. No repeated restart, settings mutation,
WSL reset or volume removal was attempted. The required 0009 service suite,
RAG-off journey and fresh dump/restore remain blocked by engine startup. Actual
privilege/schema/catalog installation tests are saved in guarded disposable
child-database tests, but unrun while the engine is unavailable. The schema
agent held0010 and restored its model additions to the pre0010 baseline to
avoid contaminating Phase 12's head/drift gate. The public image scan can use
an independently checksum-verified official Trivy binary without the daemon;
its result will be recorded separately when obtained.

The operator subsequently reported "docker started. Continue". A fresh
read-only daemon version check succeeded (Docker Engine 29.8.0), and disposable
service/recovery verification resumed. No Docker settings/volumes were changed
by that check. The earlier engine failures remain non-evidence; final passing
results will supersede them below. Phase 13 draft model/migration files were
held outside the active migration chain until the 0009 gate; the active
Subject/GenerationJob/model-export files had no Phase 13 changes at that boundary.

Fresh checks and final checkbox outcomes will be appended after completion.

Phase 12's actual `0009` disposable PostgreSQL gate passed: 42 passed, 3 skipped,
630 deselected in 34.40 seconds. Fresh upgrade/head/drift and full downgrade to
base/re-upgrade/head/drift passed. Seven real foundation contracts cover exact
PG16/extension schema/version/cosine, SQLAlchemy 1536-vector asyncpg list binding,
compatible preinstalled extension without CREATE, denied installation with and
without CREATE privilege, wrong-schema extension, and explicitly injected old
installed-version catalog metadata. The latter does not test older binaries.
Child databases/NOLOGIN test roles and owned parent test containers/generated
credentials were removed; the harness confirmed owned-container absence.

The hardened synthetic infrastructure dump/restore also passed in 7.07 seconds:
pgvector 0.8.6, two rows, vector ordering, valid synthetic HNSW+GIN indexes and
lexical query survived custom-format restore into a second isolated no-network
tmpfs database. Both owned containers were proven absent after cleanup. Its
3-dimensional table proves infrastructure only; actual 1536-dimensional
Knowledge-table recovery and previous vanilla PG16 volume compatibility remain
separate tests.
RAG-off journey and the fresh external-image security/SBOM scan are still
running; Phase 12 is not yet fully closed.

Subsequent results: the RAG-off deterministic journey passed its database proof
and browser contract (exit 0), with final owned-resource cleanup confirmed.
The sole fresh security scan used the official Trivy 0.70.0 Windows release,
whose archive matched the official SHA256 checksum
`eea5442eab86f9e26cd718d7618d43899e72a83767619e8bee47911bddbfb825`.
The exact proposed external pgvector image **failed**, with 118 HIGH/CRITICAL
findings including unfixed issues. CycloneDX generation passed; ignored
`artifacts/database-artifact/remote-118b6e491a49/` holds the public-image audit,
SBOM, identity and checksums. A failed audit is not readiness evidence. No
threshold, scanner scope or unfixed-vulnerability policy was weakened.

The runtime agent is evaluating a safe reviewed PG16/pgvector 0.8.6 image or
portable custom build, as allowed by the plan. Existing-volume compatibility
is being rehearsed only on a randomly named, labeled synthetic test volume.
The successful service/journey results above establish the rejected candidate's
functional behavior; the supported replacement requires fresh verification.
Phase 12 remains open and Phase 13 application remains held.

Independent Phase 13 draft review identified revision reopening, fabricated
actual counters/readiness at INSERT and broad lock triggers that could invert
with existing worker row locks. These are being fixed before application;
captured content/index identity must stay immutable, counters must initialize
and change only through guarded rows, and unrelated auth/generation changes
must not acquire a later global mutex behind an existing worker row lock.

Fresh strict Python dependency audit of the complete hashed development lock
passed with no known vulnerabilities. Its public-package report is retained
under ignored `artifacts/dependency-audit/python-audit.json`, not as an
untracked backend source file. The official Trixie pgvector candidate also
failed the unchanged HIGH/CRITICAL gate (148 findings); its public audit/SBOM
remain in ignored candidate artifacts. No reviewed candidate has yet passed
the DB image security gate.

An approved portable custom-build path is being evaluated: immutable official
PostgreSQL 16.15 Alpine base, checksum-pinned pgvector 0.8.6 source, locked build
dependencies and replacement of the embedded Go user-switch binary with native
`su-exec`. Final artifact consumers must verify one recipe/source/base identity
and the resulting image/platform. Previous Bookworm data uses glibc locales;
the musl replacement must either prove compatibility or require a tested
logical restore into a separate target while preserving the old volume. Same
data-directory spelling alone is insufficient. Final support claims wait for
those actual checks.
Existing A/B evidence includes offline backend/frontend, synthetic Compose
isolation and deterministic browser/API/database proof. No paid calls, real
SMTP, deployment, commit, push or merge is authorized by a configured credential.

The final label-bearing custom database recipe subsequently passed the actual
fresh-advisory Trivy 0.70.0 HIGH/CRITICAL gate with zero findings, including
unfixed vulnerabilities, and produced a CycloneDX SBOM. Proof is retained in
ignored `artifacts/database-artifact/custom-fb566f7f1368/`. Its immutable local
Docker identity is
`sha256:69f927d5831c2a6fad0129edead0b9fc8c1c32d9971663806324994ba48b1ef4`;
the exported archive's configuration digest is separately verified against
Trivy metadata, because Docker 29's containerd OCI identity is not the image
configuration digest. Earlier failed candidates remain failed evidence.

The reviewed recipe uses an immutable official PostgreSQL 16.15 Alpine base,
checksum-verified pgvector 0.8.6 source, exact build-package versions and portable
compiler flags. Its sanitized root filesystem replaces the vulnerable embedded
Go user-switch binary with native `su-exec`; a scratch final stage contains no
discarded Go binary or compiler layers. Source identity, final image/platform,
extension control files, ICU support and user-switch UID/GID/supplementary
groups/arguments/empty argument/environment were checked. The exact-source
consumer service/journey, prior-Bookworm logical recovery and official
entrypoint/Unicode checks still precede final Phase 12 acceptance.

Final-recipe functionality then passed: PostgreSQL `0009` suite 42 passed,
three gated skips, 630 deselected in 47.00 seconds, including initial upgrade,
head/drift, full base downgrade/re-upgrade and repeated head/drift. The RAG-off
deterministic journey's database proof and browser contract also passed.
Both harnesses confirmed absence of their owned services/processes/data and
generated credentials after cleanup. An independent actual-image probe verified
PostgreSQL UID/GID 70, ICU `en-US` UTF-8, Unicode uniqueness/order, valid btree/GIN
lexical behavior, PostgreSQL 16.15 and pgvector 0.8.6; its cleanup inventory
passed. No operator input is needed for the remaining disposable recovery and
source/CI checks. These passes supersede the rejected candidate only for the
same functional checks; final Phase 12 closure still waits for those remaining
prerequisites.

Final Phase 12 evidence on the guarded, aggregate-recipe-hash-specific build:
`scripts/check_runtime_artifacts.py` and `scripts/check_ci.py` passed. The final
immutable database identity was
`sha256:6e8e738c2aac135016c2411f526f0e656d65ea78498e641604d43d1c127bbdd2`;
ignored `artifacts/database-artifact/custom-f95a19657a03/` records a fresh
Trivy 0.70.0 zero-HIGH/CRITICAL scan, CycloneDX SBOM, recipe/input, archive,
configuration and inventory identities. The exact guarded image passed vector
infrastructure dump/restore, 42 PostgreSQL tests plus three gated skips,
base downgrade/re-upgrade/head/drift, and the deterministic RAG-off browser/API
journey. The separate legacy Bookworm/libc volume rehearsal refused both
unmarked and wrong-marked data without changing cluster control, logically
restored synthetic learning/Unicode/index data into a separate ICU target,
upgraded to `0009`, and removed only its labeled test containers/volumes.

After these Phase 12 prerequisites passed, the held Phase 13 draft was applied
as new head `20260918_0010`. It adds private Subject Knowledge documents,
canonical pages, independent content/index revisions, 1,536-dimensional
chunks/embedding spaces, guarded count/byte reservations, eligible-record
publication predicates and durable indexing jobs. Generation-job/document
association is authoritative; sets have optional navigation links, and
document deletion detaches them while preserving cards. No upload/index
execution, retrieval, chat or Ask AI API was introduced in this scope.
Focused offline Knowledge/privacy/generation/authorization tests: 36 passed.
First Phase 13 PostgreSQL gate: 65 passed, three gated skips, 633 deselected,
with full base downgrade/re-upgrade/head/drift. After adding an owned-child-DB
populated Knowledge dump/restore contract, the gate passed 66 tests, three
gated skips and 633 deselected in 56.08 seconds, including actual 1,536-vector,
empty original page, eligibility/index/counter/link/deletion checks.
Full offline backend: 620 passed, 81 service-gated skips, one live-AI
deselection. Mailpit: three passed. Encrypted SMTP/recovery: 12 passed.
Deterministic RAG-off browser/API/worker journey passed at head `0010` and
confirmed owned-resource cleanup. Built non-OCR backend and frontend runtime
smoke probes passed; optional OCR build/smoke, image security and final context
checks remain to record below.

The operator explicitly authorized deletion of a legacy volume and creation of
a new one. Inspection identified only the exited Compose database container
`flashcardgenerator-db-1` mounting the Compose-labeled
`flashcardgenerator_postgres_data` volume. That container and volume were
removed, then the same named fresh volume was created with the project's
`postgres_data` Compose labels. Inspection confirmed no container mounted it.
Other project containers, Mailpit volume, other projects and real root `.env`
were untouched. The fresh operator volume remains empty; isolated tests did
not use it. Actual deployment/cutover is separate from this test evidence.

## Final verification and local configuration closure

The pending OCR backend build/smoke passed, completing the non-OCR backend,
OCR backend and frontend image smoke set. The exact final database image was
rebuilt and verified by `scripts/test_database_artifact.py` with its aggregate
recipe hash, immutable local image ID
`sha256:6e8e738c2aac135016c2411f526f0e656d65ea78498e641604d43d1c127bbdd2`,
fresh-advisory zero HIGH/CRITICAL findings including unfixed findings, and a
CycloneDX SBOM. The final CI-equivalent ignored record is
`artifacts/database-artifact/4ea0b2caca48/`. Earlier candidate failures do
not count as passing evidence.

At `0010`, `scripts/test_security.py --image-tag rag-13` passed the worktree/
history secret gates and the three application image vulnerability/SBOM gates.
The offline exact CI coverage invocation passed 620 tests with 82 deselections,
77.90% overall coverage against 73%, 81.49% line against 77%, 62.57% branch
against 55%, and all critical-file floors. `scripts/check_ci.py`, runtime
artifact validation, 14 script tests, and `scripts/check_context.py` passed;
the final context report counted 37 required files, 65 guides and 873 active
local links. This supersedes the earlier pending-check statement above.
The complete frontend `npm run check` passed after Preparation B; no frontend
implementation changed in Phases 12–13. No hosted CI, paid AI, real SMTP,
application deployment or real-user Knowledge writes were claimed.

The operator then explicitly authorized editing variable names in the private
root `.env`. A name-only inspection found ten legacy assignment lines. Nine
were renamed to `FLASHCARD_AI_*` with their values and other bytes preserved;
the empty `GEMINI_API_KEY` fallback line was removed to avoid a duplicate key.
No credential value was printed, logged or changed. `scripts/check_config_migration.py`
passed; `docker compose config --quiet` returned success with a local Docker CLI
config-file access warning from the sandbox. Direct validation of the private
root configuration passed, and the generation-worker readiness guard returned
its expected fixed, value-free missing-bucket error. The active flashcard
provider flag is true, RAG is false, and no flashcard quota-bucket label is
configured; the new generation worker would reject startup until that
non-secret account/project label is supplied. The operator was asked for the
label and any shared-capacity limits. No provider work or app process was
started against the fresh volume.
