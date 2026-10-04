# Gemini 3.6 public scored calibration stopped at HTTP 503

Date: 2026-09-29 (America/Chicago). The operator separately approved one
additional public-only eight-PDF pilot after the prior call stopped in the
network-restricted command sandbox. The consent retained the same model,
endpoint, split, token/time/cost limits and zero-retry rule. It did not authorize
private Knowledge transfer, a runtime policy change or Ask activation.

## Preparation and run

The frozen public packet SHA-256 was
`7ec9a83245fd432ff9f19047d1aa5aab1835a0bc9fdab04d9807d87787d19ae7`;
independently reviewed labels SHA-256 was
`bab352ebd06bc77d2bbbfa49f7e960d946bcb5af4d2346f943412c1699cd8ad1`.
A fresh authorization identity produced calibration fingerprint
`fe85d0724342b6a684bc5d3a103d9c5f91c187f8b026e130eb7da2da4be25393`.
Preparation under the permitted command identity found 48 callable groups,
zero clarifications, maximum abstract wire 7,219 bytes. The new approval
receipt SHA-256 was
`d4b25625ed5d838c9acefd1b5c00845b7a4787f9413fd3db02455b68cddfbc86`.
The **credential-free, network-free** preflight passed under the same command
identity before the live invocation. The previous consumed claims were
preserved and not reused.

The live run completed three HTTP 200 source-ID judgments with valid STOP,
issued-ID and usage checks. The fourth physical request received HTTP 503
after about 1.1 seconds. The runner stopped with `stopped_no_retry`, four
attempts, three response-ID and usage receipts, known guard cost **USD
0.007823**, and failed-attempt cost unknown. The successful responses reported
4,120 input and 219 output/thinking tokens in total. The fourth response did
not yield a usage receipt. No retry, fifth call, heldout preparation/score,
application database write or private transfer followed. Its new global
approval/run/call claims remain consumed.

Read-only follow-up verified the four call claims were created six seconds
apart. The fourth request body passed the same offline schema/size builder as
the first three and was 5,443 bytes, below their 5,615–6,162-byte range and
the 8,192-byte bound. This rules out a local body-size guard failure; it does
not identify why the provider returned 503 or establish the account's rate
limit. The HTTP response headers were not retained, so no Retry-After claim is
made.

The four physical attempts are transport/reliability evidence, not a
calibration quality result. Selected public IDs are retained only in the
private OS Temp pilot ledger, not in tracked logs. The three prior Gemini 3.8
failed-call costs and the prior first Gemini 3.6 sandbox attempt remain
unknown; the separately approved two-call Gemini 3.6 transport diagnostic
had a conservative estimate of USD 0.004322. These figures are not an invoice.

## Decision boundary

The original no-retry consent prohibits another call using this authorization.
A further experiment needs a new exact endpoint/model/price/call/token/time/
cost approval and a new audit plan if it changes retry or continuation rules.
The retained v4 runtime still pins Gemini 3.8, Ask remains disabled, and Lane 6
remains 3/7 with all four source-quality/release items open. Provider HTTP 503
does not establish whether the model would have selected useful pages.
