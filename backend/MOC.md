# Backend Map of Content

Current source-only Ask uses `related_knowledge_navigation_v8`, `visual_source_id_v5` and `literal_subject_admission_v2` at Alembic head `20261002_0033`. Fresh installations remain default-off. The retained local installation was enabled after its measured release gates on 2026-10-04; see the [closure evidence](../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md). Historical policies and database rows remain immutable and readable; they cannot execute as new jobs.

## Entry points

| Entry | Responsibility |
| --- | --- |
| [app/main.py](app/main.py) | FastAPI factory, lifespan migration verification, CORS, routers and health endpoints. |
| [app/database.py](app/database.py) | Async SQLAlchemy engine/session dependency, rollback cleanup and Alembic-head verification. |
| [app/worker.py](app/worker.py) | Generation-worker process entry. |
| [app/email_worker.py](app/email_worker.py) | Email-worker process entry. |
| [app/index_worker.py](app/index_worker.py) | Independent Subject Knowledge embedding/index-worker process entry. |
| [app/answer_worker.py](app/answer_worker.py) | Independent source-only Subject Ask AI query-embedding/source-ID-judge worker process entry; fresh installation Ask flags remain default-off. |
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
| [alembic/](alembic/) | Sole deployed schema evolution mechanism; current source head `20261002_0033` require PostgreSQL 16/pgvector 0.8.6. Source-only terminal/reference limits, parent-stage policy/attempt binding, canonical-page offsets, immutable historical snapshots, original-PDF archive guards and admission-context constraints preserve authorization and history. Retained heads/drift passed at local activation; see [database operations](../docs/database/DATABASE_OPERATIONS.md). |

## Common change paths

- Source-only Ask: [visual contract](app/ai/source_judgment_visual.py),
  [literal context](app/ai/source_navigation_context.py),
  [admission](app/services/rag_question_context.py),
  [source preparation](app/services/source_visual_preparation.py) and
  [provider](app/ai/providers/source_visual.py) implement the released
  v8/visual-v5/admission-v2 policy. [Original archives](app/services/knowledge_pdf.py)
  authenticate all blocks before the [isolated renderer](app/services/knowledge_pdf_renderer.py)
  draws bounded original pages. The worker preserves one current-question
  embedding, at most one source-ID judgment and zero answer/verifier/retry.

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
  [AI evaluation](../docs/ai/AI_EVALUATION.md) for offline evidence and live limits.
- Native Gemini selection: [ai/gemini_catalog.py](app/ai/gemini_catalog.py)
  closes the Flashcard text-model list and historical Ask text policies;
  [config.py](app/config.py) checks configured model, thinking and budgets;
  new Ask work snapshots only its embedding/source policy. The separate
  Ask gate and old-policy fence leave history/source reads and Knowledge work
  available. Read [provider operations](../docs/ai/AI_PROVIDERS.md) and
  [Ask shutdown](../docs/ai/ASK_AI_SHUTDOWN.md).
- Study: [routers/study.py](app/routers/study.py) → `FlashcardService` answer
  resolution, receipt reservation and row-locked progress mutation →
  [models/flashcard.py](app/models/flashcard.py).
  Read [study/progress](../docs/architecture/STUDY-PROGRESS-FLOW.md).
- Recovery/invitation email: auth/subject transaction →
  [services/email.py](app/services/email.py) outbox →
  [workers/email.py](app/workers/email.py) SMTP delivery.
  Read [email operations](../docs/mail-server/EMAIL_DELIVERY.md).
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
  historical migration
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
  source-only stage policy and attempt identity to its parent job. Canonical-page
  offsets and original-PDF archives bind current exact references; migration
  `0033` admits the current v8/visual-v5/admission-v2 contract while preserving
  historical policy rows. [Source navigation](app/ai/source_navigation.py),
  [structural source units](app/ai/source_structure.py) and
  [authorized retrieval](app/services/knowledge_retrieval.py) keep bounded
  candidate assembly separate from remote issued-ID qualification.
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
Use the canonical commands in [testing](../docs/development/TESTING.md), including
`python -m pytest -q` from `backend` and the disposable service harnesses.
Offline SQLite tests do not prove PostgreSQL triggers or row-lock behavior.

Private generation source [inventory](scripts/inventory_private_generation_sources.py)
and [evaluation](scripts/evaluate_private_generation.py) remain explicit guarded
operator tools; [no-provider preflight](../scripts/preflight_private_generation_source.py)
does not authorize paid execution. Consumed navigation/verifier experiments
are retired; their rationale and results remain in dated logs and ADRs.
