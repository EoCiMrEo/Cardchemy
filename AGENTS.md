# Repository guidelines

Start every task here. This operating guide applies to the whole Cardchemy
repository; more specific directory `AGENTS.md` files govern their own scope.
The canonical project orientation is [Start Here](docs/00-START-HERE.md).
These are engineering requirements, not a claim that all planned hardening is
already implemented.

## Authority and startup

Current user/task instructions and explicit operator decisions define scope.
Source, migrations, tests, validated settings and Compose define implemented
behavior. Maintained docs describe supported/intended contracts. If docs and
code materially disagree, investigate whether the problem is implementation or
stale documentation; ask only when intended behavior remains ambiguous.
Historical logs, archived ideas, stale comments and prior chats do not override
current repository evidence.

Before planning or editing, inspect branch/HEAD, `git status --short`, relevant
diffs and untracked files. Preserve pre-existing work. Then read in this order:

1. This root `AGENTS.md` and any applicable directory instructions.
2. [Start Here](docs/00-START-HERE.md).
3. [Project map](PROJECT-MAP.md).
4. Architecture documents relevant to the task.
5. Relevant accepted decisions in the [ADR index](docs/decisions/ADR-000-INDEX.md).
6. The relevant [backend](backend/MOC.md) or [frontend](frontend/MOC.md) module map.
7. Task-relevant operational guides, source files, migrations and tests.

For phase work, read [current state](docs/development/CURRENT-STATE.md) and
[the remediation roadmap](issues-required-remediation.md). For supporting
artifacts, read [.agent governance](.agent/README.md) and its
[workspace map](.agent/MOC.md) when present, or use the
[log index](.agent/logs/README.md). Read only relevant dated logs.
Follow global context into the affected subsystem rather than recursively
rereading the repository. Full audits, release/security reviews and missing or
stale context are exceptions. Before major changes, verify documented flows,
consumers, contracts and constraints against actual source.

## Canonical ownership and scope

- Product/users/workflows/stack: [orientation](docs/00-START-HERE.md).
- Source navigation: [project map](PROJECT-MAP.md) and module MOCs.
- Cross-file behavior: [architecture](docs/architecture/SYSTEM-OVERVIEW.md);
  durable rationale: accepted ADRs.
- Runtime/configuration support: [RUNTIMES](docs/RUNTIMES.md) and
  [CONFIGURATION](docs/CONFIGURATION.md); operational detail: [guide index](docs/README.md).
- Individual phase tasks/status: remediation roadmap; milestone summary: current state.
- Dated `.agent/logs/` and [archive](docs/archive/README.md): historical evidence.
  Early `idea.md` proposals do not define shipped features or active instructions.

Cardchemy has instructor/student roles and browser → API → PostgreSQL workflows
with separate generation and email workers. Read the canonical docs for detail.
The roadmap records Phases 0–11 complete as of 2026-09-17;
refresh it for later work. Observability/privacy/export/audit are documented
operator controls; the separate v1.0 operational readiness gate remains open.
Verify their current source and
limits rather than inferring completion from individual components.
Follow accepted ADRs; do not invent replacement architecture or expand into
adjacent phases without authorization. Supersede decisions explicitly when
evidence and the authorized task require a change. Introducing Redis, Celery,
pgvector/RAG, another queue or persistence layer needs an approved architecture change.
Use independent subagents when useful for audits spanning multiple subsystems;
give each a bounded task and ownership area.

## Preservation, configuration and secrets

- Preserve user edits, log moves, real root `.env`, database data and volumes.
  Check consumers and regression coverage before removing/renaming artifacts.
  Never reset, clean or overwrite unrelated work to obtain a clean tree.
- Root `.env` is the sole user-managed file configuration, with root
  [.env.example](.env.example) as its template. Do not add backend/frontend env
  files. [Bootstrap](scripts/bootstrap_env.py) refuses overwrites; changing a
  setting is not a reason to regenerate installation secrets.
- Prefer validated [Settings](backend/app/config.py) over scattered raw env reads.
  Nonempty process values override root settings, then validated defaults.
  Only intended public `VITE_*` values reach the browser; signing and source
  encryption keys are independent.
- Compose isolates AI credentials to the generation worker and SMTP credentials
  to the email worker. Preserve that boundary. Native operators must inject
  only required credentials; reading a shared root file does not provide the
  same isolation. Tests use injected settings and guarded disposable services,
  not operator `.env`, databases or production SMTP.
- Prefer template/validation code over real environment inspection. If real
  state is necessary, inspect only what the task needs and never reveal values.
  Do not print, paste, upload, commit or log secrets, tokens/cookies, reset/invite
  URLs, private user/document data, prompts, raw model responses or internal
  exception details. Email logs must also omit recipients and message bodies.
- Destructive commands such as `docker compose down --volumes`, `git clean -fd`
  and `git reset --hard` require explicit authorization. A populated volume is data.

## Product, authentication and database invariants

- Instructor provisioning is operator CLI only; additional instructors require
  `--allow-additional`. Public registration is invitation-backed student
  registration. Instructor mutations require subject ownership; student access
  requires enrollment, and study requires published sets/approved cards.
  Browser guards support UX; backend authorization remains authoritative.
