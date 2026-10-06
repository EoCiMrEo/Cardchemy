# ADR-020: Retain validated candidates for an explicit smaller-card choice

## Status

Accepted 2026-09-25 for product-quality Lane 6. This narrowly extends the
complete-result rule in [ADR-006](ADR-006-grounded-generation-validation.md),
the atomic generation finalization in
[ADR-008](ADR-008-postgresql-durable-jobs.md), and the cancellation ownership
rule in [ADR-017](ADR-017-repeat-knowledge-upload-choice.md). A generated set
still contains exactly the instructor-confirmed number of strictly validated,
unapproved cards; no partial set is exposed.

## Context

A bounded generation run may validate some distinct, source-grounded cards but
fall short of the requested count. Existing failure handling discards those
intermediate cards. A manual retry repeats provider work and may still fail;
the final persisted `accepted_card_count` is zero because no complete set was
committed, even if intermediate valid cards existed. The operator approved
keeping the original target exact and offering an explicit smaller target from
the validated candidates, without another provider call after confirmation.
The observed candidate count is a lower bound from that attempt, not a claim
about all facts in the PDF.

The combined upload flow may independently create Knowledge before generation
finishes. A newly captured document can become reviewed or published while the
card job is still active. Cancelling the card job must not silently erase such
independently accepted Knowledge.

## Decision

Only cards that have passed the existing structural, four-option, quote/answer
containment, trusted source provenance, quality and cross-card duplicate checks
may enter temporary storage. Raw provider cards never enter this state. The
normal full-target success path remains an atomic unpublished draft set with
exactly the originally requested count.

If bounded generation is exhausted with `0 < N < requested_card_count`, the
fenced worker atomically stores at most `N` validated candidates in an
owner-private, encrypted, size/count-bounded job payload and transitions the
job to `awaiting_card_choice`. It records the number `N` and a finite expiry;
there is no `FlashcardSet` or `Flashcard` row yet. The original requested count
is immutable. The staged payload uses the existing independent source-storage
key with a distinct encryption domain and job/attempt/policy-bound authenticated
associated data. The source PDF remains temporary and encrypted only until
confirmation, explicit retry/cancel or expiry. Its retention and staged-byte
limits must remain bounded by validated configuration and deployment capacity.
The status occupies the owner's active-job capacity but is not a worker queue
claim. Stale workers cannot overwrite candidates after losing their claim.

The authorized owner may submit a new hashed idempotency key and an exact
`card_count` from 1 through `N`. A row-locked transaction rechecks owner,
Subject, status, expiry, payload authenticity, candidate count and the
applicable validation/policy snapshot. It deterministically selects a diverse
subset and rechecks canonical card shape, four-option validity and duplicate
constraints before commit. The fenced worker already established the staged
cards' quote containment and server-derived provenance against trusted chunks;
confirmation does not re-extract the PDF or ask the provider again. It creates
exactly that many unapproved cards in one unpublished draft set, records the
chosen final target separately from the original request, removes the staged
payload and temporary PDF, and completes the job atomically. This action makes
no provider request and no new AI quota charge. A replay with the same key and
count returns the committed result; a changed target or conflicting key fails
without another set. The API and browser expose only safe counts/status until
the set is committed, never partial candidate content.

The encrypted candidate payload authenticates the duplicate-similarity
threshold used for its generation attempt. Confirmation uses that saved
threshold so a later operator configuration change cannot silently invalidate
the pending choice. The choice takes the Knowledge write lock before the job
row lock, consistent with Subject/Knowledge deletion and cancellation; parent
deletion and confirmation therefore serialize. Payloads created under the
earlier v1 choice policy, which did not save the threshold, fail closed after
the v2 policy upgrade. Operators must drain or let those choices expire before
upgrading.

When `N = 0`, the job follows the ordinary insufficient-cards failure and has
no smaller-target choice. On choice expiry, cleanup deletes staged candidates
and temporary source and records a terminal expired failure without a set or
automatic provider replay. Explicit Cancel ends the job and removes staged
data and source. A separate owner-requested attempt to pursue the original
target may start only through the existing bounded admission, fresh idempotency
and quota path, after a clear extra-cost/unknown-prior-cost disclosure; it is
never triggered by smaller-target confirmation. Existing provider call, token,
cost, retry and whole-job bounds still apply to the originally authorized
attempt and any explicit new attempt.

Cancellation may remove a new, still-private and unreviewed Knowledge capture
created solely by the job, preserving the established rollback intent. A
reviewed or published capture is independently owned Knowledge and survives
card-choice expiry and cancellation. Reused or unchanged Knowledge also
survives. Under the Knowledge write lock, publication and cancellation must
serialize so a reviewed/published revision cannot be removed by a stale choice
or cleanup worker. Ordinary deletion remains an explicit owner action.

The new Alembic revision adds durable state, bounded payload and constraints.
Downgrade with a pending choice or retained incompatible choice history must
refuse rather than discard user data. Backup/restore, source-key rotation and
retention procedures include pending choices. The browser must recover the
state after reload and provide an accessible exact-count confirmation.

## Rationale

The instructor chooses the revised product outcome after seeing how many cards
actually passed, avoiding an automatic extra paid call or a surprise partial
set. Encrypting only independently validated candidates limits exposure while
fenced durable state preserves reload, cancellation, expiry and concurrent
choice safety. Atomic finalization retains ADR-006/008's essential invariant:
one job creates at most one exact-count result set whose cards passed the
server-owned evidence boundary.

## Consequences

- The `awaiting_card_choice` status, observed valid count, expiry and selected
  final count are distinct from the existing same-Subject Knowledge choice and
  cumulative rejected-card telemetry. A response must not call the observed
  `N` a maximum the document can ever support.
- Staged candidate bytes are private transient data, included in per-user and
  deployment capacity/retention controls. Key rotation drains or expires
  pending choices; account/Subject deletion and explicit Cancel clean them.
- Tests must cover exact original and smaller targets, zero candidates,
  expiry, replay/conflict, two simultaneous confirmations, stale worker,
  cancellation, source-key mismatch/rotation, storage quotas, reload, and
  published Knowledge racing with Cancel. No provider call is permitted on
  smaller-target confirmation.
- Existing accepted candidate/quality checks remain mandatory. Temporary
  storage and server confirmation are not an approval or publication action.

## Related areas

[Generation flow](../architecture/AI-GENERATION-FLOW.md),
[data model](../architecture/DATA-MODEL.md),
[AI evaluation](../ai/AI_EVALUATION.md),
[database operations](../database/DATABASE_OPERATIONS.md),
[generation service](../../backend/app/services/generation.py),
[generation worker](../../backend/app/workers/generation.py),
[generation UI](../../frontend/src/components/generation/GenerationJobCard.tsx),
[ADR index](ADR-000-INDEX.md).
