# Public heldout manual-Q033 and remaining27 proposal

## Evidence and narrow purpose

[V4 stopped](2026-10-02-public-heldout-v4-terminal-result.md) after the new
Q033 invalid verdict made availability unreachable. Twenty-seven questions
are untouched. The proposed distinct v5 trial keeps the same wire, questions,
PDFs, labels, strict parser acceptance and scorer. It carries thirty valid
responses and both Q013/Q014 failures into sixty unique scored questions.
One manual new Q033 attempt requires new explicit authorization. Q033's failed
attempt, usage and cost remain in immutable history alongside all thirty-six
physical attempts. No old trial is resumed or retrospectively passed.

## Concrete inert preparation

[Caller](../../../scripts/run_visual_public_heldout_v5.py) and
[launcher](../../../scripts/launch_visual_public_heldout_v5.py) currently have
`LIVE_AUTHORIZED=False` and a pending exact-envelope marker. Their invented
[tests](../../../backend/tests/test_visual_public_heldout_v5_caller.py) verify
the 28-request roster, retained 33 historical outcomes, 32 active checkpoint
outcomes, sixty-question scorer and maximum 64 historical physical attempts.
They also cover failure/spacing/cost/claim/resource/credential fences, unchanged
strict parser acceptance and finite content-free verdict failure codes.

Independent inspection identified a last-response reporting edge: a failure
on Q060 had no following loop iteration to mark the run stopped. The new v5
finalizer now checks the complete score and reports `stopped` if it fails;
historical callers remain unchanged. A regression covers final-call failure.
The combined new caller/provider/preparation/current-worker offline run passed
**73 tests**. Actual frozen public checkpoint keyless preflight passed with
zero provider calls, exact 28 requests, preserved history and reachable gates.
The independent agent's review was interrupted by account quota; its initial
findings and authored tests are retained, but no completed final review is
claimed. Full backend/PG checks continue independently.

## Proposed provider envelope — pending human approval

- One new trial: manual Q033 plus untouched Q034–Q060, **28 POST maximum**.
- Endpoint `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`;
  `gemini-3.5-flash-lite`, HIGH thinking, `store=false`.
- Only current public question and text/up to four bounded PNGs from the four
  frozen CC BY 4.0 PDFs; return issued IDs/categories only. No answer output.
- Zero automatic retries; at least thirty seconds between calls, 120 seconds
  per call, 150 minutes total, four CPU/two GiB hard resource fence.
- At most 32,768 input/4,096 thinking-inclusive output tokens per call;
  917,504 input/114,688 output total. Each image <=1,600 px/2 MP/1 MiB;
  request <=6 MiB, HTTP response <=64 KiB, final verdict <=2 KiB.
- Frozen guard USD0.30 input/USD2.50 output per million tokens; reservation
  USD0.561988, new cap **USD0.60**. Frozen Free-tier price is zero; public input
  may be used for provider product improvement. Known earlier public guard
  USD0.595668 and all unknown old costs remain separate, not invoices.
- Any new failed outcome makes the preserved availability gate unreachable;
  stop without calling it again. Other quality/budget gates remain unchanged.
- No private Knowledge/history/identity/gold labels/PDF bytes, database write,
  additional embedding, runtime change or Ask enablement.

Standing implementation authority covers this preparation and aligned plan
record only. **No fresh live execution is authorized yet.** New exact human
approval, updated code/approval SHA freeze and final keyless preflight must
precede provider execution. Ask remains disabled; Lane 6 remains **3/7**.
