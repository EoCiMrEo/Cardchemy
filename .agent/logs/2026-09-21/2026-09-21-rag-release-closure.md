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

Pending in this checkpoint: merge PR #35, close PR #34, run the hosted production
rehearsal against protected `main`, repeat the isolated fresh-clone exact Compose
start from that merged source, record cleanup, and merge the documentation-only
final checklist update through the protected PR flow. The aggregate definition-
of-done checkbox stays open until those checks pass; this section will be updated
with exact commit/run evidence rather than treating planned work as completed.

## Limits and preservation

- No centralized production deployment exists or is claimed.
- No exact Windows/browser/Narrator version is claimed without supplied evidence.
- No paid provider request is repeated for this release-only closure.
- Destructive migration testing never targets operator data. Any isolated fresh-
  clone volumes used by this closure are disposable and removed after verification.
- Root `.env` values and credentials are never logged or committed.
