# Data Model

Current truth verified against code: 2026-09-18.

## Purpose and scope

Explain persisted ownership and integrity across content, study, authentication
and background work. PostgreSQL is the deployed database; Alembic owns schema
evolution. Account deletion/export are operator CLI controls described in
[privacy](../PRIVACY.md); there is no public account-deletion API.

## Key components

| Source | Tables and responsibility |
| --- | --- |
| [models/user.py](../../backend/app/models/user.py) | `users`, `invite_links`, `auth_sessions`, `password_reset_tokens`, `rate_limit_buckets`: identity, single-use enrollment invitations, session/reset state and shared hashed abuse counters. |
| [models/subject.py](../../backend/app/models/subject.py) | `subjects`, `flashcard_sets`: instructor-owned content and publication/time limits. |
| [models/flashcard.py](../../backend/app/models/flashcard.py) | `flashcards`, `enrollments`, `study_progress`, `study_answer_submissions`: approved learning content, access, schedules and durable answer receipts. |
| [models/generation.py](../../backend/app/models/generation.py) | `generation_jobs`, `generation_job_sources`, `generation_quota_events`: durable job state/telemetry, encrypted temporary sources and deletion-resistant daily quota charges. |
| [models/email.py](../../backend/app/models/email.py) | `email_outbox_messages`: durable email delivery state linked to reset or invitation rows. |
| [models/operations.py](../../backend/app/models/operations.py) | `request_events`, `worker_heartbeats`: content-free request timing/correlation and worker-loop health. |
| [models/audit.py](../../backend/app/models/audit.py) | `audit_events`: fixed-field privileged state changes, committed with their domain mutation. |
| [models/knowledge.py](../../backend/app/models/knowledge.py) | `rag_embedding_spaces`, `knowledge_storage_usage`, `subject_documents`, content revisions/pages, index revisions/chunks/jobs: private Subject Knowledge, revision identity, reserved capacity and durable indexing target. |

## Primary relationships and flow

An instructor owns subjects; subjects contain sets; sets contain cards.
Students access subjects through unique enrollments and have at most one
progress row per card. A generation job belongs to an instructor and subject,
has at most one encrypted source and at most one result set. Generation
completion stages the set/cards and job result in one transaction. Study
updates stage the answer receipt and progress in one transaction.

Subject Knowledge is an independent durable store. A document belongs to its
Subject's instructor; immutable content revisions own canonical pages, review
and publication. Index revisions own chunks, full embedding-space snapshots and
1,536-dimensional vectors. An index job targets one exact index revision and
captures the Subject corpus revision. Generation jobs may authoritatively link
one document; sets carry a nullable navigation link. Existing jobs/sets have no
document link, and deleting job history leaves Knowledge intact. The schema
does not itself upload files, execute indexing or expose retrieval routes.

## Important invariants

- UUID identifiers and timezone-aware UTC timestamps; PostgreSQL uses
  `TIMESTAMPTZ` and JSONB for structured card/receipt/telemetry fields.
- Case-insensitive unique email; unique student/subject enrollment and
  student/card progress. Answer keys are hashed and unique per student;
  generation keys are hashed and unique per instructor.
- Cards have exactly four trimmed, nonempty, case-insensitively unique options
  and one matching canonical answer. Pydantic validates requests/merged edits;
  PostgreSQL also applies `flashcard_options_valid`.
- Sets start unpublished. Publication needs at least one approved card;
  service validation and PostgreSQL triggers protect that requirement and
  removal/unapproval of the final approved card while its set remains published.
- Generated cards start unapproved. Quality scores and verified source
  provenance do not grant approval. Manual instructor card creation is an
  explicit approval action.
- Status/interval bounds, nonnegative counters, job claims/completion and email
  claim/terminal-state checks protect persisted state.
- Knowledge starts private and cannot enter the eligible chunk view until its
  content and index revisions are active and ready, the content revision is
  reviewed/published, and the Subject's active embedding space matches. This
  view is an eligibility predicate, not principal authorization; future
  retrieval also checks current Subject owner/enrollment in its SQL.
- The PostgreSQL schema guards document, page, chunk/vector and aggregate
  Subject/uploader/deployment count and byte reservations under one ordered
  transaction advisory lock. Charges cover reserved payload, including
  private/staged/failed retained revisions, not PostgreSQL overhead/WAL/backups.

## Deletion ownership and edge cases

| Deleted row | Database effect |
| --- | --- |
| User | Cascades owned subjects/invitations, enrollments, progress, answer receipts, sessions, reset rows, generation jobs and quota events. Email dependent on a removed reset/invitation cascades transitively. |
| Subject | Cascades sets/cards/progress/receipts, enrollments, invitations and generation jobs/sources. |
| Set/card | Set deletes its cards; card deletes progress and answer receipts. Deleting a set does not delete its job history. |
| Invitation consumer | `invite_links.used_by` becomes null; `used_at` remains, so the invitation stays consumed. |
| Generation job | Source cascades; result set's `generation_job_id` and quota event's `job_id` become null. Learning content and quota charges survive job-history deletion. |
| Reset or invitation | Linked outbox messages cascade. |
| Audit actor account | Actor becomes null; opaque resource/subject IDs and transition history remain until configured audit cleanup. |
| Knowledge document | Content revisions/pages and index revisions/chunks/jobs cascade. Generation-job and set links detach; the job records a capture-removal tombstone; flashcards survive. |
| Subject or instructor | Owned Knowledge cascades with its Subject; ordinary generation-history deletion does not cascade Knowledge. |

Rate-limit buckets have no user foreign key and do not participate in account
cascades. Quota charges survive subject/job deletion but cascade with their
user. Parent-content deletion is distinct from deleting the final card of a
still-published set. PostgreSQL tests exercise these cases; SQLite fixtures
alone do not prove them.

## Sources, verification and related decisions

The [migration chain](../../backend/alembic/versions/) currently ends at
`20260918_0010`, requiring PostgreSQL 16 and pgvector 0.8.6 even with RAG off;
[database startup](../../backend/app/database.py) verifies the
database matches all configured heads. Never infer the live database revision
from this code snapshot. See [database operations](../DATABASE_OPERATIONS.md),
[PostgreSQL integrity tests](../../backend/tests/postgres/test_database_integrity.py),
[idempotency tests](../../backend/tests/test_study_idempotency.py) and
[backend map](../../backend/MOC.md).

Decisions: [four-option cards](../decisions/ADR-001-four-option-cards.md),
[Alembic ownership](../decisions/ADR-004-alembic-schema-ownership.md),
[deletion cascades](../decisions/ADR-005-deletion-cascades.md).
Continue with [system overview](SYSTEM-OVERVIEW.md), [auth](AUTH-FLOW.md),
[generation](AI-GENERATION-FLOW.md) and [study](STUDY-PROGRESS-FLOW.md).
