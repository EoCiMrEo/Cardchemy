# Real-query retrieval and current Ask diagnostics

## Scope and authorization

- Continue the owner-approved Lane 6 investigation on the retained local
  installation. Preserve existing working-tree changes, root `.env`, data and
  volumes. Lane 6 remains 3/7 until its independent quality gates pass.
- The owner explicitly approved another one or two live Ask tests on
  2026-09-26. Execute one BLEU comparison first using the installed current
  `two_request_local_support_v1` policy, not an unqualified experimental model.
- Endpoint: `https://generativelanguage.googleapis.com`; models:
  `gemini-embedding-001` and `gemini-3.6-flash`. Per attempt: one physical query
  embedding, at most one physical answer, zero retries, 512 embedding input,
  12,000 answer input and 1,024 answer output tokens, 30 seconds per call and
  60 seconds total. Admission prices remain the previously reviewed conservative
  USD 0.15/1.50/9.00 per million embedding/input/output tokens; maximum USD 0.04.
  These are local guard rates, not a claim of current provider invoice prices.
- Private question and authorized published evidence stay in memory except
  for the disclosed provider requests. No raw content, IDs, vectors, prompts,
  model responses or exception details enter this log. No diagnostic set/chat
  or database mutation is allowed. Prior uncertain execution costs remain
  unknown; a failure may have no billing receipt.
- A separate six-question real-query embedding diagnostic is being prepared
  with no answer call. Query task must remain `QUESTION_ANSWERING`: source
  configuration and native adapter include that task in the active embedding
  identity. The initially suggested `RETRIEVAL_QUERY` task is incompatible and
  was rejected before any provider construction or call. This correction
  changes no runtime profile, index or plan requirement.

## Preflight

- Branch and HEAD remain `main` / `6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`.
  The large existing remediation diff and untracked artifacts were preserved.
- Current app inventory: all eight services healthy; retained answer image is
  the locally rebuilt Lane 6 image. Source/image identity will be checked before
  the paid call. The current local instruction-model candidate failed 0/6
  positives in all three configurations and remains unselected.
- Existing Ask comparison safety contracts: **27 passed**, provider-free.
  Actual live results and cleanup will be appended below.

## First newly authorized live Ask result

- Before execution, SHA-256 comparisons of seven affected source files in the
  running answer worker matched the current checkout. No old-code test is
  claimed. The temporary diagnostic used that same current image.
- One BLEU expansion run completed with **one embedding and one answer**,
  zero retries and provider finish `STOP`. Both exact baseline and bounded
  OR/section diagnostic retrieved five chunks containing the expected expansion.
  The baseline had vector ranks 1–5 and no lexical candidates; the OR/section
  comparison had lexical candidates as well. This is one question, not the
  six-query or paraphrase retrieval gate.
- The answer claim contained the expected expansion. The model selected a
  contained short quote that had the expansion but not its acronym subject.
  Local NLI scores were contradiction 0.056, entailment 0.675 and neutral
  0.270; local QA did not find an answer span. Full support rejected at
  `entailment_rejected`. This is a support/output-window failure after successful
  evidence retrieval, not a provider outage or proof of general retrieval failure.
- Observed aggregate usage: 1,126 input tokens, 114 output tokens; usage is
  partly estimated. Local admitted cost USD 0.01107135; usage-price estimate
  USD 0.00270285. No observed budget overrun; neither number is an invoice and
  previous-attempt cost remains unknown. No answer, claim, quote or identifier
  was persisted by the diagnostic. Container was removed automatically.
- Reserve the second authorized Ask attempt until a distinct test can resolve
  a remaining uncertainty. Do not repeat paid generation to compensate for the
  already demonstrated local support blocker.
- The owner also approved continued real-query investigation. The prepared
  six-question batch uses one native `gemini-embedding-001` physical
  `batchEmbedContents` request, active `QUESTION_ANSWERING` task, no retries,
  at most 512 estimated input tokens, 30-second call / 45-second total and
  USD 0.001 maximum at a conservative USD 0.20 per million input guard rate.
  Send only six authored general technical questions; no lecture text, chat
  history or answer request. This is synchronous multi-content embedding, not
  a discounted asynchronous batch job. No index/vector/database mutation.
  Offline harness review remains mandatory before execution.

## Real-query harness review and zero-call preflight

- Added `scripts/evaluate_private_query_retrieval.py` and keyless contract
  tests. One native embedding batch is shared by all five predeclared local
  retrieval policies from the earlier ablation. Admission pins the six authored
  strings, model/task/space/dimension and native endpoint. No runtime adapter,
  installed model, schema, index or user-managed configuration was changed.
