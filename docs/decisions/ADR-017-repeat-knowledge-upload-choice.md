# ADR-017: Repeat Knowledge upload choice and revision reuse

## Status

Accepted 2026-09-22 for product-quality Lane 3. Its new-capture cancellation
rule is narrowed by [ADR-020](ADR-020-validated-card-choice.md) when Knowledge
has been independently reviewed or published. This supersedes ADR-012's
assumption that a distinct same-byte upload without a document link always
creates another document and narrows its cancellation rule to captures created
by the cancelled job. ADR-012's same-operation idempotency, Subject ownership,
publication, revision, privacy and worker boundaries remain accepted.

## Context

The source checksum is available only after the API has accepted and validated
the bounded PDF bytes. Before this decision, a new operation without an explicit
document link created another private document even when the latest revision of
an owned document in the same Subject had identical bytes. That duplicated
storage, indexing and embedding work. Silently deduplicating would be unsafe:
the instructor may intend a separate private document, and a checksum lookup
must not reveal content in another Subject.

An explicit upload to an existing document also needs different semantics. If
its bytes match the latest revision, creating another immutable revision cannot
represent a content change. Flashcard generation, Knowledge revisioning and
Knowledge publication remain independent actions.

## Decision

The API validates and encrypts the uploaded PDF, records its SHA-256 checksum
and charges the applicable generation or Knowledge-only raw upload quota before
checking for an exact-byte match. A daily job/upload receipt remains charged
after accepted bytes even when the later outcome is no change, reuse,
cancellation or choice expiry. The encrypted source counts against retained
source limits until the selected continuation or cleanup removes it.

For an explicit owned `document_id`, the service compares the checksum with the
latest content revision under the Knowledge write lock. An exact match produces
the typed `no_changes` outcome and links the existing document and revision. It
creates no content revision, index job, embedding request or Knowledge storage
reservation. A Knowledge-only job completes and removes its temporary source.
A combined job keeps the source for its explicitly requested flashcard pipeline,
skips Knowledge capture and follows normal source cleanup. Changed bytes follow
the ordinary new-revision, private-review and indexing path.

For a new operation without `document_id`, the service searches only the same
Subject and its owning uploader for a document whose latest revision has the
same checksum. It never queries or signals a cross-Subject match. With no match,
ordinary capture creates a separate private document. With a match, the job and
encrypted source enter durable `awaiting_choice` state for the configured upload
reservation interval. Polling or reloading reconstructs the candidate title,
expiry and current reuse eligibility from server state.

Reuse is available only when the matching latest content revision is active and
ready and has an active, complete, ready index in both the Subject's active
embedding space and the currently configured exact embedding space. Private and
Published documents are both eligible; publication is never changed by reuse.
Choice submission rechecks checksum, current revision, Subject/uploader scope and
space/index compatibility under the Knowledge write lock and a row lock.

The typed choices are `reuse` and `separate_copy`:

- `reuse` links the job to the existing document and exact revision, records the
  `reused` outcome and performs no capture, title mutation, review, publication,
  indexing or embedding work. A Knowledge-only job completes; a combined job
  continues only its requested flashcard generation.
- `separate_copy` records that outcome and queues ordinary capture. The new
  document starts Private and follows the existing review, indexing and
  publication rules.

The first committed choice wins. Its operation key is stored as a hash; replaying
the same choice returns the durable job, including after a lost response or page
reload, while a different later choice conflicts. Deleting or changing the
candidate before reuse makes the choice stale and fail closed. Expiry cancels
the whole job and deletes the encrypted source. Explicit Cancel does the same;
there is no implicit generate-cards-without-Knowledge continuation.

A reused revision is not owned by the referencing job. Job cancellation,
failure, history deletion or capture rollback cannot delete or unpublish it,
and existing flashcards remain independent. An explicit owner action to remove
the Knowledge document retains the established document-deletion semantics:
its revisions are removed, nullable job/set links detach and flashcards survive.

Migration `20260922_0015` adds the pending state, scoped candidate foreign key,
choice/outcome fields, constraints and active-job indexing. Its downgrade
refuses while a pending choice or retained `reused`, `unchanged` or typed outcome
exists because the previous schema cannot represent that history.

## Rationale

Waiting until bounded upload completion is the first point where exact-byte
identity is trustworthy. A durable choice supports reload, expiry and concurrent
requests without moving authority into browser state. Rechecking eligibility at
submission prevents a ready revision or embedding-space cutover from becoming
stale between warning and choice. Keeping raw transfer accounting independent
from avoided Knowledge work preserves abuse limits while making the saved
storage, index and provider work explicit.

## Consequences

- API clients must handle `awaiting_choice`, `duplicate_candidate`,
  `choice_expires_at`, and the `no_changes`, `reused` and `separate_copy`
  outcomes. The browser must expose Reuse only when the server reports it ready.
- Operators should expect accepted duplicate bytes to consume the applicable
  daily upload allowance even when no Knowledge revision is added. Choice
  sources remain transient and are removed on completion, cancellation or
  expiry.
- A rollback from `0015` is a pre-use or verified-backup operation. Operators do
  not erase retained decisions merely to make a downgrade pass.
- Tests must cover Subject/owner isolation, changed and exact bytes, private and
  published eligibility, incompatible/incomplete indexes, concurrent choices,
  reload, expiry, retry, cancellation, failure and source cleanup.

## Related areas

[Prior Knowledge decision](ADR-012-subject-knowledge-and-rag-boundaries.md),
[durable work](ADR-008-postgresql-durable-jobs.md),
[deletion ownership](ADR-005-deletion-cascades.md),
[Knowledge flow](../architecture/SUBJECT-KNOWLEDGE-FLOW.md),
[data model](../architecture/DATA-MODEL.md),
[configuration](../operations/CONFIGURATION.md),
[database operations](../database/DATABASE_OPERATIONS.md),
[generation service](../../backend/app/services/generation.py).
[ADR-020: private validated-card choice](ADR-020-validated-card-choice.md).
