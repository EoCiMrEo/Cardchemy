# Root agent guidelines merge

Date: 2026-09-16.

## Scope and inputs

User requested merging repository-root `AGENTS.md` with the supplied Downloads
`AGENTS.md`. The supplied document was treated as merge input, not a request to
execute its deployment/migration/test commands or perform open roadmap work.

Read both guides, canonical orientation/navigation/current state, context-plan
requirements, supporting-artifact governance/log index and the pre-existing
untracked agent-context audit. Rechecked configuration/test/CI/branch-protection
and release-workflow facts against repository files. Independent review mapped
the attachment's unique requirements to retain and reviewed the merged result.

## Merge decisions

- Retained root canonical bootstrap: agent rules → Start Here → project map →
  relevant architecture/ADRs/MOC → task-relevant guides/source/tests. Adapted
  attached older startup order to the now-completed context system.
- Added attached authority/conflict resolution, scoped instructions, branch/diff
  inspection, explicit data/secret preservation and architecture/Git safeguards.
- Integrated product/auth/DB, durable PDF/AI/provider/email, backend/frontend,
  migrations/dependencies, applicable testing/security/accessibility, operations,
  logging/documentation and definition-of-done rules. Removed duplicated
  product snapshots/navigation tables/command blocks in favor of canonical links.
- Retained source limitations from the current context: only sets publish;
  study-session answer secrecy is limited; native root-file loading is not
  Compose credential isolation; governor is process-local; DB result uniqueness
  differs from one remote execution; telemetry differs from a billing ledger.
- Protection wording describes the checked-in definition, not a fresh remote
  state claim. Release SBOM has a separate workflow. Engineering standards do
  not assert unfinished Phase 10/11 hardening exists.
- Expanded the root guide to retain both inputs' operational requirements while
  avoiding a second detailed architecture/navigation document. The original
  plan's approximate 1–2-page size is guidance, not a reason to discard user-
  supplied requirements in this authorized merge.

## Preservation

Preserved the Downloads attachment, the pre-existing untracked context-audit log,
all application/runtime/CI code, real `.env` and services/data. Only root
`AGENTS.md`, this new record and the nearest log index are in the change scope.
Indexed the existing context-audit record as requested by its own closing note;
its contents remain untouched.

## Verification

- `python scripts/check_context.py`: passed; 26 required files, 49 active guides,
  610 local links. All merged guide/index links resolve.
- `git diff --check`: passed; only standard LF/CRLF checkout notices were emitted.
- Independent final review confirms all substantive requirements from both inputs
  are retained directly or through canonical links. Corrected its one finding:
  delivery-stage disconnects/timeouts (or lost lease after send starts) are
  ambiguous; explicit SMTP rejections have their existing retry/terminal policy.
- Clarified privacy wording explicitly for raw model responses/internal exception
  details and email recipients/message bodies.
- Final local scope: root guide and log index modified; new merge log added;
  pre-existing untracked context-audit log preserved and indexed. Attachment and
  all application/runtime/service state remain unchanged. No temporary operational
  resources were created.
- Application/backend/frontend/service/live suites were not run because no
  runtime code changed. No commit, push, merge to a Git branch or deployment was
  requested/performed; this task merges document contents locally.

No unresolved conflict or blocker remains in the document-merge scope.
