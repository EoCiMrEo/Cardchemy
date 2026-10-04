# Product quality Lane 6 implementation and verification

Date: 2026-09-25. Scope: the seven Lane 6 checklist items in
[the remediation plan](../../../docs/development/PRODUCT-QUALITY-REMEDIATION-PLAN.md).
This is a working evidence record; final gate status is recorded below only
after each required check completes. Earlier investigation and plan-update logs
remain unchanged.

## Starting context and decisions

- Read root `AGENTS.md`, orientation, project/module maps, accepted RAG/generation
  ADRs, current state, relevant architecture and `.agent/logs/` before edits.
  Inspected branch, HEAD and the dirty working tree; preserved pre-existing
  Lane 0–5 work, root `.env`, local database volume and user data.
- The owner approved Lane 6 implementation. Original requested card count stays
  exact; an insufficient bounded run may retain only fully validated candidates
  and offer an explicit exact smaller count without another model call. A new
  attempt toward the original target needs a distinct extra-cost confirmation.
- [ADR-020](../../../docs/decisions/ADR-020-validated-card-choice.md) records
  encrypted staging, expiry, fencing, atomic choice and Knowledge ownership.
  Existing Ask policy retains one query embedding and one answer request per
  attempt with zero automatic provider retries. No new embedding space or remote
  support/reranker is introduced.

## Work performed

- Backend work includes safe Ask/provider/retrieval/local-support stage
  diagnostics and migration `20260925_0018`; adaptive generation, validated
  candidate staging/choice and migration `20260925_0019`. Source changes and
  their tests remain the authority for exact behavior.
- Frontend typed contracts and API service now show distinct Ask abstention vs
  provider failure explanations, per-attempt generation counts versus
  cumulative rejected count, reloadable smaller-target confirmation, and a
  separate cost-aware manual Retry. The choice request uses a stable operation
  key and exact count. Retrying from a pending card choice sends explicit
  `acknowledge_additional_cost: true` to the API.
- Added root template/configuration entries for finite encrypted-candidate
  retention and per-job/user/deployment byte caps. Updated the generation flow
  and ADR links. Further evaluation, operations and context updates follow
  completed backend measurements.

## Verification so far

- Frontend `npm run check`: typechecks, lint, 4 unit tests, 36 component tests,
  production build and Chromium suite passed; 67 browser tests passed, one
  separately opted-in live reset test skipped. The new card-choice/retry browser
  tests passed after reload/mobile/idempotency and cost-confirmation coverage.
  Two initially observed test races were repaired with awaited request counts;
  full check passed afterward. A second full check after the pending-choice
  presentation adjustment also passed with the same counts.
- Ask backend scoped offline checks: 159 passed, 3 skipped; privacy/observability
  targeted checks: 35 passed (agent report; final integration still pending).
- Generation backend focused offline suite: 47 passed after selector and
  staging edits (agent report; full integration below).
- The first disposable PostgreSQL retrieval harness had 86 passed, 3 skipped,
  5 failed, 880 deselected; later cross-area fixture repairs resolved those
  failures. Its new bounded OR ablation improved a synthetic
  9-case sample from 0.8889 to 1.0 recall@5/MRR with zero duplicate overlap,
  but that toy result is insufficient to change the shipped policy. New
  migrations 0018/0019 upgraded, downgraded and re-upgraded on disposable
  PostgreSQL without drift.
- Docker Desktop access was confirmed with approved escalation. The local
  installation's volume was preserved through backup, migration and service
  recreation. Paid diagnostics are recorded below.
- Read-only real Knowledge probing isolated a lexical candidate failure for a
  reproduced abstention: full-question and bounded-AND FTS returned zero,
  while bounded-OR FTS returned five eligible published chunks with relevant
  concept flags. Historical hybrid top-five adequacy cannot be reconstructed:
  retained jobs contain neither their query vectors nor rejected-answer source
  selections. A local authored-claim probe against two contiguous source quotes
  returned one entailment rejection and one contradiction rejection. These are
  diagnostic observations, not a reviewed false-rejection label. The previously
  failed 20-card source has 42 current published pages and 39 indexed chunks;
  distinct supported-fact capacity is still unknown. No private text or IDs
  were exported.
