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

For phase work, read [current state](docs/development/CURRENT-STATE.md) and the
[public roadmap](ROADMAP.md). Completed phase checklists are historical material
in the [archive](docs/archive/README.md). For supporting artifacts, read
[.agent governance](.agent/README.md) and its
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
- Runtime/configuration support: [RUNTIMES](docs/development/RUNTIMES.md) and
  [CONFIGURATION](docs/operations/CONFIGURATION.md); operational detail: [guide index](docs/README.md).
- Milestone status: current state; proposals: public roadmap; completed phase
  tasks/checklists: archive and dated evidence.
- Dated `.agent/logs/` and [archive](docs/archive/README.md): historical evidence.
  Early `idea.md` proposals do not define shipped features or active instructions.

Cardchemy has instructor/student roles and browser → API → PostgreSQL workflows
with separate generation and email workers. Read the canonical docs for detail.
Current state records Phases 0–11 and Subject Knowledge/RAG Phases 12–21
complete. Observability/privacy/export/audit are documented
operator controls; the separate v1.0 operational readiness gate passed.
Current published version is 0.2.0; readiness completion did not publish v1.0.
Verify their current source and
limits rather than inferring completion from individual components.
Follow accepted ADRs; do not invent replacement architecture or expand into
adjacent phases without authorization. Supersede decisions explicitly when
evidence and the authorized task require a change. Replacing the accepted
pgvector/RAG design or introducing Redis, Celery, another queue or persistence
layer needs an approved architecture change.
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
- Compose isolates Flashcard AI credentials to the generation worker, RAG
  embedding credentials to the index and answer workers, source-judge
  credentials to the answer worker, and SMTP credentials to the email worker.
  Preserve those boundaries. Native operators must inject
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
  Student Progress is distinct currently approved cards answered correctly at
  least once; Accuracy is correct attempts over all attempts on those cards,
  including no-answer as incorrect. The browser shuffles a copy of options once
  per card presentation and submits option text against canonical server order.
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

- Preserve reserve → bounded raw-PDF upload → any authorized same-Subject
  Knowledge duplicate choice → PostgreSQL queue → fenced worker
  claim → isolated extraction → validated pipeline → atomic draft set/cards.
  Count streamed bytes regardless of `Content-Length`; validate media/signature,
  use filenames only as metadata, and keep extraction off the API event loop in
  a bounded child process. OCR is opt-in and needs the appropriate build/runtime.
- Retain metadata/manual-retry idempotency, race-safe admission/quotas, upload
  expiry, lease/worker identity/claim-token fencing and durable cancellation.
  A repeated new Knowledge upload pauses before capture/indexing for an explicit
  reuse or separate-copy choice. Reuse requires the current ready revision in
  the active compatible embedding space; an unchanged explicit revision is a
  Knowledge no-op. Cancel ends the whole upload job. Raw upload-byte accounting
  remains separate from avoided Knowledge storage/index work.
  Stale workers cannot commit. AES-256-GCM sources are temporary: success,
  cancellation/permanent failures delete them; retryable failures have bounded
  retention. Final set/cards/status/source cleanup commit atomically with no
  partial generated set. At most one DB result does not mean one remote execution.
  If bounded generation yields too few cards, only fully validated, deduplicated
  cards may be encrypted in a finite owner-private pending choice; keep the
  original requested count unchanged. Confirming an exact smaller count creates
  the set atomically without another provider call. A new paid attempt toward
  the original count requires a separate cost acknowledgement. Expiry or cancel
  clears staged cards and the temporary source without deleting independent
  reviewed Knowledge.
- Treat documents/summaries/model output as untrusted evidence, never system
  instructions. Preserve token-bounded server-issued chunks, bounded requests,
  structured output plus strict local validation, trusted chunk lookup,
  normalized quote/answer containment, server-derived page/section provenance,
  canonical card rules, deterministic quality/duplicate rejection and bounded
  refill. Never persist raw model cards through a validation shortcut.
