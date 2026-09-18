# Flashcard prompt, AI configuration and subject-scoped RAG plan review

Date: 2026-09-17 (operator timezone). Review only; implementation and plan edits
remain subject to the user's requested approval.

## Scope, starting state and preservation

User requested deep repository orientation, review of
`Cardchemy-Subject-Scoped RAG Implementation Plan.md`, recommendations for
flashcard prompt refinement and separate flashcard/RAG model configuration,
subagent support, and durable investigation evidence. The user explicitly
accepts existing `insufficient_grounded_cards` handling and does not request
loosening validation or partial-result persistence.

Starting branch: `main`. HEAD: `e10f5839735379e4277d35600067835f53272a89`.
Tracked tree was clean. The RAG plan was the only untracked user artifact.
Its SHA256 before evidence edits was
`AF530620C81712B2B626BE736E208EC3DAFE8B193F13DCCB9C57C3152EF3FD61`.

Read root instructions; `.agent/AGENTS.md` does not exist. Followed Start Here,
project/module maps, architecture/ADRs, current state/roadmaps, agent governance
and log index into affected source/tests and relevant historical logs. Applied
the existing memory orientation skill; current source and fresh commands, not
historical memory, establish conclusions below. Three independent read-only
subagents reviewed AI prompts/pipeline, configuration/runtime consumers, and
RAG security/data/privacy architecture. Root reviewed cross-stack contracts,
frontend workflows and integrated the evidence.

This is comprehensive review of the proposed change boundaries, not a claim
that every repository byte, unrelated test body, lock hash or artwork was read.
Secrets, generated artifacts, dependency trees and private/operator data were
excluded. No real `.env` inspection/edit, database operation, service startup,
provider call, branch/commit/push/merge or deployment occurred. Only this
evidence log and its nearest index are changed.

## Operator decisions received during review

1. Knowledge requires separate instructor review/publication before student
   access. Indexing `ready` does not publish a document. Knowledge publication
   remains independent of flashcard-set publication.
2. AI environment names change definitively, with mandatory migration guidance;
   no compatibility alias/deprecation period was selected. This supersedes the
   review's initial optional alias recommendation.

These decisions do not authorize editing the plan or implementing RAG. Overall
recommendations still await approval, as requested by the user.

## Current implementation verified from source

- Product is version 0.1.0. Maintained current state/roadmap record Phases 0-11
  complete and a separate operational readiness gate; this review does not
  refresh hosted/release or production status.
- FastAPI enqueues PostgreSQL work; a separate fenced generation worker does
  bounded page-preserving extraction, grounded structured AI generation and
  atomic complete draft-set/card/source-cleanup persistence. Email has its own
  worker/outbox. No RAG/embedding/pgvector implementation exists.
- Root `.env` is the sole user-managed file. Settings use nonempty process
  overrides, root file and defaults; Compose limits provider secrets to the
  generation worker, SMTP secrets to the email worker, and browser settings to
  the public allowlist.
- Cards require four distinct options, one matching answer, trusted chunk ID,
  normalized contiguous source quotation and full answer containment. Generated
  cards are unapproved; publishing/studying has separate approval/access guards.
- Job success requires exactly the requested number of distinct validated
  cards. Bounded refill exhaustion produces `insufficient_grounded_cards` and
  no partial set. One application provider retry owner and process-local
  concurrency/RPM/input-TPM admission remain necessary.

## Flashcard prompt findings and recommendations

