# Published sparse whole-PDF control and exact smaller-count choice

## Scope and authorization

The root task authorized a no-paid completion of the earlier one-page sparse
control: independently review its entire original PDF and authored card, then
exercise actual capture, deterministic offline indexing, review/publication,
shortfall staging and exact smaller-count confirmation on guarded disposable
PostgreSQL. The user has only long lectures and previously accepted an offline
one-page control. This record is **synthetic published sparse control evidence**,
not a sparse private lecture, current Gemini generation yield or live-provider
quality measurement.

Existing working-tree edits, the retained application database/volumes,
operator root `.env`, original lectures, core runtime and migrations were
preserved. No operator key or retained database was read. Existing full offline,
PostgreSQL and image proofs were not replaced or repeated by this focused check.
Reading covered root guidance, relevant project/module maps, the generation and
Knowledge contracts, testing authority, earlier sparse control and independent
twenty-card teaching-review evidence. The PDF skill was used for complete
original-page rendering and inspection.

## Independent whole-source review

The existing `impossible_sparse` fixture in
`backend/tests/fixtures/ai_eval/quality_v2.json` was converted using the existing
`tests.test_pdf_processor.pdf_bytes` helper. This is an authored one-page PDF
containing one explicit learning fact and no other page, diagram or omitted
source context. The complete original was rendered with Poppler, visually
inspected, reopened and checked against its extracted text. The sole authored
card was reviewed separately from the generation pipeline: one explicit
question/answer relation, one unambiguous supported answer, four unique parallel
biological-pigment options, compact wording and exact page-one evidence. The
one-card teaching/source review passed 1/1. This independent agent review does
not stand in for an instructor's product approval or a population quality rate.

Frozen reviewed bytes:

- Original PDF SHA-256:
  `fa7bc9f4b9163c36a6e1a5d3afdafdc08fad52329157a07f92ea0b76716aed46`.
- Authored card JSON SHA-256, explicit Windows CRLF serialization:
  `d7adf2da38f1b7eb3f407e86be08d4390c8b2b7654eea4d60fce4f0ebe934248`.
- Complete-page PNG SHA-256:
  `e9fe6ab0dbb20f65022ac8d8671517a13a364b0d9ebef4cdf6c18b8686db6bfb`.

Review artifacts remain in the ignored owned directory
`.agent/.verification/sparse-whole-source-review-20261003-79e8c56d`.
The integration test asserts both reviewed source/card pins before transactions.
The deliberately scripted provider supplies only that reviewed fact; this does
not establish the maximum number of all imaginable cards from a real document.

## Meaningful integration added

- `backend/tests/postgres/test_postgres_sparse_generation_control.py`: one test
  exercising actual services and workers, with injected deterministic providers.
- `scripts/test_sparse_generation_control.py`: a thin focused wrapper around the
  unchanged canonical `scripts/test_services.py postgres` authority. It only
  selects this one test and forwards a closed numeric aggregate. The canonical
  runner continues to own verified database image selection, a unique loopback
  container, generated credentials, Alembic checks and verified cleanup.

There are no core or shared-fixture modifications. No source/capture/index/set
transaction is mocked. The generation graph/pipeline are real; only provider
implementations are intentionally scripted. Embedding-provider resolution and
HTTP provider requests are guarded against accidental execution.

The test executes two real jobs:

1. Reserve and upload the complete original for Knowledge only; the generation
   worker performs isolated PDF extraction and durable canonical capture with
   encrypted original storage. The index worker embeds the captured chunk with
   one injected local call. Before publication, retrieval is refused. The real
   review/publication service marks the ready revision reviewed and published
   and cuts over its compatible space. Authorized pgvector retrieval finds the
   exact page-one evidence; a foreign owner cannot authorize that Subject. The
   encrypted original authenticates and round-trips to the reviewed PDF bytes.