- New AI text execution for flashcards uses the verified native Gemini-only
  catalog; `gemini-embedding-001` remains the default and optional Embedding 2
  uses a distinct staged space. Preserve historical provider/model/space
  snapshots without executing an old policy under a new worker. Ask AI has a
  separate default-off gate. Its approved new-job path is source-only Related
  published Knowledge: at most one current-question query embedding, zero
  answer-model or local answer-verifier calls, and exact current authorized
  unverified references that direct students to the original lecture PDF page
  under ADR-023, with bounded local lexical fallback for transient embedding
  unavailability. The ADR-024 v8/visual-v5 policy may add at most one bounded
  Gemini source-ID judgment over the current question and authorized published
  exact text and bounded original-page PNGs, returning only issued IDs. Unresolved
  follow-ups may additionally transfer only a unique literal subject of at most
  160 characters/twelve words from the strictly preceding user question, bound
  immutably at admission and rechecked before dispatch; full history and assistant
  responses are excluded. It makes no answer/verifier call and
  has zero automatic retries. Its immutable admission contract is
  `literal_subject_admission_v2`; historical v7/visual-v3/v1 rows stay readable
  but cannot execute or retry under v8. The clarity change only permits an
  ordinary learning use of `ignore`; it is not a semantic instruction detector.
  A non-useful page with a conflicting positive cue is discarded, never promoted.
  Source/schema head `0033` does not itself activate Ask. The released v8
  source fence still requires explicit installation Ask/judge flags; fresh
  installations stay default-off. Ask AI is enabled in the retained local installation (verified 2026-10-04). Complete public
  sixty-case quality is 94/99 useful cards; independently reviewed private
  twelve-case quality is 21/24 (87.5%), with 12/12 hits and four per form.
  The accepted floor is 80% of all displayed cards; source/access integrity
  requires zero fabricated, stale, unauthorized or wrong-page references.
  See the [actual closure](.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md)
  for seed/control, display, activation and release proof and all retained
  physical failures/unknown charges. Local closure does not claim hosted CI
  or production deployment; future live evaluations retain exact approval.
  Legacy three-call and two-request answer policies stay fenced. Enable the
  new path only after its displayed-window, access and release gates pass. Preserve the
  non-secret generation enablement switch. One application retry owner handles transient
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
  a configured key is not authorization. See [AI evaluation](docs/ai/AI_EVALUATION.md).
- Email scope is reset, password-change notification and student invitation.
  Keep atomic domain/outbox enqueue, separate SMTP delivery, unique event IDs,
  leases/fencing and send-time token/link rendering instead of stored rendered
  bodies/URLs. Retry only unambiguous transient failures. Disconnects/timeouts
  during delivery or lease loss after send begins are ambiguous and require operator review,
  not automatic duplicate sending. Mailpit is local/test only; production SMTP
  is encrypted. See [email delivery](docs/mail-server/EMAIL_DELIVERY.md).

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

Use [TESTING.md](docs/development/TESTING.md) as command authority; run applicable checks:

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
release checks remain required by [accessibility guidance](docs/ui/ACCESSIBILITY.md).
Do not lower coverage/bundle/accessibility/audit/security thresholds to get a pass;
budget changes need explicit measured rationale.

Update Python direct `.in` inputs and regenerate hashed locks with
[lock_dependencies.ps1](backend/scripts/lock_dependencies.ps1); verify supported
Python versions. Keep frontend package/lock consistent and use `npm ci` for clean
installs. [Runtime support](docs/development/RUNTIMES.md) and [dependency policy](docs/ci-cd/DEPENDENCIES.md)
own the details.

Base Compose is a built production-shaped local stack; use exactly the documented
development or production override. Follow [local setup](docs/development/LOCAL-SETUP.md)
and [deployment](docs/operations/DEPLOYMENT.md). Keep production DB/API private behind the
frontend/TLS edge. For upgrades, drain writers/workers, verify backups, migrate,
verify heads and then restore traffic per [database operations](docs/database/DATABASE_OPERATIONS.md).

Keep commits/tasks focused, preserve shared history, never add secrets or bypass
required checks/protection. Force-push/history rewrites require authorization.
The [protection definition](.github/branch-protection.json) requires PR flow,
resolved conversations, current-base `ci-required`, administrator enforcement
and no force push/deletion; verify remote state before operational claims.
[CI](docs/ci-cd/CI.md) covers offline/service/frontend/journey/audit/secret/container
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