- Cards support only `multiple_choice`: trimmed nonempty front/back, exactly
  four trimmed nonempty case-insensitively unique options, and one matching
  canonical answer. AI cards start unapproved; manual instructor-created cards
  are currently approved. Publishing a set requires at least one approved card
  under service/database guards. Subjects do not have publication state.
- Submit an option text/index or explicit null; the server derives correctness
  and quality (5 correct, 1 incorrect/no-answer). Receipt and progress mutation
  are atomic. Same logical retry keeps its key/payload; changed reuse conflicts.
  Do not restore client-supplied correctness or client-owned progress metrics.
- Completion measures attempted approved cards; mastery measures `review` plus
  `mastered` approved cards. Statuses: `new` before an attempt, `learning` below
  7 interval days, `review` at 7–20, `mastered` from 21. See [study flow](docs/architecture/STUDY-PROGRESS-FLOW.md).
  Answer secrecy is limited to study-session payloads; general authorized card
  reads currently expose answers. Do not claim exam secrecy.
- Keep short-lived access tokens in browser memory; refresh tokens remain in
  protected cookies with server-backed rotation/reuse detection. Token purposes
  (access/refresh/invitation/reset), issuer/audience, UUID/JTI/time/session checks
  remain enforced. Logout/reset revoke sessions. Normalize emails, retain
  generic recovery responses, single-use/race-safe optionally recipient-bound
  invitations, and sensitive-endpoint rate limits. No email-verification flow exists.
- Alembic alone evolves deployed schema; API/workers verify all configured
  heads. Startup must not migrate using `create_all`. Preserve UTC-aware times,
  foreign-key deletion semantics, uniqueness, constraints and indexes.
  Used migrations need new revisions, not rewritten history, unless the operator
  explicitly chooses otherwise for disposable unreleased data. Never stamp past
  a failed migration or fix drift by deleting a populated volume.

## Generation, AI and transactional email

- Preserve reserve → bounded raw-PDF upload → PostgreSQL queue → fenced worker
  claim → isolated extraction → validated pipeline → atomic draft set/cards.
  Count streamed bytes regardless of `Content-Length`; validate media/signature,
  use filenames only as metadata, and keep extraction off the API event loop in
  a bounded child process. OCR is opt-in and needs the appropriate build/runtime.
- Retain metadata/manual-retry idempotency, race-safe admission/quotas, upload
  expiry, lease/worker identity/claim-token fencing and durable cancellation.
  Stale workers cannot commit. AES-256-GCM sources are temporary: success,
  cancellation/permanent failures delete them; retryable failures have bounded
  retention. Final set/cards/status/source cleanup commit atomically with no
  partial generated set. At most one DB result does not mean one remote execution.
- Treat documents/summaries/model output as untrusted evidence, never system
  instructions. Preserve token-bounded server-issued chunks, bounded requests,
  structured output plus strict local validation, trusted chunk lookup,
  normalized quote/answer containment, server-derived page/section provenance,
  canonical card rules, deterministic quality/duplicate rejection and bounded
  refill. Never persist raw model cards through a validation shortcut.
- Preserve `gemini`/`openai_compatible` profiles, the non-secret enablement switch
  and snapshotted provider/model. One application retry owner handles transient
  requests with at most three retries and configured delays of at least three
  seconds, respecting usable longer `Retry-After`; SDK retries must not multiply
  attempts. Invalid request/auth/access/model failures do not retry. Handled
  provider/pipeline failure or whole-job timeout must not automatically replay
  the expensive pipeline; bounded infrastructure/dead-lease recovery is distinct.
- Every physical provider attempt uses worker-wide concurrency/RPM/input-TPM
  admission. The governor is process-local; replicas need divided limits or
  distributed governance. Bound time/tokens/cost and telemetry; counters are not
  a complete provider billing ledger and must omit content/prompts/raw responses.
- Normal tests/CI spend no provider quota. Live evaluation needs explicit user
  authorization plus documented endpoint/model/price/call/token/time/cost guards;
  a configured key is not authorization. See [AI evaluation](docs/AI_EVALUATION.md).
- Email scope is reset, password-change notification and student invitation.
  Keep atomic domain/outbox enqueue, separate SMTP delivery, unique event IDs,
  leases/fencing and send-time token/link rendering instead of stored rendered
  bodies/URLs. Retry only unambiguous transient failures. Disconnects/timeouts
  during delivery or lease loss after send begins are ambiguous and require operator review,
  not automatic duplicate sending. Mailpit is local/test only; production SMTP
  is encrypted. See [email delivery](docs/EMAIL_DELIVERY.md).

## Backend and frontend engineering

Keep async I/O async. Do not block requests with PDF/OCR/SMTP/provider work.
Validate requests in Pydantic and stored invariants in the database. Authorize
before expensive work/mutation; keep multi-record operations atomic and understand
commit ownership. Use locks/UPSERT/uniqueness for races, deterministic query/queue
ordering, existing eager-loading patterns and bounded safe errors. Avoid N+1
regressions, hidden commits and raw internal errors. Keep provider-neutral logic
outside adapters. Preserve static generation routes before `/flashcards/{flashcard_id}`.

