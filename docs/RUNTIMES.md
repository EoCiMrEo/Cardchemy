# Supported runtimes

This file is the source of truth for local, CI, and container runtime support.

| Component | Supported | Baseline verified for this remediation |
| --- | --- | --- |
| Node.js | 24.x | 24.21.0 reference build; 24.7.0 local |
| npm | 11.x | 11.19.1 |
| Python | 3.11 through 3.13 | 3.11.16 container target; 3.13.7 local |
| PostgreSQL | 16.x with pgvector 0.8.6 and ICU en-US UTF8 | Reviewed PostgreSQL 16.15/Alpine 3.24 recipe in `runtime-artifacts.json`; final immutable image/platform, extension, ICU, entrypoint and Unicode probes verified on disposable services |
| Docker Engine | 24 or newer | 29.8.0 |
| Docker Compose | 2.20 or newer | 5.5.1 |

## Container platform support

Published self-hosting support targets Linux/amd64 containers. Linux hosts run
them directly; supported Windows and macOS hosts run them through a current
Docker Desktop Linux-container VM. Linux/arm64 is best effort until the default
and OCR images, PostgreSQL integration suite, and browser acceptance flow are
verified on that architecture.

## Database runtime and native installation

The mandatory database runtime is the reviewed local build in
[`runtime-artifacts.json`](../runtime-artifacts.json), selected as `linux/amd64`.
The inventory pins the official PostgreSQL 16.15/Alpine 3.24 base OCI index and
platform manifest, pgvector 0.8.6 source checksum/commit, every recipe input and
the complete added compiler/runtime APK package versions. Its aggregate recipe
hash controls the local image tag and verified image label. The build compiles
with portable `OPTFLAGS=""` and omits extension LLVM bitcode; PostgreSQL's ICU
and JIT support remain. A native pinned `su-exec` replaces the upstream Go
privilege helper; a sanitized flat final filesystem contains no compiler or
removed vulnerable helper bytes. Its wrapper preserves the official entrypoint
and verifies fresh PostgreSQL16/UTF8/ICU en-US before marking the cluster.
Recipe and shell inputs enforce LF independently of host checkout conventions.

Build with `docker compose build db` or
`python scripts/runtime_database.py`. Disposable harnesses call that shared
lazy helper and start only its verified immutable local image ID. Compose
uses the recipe-hash-specific tag; a plain mutable alias is not runtime proof.
Fresh clusters use ICU en-US/UTF8. The existing data path
`postgres_data:/var/lib/postgresql/data` remains, but previous Bookworm/libc
clusters require a logical backup/restore into a **separate** fresh ICU target,
with their original volume retained. The wrapper refuses populated unmarked or
incompatible data before starting PostgreSQL. Follow
[database operations](DATABASE_OPERATIONS.md); never attach the new Alpine
runtime directly to an old operator cluster or remove its populated volume.

Native PostgreSQL 16 operators must install pgvector **0.8.6** server binaries
and extension SQL/control files on every database server before applying the new
Alembic head. Build the reviewed pgvector tag with portable compiler flags or
use a package whose installed files and extension version have been verified.
The migration role must be allowed to create the `vector` extension, or a
privileged operator must preinstall that exact extension version in the
application database's **public** schema. The migration preserves a compatible
preinstalled extension under its current owner and rejects a different version
or schema. Confirm `SELECT extversion FROM pg_extension WHERE extname
= 'vector'` after migration and after restore. The extension is mandatory even
when `RAG_ENABLED=false`; that flag controls product behavior, not schema
installation. A missing/incompatible binary or insufficient privilege is a
deployment prerequisite failure, not a reason to skip or stamp the migration.
Future PostgreSQL patch or pgvector changes require a new reviewed digest,
inventory update, disposable migration/restore rehearsal, security scan, and
SBOM. The reviewed database recipe has its own mandatory archive audit/SBOM and
input/image/configuration provenance contract. Cardchemy's current three-image
signed application release workflow does not publish or sign this database
image; no registry publication is required to build the reviewed recipe.

Use `python scripts/check_runtime_artifacts.py` for the source contract,
`python scripts/test_database_artifact.py` for the exact-image vulnerability
gate and SBOM, and `python scripts/test_pgvector_restore.py` for an isolated
populated extension/vector/lexical-index recovery probe. The latter uses fixed
synthetic three-dimensional vectors and a temporary HNSW index to exercise
extension infrastructure; it does not choose HNSW for application retrieval or
establish recovery of populated Subject Knowledge. Application schema recovery
and migration checks remain separate obligations in [testing](TESTING.md).

`python scripts/test_database_volume_upgrade.py` seeds the prior Alembic head
and synthetic learning content on a pinned Bookworm/libc reference. It proves
unmarked/wrong-marked legacy startup rejection without changing cluster control,
then logically restores into a separate ICU target. It verifies rows/head,
Unicode unique/btree/GIN behavior and the vector foundation migration/query.
Both random labeled source/target volumes survive until verification finishes;
exact ownership and final container/volume absence are checked before cleanup.
This disposable proof does not authorize migrating an operator's data.

The reference frontend build pins Node 24.21.0 for compilation and runs on an
unprivileged Nginx 1.31.6 Alpine image. The backend runtime uses Python 3.11.16 on
Alpine 3.24, runs as a non-root application user, and omits the compiler/header
toolchain used in its dependency-builder stage. Exact reference sizes and release inspection
commands are in [Deployment and self-hosting](DEPLOYMENT.md).

Reference build/runtime bases are pinned to immutable OCI index digests in the
Dockerfiles. Dependency PR #3's Python 3.14 and Node 26 suggestions are reconciled
to current patches of the supported majors; a dependency merge does not expand
the application runtime contract. The official image manifests and source
revisions were verified before pinning. Native and OCR smoke tests accompany
these patches, and hosted CI still tests Python 3.11 and 3.13.

The npm version is declared in `frontend/package.json` and explicitly installed
in the frontend Docker builder before `npm ci`; host CI and image builds use
the same lockfile resolver. Python runtime packages
are pinned with hashes in `backend/requirements*.txt`; update them only through
`backend/scripts/lock_dependencies.ps1` and verify both Python 3.11 and 3.13.
