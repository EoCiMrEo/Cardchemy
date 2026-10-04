# Approved public Gemini 3.6 source-ID transport diagnostic

Date: 2026-09-29 (America/Chicago). Scope: the operator explicitly approved
one two-request, public-PDF-only diagnostic after three separately approved
Gemini 3.8 Flash pilots stopped without a quality score. The actual cost of
those three failed requests remains unknown. This diagnostic is **not** a
calibration, heldout evaluation, private-Knowledge transfer or Ask activation.

## Preparation and boundary

The fixed two-PDF blind packet matched SHA-256
`7ec9a83245fd432ff9f19047d1aa5aab1835a0bc9fdab04d9807d87787d19ae7`.
The keyless preflight rebuilt the public control and first frozen four-page
calibration request from that packet and matched both pinned body hashes; the
canonical REST bodies were 1,827 and 6,162 bytes. The approval receipt for
`gemini-3.6-flash:generateContent` matched the operator's exact endpoint,
model, low thinking, `store=false`, maximum two calls, zero retries, at least
six seconds between starts, 8,192/1,024 tokens per call, 16,384/2,048 total,
30 seconds per call, 120 seconds overall and USD 0.04 new-spend guard. The
receipt SHA-256 was
`d92488e56e23b0726bde067c2418446a4870215e59806205076ec4666b576585`.
The script and receipt were never used for private lectures or database writes.

An initial launch stopped with `PermissionError` **before a run claim or
provider request** because the elevated process could not read the Temp
receipt and write the output directory created by a different local identity.
A content-free ACL probe identified those two paths; the public packet and
fixed one-shot ledger were accessible. A new identical-hash receipt and empty
output directory were prepared under the executing identity, then the same
authorization was run once. The abandoned first directory has no run or call
claim. No response text or selected IDs were stored.

## Observed execution

The second launch consumed the one-shot approval claim and made exactly two
physical requests, with no retry. Control: HTTP 200, 10,761 ms, 312 input
tokens and 21 output tokens, strict source-ID/usage validation passed. The
frozen four-page request: HTTP 200, 1,784 ms, 1,404 input tokens and 212
output tokens, strict source-ID/usage validation passed. Total reported usage
was 1,716 input and 233 output tokens; the conservative guard calculation is
4,322 micro-USD (USD 0.004322). Both responses stayed inside the approved
call, token, time and cost bounds. The fixed claim prevents replay.

This establishes that the exact public source-ID request format can receive a
valid response from Gemini 3.6 Flash in this local environment. The runner
deliberately discarded selected IDs, so **no source-usefulness, no-match,
calibration or holdout score exists**. It does not explain the two earlier
Gemini 3.8 HTTP 503 responses. A scored public pilot needs a fresh exact paid
AI envelope. Ask remained disabled and the populated volume, root `.env`,
published Knowledge and original PDFs were unchanged.

## Checks

- Focused keyless diagnostic contracts: 10 passed.
- Exact public packet/body/receipt preflight: passed.
- Live diagnostic: two validated HTTP 200 requests under the explicit envelope;
  no quality gate was scored.