- The owner subsequently checked narrowed original-PDF pages and confirmed
  five distinct concept topics: BLEU, Bag-of-Words/TF-IDF, Logistic Regression,
  topic modeling and cosine similarity. The BLEU topic includes two separately
  confirmed question forms. These are owner labels about the visible PDF, not
  automatic proof that the current canonical text and selected chunks preserve
  every supporting statement. A read-only published-page scan found local
  keyword proxies for the first four topics. The initial cosine keyword probe
  selected page 23, a topic recap without the requested angle/magnitude fact;
  its neutral 0.985/no-QA result was an expected non-answer, not a diagnosed
  extraction failure. See the correction below.
- A content-free inventory of the 17 retained current-policy Ask jobs found
  12 completed abstentions, all with support rejection, and 5 answer-stage
  failures; no persisted supported answers. The counts span the pinned 3.5 and
  3.6 Flash answer profiles and cannot reconstruct the prior raw claims or
  selected evidence. They quantify the owner's observed failure pattern on
  this small local installation, not global model reliability.
- Correction to the cosine page hypothesis: a read-only SHA-256 match found the
  exact original PDF in the owner's lecture directory without printing its name
  or hash. Visual inspection showed page 23 is only a recap, while page 13
  explicitly states the angle-versus-magnitude distinction alongside a formula.
  The page 23 native pypdf text exactly matched its 518-character canonical
  database page; independent pdfplumber extraction was similar. The current
  canonical page 13 contains the actual answer-bearing sentence. A local-only
  authored claim with a contiguous page-13 quote passed the pinned support
  gate: 0.993 entailment, 0.001 contradiction, 0.006 neutral and a QA span.
  The earlier neutral probe establishes only that a topic mention is not
  enough to answer. It does not support an OCR or recapture recommendation.
- A later read-only canonical BLEU page-22 probe used authored claims and
  source-contiguous quote windows. The correct acronym claim's shortest quote
  scored 0.992 NLI entailment and had a QA span, but the whole-chunk
  contradiction scan rejected it; five of six sentence units exceeded the
  0.50 contradiction threshold, including non-BLEU units with no acronym QA
  answer span. A short correct evaluation-focus quote scored 0.942 entailment
  with a QA span, yet the scan rejected it. Longer focus windows sometimes
  passed entailment but lost the QA span. Wrong expansion and wrong focus
  controls were rejected by NLI. This establishes false local rejection on
  these reviewed authored positives, not on the unrecoverable third-live-run
  model claim. The probe made zero provider calls, wrote no data, and emitted
  no private source text or identifiers. A one-off probe script had an
  event-loop disposal warning after output; the later narrowed probe closed
  its database engine inside the same event loop and exited cleanly.
- A separate read-only audit matched all three published Subject Knowledge
  documents to the owner's original local lecture PDFs by exact digest and
  visually inspected five answer-bearing pages. The original extraction and
  canonical stored page text matched exactly on each; every nonempty canonical
  line survived in the eligible embedded chunk body or section. The five
  confirmed topics are therefore present in the current published/indexed
  corpus. The cosine concept name is in the chunk section field while its
  answer sentence is in the body, a representation nuance for body-only FTS.
  This audit did not reconstruct an old Ask retrieval result, make a provider
  request, change database content or retain private page text. Temporary
  renders were removed.
- A provider-free six-case/five-topic private support comparison selected
  current eligible published chunks in the active space and exact, bounded
  source-contiguous line windows. Its authored positives were rejected 0/6
  accepted by both shipped v1 and an unshipped structural v2 candidate; all
  six wrong-claim controls were rejected. The v2 candidate clears only an
  explicit different-heading topic and cannot clear same-heading BLEU
  ancillary facts. Entailment and QA also reject some other authored positives;
  the cosine selected quote lacks the concept name stored in its section.
  These auto-selected quote/claim pairs were not individually owner reviewed,
  and no model answer was replayed, so the figures are a local diagnostic,
  not product accuracy. The transient read-only container was removed; no
  provider calls, data writes or private content output occurred. Five keyless
  harness tests and 23 synthetic verifier tests passed; three opt-in real-model
  tests were skipped in the host suite. V2 was not activated and the remaining
  owner-approved live Ask call was reserved for an actually improved policy.