Keep [typed API contracts](frontend/src/services/types.ts) and domain services;
do not hide mismatches with `any`. Preserve memory-only auth, shared refresh and
operation-race protection. Clean up async effects, requests and timers; polling
must remain non-overlapping/reload-recoverable. Study waits for durable save
before feedback/advance; retries reuse identity and timer/click races stay fenced.
Preserve keyboard/focus/dialog/live-region semantics, text equivalents for color,
reduced motion, mobile targets and no overflow. English v1 copy belongs in
[the typed catalog](frontend/src/i18n/en.ts). Offline/PWA/conflict storage or a
second locale requires an explicit product decision and complete design.

## Verification, dependencies, deployment and Git

Use [TESTING.md](docs/TESTING.md) as command authority; run applicable checks:

| Change scope | Required verification |
| --- | --- |
| Backend logic/auth | Targeted contracts plus offline suite from `backend`; include negative cross-role/subject/publication/approval/expired/reused/malformed cases when relevant |
| Persisted model/transaction/index | Models plus new Alembic revision/contracts/constraints/indexes as needed; PostgreSQL integration and head/drift/upgrade/downgrade/re-upgrade on disposable DB via `python scripts/test_services.py postgres` |
| Email | Targeted delivery units plus `python scripts/test_services.py mailpit` |
| Frontend behavior | `npm run check` from `frontend`, including types/lint/units/components/coverage/build/Chromium |
| Critical cross-stack contract | `python scripts/test_journey.py` with deterministic offline provider |
| Compose/images/security/CI | Documented runtime/image/security checks; workflow changes also use `python scripts/check_ci.py` |
| Context documentation | `python scripts/check_context.py` for required files and active local links |

Never downgrade real data for verification. Destructive operational rollback
requires explicit authorization and a verified backup. Paid AI and the separate
live reset browser test need their opt-ins. Skipped/deselected/fixture tests do
not establish live/provider/production success. Manual spoken assistive-technology
release checks remain required by [accessibility guidance](docs/ACCESSIBILITY.md).
Do not lower coverage/bundle/accessibility/audit/security thresholds to get a pass;
budget changes need explicit measured rationale.

Update Python direct `.in` inputs and regenerate hashed locks with
[lock_dependencies.ps1](backend/scripts/lock_dependencies.ps1); verify supported
Python versions. Keep frontend package/lock consistent and use `npm ci` for clean
installs. [Runtime support](docs/RUNTIMES.md) and [dependency policy](docs/DEPENDENCIES.md)
own the details.

Base Compose is a built production-shaped local stack; use exactly the documented
development or production override. Follow [local setup](docs/development/LOCAL-SETUP.md)
and [deployment](docs/DEPLOYMENT.md). Keep production DB/API private behind the
frontend/TLS edge. For upgrades, drain writers/workers, verify backups, migrate,
verify heads and then restore traffic per [database operations](docs/DATABASE_OPERATIONS.md).

Keep commits/tasks focused, preserve shared history, never add secrets or bypass
required checks/protection. Force-push/history rewrites require authorization.
The [protection definition](.github/branch-protection.json) requires PR flow,
resolved conversations, current-base `ci-required`, administrator enforcement
and no force push/deletion; verify remote state before operational claims.
[CI](docs/CI.md) covers offline/service/frontend/journey/audit/secret/container
gates and context validation; release SBOM work also has a separate workflow.

## Documentation, evidence and definition of done

Update relevant context in the same task when architecture, behavior, ownership,
data contracts/invariants or structure changes: maps/MOCs for paths/responsibility,
architecture for flows, ADRs for durable decisions, current state for milestones.
Retain and explicitly supersede old ADRs. Keep individual tasks in the roadmap.
Do not require unrelated context edits for formatting or obvious local refactors.

Update domain guides for affected auth, DB/recovery, settings/template, PDF, AI,
email, tests, CI, runtimes, deployment, accessibility, localization, dependencies
or versioning; find them in the [guide index](docs/README.md). Release behavior
also updates the [changelog](CHANGELOG.md). Prefer links over copied truth.
Check consumers before archiving obsolete material and repair active navigation.

For substantial implementation/investigation/remediation/security/migration/release
work, add a dated `.agent/logs/YYYY-MM-DD/` record: scope, starting context,
approved decisions, what/why/paths, checks/results, failures/limits and cleanup.
Update the nearest index; root `.agent/MOC.md` changes only for area structure.
Preserve historical log bodies; supersession needs a new log or explicit correction.
Never store secrets, private content/credentials or private reasoning/transcripts.

Before completion, confirm preservation, relevant reading, intact product/security/
data/access boundaries, migrations and race/idempotency/transaction coverage when
applicable, safe errors/logs, authorized live spending, actual passing targeted
and required scope checks, updated docs/evidence and cleanup of temporary resources.
Report changes, checks actually passed/skipped/not run, remaining risks and any
applicable unsatisfied item. A task leaving relevant context stale is incomplete.
