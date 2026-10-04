# Backend Map of Content

## Current local Lane 6 closure — 2026-10-04

The local source-only v8/visual-v5/admission-v2 installation on head `0033`
is enabled after its measured quality, PDF/display and release gates. Fresh
installations remain default-off. See the
[closure and activation evidence](../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md). Earlier installation
checkpoints below remain historical snapshots; the linked closure supersedes
their off/pending status, while default-off and upgrade safeguards still apply.

The [published sparse control](tests/postgres/test_postgres_sparse_generation_control.py)
uses the [guarded focused runner](../scripts/test_sparse_generation_control.py)
to validate a whole authored PDF through real persistence/publication and exact
target choice with offline providers. See
[evidence and scope](../.agent/logs/2026-10-03/2026-10-03-published-sparse-whole-pdf-control.md).

The prospective v8 path binds [visual-v5](app/ai/source_judgment_visual_v5.py),
[admission-v2](app/services/rag_question_context_v2.py),
[preparation-v5](app/services/source_visual_preparation_v5.py) and
[migration 0033](alembic/versions/20261002_0033_visual_clarity_policy.py).
Provider-free [hybrid](scripts/prepare_private_navigation_v8.py) and
[seed](scripts/prepare_private_navigation_seed_v8.py) diagnostics retain frozen
inputs and SQL authorization; they do not prove private display or enable Ask.
See [current completion work](../.agent/logs/2026-10-03/2026-10-03-v8-completion-work.md).

Inert [visual-v4](app/ai/source_judgment_visual_v4.py) and
[context-v2](app/ai/source_navigation_context_v2.py) correctness prototypes
leave the retained v7 worker unchanged. Their
[dated evidence](../.agent/logs/2026-10-02/2026-10-02-candidate-local-and-question-clarity-repair.md)
distinguishes pure parser/clarity proofs from provider and release results.

## Dormant retained v7 integration — 2026-10-02

Checkout source head is `20261002_0032`, required policy v7 / visual-v3.
The [admission service](app/services/rag_question_context.py),
[context model](app/models/rag.py) and [additive migration](alembic/versions/20261002_0032_literal_subject_context.py)
bind exact current/strictly preceding user identities, hashes, timestamps and
literal offsets atomically. [Enqueue/retry](app/services/rag_answers.py) and
[worker](app/workers/rag_answer.py) consume the immutable binding. The
[v3 preparer](app/services/source_visual_preparation_v3.py) and
[provider](app/ai/providers/source_visual_v3.py) retain raw-question embedding,
project only a bounded literal subject when needed, and recheck access/context
after quota waiting immediately before HTTP. Typed profile/disclosure matches.
Retained installation is now v7/0032 with healthy matching services and a
120-second source-judge deadline; Ask and source judging remain disabled.
See [current cutover and passing checks](../.agent/logs/2026-10-02/2026-10-02-v7-retained-cutover-and-release-recheck.md)
for completed technical checks and open quality/release gates. The dated
preparation sections below are earlier snapshots.

The [private fresh guard](scripts/private_visual_dispatch_guard_v7.py) binds
the reviewed request to current authorized text/PDF/revisions. Callers own
separate fresh read-only transactions, SQL deadlines and callback cancellation.
The [provider-free rehearsal](scripts/rehearse_private_visual_dispatch_v7.py)
uses production guards and authenticated rendering without AI credentials.
The [keyless planner](../scripts/prepare_private_visual_trial_v7.py) and
[mock-only caller](../scripts/run_private_visual_trial_v7.py) provide prospective
input/budget and custody checks; neither authorizes private transfer or activation.

## Inert literal subject-context preparation — 2026-10-02

The [pure context helper](app/ai/source_navigation_context_v1.py) reads no
settings/provider/database. Ten private questions remain raw-clear; two
follow-ups match independently frozen literal subjects from the immediately
preceding user turn. Its [offline contracts](tests/test_source_navigation_context_v1.py)
cover exact hashes/offsets, ambiguity, untrusted text and no older-turn fallback.
This helper is not consumed by the retained worker. Future integration must
snapshot the strictly preceding user message under admission locking and
revalidate identity/access/expiry; provider transfer needs a new explicit
envelope and disclosure. See the [dated evidence](../.agent/logs/2026-10-02/2026-10-02-literal-subject-context-preparation.md).

