# Backend Map of Content

Current code verified: 2026-09-16. This is navigation, not an API specification.
Start with [project orientation](../docs/00-START-HERE.md) and the
[project map](../PROJECT-MAP.md).

## Entry points

| Entry | Responsibility |
| --- | --- |
| [app/main.py](app/main.py) | FastAPI factory, lifespan migration verification, CORS, routers and health endpoints. |
| [app/database.py](app/database.py) | Async SQLAlchemy engine/session dependency, rollback cleanup and Alembic-head verification. |
| [app/worker.py](app/worker.py) | Generation-worker process entry. |
| [app/email_worker.py](app/email_worker.py) | Email-worker process entry. |
| [app/cli.py](app/cli.py) | Operator bootstrap/email retry, content-free diagnostics/audits, private export, explicit account deletion, bounded retention and optional aggregate reporting. |
| [app/config.py](app/config.py) | Validated settings from process environment and the sole root `.env`; test mode suppresses file loading. |

## Main areas

| Area | Responsibility |
| --- | --- |
| [app/routers/](app/routers/) | Auth, subjects/sets/invitations, flashcard CRUD, generation jobs and study HTTP contracts. |
| [app/services/](app/services/) | Auth/session/invitation logic, content CRUD, progress/idempotency, generation lifecycle/quotas, PDF extraction/storage and email composition. |
| [app/schemas/](app/schemas/) | Pydantic request/response validation. Student study cards have a separate answer-free response. |
| [app/models/](app/models/) | SQLAlchemy application and operational tables; database constraints and foreign-key ownership. |
| [app/observability.py](app/observability.py), [app/services/operations.py](app/services/operations.py) | Closed JSON logs/errors, request/job correlation, retained metrics and local/durable loop heartbeats. |
| [app/services/privacy.py](app/services/privacy.py), [app/services/audit.py](app/services/audit.py) | Consistent allowlisted export, guarded explicit deletion, bounded metadata expiry and fixed-field transactional audits. |
| [app/workers/](app/workers/) | Generation/email claiming, leases, fencing, retention and graceful shutdown. |
| [app/ai/](app/ai/) | Provider-neutral pipeline, closed contracts, chunking, grounding, provider adapters and worker-wide quota admission. |
| [app/agents/graph.py](app/agents/graph.py) | Active `ainvoke` compatibility facade used by the generation worker; delegates to `FlashcardGenerationPipeline`, without LangGraph. |
| [alembic/](alembic/) | Sole deployed schema evolution mechanism; current code head `20260917_0008`. |

## Common change paths

- Authentication: [routers/auth.py](app/routers/auth.py) →
  [services/auth.py](app/services/auth.py) → [models/user.py](app/models/user.py),
  with [frontend auth](../frontend/MOC.md) and [auth flow](../docs/architecture/AUTH-FLOW.md).
- Subjects, manual cards and publication: [routers/subjects.py](app/routers/subjects.py) /
  [routers/flashcards.py](app/routers/flashcards.py) →
  [services/subject.py](app/services/subject.py) /
  [services/flashcard.py](app/services/flashcard.py) → schemas/models and publication triggers.
- PDF generation: [routers/generation.py](app/routers/generation.py) →
  [services/generation.py](app/services/generation.py) →
  [workers/generation.py](app/workers/generation.py) → graph facade →
  [ai/pipeline.py](app/ai/pipeline.py) → atomic result persistence.
  Read [AI generation flow](../docs/architecture/AI-GENERATION-FLOW.md).
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

## Verification and operations

[tests/](tests/) contains offline suites; [tests/postgres/](tests/postgres/)
checks deployed PostgreSQL constraints and concurrency;
[tests/integration/](tests/integration/) holds Mailpit/live-AI gates;
[tests/support/](tests/support/) contains guarded journey helpers.
Use the canonical commands in [testing](../docs/TESTING.md), including
`python -m pytest -q` from `backend` and the disposable service harnesses.
Offline SQLite tests do not prove PostgreSQL triggers or row-lock behavior.

See [configuration](../docs/CONFIGURATION.md),
[database operations](../docs/DATABASE_OPERATIONS.md),
[system overview](../docs/architecture/SYSTEM-OVERVIEW.md) and the
[ADR index](../docs/decisions/ADR-000-INDEX.md). Older remediation logs are
historical evidence; verify their claims against the current paths above.
