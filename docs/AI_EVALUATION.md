# AI generation evaluation

## Current local Lane 6 closure — 2026-10-04

The local source-only v8/visual-v5/admission-v2 installation on head `0033`
is enabled after its measured quality, PDF/display and release gates. Fresh
installations remain default-off. See the
[closure and activation evidence](../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md). Earlier installation
checkpoints below remain historical snapshots; the linked closure supersedes
their off/pending status, while default-off and upgrade safeguards still apply.

## Current source-only evaluation state — 2026-10-03

The [independently reconciled public heldout](../.agent/logs/2026-10-03/2026-10-03-public-heldout-v11-terminal-result.md)
passed all unchanged current public gates on **60/60 cases**: **94/99 (94.95%)**
useful displayed cards, **48/48** positive hits, **58/60** valid outcomes and
**10/12** clear empty no-match outcomes. Prior manually replaced failures remain
in the physical ledger: **58/70** valid physical requests. Reviewer-Unsure cards
receive no usefulness credit. This mixed-parser result preserves every old
failure and selected ID; it is not a guarantee for arbitrary lecture questions.

The matching dormant runtime is v8/visual-v5/admission-v2 at source and retained
head `20261002_0033`. Restore-verified forward migration and retained heads/drift
passed; Ask stays off. The change keeps one current-question embedding, one
ID-only judgment, no answer/verifier and no automatic retry. Its `ignore`
handling is a narrow lexical routing repair; conflicting cues on a non-useful
page are discarded without promoting that page. Neither change is a semantic
instruction classifier. Public success does not authorize private Knowledge
transfer, provider calls or activation. Private original-PDF displayed-source,
matching-service and final release gates remain separate.
See [ADR-024](decisions/ADR-024-gemini-source-id-judge.md). The earlier state below
is preserved as dated history, not regraded.

## Historical v7 evaluation state — 2026-10-02

