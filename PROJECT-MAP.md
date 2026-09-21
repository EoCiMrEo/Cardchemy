# Project Map

Current navigation, verified 2026-09-20. Begin with
[orientation](docs/00-START-HERE.md); use this map to find the smallest relevant
source area. [Backend MOC](backend/MOC.md) and [frontend MOC](frontend/MOC.md)
give the next level of detail.

## Backend

| Area | Path | Responsibility |
| --- | --- | --- |
| API startup | [main.py](backend/app/main.py) | Router order, lifespan/migration verification, CORS and health |
| Configuration/database | [config.py](backend/app/config.py), [database.py](backend/app/database.py) | Root settings, validated boundaries, async sessions and heads/readiness |
| Authentication | [auth router](backend/app/routers/auth.py), [auth service](backend/app/services/auth.py), [password records](backend/app/services/passwords.py), [user model](backend/app/models/user.py) | Purpose-scoped tokens, compatible password hashes, sessions, invitations, registration and reset |
| Subjects/enrollment | [subjects router](backend/app/routers/subjects.py), [subject service](backend/app/services/subject.py), [subject model](backend/app/models/subject.py) | Subject ownership/deletion, invites/enrollment and set publication |
| Sets/cards | [flashcards router](backend/app/routers/flashcards.py), [flashcard service](backend/app/services/flashcard.py), [schemas](backend/app/schemas/flashcard.py) | CRUD, strict four-option validation, approval/publication |
| Generation admission | [generation router](backend/app/routers/generation.py), [generation service](backend/app/services/generation.py) | Job reservation, raw-PDF upload, quotas, polling/cancel/manual retry |
| Generation execution | [worker entry](backend/app/worker.py), [generation worker](backend/app/workers/generation.py), [compatibility facade](backend/app/agents/graph.py) | Lease claims, extraction, pipeline invocation, fencing and atomic result |
| Knowledge capture/indexing | [capture service](backend/app/services/knowledge_capture.py), [index operations](backend/app/services/knowledge_indexing.py), [index entry](backend/app/index_worker.py), [index worker](backend/app/workers/knowledge_index.py) | One-pass private capture, durable embedding claims, fenced batches, reindex staging and atomic space cutover |
| Knowledge retrieval | [retriever](backend/app/services/knowledge_retrieval.py), [embedding adapter](backend/app/ai/embeddings.py) | Worker-owned query embeddings and authorized exact cosine plus PostgreSQL FTS retrieval with bounded deterministic fusion |
| Subject Ask AI | [router](backend/app/routers/rag.py), [service](backend/app/services/rag_answers.py), [answer contract](backend/app/ai/answering.py), [answer entry](backend/app/answer_worker.py), [answer worker](backend/app/workers/rag_answer.py), [models](backend/app/models/rag.py) | Private threads, durable bounded admission, current-access checks, grounded/support-validated answers, citations and fenced lifecycle |
| Knowledge management | [router](backend/app/routers/knowledge.py), [service](backend/app/services/knowledge_management.py), [schemas](backend/app/schemas/knowledge.py) | Owner-only document state, explicit review/publication, persisted-page index retry, unpublish and card-preserving deletion |
| RAG evaluation | [v2 corpus](backend/tests/fixtures/rag_eval/subject_knowledge_v2.json), [metric support](backend/tests/support/rag_evaluation.py), [PostgreSQL evaluation](backend/tests/postgres/test_postgres_rag_pipeline.py) | Reviewed deterministic recall/ranking/support/security/latency/throughput gates and explicit exact-search/ANN/reranker decisions |
| AI quality/providers | [pipeline](backend/app/ai/pipeline.py), [prompts](backend/app/ai/prompts.py), [grounding](backend/app/ai/grounding.py), [providers](backend/app/ai/providers/__init__.py), [rate governor](backend/app/ai/rate_limit.py) | Evidence packing, versioned prompts/refill exclusions, typed output, fixed quality diagnostics, duplicate rejection, one retry owner and request budgets |
| PDF/source protection | [PDF processor](backend/app/services/pdf_processor.py), [source storage](backend/app/services/source_storage.py) | Subprocess bounds, optional OCR, encrypted temporary sources |
| Study/progress | [study router](backend/app/routers/study.py), [flashcard service](backend/app/services/flashcard.py), [models](backend/app/models/flashcard.py) | Eligibility, due/review-all queries, server grading/scheduling and receipts |
| Transactional email | [email service](backend/app/services/email.py), [worker entry](backend/app/email_worker.py), [email worker](backend/app/workers/email.py), [outbox model](backend/app/models/email.py) | Atomic enqueue, safe templates, SMTP delivery and ambiguity recovery |
| Operators | [CLI](backend/app/cli.py), [health probe](backend/app/healthcheck.py), [shutdown](backend/app/workers/shutdown.py) | Instructor bootstrap, queue status/retry and process health/drain |
| Diagnostics/privacy/audit | [safe diagnostics](backend/app/observability.py), [operations](backend/app/services/operations.py), [privacy](backend/app/services/privacy.py), [audit](backend/app/services/audit.py) | Correlation/errors, retained aggregate metrics, worker-loop health, operator lifecycle and transactional privileged history |
| Schema evolution | [Alembic versions](backend/alembic/versions), [env](backend/alembic/env.py) | Baseline → current `20260920_0013` head; native Gemini embedding identity, request correlation/timings and Knowledge lifecycle audits extend the capture/index/Ask AI schema |
| Subject Knowledge foundation | [Knowledge models](backend/app/models/knowledge.py), [Knowledge lock](backend/app/services/knowledge_lock.py) | Private document/content/index revisions, reserved capacity, eligible-record predicate, durable index queue and ordered writer/deletion locking |