The separate [inert visual v3 contract](app/ai/source_judgment_visual_v3.py)
binds local current/preceding message identities, raw-question clarity and
UTC lifetimes before creating a provider wire. Clear questions keep the v2
wire; unresolved follow-ups may add only the validated literal subject and
trusted referent-purpose statement. Its [offline tests](tests/test_source_judgment_visual_v3.py)
do not establish SQL ordering or runtime authorization. The retained worker,
Settings, source-provider adapter and migration head still use v6/v2/0031.

## Historical dormant visual Ask contract — 2026-10-01

Source head is `20261001_0031`; the retained installation reached `0031`
after its restore-verified forward cutover. Ask stays disabled. The
prospective `related_knowledge_navigation_v6` / `hybrid_source_navigation_v9`
path uses [visual contract v2](app/ai/source_judgment_visual_v2.py): the same
Gemini 3.5 Flash-Lite HIGH-thinking prompt, exact authorized text/cues and
faithful bounded page PNGs, with 32,768 input / 4,096 output tokens including
thinking and a 60-second deadline. It allows at most one query embedding and
one ID/category-only judgment, with no answer/verifier call or automatic retry.
V6 selects the bounded adaptive full-page renderer: start at 1,600 pixels and
reduce to 1,400/1,200/1,000 only after definitive PNG oversize, retaining the
same 1 MiB/2 MP guards, one 30-second page deadline and truthful scale metadata.

Installed `0030`, historical v5 / `visual_source_id_v1`, and its 2,048-token
snapshots remain immutable and readable. New workers and manual retry cannot
replay those jobs as v6. The additive `0031` preserves grants, revision and
parent-stage/reference guards and extends one-attempt constraints to v6;
downgrade refuses existing v6 snapshots. The runtime activation fence remains
closed pending independent public/private and release gates. The prospective
usefulness floor is 80%; fabricated, unauthorized, stale or wrong-page
references still require zero. Earlier v4/v5 sections below are historical.

The current [v7 private preparer](scripts/prepare_private_navigation_v7.py)
and [signed-review bridge/scorer](../scripts/score_private_source_display_v7.py)
prepare current authorized visual-v3 inputs without provider calls and bind
new runtime/question-context/request identities to 44 unchanged signed slots
and four freshly reviewed changed slots. The
[raw-query projection](../scripts/navigation_raw_query_projection_v1.py) checks
raw clarity from SHA-pinned pure production functions without Settings imports;
the scorer also binds issued aliases to reviewed UUID/page/revision identities.
Diagnostic admissions are simulated frozen-case inputs; actual SQL
admission remains separate. Changed source parts require fresh review.
See [current input evidence](../.agent/logs/2026-10-02/2026-10-02-private-v7-hybrid-input-verification.md).

The pure [private v6 display metric](../scripts/score_private_source_display_v6.py)
and [its keyless contracts](tests/test_private_source_display_v6_score.py)
apply the accepted 80% floor to all displayed cards and preserve complete
independent case/candidate reviews, hit/form, source-integrity and one-call
budgets. A synthetic/component pass neither proves actual displays nor
activates the worker; the old v4 scorer and its evidence remain unchanged.

The [private v6 query preparer](../scripts/prepare_private_query_vectors_v6.py)
and [synthetic native transport contracts](tests/test_private_query_vectors_v6.py)
bind the twelve current questions and compatible source snapshot, preserve
private checkpoints and enforce fresh authorization/no replay. Preparation
makes no provider or database call; real vectors and hybrid/display measurement
remain separate from this offline helper and the older eleven-case builder.
The [inert outer caller](../scripts/run_private_query_vectors_v6.py) and
[its synthetic contracts](tests/test_private_query_vectors_v6_caller.py)
add fresh UUID/code/profile pins, isolated embedding-only Settings, durable
aggregates and the suspended four-CPU/two-GiB hard-deadline worker fence.

The [private hybrid-input preparer](scripts/prepare_private_navigation_v6.py)
and [synthetic contracts](tests/test_private_navigation_v6_preparation.py)
bind externally supplied current-query vectors to production retrieval,
authorized current pages and exact visual inputs in a read-only transaction.
Default execution is inert; explicit preparation rejects AI credentials and
enabled Ask, requires finite four-CPU/two-GiB cgroups and an outer hard
300-second deadline. It does not call a provider, commit data or grade displays.

Current code map updated: 2026-10-01. This is navigation, not an API specification.
Start with [project orientation](../docs/00-START-HERE.md) and the
[project map](../PROJECT-MAP.md).

[Visual contract v2](app/ai/source_judgment_visual_v2.py) is wired to the
prospective v6 worker. It does not reinterpret retained v5 / visual-v1 data
or activate Ask; public, private and release gates remain open.


