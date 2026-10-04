# v8 runtime: independent boundary review

## Scope and authority

Independently review the authorized, prospective source-only v8 integration
before retained cutover. The implementation agent owns runtime changes and its
positive tests; this reviewer preserves those files and adds only missing
negative PostgreSQL coverage in a separate test module. No retained operation,
operator configuration/key read, provider call, private transfer or activation
is performed by this review.

Starting checkout: dirty `main` at
`6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`. Earlier operating guidance,
orientation, subsystem maps and dated Lane 6 context remain applicable.

## Source reviewed

- [Settings and release-policy fence](../../../backend/app/config.py).
- [Persisted jobs, context, result and stage constraints](../../../backend/app/models/rag.py).
- [Admission and retry service](../../../backend/app/services/rag_answers.py).
- [Immutable v2 admission capture/rehydration](../../../backend/app/services/rag_question_context_v2.py).
- [v5 visual preparation](../../../backend/app/services/source_visual_preparation_v5.py)
  and [pure contract](../../../backend/app/ai/source_judgment_visual_v5.py).
- [Worker claim, stage, pre/post-quota and completion fences](../../../backend/app/workers/rag_answer.py).
- [v5 one-request provider](../../../backend/app/ai/providers/source_visual_v5.py).
- [Additive 0033 migration](../../../backend/alembic/versions/20261002_0033_visual_clarity_policy.py)
  against the existing 0032 context/parent guards.

The exact new snapshot is `related_knowledge_navigation_v8` /
`visual_source_id_v5` / `literal_subject_admission_v2`. Historical v7/v3/v1
rows retain their original meanings; the new worker/profile and manual retry
path fence them from reinterpretation. Only the raw-clear branch gains the
bounded context-v2 routing repair. Unresolved context still requires the
original v1 unique literal-subject grammar and exact byte/character offsets.

The conservative parser excludes a contradictory cue flag on a non-useful
category; it does not promote a page or bypass global output validation.
Authorized exact sources/PDF bindings and context are rechecked before stage
admission, after quota wait before HTTP, and at atomic completion. Provider
transport remains one issued-ID/category request, with zero automatic retry,
no answer or verifier call and no full conversation transfer.

Migration 0033 extends the source-only job/result/profile checks, matching
context-parent/admission guards, stage policy/caps and unique physical-attempt
index. It does not rewrite historical rows or enable Ask. Downgrade refuses
while v8 job snapshots exist. No source blocker was found in this bounded
static review; this is not a substitute for real PostgreSQL enactment.

## Independent missing-negative coverage

Added [test_postgres_visual_clarity_v8.py](../../../backend/tests/postgres/test_postgres_visual_clarity_v8.py)
without modifying the implementation agent's existing nine positive/profile
cases or the frozen v7 helper defaults. Its fifty-four cases cover:

- Explicit NULL fences for all v8 source-judge snapshot fields and the
  admission hash, avoiding PostgreSQL CHECK acceptance through SQL UNKNOWN.
- Exact retrieval/profile/price/token/thinking/answer-field boundaries and
  rejection of a v8 contract under the old v7 policy.
- Existing wrong current-message identity, foreign scope, changed current or
  preceding hash, literal hash and character/UTF-8 offsets.
- Immutable context/job policy updates, exact harmless no-op preservation,
  changed current/predecessor content or expiry, and safe predecessor deletion
  without rebinding or deleting the retained job.
- Correct stage-parent policy, zero answer/support/local-verifier stages,
  one physical embedding/judgment, zero retries and prevention of replay under
  a new worker attempt within the same manual attempt.

All data and credentials are invented disposable fixtures. Tests import no
provider executor, operator Settings or private source. Every fixture rolls
back its inserted rows.

## Verification and remaining boundary

- Fifty-four new PostgreSQL cases collected successfully. Collection alone
  is not a PostgreSQL pass.
- The first root full PostgreSQL run reached **239 passing, 11 failing and
  three skipped** cases. All eleven new-file failures occurred before their
  negative assertions because this reviewer's synthetic running fixture used
  a 32-character claim token; the existing claim constraint requires 64.
  Corrected only that fixture. A targeted guarded disposable run then reached
  **52/54 passing**; its two replay cases directly rewrote a running attempt,
  correctly rejected by the pre-existing transition guard. Those fixtures now
  reclaim through running-to-queued-to-running before asserting stage replay
  rejection. Both failed runs remain recorded; no runtime guard was relaxed.
- Final targeted guarded disposable PostgreSQL run: **54 passed in 13.18
  seconds**, with migration head/drift and empty disposable base/head
  downgrade/re-upgrade passed. The harness confirmed owned temporary container
  and generated credential cleanup. No retained schema was downgraded.
- Independently ran pure migration, context-v2, visual-v5 and provider contracts:
  **177 passed in 13.91 seconds**.
- The root task owns the guarded disposable PostgreSQL run including these
  cases, head/drift/base/head validation, matching-image checks and retained
  backup/cutover. Its actual outcome must be recorded separately before release.
- Repository context validation passed: **37 required files, 79 active guides,
  2,085 local links**. Scoped `git diff --check` passed.
- No runtime, migration or implementation-owned test was changed by this
  reviewer. Root `.env`, retained volume/data and original PDFs were untouched.
- Zero provider calls, private transfer, retained database operations or Ask
  activation. Public/private displayed-source and spoken accessibility gates
  retain their separate scope.
