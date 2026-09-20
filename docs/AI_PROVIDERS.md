# AI provider configuration

The generation pipeline supports `gemini` and `openai_compatible` through one
strict application contract. Provider clients are created lazily by workers;
the API can still start when credentials are absent and reports a precise
generation-availability reason.

`FLASHCARD_AI_PROVIDER_ENABLED` is the non-secret operator switch shared by the API and
generation worker. When false, the API rejects new generation jobs and the
worker does not claim queued jobs. Provider credentials remain available only
to the worker process.

## Supported profiles

| Provider | Required settings | Production baseline |
|---|---|---|
| `gemini` | `FLASHCARD_AI_PROVIDER_ENABLED=true`, `FLASHCARD_AI_MODEL`, `FLASHCARD_AI_API_KEY` | A specific stable Gemini text model with structured JSON output and usage metadata |
| `openai_compatible` | `FLASHCARD_AI_PROVIDER_ENABLED=true`, `FLASHCARD_AI_MODEL`, `FLASHCARD_AI_BASE_URL`; key when the endpoint requires one | Chat Completions, separate system/user roles, strict JSON Schema response format, output-token limits, and usage metadata or estimator fallback |

For native Gemini, use:

```dotenv
FLASHCARD_AI_PROVIDER_ENABLED=true
FLASHCARD_AI_PROVIDER=gemini
FLASHCARD_AI_MODEL=gemini-3.8-flash
FLASHCARD_AI_API_KEY=<provider-key>
FLASHCARD_AI_BASE_URL=
FLASHCARD_AI_QUOTA_BUCKET=<account-or-project-quota-label>
```

`FLASHCARD_AI_BASE_URL` must remain empty for the native Gemini adapter.
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

The default, `gemini-3.8-flash`, is a specific stable identifier in Google’s
model catalog as checked on 2026-09-14. Model availability changes over time;
operators must review the provider’s lifecycle page during upgrades. Production
configuration rejects names containing `preview`, `latest`, `experimental`, or
`exp` unless `FLASHCARD_AI_ALLOW_UNSTABLE_MODEL=true` is an explicit risk decision.

Authoritative references:

- [Gemini model lifecycle](https://ai.google.dev/gemini-api/docs/models)
- [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [Gemini token counting and response usage](https://ai.google.dev/gemini-api/docs/tokens)
- [Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai)
- [OpenAI Chat API usage fields](https://developers.openai.com/api/reference/resources/chat)

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

An OpenAI-compatible URL cannot contain credentials, query parameters, or a
fragment. Prefer TLS for hosted endpoints. Plain HTTP is appropriate only on a
trusted private network such as the internal Compose network. Never put keys in
the URL; use `FLASHCARD_AI_API_KEY`.

## Provider changes

The provider and model are snapshotted onto each job. Before changing models or
credentials, stop new admissions and drain, complete, or cancel queued and
retryable jobs. This avoids attempting an old model snapshot against a new
provider account. Re-run the offline corpus and the deliberately opt-in live
evaluation described in `AI_EVALUATION.md` before production rollout.

The [subject-scoped RAG plan](<../Cardchemy-Subject-Scoped RAG Implementation Plan.md>)
adds independent `RAG_AI_*` and `RAG_EMBEDDING_*` profiles and a mandatory
PostgreSQL 16 + pgvector foundation. See
[ADR-012](decisions/ADR-012-subject-knowledge-and-rag-boundaries.md) for the
accepted boundary. The isolated index worker now implements strict bounded
document embeddings; the answer worker owns query embeddings, grounded answer
generation and semantic support evaluation. API/frontend/email processes receive
no provider key. Configured credentials or enablement do not authorize live
evaluation spending.

The selected RAG profiles are native Gemini: `gemini-3.5-flash` for grounded
answer/support JSON and `gemini-embedding-001` for embeddings. The embedding
adapter requests 1,536 dimensions, uses `RETRIEVAL_DOCUMENT` for stored chunks
and `QUESTION_ANSWERING` for questions, and L2-normalizes reduced vectors before
cosine storage/search. The native endpoint identity is
`https://generativelanguage.googleapis.com`; both `RAG_*_BASE_URL` values stay
empty. Gemini SDK retries are fixed at one physical attempt so the application
remains the sole retry owner. Gemini thinking tokens are added to reported
output usage and cost; embedding usage remains an explicitly estimated local
count when the provider supplies no token receipt. See
[ADR-014](decisions/ADR-014-native-gemini-rag-profiles.md).

Gemini 3 text requests omit `temperature`, as recommended by the provider, and
send the validated role-specific `*_THINKING_LEVEL`. The initial grounded-answer
profile pins `minimal` for a bounded factual task; the root template's Gemini
3.8 flashcard profile uses `low`, since 3.8 does not accept `minimal`. Older
Gemini models retain the configured temperature and do not receive a Gemini 3
thinking-level field.

Before enabling a provider, review [the transfer disclosure and operator
responsibilities](PRIVACY.md). Source encryption in Cardchemy does not prevent
selected extracted evidence from being sent to the configured provider.
