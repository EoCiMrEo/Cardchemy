# Flash-Lite failure-inclusive continuation harness, offline only

Date: 2026-09-30 (America/Chicago). Starting branch `main`, HEAD `6c02d6c`.
Scope: implement a prospective, versioned public source-ID continuation after
the approved September 29 Flash-Lite timeout. The checkout already had broad
Lane 6 work, so this slice preserved the old runner, evaluator, consumed
approval, old Temp ledger, root configuration and application state.

## Decision and implementation

The owner chose to retain ten accepted Flash-Lite source-ID/usage receipts,
count the eleventh timed-out physical call as a failed case in the frozen
48-group calibration, and never replay it. The new
[`continue_public_source_id_multipdf_35_lite_v1.py`](../../../scripts/continue_public_source_id_multipdf_35_lite_v1.py)
checks the old runner/evaluator and every consumed checkpoint file by digest,
then validates the old receipt identities, issued IDs, usage totals and timeout
claim. A read-only check against the actual retained public files and frozen
labels returned 48 calibration groups, ten accepted pairs and group 11 sealed
as the uncertain timeout. Among those ten accepted groups, zero were negative;
17 cards were displayed, with zero weak cue-plus-page cards. Thus the
irreversible zero-false-display gate remains feasible. The admission now
rejects a preexisting false no-useful display before a new claim or request.
No old file was changed.

The prospective new authorization remains `PENDING_SEPARATE_OPERATOR_APPROVAL`.
The module has no live CLI, credential reader or HTTP client; its callable
transport is injected for offline tests. A distinct future approval receipt
must bind the new script hash, the exact separate HTTP-adapter file hash and
prior checkpoint, and a separate exclusive
claim prevents repeating that authorization. Before each prospective physical
attempt, a numbered claim is durable. Calibration would send only groups
12–48 (37 new calls); an independent 48-group public heldout could open only
after the complete failure-inclusive calibration passes. Group 11 cannot be
selected by the continuation loop.

The explicit proposed bounds are at most 85 new calls, zero retries, at least
20 seconds between starts, at most 90 seconds per call and 180 minutes total;
per-call input/output caps are 8,192/1,024 tokens and total caps are
696,320/87,040. The separate new-spend guard is USD 0.50 at USD 0.30/2.50
per million input/output tokens. The maximum all-call reservation is
USD 0.426530. The prior ten accepted calls have a known guard of USD
0.004363; the timed-out call and older failed calls have unknown actual cost.
These are proposed limits for a later exact user decision, not permission to
send requests.

Each frozen split keeps a full denominator of 48 and needs at least 46 valid
responses. A timeout, HTTP 408/502/503/504 or bounded network failure consumes
one group without retry and scores as a miss; the run continues only while
46/48 remains feasible. HTTP 429 stops to avoid repeated quota requests.
Other HTTP, schema, identity, output and budget failures stop. Completed
negative groups must return an empty selection; a failed negative group is
never credited as no-match. The existing positive-hit, top-one, count and
at-least-90%-of-**all-displayed** cue-plus-original-PDF-page gates are applied
on all 48 groups. Availability and source usefulness are reported separately.
No full public score was produced in this offline slice.

## Verification and limits

- `venv\\Scripts\\python.exe -m pytest -q tests/test_public_source_id_multipdf_35_lite_continuation.py tests/test_public_source_id_multipdf_35_lite_caller.py tests/test_public_source_id_multipdf_35_lite_score.py` from `backend`: **55 passed**. Fake transport covers group-11 non-replay, one-use claim, 46/48 availability, negative error versus no-match, displayed-card quality, quota stop, unreachable availability and heldout admission. Additional tests cover the irreversible prior-display preflight and exact future adapter hash binding.
- `venv\\Scripts\\python.exe -m py_compile` on the new script and test from `backend`: passed.
- Read-only hash recheck: prior runner `31089ce26658610ff7d5c95246897538140e75ee7e0a89d4bd838ce62c1344`; prior evaluator `8efec637cf54f35c45003e0b3cdf8f534ca01bab766e5a2eab0f0d11909d4ac5`; old response/usage/failure/group-11 claim digests still match their frozen values.
- New core script SHA-256: `0751e90e1a0ba720b520c41439303a8e633adb59761b8c5b404ef6ae903ad085`. New focused test SHA-256: `0ca3c20386217c56adc3b23e3cdad2b39f30f511b1ae34ded05aa24905432939`. The adapter hash is evaluated from the exact final file when a future approval receipt is constructed; no approval exists now.
- Optional `ruff` check was unavailable in the backend environment (`No module named ruff`); no package was installed. The focused tests and compilation above passed.

This was offline only: no Gemini request, key access, private lecture transfer,
heldout score, Ask activation, database migration, volume operation or root
`.env` update. The original Temp ledger was read, not modified. Test temporary
files were confined to pytest's disposable area. Public and private release
quality, provider availability on a full sample and spoken assistive-technology
checks remain unproven. The four open Lane 6 quality/release checklist items
stay open.
