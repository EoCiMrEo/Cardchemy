# Scored public Gemini 3.6 pilot stopped before a quality result

Date: 2026-09-29 (America/Chicago). The operator separately approved the
public-only eight-PDF Gemini 3.6 Flash scored pilot described in the
[approval record](2026-09-29-public-source-id-36-scored-pilot-approval.md).
The approved run allowed up to 48 calibration requests and, only after a
passing calibration score, up to 48 heldout requests. It had no retry, at
least six seconds between starts, 30 seconds per call, 90 minutes total,
8,192 input/1,024 output tokens per call, and a USD 2.00 conservative cap.
No private Knowledge transfer, Ask activation or database write was approved.

## Observation and likely cause

The calibration caller passed its frozen public packet and receipt preflight,
then consumed its exclusive approval/run claim and wrote `call-01.claim`.
It immediately recorded `stopped_no_retry` with
`provider_execution_uncertain`, `attempts=1`, known accounted cost zero and
failed-attempt cost unknown. Its response-ID and usage files are both zero
bytes. The call marker was created at 22:32:32.079 UTC and the failure
receipt at 22:32:32.173 UTC, about 94 ms later. There is no accepted result,
no calibration score and no heldout run. The consumed claims remain in Temp;
the same authorization must not be replayed.

The command was invoked in the default filesystem sandbox, which restricts
network access. The earlier separately approved two-request transport
diagnostic ran with elevated command permission and returned two valid
HTTP 200 responses. The immediate stop makes sandbox network denial the
leading explanation, but the old caller suppressed the exception class.
There is **no confirmed exception type or proof of whether a request reached
the provider**. The actual failed-attempt cost remains unknown. This is a
transport/invocation failure, not evidence for or against source-selection
quality.

## Diagnostic repair and future boundary

The dormant one-shot caller now maps known transport, proxy, timeout,
protocol and local permission errors to fixed content-free codes. Its failure
receipt records elapsed milliseconds since the call claim when available;
it never records exception messages, request/response bodies, credentials or
private lecture text. It still stops on the first failure and retains the
unknown-cost flag. Synthetic fake-transport checks cover exception text
redaction, a connection error after 125 ms, no retry, empty response/usage
files and durable claims.

A subsequent pilot would need a new exact live-cost authorization. Its
`--preflight-only` step should run with the same elevated command permission
as the eventual single paid launch to check Temp ACLs and the frozen receipt
without network or claim consumption. The paid launch itself must use that
approved permission. These checks cannot guarantee provider availability.
This source edit changes the caller SHA inside the pilot fingerprint, so the
old prepared receipt and approval cannot be reused; a future trial must
prepare and approve a fresh frozen fingerprint. The public source packet and
independent labels were not changed by this diagnostic repair.

## Verification and preservation

- Focused keyless caller/scorer suite: 35 passed from `backend`.
- Full backend offline suite after the safe telemetry change: 2,417 passed,
  151 skipped and two deselected in 260.39 seconds. Skipped/deselected cases
  do not establish live-provider or hosted-CI success.
- No additional provider call, private source transfer, database write or
  volume/root `.env` change occurred during diagnosis and repair.
- Ask remains disabled; Lane 6 remains 3/7 with the independent
  source-usefulness and release gates open.
