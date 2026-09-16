# Repository context system implementation

Date: 2026-09-16. Scope: implement all eight steps of
[repository-context-system-plan.md](../../../repository-context-system-plan.md).
User requested repository/log orientation, subagents where useful, complete task
verification and a development log. No application behavior or adjacent Phase
10/11 remediation is included.

## Audit and preservation

- Read the complete context-system plan, current source inventory, maintained
  domain guides, roadmap/changelog/runtime policy and dated implementation logs.
  `.agent/AGENTS.md` was absent; root `AGENTS.md` and README were also absent.
- Used independent backend, generation/email and frontend audits. Followed
  actual entry points, UI → HTTP → service → persistence, migration chain and
  guarded test/CI harnesses. Memory was an orientation aid only; current code
  and repository evidence supplied documentation facts.
- Starting user-owned changes: twelve flat tracked log deletions with logs
  present in untracked date folders, plus the untracked requested plan. Preserved
  all log bodies/moves, real root `.env`, application source, services/data and
  volumes. Changed the log index and one active roadmap reference to new paths.
- Code head observed `a9461b7`; code migration head `20260916_0007`. These are
  code observations, not a fresh remote protection or live DB status check.
- Additional untracked `.agent/README.md` and `.agent/MOC.md` appeared during
  integration. Read their supporting-evidence governance/navigation and preserved
  their contents. Linked them from canonical navigation and included their
  local links in validation; the new log updates only the existing log area index.

## Documentation inventory and decisions

Current domain guides retained in place: ACCESSIBILITY, AI_EVALUATION,
AI_GENERATION, AI_PROVIDERS, AUTHENTICATION, CI, CONFIGURATION,
DATABASE_OPERATIONS, DEPENDENCIES, DEPLOYMENT, EMAIL_DELIVERY, LOCALIZATION,
PDF_GENERATION, RUNTIMES, TESTING and VERSIONING. They own operational detail;
new architecture/maps link to them instead of duplicating setting tables.
The active remediation plan remains the individual-task authority, changelog
the release record, frontend README the module setup entry.

Historical material: dated logs remain snapshots; Phase 9 merge closure
supersedes earlier unmerged notes. `docs/archive/idea.md` was already archived
and clearly historical; added archive navigation rather than moving active
guides. The context-system plan becomes a completed reusable reference.

Durable ADRs record existing product/security/data/worker decisions: four-option
cards, server grading, distinct completion/mastery, Alembic ownership, deletion
cascades, grounded validation, one root configuration, PostgreSQL durable jobs,
purpose-scoped sessions/roles and transactional email. No new product decision
was inferred from speculative ideas or examples in the reusable plan.

## Implementation and important corrections

- Added root agent rules, human README, canonical orientation and project map;
  backend/frontend MOCs; five cross-file architecture documents; ten ADRs and
  their index; local setup/current state; guide/archive indexes.
- Cross-linked entrypoints → maps → architecture → ADRs → actual source/tests.
  Added common change paths to answer where to change auth, invitation,
  generation, review/publication, study/progress and runtime configuration.
- Current state records Phases 0–9 complete from current roadmap/closure log,
  with Phases 10–11 open. Adding this README does not complete broader release
  requirements, select a license or establish live production deployment.
- Qualified email guide timeout/disconnect retries: pre-delivery failures retry;
  delivery-stage disconnect/timeouts are ambiguous and require operator review.
- Captured source limits precisely: study-session response hides answers but
  authorized general card GETs disclose them; no public account deletion API;
  incorrect answers leave ease factor unchanged; worker governor is process-local;
  durable telemetry can miss crash/cancellation attempts; atomic DB job result
  does not guarantee one remote provider execution.
- Added standard-library `scripts/check_context.py` to check required files,
  active relative Markdown links and heading targets. It reads no application
  settings or secrets and makes no network calls. Historical bodies/external
  URLs are excluded. Added it to both existing backend CI matrix members and
  documented the local command; behavioral accuracy remains source-reviewed.

## Verification

- `python scripts/check_context.py`: passed; 26 required files, 49 active guides,
  582 local links validated. Active guide/source/ADR/module targets resolve.
- Temporary positive/negative fixtures: valid file/self/inline-code-heading
  fragments pass; examples/external URLs are excluded; missing/empty required
  context, dead local links, missing heading fragments and repository escapes
  produce failures. No persistent fixture/test artifacts were added.
- `backend/venv/Scripts/python.exe scripts/check_ci.py`: passed all three
  workflow contracts and protection/budget definitions, including mandatory
  context validation in the backend matrix. This is local workflow validation,
  not a hosted CI execution or remote protection refresh.
- `python -m py_compile scripts/check_context.py scripts/check_ci.py`: passed.
- `git diff --check`: passed. Git reports normal LF/CRLF checkout notices;
  no whitespace error was found.
- Preservation check: all twelve pre-existing moved log bodies match HEAD after
  ignoring line-ending encoding. Dated folders/moves remain user-owned.
- Independent final frontend/config/setup/plan review passed. Independent
  backend review found two publication phrases to narrow: only sets have
  `is_published`, not subjects. Corrected the map/system overview and rescanned
  active context for that terminology. No other substantive issue remained.
- Plan completion review: all eight implementation steps, maintenance/bootstrap
  duties and eight success criteria have concrete files/source/path evidence.
  Confirmed a newcomer can navigate generation, auth/invitation/recovery,
  review/publication, study/progress and configuration from map to source.

Full application/backend/frontend/service/browser/security/live suites were
not rerun: application code and runtime behavior did not change. No live AI,
production SMTP, destructive migration, data/volume operation, commit, push or
deployment was performed. Earlier hosted/application results remain labeled
as dated repository evidence rather than new gate results. No blocker remains
for this documentation-system scope; Phases 10–11 stay open in their tracker.
