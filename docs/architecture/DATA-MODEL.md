# Data Model

Current source-only Ask uses `related_knowledge_navigation_v8`, `visual_source_id_v5` and `literal_subject_admission_v2` at Alembic head `20261002_0033`. Fresh installations remain default-off. The retained local installation was enabled after its measured release gates on 2026-10-04; see the [closure evidence](../../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md). Historical policies and database rows remain immutable and readable; they cannot execute as new jobs.

## Purpose and scope

Explain persisted ownership and integrity across content, study, authentication
and background work. PostgreSQL is the deployed database; Alembic owns schema
evolution. Account deletion/export are operator CLI controls described in
[privacy](../security/PRIVACY.md); there is no public account-deletion API.

## Key components

| Source | Tables and responsibility |
| --- | --- |
| [models/user.py](../../backend/app/models/user.py) | `users`, `invite_links`, `auth_sessions`, `password_reset_tokens`, `rate_limit_buckets`: identity, single-use enrollment invitations, session/reset state and shared hashed abuse counters. |
| [models/subject.py](../../backend/app/models/subject.py) | `subjects`, `flashcard_sets`: instructor-owned content and publication/time limits. |
| [models/flashcard.py](../../backend/app/models/flashcard.py) | `flashcards`, `enrollments`, `study_progress`, `study_answer_submissions`: approved learning content, access, schedules and durable answer receipts. |
| [models/generation.py](../../backend/app/models/generation.py) | `generation_jobs`, `generation_job_sources`, generation/Knowledge quota events: durable flashcard or Knowledge-only job state, repeat-upload choice and typed capture outcome, encrypted temporary sources and deletion-resistant daily charges. |
| [models/email.py](../../backend/app/models/email.py) | `email_outbox_messages`: durable email delivery state linked to reset or invitation rows. |
| [models/operations.py](../../backend/app/models/operations.py) | `request_events`, `worker_heartbeats`: content-free request timing/correlation and worker-loop health. |
| [models/audit.py](../../backend/app/models/audit.py) | `audit_events`: fixed-field privileged state changes, committed with their domain mutation. |
| [models/knowledge.py](../../backend/app/models/knowledge.py) | `rag_embedding_spaces`, `knowledge_storage_usage`, `subject_documents`, content revisions/pages, index revisions/chunks/jobs: private Subject Knowledge, revision identity, reserved capacity and durable indexing target. |
| [models/rag.py](../../backend/app/models/rag.py) | `rag_threads`, `rag_messages`, `rag_message_sources`, `rag_answer_jobs`, `rag_answer_stage_attempts`, `rag_answer_quota_events`, `rag_related_evidence`: private conversation ownership, historical citations, fenced source-only and historical policy snapshots, per-attempt request/cost provenance, daily charges and bounded exact source-offset references. |

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
1,536-dimensional vectors. Each chunk preserves its server-issued local ID and
gets a persistent UUID. An index job targets one exact index revision and
captures the Subject corpus revision plus content-free usage/cost telemetry.
Generation jobs may authoritatively link one document; sets carry a nullable
navigation link. Existing jobs/sets have no document link, and deleting job
history leaves Knowledge intact. Capture/index execution and internal retrieval
feed durable answer jobs. Each Ask AI thread belongs to one principal and
Subject; messages, jobs and sources repeat that scope through composite foreign
keys. Answer sources identify exact active content/index/chunk revisions. The
API, index/answer workers and typed Knowledge/Ask AI frontend presentation are
implemented. Browser state is a projection of these durable server records; it
does not own publication, authorization, evidence validity or retry identity.

After accepted PDF bytes establish a checksum, a job may durably enter
`awaiting_choice` with an owner/Subject-scoped candidate and encrypted source.
The candidate foreign key repeats job Subject and user scope. A committed
`reuse` or `separate_copy` choice and its hashed operation key survive reload;
typed upload outcomes are `no_changes`, `reused` and `separate_copy`.
`no_changes` and `reused` link an existing exact revision without adding a
Knowledge storage reservation or index job. Their daily raw upload quota receipt
still survives job deletion, independently of the reused document.

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
  view is an eligibility predicate, not principal authorization; the retriever
  repeats current Subject owner/enrollment and all eligibility predicates in
  vector, lexical and source-read SQL.
- Embedding compatibility includes provider, base URL, model, space/format
  versions, fixed document/query task modes, dimensions, representation and
  cosine metric. Matching dimensions alone are insufficient. Embedding 2 uses
  `gemini2_qa_section_v1` plus its two text-mode identities; 001 and historical
  rows retain their own allowed combinations.
- A pre-provider dead index lease may be requeued within its attempt/deadline
  bounds. Once a provider call starts, dead leases and handled provider failures
  are terminal until an explicit new operator action; claim tokens fence writes.
- New source-only Ask jobs snapshot the current corpus, embedding space,
  retrieval/source policy and authorizing session; historical answer jobs retain
  their answer provider/model/support snapshots. Jobs use separate admission and
  quota rows, bounded manual retry, claim tokens, leases, deadlines and current-
  access/corpus checks before the provider stage and final commit. A new
  `related_knowledge_navigation_v8` completion atomically binds `related_knowledge` and
  up to three exact ordered source references, or `no_match` and zero refs;
  neither kind has an assistant answer message. Historical answer/abstention
  completion still binds its message and citation rules.