- Independent review caught two draft defects: client/database disposal could
  mask already-observed requests, and separate source/job read snapshots could
  bind a different authorized scope. Bounded nonmasking disposal now preserves
  attempt provenance. Exact current-source reads bind every selected chunk to
  the newly authorized Subject/document scope and citation/content fields,
  before spending and again after retrieval.
- A draft native-wire test initially assumed content had only `parts`; the
  installed SDK also emits `role: user`. Corrected the assertion to require
  exactly those two keys, one original authored text part, query task and
  dimension. No live request was involved in this failed test.
- Combined Ask comparison, retrieval-ablation and new batch contracts:
  **74 passed**, provider-free. Native mock tests count physical requests
  including retryable errors and redirects, and cover source rebinding and
  cleanup failure/timeout provenance. Normal CI remains keyless.
- Actual current-image zero-call preflight returned `preflight_ready`: six
  questions, **103 estimated input tokens**, task `QUESTION_ANSWERING`, zero
  provider requests, zero database writes and no answer call. Temporary
  container removed automatically. Live execution awaits final independent
  review; no paid retrieval result is claimed here yet.

## Final review and explicit batch-approval boundary

- Independent reviewer confirmed both draft defects fixed and found no
  remaining blocking issue in the final one-batch harness. Final root run of
  the three targeted files: **75 passed**, provider-free (supersedes the earlier
  intermediate 74-test run for final-file coverage).
- Automatic approval review rejected the attempted six-question batch command
  **before process creation**. Its reason: the owner's general continuation and
  one-or-two live Ask approval did not explicitly authorize this separate
  six-question payload/egress. No batch request was sent. The earlier paragraph
  records the proposed batch envelope, not a successfully accepted authorization
  or execution. No workaround or indirect execution was attempted.
- Explained the rejection to the owner and requested a dedicated approval for
  the exact official `batchEmbedContents` endpoint, six authored question types,
  unchanged task, token/time/cost cap, zero retries and no lecture/history/answer
  payload. Batch execution remains pending that response. The completed BLEU
  one-plus-one result remains valid and separately authorized.

## Support-design recommendation — proposed, not approved or implemented

- Two independent source reviews found no demonstrated routine bug that
  resolves all six reviewed positive refusals. Four fail entailment, one QA
  relevance and one contradiction in the authored baseline. Exact source binding
  and wrap normalization have already been corrected/tested. Learned conflict
  checks still confuse different properties; QA absence does not prove
  proposition independence.
- Do not choose another model or raise runtime resources from these results.
  The instruction experiment's 0.80 cutoff is full-vocabulary single-token
  confidence across 151,936 tokens, not calibrated NLI class confidence.
  Nonlabel/low-confidence uncertainty and unavailable inference were grouped;
  0/6 therefore does not isolate relation-recognition capability.
- Recommended next experiment, requiring a new approved plan extension: one
  measurement/calibration audit of the same pinned instruction candidate and
  joint classifier. Freeze artifacts, chat/label contract, complete-source
  requirement and resource limits; no new model, provider call, replacement
  answer or private-case tuning. Add aggregate-only nonlabel/label-mass,
  confidence-bin, input-budget and timeout diagnostics before inference.
- Independently author/review 96 public cases: 24 supported + 24 unsupported
  for calibration, and another 24 + 24 held out by source/template family.
  Cover definitions, comparisons, headings/bullets, conditions, quantities,
  fictional facts and input-length bands. Negatives include same-proposition
  conflicts, unrelated questions, ambiguous references, negation, altered
  numbers, mixed claims and injection. Keep each complete source within the
  predeclared envelope; never crop a conflict to fit.
- Preregister one deterministic calibration procedure before seeing scores;
  retain a valid global-vocabulary label winner and competition from nonlabel
  tokens. Do not normalize only A/B/C and conceal off-format uncertainty.
  Freeze at most one selected rule before opening heldout results. Stop on any
  heldout false acceptance, incomplete evidence, unavailable inference, resource
  failure or inability to pass all 24 heldout positives. Keep the 1 GiB artifact,
  2 GiB additional peak RSS, 20-second startup, 5-second p95 and bounded
  600-second public-run ceilings.
- Only a public pass could justify a separately bounded replay of the six
  reviewed pairs, eleven maintained cases and existing adversarial controls;
  no adjustment after private results. A fresh independently reviewed course
  holdout and real-query retrieval remain mandatory for release. This is a
  diagnostic proposal, not a promised fix or approval to replace the runtime.
- A symbolic exact-acronym relation policy is narrow and would require an
  explicit ADR-019 amendment to replace mandatory NLI/QA; extending special
  regex cases around the six known examples would not solve general lectures.
  Keep the approved Related published Knowledge fallback while support
  selection is unresolved. No new plan checkbox or runtime policy was changed.

## Dedicated approval and one batch execution