| Finding | Current source evidence | Proposed response |
| --- | --- | --- |
| Quantity wording permits underproduction | `backend/app/ai/pipeline.py:274-295` asks for up to the batch target; `:707-711` requires exact global count; `backend/app/ai/contracts.py:110-111` allows empty batches | Ask for the target when supported by distinct evidence; explicitly forbid fabrication or cosmetic paraphrases to fill an impossible target. Keep legitimate underfill/failure. |
| Refill lacks memory | `pipeline.py:588-598`, `:645-660` reuse evidence/quota/summary without accepted-card exclusions or rejection feedback | Supply bounded accepted question/answer/concept exclusions and safe reason guidance as untrusted context. Version prompts. Include their bytes in packing/preflight. |
| Same-chunk requests can repeat facts | `pipeline.py:298-358`, `:663-676` split quotas and obtain siblings before validating accepted state | Evaluate repeated same-chunk and overlapping-source cases. Consider bounded topic partitions or same-source scheduling only if evidence requires a separately approved behavioral change. |
| Text-weight quotas can exceed fact capacity | `backend/app/ai/chunking.py:198-208`, `pipeline.py:649`, `:682-690` | Initially preserve allocation; measure exhausted/boilerplate chunks. Evidence-based refill redistribution is a separate pipeline decision, not a wording edit. |
| Grounding prompt needs precise evidence instructions | `backend/app/ai/grounding.py:55-70` | Choose a short exact answer span and a contiguous supporting quote before question/options. Reject stitched/ellipsis/paraphrased quotes. Summary guides navigation; original chunk supports the answer. |
| Educational quality checks are narrow | `grounding.py:64-73` mostly checks clarity shape and calculates answer/quote coverage | Request one clear fact, an unambiguous question and plausible parallel distractors. Instructor/corpus review measures pedagogy; do not present the numeric score as semantic quality proof. |
| Effective output cap is below the configured ceiling | `pipeline.py:593-595` uses `min(max, requested*512+256)` | Ten cards receive 5,376 output tokens even when max is 8,192. Prefer compact quotes/options and measure before changing caps. Truncated invalid JSON and valid underfilled output remain different failures. |
| Aggregate rejection count cannot explain dominant cause | `pipeline.py:689`, `:699`; `backend/app/workers/generation.py:510-511` records persisted accepted success count | Add bounded content-free reason/round/raw/grounded/distinct/missing counters and prompt version if approved. Preserve existing count semantics; never persist candidate bodies/prompts. |

An injected offline duplicate-only probe reproduced refill blindness: one fact,
target two, two refill rounds, three calls, three rejected candidates, requested
counts `[2, 1, 1]`, and byte-equivalent refill payloads without exclusions. The
expected quality failure remained intact. This proves a possible mechanism;
it does not establish the cause of the user's particular real document runs.

Current offline AI tests validate contracts and mechanics. The deterministic
provider adds artificial SHA256 serial markers to fronts
(`backend/tests/test_ai_pipeline.py:73-81`) and generic distractors, which can
make repeated facts appear distinct. No passing fixture establishes real-model
prompt yield or teaching quality. The existing live harness admits one pinned
OpenAI-compatible model, one call and no refills/retries; it is not a general
Gemini A/B evaluation runner.

Recommended separate workstream before RAG: realistic feasible/impossible-source
corpus and safe diagnostics, prompt refinement, bounded refill exclusions,
then measurement of exact-count success on feasible documents, accepted/raw
yield, reason categories, duplicates, refill use, coverage, instructor quality,
tokens/cost/latency. Keep grounding/security thresholds and impossible-source
failures. Expand prompts or change scheduling/limits only with corresponding
rendered-token/preflight contracts (`pipeline.py:368-490`). Live comparison needs
new explicit authorization and reviewed model-specific spending guards.

## Definitive AI configuration migration recommendation

The template has 29 `AI_*` settings (`.env.example:73-106`) and Settings retains
`GEMINI_API_KEY` fallback (`backend/app/config.py:167-174`). A template-only
rename is insufficient: `Settings` currently ignores unknown extras
(`config.py:86-91`) and all adapters/governor/pipeline/service/worker consumers
use current `ai_*` fields.

Recommended namespaces, with exact provider/model selection left for reviewed
capability/evaluation decisions:

| Namespace | Responsibility |
| --- | --- |
| `FLASHCARD_AI_*` | Existing flashcard generation model, connection, retry/rate/token/cost and generation-specific quality/packing controls |
| `RAG_AI_*` | Ask AI answer-generation model and its connection/request/rate/token/cost controls |
| `RAG_EMBEDDING_*` | Embedding provider/model/key/base URL/dimensions, compatible document/query tasks and batch/request/rate/cost controls |
| `RAG_ENABLED` | Overall product feature flag; explicitly define capture, admission, retrieval and worker behavior when off |

Use `*_PROVIDER_ENABLED`, preserving the established `ENABLED` convention.
Embedding is a separate capability even if it shares a provider account/key
with answer generation. Do not silently inherit flashcard credentials or copy
flashcard-only refill/card-count/summary settings into RAG.

For the chosen hard rename: add safe fail-fast detection of nonempty removed
`AI_*` names and legacy `GEMINI_API_KEY` in supported configuration sources,
reporting key names/fixed migration guidance only, never values. Define and test
empty/process/root precedence and disabled-profile validation. Do not turn on
global extra-forbid in a shared root file containing other components' settings.
Remove active fallback behavior and migrate fixtures/harness injection together.

