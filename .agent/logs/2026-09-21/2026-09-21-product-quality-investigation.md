# Product quality investigation and phased plan

Date: 2026-09-21

## Scope and starting context

The operator requested a thorough diagnosis and a concise phased checkbox plan
for Ask AI inconsistency/request count/failures, Study metrics and option order,
Gemini's newer embedding model, and repeated Knowledge capture. This turn
investigated and planned; it did not change runtime code, configuration,
database data or deployment. Starting branch was `main` at
`6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`; `git status --short`, diff
stat and untracked-file listing were empty. Existing data and the root `.env`
were preserved. Three bounded, read-only agents independently traced Ask AI,
Study and Knowledge/embedding paths.

Root guidance, canonical orientation/project and module maps, relevant system,
Knowledge and Study flows, accepted ADRs, current state, roadmap, evaluation,
observability and configuration guides, and the 2026-09-19 through 2026-09-21
RAG closure logs were read. Current source, tests and official Google model
documentation were used to verify historical claims.

## Read-only evidence

- Compose listed the API, database, frontend, generation, indexing, answer and
  email workers as running/healthy. The initial sandboxed Docker query lacked
  daemon access; the approved read-only status/diagnostic calls succeeded.
- Documented content-free `operations-status` reported 12 retained answer jobs:
  5 completed (3 answers, 2 abstentions), 7 failed. The 3.5 model group had
  11 provider retries across its jobs; the 3.8 group had four fast nonretryable
  failures. A bounded metadata-only database query showed every failed job had
  completed retrieval and reached its first text stage. The generic persisted
  error code cannot distinguish provider rejection, invalid output, timeout or
  internal failure.
- Matching only the operator-supplied repeated question inside the database,
  without returning question/answer text, found two completed jobs. The first
  abstained after one semantic-support rejection and three provider requests.
  The later job answered with one source after five requests, including two
  retries. This establishes the observed inconsistency at the support verdict;
  model nondeterminism or changed bounded conversation history remain possible
  contributors. It was not an empty-retrieval case.
- A content-free count of 35 approved cards found correct option positions
  A=27, B=6, C=2, D=0. Source inspection found no option shuffle between model
  output, persistence and Study rendering. Existing targeted offline Study tests
  passed: 9 tests across progress, session and idempotency modules.
- A same-Subject/same-SHA aggregate found one two-document pair with two
  completed index jobs, two physical embedding requests and 6,734 reported
  input tokens. Only one current record matches the screenshot filename; the
  operator confirmed they changed the records after the screenshots. This
  aggregate is therefore not attributed to that specific historical pair.
- Official Google documentation names the newer model `gemini-embedding-2`.
  It is incompatible with the stored `001` space and uses different input/task
  rules. Official thinking support excludes `minimal` for Gemini 3.7/3.8,
  while current settings send `minimal` to Gemini 3 models. The historical
  3.8 provider response was not retained, so its exact error is unproven.

No stored prompt, document/card content, private response, credential or real
`.env` value was returned by the diagnostics, and this investigation made no
provider call. The live
diagnostics are a point-in-time local installation observation; they do not
establish billed usage or any other installation's state.

## Operator decisions and open choice

The operator chose Progress as the number of distinct cards answered correctly
at least once, retaining credit after a later wrong review. They chose a strict
maximum of one physical AI-provider request per Ask AI question, counting all
stages and retries. The current workflow makes three sequential calls on a
normal supported answer, so satisfying this changes retrieval and independent
support validation, not just retry settings. The operator was asked whether a
repeat same-Subject PDF should reuse Knowledge automatically or show a warning
and choice; the answer was pending when this record was written.

## Plan, verification and limits

The active [phased plan](../../../docs/development/PRODUCT-QUALITY-REMEDIATION-PLAN.md)
sequences safe diagnostics/model preflight, measured one-call Ask AI design,
server-derived Study metric and stable option shuffle, separate embedding-2
space and staged cutover, race-safe duplicate handling, then integration and
rollout gates. The [roadmap](../../../ROADMAP.md) links it. No production data
cleanup, migration, root `.env` edit, service restart or paid evaluation was
performed. No runtime test pass is claimed for this documentation-only change.
`python scripts/check_context.py` passed (37 required files, 68 active guides,
979 local links), and `git diff --check` passed. The Study agent's nine targeted
offline tests are subsystem evidence, not a full release gate.

## Follow-up operator decisions and plan revision

The operator subsequently chose a same-Subject duplicate warning with a user
choice. They asked for operator-selectable multiple models for both Flashcard
generation and Ask AI, with model-aware provider wire schemas; they selected a
catalog of verified models rather than arbitrary new IDs. They also chose to
retain `gemini-embedding-001` as the default while adding
`gemini-embedding-2`, and asked for better measured retrieval under the current
default. The plan now records these decisions and the necessary capability,
schema, snapshot, transition and retrieval tests. The reported repeated question
had already reached evidence, so its first abstention remains a support-stage
finding, not evidence that the embedding model alone failed.

Current source showed one broad Gemini 3 thinking switch and a shared minimal
JSON-schema wire form for text roles; Google model metadata does not expose all
schema/thinking compatibility details. Official capability documentation and
the pinned adapter therefore require a versioned verified catalog and offline
model-by-model payload tests. The one-request Ask AI cap still excludes a remote
query embedding plus remote answer in the same operation; supporting two
embedding profiles does not by itself resolve that constraint. No runtime,
database or `.env` change or provider call was made in this follow-up.

The revised plan has 2 checked decision/investigation items and 24 unchecked
implementation/verification items. The follow-up `python scripts/check_context.py`
passed (37 required files, 68 active guides, 981 local links), and
`git diff --check` passed. These are documentation checks, not runtime gates.

## Follow-up request-budget correction

The operator explicitly superseded the earlier one-total-request decision:
one remote query embedding request plus one remote answer generation request
per Ask attempt is acceptable and approved. The target is now two physical
provider attempts, with no separate remote support pass or automatic retries
within that attempt. An explicit user retry is a separately authorized attempt
and must show potential additional cost. The current Gemini query embedding and
matching document vectors can therefore remain in the retrieval path.

The reported repeated question is still not evidence of an embedding miss:
the first recorded attempt had completed retrieval and was rejected by the
support pass; the later attempt answered after transient retries. A safer
two-request design must measure retrieval quality for other cases and replace
the remote support call with an independently local semantic check, preserving
entailment, relevance, contradiction, source and authorization gates. Exact
quote containment or an answer model's own assertion alone does not establish
these properties. The plan was corrected accordingly; no runtime/data/.env
change or paid provider call was made.

The follow-up retrieval audit identified a concrete, unproven quality
hypothesis: current RAG chunking retains trusted headings as `section` metadata
but embeds and full-text-searches only chunk content. Full-question PostgreSQL
`plainto_tsquery('simple', ...)` can also require every retained query term,
while overlap removal does not suppress equivalent chunks across different
documents. The plan now measures title/section search representation, lexical
query variants, chunking and duplicate-document diversity as separate
ablations against the unchanged 001 baseline. Any changed embedding input gets
a new format identity and staged reindex. These are possible improvements for
other misses, not an asserted cause of the recorded support rejection.

The corrected plan has 2 checked items and 25 unchecked items. Its final
documentation checks passed: `python scripts/check_context.py` validated 37
required files, 68 active guides and 981 local links; `git diff --check`
reported no whitespace errors. No runtime gate or paid evaluation ran in this
follow-up.
