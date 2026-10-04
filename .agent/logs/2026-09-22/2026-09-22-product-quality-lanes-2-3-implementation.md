# Product quality Lanes 2 and 3 implementation

Date: 2026-09-22

## Scope and starting context

This record covers only Lane 2 (Study metrics and option order) and Lane 3
(repeat Knowledge capture) of the active
[product quality remediation plan](../../../docs/development/PRODUCT-QUALITY-REMEDIATION-PLAN.md).
The requested short path `docs/PRODUCT-QUALITY-REMEDIATION-PLAN.md` does not
exist; the active plan is under `docs/development/`. Work began on `main` at
`6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57` with the uncommitted Lane 0/1
implementation and its documentation already present. Those changes, the real
root `.env` and the existing verified backup were preserved. The retained
installation volume recovery found during final verification is recorded below.

Before editing, the root `AGENTS.md`, Start Here, project and module maps,
relevant Study/Knowledge architecture, ADR index and ADR-003, current state,
roadmap, testing and accessibility guides, and the product-quality investigation,
plan audit/update and Lane 0/1 implementation logs were read. Three bounded
subagents audited Lane 2, Lane 3 and integration independently, then took
separate Study, backend Knowledge and frontend Knowledge ownership areas.

The operator's already recorded choices govern this work: Progress is distinct
currently approved cards answered correctly at least once, attempted and
accuracy are separate, and the displayed correct option position is shuffled
per presentation. Same-Subject exact-byte repeats require an authorized choice;
an unchanged explicit revision is a Knowledge no-op; Cancel ends the entire
job; reuse requires a ready compatible index and preserves review/publication.

## Implementation and verification

### Lane 2: Study metrics and option presentation

The progress service now derives five separate meanings from the current set of
approved cards:

- `ever_correct_count` and `progress_percentage` count distinct cards whose
  durable `correct_count` is greater than zero;
- `attempted_count` and `attempted_percentage` explicitly expose distinct-card
  attempt coverage;
- `accuracy_percentage` divides all correct attempts by correct plus incorrect
  attempts, so a timeout/no-answer lowers Accuracy;
- the compatible `studied`, cumulative `correct_count` and attempted
  `completion_percentage` fields remain available; and
- Mastery remains the existing `review` plus `mastered` status calculation.

All aggregates join through currently approved cards, so approval changes,
deletion and later additions take effect without rewriting answer history.
Empty sets return zero. The student Subject page uses the exact nonempty
`ever_correct_count == total` condition for its trophy, completion styling and
`Review Again`; rounded percentages cannot create a false success state. Its
visible and accessible copy distinguishes Progress, Accuracy, Attempted and
Mastery.

Study now shuffles a copy of the four canonical options once when a card view is
mounted. Timer renders, feedback and a failed-save retry retain that displayed
order. The selected option text is submitted, leaving server grading, stored
option order and receipt fingerprints canonical. The completion screen also no
longer uses success-only green styling for a session that contains wrong
answers. [ADR-016](../../../docs/decisions/ADR-016-study-progress-and-option-order.md)
supersedes only ADR-003's display/success decision and preserves its compatible
attempted-completion meaning.

Backend and browser coverage includes ten distinct wrong answers (`0/10`
Progress, `0%` Accuracy and `10/10` Attempted), timeout, later correct and later
wrong answers, receipt replay, set publication, approval/unapproval, deletion
and newly approved cards. Controlled randomness places the correct option in
all four displayed positions without mutating the input. Component and browser
tests assert stable order through a timer render, feedback and save retry,
durable-save-first feedback, timer/click fencing, keyboard use and mobile layout.

### Lane 3: exact-byte Knowledge decisions

Alembic revision `20260922_0015` adds the durable `awaiting_choice` lifecycle,
owner/Subject-scoped candidate link, expiry, hashed choice key and typed
`no_changes`, `reused` and `separate_copy` outcomes. Database constraints keep
status, choice, outcome and capture state coherent; candidate deletion clears
the hint, while the composite deferred foreign key prevents cross-owner or
cross-Subject linkage.

After a bounded PDF is accepted and encrypted, admission charges its deletion-
resistant raw-upload receipt and compares its SHA under the Knowledge write
lock. The implementation then behaves as follows:

- An explicit upload matching its document's current revision returns
  `no_changes`. Knowledge-only work completes without a revision, storage/index
  charge or embedding request. Combined work retains the current revision link
  and continues only the requested card generation, keeping the temporary PDF
  until normal source cleanup.
- A new-document exact match is searched only for the same uploader and Subject.
  The encrypted source remains resumable until the durable choice expiry, and
  capture/index work does not start while the choice is pending.
- `reuse` is available only for the latest ready revision with a complete ready
  index in both the Subject's active and configured embedding space, regardless
  of Private or Published review state. Submission rechecks all predicates under
  the write lock and links without capture, indexing, title or publication
  mutation.