## Frontend

| Area | Path | Responsibility |
| --- | --- | --- |
| Bootstrap/routes | [main.tsx](frontend/src/main.tsx), [App.tsx](frontend/src/App.tsx), [guards](frontend/src/components/auth/RouteGuards.tsx) | Providers, lazy pages and role-protected routes |
| Auth/API | [AuthContext](frontend/src/context/AuthContext.tsx), [api.ts](frontend/src/services/api.ts), [types](frontend/src/services/types.ts), [errors](frontend/src/services/errors.ts) | Memory tokens, single-flight refresh, typed HTTP/errors |
| Instructor workflow | [instructor pages](frontend/src/pages/instructor), [subject dialogs](frontend/src/components/subjects), [set dialogs](frontend/src/components/sets) | Subjects, generation, review/edit/approval/publication, invitation |
| Generation UI | [job hook](frontend/src/hooks/useGenerationJobs.ts), [job card](frontend/src/components/generation/GenerationJobCard.tsx), [flashcards API](frontend/src/services/flashcards.ts) | Reservation/upload, polling, cancellation/retry and bounded telemetry |
| Student workflow | [student pages](frontend/src/pages/student), [study slice](frontend/src/store/slices/studySlice.ts), [study API](frontend/src/services/study.ts) | Enrollment views, due/review-all sessions, durable save/retry/progress |
| Subject Knowledge/Ask AI UI | [KnowledgeArea](frontend/src/components/knowledge/KnowledgeArea.tsx), [AskAiPanel](frontend/src/components/rag/AskAiPanel.tsx), [Knowledge API](frontend/src/services/knowledge.ts), [RAG API](frontend/src/services/rag.ts) | Independent instructor Knowledge lifecycle plus principal-private conversations, job recovery, safe citations and accessible responsive states |
| Join/recovery | [JoinCourse](frontend/src/pages/JoinCourse.tsx), [ForgotPassword](frontend/src/pages/ForgotPassword.tsx), [ResetPassword](frontend/src/pages/ResetPassword.tsx) | Invite validation/join and account recovery |
| Shared experience | [UI controls](frontend/src/components/ui), [feedback](frontend/src/components/feedback), [English catalog](frontend/src/i18n/en.ts), [styles](frontend/src/index.css) | Accessible controls, errors, copy, responsive layout |

## Cross-cutting change paths

