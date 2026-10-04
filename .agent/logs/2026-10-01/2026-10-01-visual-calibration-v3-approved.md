# One checkpoint-bound public continuation approved

Date: 2026-10-01 (America/Chicago).

The operator answered `call_JhHkP71DY6BVPWwf2pr5oRay`:
“Duyệt đúng lượt 63 câu trong giới hạn này”. This authorizes exactly the
63 remaining calibration requests in the
[prepared envelope](2026-10-01-visual-calibration-v3-offline-preparation.md),
not replay of the four prior successful groups, heldout, private transfer,
database writes or Ask activation.

Endpoint: POST
`https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`;
model `gemini-3.5-flash-lite`, HIGH thinking, `store=false`. Only current
public questions, exact text/cues and four bounded page PNGs from the fixed
four public CC BY 4.0 PDFs; only issued source IDs and closed classifications
are accepted. No generated answer, retry, embedding, File API or countTokens.

At most 63 POSTs, 20-second minimum spacing, 30 seconds each, 90 minutes
total, four CPUs/two GiB. Per call at most 32,768 input tokens including
images and 2,048 output including thinking; aggregate 2,064,384/129,024.
Four PNGs at most 1,600 pixels/2 MP/1 MiB each, 6 MiB request, 64 KiB
HTTP response and 2 KiB final verdict. Paid guard USD 0.30/2.50 per million
input/output tokens, new cap USD **0.95**. Free tier is listed free with
public-data product-improvement use; old USD 0.020718 guard cost is separate
and prior failed-request actual costs remain uncertain.

All 67 groups and tri-state labels remain; 80% all-displayed usefulness,
45/54 and 15/18 hit thresholds, 65/67 availability and all 12 valid clear
empty no-match gates are enforced. Stop if gates become unreachable or
limits are exceeded. Independent private/different-PDF release is not
established by calibration.

After binding the new reply and before execution, 75 synthetic
caller/scorer/supervisor tests passed. The prior keyless actual-public
preflight passed, with four inherited receipts and zero provider requests.
Final immutable executable/approval SHA and the same execution-environment
preflight must precede the one resource-fenced worker. Root `.env`, populated
data, original private PDFs, backups and old frozen v2 ledgers remain intact.
Lane 6 remains 3/7; Ask disabled.