## Entry points

| Entry | Responsibility |
| --- | --- |
| [app/main.py](app/main.py) | FastAPI factory, lifespan migration verification, CORS, routers and health endpoints. |
| [app/database.py](app/database.py) | Async SQLAlchemy engine/session dependency, rollback cleanup and Alembic-head verification. |
| [app/worker.py](app/worker.py) | Generation-worker process entry. |
| [app/email_worker.py](app/email_worker.py) | Email-worker process entry. |
| [app/index_worker.py](app/index_worker.py) | Independent Subject Knowledge embedding/index-worker process entry. |
| [app/answer_worker.py](app/answer_worker.py) | Independent source-only Subject Ask AI query-embedding/source-ID-judge worker process entry; v7 visual execution remains fenced. |
| [app/cli.py](app/cli.py) | Operator bootstrap/email retry, content-free diagnostics/audits, private export, explicit account deletion, bounded retention and optional aggregate reporting. |
| [app/config.py](app/config.py) | Validated settings from process environment and the sole root `.env`; test mode suppresses file loading. |

## Main areas

| Area | Responsibility |
| --- | --- |
| [app/routers/](app/routers/) | Auth, subjects/sets/invitations, flashcard CRUD, generation jobs, private Subject Ask AI, enrollment-scoped published-lecture browse/PDF range, and study HTTP contracts. |
| [app/services/](app/services/) | Auth/session/invitation logic, content CRUD, progress/idempotency, generation/Ask AI lifecycle and quotas, authorized retrieval, PDF extraction/storage and email composition. |
| [app/schemas/](app/schemas/) | Pydantic request/response validation. Student study cards have a separate answer-free response. |
| [app/models/](app/models/) | SQLAlchemy application, operational and Subject Knowledge tables; database constraints and foreign-key ownership. |
| [app/observability.py](app/observability.py), [app/services/operations.py](app/services/operations.py) | Closed JSON logs/errors, request/job correlation, retained metrics and local/durable loop heartbeats. |
| [app/services/privacy.py](app/services/privacy.py), [app/services/audit.py](app/services/audit.py) | Consistent allowlisted export, guarded explicit deletion, bounded metadata expiry and fixed-field transactional audits. |
| [app/workers/](app/workers/) | Generation/email/index/answer claiming, leases, fencing, retention and graceful shutdown. |
| [app/ai/](app/ai/) | Gemini-only versioned text catalog/preflight, provider-neutral generation pipeline, strict embedding contract, shared page-aware preparation, versioned prompts, grounding and worker-wide quota admission. |
| [app/agents/graph.py](app/agents/graph.py) | Active `ainvoke` compatibility facade used by the generation worker; delegates to `FlashcardGenerationPipeline`, without LangGraph. |
| [alembic/](alembic/) | Sole deployed schema evolution mechanism; source and retained head `20261002_0032` require PostgreSQL 16/pgvector 0.8.6. Source-only terminal/reference limits, parent-stage policy/attempt binding, canonical-page offsets, immutable historical snapshots, original-PDF archive guards and admission-context constraints preserve authorization and history. Retained heads/drift passed with Ask disabled; see [database operations](../docs/DATABASE_OPERATIONS.md). |

## Common change paths

- Prospective visual source-only Ask: [ai/source_judgment_visual.py](app/ai/source_judgment_visual.py)
  is a pure exact cue/image/issued-ID contract. The complete worker archive
  reader in [services/knowledge_pdf.py](app/services/knowledge_pdf.py) authenticates
  all blocks before rendering; it grants no access. These helpers and the versioned v2 completion ceiling are connected to the dormant v6 worker through
  [services/source_visual_preparation.py](app/services/source_visual_preparation.py)
  and [ai/providers/source_visual.py](app/ai/providers/source_visual.py); the
  isolated renderer is [services/knowledge_pdf_renderer.py](app/services/knowledge_pdf_renderer.py). Public calibration and matching
  application/private/release gates remain separate.

- Authentication: [routers/auth.py](app/routers/auth.py) →
  [services/auth.py](app/services/auth.py) →
  [services/passwords.py](app/services/passwords.py) / [models/user.py](app/models/user.py),
  with [frontend auth](../frontend/MOC.md) and [auth flow](../docs/architecture/AUTH-FLOW.md).
