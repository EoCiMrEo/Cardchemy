# Product quality Lanes 0 and 1 implementation

Date: 2026-09-22

## Scope and starting context

This implements only Lane 0 and Lane 1 of the
[product quality remediation plan](../../../docs/development/PRODUCT-QUALITY-REMEDIATION-PLAN.md).
The work started on branch `main` at `6c02d6c`. Existing edits and the untracked
investigation, audit and plan files were preserved. The root operating guide,
canonical orientation, project/module maps, current state, roadmap, relevant
architecture/ADRs/guides, source, tests and dated RAG/product-quality logs were
reviewed before implementation. Bounded subagents independently audited Lane 0,
Lane 1, documentation and the final integration; their useful findings were
incorporated before their later usage-limit failures.

The operator confirmed that this checkout is the only affected installation.
The operator also chose a Lane 0 diagnostic baseline whose local-support
verdict is explicitly `not_implemented`; the measured local verifier remains
Lane 5 work. No Lane 2–6 implementation was added.

## Lane 0: paused Ask and safe diagnostics

- `RAG_ASK_ENABLED` is a separate fail-closed switch with a false default. A
  code-owned mismatch between `legacy_three_call_v1` and the required
  `two_request_local_support_v1` policy prevents configuration alone from
  reopening the legacy worker. Capability responses expose the effective
  state. New conversation, question and retry admission fails safely; the
  answer worker claims no work. Owner-authorized history, sources and
  cancellation remain available, while Knowledge capture, indexing and
  reindexing remain independently available.
- The Ask panel shows a paused notice, disables new conversation/question
  controls and hides Retry. Typed contracts and browser fixtures cover the
  state. The deterministic cross-stack journey covers both RAG-disabled and
  RAG-enabled/Ask-paused configurations and verifies that the rest of the
  product still works.
- `resolve-ask-shutdown` previews and, only with stopped writers, terminally
  resolves queued/running legacy jobs without erasing questions or history.
  It records possible remote execution so an uncertain attempt is never
  silently replayed. `docs/ASK_AI_SHUTDOWN.md` owns stop-admission, drain,
  restart, monitoring and rollback steps.
- Alembic `20260922_0014` adds safe job-level stage/error/uncertainty fields,
  catalog/schema snapshots and attempt-scoped stage rows. Context-local
  provider scopes attribute physical requests, retries, elapsed time, token
  usage, cost estimates and remote uncertainty to the correct concurrent
  durable attempt without persisting content or raw exceptions. Cancellation
  during a provider call retains the completed stage metrics.
- The focused synthetic corpus adds repeated direct/paraphrase, reported
  support false-rejection and contradiction-control cases. The retained live
  RAG harness now refuses before provider construction even if its historical
  authorization flags are set.

## Lane 0 diagnostic baseline

The disposable PostgreSQL run used deterministic local embeddings with the
real exact pgvector/FTS retrieval path. Each case returned vector candidate
`p1` at rank 1 and `p4` at rank 2, no lexical candidate, and selected evidence
pages `[p1, p4]`.

| Case | Retrieval latency (ms) | Observed answer | False abstention | Local support | Remote tokens / cost / calls |
| --- | ---: | --- | --- | --- | ---: |
| `direct-first` | 4.900 | `not_run_ask_paused` | `not_measured` | `not_implemented` | 0 / 0 / 0 |
| `direct-repeat` | 4.861 | `not_run_ask_paused` | `not_measured` | `not_implemented` | 0 / 0 / 0 |
| `paraphrase-first` | 5.686 | `not_run_ask_paused` | `not_measured` | `not_implemented` | 0 / 0 / 0 |
| `paraphrase-repeat` | 5.298 | `not_run_ask_paused` | `not_measured` | `not_implemented` | 0 / 0 / 0 |
| `semantic-support-false-rejection` | 5.528 | `not_run_ask_paused` | `not_measured` | `not_implemented` | 0 / 0 / 0 |
| `contradiction-control` | 6.156 | `not_run_ask_paused` | `not_measured` | `not_implemented` | 0 / 0 / 0 |

The authored future accept/reject fields remain Lane 5 targets. This baseline
does not claim answer quality or a local-support decision while Ask is paused.

## Lane 1: audited Gemini-only new work

- `backend/app/ai/gemini_catalog.py` is a closed, versioned catalog shared by
  Flashcard and Ask roles. On 2026-09-22 the official Google model, thinking,
  structured-output, token and pricing pages were rechecked for the stable IDs
  `gemini-3.5-flash-lite`, `gemini-3.5-flash`, `gemini-3.6-flash`,
  `gemini-3.7-flash` and `gemini-3.8-flash`. All five advertise structured
  output, a 1,048,576-token input limit and 65,536-token output limit. The
  catalog permits `minimal` only for 3.5/3.6, uses provider-default sampling,
  counts candidate plus thinking output, and stores the reviewed standard-tier
  input/output prices. The 3.6/3.7/3.8 introductory prices carry an explicit
  2026-12-31 recheck boundary.
