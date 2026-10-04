# AI provider configuration

## Current source-only v8 provider contract — 2026-10-04

Ask AI is enabled in the retained local installation (verified 2026-10-04). The released v8/visual-v5/admission-v2 policy operates
on retained/source head `20261002_0033`; fresh installations remain default-off.
The current new-job identities are `related_knowledge_navigation_v8` /
`hybrid_source_navigation_v9` / `visual_source_id_v5`, with immutable
`literal_subject_admission_v2` context on retained/source head `20261002_0033`.
Each attempt allows at most one raw-current-question embedding and one bounded
source-ID judgment, zero generated-answer/verifier calls and zero automatic
retries. It returns zero to three exact current published-PDF page references,
each visibly unverified; weak pages are never padding. An eligible unresolved
follow-up can transfer only a unique literal subject from the strictly preceding
user question (at most 160 characters/twelve words), immutably bound and
rechecked. Full history and assistant text stay out of provider input.

Its query model remains `gemini-embedding-001`, QUESTION_ANSWERING and the
Subject's exact compatible embedding space. The one optional judge request
uses `gemini-3.5-flash-lite:generateContent`, HIGH, `store=false`, 32,768 input
tokens including images and 4,096 output including thinking, a 120-second
deadline and zero retries. At most four current-page PNGs are bounded to
1,600 pixels/two megapixels/one MiB; request bytes remain at most six MiB.
Only issued source IDs/categories/cue flags are accepted, and exact references
are derived/authorized locally. There is no answer model or local verifier.

Source-judge pricing guards are USD0.30 input/USD2.50 output per million tokens;
they are budget guards, not receipts. Refresh actual price/quota and transfer
conditions before each exact authorized live evaluation. `store=false` does
not guarantee no provider retention, including Free tier; review disclosure
before transferring lecture content or page images. Provider failure and
uncertain spend are retained separately from a true no-match. At most one
application/SDK physical attempt occurs per Ask provider stage.

See [actual local closure and transfer evidence](../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md),
[configuration](CONFIGURATION.md), [maintenance](ASK_AI_SHUTDOWN.md) and
[ADR-024](decisions/ADR-024-gemini-source-id-judge.md). The dated dormant
v4/v5/v6/v7 installation/pilot descriptions below are historical; they do not
override this current identity or authorize replay of consumed trials.

## Historical dormant visual Ask contract — 2026-10-01

Source and retained schema are `20261001_0031`; matching application services
are healthy after a restore-verified forward cutover, with data, original PDFs
and root `.env` preserved. Ask and source judging remain disabled. The
`related_knowledge_navigation_v6` / `hybrid_source_navigation_v9` path uses
`visual_source_id_v2`, Gemini 3.5 Flash-Lite HIGH, 32,768 input / 4,096 output
including thinking and a 60-second provider deadline. It allows at most one
current-question embedding and one issued-ID/category-only judgment, zero
answer/verifier calls and zero automatic provider retries. Full-page PNGs are
bounded to 1 MiB/2 MP/1,600 pixels; definitive oversize alone permits bounded
1,400/1,200/1,000 scale reduction within one 30-second page deadline.

Complete public calibration passed with 89.32% useful displayed cards.
Independent different-PDF/private usefulness and release gates remain open:
the prospective target is 80% displayed usefulness, at least 10/12 ordinary
no-match controls and the existing hit/availability gates. Fabricated,
unauthorized, stale or wrong-page references still require zero. Installed
0030 and historical v5/visual-v1 2,048-token snapshots remain immutable and
readable; they cannot execute or manually retry as v6.

See the [current verification record](../.agent/logs/2026-10-01/2026-10-01-visual-v6-matching-contract-and-backup.md).
Earlier dated v4/v5 details below describe retained history where they differ.


The generation pipeline accepts native `gemini` through a closed, versioned
text-model catalog. Provider clients are created lazily by workers;
the API can still start when credentials are absent and reports a precise
generation-availability reason.

`FLASHCARD_AI_PROVIDER_ENABLED` is the non-secret operator switch shared by the API and
generation worker. When false, the API rejects new generation jobs and the
worker does not claim queued jobs. Provider credentials remain available only
to the worker process.

## Supported profiles

| Role | Default | Model boundary |
|---|---|---|
| Flashcard generation | `gemini-3.8-flash` | `gemini-3.5-flash-lite`, `gemini-3.5-flash`, `gemini-3.6-flash`, `gemini-3.7-flash`, `gemini-3.8-flash` |
| Ask AI (source-only v8) | `gemini-embedding-001` plus `gemini-3.5-flash-lite` source-ID judge | At most one raw-current-question embedding and one bounded ID-only source judgment, with a literal preceding-user subject only for an admitted unresolved follow-up; no answer model or local verifier. The former answer catalog is historical. |