- Under current navigation-v8/visual-v5/admission-v2, one manual attempt can have
  only one query-embedding stage and at most one source-ID judgment stage, each
  with at most one physical request and zero retries; it makes zero answer-model/
  verifier calls. Historical two-request stages remain
  stored for audit but cannot execute as new work. The `0023` stage trigger binds
  source-only stage policy and current manual/worker attempt numbers to the
  locked parent job, preventing null or different policy snapshots from bypassing
  the `0022` stage and physical-request limits. Attempt cost records distinguish known from uncertain
  execution; a manual Retry increments the attempt number and gets a fresh
  idempotency/quota identity without erasing cumulative usage.
- Revision `0026` adds immutable `subject_document_pdfs` and encrypted
  `subject_document_pdf_blocks`, bound to the content revision's document,
  Subject, uploader, SHA and page count. Deferred complete-block checks,
  fixed quotas and writer locking fence archive admission; parent deletion
  cascades blocks. Revision `0027` admits navigation v2 without converting old
  jobs and binds canonical references to their exact v1/v7 or v2/v8 policy pair.
  Downgrade refuses retained v2 job snapshots. Original reads repeat full-bundle
  access checks; archive presence alone never grants student access.
- Revision `0028` admits the corrected navigation-v3/source-v9 pair without
  rewriting v2/v8 job snapshots. Downgrade refuses any retained v3 job,
  including terminal/no-match outcomes; keep Ask disabled and prefer forward
  repair or a restore-verified backup over deleting historical jobs.
- Threads are private to their user even when that user is a student and the
  reader is the Subject instructor. Answer/source reads hide stored content when
  current publication, active revision, embedding space or corpus no longer
  matches. Messages expire after the configured 90-day default; retention does
  not grant access.
- The PostgreSQL schema guards document, page, chunk/vector and aggregate
  Subject/uploader/deployment count and byte reservations under one ordered
  transaction advisory lock. Charges cover reserved payload, including
  private/staged/failed retained revisions, not PostgreSQL overhead/WAL/backups.
- A pending repeat-upload candidate is scoped by a composite document/Subject/
  uploader foreign key and must have an expiry. Only `reuse` and
  `separate_copy` are valid choices; only `no_changes`, `reused` and
  `separate_copy` are valid outcomes. `captured`, `reused` and `unchanged`
  capture statuses require both document and content-revision links.
- Same-operation upload idempotency and the later duplicate choice are separate
  identities. The Knowledge write lock plus a generation-job row lock makes the
  first choice win; a conflicting later choice cannot reinterpret the job.

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
| Knowledge document | Content revisions/pages and index revisions/chunks/jobs cascade. Pending duplicate-candidate hints clear; generation-job and set links detach; the job records a capture-removal tombstone where applicable; flashcards survive. |
| RAG thread/message | Thread deletion cascades its messages/jobs/sources. Question expiry cascades its job; source rows cascade with the cited chunk/revision, after which history redacts the answer. Detached quota receipts remain until metadata cleanup. |
| Subject or instructor | Owned Knowledge cascades with its Subject; ordinary generation-history deletion does not cascade Knowledge. |

Rate-limit buckets have no user foreign key and do not participate in account
cascades. Quota charges survive subject/job deletion but cascade with their
user. Parent-content deletion is distinct from deleting the final card of a
still-published set. PostgreSQL tests exercise these cases; SQLite fixtures
alone do not prove them.

## Sources, verification and related decisions

The [migration chain](../../backend/alembic/versions/) in this checkout ends at
`20260926_0023`, requiring PostgreSQL 16 and pgvector 0.8.6 even with RAG off.
The `0020` answer-v2 stage guard remains historical and fenced; `0022` introduces
source-only terminal results and `0023` binds their stage policy and attempt
identity to the parent job. Source-only activation needs its separate quality
and rollout gate.
[database startup](../../backend/app/database.py) verifies the
database matches all configured heads. Never infer the live database revision
from this code snapshot. See [database operations](../database/DATABASE_OPERATIONS.md),
[PostgreSQL integrity tests](../../backend/tests/postgres/test_database_integrity.py),
[duplicate-choice PostgreSQL tests](../../backend/tests/postgres/test_postgres_knowledge_duplicate_choice.py),
[idempotency tests](../../backend/tests/test_study_idempotency.py) and
[backend map](../../backend/MOC.md).

Decisions: [four-option cards](../decisions/ADR-001-four-option-cards.md),
[Alembic ownership](../decisions/ADR-004-alembic-schema-ownership.md),
[deletion cascades](../decisions/ADR-005-deletion-cascades.md), and
[repeat Knowledge uploads](../decisions/ADR-017-repeat-knowledge-upload-choice.md),
[Embedding 2 spaces](../decisions/ADR-018-gemini-embedding-2-space.md), and
[historical two-request Ask](../decisions/ADR-019-two-request-local-support-ask.md),
and [source-only Ask](../decisions/ADR-022-related-knowledge-primary-ask.md).
Continue with [system overview](SYSTEM-OVERVIEW.md), [auth](AUTH-FLOW.md),
[generation](AI-GENERATION-FLOW.md) and [study](STUDY-PROGRESS-FLOW.md).
