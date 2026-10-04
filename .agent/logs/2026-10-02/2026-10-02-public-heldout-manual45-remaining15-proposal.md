# Inert public successor: manual Q045 and fifteen untouched cases

## Concrete proposal

The [approved 23-call trial](2026-10-02-public-heldout-v7-terminal-result.md)
stopped at Q045 HTTP 503. Preserve all 45 evaluated outcomes and 51 physical
requests, including every prior failed attempt. A distinct future scope would
manually reattempt only Q045 once and run Q046–Q060 once: **16 POST maximum**.
Keep Q013/Q014 as failed cases, so one new failure makes the unchanged 58/60
availability gate unreachable. Do not clear any consumed execution ledger.

Use the same frozen public four-PDF heldout and issued-ID classifier, native
`https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`,
Gemini 3.5 Flash-Lite, HIGH, `store=false`. Send only current public question,
exact text and at most four bounded original-page PNGs; receive ID/categories,
never an answer. Zero retry, >=30 seconds between starts, <=120 seconds/call,
<=150 minutes total, four CPU/two GiB hard kill-tree supervision. Each call
<=32,768 input and <=4,096 thinking-inclusive output; total <=524,288/65,536.
Each PNG <=1,600px/two MP/one MiB; request <=six MiB, HTTP <=64 KiB,
verdict <=two KiB. Frozen guard USD0.30/2.50 per million input/output tokens;
new cap **USD0.35**, maximum reservation USD0.321136. Frozen Free tier is USD0
and public inputs may improve provider products. Previous known public guard
cost USD0.663937 remains separate; eight heldout charges and older failures
remain unknown.

No private Knowledge/history/identity/label/PDF-byte transfer, embedding,
database write or runtime enablement is part of this proposal. Do not execute
before a fresh exact provider approval.

## Prepared result

Separate `run_visual_public_heldout_v8.py`, `launch_visual_public_heldout_v8.py`
and `public_trial_process_identity_v2.py` preserve every consumed file. The
extended identity proof adds v7's immutable stopped resource/claim bindings;
unknown or original live process identities still refuse. Local metadata and
all source, quality and provider budgets remain bounded. The historical
seven-stage admission chain is rechecked before the proposed new roster.

**41 mocked contracts passed** with disabled injected authority. Real keyless
preflight passed: zero calls, exactly 16 new requests, 45 historical evaluated
outcomes, 51 historical physical requests, two inherited active failures and
reachable unchanged quality gates after the single prospective manual attempt.
`LIVE_AUTHORIZED=false`; no key, provider execution claim or call was used.
Ask remains off; no release or quality pass is claimed.
