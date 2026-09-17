# Study and Progress Flow

Current truth verified against code: 2026-09-16.

## Purpose and scope

Describe the online student study loop, exactly-once answer effects and separate
completion/mastery metrics. There is no offline sync API or durable browser
answer outbox.

## Key components

[Study router](../../backend/app/routers/study.py) owns authorization/commit;
[flashcard service](../../backend/app/services/flashcard.py) owns queries,
answer resolution, receipts and scheduling;
[study schemas](../../backend/app/schemas/flashcard.py) define contracts;
[models](../../backend/app/models/flashcard.py) persist progress and receipts.
The browser flow lives in [StudyMode](../../frontend/src/pages/student/StudyMode.tsx)
and the [frontend study service](../../frontend/src/services/study.ts).

## Primary flow

1. `GET /study/sets/{set_id}/session` requires a student, subject enrollment and
   a published set. It returns approved cards through `StudyCardResponse`,
   excluding the correct answer and provenance. Limits are 1–100 (default 20).
2. Default `due` mode selects unseen cards or cards with null/expired review
   dates using database filtering, stable ordering and `LIMIT`. `review_all`
   ignores due dates and orders least-recently-reviewed cards first.
3. The client submits exactly one selected option text or index (0–3), or an
   explicit null for no answer/timeout, to `POST /study/progress`. It sends one
   8–128-character visible-ASCII `Idempotency-Key` per logical answer.
4. The route rechecks enrollment, publication and approval. The service resolves
   the selection against the canonical stored options, derives correctness and
   assigns quality 5 for correct or 1 for incorrect/no-answer.
5. The service hashes the key and canonical card/index fingerprint, atomically
   reserves a receipt, UPSERTs missing progress and locks that progress row.
   Progress mutation and the exact JSON response receipt commit together.
6. Same key/same fingerprint returns the stored response without another
   counter update; changed reuse returns typed 409 `idempotency_key_reused`.
   Distinct-key concurrent answers serialize their progress updates.
7. The browser reveals feedback/advances only after persistence succeeds. An
   ambiguous failed save retries the same key/payload. The next card gets a new
   key; rapid click/timer paths share a submission lock.

## Scheduling and metric invariants

| Rule | Current implementation |
| --- | --- |
| Incorrect or no answer | Increment incorrect count, reset interval to 0, status `learning`, review due immediately. Ease factor is unchanged on this branch. |
| Correct answer | Increment correct count; interval progresses 0 → 1 → 6 → rounded previous interval × ease factor. Then adjust ease factor with the quality formula, floor 1.3. |
| Status | `new` before an attempt; `learning` below 7 days; `review` at 7–20; `mastered` from 21 days. |
| Completion | Cards with `last_reviewed` / total approved cards × 100. Attempting a card counts even when incorrect. |
| Mastery | (`review` + `mastered`) / total approved cards × 100. |

Percentages round to one decimal and empty sets return zero. `correct_count`
is accumulated successful attempts, not a distinct-card or completion metric.
The session's `total_due` is the number of returned cards after the requested
limit; `review_cards` is a status count, not an independently computed global
due queue size. Set publication is checked before study/progress reads.

## Failures and edge cases

Invalid selections or headers return 422; mismatched receipt reuse returns 409;
missing/unpublished/unapproved answer targets return 404; enrollment denial
returns 403. Transaction rollback releases the receipt reservation and undoes
progress changes together. Receipts cascade on user/card deletion and replays
still pass current content/access checks before receipt retrieval.

The general card GET endpoints also permit enrolled students to read approved
published cards with `back_content`. The answer-free guarantee applies to the
study-session contract only. Changing that broader read policy is separate
remediation. Untimed sets avoid timers; timed sets use 5–3600 seconds per card.

## Sources, verification and related decisions

See [study progress tests](../../backend/tests/test_study_progress.py),
[session tests](../../backend/tests/test_study_sessions.py),
[idempotency tests](../../backend/tests/test_study_idempotency.py),
[PostgreSQL transaction tests](../../backend/tests/postgres/test_database_integrity.py),
[testing commands](../TESTING.md) and [backend map](../../backend/MOC.md).
Decisions: [server correctness](../decisions/ADR-002-server-derived-correctness.md),
[completion/mastery](../decisions/ADR-003-completion-and-mastery.md) and
[four-option cards](../decisions/ADR-001-four-option-cards.md).
Continue with [data model](DATA-MODEL.md) and [system overview](SYSTEM-OVERVIEW.md).
