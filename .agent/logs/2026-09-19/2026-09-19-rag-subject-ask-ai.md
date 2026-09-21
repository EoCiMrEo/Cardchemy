# Subject Ask AI backend and durable answer jobs

Date: 2026-09-19

Scope: implement and close Phase 17 of the approved
`Cardchemy-Subject-Scoped RAG Implementation Plan.md`. Phase 18 frontend work,
Phase 19 corpus-scale/live quality evaluation and Phase 20 rollout remain out of
scope.

## Starting context and preservation

Work started on `main` at `479f56f597ff5a13410d01cad433ef075da260bd`.
The working tree already contained the in-progress, uncommitted Phase 14–16 RAG
implementation and its documentation/evidence. Those changes and all unrelated
user work were preserved. Root `AGENTS.md`, canonical orientation/project/module
maps, current state, the approved RAG plan and ADR-012, architecture, provider,
configuration, database, privacy, deployment, testing and the relevant dated
RAG logs were read before implementation.

The real root `.env`, user content, database volumes and credentials were not
read, rewritten or removed. Provider behavior used deterministic local fakes;
no paid AI call or live provider evaluation was authorized or made. Three
bounded Phase 17 audit subagents were dispatched as requested for database,
API and AI/worker review. Each hit the external usage limit before returning a
finding, so none was treated as evidence; the areas were reviewed and verified
directly.

## Implemented contracts

- Added migration `20260919_0012` and ORM models for owner-private
  `rag_threads`, expiring `rag_messages`, exact `rag_message_sources`, durable
  `rag_answer_jobs` and deletion-resistant `rag_answer_quota_events`. Composite
  foreign keys bind thread/user/Subject/message/job/source scope and exact
  content/index/chunk revisions. PostgreSQL triggers enforce state transitions,
  claim immutability, exact current quote sources and atomic completion.
- Added authenticated Subject Ask AI endpoints to create/list/read/delete own
  threads, enqueue/poll/cancel/manual-retry jobs and read current citations.
  Every operation rechecks actual Subject access and thread ownership;
  instructors cannot read student chats. Admission uses a transaction advisory
  lock, stable hashed idempotency and payload fingerprints, separate daily and
  active/queue limits, per-user and deployment thread/message storage caps,
  future-answer storage reservation and token/time/cost bounds.
- Added a dedicated answer worker/process and Compose service with only answer
  and query-embedding credentials. FIFO `SKIP LOCKED` claims use worker identity,
  64-hex claim tokens, leases, heartbeats, attempts and deadlines. Current
  session, principal role/enrollment, selected documents, publication, corpus,
  embedding space and provider snapshots are rechecked before query embedding,
  each model stage and the final fenced transaction.
- Added strict course-only structured answers: explicit answer/abstention,
  one-to-five ordered claims, distinct retrieved chunk UUIDs, byte-exact
  contiguous quotes and answer text containing only the cited claims. A separate
  structured semantic-support call must approve every claim; empty/insufficient
  retrieval, model abstention or rejected support commits a fixed server-issued
  abstention. Titles/pages/sections/revisions come only from current database
  rows. Questions, history, source text and model output remain delimited
  untrusted data with no tools/configuration authority.
- Added explicit cancellation and bounded manual retry with a refreshed current
  auth-session fence. Only pre-provider dead leases can requeue automatically,
  under bounded exponential delay/attempt/deadline rules. Provider-started dead
  leases, handled failures and whole-job timeouts are terminal until explicit
  retry. Graceful-shutdown cancellation does not masquerade as a user cancel;
  stale workers cannot persist usage or results.
- Implemented G2 lifecycle: 90-day default per-message/source expiry, bounded
  question-first cleanup and empty-thread removal; current-access history/source
  checks; immediate stored-answer/citation hiding after unpublication,
  replacement, deletion, corpus or space change. Account export includes only
  the requester's conversations and safe job fields; deletion refuses active
  affected answer work.
- Added content-free error/worker/queue/support telemetry, answer health probes,
  root-only configuration, privacy/deployment/database/provider guidance and
  production-rehearsal service/credential-isolation coverage. API/browser/email
  processes receive no RAG provider key.