The audited catalog is `gemini-text-2026-09-22-v1` with inline JSON schema
policy `gemini-inline-json-subset-v1`. Flashcard text generation validates its selected model,
thinking level, 1,048,576-token context ceiling and 65,536-token output ceiling
before enqueue and again before worker execution. The former Ask text-model
selection is historical. Gemini 3.7/3.8 reject
`minimal` thinking; the other catalog entries allow `minimal`, `low`, `medium`
and `high`. All catalog text requests use provider-default sampling and count
reported candidate plus thinking tokens in output usage. A model or schema
policy change requires explicit resolution of queued work, not a silent model
substitution. See [ADR-015](decisions/ADR-015-ask-pause-and-gemini-catalog.md).

For native Gemini, use:

```dotenv
FLASHCARD_AI_PROVIDER_ENABLED=true
FLASHCARD_AI_PROVIDER=gemini
FLASHCARD_AI_MODEL=gemini-3.8-flash
FLASHCARD_AI_API_KEY=<provider-key>
FLASHCARD_AI_QUOTA_BUCKET=<account-or-project-quota-label>
```

Remove the retired `FLASHCARD_AI_BASE_URL` key; native Gemini always uses the
official endpoint.
The old `GEMINI_API_KEY` fallback is removed. Use the
[private migration sequence](AI_PROFILE_MIGRATION.md) for existing settings.
After changing provider settings, recreate the API and worker so
both receive the non-secret switch and the worker receives the credential:

```text
docker compose up -d --force-recreate backend worker
```

Recreating the frontend is unnecessary because it reads availability from the
API. Enabling Gemini without a worker credential fails the generation worker at
startup instead of accepting jobs that can never run.

The defaults are independent. Model availability and prices change; operators
must review the provider lifecycle and price pages before paid execution. The
closed catalog rejects unknown and preview model IDs for new work, regardless
of the former unstable-name opt-in. The retired `FLASHCARD_AI_BASE_URL`,
`RAG_AI_BASE_URL` and `RAG_EMBEDDING_BASE_URL` keys must be absent. Historical
`openai_compatible` job and embedding-space identities remain in persisted
data for recovery, but their adapters are unavailable for new execution.

Authoritative references:

