# Stronger public page judge: provider-availability stop

Date: 2026-09-30 (America/Chicago). This is the result of one separately
approved, one-use public-only `gemini-3.5-flash` calibration pilot under the
[exact envelope](2026-09-30-stronger-page-judge-approved-offline.md).

## Physical attempts and stop

- The new SHA-bound calibration approval passed the isolated keyless
  preflight before execution. The frozen 66 public request bodies matched the
  prior four-verdict candidate; the body manifest SHA was
  `fd4421940eb613523d126138e6453e4e4e731bf14af1ae03b908b783fb75e6ed`.
- Ten physical POST claims were consumed, with no retry. Seven returned
  schema-valid per-page verdicts and usage receipts; three returned HTTP 503.
  The runner stopped at its frozen `too_many_provider_failures` guard. No
  further calibration request was sent. The run-stop receipt SHA is
  `62a354772b789769d6577f1dc3f07bed0d1566d1f9beab54a04aa641c4778c73`.
- Successful receipts reported 8,954 input and 1,019 output tokens, a
  conservative Paid-price guard estimate of **USD 0.022604**. Actual cost of
  the three failed calls and earlier failed pilots is unknown; Free-tier
  billing was not inferred to be a provider receipt.
- The new ledger holds its calibration split claim plus ten attempt claims;
  it has **zero heldout claims**. The 60 different-PDF heldout was not opened
  or called. The previous v3 ledger and retained local database were not
  reused or changed.

There is **no complete 66-case calibration quality score**. The three
HTTP 503 failures already exceed the approved maximum of two transport
failures for that split, so continuing this same pilot cannot pass its
availability gate. Its one-use authorization is consumed; do not resume,
retry, relabel or substitute the seven valid cases as a pass. The provider's
[API error guide](https://ai.google.dev/gemini-api/docs/api-errors)
describes 503 as a temporarily unavailable or overloaded service; the
numeric responses here do not identify a more specific upstream cause.
This result neither proves nor disproves the stronger model's page-selection
quality. Ask remains disabled, and Lane 6 remains **3/7**.

The public-only pilot sent no private Knowledge, PDF bytes, history,
identity or review labels. No application database write, new index, model
switch or Ask activation occurred. The populated volume, root `.env`,
archived original PDFs, frozen evaluation packet and independent holdout
were preserved. Another paid evaluation needs a new approved plan, exact
endpoint/model/price/call/token/time/cost envelope and one-use ledger.
