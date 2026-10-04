# Approved augmented public source-ID pilot: preflight

Date: 2026-09-30 (America/Chicago). Checkout `main` at `6c02d6c`;
the pre-existing working tree and retained populated installation were preserved.
This is **pre-inference** evidence. Ask remains disabled and Lane 6 is 3/7.

## Operator decision and exact boundary

After the 126-group public packet was independently reviewed and frozen, the
operator approved one synchronous public pilot: 66 calibration requests and,
only after a complete calibration pass, 60 different-PDF heldout requests.
The endpoint is
`https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`,
with `gemini-3.5-flash-lite`, low thinking, `store=false`, and 0–3 issued page
IDs as output. Each input contains only the current authored public question
and four bounded page/cue windows from two of eight hash-verified CC BY 4.0
PDFs. No private Knowledge, account identity, history, labels, source paths or
PDF bytes may be sent. The pilot writes no application DB records and cannot
enable Ask.

The operator approved at most 126 physical POSTs, zero retries, starts at
least 20 seconds apart, at most 30 seconds per call, 60 minutes per split and
120 minutes wall time from the calibration start. Each call is limited to
8,192 input and 1,024 output tokens (including thinking); the combined ceiling
is 1,032,192 input and 129,024 output tokens. The guard uses the
[official Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing):
USD 0.30 input / 2.50 output per million tokens, capped at USD 0.34 for
calibration and USD 0.31 for heldout, USD 0.65 new total. Free-tier use may
be unbilled, and Google's posted terms permit public Free-tier content to be
used to improve products. Actual costs of earlier failed attempts remain
unknown. This approval does not authorize private transfer, a runtime policy
change, or Ask activation.

## Safety corrections before using the approval

An independent read-only audit identified three live-run gaps; all were
corrected before any provider call:

1. Heldout now requires the saved passing calibration score **and** its exact
   approved receipt, persistent split/attempt claims, matching completion and
   evaluation hashes. A copied or edited local score alone cannot open heldout.
2. Heldout waits a full 20 seconds before its first request, including after
   a process restart. A persisted calibration start time also enforces the
   approved 120-minute wall-clock envelope across both invocations.
3. The native pilot caller reads only a process-injected source-judge key. The
   separate launcher checks the exact packet/approval without a key first,
   then injects only that credential from the root `.env` into a minimal child.
   It logs neither the key nor unrelated environment values.

The first launcher preflight stopped locally because the PDF parser's known
`Ignoring wrong pointing object` warnings preceded its safe JSON result.
The launcher now accepts only that exact bounded warning form before the
expected missing-key code. It continues to reject any other diagnostic.
No provider request or one-use attempt claim was made by that preflight.

## Frozen, keyless proof

- Freeze: `c8b97e3851f081c40108d6f6a40b9bb675dc3b824329d4fc7f047480425017b1`.
- Calibration packet: `cd7c6aefdda0b6f33e75a5e499c7eef42b9cc1797c414e17c742d5bde5ac8965`.
- REST body manifest: `f0b1e14f0665d280551a3b4887978a1e017a339eb202e57413698ceb96fab2b3`.
- Pinned caller: `0154cdc2499758352abd5cc0ff0574ddf7b7293105b997f49caa59ddaa59502f`.
- Single-credential launcher: `6278a3d798e2d7ddfc574f5f671cae06bd1790085c54d696371b97310dea49ec`.
- Scorer: `9e4654b0a14e2a7854765265bd994c566ee1756db52f2a47648ec3ba8186c7ec`.
- One-use calibration approval receipt in OS Temp:
  `cardchemy-fresh-public-v2-approved-26vwdx_s/calibration-approval.json`,
  SHA-256 `70a577ac506a41fb256048f355447de34ae351899194006062b138dc8523e127`.
  The receipt binds the frozen files, all six caller/source code hashes,
  approved model, request manifest, prices and limits. It contains no key.
- The current caller independently rechecked all eight public PDF hashes,
  excluded overlap pages and all 66 exact request wires. Its maximum REST
  body was 6,103 bytes. The isolated launcher completed approval preflight
  with **zero provider calls** and no one-use claim.
- Focused original/augmented review, freeze, scorer, caller and launcher
  checks: **96/96 passed**. Context validation passed 37 required files,
  79 active guides and 1,604 local links. `git diff --check` passed.

The next step is the approved **single** calibration execution. A failure
consumes its physical claim and counts as a miss; at most two transient failed
groups are scorable. Any other failure or a third transient stops the split
without retry. Heldout remains sealed unless all calibration gates pass.
