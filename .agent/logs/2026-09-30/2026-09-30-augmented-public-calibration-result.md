# Augmented public source-ID calibration: failed quality gate

Date: 2026-09-30 (America/Chicago). Checkout `main` at `6c02d6c`;
pre-existing working tree, populated database volume and root `.env` preserved.
Ask remains disabled; Lane 6 remains **3/7**. This is an aggregate-only public
experiment record, not an application or private Knowledge result.

## Approved execution

The operator approved the exact public Gemini 3.5 Flash-Lite envelope recorded
in the [preflight log](2026-09-30-approved-augmented-public-pilot-preflight.md).
The first network-enabled launch stopped **before key access or a provider
attempt**: the process could not read the local OS Temp packet. We copied only
the eight approved public PDFs, their official schedule, the frozen packet,
overlap record and keyless approval receipt into ignored
`.agent/.verification/fresh-public-v2-approved-70a577/`; SHA-256 checks
matched the source manifest, freeze and approval. A second zero-network
preflight in that environment passed, then the approved single calibration
execution ran. The one-use ledger contains 66 physical claims. The source
PDF parser emitted known structural warnings during local extraction; the
source and page hashes still matched. No private Knowledge or database
record was accessed or transferred.

## Actual measured outcome

Calibration completed **66/66** physical requests with valid responses,
zero automatic retries, zero provider failures and zero invalid model output.
Provider usage reported 84,067 input and 1,087 output tokens. The conservative
price guard estimates **USD 0.027963** from reported usage, not a bill; actual
fees from earlier failed pilots remain unknown. The completed run binds
approval SHA-256 `70a577ac506a41fb256048f355447de34ae351899194006062b138dc8523e127`,
request manifest `f0b1e14f0665d280551a3b4887978a1e017a339eb202e57413698ceb96fab2b3`,
evaluation `6a6b467941fc57769216d40e9b73b9f11f3a05f694eeae73b666c2b8fcf3e954`
and claim manifest `098014fcb5aabefe6de0e6dd9d8562efd39d407b31fd8a2f64ba4fb83fc56f26`.

| Predeclared calibration measure | Result | Decision |
| --- | ---: | --- |
| Valid responses | 66/66 | Pass |
| Positives with a useful selected page | 53/54 | Pass for global hit gate |
| Displayed original-PDF page **and cue** useful | 81/84 = 96.4% | Pass ≥90% |
| No-useful questions displaying zero pages | 11/12 | **Fail; required 12/12** |
| One-useful exact selection | 19/19 | Pass |
| Two-useful exact selection | 11/17 | Fail proportional cardinality gate |
| Three-useful exact selection | 4/16 | Fail proportional cardinality gate |
| Four-useful overflow selecting three useful IDs | 1/2 | **Fail; required 2/2** |

The 60 different-PDF heldout questions were **not opened, called or scored**.
The run did not prove private-source quality or permit an Ask runtime switch.

## Diagnosis and limit

Aggregate ID-only analysis found 18 groups with fewer selections than their
independently useful pages and three over-selections. Twelve of 18 newly
authored reserve groups were under-selected, compared with six of 48 original
groups. One no-useful question asked for a **reported batch size**; the chosen
public page described stochastic gradient descent but did not provide the
requested batch-size result. The other dominant error is choosing only the
strongest one or two reading pages when several independently useful pages
exist. These observations are calibration diagnostics, **not** authority to
rewrite labels, delete hard cases, relax gates or reuse the unopened heldout
as though the current candidate passed. Any new candidate needs a prospectively
reviewed plan/ADR change, a new one-use ledger and a separately approved
provider envelope. Until then, preserve the failure and keep Ask off.