- Subjects, manual cards and publication: [routers/subjects.py](app/routers/subjects.py) /
  [routers/flashcards.py](app/routers/flashcards.py) →
  [services/subject.py](app/services/subject.py) /
  [services/flashcard.py](app/services/flashcard.py) → schemas/models and publication triggers.
- PDF generation: [routers/generation.py](app/routers/generation.py) →
  [services/generation.py](app/services/generation.py) →
  [workers/generation.py](app/workers/generation.py) → graph facade →
  [ai/pipeline.py](app/ai/pipeline.py) → atomic result persistence.
  [services/candidate_storage.py](app/services/candidate_storage.py) encrypts
  fully validated cards for a finite owner-private exact smaller-target choice;
  the route does not return staged card content.
  Read [AI generation flow](../docs/architecture/AI-GENERATION-FLOW.md).
- Flashcard prompt quality: [ai/prompts.py](app/ai/prompts.py) renders versioned
  map/reduce/generation prompts and bounded untrusted refill exclusions;
  [ai/grounding.py](app/ai/grounding.py) enforces trusted evidence and duplicates;
  the pipeline reports fixed content-free per-round diagnostics. Read
  [AI evaluation](../docs/AI_EVALUATION.md) for offline evidence and live limits.
- Native Gemini selection: [ai/gemini_catalog.py](app/ai/gemini_catalog.py)
  closes the Flashcard text-model list and historical Ask text policies;
  [config.py](app/config.py) checks configured model, thinking and budgets;
  new Ask work snapshots only its embedding/source policy. The separate
  Ask gate and old-policy fence leave history/source reads and Knowledge work
  available. Read [provider operations](../docs/AI_PROVIDERS.md) and
  [Ask shutdown](../docs/ASK_AI_SHUTDOWN.md).
- Historical v4 text source judging: [ai/source_judgment.py](app/ai/source_judgment.py)
  defines its bounded issued-ID contract. Dormant v7 visual judging uses
  [ai/source_judgment_visual_v3.py](app/ai/source_judgment_visual_v3.py), retaining
  [historical v2](app/ai/source_judgment_visual_v2.py) and
  [historical v1](app/ai/source_judgment_visual.py);
  [services/rag_answers.py](app/services/rag_answers.py) snapshots the separate
  judge identity/prices; [workers/rag_answer.py](app/workers/rag_answer.py)
  fences one query embedding and at most one source-ID request before deriving
  exact current page references. Source and retained head are `0032`; Ask stays disabled
  until public, private, access and release gates pass.
- Study: [routers/study.py](app/routers/study.py) → `FlashcardService` answer
  resolution, receipt reservation and row-locked progress mutation →
  [models/flashcard.py](app/models/flashcard.py).
  Read [study/progress](../docs/architecture/STUDY-PROGRESS-FLOW.md).
- Recovery/invitation email: auth/subject transaction →
  [services/email.py](app/services/email.py) outbox →
  [workers/email.py](app/workers/email.py) SMTP delivery.
  Read [email operations](../docs/EMAIL_DELIVERY.md).
- Schema changes: models + a new [Alembic revision](alembic/versions/) +
  [PostgreSQL regressions](tests/postgres/) + [data model](../docs/architecture/DATA-MODEL.md).
