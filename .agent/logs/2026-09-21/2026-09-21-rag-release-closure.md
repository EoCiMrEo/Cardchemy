# RAG Phase 20/21 release closure

Date: 2026-09-21

## Scope and starting context

This record closes the operator-owned rollout decisions and captures the final
protected-main evidence for the Subject-scoped RAG implementation plan. Work
started from branch `codex/rag-phase20-21-closure` at commit `6908c64`, with PR
#35 open and its exact head already passing all required hosted checks. Dependabot
PR #34 was also open. The working tree was clean; the root `.env`, existing data
and unrelated work were preserved. No secret values or private content are
recorded here.

## Operator decisions and authorization

- The operator explicitly authorized merging PR #35 and closing PR #34.
- Cardchemy has no centralized production deployment. Users clone the repository
  and run the production-shaped Docker stack as self-hosted operators.
- Each installation remains responsible for its applicable evaluation/operator
  gates and the documented reversible RAG disable/drain procedure. This decision
  does not imply that a centrally operated production service exists.
- The operator reported the release-specific Windows/browser/Narrator validation
  as passed. Exact operating-system, browser and assistive-technology version
  identifiers were not supplied and are not inferred.

## Evidence already established before merge

- Backend offline suite: 748 passed, 98 deselected, with all configured coverage
  floors met.
- Frontend `npm run check`: type checks, lint, units, components, coverage, build
  and 56 Chromium browser tests passed; one explicitly gated test remained a
  non-evidence skip.
- Disposable PostgreSQL/service, RAG-off/RAG-on journey, Mailpit, authenticated
  TLS SMTP, populated pgvector/restore, runtime-image, dependency and zero
  HIGH/CRITICAL image-security gates passed.
- Separately authorized bounded live Gemini flashcard and Subject RAG evaluations
  passed with zero application retries.
- An exact `docker compose up -d` start from the pushed branch in an isolated fresh
  clone completed with migration exit zero, all eight long-running services
  healthy and routed `/healthz` HTTP 200.
- PR #35 commit `6908c64` passed the complete hosted Linux CI and dependency-review
  checks and was reported mergeable before the operator authorized the merge.

## Final protected-main closure

- PR #35 was merged through the protected GitHub flow as merge commit
  `5eb84b2b948d916a60b026a148e31c1be1afb669`; that commit contains exact tested
  head `ed749515297e8055c75465ecc97f944f8b0615a7`.
- PR #34 was closed without merging. Its remote branch was not deleted.
- A new isolated clone of protected `main` at `5eb84b2` bootstrapped generated
  secrets without printing them. Exact `docker compose up -d` exited zero,
  migration exited zero, all eight long-running services became healthy, routed
  `/healthz` returned HTTP 200, and `git status --short` remained empty.
- Production recovery rehearsal run #6 targeted exact `main` commit `5eb84b2`
  but failed in 10 seconds at its production-profile Compose configuration gate.
  This failure is recorded as evidence against closure, not hidden by the otherwise
  successful clean-clone start.

## Hosted Compose compatibility failure and remediation

The rehearsal runner reported Docker Compose 2.38.2. The production-profile
configuration validated under the local Compose 5.5.1 but failed on 2.38.2 because
that version eagerly evaluated the nested `CARDCH_LEGACY_AI_CONFIGURATION_ERROR`
expression even when no removed AI key was present. The fixed failure category
was `compose_config:command_failed`; no credentials or configuration values were
printed.

The failure was reproduced with Docker's official Compose 2.38.2 Windows binary,
verified against published SHA-256
`ba8f09d3873f7a9755b863ed2013a1276b96fcbbc074c69ff3d3cfbce3e0186f`.
The base Compose guard now uses single-pass interpolation: every nonempty removed
key appends only its key name to the otherwise numeric one-instance `migrate`
scale. Compose 2.38.2 accepts the clean configuration and rejects an injected
removed `AI_MODEL` as the value-free invalid scale `1-AI_MODEL`. The standalone
Python preflight remains authoritative for empty/root/process cases.

Targeted verification on the follow-up branch: Compose 2.38.2 clean configuration
passed; its legacy-key negative control failed closed; installed Compose 5.5.1
configuration passed; configuration migration preflight passed; 19 focused
configuration/migration tests passed; context validation passed with 37 required
files, 68 guides and 967 links. An initial root-cwd pytest invocation failed to
resolve the backend `app` package; rerunning the documented command from `backend`
passed. PR #36 was opened for exact implementation commit `12f73c3`. A fresh
single-branch clone of that pushed commit bootstrapped independent generated
secrets without printing them; exact root `docker compose up -d` exited zero,
the migration exited zero, all eight long-running services became healthy,
routed `/healthz` returned HTTP 200, and `git status --short` remained empty.
PR #36 exact head `01ee388e0afa1f4e377206e0984b0e56b496c1ad` passed all
14 GitHub checks, including every CI job, `ci-required` and dependency review,
with no base conflict. It merged through the protected flow as commit
`8a5c0aab14de7a6ef1bcf707f28507b9ba3dec6f`.

Production recovery rehearsal run #7 (`35612905122`) targeted that exact `main`
commit and passed in 2m26s; its `clean-install-recovery` job passed in 2m20s. A
new isolated single-branch clone of exact protected `main` bootstrapped generated
secrets without printing them. Exact root `docker compose up -d` exited zero,
the migration exited zero, all eight long-running services became healthy,
routed `/healthz` returned HTTP 200, and `git status --short` remained empty.
Only evidence/status files change in the resulting checklist-closure commit; no
runtime source or configuration behavior changes. These results resolve the
aggregate definition-of-done gate without asserting a centralized production
deployment.

## Limits and preservation

- No centralized production deployment exists or is claimed.
- No exact Windows/browser/Narrator version is claimed without supplied evidence.
- No paid provider request is repeated for this release-only closure.
- Destructive migration testing never targets operator data. Any isolated fresh-
  clone volumes used by this closure are disposable and removed after verification.
- Root `.env` values and credentials are never logged or committed.
