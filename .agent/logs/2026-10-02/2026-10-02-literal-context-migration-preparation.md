# Literal admission context migration preparation

## Scope and starting state

The matching successor plan authorizes additive offline preparation for
`related_knowledge_navigation_v7` / `visual_source_id_v3`. The retained stack
remains at 0031 with Ask disabled. The public continuation retains its own
immutable code and provider authorization; this work makes no provider request,
database mutation, settings change, or rollout.

The existing dirty main worktree and root configuration were preserved. Root
guidance, relevant project/module orientation, ADR-024, the matching successor
plan, prior pure-context evidence and the 0031/model/trigger contracts were read.
Existing used migrations were inspected, not edited.

## New paths and contract

- `backend/alembic/versions/20261002_0032_literal_subject_context.py` is a new
  additive revision after `20261001_0031`.
- `backend/tests/test_literal_subject_context_migration.py` exercises invented
  rows, schema shape and exact historical trigger round trips offline.
- `backend/tests/postgres/test_postgres_literal_subject_context.py` prepares
  actual guarded disposable PostgreSQL enactment checks.

V7 alone permits the prospective 120-second source-ID ceiling, HIGH thinking,
4,096 thinking-inclusive output and `visual_source_id_v3`. V5/V6 retain their
exact historical contract and maximum 60-second snapshots. All source-only
policy/stage/reference guards include the new identity without changing old
branches: at most one query embedding and one source judgment, zero answer or
support stages, zero automatic retries. No migration enables Ask.

The job gains two immutable nullable fields:
`source_context_policy_version` and `source_context_admission_sha256`. Old jobs
must keep both null. New V7 jobs require the literal admission version and a
lowercase 64-character SHA256. Existing immutable job identity binds corpus
revision, embedding space and provider snapshots.

The separate `rag_answer_question_context` binding table stores only scoped
message identities, raw-question clarity, exact content hashes, UTC timestamps
and optional literal character/UTF8 offsets and subject hash. It copies neither
the earlier body nor the literal subject. Its 21 fields are immutable. Exact
current/preceding role, scope, time, SHA and literal-byte checks run on insertion.
The runtime pure resolver remains responsible for conservative grammar,
uniqueness and trusted canonical admission-hash recomputation; the database is
not presented as a natural-language resolver.

## Admission ordering and retention

The thread is locked during context insertion. If a preceding user ID is
provided, it must be the newest USER of the same owner/thread/Subject with a
strictly earlier timestamp, ordered by timestamp and ID. Selection has no
expiry, hidden or content filter that could skip an unsafe latest turn and
fall back to an older topic. Bound messages must still be unexpired. Equal-time
and later queued turns cannot become preceding context.

Raw-clear jobs have no preceding/subject fields. Raw-unclear jobs may instead
persist a conservative no-ID/no-anchor binding for clarification if the latest
turn is missing, expired or unusable. Such a binding never dispatches source
judgment; no older question is searched as a substitute.

A deferred constraint trigger requires the matching binding at the end of new
job INSERT transactions. It does not re-fire on retention deletes. The
predecessor message FK cascades into this binding row only; it cannot delete a
newer job or its current question. Missing bindings must fail before provider
execution. Completed references remain subject to their independent current
source authorization. Current-question or job deletion still removes that
job's binding. A downgrade refuses any V7 job rather than deleting or
reinterpreting snapshots.

## Model/runtime integration handoff

The context service agent now owns ORM parity. The exact new migration
constants to mirror are `NEW_IDENTITY`, `NEW_RESULT`, `JUDGE_SNAPSHOT`,
`NEW_RETRIEVAL_PAIR`, `NEW_STAGE_POLICY`, `VISUAL_STAGE_CAP`,
`NEW_VISUAL_INDEX`, `NEW_REFERENCE_POLICY`, `NEW_REFERENCE_PAIR`,
`JOB_CONTEXT_CHECK` and `CONTEXT_SHAPE_CHECK`. Mirror the table columns,
three named scoped foreign keys, named primary key and predecessor index;
export `RagAnswerQuestionContext`. The new pure service captures before current
message insertion under the enqueue thread lock and rehydrates/rechecks that
immutable binding before retrieval/judgment/completion. This log is a handoff,
not a claim that those callers or models were changed by this subtask.

## Checks actually performed

- 52 new offline migration tests collected and passed.
- Combined new migration, literal-context and visual-v3 units: **235 passed**.
- The wider batch included the preserved 0031 migration tests: **247 passed,
  1 failed** because a shared prospective release-policy constant had advanced
  to V7 while that old test still expected V6. Root was notified and owns the
  expectation update; this subtask did not edit the old test or migration.
- 26 new PostgreSQL tests collected successfully. Collection is not database
  enactment proof. They cover deferred admission, scoped foreign keys,
  predecessor/current deletion direction, hash and UTF8 span tampering,
  immutability, strict latest selection without older fallback, future/equal
  timestamps, frozen profile limits and source-only physical-stage caps. All
  data is invented and each test rolls it back.
- No PostgreSQL upgrade/downgrade/re-upgrade, head/drift check, concurrency
  execution, retained cutover, provider call, or Ask activation was performed.

Required next evidence is ORM parity plus the documented guarded disposable
PostgreSQL harness, including actual 0032 upgrade/downgrade/re-upgrade, trigger
and retention checks. Never downgrade the retained installation for a test.

## Prepared file identities

- Migration SHA256:
  `31f325c6d1b53c4b5a0f85a2c70a8acd4f7a4cfa20e6575177a9ebf9d67c64b9`.
- Offline migration test SHA256:
  `765309cd5288878353d76b4ebebcca089e680974d36fd9044b98f21969911a83`.

No private question, literal subject, lecture text, key, prompt or model output
appears in this evidence. No temporary provider/container/retained resources
were created by this migration-preparation subtask.