- Subject Knowledge: [models/knowledge.py](app/models/knowledge.py),
  [migration `0011`](alembic/versions/20260919_0011_rag_capture_indexing.py),
  [capture](app/services/knowledge_capture.py),
  [index operations](app/services/knowledge_indexing.py),
  [index worker](app/workers/knowledge_index.py) and
  [authorized retrieval](app/services/knowledge_retrieval.py) implement private
  capture, exact-space indexing, explicit cutover and exact hybrid retrieval.
  [knowledge_lock.py](app/services/knowledge_lock.py) orders deletion/capture/
  indexing/final-answer writes. Phase 17 adds [private Ask AI models](app/models/rag.py),
  [HTTP contracts](app/routers/rag.py), [admission/history](app/services/rag_answers.py),
  historical [strict answer validation](app/ai/answering.py), migration
  [`0012`](alembic/versions/20260919_0012_subject_ask_ai.py) and the
  [fenced answer worker](app/workers/rag_answer.py). Read the
  [Knowledge flow](../docs/architecture/SUBJECT-KNOWLEDGE-FLOW.md).
  Phase 18 adds owner-only [Knowledge management](app/services/knowledge_management.py)
  and [routes](app/routers/knowledge.py). Phase 19 evaluation lives in the
  [authored v2 corpus](tests/fixtures/rag_eval/subject_knowledge_v2.json),
  [metric support](tests/support/rag_evaluation.py) and actual PostgreSQL
  retrieval cases; its separately gated live harness is under
  [integration tests](tests/integration/test_live_rag_evaluation.py).
  Phase 20/21 closure adds native Gemini embedding/answer profiles and
  operational metadata in
  [`0013`](alembic/versions/20260920_0013_rag_phase20_21_closure.py).
  Lane 0/1 adds Ask diagnostics and policy snapshots in
  [`0014`](alembic/versions/20260922_0014_product_quality_shutdown_diagnostics.py).
  Lane 6 adds [exact related-Knowledge selection](app/ai/related_evidence.py)
  and [job-owned references](app/models/rag.py) under
  [`0021`](alembic/versions/20260925_0021_rag_related_evidence.py). The
  [source-only revision `0022`](alembic/versions/20260926_0022_related_knowledge_only.py)
  adds related/no-match terminal kinds without assistant answer messages.
  [`0023`](alembic/versions/20260926_0023_source_stage_parent_policy.py) binds
  source-only stage policy and attempt identity to its parent job. The historical
  [source-sufficiency selector](app/ai/source_sufficiency.py) preserves question
  relation and exact unit offsets. Its canonical-page policy can select a contiguous
  owning slide title plus bullet from the authorized canonical page after
  matching its discovery chunk body and section. Entity, predicate, qualifier
  and second-subject guards still apply. The approved v7
  [structural grammar](app/ai/source_structure.py) recognizes explicit question
  roles, source relation labels/lists/examples and source-attested aliases;
  independent displayed-window quality remains unproved.
  [`0024`](alembic/versions/20260927_0024_canonical_page_references.py) records
  explicit page-versus-chunk offsets, with current-source insertion/read guards.
  [`0025`](alembic/versions/20260927_0025_structural_source_policy.py) fences new
  page references to v7 while preserving v6 reads; downgrade refuses retained
  v7 job snapshots. The
  [authorized retriever](app/services/knowledge_retrieval.py)
  supplies a new immutable candidate policy and bounded same-document
  eligible neighbor inspection. The retained stack has not enabled this
  historical selector; independently reviewed displayed-window quality remains a release gate.
  The [aggregate display scorer](../scripts/score_source_first_display.py)
  retains the original public gate and supports a separately reviewed,
  fingerprint-bound private `X##` holdout registration before measurement;
  it rejects incomplete labels and earlier exposed-page reuse.
  The
  [Ask service](app/services/rag_answers.py) reconstructs exact current excerpts
  and extracted pages under authorized source reads, separately from historical
  verified message citations. Ask activation still awaits its release gate.
  [Private gold alternatives](../scripts/refine_private_source_holdout.py) retain
  rejected owner labels and fixed questions while offering source-exact context
  for separate excerpt/page review; this discovery is not a runtime score.
  The [extractive acronym experiment](app/ai/extractive_support.py) is a
  provider-free research candidate; the runtime worker does not select it.
  The [larger local verifier evaluator](../scripts/evaluate_larger_local_support.py)
  compares isolated public NLI/QA artifacts and fixed, content-free private
  verdicts against the maintained corpus; its experimental budget does not
  replace the runtime release gates.
  The [local relation classifier](../scripts/local_relation_candidate.py) and
  [isolated evaluator](../scripts/evaluate_local_relation.py) test one pinned
  public instruction-model export under a separately approved experimental
  budget. They bind exact source units, emit only aggregate decisions and
  remain outside the Ask worker factory. The
  [public adversarial controls](tests/fixtures/rag_eval/local_relation_adversarial_v1.json)
  are development evidence, not a reviewed private holdout.
  The [public calibration audit](../scripts/calibrate_local_relation.py)
  measures the same pinned instruction candidate with a preregistered public
  selection rule and separately reviewed heldout cases. It never reads private
  Knowledge, changes runtime thresholds or selects the worker policy.
  The [approved 4B candidate](../scripts/local_relation_4b_candidate.py) and
  [supervised public audit](../scripts/calibrate_local_relation_4b.py) use the
  same frozen fixture/procedure under a separate experimental resource ceiling.
  The [public artifact downloader](../scripts/download_local_relation_4b.py)
  validates immutable bytes without importing operator settings; the audit
  strips operator credentials and enforces hard startup/whole-run limits.
  These paths remain outside runtime selection and release claims.
  The [real-query retrieval diagnostic](../scripts/evaluate_private_query_retrieval.py)
  makes zero provider calls by default. Separately authorized execution embeds
  six authored questions in one native request, keeps the installed query task
  and active space unchanged, and emits only read-only retrieval aggregates.
  The [private query-vector packet builder](scripts/build_private_query_vectors.py)
  preflights the frozen eleven published-source questions and active embedding
  profile without database or provider access. Its separately approved one-shot
  mode writes only a guarded private packet for the
  [source-navigation diagnostic](scripts/diagnose_source_navigation.py).
  The [public Knowledge holdout preflight](scripts/preflight_public_knowledge_holdout.py)
  checks two SHA-frozen, attributed OS-Temp PDFs against current extraction,
  chunking and a bounded embedding envelope without provider or database access.
  The [independent source-page review builder](../scripts/build_private_source_holdout.py)
  defaults to provider-free preflight; explicit creation writes an owner-private
  packet without assigning quality labels or measuring runtime ranking. The
  [displayed-window probe](../scripts/evaluate_private_source_display.py) defaults
  to a no-database/no-provider design preflight. Executing it requires frozen
  reviewed cases and a fresh approved embedding envelope; canonical alignment
  alone is not actual page-open or owner-reviewed displayed-window proof.
  Lane 3 extends the shared [generation service](app/services/generation.py),
  [HTTP route](app/routers/generation.py) and [generation model](app/models/generation.py)
  with a durable post-upload exact-byte choice, explicit revision no-op and
  source/quota cleanup. Migration
  [`0015`](alembic/versions/20260922_0015_knowledge_duplicate_choice.py) adds
  the scoped candidate, pending state and typed outcomes. Reuse links an
  existing ready compatible revision without capture or indexing; separate copy
  follows the ordinary private Knowledge path.