- The frontend Ask panel now distinguishes a classified temporary AI service
  failure from a completed, unverified evidence abstention using stable public
  job/message codes. The message remains phase neutral because the public API
  does not expose embedding-versus-answer failure. Manual Retry still requires
  separate cost confirmation. Three focused component cases passed; the full
  `npm run check` passed 4 unit, 39 component and 67 Chromium tests, with one
  deliberate live-reset skip. This UI improvement does not enable a new support
  policy or cure provider HTTP 503.
- After the unshipped support candidate and private harness additions, the
  complete backend offline suite passed 935 tests, skipped 113 gated cases
  and deselected two live cases. A targeted invocation from the repository
  root initially failed because `app` was not on Python's import path; the
  corrected documented backend-working-directory command passed 28 tests
  with three opt-in real-model skips. Context validation passed 37 required
  files, 75 active guides and 1,129 local links; `git diff --check` exited 0
  with only Windows line-ending conversion warnings. No live provider call
  followed these edits.
- A second provider-free read-only ablation used exact contiguous windows
  from immutable canonical pages. Cosine's heading-to-answer span improved
  local NLI entailment from 0.528 to 0.991 and produced a QA span; a
  non-contiguous section-plus-quote composite behaved similarly but is not
  citable under current guards. Its QA span still required claim-equivalence
  checking. BLEU acronym remained blocked by global contradiction; Bag-of-
  Words and Logistic Regression still had no QA span despite NLI entailment
  0.904/0.962; topic modeling's selected span was neutral 0.978, and no safe
  BLEU-focus heading span was selected. These authored auto-selected pairs
  are diagnostic only. No provider calls, writes, raw content output or
  persistent transient containers resulted.
- A source/index design audit found that the chunker strips headings from
  `content` into `section`, while both application and database citation
  guards require `source_quote` inside chunk content. A safe exact-page-span
  reindex would need a new chunker and embedding-space revision, a separately
  approved document-embedding cost envelope, and a review of current
  staging-only corpus-revision bumps that hide old citations. Do not perform
  that real-Subject reindex under the remaining Ask 1+1 approval. A public
  larger NLI candidate alone exceeds ADR-019's 200 MiB full-bundle ceiling;
  a sandboxed network HEAD failed, so no artifact was downloaded and no
  quality/RSS/load benchmark was claimed.
- The final keyless targeted rerun after the canonical-window harness cases
  passed 30 tests with three opt-in real-model skips. Context validation
  remained at 37 required files, 75 active guides and 1,129 links, and
  `git diff --check` exited 0. The earlier complete backend offline pass
  predates only these added harness tests; no product verifier policy changed
  afterward.
- An additional read-only QA fallback ablation required quote-to-claim NLI,
  an answer span extracted from the authored claim, and that span's normalized
  presence in the exact quote. It opened two of six authored positives and
  none of six wrong controls in this tiny probe. Independent review rejected
  using it as an acceptance gate: QA on model-authored claim is self-
  confirming, while token presence in source does not prove the questioned
  relation; an NLI false entailment could accept a swapped subject, negation
  or ambiguous word. Keep source-QA miss fail-closed. No runtime change,
  provider call, database write or private output resulted.
- Rebuilt only the local frontend image from the tested checkout and recreated
  only the frontend container. All eight long-running Compose services then
  reported healthy, and the frontend `/healthz` returned HTTP 200. API,
  answer/generation/index/email workers, root `.env`, the existing v1 Ask
  policy, database schema/data and volumes were untouched by this UI rollout.
  No Gemini call was made. The v2 prototype remains unshipped.
- After a fresh official Gemini price/model review and an aggregate empty-job
  preflight, the owner-approved fourth one-shot Ask comparison used the same
  conservative endpoint/model/call/token/time/USD 0.04 envelope. It selected
  five current authorized chunks under both policies, with the BLEU anchor in
  both; it made exactly one embedding and one answer request, zero retries.
  The answer provider returned HTTP 503 before a claim existed. The safe
  diagnostic reported `ai_provider_unavailable`/`http_server_error`, admitted
  estimate USD 0.01107135 and previous-attempt cost unknown. No raw claim,
  source text or identifiers were emitted. The newly added first-claim
  score/anchor probe therefore had no claim to inspect. This is provider
  availability evidence, not a retrieval or support outcome.
