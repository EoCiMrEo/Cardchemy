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
