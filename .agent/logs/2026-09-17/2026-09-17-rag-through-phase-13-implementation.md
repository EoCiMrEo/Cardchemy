# Subject-scoped RAG through Phase 13: implementation evidence

Date: 2026-09-17 (operator timezone). Work in progress; no phase closure claim.

## Scope and starting context

The operator requested Preparation A, Preparation B and Phases 12-13 of
[the Subject-scoped RAG plan](<../../../Cardchemy-Subject-Scoped RAG Implementation Plan.md>).
The [startup audit](2026-09-17-rag-through-phase-13-startup-audit.md) records
deep source/document/log orientation, three independent audits and fresh
existing-behavior baselines. Historical completed remediation Phases 0-11
are a separate roadmap, not completed RAG implementation.

Started on `main` at `e10f5839735379e4277d35600067835f53272a89`, preserving
the pre-existing untracked plan/review/update logs and tracked index additions.
Implementation branch: `codex/subject-rag-through-phase-13`; existing changes
were carried intact. The prior startup audit remains historical evidence.

## Decisions received and research

The operator approved mandatory PostgreSQL 16 + pgvector (including RAG off),
90-day private own-chat/published-Knowledge/history hiding policy, Knowledge-only
upload/same-Subject replay/fresh review for changed content, and separate role
workers with explicit division of shared provider quotas. G5 model selection
was delegated explicitly to the agent. These choices are recorded as accepted
design in [ADR-012](../../../docs/decisions/ADR-012-subject-knowledge-and-rag-boundaries.md)
and linked from the plan. No capture/index/Ask AI feature is inferred shipped
from the design record. G3 remains a Phase 14 prerequisite outside this scope.

Read current official OpenAI embeddings/model/snapshot/pricing/deprecation
documentation and independent Google research. Selected `text-embedding-3-small`
at native 1,536 float32 dimensions/cosine, versioned raw-text document/query
format, and `gpt-4.1-mini-2025-04-14` for bounded structured Ask AI. This fits
ordinary per-input batching and the existing HTTP adapter without reasoning
token budgeting. Official prices at review: USD 0.02/M embedding input;
USD 0.40/1.60/M answer input/output. Availability/quality/account quota and future
prices need separate deployment/live evidence; no requests or spending occurred.

Google research identified stable Embedding 2 and Flash-Lite 3.5 alternatives,
but Embedding 2 requires different task-prefix/per-input aggregation semantics
and Flash-Lite billable thinking accounting. They are not implicit fallbacks.
The configured existing flashcard provider/model and job snapshots are retained.
Primary sources and compatibility/corpus requirements are linked in ADR-012.

## Implementation and verification

Preparation A is being implemented by an independent subagent: realistic
authored replay corpus, versioned prompts, bounded refill exclusions, safe fixed
diagnostics and complete prompt/preflight/context/usage accounting. Settings
field rename is reserved for Preparation B after A source stabilizes. Exact
card count, strict batch/grounding thresholds, allocation/scheduling/output
caps and atomic complete-result persistence remain constraints.

Runtime/schema design review proceeds read-only alongside quality work.
An exact database image candidate was inspected through public registry
metadata without pulling/running it; metadata is not runtime, scan, native,
existing-volume or restore evidence. No operator services were changed.

Candidate runtime: `pgvector/pgvector:0.8.6-pg16-bookworm` at multi-platform
digest `sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b`.
Public amd64 metadata identifies PostgreSQL 16.15, vector 0.8.6 and the existing
`/var/lib/postgresql/data` path with portable compiler flags. Candidate Python
integration is `pgvector==0.5.0`; direct input/lock/runtime changes await Phase 12.
The five direct DB consumers and current external-image scan gap were identified.
Deferred composite consistency FKs plus scalar `ON DELETE SET NULL` links were
compiled/tested in synthetic in-memory SQLite; this is deliberate portability
design, not actual PostgreSQL migration/cascade proof. No schema was changed.

An independent A review found that a character-heavy placeholder did not bound
lexical-heavy refill exclusions under the existing token estimator. The owning
subagent is repairing this with an additive rendered envelope and boundary
regressions. Failed/cancelled concurrent request reservations also receive an
explicit uncertain-envelope policy and reuse guard. These reviews do not change
provider retry ownership, structural/grounding thresholds, allocation or caps.

Updated backend/project maps for the prompt module and current-state navigation
for this in-progress work; previous completed remediation/release claims remain
separate. New check: generation lifecycle offline contracts, 18 passed in 4.66s,
including atomic completion, stale fencing, source cleanup and timeout/failure
telemetry. The full changed-source suite and deterministic journey are pending.
Docker Engine/client 29.8.0 and Compose 5.5.1 were observed; the read-only engine
version required approved sandbox escalation. No runtime was started by that
check, and there was no automatic approval-review rejection.

Fresh startup baselines: backend 376 passed, 50 service-gated skips, one live-AI
deselection; focused AI 42 passes; configuration/harness/provider 29 passes.
Those validate the starting product, not new changes. Passing checks, measured
artifacts, failures/limits and checkbox outcomes will be added as achieved.