- Before installing the final audited backend/worker images locally, a
  read-only aggregate query found zero active generation and Ask jobs;
  configuration migration preflight passed. Rebuilt the backend and dedicated
  answer-worker images, then recreated only backend, generation, indexing,
  answer and email services without removing database or volumes. All eight
  long-running services reported healthy. The preserved database remained at
  Alembic `20260925_0019` head, and `alembic check` reported no model drift.
  A post-recreation settings check showed this owner's local root profile still
  enables the existing fail-closed Ask v1 policy. The earlier statement that
  Ask admission was disabled was inaccurate; the local setting was preserved.
  No Lane 6 retrieval or support-policy cutover was enabled. Read-only
  post-recreation aggregate counts matched the pre-upgrade verified backup:
  1 user, 1 Subject, 3 Knowledge documents, 107 pages, 4 generation jobs and
  17 Ask jobs.
- The complete backend offline suite passed 892 tests, skipped 110 gated cases
  and deselected 2 live cases. The final guarded disposable PostgreSQL suite
  after selector/retrieval security edits passed 93 tests, skipped 3, and proved
  0018/0019 upgrade, downgrade,
  re-upgrade, heads and drift; temporary containers and credentials were
  cleaned. A prior cross-area failure was traced to test-fixture Knowledge
  quota contamination and repaired without changing product quotas.
- A later complete offline rerun after the private Ask harness cleanup and
  diagnostic edits passed 903 tests, skipped 111 gated cases and deselected
  2 live cases. These counts are keyless and do not prove a provider outcome.
- After the candidate-choice audit fixes, the complete backend offline suite
  passed 921 tests, skipped 113 gated cases and deselected 2 live cases.
  Context validation checked 37 required files, 75 active guides and 1,127
  local links. CI-workflow and release-metadata validators passed; `git diff
  --check` passed with only Windows LF/CRLF conversion warnings.
- `npm run check` was repeated after the pending-choice visual adjustment and
  passed with 67 Chromium tests and one gated live reset skip. Context, CI
  workflow and release-metadata validators passed. The first journey invocation
  used a Python installation lacking Alembic; it made no product assertion and
  cleaned its disposable resources. The virtualenv rerun passed both RAG-off
  and RAG-on browser/API/database paths and cleaned disposable resources.
- The owner separately approved one private Ask diagnostic capped at two
  provider calls and USD 0.04 estimated admission, and one private 20-card
  generation diagnostic capped at 16 calls and USD 0.18 estimated admission.
  The reviewed models, prices, token/time limits and Google endpoint were
  presented with the approval. Both one-shot runs executed as recorded below.
- Before local schema upgrade, aggregate counts showed no active generation,
  Knowledge-index, Ask or email work and revision 0017. All application writers
  were stopped. A custom-format archive was saved under git-ignored `backups/`,
  its copy-back SHA-256 matched, and a separate restore rehearsal matched the
  source revision and aggregate counts (1 user, 1 Subject, 3 Knowledge documents,
  107 pages, 4 generation jobs, 17 Ask jobs). Only the rehearsal database was
  dropped. The original volume remains intact; the subsequent upgrade is
  recorded below.
- The guarded offline browser journey passed both RAG-disabled and RAG-enabled
  paths with deterministic providers and cleaned its disposable resources.
  Mailpit service contracts passed 3 tests with 1009 deselected and cleaned
  their disposable resources. Local images were rebuilt; the backed-up real
  database upgraded 0017→0018→0019, passed exact-head and no-drift checks,
  and all eight Compose services reported healthy after recreation. AI workers
  were then temporarily stopped for isolated live diagnostics.
