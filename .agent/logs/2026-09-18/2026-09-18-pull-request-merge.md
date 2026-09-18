# Pull request merge and compatibility remediation

The operator requested merging all open pull requests and the completed RAG
feature into protected `main`. Starting checkout was clean at `4a5bea7`, branch
`codex/subject-rag-through-phase-13`; remote main was `e10f583`. All twelve
relevant PRs are attached to the task. No protection bypass, force push, real
database changes or paid provider requests are authorized or needed here.

PR #23 was created and hosted CI run `35374120904` passed every mandatory job
except `database-artifact`, which failed before its CycloneDX report existed.
The original harness suppressed scanner output. Bounded diagnostic capture is
now limited to public-image scanner calls, retained as ignored artifacts and
uploaded on failure. Other command output remains withheld. The vulnerability
threshold and exact-artifact identity requirements remain intact.

Independent audits found coupled frontend peers in #4–8, Passlib startup
incompatibility with bcrypt 5 in #10, platform-incorrect generated Python locks
in #9/#11, unsupported image-major changes in #3, and a superseded/conflicting
draft plan in #12. Separate ignored Git worktrees preserve the original PR
commits while preparing compatible changes. Source/runtime compatibility,
current-base checks and historical-document reconciliation are required before
the respective merges. Their outcomes will be appended as work completes.

Verification at this checkpoint: runtime contract tests passed (10 tests).
Hosted SBOM failure is unresolved; no PR has been merged at this checkpoint.
The local public-image diagnostic scan is running with a fresh advisory cache.
Operator `.env`, application volumes and private content are not mounted.

## Hosted scanner permission fix

Diagnostic run `35375383077` established the actual error: Trivy could not open
the runner-owned `/image.tar` (permission denied). A local synthetic classic
Docker archive passed, excluding archive format as the cause. The scanner's
default root identity combined with `--cap-drop ALL` cannot override the host
user's archive permissions on native Linux. The scanner now explicitly matches
the caller's POSIX UID/GID and owns private `0700` tmpfs caches under that
identity; Docker Desktop uses its Windows ACL mapping and explicit `0:0`.
Read-only root, no-new-privileges, dropped capabilities, offline scan and exact
identity/vulnerability requirements remain intact. No host modes are widened.

Both local public-image audit/SBOM runs passed with fresh advisory downloads:
`ece799f73209` (native Desktop archive) and `c2a4785ba3ea` (synthetic classic
archive). Owned scanner containers and archives were removed. Diagnostic and
host-identity contracts passed before pushing; hosted verification of this
fix is pending. No merge has occurred at this checkpoint.

Live GitHub branch protection was inspected read-only in Settings: PR flow,
`ci-required` from GitHub Actions, up-to-date branches, conversation resolution,
and no administrator bypass are enabled; force pushes/deletions are disabled.
No settings were modified. The 14 runtime/diagnostic/identity contracts pass,
CI structure passes, and context validates 37 files/65 guides/874 local links.

## Feature merge completed

PR #23 head `6c833653b88ede6a0bfd679e58f56703129fd083` passed all 13 mandatory
jobs in hosted CI run `35376050704`, including the corrected exact database
scan/SBOM gate. Dependency review passed and there were no review threads.
GitHub merged it normally into protected main at
`62796df3efd420cb140308eae4d0eec73acd13a7`, verified by the merge result and
subsequent PR metadata (`merged=true`, 2026-09-18T17:46:43Z). No protections
were bypassed. The remaining dependency and historical-plan PRs are being
prepared against that exact main revision.

## Dependency and runtime integration prepared

The remaining infrastructure integration was prepared through normal local
merges from exact protected-main commit
`94aef49feb23ac18af4abffddb197f9a509c1388` and the current heads of PR #3
(`5aea34e66fe085571dc316359a9353342d40468f`), PR #9
(`afea6f8b57f5cf9cdf4811227c5d298dd6c03014`), PR #11
(`dad178b66a0fc266a7a13a863337bcf01a079bb7`) and PR #14
(`a23bf15ee2dc9a1f7e202dc8acbe0f230512da41`). Their histories are retained;
no rebase, force push, protected-main write or branch-protection change was
used.

Lock conflicts were resolved from the direct `.in` inputs. The final graph
keeps the compatible-group upgrades, direct bcrypt 5 without Passlib, Google
GenAI 2.23, Phase 13's pgvector client, and `uvicorn[standard]`. Windows lock
generation retains the portable standard-server dependencies and does not make
Linux-only `uvloop` unconditional. Both generated hash locks were first rebuilt
from no existing output, then the canonical generator reproduced them without
a diff. The merged runtime proposal stays within the supported majors: Python
3.11.16/Alpine 3.24, Node 24.21.0/Alpine 3.24, and unprivileged Nginx 1.31.6,
all with immutable base digests. The action update retains immutable commit
pins across every current workflow and its documented provenance.

Local validation of this combined state passed:

- final development hash-lock installation on Windows;
- 73 focused password-compatibility and installed Gemini SDK transport/retry
  tests;
- the complete offline backend selection: 660 passed in 79.05 seconds, with
  78.34% combined, 81.79% line and 63.64% branch coverage, all maintained
  global and critical-module floors passing;
- a fresh strict audit of 80 Python dependencies with zero known
  vulnerabilities;
- CI/protection structure, runtime-artifact identity, and repository context
  validation (37 required files, 67 active guides, 895 local links);
- native backend, OCR backend and frontend production image builds, followed by
  their isolated no-network runtime smoke harnesses; and
- Gitleaks over 75 commits plus the isolated source-secret and all three
  HIGH/CRITICAL image vulnerability/SBOM gates.

No provider request or paid evaluation was made. PostgreSQL, Mailpit, journey
and production-rehearsal services were not repeated for this dependency-only
integration; exact current-base hosted CI remains mandatory before GitHub can
merge it. The local scanner cleaned its owned containers and snapshots and
retained only ignored reports/checksums under `artifacts/security/`.