Preparation A completion checkpoint: versioned map/reduce/generation prompts,
bounded untrusted accepted-card refill exclusions, fixed content-free per-round
quality diagnostics and concurrency-safe per-request input/output/cost admission
are implemented. A nine-case authored corpus/18-row replay isolates the prior
generation renderer; it reports exact-count outcome, accepted/raw yield,
rejections, refill, numerical chunk transfer, persistable-card pages, local
tokens/fixture cost and local timing. Four complete cards and an unscored
pedagogical rubric were shown to the operator; on 2026-09-18 the operator replied
"very good" to the explicit quality-acceptance request. This accepts the sample,
not remote-model quality. An earlier independent review found and resolved
lexical-heavy exclusion reserve, uncertain pending request and partial-fanout
raw-count defects before acceptance.

Focused quality/pipeline/grounding: 55 passed. Full backend: 413 passed,
50 service-gated skips, one paid/live-AI deselection, 71.00 s. Disposable
browser/API/worker/PostgreSQL journey: database proof and browser contract
passed, with owned containers/processes/data/credentials cleaned. Context:
37 required files, 62 guides, 813 links passed; `git diff --check` passed.
The prior 18 generation lifecycle tests passed separately. Bounded summary
preflight is an estimate, not an exact provider bill; actual rendered requests
are readmitted, and failed/cancelled calls retain an uncertain local envelope.
No provider calls or credential use occurred. Any paid A/B still requires
separate explicit endpoint/model/price/call/token/time/cost authorization.

Preparation B has begun after A acceptance. Work ownership is split among
validated backend profile/config consumers, Compose/browser secrecy and offline
script/CI consumers. Neither B nor Phase 12/13 is claimed complete yet.

Preparation B interim evidence (2026-09-18): the root template contains the
hard-renamed 29 flashcard settings, explicit flashcard/answer/embedding quota
buckets and separate disabled-by-default RAG profiles. The private
[migration guide](../../../docs/AI_PROFILE_MIGRATION.md) records drain, key
movement, root/process preflight, restart and snapshot compatibility; no actual
operator `.env` values were read, edited or logged. Active configuration,
provider, testing, privacy, setup and deployment guides were updated. The
Compose boundary now interpolates only the flashcard provider key into its
current generation worker, exposes nonsecret RAG metadata to the API and
rejects 30 removed names through a name-only guard. Independently tested
process-empty shadowing of an old nonempty root key can bypass Compose's
resolved interpolation, so the separate standard-library preflight checks
root/process sources independently and remains mandatory for operators.
No index/answer worker or paid request is claimed yet.

Subagent checks: complete frontend `npm run check` passed (4 Node, 26 component,
53 Chromium; one separately gated live reset skipped); synthetic Compose 5.5.1
base/development/production configuration and per-role secret isolation passed;
all 30 nonempty removed-key cases failed with fixed name-only errors and
absent/empty cases passed. Script/harness targeted checks: 4 new migration
preflight tests, 42 existing harness tests, bootstrap template validation and
`python scripts/check_ci.py` passed. The backend Settings/provider consumer
migration and combined full offline/journey checks are still in progress, so
these are not a B completion claim. Current context validation after the new
guide: 37 required files, 63 active guides, 820 local links passed. `git diff
--check` passed. No current application service or real provider was started.

Preparation B completion checkpoint (2026-09-18): all 29 prior `AI_*` settings
were hard-renamed to `FLASHCARD_AI_*`; the `GEMINI_API_KEY` fallback is removed.
Validated settings and a standard-library operator preflight reject all 30
nonempty removed names in root/process sources independently, with key-name-only
errors. Empty values, process precedence, unrelated root keys, disabled profiles,
role credentials/buckets, independent flags and existing queued generation
provider/model snapshots have focused negative tests. The live smoke guard
requires an explicit quota bucket before SDK construction. The deterministic
journey now supplies a local-only quota label. The future index/answer worker
secret-injection and job-snapshot contracts are defined; those workers/jobs are
not represented as current runtime functionality.

After the last B changes, the complete offline backend run passed: 607 passed,
50 service-gated skips and one live-AI deselection in 67.99 seconds. Frontend
`npm run check` passed (4 Node, 26 component, 53 Chromium; one separately gated
live reset skipped). Synthetic base/dev/production Compose isolation, 30
removed-key guard cases, 181 Python source-matrix cases, 4 standard-library
preflight tests, 42 harness tests, `check_ci.py` and context validation passed.
An initial journey attempt using system Python and sandboxed Docker failed
before services started: system Python lacked Alembic and sandboxed Docker
could not access the daemon. Rerunning the same disposable script with the
repository venv and authorized local Docker access passed the database proof
(generation, review, publication, enrollment, email, answer/progress) and
browser contract. It removed all owned test processes, containers, data,
fixture and generated credentials. No paid calls or operator configuration
were used. B checkboxes are checked as implemented contracts; future RAG worker
execution and index/answer job snapshots remain obligations in Phases 13/15/17.

Phase 12 started only after B's source and focused checks stabilized. Its
synthetic `subject_knowledge_v1` corpus and [evaluation guide](../../../docs/RAG_EVALUATION.md)
fix exact-search recall, authorization, publication, revision, abstention,
invalid-citation and injection cases before ranking/embedding tuning. The JSON
parsed and context navigation passed (37 required files, 64 guides, 826 links).
No retrieval implementation or remote-model quality is claimed by that fixture.

## Preservation and limits

Root `.env` values were not inspected or modified. Installation secrets,
populated databases/volumes, used migrations and prior historical logs remain
preserved. No commits/push/merge/deployment or destructive data operation was
performed. Preparation A/B are complete; Phase 12/13 remain in progress and
only genuinely verified tasks will be checked. Normal tests remain offline and
use injected settings.