| Change | Trace and contract to read |
| --- | --- |
| Generation behavior | Instructor `SubjectDetails` → `useGenerationJobs`/flashcards API → generation router/service → generation worker → graph facade → pipeline/provider → models; [generation flow](docs/architecture/AI-GENERATION-FLOW.md) |
| Subject Knowledge/Ask AI | Generation/Knowledge reservation and upload → shared bounded preparation → atomic capture/index enqueue → index worker → explicit publication/space cutover → authorized retriever → private answer queue/worker → grounded answer and citations; [Knowledge flow](docs/architecture/SUBJECT-KNOWLEDGE-FLOW.md) |
| Card review/publication | `SetView`/dialogs → flashcards/subjects APIs → routers/services → card/set/subject constraints and migration trigger; [data model](docs/architecture/DATA-MODEL.md) |
| Auth/invitation/reset | Auth/join pages and context → auth/subjects APIs → auth/subject services → user/session/invitation + outbox → email worker; [auth flow](docs/architecture/AUTH-FLOW.md) |
| Answer/progress | `StudyMode`/study slice → study API with receipt key → study router → flashcard service → progress/receipt/enrollment rows; [study flow](docs/architecture/STUDY-PROGRESS-FLOW.md) |
| Runtime/configuration | Root `.env.example` → settings/public loader/Compose → workers/API/Vite build; [configuration](docs/CONFIGURATION.md) and [system overview](docs/architecture/SYSTEM-OVERVIEW.md) |

## Configuration, infrastructure and verification

- [Root template](.env.example) is the only configuration template; real `.env`
  is private. [Bootstrap](scripts/bootstrap_env.py) never overwrites it.
- [Base Compose](docker-compose.yml), [development override](docker-compose.dev.yml),
  [production override](docker-compose.prod.yml), [backend Dockerfile](backend/Dockerfile),
  [frontend Dockerfile](frontend/Dockerfile) and [Nginx](frontend/nginx.conf)
  define the runtime. [Vite](frontend/vite.config.ts) and the
  [public loader](frontend/config/environment.mjs) define browser configuration.
- [Database inventory](runtime-artifacts.json), the
  [reviewed database recipe](docker/database/Dockerfile), and the
  [database image helper](scripts/runtime_database.py) own the pinned
  PostgreSQL 16/pgvector build and verified immutable consumer identity.
  [Artifact scanning](scripts/test_database_artifact.py),
  [vector recovery](scripts/test_pgvector_restore.py), and
  [prior-installation recovery](scripts/test_database_volume_upgrade.py)
  verify security and disposable restore contracts; see
  [database operations](docs/DATABASE_OPERATIONS.md).
- Backend [tests](backend/tests) separate offline, `postgres/`, and opt-in
  `integration/`; frontend [Node units](frontend/tests), [component tests](frontend/tests/components)
  and [E2E](frontend/e2e) cover client contracts.
- [Service harness](scripts/test_services.py), [real journey](scripts/test_journey.py),
  [CI validator](scripts/check_ci.py), [context validator](scripts/check_context.py),
  [coverage](scripts/check_coverage.py), [bundle](scripts/check_bundle.mjs),
  [security](scripts/test_security.py) and [images](scripts/check_images.py)
  validate distinct gates. See [testing](docs/TESTING.md).
- [TLS SMTP verifier](scripts/test_smtp_tls.py) and
  [production recovery rehearsal](scripts/test_production_rehearsal.py) verify
  local encrypted email and fresh production-profile backup/restore respectively.
  Their guides are [SMTP verification](docs/SMTP-VERIFICATION.md) and
  [production rehearsal](docs/PRODUCTION_REHEARSAL.md).
- [Release validator](scripts/check_release.py), [notice synchronization](scripts/prepare_release_notices.py)
  and [brand preparation](scripts/prepare_brand_assets.py) own exact release
  provenance and distribution notices/exports. See [releasing](docs/RELEASING.md)
  and the disposable [demo](docs/DEMO.md).
- [Workflows](.github/workflows), [coverage budget](.github/coverage-budget.json),
  [bundle budget](.github/bundle-budget.json) and [protection definition](.github/branch-protection.json)
  are explained in [CI](docs/CI.md). A local definition is not a fresh remote-status check.

## Documentation

[Guide index](docs/README.md) → [architecture](docs/architecture/SYSTEM-OVERVIEW.md)
and [decision index](docs/decisions/ADR-000-INDEX.md). [Local setup](docs/development/LOCAL-SETUP.md)
owns onboarding; [current state](docs/development/CURRENT-STATE.md) summarizes
completed phases; the [public roadmap](ROADMAP.md) owns current proposals.
[Dated logs](.agent/logs/README.md) and the [archive](docs/archive/README.md)
retain completed phase checklists and historical evidence. [Agent rules](AGENTS.md)
define context maintenance.
