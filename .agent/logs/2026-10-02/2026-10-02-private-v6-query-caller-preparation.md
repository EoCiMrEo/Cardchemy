# Inert private v6 embedding caller preparation

## Scope and implementation

Added [the prospective outer caller](../../../scripts/run_private_query_vectors_v6.py)
and [synthetic contracts](../../../backend/tests/test_private_query_vectors_v6_caller.py)
under standing aligned implementation authority. Default invocation reads no
inputs, settings, key or database and makes zero provider calls. Preparation
binds exact source/gold/question/code and embedding-space/profile hashes.
Execution stays disabled pending a separate exact twelve-request envelope,
fixed fresh UUID and matching process token.

The caller accepts only a process-injected embedding key, whitelists the
child environment and constructs validated Settings with file loading off.
Ask, generation, source judging and answer execution are disabled; unrelated
role credentials/configuration are rejected. Durable launch/worker/component
claims prevent replay through another output directory. The unchanged audited
Windows supervisor is reused with isolated function globals, assigning the
suspended worker to a named four-CPU/two-GiB kill-tree Job before resume and
enforcing a hard 360-second worker deadline. Historical files are unchanged.

Two review findings were corrected before any real invocation: completed or
failed safe aggregates are now persisted exclusively in private Temp instead
of disappearing into hidden child stdout; and Windows venv redirector PID
is permitted only as the current interpreter's direct parent, after current
named Job/limit verification. Arbitrary ancestors/unrelated PIDs are rejected.
A missing aggregate after interruption means physical calls/cost may be
unknown, never zero. Source authorization must be refreshed before later
private source transfer; this embedding stage sends current questions only.

## Verification and limits

**107 synthetic/native-local contracts passed** with the preserved query
builder/native suites. The mock HTTP transport verifies twelve singleton
batchEmbedContents requests, QUESTION_ANSWERING, 1,536 dimensions, exact
current questions and zero retry. A mocked HTTP503 stops once and persists
only safe aggregate uncertainty. The native local child proves the venv
redirector/direct-parent relationship without a key, source, DB or network.
Default CLI separately returned unexecuted/zero calls. Compilation passed
before the final direct-parent correction; targeted tests exercised that
final correction. The independent reviewer identified that functional PID
issue, then its review was interrupted by agent usage limits; no final
independent-review pass for the corrected caller is claimed.

No real private input or profile was read by these checks, no query vector
was produced, no provider key or request/DB write occurred. Execution remains
`LIVE_AUTHORIZED=False`, no approval UUID. The next necessary preparation is
current non-secret profile/input admission and exact provider approval;
synthetic checks alone do not establish actual retrieval/display quality.
Lane 6 remains **3/7**, Ask off, goal active.
