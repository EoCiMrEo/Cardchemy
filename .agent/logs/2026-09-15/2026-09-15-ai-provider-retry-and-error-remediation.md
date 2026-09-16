# AI provider retry and error remediation

Date: 2026-09-15

## Problem and evidence

Generation with `gemini-3.8-flash` produced an initial set of HTTP 400 responses
followed by HTTP 429 responses. A single diagnostic call using the production
`SummaryOutput` contract reproduced `400 INVALID_ARGUMENT`, while earlier
minimal structured-output checks succeeded. Removing only Pydantic string
constraints was insufficient in a rebuilt-container check, so the final Gemini
wire schema was reduced to an inline structural shape. The complete strict
contract remains enforced after the response reaches the application.

The request volume had three independent multipliers:

- every document chunk was submitted concurrently before provider compatibility
  was established;
- the summary layer replaced the provider's permanent error with a retryable
  generic summary failure;
- the generation worker then reran the entire job up to its job-attempt limit.

The installed Google SDK defaults to one SDK attempt when no SDK retry settings
are supplied. The adapter now also sets `attempts=1` explicitly so an SDK
default change cannot multiply the application-owned retry count later.

## Changes

- Gemini schemas now inline definitions and send only the provider-side field
  structure while retaining all strict Pydantic validation after generation.
- HTTP 400, 401, 403, and 404 now retain distinct, safe, non-retryable error
  codes and actionable messages. HTTP 429 and other transient classes remain
  retryable.
- A transient provider call makes one initial attempt plus at most three
  retries, waiting exactly three seconds before every retry.
- Gemini SDK retries are explicitly disabled so this remains the total request
  count rather than one layer in a multiplied retry stack.
- Provider-originated `PipelineError` values are preserved rather than replaced
  by `summary_generation_failed`.
- Summary and card stages each make one compatibility probe before fan-out.
  Concurrent sibling tasks are cancelled after the first failure.
- Provider concurrency is shared across all jobs in one worker process instead
  of being multiplied by concurrent jobs.
- A provider/pipeline failure is finalized after that job attempt. Retryable
  failures retain the encrypted source and expose manual Retry, but the worker
  does not immediately repeat the entire expensive pipeline.
- Examples and provider documentation now describe the bounded retry policy.

## Verification

- Targeted provider, pipeline, generation-worker, and Phase 8 runtime suite:
  `56 passed` before the final shared-gate regression was added.
- Provider and pipeline suite after the shared-gate regression:
  `20 passed`.
- Added regression coverage for Gemini schema filtering, HTTP 400 and 404
  classification, exact retry count/delays, permanent-error canary behavior,
  fail-fast propagation, worker finalization without a whole-job retry, and a
  shared cross-job provider concurrency gate.

- Final backend suite: `148 passed, 23 skipped, 1 deselected`. The deselected
  test is the intentionally opt-in live-provider evaluation.
- `docker compose config --quiet` passed for base and development. The
  production overlay passed with non-secret placeholder SMTP requirements.
- Backend and generation-worker images rebuilt; database, backend, and worker
  reported healthy.
- Effective worker settings confirmed Gemini `gemini-3.8-flash`, enabled
  provider, configured credential presence, three provider retries, a
  three-second retry delay, provider concurrency three, and worker concurrency
  two. The final rebuilt worker also reported the Gemini SDK guard as one total
  SDK attempt. No credential value was printed.
- An intermediate rebuilt check that removed only string constraints still
  returned one HTTP 400 and stopped immediately with
  `ai_provider_invalid_request`; there was no fan-out or whole-job retry.
- After switching to the minimal inline wire schema, one live `SummaryOutput`
  call and one live `CandidateBatch` call both succeeded, passed strict local
  validation, and recorded provider usage. A full PDF job was intentionally not
  run to avoid unnecessary provider cost.

No API keys or provider response bodies are recorded in this log.
