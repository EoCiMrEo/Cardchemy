# Data, privacy and operations

PostgreSQL is the authoritative store for accounts, learning content, durable
jobs, progress and outbox. This conceptual map highlights ownership; it omits
individual fields and composite constraints, which remain defined by models
and used Alembic migrations.

```mermaid
erDiagram
  USER ||--o{ SUBJECT : owns_as_instructor
  USER ||--o{ ENROLLMENT : joins_as_student
  SUBJECT ||--o{ ENROLLMENT : admits
  USER ||--o{ AUTH_SESSION : authenticates
  SUBJECT ||--o{ FLASHCARD_SET : contains
  FLASHCARD_SET ||--o{ FLASHCARD : contains
  USER ||--o{ STUDY_PROGRESS : has
  FLASHCARD ||--o{ STUDY_PROGRESS : tracks
  USER ||--o{ ANSWER_RECEIPT : submits
  FLASHCARD ||--o{ ANSWER_RECEIPT : grades
  SUBJECT ||--o{ KNOWLEDGE_DOCUMENT : owns
  KNOWLEDGE_DOCUMENT ||--o{ CONTENT_REVISION : retains
  CONTENT_REVISION ||--o{ PAGE : preserves
  CONTENT_REVISION ||--o| ORIGINAL_PDF_ARCHIVE : may_have
  CONTENT_REVISION ||--o{ INDEX_REVISION : indexes
  INDEX_REVISION ||--o{ CHUNK_VECTOR : contains
  EMBEDDING_SPACE ||--o{ INDEX_REVISION : identifies
  USER ||--o{ PRIVATE_ASK_THREAD : owns
  SUBJECT ||--o{ PRIVATE_ASK_THREAD : scopes
  PRIVATE_ASK_THREAD ||--o{ MESSAGE : contains
  PRIVATE_ASK_THREAD ||--o{ ASK_JOB : queues
  ASK_JOB ||--o{ SOURCE_REFERENCE : derives
  ASK_JOB ||--o{ STAGE_ATTEMPT : accounts
```

An instructor cannot read a student's private Ask thread. Job/set Knowledge
links preserve provenance without making card publication depend on Knowledge
publication. Removing Knowledge detaches surviving card links. Removing a
Subject or owning account cascades the corresponding owned data; explicit
operator deletion requires quiesced writers and appropriate recovery evidence.

## Content lifetime and egress

```mermaid
flowchart LR
  Upload["Authorized PDF upload"] --> Temporary["Encrypted temporary generation source"]
  Temporary --> Terminal["Success / cancel / permanent failure: delete"]
  Temporary --> Retry["Retryable failure: bounded retention"]
  Upload --> Knowledge["Private canonical pages + vectors + encrypted original"]
  Knowledge --> Retain["Until explicit document / Subject / owner deletion"]
  Question["Private Ask question + exact reference metadata"] --> Chat["Bounded expiry and current-access redaction"]
  Events["Content-free request / job / audit / email status"] --> Cleanup["Bounded metadata retention cleanup"]
  Knowledge -. "Responsible worker only" .-> Provider["Gemini embedding / bounded source-ID processing"]
  Temporary -. "Extracted evidence from generation worker" .-> Provider
  Question -. "Raw current question; narrow admitted subject if needed" .-> Provider
  Backup["Operator backups and exports"] -. "Independent lifecycle" .-> Outside["Provider copies and delivered mail also have separate lifetimes"]
```

The original Knowledge archive uses an independent revision-bound encryption
key, separate from temporary generation sources and JWT signing. Encryption at
rest does not prevent authorized provider egress. Routine logs, telemetry and
safe errors exclude source text, questions, prompts, raw responses, secrets and
link-bearing messages. Optional aggregate telemetry is default-off and runs
only when explicitly requested; API/workers do not continuously push it.

Own-account JSON export uses an allowlist and consistent database snapshot.
It excludes credentials, tokens/hashes, claim/idempotency secrets, vectors,
encrypted archive bytes, staged candidate cards and other users' records.
Database deletion does not erase already delivered mail, provider copies,
backups or downloaded exports; operators own those separate controls.

## Health, worker fencing and upgrades

```mermaid
flowchart TD
  Probe["Health and operator diagnostics"] --> Live["API liveness: process responds"]
  Probe --> Ready["API readiness: database can answer"]
  Probe --> Heartbeat["Worker heartbeat + database connectivity"]
  Heartbeat --> Limit["Does not prove provider availability or completed job throughput"]
  Upgrade["Operator upgrades an existing installation"] --> Drain["Drain writers / workers"]
  Drain --> Backup["Verify database + independent key backup and recovery"]
  Backup --> Migrate["Alembic migrate; never rewrite used history"]
  Migrate --> Verify["Verify all heads, drift, images and current access"]
  Verify --> Resume["Restore traffic and monitor bounded work"]
  Resume --> Claim["Poll queue; claim token + lease + worker identity"]
  Claim --> Fence["Recheck before egress and atomic commit"]
  Fence --> Complete["Current owner commits; stale worker rejected"]
```

Expired leases permit only bounded infrastructure recovery. Handled paid
pipeline failures and uncertain provider execution are not automatically
replayed. SMTP uncertainty requires operator review. Graceful shutdown stops
new claims and gives active work a bounded drain window. Never downgrade a
real database or delete a populated volume as a verification shortcut.

Sources: [data model](../architecture/DATA-MODEL.md),
[models](../../backend/app/models), [Alembic](../../backend/alembic/versions),
[privacy operations](../../backend/app/services/privacy.py),
[diagnostics](../../backend/app/services/operations.py),
[audit](../../backend/app/services/audit.py),
[privacy guide](../security/PRIVACY.md),
[observability](../operations/OBSERVABILITY.md),
[database recovery](../database/DATABASE_OPERATIONS.md).
