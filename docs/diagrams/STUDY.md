# Study, answer receipts and progress

An enrolled student studies approved cards from a published set. The server
grades the selected option and commits scheduling/progress with a replayable
answer receipt. The browser waits for that durable acknowledgement before
feedback or advancing.

```mermaid
sequenceDiagram
  participant B as Student browser
  participant A as Study API
  participant D as PostgreSQL
  B->>A: Get due or review-all session
  A->>D: Check enrollment, set publication and card approval
  A-->>B: Approved cards without answers in this session payload
  Note over B: Shuffle a display-only copy of four options once
  B->>A: Selected option text/index or null + logical idempotency key
  A->>D: Recheck access/content and reserve receipt
  A->>D: Lock progress, derive correctness and quality, update schedule
  A->>D: Commit progress and exact response receipt together
  A-->>B: Saved correctness, correct option and progress
  Note over B: Reveal feedback and permit Next only after success
  B->>A: Ambiguous save retry with same key and payload
  A->>D: Recheck current access and read stored receipt
  A-->>B: Same result with no second progress mutation
```

Changed key reuse conflicts. Distinct logical answers use distinct keys;
concurrent answers serialize progress updates. Click and timer paths share a
submission lock. There is no offline answer outbox. General authorized card
reads currently expose answers, so the answer-free study-session contract does
not establish exam secrecy.

## Scheduling

```mermaid
flowchart TD
  Answer["Canonical server grading"] --> Correct{"Correct?"}
  Correct -->|"No answer or incorrect: quality 1"| Reset["Incorrect count +1; interval 0; learning; due now"]
  Correct -->|"Yes: quality 5"| Grow["Correct count +1; interval 0 to 1 to 6 to rounded prior times ease"]
  Grow --> Ease["Adjust ease factor; minimum 1.3"]
  Ease --> Days{"New interval"}
  Days -->|"Below 7 days"| Learning["learning"]
  Days -->|"7 to 20 days"| Review["review"]
  Days -->|"21 days or more"| Mastered["mastered"]
  Reset --> Next["Set last review and next review time"]
  Learning --> Next
  Review --> Next
  Mastered --> Next
```

Cards are `new` before any attempt. Due mode selects unseen or due cards;
review-all ignores due dates and orders least recently reviewed first.

| Metric | Meaning, restricted to currently approved cards |
| --- | --- |
| Progress | Distinct cards answered correctly at least once / total cards |
| Accuracy | Correct attempts / all attempts, including null as incorrect |
| Attempted / compatible Completion | Distinct cards attempted / total cards |
| Mastery | Cards in `review` or `mastered` / total cards |

Later wrong answers do not erase Progress credit. The UI's completion trophy
uses the exact nonzero distinct-ever-correct count, not a rounded percentage.
These metrics are separate; old API fields retain their established meanings.

Sources: [study contract](../architecture/STUDY-PROGRESS-FLOW.md),
[study router](../../backend/app/routers/study.py),
[grading and scheduling](../../backend/app/services/flashcard.py),
[progress and receipts](../../backend/app/models/flashcard.py),
[study page](../../frontend/src/pages/student/StudyMode.tsx),
[idempotency tests](../../backend/tests/test_study_idempotency.py).