## Verification and operations

[tests/](tests/) contains offline suites; [tests/postgres/](tests/postgres/)
checks deployed PostgreSQL constraints and concurrency;
[tests/integration/](tests/integration/) holds Mailpit/live-AI gates;
[tests/support/](tests/support/) contains guarded journey helpers. The
[journey API](tests/support/journey_api.py) and
[worker entry](tests/support/journey_runtime.py) allow the source-only policy
only with a guarded disposable test database and deterministic providers;
they do not enable the installed application.
Use the canonical commands in [testing](../docs/TESTING.md), including
`python -m pytest -q` from `backend` and the disposable service harnesses.
Offline SQLite tests do not prove PostgreSQL triggers or row-lock behavior.

The [source sufficiency packet builder](../scripts/build_private_source_sufficiency_packet.py)
uses authored source patterns and a read-only owner-authorized snapshot to
prepare independent human review in private OS Temp storage. Its
optional literal-only `--authored-spec` adds bounded private questions for
unexposed pages; those matches remain
unreviewed candidates and never become gold without independent labels. Its
[synthetic contracts](tests/test_private_source_sufficiency_packet.py) do not
prove private source usefulness or actual displayed-window quality. The
[display probe](../scripts/evaluate_private_source_display.py) needs a frozen
reviewed roster and a separate live embedding envelope before execution.

The provider-free [source-pair evaluator](../scripts/evaluate_private_source_sufficiency.py)
and [synthetic guards](tests/test_private_source_sufficiency.py) separately audit
owner-reviewed exact insufficient/sufficient windows across eight relation
families. It defaults to no database; explicit private inputs bind the original
candidate manifest, controls, runtime and evaluator fingerprints. Execution
reauthorizes current owner/Subject/published/revision/space SQL reads without
providers or writes. Unknown/cropped positive windows cannot pass, and pair
results do not satisfy retrieval, displayed-window, page-open or release gates.

The independent [source-ranker audit](../scripts/audit_source_ranker.py) scores
exact question/window pairs with one frozen calibration-only threshold under
the operator-approved offline resource envelope. Its [public downloader](../scripts/download_source_ranker_bundle.py)
has a durable bounded acquisition ledger, hash/size checks and at most one
transport retry/resume per file. [Audit safety tests](tests/test_source_ranker_audit.py)
exercise fixture binding, threshold and holdout gates, bundle integrity and
supervised timeout/no-replay. These tools import no application settings,
answer/verifier, provider or database and do not integrate a runtime model.

See [configuration](../docs/CONFIGURATION.md),
[database operations](../docs/DATABASE_OPERATIONS.md),
[system overview](../docs/architecture/SYSTEM-OVERVIEW.md) and the
[ADR index](../docs/decisions/ADR-000-INDEX.md). Older remediation logs are
historical evidence; verify their claims against the current paths above.