- The one approved private Ask diagnostic made exactly one query embedding and
  one answer request. The shipped exact-vector top five and diagnostic bounded-
  OR top five each selected five eligible chunks; both contained the targeted
  concept. Exact-v1's selected chunks had vector ranks 1–5 and no lexical ranks;
  the OR variant added lexical ranks. The answer stage failed with the safe
  `ai_provider_unavailable` category before local support, leaving answer-call
  cost uncertain. The diagnostic process also exposed an event-loop cleanup
  traceback after its aggregate result. The harness cleanup was fixed and 14
  keyless tests passed; the first run's finer provider reason cannot be
  reconstructed. The owner later approved one additional Ask attempt under
  the same envelope. An initial Docker preflight was rejected by automatic
  approval review because that review service hit a usage limit; it executed
  nothing. Normal review later recovered. The aggregate preflight found no
  queued or running Ask jobs, and the answer worker was stopped temporarily.
  The second one-shot attempt answered from the shipped exact-v1 top five and
  again made exactly one embedding and one answer request. The exact-v1 and
  diagnostic bounded-OR top fives each contained the target concept; the answer
  failed before local support with `ai_provider_unavailable` and the finer
  `http_server_error` reason. Its admitted conservative estimate was USD
  0.01107135, not a bill; actual cost is unknown because no answer usage
  receipt was returned. No automatic retry or additional request occurred.
  The owner subsequently approved at most one further Ask attempt if needed;
  it was reserved pending a diagnostic hypothesis. The answer worker was
  restarted and all application services returned healthy.
- After a bounded wait, the owner approved and the operator executed that
  third one-shot Ask attempt under the same endpoint, model, price, token,
  call, time and cost envelope, after confirming no active Ask/generation job.
  It made exactly one embedding and one answer request, with zero retries.
  Current exact-v1 and diagnostic bounded-OR retrieval each returned five
  eligible chunks containing the target BLEU concept. This time the answer
  provider returned a `STOP` finish with one claim, 1,126 combined input tokens
  and 114 answer output tokens. The local verifier rejected the generated
  claim at `entailment_rejected`; the script intentionally did not retain the
  raw claim/quote, so correctness or a false rejection cannot be assigned.
  The conservative estimated usage cost was USD 0.00270285, not a billing
  receipt, and embedding usage was estimated, so prior-attempt cost remains
  unknown. The answer worker was restarted immediately afterward. This
  completed the owner's three approved Ask diagnostics; no fourth call is
  included in this evidence record.
- The separately approved private generation diagnostic read 42 published
  canonical pages, prepared 39 chunks and passed a no-provider preflight of
  6 requests, 37,140 estimated input/32,256 output tokens and USD 0.091782.
  Its one live run produced 20/20 locally validated distinct cards from 20
  pages in four physical requests and 42.349 seconds, with round accepted
  increments of 19, 0 and 1. One candidate failed answer-in-quote containment.
  Provider-reported usage gave a local USD 0.012827 estimate, not a billing
  receipt. The tool wrote no cards or set.
- All eight app services became healthy after the diagnostics; a stale Compose
  migration container initially blocked `docker compose start`, so it was
  recreated with the current image and exited 0. Workers were restarted via
  `up --no-deps --no-build`, and all services and the migrate gate showed
  healthy/success state. The real database remained at head 0019.

## Pending gates and limits

- Marked three of seven Lane 6 implementation items complete in the plan:
  content-free diagnostics, bounded adaptive generation and the validated
  exact smaller-target choice. The reviewed private Ask corpus, retrieval
  decision, support-policy improvement and overall release gate remain open.
- Review the private source/citation pairs and evaluate Ask provider failure
  subreason before selecting a retrieval or support-policy change. The current
  exact-v1 top five found concept-bearing evidence in all four live comparisons;
  none established a supported answer, so a retrieval cutover is not justified.
  Keep private questions/pages, document
  text, IDs, credentials and model responses out of this log and tracked files.
- Three Ask attempts failed at answer-provider execution; the fourth diagnostic
  identified exact HTTP 503, while the second only classified HTTP 5xx. The
  remaining attempt completed provider generation but failed local entailment.
  None established a supported answer. One further owner-approved live Ask
  comparison remains available if a specific hypothesis and reviewed envelope
  justify it. Do not silently retry or infer billed cost from admission or
  estimated usage.
- Complete remaining context, manual accessibility and release evidence, then
  mark each Lane 6 checkbox only if its gate is actually satisfied.

## Offline NLI-base option, rejected for this release

