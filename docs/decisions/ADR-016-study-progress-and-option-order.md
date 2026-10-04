# ADR-016: Study progress and displayed option order

## Status

Accepted 2026-09-22. Supersedes ADR-003's display and success decision while
retaining its attempted completion and mastery API meanings.

## Context

Attempting every approved card can produce 100% completion even if every answer
is wrong. The former student page labeled this as Progress and showed a trophy
and Review Again. Displaying stored option order also repeated the content's
correct-answer position.

## Decision

Progress is the count of currently approved cards with `correct_count > 0`
divided by the currently approved card total. A later wrong review does not
remove that credit. Attempted is the count of distinct currently approved cards
with an answer, divided by the same total. Accuracy is the sum of correct
attempts divided by correct plus incorrect attempts on those approved cards;
timeout and explicit no-answer count as incorrect. Mastery remains the share of
approved cards in `review` or `mastered`. All empty denominators yield zero and
percentages round to one decimal.

The existing `correct_count`, `studied`, `completion_percentage`, and
`mastery_percentage` API fields keep their meanings. New explicit fields are
`ever_correct_count`, `progress_percentage`, `attempted_count`,
`attempted_percentage`, and `accuracy_percentage`. The student page uses
`ever_correct_count == total` with `total > 0` for trophy, green completion
styling and Review Again. An ended study session alone does not imply set
completion.

Each card presentation shuffles a copy of its four options once. Display order
stays stable during rerenders, countdown, save retry and feedback. The client
submits option text; the server resolves it against canonical stored options and
retains its atomic answer receipt and grading rules.

## Rationale

Correct-card coverage matches the learner's visible milestone. Attempted and
accuracy expose participation and repeated-answer quality separately. Exact
count comparison prevents rounded percentages from marking an incomplete set
complete. A presentation-only shuffle varies answer position without changing
persisted cards, correctness, or idempotency identity.

## Consequences

Approving, unapproving or deleting a card changes current denominators and
included attempt totals without rewriting historic answer records. The browser
labels each metric separately and treats session completion as a neutral state.
Backend and frontend contracts must evolve together when adding progress fields.

## Related Areas

[Previous decision](ADR-003-completion-and-mastery.md),
[study flow](../architecture/STUDY-PROGRESS-FLOW.md),
[progress service](../../backend/app/services/flashcard.py),
[student set page](../../frontend/src/pages/student/StudentSubjectDetails.tsx),
[study page](../../frontend/src/pages/student/StudyMode.tsx).