Provide a mandatory key mapping and drain/restart/recreate procedure. Do not
regenerate signing/encryption/database secrets or overwrite the real `.env`;
bootstrap refuses overwrites and is not a migration tool. API response fields
and DB `ai_provider`/`ai_model` columns can remain unchanged; the env rename alone
does not justify rewriting migration history or breaking typed API contracts.
Preserve queued/manual-retry provider/model snapshots. Current endpoints/keys
are not snapshotted, so incompatible account changes require draining/cancelling
existing work.

Consumers to update together: settings/validators/safe messages, providers,
pipeline/governor, generation service/worker, Compose anchors and explicit
per-service secret lists, bootstrap template consumers, test injection and
live guards, journey/image/security/production-rehearsal harnesses, frontend
secrecy assertions, current configuration/provider/evaluation/testing/setup
guides and context navigation. Historical log bodies and used migrations remain
historical evidence.

## RAG plan: phase-by-phase review

| Existing phase | Recommendation before implementation |
| --- | --- |
| 12: Foundation/runtime | Add architecture ADR and configuration/enablement contracts. Decide that pgvector runtime is mandatory even when the feature is off, or explicitly design an optional supported profile. Never make migrations depend on arbitrary env flags. Complete PostgreSQL image inventory, privileges, digest/version and DB security/SBOM ownership. |
| 13: Knowledge model | Separate index state from approved/published visibility. Add bounded durable indexing jobs or equivalent complete claim fields; extraction/chunker/embedding/corpus revisions; FK subject integrity across documents/jobs/sets/chats/citations; deliberate ON DELETE rules. Avoid redundant document/job association cycles. |
| 14: Capture | Use the smallest shared page/chunk preparation seam with validated precomputed chunks; preserve local flashcard ID contracts and map separately to persistent UUID chunk IDs. Persist complete knowledge and enqueue indexing in one short lease-fenced transaction before PDF cleanup, independently of flashcard result success. Specify capture failures and post-capture cancellation outcome. |
| 15: Embeddings/indexing | Define embedding-space identity beyond dimensions. Validate count/order/finite vectors and document/query task compatibility. Batch and budget calls; fenced revision-aware persistence; stage rebuild/reembedding and atomically activate compatible revisions. Do not expose mixed old/new vectors. |
| 16: Retrieval | Carry trusted principal/access context. Apply subject, current Knowledge publication, ready/active revision and document filters inside lexical/vector SQL. Query embeddings remain worker-side. Establish exact filtered search baseline and evaluate approximate filtered recall before choosing ANN tuning. Bound top-K/context, deduplicate overlap and derive provenance server-side. |
| 17: Ask AI backend | Authorize every thread/message/job/poll/retry/delete/source endpoint by current principal and actual subject. Recheck access/visibility before expensive work and finalization. Bound/race-protect quotas, storage, thread/history size, retries, cancellation and job deadlines. Atomically commit answer/sources/status with one logical result. Add claim/evidence support association and explicit abstention; valid chunk IDs alone are insufficient. |
| 18: Frontend | Knowledge review/publish/unpublish and sanitized capture/index state, separately from sets. Define unavailable/cancelled/abstained answers, reload recovery, stable retries, bounded nonoverlapping polling, keyboard/focus/live regions and English catalog copy. Render model text safely; raw HTML/unsafe links cannot become trusted UI. Citations may show authorized extracted evidence without a raw-PDF viewer. |
| 19: Evaluation | Establish authored retrieval/answer corpus and acceptance metrics before retrieval/prompt tuning. Measure recall/ranking, supported claims, abstention, citations, cross-subject/visibility attacks, reindex/deletion races, latency and usage. No paid calls in ordinary CI; live evaluation stays explicitly bounded/approved. |
| 20: Regression/security/CI | Run relevant checks in every phase; retain this phase as final integrated gate. Add configuration combinations, SQL-filter recall, ownership/publication, stale workers, quota races, indexing/answer idempotency, citation deletion and portable offline model tests. RAG journey must publish Knowledge independently before student Ask AI. |
| 21: Privacy/operations/rollout | Decide data/provider disclosure, exports/deletion/draining and retention before first persistent writes, then verify them here. Extend actual privacy CLI, closed diagnostic codes/events, audit actions, worker kinds/health/table constraints and content-free metrics. Restore populated vector/text/chat fixtures and verify active indexes/retrieval, not extension availability alone. |