- A bounded public-artifact probe fetched the pinned quantized
  `cross-encoder/nli-deberta-v3-base` ONNX model. The 244,422,412-byte file
  matched its published SHA-256; download/checksum took 248.4 seconds. The
  full verifier bundle with the retained QA/tokenizer files was projected at
  338,778,897 bytes (323.08 MiB), above ADR-019's 200 MiB cap.
- On six public synthetic NLI pairs, the larger model scored unrelated ROUGE
  content as BLEU entailment 0.958 and a same-BLEU wrong acronym as only 0.449
  contradiction, below the existing 0.50 conflict gate. Its load time was
  4.45 seconds and process RSS increased about 365.3 MiB. These are component
  measurements, not observed full-verifier false acceptances; the quote and QA
  checks were not evaluated with this model.
- The probe did not use the private database or provider. It did not alter the
  active model, configuration, policy or app deployment. The exact ignored
  benchmark directory was removed after verifying it was inside the workspace;
  a subsequent `Test-Path` returned false. The larger model was not selected.
- A fresh local Compose read showed all eight long-running services healthy.
  An in-container import printed `local_nli_qa_v1` as the answer-worker support
  policy. Only the separately tested frontend failure/abstention copy is on
  the current local UI; no Ask verifier v2 is deployed. The remaining approved
  Ask provider attempt was preserved while the offline release gate fails.

## Independent Ask contract and window checks

- Three bounded read-only reviews examined answer shape, source windows and
  support policy. The current model must duplicate its joined answer and copy
  an exact quote/UUID; a proposed versioned contract would supply bounded
  start/end IDs for offset-preserving source units and derive the exact quote,
  chunk and joined answer server-side. Current database request-cap/check
  constraints name only the v1 policy, so a v2 cutover also needs a migration
  extending them. This remains unimplemented: it could reduce output-shape
  errors but would not resolve local-support false rejections.
- A provider-free read-only search tested 64 exact source-contiguous windows
  from currently eligible chunks across six authored case shapes. The shipped
  full verifier accepted one positive (logistic) and zero of 64 authored wrong
  controls. The original shortest windows accepted zero of six positives;
  full eligible chunks also accepted zero of six. The one passing window was
  270 characters. This did not replay all top-five conflict context and the
  exact quote/claim pairs still lacked individual owner review. It cannot
  justify a window-selection release or a best-passing-window search.
- An independent synthetic NLI probe showed that reciprocal scoring still
  misclassified an unrelated topic as a conflict. An extractive-claim mode
  could remove some paraphrase mismatch but retained BLEU conflict and
  source-question relevance failures. No general local-support v2 passed the
  offline gate; neither alternative was activated.
- The next gate needs individually reviewed five-topic direct/paraphrase and
  follow-up positives plus zero accepted adversarial wrong relation, swapped
  entity, explicit negation, conflicting/anaphoric evidence, incidental answer
  word, prompt injection, invalid citation, stale/unpublished/cross-Subject,
  overlimit and malformed-output controls. Measure support reasons and p95
  latency before any new policy deployment and only then spend the remaining
  approved Ask attempt under its same bounded envelope.
- After documenting these findings, `python scripts/check_context.py` passed
  with 37 required files, 75 active guides and 1129 local links;
  `git -c core.safecrlf=false diff --check` passed. This documentation-only
  follow-up did not change backend runtime code or require a repeated backend
  suite. Earlier scope checks and their limits are recorded above.

## Continued staged Ask answer-contract and private offline evaluation

- The existing checkout was preserved. The working branch remains `main` at
  `6c02d6c` plus uncommitted Lane 0–6 work; no volume was deleted, no root
  `.env` value was changed, and no Google request was made in this continuation.
  The owner authorized local volume/configuration changes if needed, but neither
  would fix the observed local-verifier false rejection.
- Added dormant `two_request_local_support_v2` answer-shape handling: the model
  selects bounded server-issued source-unit ranges, while the server derives
  exact current-chunk quotes, citation references and concatenated answer.
  Invalid, cross-chunk, repeated or oversized ranges fail closed. The worker
  branch remains unreachable under the unchanged v1 release-policy constant.
  New migration `20260925_0020` extends the database stage cap and unique
  remote-attempt guard to v2 without enabling it. Existing v1 jobs remain v1.
