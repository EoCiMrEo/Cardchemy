# AI generation evaluation

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

The long allocation case deliberately retains a known limitation: token-weighted
quotas can repeatedly target administrative-only material despite supported facts
elsewhere. No prompt refinement redistributes those quotas. The long target-one
case measures all-chunk evidence transfer separately from accepted-card page
coverage; it does not establish complete pedagogical coverage.

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
cards. These diagnostics are available on the pipeline and are not additional
database/API fields. They never contain document/card text, quotes, IDs, prompts,
provider responses or private exception details. Existing rejected-card and usage
telemetry retain their semantics.

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
OpenAI smoke test below is not a Gemini/refill comparison runner.

Provider wire fixtures and injected test providers exercise both `gemini` and
`openai_compatible` contract profiles without network traffic. The optional
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

The optional live RAG test requires both:

```powershell
$env:RUN_LIVE_RAG_TESTS='1'
$env:RAG_LIVE_EVAL_AUTHORIZED='I_ACCEPT_PROVIDER_CHARGES'
pytest -m ai_live tests/integration/test_live_rag_evaluation.py -q
```

It additionally requires the pinned official answer/embedding profiles,
role-specific credentials/quota buckets and reviewed current prices documented
in [maintained test commands](TESTING.md). It permits at most three physical
provider calls total, zero retries, 12,000 input tokens, 2,048 answer-output
tokens, 60 seconds and USD 0.04. It remains excluded from routine test runs and
requires the explicit charge-acceptance value shown above for each invocation.