## High-priority cross-file contracts and conflicts

1. **Student visibility:** `SubjectService.check_subject_access()`
   (`backend/app/services/subject.py:228-293`) authorizes ownership/enrollment,
   not publication. Study separately checks publication/approval
   (`backend/app/routers/study.py:59-62`, `:124-129`). Retrieval of every ready
   document would therefore expose source materials from draft/failed sets.
   Apply the confirmed independent Knowledge publication policy to retrieval,
   citations, queued/running finalization and history reads. Indexing never
   publishes automatically; transitions receive transactional audits.
2. **Independent capture:** `_finish_success()`
   (`backend/app/workers/generation.py:467-523`) executes after complete card
   success and deletes the source atomically. Knowledge written only there
   would be lost on card failure. Separate capture must validate lease/cancel
   (`:204-227`), persist/enqueue once, and recover crash-after-capture safely.
   Capture failures, not only embedding failures, need an isolated outcome;
   source cleanup may make reupload necessary if no durable capture succeeded.
3. **Independent enabled lanes:** worker `run()` exits into disabled heartbeat
   behavior when flashcard AI is off (`workers/generation.py:78-89`). Simply
   appending RAG polling would couple the features. Reuse worker primitives with
   role-aware bounded scheduling, reserved capacity and separate health/admission.
   Different configuration prefixes do not imply different provider account
   quotas: shared account/project limits need shared admission or divided
   budgets; process replicas retain current distributed-governance limits.
4. **Citation/history lifecycle:** document deletion must preserve flashcards,
   detach job/set links, remove knowledge and prevent stale workers restoring
   it. Decide invalidation/redaction or tightly authorized version/tombstone
   behavior for retained answers derived from removed/unpublished material.
   Citation-row cascade alone leaves answer content; restrictive FKs can instead
   block the promised document deletion. Corpus revision fences and atomic
   reindex cutover are necessary.
5. **Answer grounding:** citation membership must be against the exact retrieved,
   authorized active revision, not any globally existing chunk. Real but unrelated
   citations can still accompany false claims. Add claim/evidence associations or
   validated quote spans plus semantic support evaluation and abstention. Do not
   claim deterministic ID/quote checks prove arbitrary prose semantically true.
6. **Privacy implementation:** extend snapshot exports, deletion locks/refusal,
   cascades/cleanup/drain to knowledge, conversations and new active jobs
   (`backend/app/services/privacy.py:49-227`). An instructor's export must not
   include other students' chats. Forbid all chat/document/prompt/embedding/model
   content in logs, rather than the plan's conditional wording. Disclose query
   and history transfers as well as embedding/generation transfers.
7. **Runtime inventory:** unconditional extension migration requires extension
   binaries/privileges in all databases, including RAG-off environments. Plan
   omits `scripts/test_smtp_tls.py:112` and
   `backend/tests/postgres/test_postgres_startup_probe.py:53`, which independently
   launch vanilla PostgreSQL 16. DB scans/provenance are outside current app-only
   image lists (`.github/workflows/ci.yml:224-233`, release SBOM workflow). Native
   PostgreSQL operators and populated backup/restore also need explicit support.
8. **Storage/reupload:** existing quotas bound transient PDFs/generation, not
   permanently retained pages/chunks/vectors/chat. Add permanent capacity caps.
   Historical-source reupload solely for Knowledge currently forces another
   generation job with AI enabled/quota charges. Decide knowledge-only upload
   versus intentional regeneration; specify within-subject duplicate/version
   policy without cross-subject hash/existence leakage.

## External technical verification

Reviewed primary documentation during this task:

