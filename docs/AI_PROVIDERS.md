# AI provider configuration

The generation pipeline supports `gemini` and `openai_compatible` through one
strict application contract. Provider clients are created lazily by workers;
the API can still start when credentials are absent and reports a precise
generation-availability reason.

## Supported profiles

| Provider | Required settings | Production baseline |
|---|---|---|
| `gemini` | `AI_MODEL`, `AI_API_KEY` | A specific stable Gemini text model with structured JSON output and usage metadata |
| `openai_compatible` | `AI_MODEL`, `AI_BASE_URL`; key when the endpoint requires one | Chat Completions, separate system/user roles, strict JSON Schema response format, output-token limits, and usage metadata or estimator fallback |

The default, `gemini-3.8-flash`, is a specific stable identifier in Google’s
model catalog as checked on 2026-09-14. Model availability changes over time;
operators must review the provider’s lifecycle page during upgrades. Production
configuration rejects names containing `preview`, `latest`, `experimental`, or
`exp` unless `AI_ALLOW_UNSTABLE_MODEL=true` is an explicit risk decision.

Authoritative references:

- [Gemini model lifecycle](https://ai.google.dev/gemini-api/docs/models)
- [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [Gemini token counting and response usage](https://ai.google.dev/gemini-api/docs/tokens)
- [Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai)
- [OpenAI Chat API usage fields](https://developers.openai.com/api/reference/resources/chat)

Provider-native JSON Schema constrains the wire response, but it is never the
trust boundary. The server validates strict Pydantic types, canonical card
rules, exact document grounding, page/section provenance, and near duplicates
before persistence.

## Bounds and pricing

Temperature, context and output tokens, provider timeout/retries, retry jitter,
parallelism, chunk/summary budgets, per-job input/output ceilings, refill
rounds, duplicate threshold, and cost ceiling are validated settings documented
in `.env.example`.

Set both `AI_INPUT_COST_PER_MILLION_USD` and
`AI_OUTPUT_COST_PER_MILLION_USD` from the provider’s current price sheet. When
both are zero, token budgets remain enforced and the UI labels monetary cost as
unavailable. Prices are deliberately not hard-coded because they change.

An OpenAI-compatible URL cannot contain credentials, query parameters, or a
fragment. Prefer TLS for hosted endpoints. Plain HTTP is appropriate only on a
trusted private network such as the internal Compose network. Never put keys in
the URL; use `AI_API_KEY`.

## Provider changes

The provider and model are snapshotted onto each job. Before changing models or
credentials, stop new admissions and drain, complete, or cancel queued and
retryable jobs. This avoids attempting an old model snapshot against a new
provider account. Re-run the offline corpus and the deliberately opt-in live
evaluation described in `AI_EVALUATION.md` before production rollout.

No embeddings, vector database, retrieval-augmented generation profile, or
`pgvector` extension is included. Adding one later requires an explicit
optional dependency profile, migrations, privacy analysis, and tests.