- The owner subsequently approved the exact separate six-query envelope in
  the presented question. Reissued that same command after approval; this is
  an authorized execution, not a workaround for the earlier rejection.
- One batch attempt ended `diagnostic_unavailable`, **one physical embedding
  request**, zero retries, no answer call, no database mutation or policy change.
  The prior broad safe catch did not retain its failure stage, so the precise
  cause is unrecoverable from captured aggregate output. It must not be labelled
  a provider outage, malformed vector or local SQL error without evidence.
  No recall/rank result is claimed. Cost is unknown and no automatic repeat
  occurred. The temporary container was removed automatically.
- A follow-up offline-only repair adds whitelisted failure stages/reasons and
  exercises local metrics on current authorized stored-source oracle vectors.
  Oracle vectors cannot substitute for real query vectors or qualify retrieval.
  Any repeated paid batch will need a fresh explicit envelope approval.

## Approved calibration scope

- The owner explicitly approved the proposed 96-case local audit/calibration
  extension. Added that bounded paragraph to Lane 6; no checkbox, runtime
  threshold, model, dependency, database, index or `.env` changed.
- Public fixtures will be authored and independently reviewed before model
  inference. Preregistered calibration and heldout separation, complete-source
  bounds, fixed global label mapping and resource stops apply. No private
  case can influence the selected rule; calibration failure keeps heldout closed.

## Offline retrieval repair and oracle result

- Source-oracle execution with no provider initially failed at `retrieval`.
  One agent and root each ran a zero-call oracle before exchanging results;
  this duplicate observation spent no provider quota and mutated no data.
- Identified a concrete harness bug offline: `load_context` stored a SQLAlchemy
  User that `rollback` expired, then used it after the session closed. Replaced
  it with immutable principal fields before rollback. Current authorization
  continues to query the real principal/Subject inside existing SQL; a snapshot
  is not authorization. A real SQLite rollback/closed-ORM regression proves
  the difference. It does not recover or prove the earlier paid batch's cause.
- Added fixed safe context/embedding/retrieval/scope-recheck stages, whitelisted
  provider/refusal codes, and separate validated-embedding flag. No raw exception
  or content is emitted. Validated estimated usage/cost survives a later local
  failure; actual billing can still be unknown. Query safety contracts now
  **53 passed**; combined query/ablation/Ask/classifier contracts **104 passed**.
- Repaired current-app source oracle completed: all five policies exercised
  30 authorized read-only queries, zero provider requests/writes. Baseline and
  OR/section variants had confirmed-page recall@5/MRR 1.0/1.0; bounded AND
  1.0/0.8889; bounded OR 0.8333/0.7. All reported zero overlap and scope
  violations; p95 ranged 16.435–58.856 ms. These use stored document vectors,
  not question vectors: all retrieval-threshold/release flags remain false.
- Requested fresh explicit approval before repeating the single paid batch
  on the repaired harness. No paid repeat has occurred at this point.

## Explicitly approved repeat — completed real-query result

- The owner approved exactly one additional identical six-question batch after
  the harness repair. It completed with **one** physical embedding request,
  zero retries, no answer call, no Knowledge/history sent, no database write
  or persisted vector. Embedding response validated. Local token estimate 103;
  conservative price estimate **USD 0.0000206**, not a provider billing receipt.
  The earlier unknown attempt is not assigned that cost retroactively.
- All five local policies reused the six actual query vectors and completed
  30 current-authorized read-only retrievals. Baseline ranks for the six
  reviewed page/source targets: **2, 3, 1, 1, 3, 1**. Page and machine-selected
  chunk recall@5 both 1.0; MRR 0.6944. This is actual query-vector evidence on
  the six authored direct questions, not paraphrase/followup/holdout proof.

| Policy | Page recall@5 | Page MRR | p95 ms |
| --- | ---: | ---: | ---: |
| Exact baseline | 1.0 | 0.6944 | 83.135 |
| Bounded AND | 1.0 | 0.5833 | 16.062 |
| Bounded OR | 0.8333 | 0.4778 | 75.737 |
| Bounded OR + section | 1.0 | 0.6111 | 39.683 |
| Bounded OR + section + diversity | 1.0 | 0.6111 | 42.119 |

- All variants reported zero overlap and scope violations in this authorized
  sample. Those counts do not replace cross-Subject/unpublished negative tests.
  None passes the preregistered MRR >=0.8/nonregression gate, and all lexical
  variants rank worse than baseline. **Do not select them or reindex** from
  these results. Runtime exact policy and active embedding space stay unchanged.
- The six target pages being in top five separates this sample's known support
  refusal from a general missing-evidence claim. It does not prove every course
  question is retrieved or that all source representation/citation issues are
  fixed. The remaining reviewed corpus, support-quality and release gates stay
  open. No second answer test was spent on this duplicate support uncertainty.