- [pgvector](https://github.com/pgvector/pgvector): PostgreSQL 16 builds/images
  exist; choose reviewed exact artifacts rather than assuming compatibility.
  HNSW/IVFFlat indexing of `vector` supports up to 2,000 dimensions and `halfvec`
  up to 4,000. Approximate scans with WHERE filtering can under-return matches;
  use filtered exact baseline and measured iterative-scan/fallback policies.
  This planner behavior does not authorize application-level global retrieval
  followed by filtering or removal of SQL subject/visibility predicates.
- [pgvector Python](https://github.com/pgvector/pgvector-python): SQLAlchemy and
  asyncpg integration require reviewed types/connection registration. Retain
  an explicit portable offline fixture strategy; SQLite is not vector-query proof.
- [PostgreSQL extension installation](https://www.postgresql.org/docs/16/sql-createextension.html):
  extension files and appropriate installation permissions are prerequisites.
- [PostgreSQL full-text query controls](https://www.postgresql.org/docs/16/textsearch-controls.html):
  lexical query construction/configuration and ranking need a bounded contract.

No embedding/chat model or provider-price recommendation was guessed or paid
evaluation performed. Image/package versions are implementation-time verification
items, not approved defaults from this review.

## Verification actually executed

| Check | Result / limit |
| --- | --- |
| Initial system Python offline attempt | Failed before collection: missing `alembic.script`. Non-evidence for behavior. Recovered by using documented existing backend development venv; no dependencies changed. |
| Focused offline AI suite, subagent | `backend/venv/Scripts/python.exe -m pytest tests/test_ai_chunking.py tests/test_ai_grounding.py tests/test_ai_pipeline.py tests/test_ai_evaluation.py tests/test_ai_providers.py tests/test_ai_rate_limit.py -q`: 42 passed in 4.67 seconds. |
| Bounded injected refill probe, subagent | Reproduced duplicate refill/identical payload mechanism without provider network traffic; described above. Not a real-document/provider diagnosis. |
| Full backend offline suite, root | From backend, `venv/Scripts/python.exe -m pytest -q`: 376 passed, 50 skipped, 1 deselected in 64.25 seconds. Skips are service/environment gates; live AI is deselected. |
| Context baseline, root | `backend/venv/Scripts/python.exe scripts/check_context.py`: 37 required files, 61 active guides, 787 local links passed before evidence additions. |
| Final context check | Passed after evidence additions: 37 required files, 61 active guides, 788 local links. Historical bodies/external URLs are excluded; this is navigation validation, not runtime proof. |
| Final diff/preservation checks | `git diff --check` passed. Only the log index and new review log are changed/added. Plan SHA256 remains identical to the recorded starting hash. Git reports a normal LF-to-CRLF conversion advisory for the index. |

No frontend `npm run check`, PostgreSQL service/migration suite, email/TLS service
suite, real journey, Docker/image/security/SBOM build, hosted CI, manual assistive
technology or live-provider test was run. No implementation changed. These
remain required at their respective future change scopes; prior logs are not
fresh validation of proposed RAG behavior.

## Reading coverage and boundaries

- Root guide, Start Here/project map/backend/frontend maps, all architecture
  flow documents, ADR index and relevant accepted card/schema/deletion/grounding/
  configuration/jobs/session/email/privacy decisions, current state and roadmap.
- Agent governance/map/index and relevant Phase 3/4, provider enablement/retry,
  request efficiency, Phase 9 and Phase 10 logs; release/state evidence consulted
  for orientation without asserting freshly checked remote status.
- Every active AI/agent module (ten files), AI contracts/chunker/grounding/
  pipeline/providers/governor and focused AI fixtures/tests/live guard; generation
  worker/PDF preparation and relevant service/model/persistence/failure contracts.
- Subject/study/auth access boundaries, persisted relationship/migration
  contracts, privacy/audit/operations/health/shutdown paths and relevant tests.
- Configuration/Compose/bootstrap/public-loader, runtime/dependency/database/
  deployment/evaluation/testing guides, test/image/security/rehearsal consumers
  and CI/release workflow inventories. Some peripheral files were searched for
  consumers or read in excerpts; this is not represented as whole-body reading.
- Frontend routes/auth/typed services, generation reservation/upload/poll/retry/
  telemetry, instructor review/publication, student subject/study flow, shared
  dialog/feedback/citation-like source rendering, accessibility/localization and
  relevant browser/journey fixture contracts. No RAG UI was created.
- Full supplied RAG plan, including phases 12-21, backfill, exclusions, final
  target architecture and definition of done.

## Remaining decisions and approval boundary

Recommended next ordering is a separate measured flashcard-quality workstream,
definitive profile migration, RAG architecture/privacy/data-policy decisions,
then the existing foundation/capture/index/retrieval/Ask AI phases with tests at
each phase. Privacy design/evaluation corpus move earlier; final operational
verification remains a rollout gate.

Before implementation, settle post-capture cancellation, answer/history behavior
after document delete/unpublish/reindex, conversation retention, knowledge-only
upload/version behavior, selected embedding-space/model/index representation,
pgvector installation support and provider quota topology. These can be explicit
design gates in an approved revised plan; no current default is silently chosen.

The user still must approve the recommendations before the plan is updated.
The plan and application/runtime configuration remain untouched.
