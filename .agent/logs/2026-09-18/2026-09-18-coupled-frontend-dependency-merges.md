# Coupled frontend dependency PR remediation

Date: 2026-09-18. Scope: user-authorized merge of all open PRs and the completed
Subject RAG feature into protected main. This record covers PRs #4–8 only.

## Starting context and preservation

The isolated worktree began clean on PR #4's original
`f712e8271b27f1794451bbe3eb4beeb4a4d5ad4a` head. Read root engineering guidance,
canonical orientation/map, frontend MOC, relevant architecture/runtime/dependency
and testing guides, agent governance and relevant dated evidence. No operator
`.env`, credentials, provider quota, private content, database or volume changed.
Applied the React review skill and verified official Vite, Vitest, ESLint and
React migration/fetching guidance against the affected source.

Normal merges preserve the feature head `4a5bea7`, the original dependency heads
below, and protected main through `f32a1c8` (including hosted scan ownership
remediation and historical plan reconciliation). No history rewrites, forced
peer installs or protected-branch bypasses were used. Local commits are handed
to the coordinating task; this worktree does not push or merge GitHub PRs.

| PR | Original head | Concrete failure |
| --- | --- | --- |
| #4 | `f712e8271b27f1794451bbe3eb4beeb4a4d5ad4a` | New hooks lint rule found synchronous loading/reset state inside effects. |
| #5 | `47b79c9f17c2ab3be817705816e1dfe1a2a952f4` | `@eslint/js` 10 paired with ESLint 9 in the frontend image's npm resolver. |
| #6 | `af242174754d01fbfbd6c08a28bcc48edbe23cb0` | React Vite plugin 6 requires Vite 8. |
| #7 | `bc3894084de5624bae5787e3af4759e83de2b184` | Vite 8 unsupported by the old Tailwind Vite plugin's peer range. |
| #8 | `2136b24ad6b7de3d435a87af75b997c86de24642` | Coverage 5 requires the matching exact Vitest 5 version. |

## Changes and rationale

- Combined ESLint/js 10, Vite 8.3/React plugin 6.1.1/Tailwind plugin 4.3.3 and
  exact Vitest/coverage 5.0.0. Regenerated one consistent lock using verified
  npm 11.19.1; the Docker builder explicitly uses that resolver too.
- Initial loading comes from state; route loading derives from completed keys;
  retry/mutation events enter loading explicitly. Data loaders write state only
  in promise completion callbacks, pass abort signals and ignore canceled
  responses. An initial `async` callback refactor still triggered the new lint
  analysis despite awaited writes; explicit promise callbacks pass without new
  rule suppression. Dashboard/auth operation fencing remains intact.
- Instructor Subject/set forms and student Subject/session content remount for
  changed route scope, including return navigation. Study countdown starts from
  its card's initialized limit; timers still clean up, and click/timeout/retry
  share the existing durable, idempotent answer submission.
- Generation jobs/limits are displayed only in their loaded Subject scope.
  A failed new poll removes previous-Subject jobs; delayed retry/cancel responses
  cannot add jobs outside the current scope. Completion refreshes are abortable.
- Meaningful component regressions exercise immediate loading, late canceled
  Subject/session transports, Redux session fencing, failed new-Subject polls,
  old retry completions and cancellation of old polling. Existing durable
  answer, timeout/retry, auth and accessibility gates remain enabled.
- Updated frontend MOC, runtime/dependency/test/CI guides and changelog.

## Verification and limits

- Node 24.7.0; verified npm 11.19.1. Clean `npm ci`: 354 packages, zero audit
  vulnerabilities, no peer overrides.
- Exact npm 11.19.1 clean install passed: 354 packages installed, 355 audited,
  zero vulnerabilities and no peer override. The first full-gate attempt stopped
  at lint because a temporary Corepack download had been placed under
  `frontend/`; moving that tool cache outside the lint scope resolved the
  harness-only problem without changing source or rules.
- Full `npm run check` with npm 11.19.1 passed: all TypeScript configurations,
  ESLint 10, four Node units, 31 component tests, coverage (96.65% statements,
  85.16% branches, 93.10% functions and 97.84% lines), the Vite 8.3.0
  production build and 53 maintained Chromium cases. The separately gated live
  password-reset case was the one expected skip.
- Final frontend Docker build passed. Local immutable OCI index:
  `sha256:1a7cd7da2e176af91869a8ea44145882a0b1f9c11aea27dffe8fdd3c030b867a`.
  The image configuration digest is a distinct identity; an initial attempt to
  run that digest correctly failed lookup, then inspected OCI identity passed.
- Exact-image Nginx smoke passed UID 101, config, health/index/assets, PNG/ICO,
  missing-brand 404, security/cache headers and private-target redaction; its
  generated probe container was removed by the harness.
- The first offline journey invocation used an unprepared system Python and
  stopped before application startup because Alembic was absent. Its guarded
  cleanup completed. The rerun with the repository Python 3.13 development
  environment passed migration, generation, review, publication, enrollment,
  invitation email, durable answer/progress proof and browser contracts; all
  generated processes, containers, data, fixture and credentials were removed.
- Workflow/context contracts passed before this final log update; the final
  current-main rerun is recorded below after integration.
- Exact-image vulnerability/SBOM review is coordinated separately by the image
  audit subagent; hosted current-base CI and remote merge remain the parent
  task's responsibility. No paid AI, production delivery or deployment claim.

## Sources

- [Vite migration](https://vite.dev/guide/migration.html)
- [Vitest migration](https://vitest.dev/guide/migration/)
- [ESLint 10 migration](https://eslint.org/docs/latest/use/migrate-to-10.0.0)
- [React fetching and effect cleanup](https://react.dev/reference/react/useEffect)
