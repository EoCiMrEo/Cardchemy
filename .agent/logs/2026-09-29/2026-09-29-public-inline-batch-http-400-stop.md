# Approved public inline Batch pilot stopped at HTTP 400

Date: 2026-09-29 (America/Chicago). Branch `main`, starting HEAD
`6c02d6c`. The owner separately approved the exact public-only Batch
envelope in [the approval record](2026-09-29-approved-public-inline-batch-envelope.md).
The populated local database, original PDFs, root `.env`, earlier ledgers and
Ask-off runtime fence were preserved. No private Knowledge, history, identity,
labels or PDF bytes were submitted.

## Preflight and one physical attempt

The frozen Batch runner SHA-256 was
`71b82d9f9d5aedefafd9f42e297888894e721da9e9a00626781f39d0177d0589`;
the exact canonical approval receipt SHA-256 was
`c9087a9ff82ffc3822dd449b19cf86b0730146018b9444515ba357e435e7d7aa`.
The public prior-ledger checkpoint SHA-256 was
`5c39c622444e1df5a547e36cb00cf8e91cea81d83ad4ee0fa1a2f09681fffb73`.
The credential-free, network-free preflight passed both normally and under
the permitted network command identity. It admitted 45 unresolved calibration
items and a conditional 48-item heldout, with zero calls.

The first launch stopped **before creating any claim, output directory or
provider request**. A no-network diagnostic under the same permitted process
identified `PermissionError` when reading the approval receipt created by a
different OS security context. A new OS-Temp receipt was made under the
permitted process; its bytes and SHA were identical. A second no-network
admission confirmed the global claim and output were absent. This did not
consume the provider authorization.

The subsequent **single physical Batch creation POST** wrote its exclusive
approval/pilot/create claims and received **HTTP 400**. It produced no known
Batch name or usage receipt. The approval is now consumed: no POST replay,
item retry, status GET or heldout creation followed. Exactly three older
public synchronous ID receipts remain; the 45 new items have no accepted
result, so the 48-case calibration and independent heldout have **no quality
score**. The maximum reservation for this 45-item creation is USD 0.449280
at the approved conservative guard; the actual charge is unknown and that
reservation is not an invoice. The payload error body was intentionally not
stored or printed because it might echo public excerpts; only numeric HTTP
status is known.

## Diagnosis and release boundary

The [official Batch REST contract](https://ai.google.dev/api/batch-api)
documents the inline wrapper and keyed item format used by the harness, and
the [Gemini 3.6 model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash)
lists Batch support. An offline comparison with the installed Gemini SDK's
request serializer found the same outer `batch.inputConfig.requests.requests`
shape and no required per-item model field. These facts do **not** identify
why this installation received HTTP 400: account eligibility, service-side
parameter admission and a particular item remain unconfirmed possibilities.
The 400 is a request-admission result, not evidence that source selection
fails or passes. No score, runtime model switch, database write or Ask
activation followed; Lane 6 remains **3/7** with its four quality/release
items open. A new paid diagnostic needs a fresh, narrower envelope and a
safe allowlisted error-category collector before any further request.

Before this run, 65 focused public-pilot tests and the exact keyless
preflight passed; `python scripts/check_context.py` passed 37 required files,
79 active guides and 1,529 local links. A separate disposable PostgreSQL
and journey check passed as recorded in the log index. No retained container
or volume was recreated for this pilot.
