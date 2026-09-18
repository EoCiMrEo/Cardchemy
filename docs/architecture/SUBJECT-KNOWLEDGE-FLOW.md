# Subject Knowledge data boundary and lifecycle

This records the approved Subject-scoped Knowledge architecture through Phase
13. [ADR-012](../decisions/ADR-012-subject-knowledge-and-rag-boundaries.md)
owns the durable choices, [the implementation plan](<../../Cardchemy-Subject-Scoped RAG Implementation Plan.md>)
owns phase tasks, and [current state](../development/CURRENT-STATE.md) says
which parts have actually shipped. Schema foundation precedes upload, indexing,
retrieval, conversation and UI work; a table's existence alone grants no
student access or provider-call permission.

## Ownership and state

Knowledge belongs to an instructor-owned Subject. The uploader must be that
Subject's instructor; a student's enrollment grants access only to eligible
published content once retrieval exists. A document has stable identity and
immutable content revisions. Original page numbers, including empty pages, are
retained as canonical extracted text, and chunks/vectors belong to one content
revision and one explicit embedding space. Temporary encrypted source PDFs keep
the existing generation lifecycle; raw PDFs are not a permanent Knowledge
archive. Flashcards and their review/publication stay separate from Knowledge.

New or changed content starts private. Extraction/index readiness is an
operational state, not approval. Publication names one instructor-reviewed
content revision; reindexing that same revision cannot inherit approval for a
different revision. A staged replacement counts against storage limits and
cannot become student evidence until ready, reviewed, published and atomically
activated. Every retrieval and citation must filter current Subject access,
document publication, active revision, ready index and compatible embedding
space in its database query and subsequent read. A Subject itself has no
publication flag.

One generation job may point to a durable document, and a resulting set may
carry a nullable link for navigation. The generation job is the authoritative
capture association. Historical jobs/sets have null links; no old PDF pages are
invented from cards. Deleting a document cascades pages/chunks/index jobs and
detaches surviving job/set links, preserving flashcards. Deleting job history
does not delete Knowledge. Subject/account deletion cascades owned Knowledge.
Membership is enforced by composite database constraints, not just route code.
Future routes must reuse `SubjectService.check_subject_access()` for current
owner/enrollment decisions and repeat the eligible Subject/document/revision
filters inside retrieval SQL. A prior route check is not enough to authorize a
later asynchronous worker claim.

## Worker and provider boundary

The existing generation worker and future indexing/answer workers use separate
PostgreSQL queues, leases and credentials. An index worker needs only the
embedding profile; an answer worker needs its answer and query-embedding
profiles; the generation worker needs only its flashcard profile. API, email
worker and browser receive no provider keys. Operators must divide an actual
provider account/project RPM and input-TPM allowance across roles and replicas.
Quota-bucket names do not form a distributed governor.

Index jobs snapshot document/content revision, chunker version and complete
embedding-space identity. Future answer jobs snapshot the authorized corpus
revision and answer/query model identities. Claims recheck current access,
publication, cancellation and revision fences before commit; stale claims
cannot publish vectors or answers. Phase 13 creates the durable index-job
target; Phases 14–18 implement capture, execution, retrieval and chat. With
`RAG_ENABLED=false`, no new RAG work is admitted and stored records are not
purged. Independent provider-disable flags suspend only affected model work.

## Privacy, capacity and deletion design

Persisted page text, chunks and vectors are private teaching content. Before
upload routes write them, the operator notice must disclose retention and
embedding text transfer to the selected endpoint. Before Ask AI stores chat,
it must disclose question, bounded history and evidence transfer to the
answer endpoint. No content, vector values, prompts or answers enter routine
logs, telemetry or error messages. Backups, provider copies and exported files
have separate operator/provider expiry; database deletion cannot erase them.

Private conversation ownership is per user and Subject, including instructors.
Instructors do not inherit access to student chats. Each chat message and its
sources expire 90 days after creation, with bounded operator-run cleanup;
threads with no retained messages can then be removed. This clock and cleanup
are implemented with chat writes in Phase 17. If a cited document
is unpublished, deleted or replaced, future history reads hide the derived
stored answer and citations, even if a citation row was removed by a cascade.
Every read also rechecks the current principal's Subject access. No historical
source-read exception is granted.

Per-revision page/text/chunk/vector limits and aggregate document/byte limits
for Subject, uploader and deployment must be enforced in transaction-scoped
admission, counting active, private, staged and failed retained revisions. A
changed-content upload cannot replace an old quota charge until its old
revision is actually removed. Phase 13 fixes schema bounds and the admission
contract; Phase 14 connects the capture/upload write path. Account export must
allowlist instructor-owned Knowledge and a user's own conversations only;
account/Subject deletion must stop or fence affected writers before cascade.
The existing operator export/delete commands require extension before first
Knowledge or chat writes. This is a prerequisite, not a claim those workflows
are already extended.

The [authored retrieval corpus](../RAG_EVALUATION.md) fixes exact-search,
publication, revision, support and abstention criteria before tuning. The
[privacy guide](../PRIVACY.md) and [database operations](../DATABASE_OPERATIONS.md)
own deployed retention and recovery procedures.