Primary paths:

- `backend/alembic/versions/20260919_0012_subject_ask_ai.py`
- `backend/app/models/rag.py`
- `backend/app/schemas/rag.py`
- `backend/app/routers/rag.py`
- `backend/app/services/rag_answers.py`
- `backend/app/ai/answering.py`
- `backend/app/workers/rag_answer.py`
- `backend/app/answer_worker.py`
- `docker-compose.yml`

## Verification evidence

Passing evidence on the final source:

- Final focused answer/configuration/observability/rehearsal-guard suite: 69
  passed in 32.36 seconds.
- Complete backend offline suite: 702 passed, 87 service/opt-in skips and one
  explicitly deselected live-AI case in 83.67 seconds.
- Phase 17 focused strict-answer, lifecycle and every-endpoint tests passed as
  part of that suite. They cover uncited prose, unknown/duplicate/noncontiguous
  citations, separate semantic support rejection, prompt injection delimiting,
  abstention, idempotency/payload conflicts, storage/active limits, cancel/retry
  and instructor/outsider privacy for every thread/job/source route.
- Disposable PostgreSQL/pgvector suite: 72 passed, three gated skips and 715
  deselected in 53.35 seconds. Fresh migration reached `20260919_0012`; head and
  Alembic drift checks passed; full downgrade to base, re-upgrade to head and
  repeated head/drift checks passed. Owned container/data/credential cleanup was
  confirmed.
- PostgreSQL Phase 17 cases prove grounded answer plus exact source atomicity,
  server metadata, current-access history, zero provider calls after queued
  enrollment revocation, immediate G2 redaction after unpublication, same-key
  concurrent collapse, race-safe per-user active capacity, pre-provider recovery,
  post-provider terminal dead leases, deadline/cancellation behavior, atomic
  rollback and stale-claim refusal.
- Production-rehearsal guard tests: 27 passed. Base `docker compose config
  --quiet` passed; Docker emitted host-config permission warnings without
  exposing values. `scripts/check_ci.py` passed all workflow/protection/budget
  contracts.
- Python compileall passed for application, migration and new tests. `git diff
  --check` reported no whitespace errors (only the repository's existing
  Windows line-ending notices). Context validation passed with 37 required
  files, 67 active guides and 926 local links. The Phase 17 plan scan reports
  19 checked and zero unchecked tasks.

The final PostgreSQL best-practices audit added dedicated indexes for Subject,
auth-session and retention/deletion access paths, deployment-wide durable chat
storage bounds, active-job future-answer reservations, an allowlist constraint
for public terminal error pairs and consecutive citation-order enforcement.

## Failed attempts and non-evidence

- The first offline suite used the system Python, which lacked the backend
  Alembic dependencies; it was rerun with `backend/venv`. Three privacy tests
  then exposed a narrow legacy test settings object without the new chat field;
  the runtime setting remains authoritative and the compatibility fallback was
  added before the complete passing rerun.
- The first sandboxed PostgreSQL harness could not access Docker. The exact
  documented command was rerun with approved Docker access. Its first complete
  run found one Phase 16 recovery assertion still naming the former `0011` head;
  that test was updated to `0012`, then the entire disposable migration/service
  gate passed twice. Failed runs are not evidence.
- An endpoint fixture initially passed a response UUID string directly to the
  SQLite UUID binder. The fixture was corrected to use `UUID`; the endpoint test
  and complete offline suite passed afterward.

## Limits and deferred work

- RAG remains disabled by default. No UI was added; Phase 18 owns accessible
  frontend threads, polling, citation presentation and user-facing disclosure.
- No live provider/model quality, current-price, production-deployment, hosted
  CI or external telemetry claim is made. Phase 19 owns authored-corpus quality,
  latency/support thresholds and any explicit, bounded live evaluation.
- The provider governors are process-local. Operators must divide actual shared
  account/project RPM and input-TPM across index/answer replicas and set explicit
  quota-bucket labels; labels are not distributed enforcement.
- One committed answer does not imply exactly one remote execution. Network
  ambiguity after a provider boundary is terminal and requires deliberate
  review/retry under the documented bounds.