2. Reserve an explicit same-document generation job for **20** cards and upload
   the exact original again. The current reviewed revision is unchanged and
   reused without additional indexing. The actual graph/pipeline underproduces
   and bounded refill ends in `insufficient_grounded_cards`. The worker retains
   exactly one encrypted validated candidate, preserves the original target 20
   and creates **zero** sets before the explicit choice. Foreign-owner choice
   is rejected with 404 and choosing two when only one is available with 422.
   Selecting exactly one commits one draft set and one unapproved grounded
   card atomically. A repeated identical choice returns the completed job
   without another set or provider call. Candidate stage and temporary upload
   source are removed; the independent reviewed/published Knowledge and
   encrypted original remain intact.

## Verification and observed aggregate

Command, through normal approval:

```powershell
backend\venv\Scripts\python.exe scripts/test_sparse_generation_control.py
```

Final focused run: **1 passed in 9.24 seconds**, exit 0. Disposable Alembic
upgrade/current-head/drift checks and empty-schema downgrade to base/re-upgrade
passed. The canonical runner verified removal of its owned container and
generated credential file. All numeric result fields were validated before
being printed; no credentials, source text or provider response was emitted.

| Measurement | Observed |
| --- | ---: |
| Complete authored source pages / facts | 1 / 1 |
| Reviewed and published revisions | 1 |
| Original requested cards | 20 |
| Encrypted pending validated cards | 1 |
| Sets before / after explicit choice | 0 / 1 |
| Exact chosen / persisted cards | 1 / 1 |
| Injected local generation / indexing calls | 6 / 1 |
| Additional provider calls on choice or identical replay | 0 |
| Physical remote provider requests / actual new cost USD | 0 / 0 |
| Foreign-owner / excessive-count denials | 1 / 1 |
| Temporary source / candidate stage after choice | 0 / 0 |
| Published original preserved | 1 |

The six generation calls count the scripted provider's local method invocations,
not billed requests. Local usage estimation and stored provider telemetry do not
change the observed zero network calls or zero actual new AI cost.

Machine aggregate:
`.agent/.verification/sparse-published-control-2db19637b72443cc9512f6c3993eb599/aggregate.json`.
The directory is ignored and contains numeric fixture data only.
Aggregate SHA-256:
`fc245f5d352c388fdb4464f3d29d9752518867379f49c8097b0eac80ca11cbff`.
Executed test SHA-256:
`36d47ca671d80877e1d177b4dbb1fdc28ce7d515e514907a2871881943d145a2`.
Focused wrapper SHA-256:
`8e74e1e9760f515bc64a54d3b3c70662e614a1a85fbb48ec2292e43197a5607a`.

`py_compile` for both added files and scoped `git diff --check` passed.
No new broad scan, full offline suite, all-PostgreSQL rerun, hosted CI or paid
provider evaluation was performed by this subtask.

## Failed attempts retained

The initial sandboxed invocation stopped at the service guard before testing;
the normal escalation was used rather than bypassing it. The first disposable
test run stopped before domain transactions because the reviewed card artifact
used CRLF bytes while its test comparison serialized LF. The test now uses
explicit CRLF and the originally reviewed SHA remains unchanged. The next run
completed capture/index/publication and reached exact-choice commit but its
assertion incorrectly expected the response-only `result_set_id` field on a
`GenerationJob` ORM object. The assertion was corrected to the model status;
the final persisted set/card counts already verify the actual result. Both
failed disposable runs passed migration guards and cleaned their owned service
and credential file. Neither failure required a runtime/data/policy change.

## Boundaries for Lane 6 closure

This fills the approved published sparse **control** transaction bridge without
new live calls. The separate independently reviewed historical twenty-card
lecture result remains evidence for a feasible long-source sample, with its
recorded historical-policy and billing limits. Neither result is relabeled as
a current-policy live success rate. Matching private Ask displayed-source
quality, original-page browser checks and actual spoken assistive-technology
release evidence remain separate root-owned gates. This subtask does not enable
Ask, alter any threshold or mark the Lane complete.
