# Subject Knowledge data boundary and lifecycle

Current source-only Ask uses `related_knowledge_navigation_v8`, `visual_source_id_v5` and `literal_subject_admission_v2` at Alembic head `20261002_0033`. Fresh installations remain default-off. The retained local installation was enabled after its measured release gates on 2026-10-04; see the [closure evidence](../../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md). Historical policies and database rows remain immutable and readable; they cannot execute as new jobs.

## Ownership and state

Knowledge belongs to an instructor-owned Subject. The uploader must be that
Subject's instructor; a student's enrollment grants access only to eligible
published content once retrieval exists. A document has stable identity and
immutable content revisions. Original page numbers, including empty pages, are
retained as canonical extracted text, and chunks/vectors belong to one content
revision and one explicit embedding space. Temporary encrypted source PDFs keep
the existing generation lifecycle. ADR-023 adds a separate encrypted original-PDF
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
capture or reuse association. A pending duplicate candidate is an owner/Subject-
scoped choice hint, not ownership of that document. Historical jobs/sets have
null links; no old PDF pages are invented from cards. Deleting a document clears
pending candidate hints, cascades pages/chunks/index jobs and detaches surviving
job/set links, preserving flashcards. Deleting job history does not delete
Knowledge. Subject/account deletion cascades owned Knowledge.
Membership is enforced by composite database constraints, not just route code.
Routes reuse `SubjectService.check_subject_access()` for current
owner/enrollment decisions and repeat the eligible Subject/document/revision
filters inside retrieval SQL. A prior route check is not enough to authorize a
later asynchronous worker claim.

## Worker and provider boundary

The generation, indexing and Ask workers use separate
PostgreSQL queues, leases and credentials. An index worker needs only the
document-embedding profile; an enabled v8 source-only Ask worker needs the
query-embedding and separate Gemini source-judge profiles with worker-only
credentials. The generation worker needs only its flashcard profile. Historical
answer-model settings describe fenced old jobs. API, email
worker and browser receive no provider keys. Operators must divide an actual
provider account/project RPM and input-TPM allowance across roles and replicas.
Quota-bucket names do not form a distributed governor.

The default RAG profiles are native Gemini under
[ADR-014](../decisions/ADR-014-native-gemini-rag-profiles.md):
`gemini-embedding-001` produces 1,536-dimensional normalized cosine vectors
with `RETRIEVAL_DOCUMENT`/`QUESTION_ANSWERING` task modes, while
`gemini-3.5-flash` was selected for the retired strict structured-answer
policy; new Ask work makes no answer-model call.
New text model selections use the closed, versioned Gemini-only catalog in
[ADR-015](../decisions/ADR-015-ask-pause-and-gemini-catalog.md). Embedding
space identity frames provider, canonical endpoint, model, revision, format,
dimensions, representation, metric and both task modes. A changed field creates
an incompatible staged space; vectors are never silently mixed.

[ADR-018](../decisions/ADR-018-gemini-embedding-2-space.md) adds optional
`gemini-embedding-2` staging under `gemini2_qa_section_v1`. It formats immutable
chunk sections and canonical text, formats questions with the answering task,
sends distinct provider `Content` objects without `task_type`, and keeps an
incompatible space hash even at 1,536 dimensions. Embedding 001 remains default.

Index jobs snapshot document/content revision, chunker version and complete
embedding-space identity, including fixed document/query task modes. Current
source-only Ask jobs snapshot the authorizing session, corpus revision,
retrieval/source policy and embedding space. Historical answer jobs retain
their answer provider/model, catalog/schema and answer/support policy
snapshots for audit but cannot execute as new work.
Old or changed policy snapshots cannot execute on the new worker. Claims recheck
cancellation and revision fences before commit;
retrieval rechecks principal access, publication and corpus/space identity in
SQL. Stale claims cannot publish vectors or Ask results. With
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
operation replays the same job; changed bytes conflict. This is distinct from a
new operation whose accepted bytes match existing Knowledge.

After bounded upload validation, the API encrypts the source, records its
SHA-256 checksum and charges the applicable raw upload receipt. Under the
Knowledge write lock it then applies the repeat-upload rules:

- An explicit owned document upload matching its latest revision returns the
  typed `no_changes` outcome. No revision, storage reservation, index job or
  embedding request is created. A Knowledge-only job completes; a combined job
  keeps the temporary source and continues only flashcard generation. Changed
  bytes create an ordinary new private revision.
- A new operation without a document link searches only the same Subject and
  uploader for a latest revision with the exact checksum. No match follows
  ordinary private capture. A match enters durable `awaiting_choice`, retains
  the encrypted source until the displayed expiry and survives page reload.
  Cross-Subject matches are neither queried nor disclosed.