- A focused offline worker fake exercised v2 supported, local-rejected and
  invalid-citation outcomes. Each made one query embedding and at most one
  answer request; the supported answer persisted the server-derived quote.
  The expanded worker cases passed 15/15. The full backend offline suite passed
  947 with 4 optional model cases skipped. Targeted contract/support/private
  evaluation tests passed 68 with the same 4 skips.
- Disposable PostgreSQL reached 0020, reported no model drift, downgraded and
  re-upgraded, and passed 96 service tests with 3 skipped. The first run of the
  new v2 stage test leaked its queued fixture to later tests and produced six
  suite failures; the test now removes only its own fixture job, and the full
  rerun passed. An earlier invocation with system Python could not load
  Alembic; rerunning with `backend/venv` passed. Disposable containers and
  credentials were cleaned after the tests.
- The read-only local replay used the latest source mounted in a temporary
  answer-worker container against current authorized, published active-space
  chunks. It made zero provider requests and zero database writes. Six fixed
  authored cases were selected; four quote selections bound to v2 source units
  and two exceeded the four-unit limit. The current local verifier accepted
  zero of the four bound positive claims and rejected all four corresponding
  wrong-claim/unrelated-question controls. Exact quote/question/claim pairs
  are still awaiting individual owner review, and no model answer or complete
  top-five context was replayed. This fails the Ask quality gate.
- An unshipped narrow `LocalSupportVerifierV3` candidate improved one synthetic
  exact-acronym case while retaining its wrong-expansion rejection. It does not
  cover the other reviewed topic forms and is not selected by the factory.
  A later read-only private six-case run with the pinned local models accepted
  zero of six authored positives under V3; no real-course improvement was
  established. Its selected quotes were not bound through the v2 source-unit
  contract in that probe. The shipped base verifier additionally rejects empty
  or whitespace-only QA spans, closing a false-relevance edge. Pinned-model targeted tests passed
  44 with 1 unrelated optional skip; no policy/factory change occurred.
- A separate read-only retrieval ablation used stored source vectors as
  labeled surrogates because historical Ask query vectors were not retained.
  With source-oracle vectors, the active exact baseline had 6/6 confirmed-page
  recall@5 and MRR 1.0. Simple bounded OR fell to 5/6 and MRR 0.70; bounded
  OR plus section context restored 6/6 in this surrogate setup. Different-topic
  surrogate vectors mostly missed. This cannot establish real-question recall
  or answerability, so no retrieval policy changed and that Lane 6 item stays
  open. The script emitted only fixed labels/ranks/aggregate metrics and made
  zero provider requests or database writes.
- Updated the source-head navigation and RAG evaluation guide to distinguish
  checkout schema 0020 from the owner's still-0019 database and to record the
  quality boundary. `python scripts/check_context.py` passed: 37 required
  files, 75 active guides, 1130 local links. `git -c core.safecrlf=false diff
  --check` passed. The remaining approved bounded Ask call has not been spent;
  v2 is not deployed or enabled, and Lane 6 remains 3/7 checked.

## Owner review access and final local cleanup for this continuation

- Added an opt-in, escaped static HTML review sheet for the six selected
  private quote/question/claim pairs. It is generated only from an authorized,
  read-only published/active-space view, requires canonical-page alignment,
  writes exclusively to a caller-selected path outside the repository and
  prints only status/count. Synthetic keyless tests cover output escaping,
  path refusal, private-output refusal and CLI exclusivity. The one real sheet
  was created in a dedicated Windows Temp folder for owner inspection; neither
  its text nor its private identifiers were written to this log or tracked
  files. The owner was asked to review the six pairs; no answer has yet been
  received, so no pair is labeled reviewed.
- The finalized retrieval ablation was rerun after its overlap-metric change.
  The source-oracle exact baseline remained 6/6 page recall@5 and MRR 1.0;
  simple OR remained 5/6 and MRR 0.70, with zero scope violations. This is
  surrogate-only evidence and the cutover decision remains blocked. A separate
  V3 private probe accepted zero of six authored positives, confirming the
  narrow synthetic improvement is insufficient. Both probes were read-only,
  keyless and printed only fixed labels/aggregate measurements.
