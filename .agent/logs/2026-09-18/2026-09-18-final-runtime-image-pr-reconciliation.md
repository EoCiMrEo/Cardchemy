# Final runtime-image pull request reconciliation

Date: 2026-09-18

## Scope and starting state

The operator requested merging all open pull requests and the Subject-scoped
RAG feature branch into protected `main`. PR #24 was the final open pull request
after the feature, historical-plan, frontend, password, backend, AI, Actions,
and compatible runtime changes merged normally. Its Dependabot head was
`4d871b06b2f6333ba2b7939c1af06bbd8ff302b6`; protected main was
`4ce06e0` when this reconciliation started. The worktree was clean. Root
instructions, current runtime/dependency guidance and the existing dated merge
log governed this follow-up; the real root `.env`, data and volumes were left
untouched.

## Decision and changes

PR #24 proposed Node 26.3.0 on Alpine 3.22 and Nginx 1.31.5 via mutable tags.
The just-merged runtime integration supports Node 24.21.0 on Alpine 3.24 and
Nginx 1.31.6 with immutable digests. Applying #24's Dockerfile after that
integration would move beyond the documented Node major and regress the Nginx
version and image identity. No product or runtime change was needed.

In an isolated worktree, a normal merge brought exact protected main into the
Dependabot branch. The single `frontend/Dockerfile` conflict was resolved to
the tested main file byte-for-byte. Merge commit `b85b169` retains the original
Dependabot commit and all main commits in ancestry without rewriting either.
This dated log and index provide the sole effective branch diff, explaining why
the historical proposal is superseded. The pull request must still pass its
current-base hosted checks and merge under the existing branch protection.

## Verification and limits

The combined branch is prepared for the repository's context, CI-structure and
diff checks. Hosted CI and final GitHub merge are pending at this checkpoint.
No paid model call, provider request, production deployment, database
migration, secret inspection or volume operation was performed for this PR.

## Dependabot replacement and final policy

While this reconciliation was being prepared, Dependabot marked #24 obsolete,
closed it without a merge and deleted its branch. Dependabot immediately opened
replacement PR #25 at `312fbb8fb5450fb3450691e4c48ac68cc27162ad`. It
proposes changing only the frontend build stage from pinned Node 24.21.0 to
pinned Node 26.8.2; current `docs/RUNTIMES.md` supports Node 24.x. The earlier
push recreated #24's deleted branch, but did not reopen or change that closed
PR. Its commits remain isolated and must be cleaned up after final merge.

The #25 head was normally merged into this isolated branch with merge commit
`9c42bce`, preserving the Dependabot commit in ancestry and resolving the
resulting Dockerfile to exact protected-main Node 24 bytes. The effective
runtime remains unchanged. The Docker `dependabot.yml` entry now ignores only
major `node` version updates; minor and patch releases, other Docker images,
and security updates remain eligible. [GitHub's Dependabot options reference](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)
documents `dependency-name` plus `version-update:semver-major` in `ignore`.
This prevents another automatic unsupported-major replacement PR while a future
Node-major upgrade can be planned, verified and explicitly supported.

The #25 branch must pass context/CI structure checks locally and all
current-base hosted checks before its protected merge. No Node 26 runtime
claims or live-provider claims result from this reconciliation.
