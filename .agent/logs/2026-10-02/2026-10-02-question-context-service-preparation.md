# Admission-bound question context service

## Scope and preserved state

Prepared the prospective v7 local context boundary on dirty `main`, HEAD
`6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`. Read root guidance, orientation,
project/backend maps, the Subject Knowledge flow, accepted ADR context,
current RAG model/service/worker contracts, testing guidance and the dated
literal-context successor plan. This bounded task owns only the new
[service](../../../backend/app/services/rag_question_context.py), its new
[contract tests](../../../backend/tests/test_rag_question_context.py) and this
record. Existing worker/services/configuration/models and consumed public
trial code are owned by the parent task and were not edited here.

No provider call, credential access, operator environment read, retained DB
access, migration execution, indexing, volume or enablement action occurred.
The helper is not wired into runtime by this task. Ask remains subject to the
parent's independent quality, private-transfer and release gates.

## Implementation and ordering

The helper captures the latest strictly preceding user message before the
current question is inserted. The caller assigns its UUID and admission time
first and already owns Subject/access/corpus authorization. A scoped thread
row is locked, and the latest user is selected deterministically by descending
creation time and UUID. Current/future queued turns and assistant messages are
excluded. Selecting the latest user occurs before expiry/content eligibility
checks so an unusable latest turn cannot reveal an older topic by fallback.

A clear current question captures no prior chat. A missing, expired, hidden or
unusable latest turn produces a metadata-only absent-predecessor snapshot and
clarification, without source-provider data. Ambiguous grammar in an otherwise
valid prior turn likewise remains clarification. The current model has no
persisted hidden-user flag; the helper treats any caller-supplied hidden
marker conservatively and does not infer hidden state from assistant sources.

Persistence assigns the two new job context snapshot fields and adds a new
immutable binding row in the caller's transaction. It neither flushes nor
commits implicitly and never overwrites an existing binding. Only message IDs,
scope, policy/version, timestamps, exact hashes and literal-span character and
UTF-8 byte offsets are stored; neither message body nor subject text is stored.
The new migration/model and PostgreSQL triggers are a separate ownership area.

Rehydration verifies policy/version, job/current scope, snapshot SHA, exact
message bytes/times and lifetime. For an actual predecessor binding it also
rechecks the latest strictly prior user ID, rejecting deletion, alteration,
foreign scope and backdated substitution. A conservative absent-predecessor
binding remains clarification without searching for an older or newly better
reference. Completed source-reference reads do not depend on this helper.

The returned object has representation-hidden question/prior/local-query fields
for the parent worker. A resolved local query preserves the raw current question
and literal subject without truncating qualifiers; overflow remains clarification.
The separately versioned visual builder alone determines any permitted provider
projection, which requires the parent's fresh exact private-transfer envelope.

## Checks and limitations

- `venv/Scripts/python.exe -m pytest tests/test_rag_question_context.py
  tests/test_source_judgment_visual_v3.py tests/test_source_navigation_context_v1.py -q`
  from `backend`: **239 passed**, including **56 new SQLite-backed contracts**.
- Tests use invented public-style questions, injected SQLite sessions and an
  injected binding shape. They cover strict admission ordering, deterministic
  UUID ties, future-turn exclusion, clear-question privacy, no older fallback,
  altered/deleted/expired/foreign current or prior rows, job/binding tampering,
  missing/duplicate binding, Unicode byte offsets and rollback ownership.
- One initial fixture failure was caused by SQLite numeric affinity converting
  an all-numeric UUID into an integer. The invented ordering IDs now include
  alphabetic hexadecimal digits; production behavior and ordering were unchanged.
- These contracts do not prove PostgreSQL trigger parity, worker integration,
  source-selection quality, live provider behavior or release readiness. The
  parent task must integrate the new model/migration and run the required
  disposable PostgreSQL/race, worker, frontend and release checks.
