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
