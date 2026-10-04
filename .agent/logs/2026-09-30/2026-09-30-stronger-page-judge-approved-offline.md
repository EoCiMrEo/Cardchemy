# Approved stronger public page judge: offline preparation

Date: 2026-09-30 (America/Chicago).

## Starting point and decision

The one-use public `gemini-3.5-flash-lite` per-page pilot completed 66
calibration attempts with 65 valid replies and one timeout. All 63 displayed
page/cue cards were useful and no no-useful group showed a page, but the
frozen two-page, three-page and overflow cardinality gates failed. The
different-PDF heldout was neither opened nor called; Ask remained disabled.
See the [result](2026-09-30-per-page-verdict-calibration-result.md).

The operator approved the
[same-wire recommendation](2026-09-30-stronger-page-judge-recommendation.md)
for one prospectively versioned, public-only `gemini-3.5-flash` comparison.
The approved plan/ADR amendment preserves the exact four-page questions,
cues, prompt, response parser, local selector, 66/60 split and all frozen
quality gates. It permits keyless offline preparation. It is not an approval
to transfer private Knowledge, change the application runtime or enable Ask.
A separate exact endpoint/model/price/call/token/time/cost envelope and
one-use receipt are required before any provider call.

## Separately approved public live envelope

The owner then approved exactly one `gemini-3.5-flash:generateContent`
pilot on the eight frozen CC BY 4.0 public PDFs. The calibrated split has at
most 66 POST requests; the 60-group different-PDF heldout is conditional on
every frozen calibration gate. There are no retries, at least 20 seconds
between request starts, 30 seconds per request, 60 minutes per split and
120 minutes overall. Each request is capped at 8,192 input and 1,024 output
tokens (1,032,192/129,024 across both splits). The approved conservative
[Paid-tier guard](https://ai.google.dev/gemini-api/docs/pricing) is USD 1.50
input/USD 9.00 output per million tokens, with separate new-cost ceilings
USD 1.45 calibration and USD 1.35 heldout (USD 2.80 total). Free-tier
public content may be used by Google to improve its products. Actual fees
for prior failed calls are unknown. No private lecture, PDF bytes, identity,
history, labels or application database data are in the request; it returns
only issued page IDs and two Boolean judgments per page. `store=false` and
low thinking remain pinned.

Only the new public runner's one-use authorization ID, live-envelope fence
and split ceilings changed after that approval. Its response wire, parser,
selection, 66-group calibration packet and scorer stayed byte-identical to
the prior candidate; the request body manifest SHA is
`fd4421940eb613523d126138e6453e4e4e731bf14af1ae03b908b783fb75e6ed`.
The isolated keyless launcher preflight returned `approval_preflight_passed`
for the SHA-bound calibration receipt
`f822e1ddeaaaa578efdf7699929d5d19e04f5090ec4e73815938da84ca8743d6`;
the largest REST body was 6,340 bytes. It read the one required credential
without printing its value and made no HTTP request. The separate new
one-use ledger has not yet been consumed at this record. Heldout data has
not been opened. After updating the old dormant-flag test to exercise its
fail-closed branch explicitly, 85 focused public/scorer/bridge tests passed.

## Work and checks in this continuation

- Updated Lane 6 and ADR-024 to record the approved model-only comparison,
  stop rule and unchanged release fence. No checklist box was closed.
- `frontend` `npm run check` passed: type checks, lint, six Node unit tests,
  65 Vitest component tests, production build and Chromium 83 passed with
  one configured skip. This verifies the present Ask-off frontend build, not
  the still-unselected stronger-model runtime or spoken AT release check.
- Independent read-only review of the private v4 scorer found three offline
  measurement gaps: no required gold-to-slate bridge admission, ordinary
  duplicate-key-permissive JSON parse, and no top-one usefulness numerator.
  A bounded correction is in progress; the fresh private holdout remains
  unscored. No private content, database or provider was read by that audit.
- `python scripts/check_context.py` passed (37 required files, 79 active
  guides, 1,625 local links) and `git -c core.safecrlf=false diff --check`
  passed. Read-only Compose status showed all eight local services running
  healthy; this is not an Ask quality or provider-success result.

The populated volume, root `.env`, original PDFs, published Knowledge,
previous pilot ledger and sealed heldout were preserved. No Gemini request,
new index, database write or Ask activation occurred in this work.
