# Seed14 helper custody and execution review

## Scope and limits

Independent scoped source review of the seven new seed14 preparation, custody,
host, entry, executor, rehearsal and dispatch-guard helpers plus their focused
test file. The implementation owner is `v8_release_reconcile`; the root owns
evidence indexes and any new provider envelope. Existing private12 helpers and
runtime were not edited. No provider call, credential lookup, root environment
inspection, private packet/review read, database operation or broad scan was
performed by this reviewer.

This is code review, not a seed trial result or release approval. The owner
reported 31 focused tests passed; this reviewer read them without repeating
them. A regenerated final stage and actual keyless startup measurement are
still required before any new provider authority.

## Reviewed contracts

- The fourteen-case diagnostic keeps its own schemas, stage prefix, claim
  registry, executor flag and dispatch proof seal. Shared private12 function
  bodies are rebound to seed helper globals; source module globals and the
  private12 authority are not mutated. Seed-specific ledger and interface
  classes replace the private12 classes whose methods/defaults need new globals.
- Preparation pins all five artifacts and the complete helper/runtime code
  set. The independent review and exact reuse witness are explicitly **unsigned
  SHA-pinned evidence**, not a signature or current access grant. The 42 reused
  labels and eight new labels are bound to exact question/source metadata.
  The report does not claim signed verification or release completion.
- The actual fourteen-case roster contains fifty source slots: twelve slates
  of four and two restricted controls of one. Request preparation, exact wire
  binding, issued-ID schema and fresh guard support one to four sources without
  padding. The focused tests also exercise two and three sources. The result
  still displays at most three issued useful pages and never drafts an answer.
- Current publication, principal/Subject access, corpus/profile/revision,
  canonical text offsets, exact PDF/archive authentication and complete wire
  binding are checked in fresh rolled-back transactions before dispatch and
  after selection. A staged review does not replace those live source checks.
- Authority is checked before credential input and physical transport; CLI and
  default imports are inert. Host and entry claims precede key lookup, remain
  consumed after failure, and prevent copying a stage into a new run. Keys stay
  out of container environment, stage, receipts and output.
- The seed envelope is fourteen calls, zero automatic retries/embedding/answer/
  verifier calls, 120 seconds per call, at least 30 seconds between calls,
  2,400 seconds hard process time, four CPUs and two GiB. Per-call token guards
  are 32,768 input and 4,096 output including thinking. The conservative maximum
  reservation is USD 0.2809856 within the USD 0.30 ceiling. Startup remains
  30 seconds; fresh/render/SQL limits are unchanged.
- Selection scoring distinguishes the exposed seed set, N12 source control and
  two restricted wrong-source controls. Empty controls are not a proof of
  corpus-wide absence. Backend association is separate from browser opening
  and actual display/release evidence; those fields stay false.

## Narrow finding sent to implementation owner

`run_private_seed_visual_trial_v1._validate_bound` initially checked only the
exact `GuardPins` type and a `Mapping` per case before reusing successful code
verification. It did not mirror the final private12 caller's cheap validation
of each SHA field and all map keys/values as plain strings, required paths and
map size. A late pin with an equal serialized map and a string-subclass field
could therefore postpone structural rejection until fresh dispatch. Normal
JSON/preparation constructors produce plain strings, and dispatch still rejects
such a pin; this is a startup refusal consistency gap, not an observed source
or credential escape.

Requested fix: copy those per-case cheap checks into the seed adapter and add a
late equal-map malformed-field regression. No frozen private12 edit is needed.

## Performance observation

The seed host currently rereads the pinned artifact/code bytes in
`preflight_directory` after checking them against its manifest. This remains
fail closed, but does not inherit the final private12 host's verified-byte reuse.
The larger fourteen-case stage needs an actual keyless startup measurement
under the unchanged thirty-second fence. Do not infer startup compliance from
test counts or raise the budget to avoid this measurement.

## Initial reviewed source hashes

Before the narrow correction, SHA-256:

- Preparation: `ee5f3bb1641dd95ee509b228e9471e8f17832ea4d4355bc6d4962934621e76a8`.
- Custody: `f33ab162b56f46c1a5dc62185089808762a1038f187bbc72b5e043a6272411de`.
- Host: `c59f62a78910c6b3210ae8253078fb3ad4f0b5dc7763311bff672afb1d4296b2`.
- Executor: `b0b43fd6cb7cba761049d7b08f3b49204588e41ccfb9496861c7b07dde36b9d9`.
- Entry: `df2ce6a66f523c1fd6bedb2e50e06dd640f8f8f023ea0f62c2e5b1060316b50c`.
- Guard: `2f7137ad4e17b2add701d9cd4f0acb837c3926677a0a28ba8b0ae3252d6d5e80`.
- Rehearsal: `7ff5709110123e939ebce6be85ab30fe6ae5653b770647e5e278dc3d8a9ded7a`.
- Focused tests: `28b7d0f4c74f99f885b4f35580fc2cb3e58d568d18ec6f35053e77fbb78cb441`.

No other code-level blocker was found in this scoped review. The finding and
actual startup measurement must be resolved before treating a final stage as
ready for a newly approved physical provider trial.

## Final correction review

The owner repaired the seed custody helper only. Every case now validates the
exact `GuardPins` type, mapping shape, required code set and maximum count,
all five SHA fields as plain strings, and every code key/value as plain strings
with a valid SHA value before consulting the invocation-local cache. Four
regressions cover a late equal-serialized-map string subclass in the request
SHA, guard SHA, map key or map value. The existing late list-of-pairs regression
remains. The narrow startup refusal gap is resolved.

The seed host now retains only artifact/code bytes that it just read through
bounded path checks and verified against the same manifest. It passes those
bytes and the exact runtime/extra-helper subset to unchanged pure preparation,
which repeats its artifact/code hashes and independent-review bindings. Current
and staged code, watchdog, image code closure, final scope/wire/binding and
output-path checks remain. A new regression prohibits the redundant preflight
reread and proves a changed artifact on the next invocation is rejected.
There is no global cache, skipped source grant or changed resource budget.

The owner reports **36 focused seed tests passed**; this reviewer re-read the
corrections and regressions without running tests again. No remaining scoped
code blocker was found. The root must regenerate the stage against these final
hashes and measure actual keyless startup within thirty seconds; old stage
hashes do not bind the corrected helper bytes. New physical provider authority,
actual private selection/display/browser observations and release gates remain
separate.

Final corrected SHA-256:

- Custody: `dd49d5364083066cccf14fc8779859ed7accf6af528a3f5e3b8f756a3b6f4ffa`.
- Host: `be3bd919d85dc08d398c1abbb7ccfb27f0900f37b60669bc5a7326aa74574c4e`.
- Tests: `cabc558efa6c795bff8c128398e649caad00043c2223ede9874d76b5e4076249`.