- `separate_copy` resumes ordinary private capture. Cancellation or expiry ends
  the entire job and cleans the source. A job failure or cancellation never
  deletes a reused revision. Explicit owner document deletion retains the
  established behavior: it removes that document and its revisions, detaches
  nullable links and preserves flashcards.

Choice submission is typed and idempotent. A replay of the committed choice may
use the recovered operation after a lost response; an opposite choice conflicts,
and row/advisory locking makes the first concurrent commit win. The frontend
shows the warning only after upload, restores it after reload, handles a stale
candidate without leaking it and offers reuse, separate copy or whole-job
cancel as allowed. [ADR-017](../../../docs/decisions/ADR-017-repeat-knowledge-upload-choice.md)
owns these decisions and links bidirectionally with ADR-012.

Offline tests cover identical current revision, matching other document,
changed bytes, incomplete/incompatible/private/published revisions, owner and
Subject boundaries, candidate deletion, reload/expiry, retry, cancellation,
failure and separate copy. PostgreSQL tests cover concurrent opposite choices,
deferred scope constraints, Private and Published no-op accounting and
failure-safe cleanup. Browser tests cover resumed and idempotent choice,
incompatible reuse, cancellation and explicit unchanged revision.

## Existing-installation preservation and migration

The final operational check began with no running Compose services. Compose then
reported that the named `cardchemy_postgres_data` volume was absent and created
a fresh empty volume. The cause of that missing volume was not established. The
earlier verified pre-0014 custom archive remained at
`%TEMP%\cardchemy-20260922-pre-0014.dump` with its recorded size of 1,563,478
bytes. Its catalog validated, and a separate restore reproduced Alembic
`20260920_0013`, 3 users, 12 answer jobs and one embedding space, matching the
content-free counts recorded before Lane 0/1.

That validated archive was restored into the fresh retained volume. The current
migration image then applied `0014` and `0015` transactionally. `alembic current
--check-heads` reported `20260922_0015 (head)`, `alembic check` found no new
operations, and the same three content-free counts remained. A post-migration
custom archive was catalog-checked and copied outside the repository to
`%TEMP%\cardchemy-20260922-post-0015.dump` (1,571,968 bytes) with its SHA-256
checksum in the adjacent `.sha256` sidecar; both files are restricted to the
current operator and SYSTEM.
The separate restore database was dropped and Compose was returned to its
original stopped state without removing the recovered volume. The real root
`.env` was not changed and no secret or private content was printed.

## Verification results

- Targeted integrated Lane 2/3 backend contracts: `54 passed`.
- Complete backend offline suite: `783 passed, 101 skipped, 2 deselected` in
  140.90 seconds.
- Guarded disposable PostgreSQL service suite: `86 passed, 3 skipped, 797
  deselected` in 59.72 seconds, including current head/model drift, downgrade to
  base, re-upgrade through `0015`, final drift, constraints and concurrency.
- Targeted Study component tests: `12 passed`.
- Full frontend `npm run check -- --workers=2`: type checks and lint passed; 4
  Node unit tests and 36 component tests passed; coverage was 96.66% statements,
  87.36% branches, 93.22% functions and 97.84% lines; the production build
  passed; Chromium reported `63 passed, 1` explicitly gated live-reset skip.
- The deterministic full journey passed in both RAG-off and RAG-on/Ask-paused
  modes. It proved migration through `0015`, browser workflows, database state,
  Knowledge publication, cards, email and Study progress, then cleaned every
  disposable process, container, fixture and generated credential.
- `python scripts/check_ci.py` passed. `python scripts/check_context.py` passed
  with 37 required files, 72 active guides and 1,046 local links. Final
  `git diff --check` passed apart from Git's informational CRLF notices.

Independent final review found three strict Lane 2 evidence gaps: the wrong-only
browser case used four cards, order stability was asserted only on save retry,
and publication transition lacked a direct progress-read test. These were
expanded to the required ten-card browser state, timer/feedback snapshots and
explicit publication transition. The same review found the Study architecture
date stale, which was corrected. An initial overlapping PostgreSQL run exposed
stale expectations and cleanup pollution; the clean final service run above
supersedes it. Initial frontend and journey passes exposed exact-text locator
ambiguity and the old `100% complete` journey copy; both tests were corrected to
the new metric contract, and their complete reruns passed.

## Evidence boundaries and completion

Normal validation made no provider request and spent no paid AI quota. No hosted
CI, external deployment or manual spoken assistive-technology release pass is
claimed. Automated keyboard, focus, accessibility and mobile browser contracts
for the changed Study and duplicate-choice surfaces passed. Ask AI remains
paused; the embedding-2 and two-request/local-support work remains in later
lanes.

The active plan now records Lane 2 at 4 checked/0 unchecked and Lane 3 at 6
checked/0 unchecked. Lanes 4–6 remain pending by scope. Pre-existing Lane 0/1
work, private history, restored data, the root `.env` and the recovered retained
volume were preserved; disposable test resources were cleaned.
