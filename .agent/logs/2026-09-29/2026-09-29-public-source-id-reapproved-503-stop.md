# Reapproved public source-ID calibration: HTTP 503 stop

Date: 2026-09-29 (America/Chicago). This is a separate, explicitly approved
public-only pilot after the earlier one-request stop. The two pinned CC BY 4.0
PDFs, frozen 96 labels, split, candidate construction, prompt/schema and scorer
fingerprint `7268dee7258cbb13f7b002edb32813dedbff83c9634f97bb46e67b16b3f46f64`
were unchanged. The earlier request's actual cost remains unknown.

## Approval and preparation

The owner approved `gemini-3.8-flash:generateContent` with `thinkingLevel=low`,
`store=false`, public current question and four public page/cue candidates only,
and source IDs only in the result. The envelope allowed at most 48 calibration
requests and, only after passing its gate, 48 heldout requests; no retry,
at least six seconds between starts, 30 seconds per call, 90 minutes total,
8,192 input and 1,024 output tokens per call, 786,432/98,304 tokens total,
and a conservative USD 2.00 cap at USD 1.50/7.50 per million input/output
tokens. No private Knowledge, chat history, answer generation, DB write or Ask
activation was authorized.

The runner's new authorization identity and canonical receipt use a separate
one-shot ledger from the consumed first pilot. Frozen calibration was prepared
in owner Temp with 48 callable rows and zero clarification rows. Its prepare
receipt SHA-256 is `32d19ca7e5462904f4a15be122508e02b62a071b4309aa63d980d2490fccdf3d`;
the new approval receipt SHA-256 is `06b1d6848d4a02dc61d2f8163a77ba7f48a26b0249caf5ca25bef50fed9db9f3`.
A keyless identity/approval preflight passed, and focused caller tests passed
12/12 before egress.

## One physical request and stop

The newly authorized run made exactly **one** physical request. The provider
returned **HTTP 503**. The one-shot runner stopped immediately as
`provider_http_error` with `stopped_no_retry`, `attempts=1`, known accounted
cost 0 and **failed-attempt cost unknown**. It did not read, print or retain
the provider error body. The distinct global approval/run/call claims and
failure receipt remain in owner Temp to prevent accidental replay. No response
IDs or usage receipts were produced; calibration and heldout have no score.
The earlier pilot also consumed one request with unknown status/cost, so actual
cost across both failed attempts is unknown.

This HTTP 503 is an availability observation, not a source-judgment quality
result. Do not rerun the consumed authorization or open heldout. A further paid
attempt needs a new exact approval and must include both unknown failed-call
costs. Retained Knowledge, PDF archives, populated volume and root `.env` were
unchanged. Ask remains disabled and Lane 6 stays 3/7.
