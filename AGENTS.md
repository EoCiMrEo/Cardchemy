# Agent instructions

Start every task here. The canonical project orientation is
[docs/00-START-HERE.md](docs/00-START-HERE.md); code is the final authority for
implemented behavior.

## Mandatory reading order

1. This file.
2. [Start here](docs/00-START-HERE.md).
3. [Project map](PROJECT-MAP.md).
4. Architecture documents relevant to the task.
5. Relevant accepted decisions in the [ADR index](docs/decisions/ADR-000-INDEX.md).
6. The relevant [backend](backend/MOC.md) or [frontend](frontend/MOC.md) module map.
7. Task-relevant source files and tests.

Read [current state](docs/development/CURRENT-STATE.md) for phase work and
[the log index](.agent/logs/README.md) for relevant implementation evidence.
Supporting-artifact storage rules live in [.agent/README.md](.agent/README.md)
and its [workspace map](.agent/MOC.md).
Do not recursively read the entire repository unless the task is a repository
audit, context is missing/stale, or the task spans most subsystems. Before major
changes, follow the documented flow into current code and check consumers,
contracts, migrations, and tests. Resolve material ambiguity with the user.

## Canonical ownership

- Product orientation: `docs/00-START-HERE.md`.
- Navigation: `PROJECT-MAP.md` and module `MOC.md` files.
- Cross-file behavior: `docs/architecture/`; accepted rationale: `docs/decisions/`.
- Supported runtimes/configuration: `docs/RUNTIMES.md` and `docs/CONFIGURATION.md`.
- Phase tasks: `issues-required-remediation.md`; phase summary: current state.
- Operational guides: [documentation index](docs/README.md).
- Dated `.agent/logs/` records and `docs/archive/` are historical evidence, not
  current instructions. Later verified code and accepted decisions supersede
  their old paths, baselines, and unfinished-phase notes.

## Working rules

- Inspect `git status` first. Preserve unrelated working-tree edits, log moves,
  the real root `.env`, database data, and volumes. Check consumers before
  removing or renaming files. Use independent subagents when useful for an
  audit spanning multiple subsystems; give each a bounded ownership area.
- Root `.env` is the only user-managed file configuration; `.env.example` is
  its template. Never print secrets or inject them into browser variables.
  Use guarded disposable test services instead of operator databases/SMTP.
- Follow accepted ADRs. Do not invent replacement architecture or expand into
  adjacent roadmap phases without authorization. If a decision must change,
  explain the evidence and supersede its ADR explicitly.
- Keep static generation routes before `/flashcards/{flashcard_id}`. Alembic
  owns schema evolution. Preserve server-authoritative answers, ownership and
  enrollment checks, durable idempotency, bounded jobs, and provider retry limits.

## Validation and documentation definition of done

Use [testing commands](docs/TESTING.md). For backend behavior, run the relevant
offline contracts and disposable PostgreSQL/Mailpit suites when affected. For
frontend behavior, `npm run check` is authoritative. Paid AI and the separate
live password-reset browser case require their explicit opt-ins; deselected or
skipped tests do not establish live verification. Validate migrations on a
disposable database, never by downgrading operator data.

Update context in the same task when architecture, behavior, ownership, data
contracts, invariants, or project structure change:

- Update project/module maps when paths or responsibilities change.
- Update architecture documents when a cross-file flow or contract changes.
- Add/supersede an ADR when a durable decision changes; retain historical ADRs.
- Update current state when a phase or milestone completes; leave task detail
  in the remediation plan.
- Update operational guides when setup/configuration/test commands change.
- Record scope, decisions, changes, checks, failures and remaining limits in a
  dated `.agent/logs/YYYY-MM-DD/` file, and link it from the log index.

Run `python scripts/check_context.py` for active documentation links and
required context files. Trivial formatting/local implementation refactors do
not require unrelated context edits. Report exactly which checks passed,
skipped, or were not run; a task with stale relevant context is incomplete.