- Settings and provider construction resolve the role/model/thinking/context/
  output/schema combination before a job can be admitted. New generation jobs
  snapshot catalog and schema policy versions; the worker resolves them again
  and fails a stale or incompatible snapshot before extraction or a remote
  call, cleaning a retained source when required. Manual retry does not
  reinterpret an old policy.
- New text and embedding settings/factories are native Gemini only. Custom
  endpoint/task-mode settings were removed from the root template, Compose and
  active guides. Historical rows and embedding-space identities remain
  readable for recovery. The content-free migration inventory reports legacy
  values and active work without reading content or credentials, and the
  config migration preflight reports retired key names only.
- The offline role-by-model matrix covers both roles, every admitted model,
  schema/thinking payloads, unsupported 3.7/3.8 `minimal`, provider 400/error
  mapping, malformed output, legacy configuration rejection, old queued job
  behavior, historical-space restore, source cleanup and no provider
  substitution.

## Existing-installation migration and runtime evidence

Docker initially reported no running Compose services. The retained database
was at `20260920_0013`. Before migration, a custom-format dump was created at
`%TEMP%\cardchemy-20260922-pre-0014.dump` (1,563,478 bytes), restricted to the
current operator/system, listed successfully with `pg_restore`, restored into
an exact disposable database, and checked at head `0013` with 12 answer jobs
and one embedding space. The disposable restore database and container-side
temporary copy were removed after the upgrade proof; the host backup remains.
No volume was deleted.

The preflight and content-free inventory found:

- configured providers: Gemini for Flashcard, answer and embeddings; no legacy
  provider setting;
- generation jobs: 3 completed Gemini and 2 completed historical unconfigured;
  no retained generation source;
- index jobs: 4 completed Gemini;
- answer jobs: 5 completed Gemini, 4 terminal nonretryable Gemini failures and
  3 terminal retryable Gemini failures; no queued/running answer job;
- embedding spaces: one Gemini space active for one Subject, with no staged or
  legacy space requiring reindex/cutover.

The real root `.env` was not rewritten and no secret value was printed. Actual
validated settings reported raw Ask false, effective Ask false, answer
availability false and index availability true. Alembic upgraded the retained
database transactionally to `20260922_0014`. Shutdown preview and apply both
reported queued 0, running 0 and possible remote execution 0. The rebuilt full
stack then reported every service healthy; both API and answer worker confirmed
the code policy mismatch and effective Ask shutdown. The API resolved
`gemini-3.5-flash-lite`, Ask resolved `gemini-3.5-flash`, and embeddings
resolved `gemini-embedding-001`. The temporary verification stack was stopped
without removing volumes, returning the checkout to its original no-running-
service state.

## Verification

- Targeted Lane 0/1 backend contracts: `105 passed`.
- Config migration contracts: `6 passed`; actual root config preflight passed.
- Disposable PostgreSQL service/migration suite: `82 passed, 3 skipped, 784
  deselected` in 73.23 seconds, including head/drift, downgrade-to-base and
  re-upgrade-to-head.
- Frontend `npm run check`: types, lint, units, components, coverage, production
  build and Chromium passed; Chromium reported `57 passed, 1` explicitly gated
  live-reset skip. Coverage was 96.65% statements, 85.16% branches, 93.10%
  functions and 97.84% lines.
- Deterministic cross-stack journey passed in both RAG-off and RAG-on/Ask-paused
  modes, including Knowledge publication, cards, email and study progress.
- Final backend offline suite: `771 passed, 97 skipped, 2 deselected` in 115.77
  seconds. The first final attempt completed 770 tests but Windows returned
  `WinError 10055` while creating one unrelated async test loop. That test
  passed alone, the temporary Compose stack was stopped, and the complete
  clean rerun passed.
- Updated backend/frontend production images built, Alembic current reported
  `20260922_0014 (head)`, and all Compose health checks passed before cleanup.
- `python scripts/check_context.py` passed with 37 required files, 70 active
  guides and 1,019 local links. `python scripts/check_ci.py`, final Compose
  interpolation and `git diff --check` also passed. The final checklist audit
  reported Lane 0 at 5 checked/0 unchecked and Lane 1 at 6 checked/0 unchecked.
- Release metadata for v0.1.0 and the canonical code/brand notice check passed;
  no publication or signature claim was made.

## Evidence boundaries and cleanup

Normal tests, the baseline and runtime verification made zero paid provider
calls. No live provider smoke, hosted CI, production deployment outside this
checkout or manual assistive-technology release pass was claimed. Official
catalog availability is the published stable-model contract; it does not prove
that a particular API key has access. Ask remains disabled until Lane 5 ships
the two-request/local-support policy and its separately authorized quality and
cost gates. Lanes 2–6 remain unchecked. Test containers and disposable
databases were cleaned; retained user data, root `.env`, volumes, private
history and embedding-space identity were preserved.
