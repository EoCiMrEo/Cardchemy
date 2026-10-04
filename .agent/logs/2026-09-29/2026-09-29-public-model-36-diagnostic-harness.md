# Dormant public-only Gemini 3.6 source-ID diagnostic harness

Date: 2026-09-29 (America/Chicago). Scope: separate transport diagnostic after one
unknown-admission and one confirmed HTTP 503 public `gemini-3.8-flash` pilot
stop. This record is not a provider result or a new quality evaluation.

## Starting evidence and decision boundary

The first public call failed the old HTTP-200/8,192-byte admission without a
recorded status; its exact cause and cost are unknown. The later reapproved
call returned HTTP 503 and stopped after one physical request, with failed-call
cost unknown. Neither produced a calibration score. Official Gemini API docs
list `gemini-3.6-flash` as a stable model with structured output, and support
`thinkingLevel=low`. The USD 1.50 input / USD 7.50 output per million token
guard is conservative against the published introductory rate. An HTTP 503
indicates unavailable service or capacity in Google's documentation; it does
not establish source-ID quality or a malformed request.

Sources: [Gemini 3.6 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash),
[thinking levels](https://ai.google.dev/gemini-api/docs/thinking),
[pricing](https://ai.google.dev/gemini-api/docs/pricing), and
[API errors](https://ai.google.dev/gemini-api/docs/generate-content/api-errors).

## Implementation

Added `scripts/diagnose_public_source_id_36.py` and
`backend/tests/test_public_source_id_36_diagnostic.py`. The script has a
literal **pending approval** identity; it cannot execute a live call as
checked in. It reads only the hash-pinned two-PDF public packet in owner Temp,
rebuilds (1) a small synthetic control using one exact public cue, then (2)
the exact first frozen four-page calibration slate. It checks the packet and
both request-body hashes. The bodies are 1,827 and 6,162 canonical bytes.

An eventual call requires a separately approved, canonical, SHA-bound receipt
for the exact `gemini-3.6-flash:generateContent` endpoint and model, both body
hashes, two calls maximum, zero retries, 8,192/1,024 input/output tokens per
call, 16,384/2,048 total, 30 seconds/call, two minutes total, at least six
seconds between starts, and a USD 0.04 cap. Two worst-case calls reserve USD
0.039936. Previous failed-call costs must be acknowledged as unknown. The
fixed Temp ledger and per-call claims prohibit automatic replay. The second
call occurs only after the control returns HTTP 200 with a valid source-ID and
usage response. Each physical call is bounded by the lesser of 30 seconds and
the remaining two-minute global window; mandatory six-second spacing cannot
start when the global window would be exhausted. Results retain only numeric status, duration, byte count,
bounded numeric `Retry-After` when present, and token/cost usage plus safe
booleans. They never retain question/page text,
selected IDs, model response, key or error body. No database or Ask runtime
path is touched.

## Verification and limits

- Keyless frozen-packet reconstruction succeeded: exactly two bodies, 1,827
  and 6,162 canonical bytes.
- New and existing caller tests: **22 passed**. They cover approval placeholder
  and exact receipt, pinned source/hash, endpoint/body, six-second gap, HTTP
  503 stop, invalid ID/usage stop, second-call 503 accounting, strict global
  deadline at a late second call, no overshoot during mandatory spacing,
  content-free result and consumed one-shot claim.
- Python syntax and `scripts/check_context.py` passed (37 required files,
  79 active guides, 1,479 local links). No Gemini request, private Knowledge read,
  database write, release-gate score or Ask activation occurred.

This diagnostic would establish only transport/protocol availability under
its approved envelope. It cannot be scored as the 48-case calibration or
replace private original-PDF usefulness and release gates. A live run still
needs a fresh explicit operator approval and an approval identity replacing
the checked-in placeholder.

Subsequent status on 2026-09-29: a third separately approved 3.8 pilot also
stopped after one HTTP 503 response. Thus all three failed-attempt actual costs
are unknown. The dormant 3.6 harness made no request; its proposed envelope
must disclose all three prior uncertainties. See the
[third stop](2026-09-29-public-source-id-third-503-stop.md).