- The temporary answer-worker containers were removed by `docker compose run
  --rm`. The existing database container, started only for these read-only
  probes, was stopped afterward; `docker compose ps` showed no running app
  services. The populated volume and root `.env` were preserved. The owner
  review HTML remains temporarily on this machine until inspection.
- Final focused private-evaluation/contract/migration tests passed 39/39;
  context validation again passed 37 required files, 75 active guides and
  1130 links; `git -c core.safecrlf=false diff --check` passed. No final
  Lane 6 checkbox was changed and no provider request was made.

## Owner review returned

- The owner opened the local-only six-case evidence sheet and reported Yes for
  all three checks on all six cases, with no No answer. This confirms the six
  selected exact Knowledge quote/question/positive-answer pairs, their negative
  controls and original-PDF page meaning for this one Subject. No private
  passage, question wording, identifier or HTML content was copied into this
  record. The sheet's radio state is not persisted; the operator confirmation
  in the task is the review record. This resolves the previously pending
  human-label prerequisite for these six pairs only. It does not establish a
  real query-vector replay, full top-five conflict behavior, provider-output
  correctness, or broad model accuracy. Continue to fail the Ask release gate
  until supported positives pass while adversarial controls remain rejected.

## Post-review source-unit and verifier measurements

- The owner-reviewed six pairs remained the fixed local corpus. The v2 source
  unit partitioner now preserves exact byte offsets while grouping PDF line
  wraps within a sentence; a sentence boundary still makes a narrow unit.
  The bound permits up to six adjacent units, while retaining the 950-character
  and 360-estimated-token quote/claim caps. A focused synthetic PDF-wrap test
  and 58 answer/worker/private replay tests passed. The read-only real-course
  replay now bound all six reviewed quote selections; the active local verifier
  still rejected 6/6 positive claims and all wrong-claim/question controls.
  This is a contract-shape improvement, not a support-quality release.
- A second read-only local probe measured only NLI probabilities and whether
  the pinned extractive QA produced a usable span, without outputting private
  text. One reviewed negative control received 0.866 NLI entailment against
  its quote, demonstrating that a relaxed entailment or lexical gate could
  accept a wrong relation. Lowering the QA no-answer margin in memory produced
  at most one supported positive of six at the tested settings; the remainder
  were rejected by entailment or conflict checks. No QA/NLI threshold, model
  weight, release policy or runtime factory changed. Provider requests and
  database writes were zero in both probes.
- The temporary local HTML review sheet was deleted after the owner reported
  all Yes selections; only aggregate and operator-review evidence remains.

## Further local verifier candidates and regression checks

- Replayed the six owner-reviewed source selections against the current
  checkout mounted read-only in the temporary answer-worker. A first attempt
  against the previously built image failed at import because that image did
  not yet contain the dormant v2 answer contract; no private data was emitted
  and no provider request or database write occurred. The corrected replay
  bound all six cases. Positive verdicts were one contradiction rejection,
  four entailment rejections and one question-relevance rejection. Every
  wrong-claim and unrelated-question control was rejected. This is still a
  single-source, authored-claim probe, not model-output or real-query replay.
- A second keyless, read-only probe passed whitespace-collapsed copies of
  the selected source quote to the pinned QA model while retaining the exact
  server-derived citation. Its six positive and control verdicts were
  unchanged. The PDF line layout alone does not explain the remaining
  verifier failures, so no normalization policy was activated.
- Two additional public ONNX model candidates were downloaded to exact
  temporary ignored directories, checksum-verified, compared locally and
  removed after confirming the paths were within this workspace. The
  quantized MiniLM NLI replacement accepted zero of six reviewed positives
  under the existing full gate and assigned a higher entailment score to a
  wrong BLEU expansion than the pinned NLI model. The quantized DistilBERT
  extractive QA replacement, combined with the pinned NLI model, accepted
  only one of six positives; the sampled negative/question controls stayed
  rejected. Neither candidate was selected. These probes made no provider
  request or database write, sent no private Knowledge to the model host,
  and retained no private passage in logs or artifacts.
- The full keyless backend offline suite passed 960 tests with four optional
  model tests skipped after the v2 source-unit change. No release policy,
  root environment value, owner database migration or app deployment changed.
