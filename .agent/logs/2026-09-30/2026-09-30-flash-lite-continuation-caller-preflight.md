# Flash-Lite public continuation caller and preapproval preflight

Date: 2026-09-30 (America/Chicago). Starting branch `main`, HEAD `6c02d6c`,
with broad in-progress Lane 6 changes preserved. Scope: complete the
evaluation-only HTTP adapter around the separately versioned
failure-inclusive public source-ID continuation. This entry does not approve
or execute a Gemini request.

The caller at
[`scripts/call_public_source_id_multipdf_35_lite_continuation_v1.py`](../../../scripts/call_public_source_id_multipdf_35_lite_continuation_v1.py)
supports a keyless `--preapproval-preflight`, an approval-aware zero-call
preflight and a separately acknowledged execution mode. The default
authorization identifier in the core remains pending. The future approval
receipt binds exact bytes of both the core and caller, plus the frozen
checkpoint and source-ID parser. No key is read before exact approval
admission. The HTTP adapter makes one POST per selected public group, has
no retry or redirect, limits decoded success bytes and discards provider
error bodies. The core owns the one-use claim, 20-second pacing,
90-second per-call and 180-minute total bounds, and complete calibration
before optional heldout. Group 11 is not in the continuation loop.

The real, keyless preapproval CLI was run against the existing public
checkpoint, old approval, frozen labels and public packet. It returned
`preapproval_preflight_passed`, `authorization_pending=true`, 48 frozen
calibration groups, 10 accepted prior groups, and group 11 uncertain.
The irreversible prior-display check found no false no-useful display among
the ten accepted groups. No new claim, output directory, API key read or
network request was created by this mode.

Verification: the combined focused synthetic suite for continuation core,
caller, old Flash-Lite caller and scorer passed **62/62**. The caller tests
use fake HTTP and cover bounded success/error bodies, no retry, approval
admission and execution flags. Repository context validation passed 37
required files, 79 guides and 1,564 local links; scoped diff whitespace
validation passed. `docs/TESTING.md` now records the keyless focused command
and keeps live execution outside routine testing. The independent browser PDF smoke and full frontend gate
are recorded in their own same-day logs.

This is readiness evidence only. The proposed future maximum is 37 new
calibration and 48 conditional heldout physical calls, no retry, at most
8,192 input/1,024 output tokens each, 696,320/87,040 tokens total,
20 seconds between call starts, 90 seconds/call, 180 minutes total and a
USD 0.50 new-cost guard at USD 0.30/2.50 per million input/output tokens.
Actual prior timeout and older failed-attempt costs remain unknown. The
owner must approve this exact new envelope before a new one-use receipt or
provider request. Private Knowledge, retained database, original PDF
attachments, root `.env` and Ask state were not changed. Ask remains
disabled; Lane 6 remains 3/7.
