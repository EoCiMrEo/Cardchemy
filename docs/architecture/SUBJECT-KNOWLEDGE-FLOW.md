# Subject Knowledge data boundary and lifecycle

This records the implemented Subject-scoped Knowledge architecture through the
Phase 20/21 technical closure. [ADR-012](../decisions/ADR-012-subject-knowledge-and-rag-boundaries.md)
owns the durable choices, [the implementation plan](<../../Cardchemy-Subject-Scoped RAG Implementation Plan.md>)
owns phase tasks, and [current state](../development/CURRENT-STATE.md) says
which parts have actually shipped. Capture, indexing, internal retrieval,
private durable answer APIs/workers, the Knowledge/Ask AI UI and deterministic
retrieval/support evaluation are implemented.
A table's existence alone grants no student access or provider-call permission.

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
Routes reuse `SubjectService.check_subject_access()` for current
owner/enrollment decisions and repeat the eligible Subject/document/revision
filters inside retrieval SQL. A prior route check is not enough to authorize a
later asynchronous worker claim.

## Worker and provider boundary

The generation, indexing and answer workers use separate
PostgreSQL queues, leases and credentials. An index worker needs only the
embedding profile; an answer worker needs its answer and query-embedding
profiles; the generation worker needs only its flashcard profile. API, email
worker and browser receive no provider keys. Operators must divide an actual
provider account/project RPM and input-TPM allowance across roles and replicas.
Quota-bucket names do not form a distributed governor.

The default RAG profiles are native Gemini under
[ADR-014](../decisions/ADR-014-native-gemini-rag-profiles.md):
`gemini-embedding-001` produces 1,536-dimensional normalized cosine vectors
with `RETRIEVAL_DOCUMENT`/`QUESTION_ANSWERING` task modes, while
`gemini-3.5-flash` returns strict structured answer/support results. Embedding
space identity frames provider, canonical endpoint, model, revision, format,
dimensions, representation, metric and both task modes. A changed field creates
an incompatible staged space; vectors are never silently mixed.

Index jobs snapshot document/content revision, chunker version and complete
embedding-space identity, including fixed document/query task modes. Answer
jobs snapshot the authorizing session, corpus revision, retrieval policy,
embedding space and answer provider/model identities. Claims recheck
cancellation and revision fences before commit;
retrieval rechecks principal access, publication and corpus/space identity in
SQL. Stale claims cannot publish vectors or answers. With
`RAG_ENABLED=false`, no new RAG work is admitted and stored records are not
purged. Independent provider-disable flags suspend only affected model work.

## Capture, indexing and retrieval execution

Normal generation and explicit Knowledge-only upload both retain the bounded,
encrypted temporary PDF lifecycle. The generation worker extracts once and
builds one `PreparedDocument`; the unchanged flashcard pipeline and Knowledge
capture consume that validated page-aware chunk snapshot. Capture runs in one
short fenced transaction that rechecks the job lease, cancellation and Subject
ownership, persists pages/chunks with local IDs plus persistent UUIDs, reserves
capacity and enqueues one exact index revision. It never waits for embeddings.

Knowledge-only admission has its own job kind, queue limits, daily upload/job
quotas and retained-source caps. A repeated upload for the same idempotent
operation replays the same job; changed bytes conflict. Supplying an owned
document ID creates a new content revision, while omission creates a new
document. Supported capture/capacity failure is a safe independent outcome for
a combined flashcard job. Cancellation deletes the capture created by that job;
a non-cancelled flashcard failure may retain valid private Knowledge. Raw PDFs
are still removed according to the existing transient-source policy.

The index worker is a separate Compose/process lane with only the embedding
credential. It batches document vectors, validates exact count/order/finite
float32 dimensions/cosine suitability, and persists each batch only while its
worker ID, 64-hex claim token and lease remain current. A dead lease before the
provider boundary can be requeued within deadline/attempt bounds. Provider-
started work, handled provider failures and timeouts fail terminally instead of
automatically replaying an expensive request. Only a complete index can mark
content ready. Reindex rebuilds chunks from canonical stored pages; explicit cutover
requires a ready compatible index for every active ready content revision and
preserves the old active space on failure.