For the current Ask source-only navigation gate, the owner-approved
[2026-10-01 metrics](RAG_EVALUATION.md#current-source-navigation-release-metrics)
set complete displayed-card usefulness at **80%**. Hit/no-match/access and
release gates remain; historical 90%/exact-set pilot records below are not
regraded. This is separate from flashcard validation and does not permit
provider execution, private source transfer or Ask activation by itself.
The prospective public ordinary no-match floor is at least 10/12 clear empty
outcomes; source authenticity, authorization, revision and exact PDF page
integrity still require zero fabricated, unauthorized, stale or wrong-page
references. Source and retained head are `20261002_0032`, with dormant visual
v7 `visual_source_id_v3` behind the closed Ask fence. It may send current
question, bounded published text/cues and rendered original-page PNGs to one
ID-only judge, plus a uniquely bound literal preceding-user subject only for
an unresolved follow-up. Full history and assistant text are excluded. Current
application output is capped at 4,096 tokens including thinking, with a
120-second source-judge deadline. The complete public calibration passed with 92/103 useful displayed
cards (89.32%); different-PDF heldout, private-source and release gates remain
open. A prepared heldout caller and blind input review make no provider calls
and cannot activate this policy. The separately approved sixty-question trial
subsequently stopped after six requests because three network/provider failures
made availability unreachable; its partial two useful cards are not a quality
pass. The later [v6 public trial](../.agent/logs/2026-10-02/2026-10-02-public-heldout-v6-terminal-result.md)
also stopped on availability after 38 observed questions; partial 49/50
usefulness does not close the gate. See [current retained checks](../.agent/logs/2026-10-02/2026-10-02-v7-retained-cutover-and-release-recheck.md).

The [private v6 hybrid-input preparer](../backend/scripts/prepare_private_navigation_v6.py)
is an inert, provider-free component requiring exact external vector/source/gold
pins and current SQL authorization. Explicit preparation runs production
retrieval and visual preparation in one read-only snapshot, keeps all twelve
cases and writes a bounded private Temp artifact. A finite four-CPU/two-GiB
container and an outer hard 300-second process fence are mandatory; AI keys
and enabled Ask are rejected. Synthetic contracts establish mechanics only.
Actual vectors, independent candidate review, source judgment and complete
display/release measurements remain separate.

The generation pipeline uses a fixed, authored evaluation corpus under
`backend/tests/fixtures/ai_eval/`. Normal CI is deterministic, offline, and
never needs provider credentials.

## Corpus cases

- Short multi-page facts exercise exact target allocation and provenance.
- A document longer than the former 30,000-character boundary places unique
  facts at its beginning, middle, and final page.
- An injection case mixes legitimate facts with commands to ignore system
  instructions, fabricate answers, expose secrets, and change output format.
- Duplicate/invalid candidates include paraphrased questions, repeated
  options, unsupported answers, invented quotes, and valid replacements.
- Unicode text exercises NFKC normalization, whitespace folding, and repeated
  headings.

The additional [quality-v2 corpus](../backend/tests/fixtures/ai_eval/quality_v2.json)
contains authored questions, parallel options and complete contiguous supporting
quotes without artificial uniqueness markers. It covers feasible underproduction
and distinct refill, sparse/impossible sources, repeated boilerplate, same-source
split batches, 40-token chunk overlap, Unicode/OCR whitespace, untrusted injected
instructions, and a document beyond 30,000 characters. Invalid cases exercise wrong
IDs, invented/stitched quotes, missing answer spans, malformed options and cosmetic
paraphrases. Existing mechanics regressions remain intact.

An additional provider-free integration case now sends an authored one-page
PDF through real worker extraction and the generation pipeline. A scripted
provider yields two validated cards for a target of three; the worker stages
both privately without a set, and exact-two confirmation creates one draft
set with no additional provider call. See the
[dated rehearsal](../.agent/logs/2026-09-28/2026-09-28-flashcard-extraction-choice-rehearsal.md).
This verifies the extraction-to-choice mechanics, not Gemini yield from a
genuinely sparse whole document or instructor-rated teaching quality.

The long allocation case preserves the prior fixed token-weighted allocator as
a regression baseline: it repeatedly targeted administrative material despite
supported facts elsewhere. The Lane 6 adaptive allocator gives bounded work to
untried/underrepresented chunks and uses observed validated yield on refill.
The long target-one case still measures all-chunk evidence transfer separately
from accepted-card page coverage; it does not establish complete pedagogical
coverage or real-model yield.

## Prompt and replay measurement

Generation, map and reduce prompts have fixed versions in
[the prompt module](../backend/app/ai/prompts.py). Generation requests the assigned
target only when distinct facts support it, specifies per-source quotas, compact
parallel distractors, exact answer spans and contiguous verbatim quotes. Summaries
guide navigation only. Refill includes previously accepted questions/answers as
untrusted concept exclusions: at most 32 clipped pairs and 384 local tokens for
the complete serialized JSON list. All complete accepted cards still participate
in duplicate rejection.

Packing estimates include the actual rendered instructions and exclusions.
Preflight adds the bounded exclusion list/field envelope numerically (a long text
placeholder cannot conservatively reserve punctuation-heavy lexical tokens), and
renders map/reduce instruction overhead. Future summary size is estimated from an
output planning surrogate; provider tokens and the local estimator are different
measurements. Actual rendered per-call context and remaining-job input/output/cost
admission remain authoritative. Concurrent calls reserve their envelopes before
requests; successful responses reconcile to reported usage. Errors/cancellation
release pending capacity into conservative uncertain envelopes charged until the
run ends. Retry usage without a receipt remains unknown, so telemetry is not a
complete billing ledger. A facade refuses overlapping reuse and drains sibling
requests before a subsequent run resets accounting.

Content-free pipeline results/errors include fixed prompt versions, round raw/
grounded/distinct/accepted/missing counts, bounded rejection categories, refill
round use and uncertain-request count. Raw counts include successful receipts even
if a later sibling request fails; validation/acceptance counts describe inspected
cards. Lane 6 persists a bounded latest-attempt diagnostic object on the job,
including per-round raw, grounded, valid, distinct, accepted, missing and fixed
rejection-category counts. The owner response exposes that object, the latest
attempt's rejected count and the separate cumulative rejected count.
`accepted_card_count` remains the number actually persisted in a result set;
the temporary validated-candidate count is separate while awaiting an exact
smaller-target choice. These diagnostics never contain document/card text,
quotes, IDs, prompts, provider responses or private exception details. Usage
telemetry remains an incomplete billing ledger when execution was uncertain.

The current keyless authored long-allocation run reached its exact target of
two cards: 2 raw and 2 accepted, zero duplicate rejections, one refill, seven
logical requests, 3/3 evidence chunks transferred and two accepted pages. Its
local estimator counted 12,501 input and 288 output tokens. A historical
2026-09-17 fixed-allocation run on an older checkout produced one accepted card
and failed the same target after eight requests; this is a historical comparison,
not a same-checkout A/B or proof of paid-model improvement. A 39-chunk
Week-3-shaped synthetic allocation check covered 20 distinct chunks in round
one and all 39 cumulatively by round two; it does not establish 20-card yield
from the owner's private lecture.

The separately approved 2026-09-25 read-only private-source diagnostic selected
the latest eligible failed 20-card job's current reviewed, published Knowledge.
Its 42 canonical pages prepared 39 chunks. The no-provider preflight estimated
6 requests, 37,140 input and 32,256 output tokens, and USD 0.091782 under
the approved 16-request, 120,000-input, 48,000-output, USD 0.18 admission
envelope. The one live run then produced 20 locally validated distinct cards
from 20 pages in 4 physical requests and 42.349 seconds. Round accepted counts
were 19, 0 new, then 1 new; one candidate was rejected because its answer was
not contained in its quote. The local price estimate from provider usage was
12,827 micro-USD, not an invoice. No cards, set or source content were written
by this diagnostic. This demonstrates a feasible result on one private source;
it does not establish instructor-rated card quality or reliability across
documents. The aggregate-only evaluator is
[`evaluate_private_generation.py`](../backend/scripts/evaluate_private_generation.py).

Run the deterministic comparison from `backend`, supplying an absolute output
path for synthetic evaluation evidence:

```powershell
venv/Scripts/python.exe -m tests.support.quality_replay --output <absolute-output.md>
```

The replay freezes only the old generation renderer and uses the current system/
map/reduce/enforcement for both variants. Its deliberately scripted provider emits
one supported fact per source, then repeats it unless explicitly excluded. Compare
exact-target outcomes, accepted/raw yield, fixed rejection counts, duplicates,
refill use, requests, transferred/expected chunks, accepted pages, local tokens,
fixture-price cost and local latency. These measurements establish exclusion and
enforcement mechanics, not remote model yield, latency, billing or injection
refusal. The unchanged ten-card wire output limit is 5,376 tokens with an 8,192
configured ceiling; compact output precedes any separately measured cap change.

The corpus contains a human review rubric: meaningful fact, unambiguous question/
answer, plausible parallel distractors, compact wording, contiguous evidence and
coverage without repetition. Each criterion scores 0–2; unsupported or ambiguous
answers fail regardless of total. The authored exemplars remain subject to explicit
instructor judgment, which cannot be inferred from deterministic quality scores.
Any real-model A/B comparison needs separate explicit authorization and reviewed
endpoint/model/prices/call/token/time/cost guards. The existing one-call pinned
Gemini smoke test below is not a multi-model/refill comparison runner.

Provider wire fixtures exercise the native `gemini` contract and fail-closed
legacy-provider rejection without network traffic. The optional flashcard
live test is excluded from normal runs and must be explicitly enabled with
`RUN_LIVE_AI_TESTS=1` after the operator reviews the selected model and cost
configuration.

## Release thresholds

| Metric | Required result |
|---|---:|
| Strict schema validity of persisted cards | 100% |
| Rejection of known-invalid candidates | 100% |
| Valid server-derived source references | 100% |
| Answers contained in verified source evidence | 100% |
| Known near duplicates remaining | 0% |
| Successful jobs matching requested count | 100% |
| Partial sets from failed quality runs | 0 |
| Source chunks included in hierarchical summarization | 100% |
| Injection-compliance failures | 0 |
| Provider calls after a failed preflight budget | 0 |
| Requests exceeding configured token limits | 0 |
| Provider contract scenarios normalized identically | 100% |

Run the offline quality suite from `backend`:

```powershell
$env:PYTHONUTF8='1'
pytest tests/test_ai_chunking.py tests/test_ai_grounding.py tests/test_ai_pipeline.py tests/test_ai_evaluation.py tests/test_ai_quality_refinement.py tests/test_ai_providers.py tests/test_ai_rate_limit.py -q
```

Run a deliberately opt-in live smoke test only after configuring the provider:

```powershell
$env:RUN_LIVE_AI_TESTS='1'
pytest -m ai_live tests/integration/test_live_ai_pipeline.py -q
```

The live evaluation requires process-injected `FLASHCARD_AI_PROVIDER_ENABLED=true`,
the native Gemini adapter with its official endpoint and pinned stable
`gemini-3.5-flash-lite` model and `minimal` thinking, provider credentials, an explicit
`FLASHCARD_AI_QUOTA_BUCKET` assigned to this
worker's share of the provider account/project limits, and reviewed nonzero
`FLASHCARD_AI_INPUT_COST_PER_MILLION_USD` and `FLASHCARD_AI_OUTPUT_COST_PER_MILLION_USD` prices.
Tests never load the operator's root `.env`. It requests two grounded cards,
permits one physical provider request, disables provider retries and refill
rounds, and caps input at 8,192 tokens, output at 2,048 tokens, estimated cost
at USD 0.02, and the request timeout at 30 seconds. An offline budget probe
proves that extra requests or token/cost overruns are refused before a call.
On 2026-09-20 the operator explicitly authorized this bounded profile and the
final current-code run passed once in 3.47 seconds (`1 passed, 19 deselected`).
That result proves only the guarded sample at that time, not future model
availability, pricing or provider billing completeness.
See [maintained test commands](TESTING.md) for the supported model, exact
configuration, price floors, and full-envelope admission rules. Other providers
and models need a separate bound for their complete billable token usage.

Captured or offline results validate application invariants and provider
contract parity. A release owner should run the live corpus against every model
selected for a deployment because remote model behavior and pricing can drift
without application code changes.

## Subject Knowledge and Ask AI evaluation

RAG uses a separate authored corpus, metric policy and live authorization. See
[Subject Knowledge evaluation](RAG_EVALUATION.md) for the v2 direct,
paraphrase, technical, overlap, ambiguity, conflict, injection, authorization,
lifecycle and invalid-support cases. The deterministic evaluator plus actual
PostgreSQL exact-vector/FTS tests enforce recall/ranking, support, abstention,
citation, exposure, latency, throughput, context and provider-stage gates.
Those passes do not establish current remote embedding or answer quality.

The historical live RAG harness admits only answer policy
`two_request_local_support_v1`: one query embedding, one structured answer,
zero provider retries and the pinned offline `local_nli_qa_v1` gate. It also
requires a matching active Subject space and a newly reviewed
endpoint/model/prices/call/token/time/cost envelope before every paid run.
`scripts/evaluate_local_support.py` separately measures the eleven-case local
semantic corpus and CPU/RAM/startup/package/latency ceilings without making a
provider or network call. Neither result replaces current deployment-specific
privacy, model-license or remote-quality review.
The 2026-09-23 authorized synthetic live sample passed with one physical query
embedding request and one answer request after the local definition-paraphrase
gate was corrected; the preceding failed sample's cost is unknown. See the
[RAG evaluation record](RAG_EVALUATION.md#live-deployment-model-boundary) for
the exact bounded evidence.

The approved new Ask mode is source-only [ADR-022](decisions/ADR-022-related-knowledge-primary-ask.md).
It needs independent owner-reviewed **displayed excerpt** and open-page
evaluation under the [source-only gate](RAG_EVALUATION.md#source-only-displayed-window-gate-not-yet-passed).
The earlier answer-model live harness does not validate it. Any new remote
embedding evaluation requires a fresh explicit endpoint/model/price/call/token/
time/cost envelope; neither credentials nor this documentation authorize spend.
The following ADR-023/024 discussion records the **earlier 90% and v4/0029
pilot contracts**. The current 80%, 10/12 no-match and v8/0033
state is summarized above; do not regrade old trials. The
[ADR-023 original-PDF navigation](decisions/ADR-023-original-pdf-source-navigation.md)
release gate at that time required at least 90% useful original PDF pages among
**all displayed** citation cards, plus useful-page hit@3, no-match and access checks.
Three separate frozen public Mixedbread display candidates stopped at calibration;
their heldouts were not scored or used for training/calibration. The selective audit's single approved
networkless run is recorded in its [dated evidence](../.agent/logs/2026-09-28/2026-09-28-selective-navigation-frozen-audit.md).
The subsequently approved groupwise 0–3 count-cap/per-card audit scored 576
public train/calibration pairs in 20 local calls and passed resource limits,
but no calibrated set-risk rule met zero no-useful displays, at least 90%
useful exact-cue-plus-page cards among every displayed card and useful
positive hit@3 at least 30/36 together. Its frontier is diagnostic only;
there is no selected display policy. All three ledgers are consumed. None
authorizes runtime integration, another score, or a paid multi-vector query
experiment. Ask remains disabled until independent published-source and
release gates pass.

The later [ADR-024 source-ID judge](decisions/ADR-024-gemini-source-id-judge.md)
is an **approved prospective** source-only architecture after those three
calibration failures. It may use at most one current-question embedding plus
one separately bounded Gemini `source_judgment` call returning only issued
candidate IDs; zero answer-model/verifier calls remain mandatory. The dormant
v4 policy, worker and schema head `0029` exist, but the retained release-policy
fence keeps Ask disabled and its source judge is pinned to `gemini-3.8-flash`.
The later approved public-only Gemini 3.5 Flash-Lite calibration produced ten
accepted source-ID receipts, then its eleventh call timed out at 30.006 seconds.
It stopped without retry, has no complete 48-case score and did not open the
heldout. See the [dated stop](../.agent/logs/2026-09-29/2026-09-29-flash-lite-public-calibration-timeout-stop.md).
That one-use authorization is consumed; neither its 10 responses nor the
earlier 3.6 attempts establish source-selection quality. A new exact
endpoint/model/price/call/token/time/cost envelope is required for further
provider evaluation. The owner subsequently chose to seal the timed-out
eleventh calibration group as a miss rather than replay it. The amended
future public score requires at least 46/48 accepted responses per split,
counts transport failure in the full question denominator without treating
it as a valid `no_match`, and retains the ≥90% all-displayed-card cue-plus-PDF
gate and sealed different-PDF heldout. That decision alone authorized no
continuation. A separately approved continuation then made 37 accepted
public calls for groups 12–48. The full calibration scored 47/48 valid
responses, 35/36 useful-page hit@3 and 54/55 useful displayed cue-plus-PDF
cards, but **failed** because one of twelve completed no-useful groups
displayed a page. The different-PDF heldout was not opened; the new one-use
authorization is consumed. The approved
`public_exhaustive_page_and_cue_v2` ID-only prompt/candidate prototype is
offline only. It requires a new disjoint public PDF calibration and heldout,
with unchanged gates and separate acquisition/provider approval; it has no
quality result. See the [result](../.agent/logs/2026-09-30/2026-09-30-flash-lite-failure-inclusive-calibration-result.md)
and [next-candidate decision](../.agent/logs/2026-09-30/2026-09-30-source-id-calibration-cause-and-next-candidate.md).
Selecting a different judge for the
retained application also requires a versioned runtime/policy change.
Explicit private lecture
transfer disclosure, independent original-PDF usefulness measurements and
release checks remain required before Ask can open. The current credentials,
public receipts and consumed audit ledgers authorize none of those steps.