- [Gemini model lifecycle](https://ai.google.dev/gemini-api/docs/models)
- [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [Gemini token counting and response usage](https://ai.google.dev/gemini-api/docs/tokens)
- [Gemini thinking levels](https://ai.google.dev/gemini-api/docs/thinking)
- [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing)

Gemini receives a minimal, inline structured-output schema containing only the
field shape required for generation. Descriptions, references, and validation
constraints stay in the server-side Pydantic contract to avoid provider/model
schema-complexity rejection. Provider-native schema still constrains the wire
response, but it is never the trust boundary. The server validates strict
Pydantic types, unknown fields, canonical card rules, exact document grounding,
page/section provenance, and near duplicates before persistence.

## Bounds and pricing

Temperature, Gemini thinking level, context and output tokens, provider timeout/retries, retry delay,
parallelism, RPM/TPM limits, safety margin, logical chunk size, request-packing
target, cards per request, summary budgets, per-job input/output ceilings,
refill rounds, duplicate threshold, and cost ceiling are validated settings
documented in `.env.example`.

Transient timeout, network, HTTP 408/409/425/429, and provider 5xx failures are
retried at most three times after the initial call. The shipped configuration
waits at least three seconds before every retry, honors a longer usable provider
`Retry-After`, and never lets the SDK add a second retry layer. HTTP
400/401/403/404 failures are classified as permanent and are not retried. After
provider retries are exhausted, the job stops without another whole-job
automatic attempt; retryable failures retain the encrypted source so an
operator or instructor can retry later.

The Gemini SDK retry layer is explicitly disabled (`attempts=1`), leaving the
application retry loop as the single owner of request count and delay policy.
This retry policy applies to Flashcard generation and Knowledge indexing. The
source-only Ask worker overrides query-embedding retries to zero: one durable
attempt can make at most one physical embedding request and no answer request. An
uncertain failure is terminal until a separately confirmed manual Retry.

Small, provenance-safe logical chunks are retained, then greedily packed up to
`FLASHCARD_AI_REQUEST_INPUT_TARGET_TOKENS` using the actual rendered prompt. A single-pack
document skips the summary stage. Multi-pack documents summarize per pack, and
card generation requests up to `FLASHCARD_AI_CARDS_PER_REQUEST` cards at once while each
card still cites one trusted logical chunk. With the shipped 40,000-input-token
and ten-card targets, a typical sub-40K document requesting 20 cards needs two
initial provider requests instead of one request per chunk.

Direct batches include the complete evidence pack even when there are more
chunks than cards. Multi-pack summary coverage is server-owned, so the summary
output budget is used for facts rather than repeating source IDs. Request
estimates include repeated direct context and the configured refill allowance;
existing job token/cost limits still apply.

The first required summary request and first card-generation request are
compatibility probes before each stage fans out. A failed probe prevents sibling
requests, and a later failure cancels outstanding siblings. `FLASHCARD_AI_CONCURRENCY` is
enforced once per worker process, so concurrent jobs cannot each create their
own full provider request pool.

Every physical attempt, including a retry, passes through one worker-wide
rolling RPM/input-TPM governor. Defaults mirror a 5 RPM / 250,000 input-TPM
provider tier with an 80 percent safety margin, producing effective budgets of
4 RPM and 200,000 input TPM. Reservations are reconciled to reported input
usage after success and retained after ambiguous failures. This governor is
process-local: operators running multiple generation-worker replicas must divide
limits per replica and across any index/answer workers sharing the provider
account/project quota. A quota bucket is an explicit operator label, not a
distributed governor.
Quota waits are covered by the whole-job time limit. Reaching that limit stops
the job with available telemetry and manual Retry; it never automatically
replays the expensive pipeline.

Set both `FLASHCARD_AI_INPUT_COST_PER_MILLION_USD` and
`FLASHCARD_AI_OUTPUT_COST_PER_MILLION_USD` from the provider’s current price sheet. When
both are zero, token budgets remain enforced and the UI labels monetary cost as
unavailable. Prices are deliberately not hard-coded because they change.

The checked catalog records planning prices for each model, including an
introductory price period through 2026-12-31 for 3.6/3.7/3.8. Refresh actual
prices, model availability, quotas and cost budgets before a separately
authorized live evaluation. Routine tests use offline fakes.

## Provider changes

Provider, model, catalog version and schema-policy version are snapshotted onto
new jobs. Before changing settings, stop new admissions and drain or terminally
resolve queued and retryable jobs. A generation worker rejects an incompatible
old snapshot before PDF extraction and removes its retained source; manual
retry returns a policy-changed conflict. Preserve historical rows and private
content. Re-run the offline corpus and the deliberately opt-in live evaluation
described in `AI_EVALUATION.md` before production rollout.

The implemented [Subject Knowledge flow](architecture/SUBJECT-KNOWLEDGE-FLOW.md)
uses `RAG_EMBEDDING_*` for document and query embeddings and a mandatory
PostgreSQL 16 + pgvector foundation. The completed phase checklist is retained
in the [documentation archive](<archive/Cardchemy-Subject-Scoped RAG Implementation Plan.md>).
See
[ADR-012](decisions/ADR-012-subject-knowledge-and-rag-boundaries.md) for the
accepted boundary. The isolated index worker implements strict bounded document
embeddings; the prospective v5 visual Ask worker owns one query embedding and may make
one bounded source-ID judgment over authorized published page cues. It calls no
answer model or local verifier. API/frontend/email processes receive no
provider key. Configured credentials or enablement do not authorize live
evaluation spending.

The selected new Ask default is native `gemini-embedding-001` for embeddings;
the former `gemini-3.5-flash` grounded-answer profile is historical. The optional
`gemini-embedding-2` profile uses format `gemini2_qa_section_v1`, document/query
mode identities `title_section_text_v1` and `question_answering_query_v1`, one
ordered `Content` object per input and no `task_type`. It remains a distinct
staged space; equal 1,536-dimensional vectors never mix with 001. The default
001 adapter uses `RETRIEVAL_DOCUMENT`/`QUESTION_ANSWERING`. Both normalize
reduced vectors before cosine storage/search. See
[ADR-014](decisions/ADR-014-native-gemini-rag-profiles.md) and
[ADR-018](decisions/ADR-018-gemini-embedding-2-space.md).

The prospective new Ask policy is `related_knowledge_navigation_v5`; historical
v3 snapshots remain fenced. It makes at most one current-question embedding
request and one bounded HIGH-thinking `gemini-3.5-flash-lite` visual source-ID judgment, with no automatic
Ask provider retry, then derives up to three explicitly unverified original-PDF
page references locally. If embedding transport fails, bounded local lexical
search makes no additional embedding request. It makes zero answer-generation
and local verifier calls. Ask remains disabled until public-first, private
source-transfer, displayed-page, access and release gates pass. Historical
`RAG_AI_*`/local-support settings and [ADR-019](decisions/ADR-019-two-request-local-support-ask.md)
describe retained old snapshots, not a path to resume answer generation. See
[ADR-023](decisions/ADR-023-original-pdf-source-navigation.md) and
[ADR-024](decisions/ADR-024-gemini-source-id-judge.md).

The native endpoint identity is `https://generativelanguage.googleapis.com`;
both retired `RAG_*_BASE_URL` keys stay absent. Gemini SDK retries are fixed at
one physical attempt. Gemini thinking tokens are added to reported output usage
and cost; embedding usage remains an explicitly estimated local count when the
provider supplies no token receipt.

Flashcard catalog text requests omit `temperature` and send their validated
`FLASHCARD_AI_THINKING_LEVEL`; the root template's 3.8 Flashcard profile uses
`low`.

Before enabling a provider, review [the transfer disclosure and operator
responsibilities](PRIVACY.md). Source encryption in Cardchemy does not prevent
selected extracted evidence from being sent to the configured provider.