`KnowledgeRetriever` is an internal reusable worker boundary. Authorization
binds a principal, Subject, corpus revision, active space, bounded query and
optional fully authorized document set. Both exact cosine and PostgreSQL
`simple` FTS candidate CTEs repeat current owner/enrollment, publication,
ready/active revision, Subject, document, corpus and embedding-space filters.
Candidates use bounded reciprocal-rank fusion, deterministic ties, overlap
deduplication and a context-token cap. Source reads authorize again. Query
embedding belongs in the answer worker; no API route acquires a provider key.
Phase 17 exposes enqueue/poll plus owner-private thread/history, retry, cancel,
delete and citation-source reads around that boundary.

## Subject Ask AI execution

An authenticated owner or enrolled student creates a private thread under one
Subject. Instructors do not inherit student conversation access. Question
admission holds a PostgreSQL advisory lock, validates a hashed idempotency key
and payload fingerprint, reserves both question and future-answer storage,
checks per-user and deployment thread/message storage plus active/queue/daily
limits, authorizes every selected
document, and snapshots the current corpus/embedding/provider/session state.
The API never calls a provider and receives no provider credential.

The answer worker claims FIFO jobs with `SKIP LOCKED`, a worker ID, 64-hex claim
token, heartbeat, lease, attempt and absolute deadline. Before query embedding,
before each answer/support call and inside the final transaction it rechecks the
session, current owner/enrollment, fully selected document scope, publication,
corpus revision and embedding space. Pre-provider expired leases alone may be
requeued within exponential bounds. Provider-started dead leases, handled
provider errors and whole-job timeouts are terminal until an explicit bounded
manual retry; a retry refreshes the current authenticated session but cannot
change the question/corpus/provider snapshot.

Only exact-v1 retrieved chunks enter the prompt. The question, bounded visible
history and evidence are JSON-delimited as untrusted data. Structured output is
either abstention or one-to-five ordered claims, each with a distinct retrieved
chunk UUID and byte-for-byte contiguous quote. The answer field must exactly be
those claims joined in order, so uncited prose is invalid. A separate structured
model pass must semantically affirm every claim against its quote. Unknown,
duplicate, fabricated, stale or unsupported citations fail closed; insufficient
retrieval/support commits the fixed server-issued abstention. Titles, page and
section metadata come only from current database rows.

The final transaction takes the Knowledge writer lock, locks the job/session/
principal/Subject/enrollment scope, rereads exact current sources, inserts one
assistant message plus all citation rows, and moves the job to completed. A
database trigger independently requires current corpus/space, consecutive
citation order and atomic source count. Stale claim tokens cannot persist usage or results. One job commits at
most one answer, while remote execution remains at-least-once in the presence
of unavoidable network ambiguity.

## Privacy, capacity and deletion design

Persisted page text, chunks and vectors are private teaching content. Before
upload routes write them, the operator notice must disclose retention and
embedding text transfer to the selected endpoint. Before Ask AI stores chat,
it must disclose question, bounded history and evidence transfer to the
answer endpoint. No content, vector values, prompts or answers enter routine
logs, telemetry or error messages. Backups, provider copies and exported files
have separate operator/provider expiry; database deletion cannot erase them.
The authorized `/subjects/{id}/rag/profile` response exposes only the selected
provider/model roles needed for the browser's pre-transfer notice; credentials
and private endpoint configuration remain worker-only.

Private conversation ownership is per user and Subject, including instructors.
Instructors do not inherit access to student chats. Each chat message and its
sources expire 90 days after creation, with bounded operator-run cleanup;
threads with no retained messages can then be removed. This clock and cleanup
are implemented. If a cited document
is unpublished, deleted or replaced, future history reads hide the derived
stored answer and citations, even if a citation row was removed by a cascade.
Every read also rechecks the current principal's Subject access. No historical
source-read exception is granted.

Per-revision page/text/chunk/vector limits and aggregate document/byte limits
for Subject, uploader and deployment must be enforced in transaction-scoped
admission, counting active, private, staged and failed retained revisions. A
changed-content upload cannot replace an old quota charge until its old
revision is actually removed. The capture path applies the schema reservations
atomically. Account export allowlists instructor-owned Knowledge and only that
principal's own Ask AI threads/messages/sources/jobs. Account deletion locks and
refuses active answer jobs; Subject/thread/account cascades fence stale claims
through missing job/token state. Operators still stop/drain writers before
account deletion as documented.

The [authored retrieval corpus](../RAG_EVALUATION.md) fixes exact-search,
publication, revision, support and abstention criteria before tuning. The
[privacy guide](../PRIVACY.md) and [database operations](../DATABASE_OPERATIONS.md)
own deployed retention and recovery procedures.