- `reuse` is offered only for a current active ready content revision whose
  active index is ready, complete and in both the Subject's active and configured
  embedding space. Private and Published revisions are both eligible. Submission
  rechecks the owner, Subject, latest checksum and compatibility under the same
  write lock. It links that document/revision without capture, indexing, title,
  review or publication changes.
- `separate_copy` queues ordinary private capture. Cancel or expiry terminates
  the entire job and removes its encrypted source; neither path implicitly
  continues flashcard generation.

Choice submission stores a hashed operation key. Replaying the committed choice
returns the job; an opposite choice conflicts, and row locking makes the first
commit win. Candidate removal or revision/space drift makes reuse fail closed.
Cancellation or failure can remove only capture created by that job, never a
reused revision. The accepted raw upload remains charged for abuse control even
for `no_changes`, reuse, cancellation or expiry, while no-change/reuse avoids
Knowledge storage/index charges and embedding requests. Supported capture/
capacity failure is a safe independent outcome for a combined flashcard job. A
non-cancelled flashcard failure may retain valid private Knowledge. Raw PDFs are
still removed according to the existing transient-source policy.

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

Lane 6's historical navigation-v3 jobs snapshot
`hybrid_source_navigation_v9`. The provider-free `source_navigation_v9`
selector ranks exact canonical cues using topic overlap, section and search
ranks, and inspects eligible neighbor pages up to Â±2 before local selection.
Historical source head `0029` admitted the separate dormant v4/v9 pair. Current
head `20261002_0033` admits released visual v8/v9 while preserving earlier pairs. The same
authorized candidate paths inspect at most 30 chunks, 12 pages and 8,192
estimated tokens, then a bounded slate of at most four current canonical
pages may be judged. V8 authenticates each complete current original PDF archive
before bounded isolated Poppler rendering and sends exact page text/cues plus
faithful full-page PNGs to its source judge. The judge returns only issued IDs
and closed page/status labels;
the server derives at most three distinct exact page references. Candidate
presence and either selection method are not proof of useful displayed pages.
A transient embedding failure may use bounded local lexical SQL with the same
current-access and revision predicates, without another embedding request.
Results disclose `hybrid`, `lexical_fallback` or `not_searched`; unknown spend
stays unknown. Earlier v3â€“v7 relation-qualification experiments remain
historical and are not executable new-job policies. Their measured failures
motivated [ADR-023](../decisions/ADR-023-original-pdf-source-navigation.md).

Read-only private-course probes found that full-question FTS can miss relevant
terms, while one authorized live comparison showed current exact-vector top-five
retrieval already included the target concept. These observations do not prove
answer correctness or justify changing the retrieval policy. Any cutover needs
owner-reviewed source labels, maintained recall and latency gates, and the same
owner/enrollment, publication, revision and space filters inside both SQL paths.

## Subject Ask AI execution and default-off gate

The released new Ask path follows
[ADR-023](../decisions/ADR-023-original-pdf-source-navigation.md) and its
[ADR-024 source-ID amendment](../decisions/ADR-024-gemini-source-id-judge.md).
`RAG_ASK_ENABLED` remains default off for fresh installations. Installation
enablement requires explicit Ask/judge flags and measured source/access/release gates. A new Subject can still upload
and index Knowledge before it has an active space. New Ask admission requires
RAG, configured query embedding and source judge roles with current nonzero
prices, a matching Subject active space and the
`related_knowledge_navigation_v8` release policy. The current source fence permits that policy while installation flags and
profile/space validation remain authoritative. It does not require an answer-model profile or a
local NLI/QA bundle. Existing
authorized users may read private history and currently eligible sources and
cancel work while Ask is disabled. The [maintenance runbook](../ai/ASK_AI_SHUTDOWN.md)
defines old-job resolution, enablement, rollback and monitoring.

