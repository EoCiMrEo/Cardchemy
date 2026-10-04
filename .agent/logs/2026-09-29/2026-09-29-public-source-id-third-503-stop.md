# Third approved public source-ID pilot: HTTP 503 stop

Date: 2026-09-29 (America/Chicago). This record supersedes the two-attempt
status in the earlier public pilot stop log. The operator separately approved
one new public-only pilot with the same frozen two CC BY 4.0 PDFs, 96 reviewed
labels, 48 calibration and conditionally 48 heldout groups, current public
question plus four public page/cue candidates, and ID-only output. The approved
endpoint/model remained `gemini-3.8-flash:generateContent` with low thinking
and `store=false`; no private Knowledge or chat history was authorized. The
per-call, total-token, 30-second, 90-minute, six-second spacing and USD 2.00
new-spend guards were unchanged. The actual costs of the two earlier failed
requests were already unknown and were disclosed before this approval.

The third authorization identity is
`2026-09-29-public-source-id-pilot-reapproval-2`. The prepared calibration
receipt remained SHA-256
`32d19ca7e5462904f4a15be122508e02b62a071b4309aa63d980d2490fccdf3d`;
the new canonical approval receipt was SHA-256
`c1bd22a13a1e39eb68ccdd6db01bfccd08777758077f8d5b3bd4f8e2e89bc81a`.
The first receipt construction omitted the canonical trailing newline and was
rejected by keyless preflight before any provider call; a new canonical file
passed the exact approval and frozen-packet validation. Focused caller tests
passed 12/12.

The one-shot runner then made exactly **one** physical request. The response
status was **HTTP 503**. It stopped immediately without retry or response
content retention. Its durable failure receipt records `attempts=1`,
`provider_http_error`, `stopped_no_retry`, known accounted cost 0, and actual
failed-attempt cost **unknown**. Calibration and heldout have no model scores;
heldout was not opened. Across the three separately approved attempts, three
physical requests were made, none produced an accepted ID result, and all
three actual failed-request costs remain unknown. The distinct approval/run/
call claims in owner Temp are retained to prevent replay.

This is an availability/transport observation, not a quality result. Google's
[model reference](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash)
lists the model and low thinking; its
[API error guide](https://ai.google.dev/gemini-api/docs/api-errors) classifies
503 as service unavailable. A numeric status alone does not prove whether
the failure arose at Google's serving tier or an intermediary. The runner
does not retain response headers or error bodies, so root cause remains
unproven. Do not tune the source selector or count a quality failure from
these calls. No more paid calls are authorized under the consumed receipt;
any diagnostic or alternate-model pilot requires a fresh exact envelope.

The retained database, root `.env`, populated volume, three original PDFs and
backup were unchanged. Ask remains disabled, its release fence closed, and
Lane 6 remains **3/7** pending independent useful-page and release gates.
