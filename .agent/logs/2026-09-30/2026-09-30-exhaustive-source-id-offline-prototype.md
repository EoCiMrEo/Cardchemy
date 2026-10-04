# Inactive exhaustive source-ID prototype

Date: 2026-09-30 (America/Chicago). Starting checkout: `main` at `6c02d6c`.
The owner approved updating Lane 6/ADR-024 and preparing an offline prototype
after the public Flash-Lite calibration failed its no-useful-source gate.
Pre-existing Lane 6 changes, the populated database volume, root `.env`,
attached original PDFs, sealed heldout and disabled Ask gate were preserved.

`scripts/prototype_exhaustive_source_id_v2.py` is a pure request builder with
no CLI, network client, credential reader, database import or output scorer.
It reuses the current source-ID candidate and response-schema validator,
requires exactly four issued public candidates, puts each visible cue before
its page text, and states the entity/relation/condition and independent
page-plus-cue decision in a new versioned instruction. The only allowed
model output remains zero to three issued source IDs. It cannot generate an
answer, quote or citation. The current dormant v4 Ask prompt/model and all
persisted job policies remain unchanged.

The focused keyless tests passed: **6/6** cases for the wire allowlist, exact
cue/page fields, empty and three-ID parser outcomes, wrong candidate count,
noncontiguous cue, oversized page and duplicate/foreign/over-limit IDs. This
proves bounded construction and fail-closed parsing, not source usefulness or
model behavior. The public independent PDF corpus has not been assembled or
scored; no provider request or private Knowledge transfer occurred. The
previous one-use pilot approval is consumed. No quality checkbox or runtime
release claim changed.