The API admits a private, Subject-bound question under the current user session,
owner/enrollment and selected published Knowledge scope. It snapshots corpus,
space and source-only policy, reserves one question message and a bounded job,
and never calls a provider. The worker fences claims and makes at most one
physical embedding request for the **current question** and at most one bounded
Gemini source-ID judgment request, both with zero automatic retries.
Authorized exact-vector/lexical retrieval stays within the selected,
published, ready, current-revision and active-space corpus. Immediately before
source-content egress the worker rechecks the current authorized page snapshot
and authenticated original archive; it sends only the current question, opaque
candidate IDs, bounded exact published page/cue context and bounded PNGs of
those original pages. Only an unresolved follow-up may additionally project a
unique exact literal subject (at most 160 characters/twelve words) from the
strictly preceding user question, bound immutably at admission. It does not send
that whole prior question, assistant text, full history or original PDF file bytes.
A malformed or foreign-ID judgment fails safely.
The server selects up to three distinct-page contiguous cues of at most 480
characters and derives every title, offset, revision and PDF page locally.
Under the Knowledge writer lock, it rechecks access and revisions and commits
`related_knowledge` plus ordered source offsets atomically. A valid empty
selection completes `no_match` with no references; an unresolved question can
complete source-free `clarification_needed` before remote work. V8 also permits
source-free clarification after a successful, finished, certain source judgment
for that same job/attempt; failed or uncertain calls cannot claim clarification.
Neither result creates an assistant answer message. Transient embedding
failure can use bounded local lexical candidates while preserving the failed
stage, unknown spend and visible `lexical_fallback` mode. Judge unavailability
is a safe provider failure, not a true no-match. Old v3 and answer-policy jobs
cannot execute under the new worker.

Each read rechecks the whole bundle against current owner/enrollment, selected
documents, publication, content/index/corpus revision, embedding space,
offsets and expiry. Any failure hides the whole bundle. The browser labels
these as related published course material, not verified answers, and offers
an authenticated read of the corresponding **original lecture PDF page**.
A revision-bound archive retains validated original bytes separately from the
job source. Missing old originals require instructor exact-SHA/page attachment;
the UI may show extracted text with an explicit unavailable-original label. A
manual retry separately discloses possible additional embedding and judgment
cost and unknown prior spend. The source-only schema and code are present in this checkout;
the v7 sufficiency gate failed and was superseded by ADR-023 navigation.
Complete public and independent private source/display gates passed for the
retained local activation on 2026-10-04; see the [closure](../../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md).
The source judge uses at most 32,768 input / 4,096 thinking-inclusive output
tokens and a 120-second provider deadline. Historical policy snapshots stay
readable but cannot execute or retry as v8. New live evaluations require their
own explicit provider and private-transfer authorization.

### Historical answer rows

The earlier three-call and two-request/local-support answer policies are
retired from new execution. Their stored messages, policies, usage uncertainty
and citation identities remain readable under current ownership, publication,
revision, expiry and source-redaction guards. Never convert them to the
current source-only policy or replay uncertain provider work. Durable rationale
is preserved in [ADR-019](../decisions/ADR-019-two-request-local-support-ask.md),
[ADR-021](../decisions/ADR-021-related-knowledge-excerpts.md) and
[ADR-022](../decisions/ADR-022-related-knowledge-primary-ask.md).

## Privacy, capacity and deletion design

Persisted page text, chunks and vectors are private teaching content. Before
upload routes write them, the operator notice must disclose retention and
embedding text transfer to the selected endpoint. Before a source-only Ask
job, the notice discloses that the current question goes to the query-embedding
endpoint. Authorized retrieval runs locally. When candidates exist, at most
one separate Gemini source-ID judgment receives bounded published page text and
original-page PNGs. An unresolved follow-up may additionally transfer only its
immutably admitted unique literal subject from the strictly preceding user
question, at most 160 characters/twelve words. Full history and assistant
responses are excluded; no answer-model or local-verifier request is made.
No content, vector values, prompts or answers enter routine logs, telemetry or
error messages. Backups, provider copies and exported files
have separate operator/provider expiry; database deletion cannot erase them.
The authorized `/subjects/{id}/rag/profile` response exposes only the configured
query-embedding and source-judge roles/models, bounded transfer capabilities
and whether the active embedding spaces match, as needed for the browser's pre-transfer notice; credentials and
private endpoint configuration remain worker-only. The browser refreshes this
profile immediately before enqueue and stops if it changed.

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
atomically. A duplicate-choice source counts against temporary retained-source
capacity until continuation or cleanup, while its deletion-resistant daily raw
upload receipt remains distinct from Knowledge storage reservations. Account
export allowlists instructor-owned Knowledge and only that
principal's own Ask AI threads/messages/sources/jobs. Account deletion locks and
refuses active answer jobs; Subject/thread/account cascades fence stale claims
through missing job/token state. Operators still stop/drain writers before
account deletion as documented.

The [authored retrieval corpus](../ai/RAG_EVALUATION.md) fixes exact-search,
publication, revision, support and abstention criteria before tuning. The
[privacy guide](../security/PRIVACY.md) and [database operations](../database/DATABASE_OPERATIONS.md)
own deployed retention and recovery procedures.
