# Approved offline per-page verdict decision recorded

Date: 2026-09-30 (America/Chicago). Scope: Lane 6 documentation only.
Checkout `main` at `6c02d6c`; the substantial pre-existing working tree,
retained populated volume, original PDFs and root `.env` were preserved.

## Starting evidence and approval

The separately approved 66-case public Flash-Lite calibration had 66 valid
responses but failed the zero-false-display, two/three-page cardinality and
four-useful overflow gates. Its 60 different-PDF heldout was not opened.
The [aggregate result](2026-09-30-augmented-public-calibration-result.md)
contains the exact numerators and denominators. The operator approved the
[per-page recommendation](2026-09-30-per-page-source-verdict-recommendation.md)
for a Lane 6/ADR-024 update and an **offline/keyless prototype only**. No new
endpoint/model/call/token/time/cost envelope or private Knowledge transfer
was approved by this decision.

## Documentation change

- [Lane 6](../../../docs/development/PRODUCT-QUALITY-REMEDIATION-PLAN.md)
  and [ADR-024](../../../docs/decisions/ADR-024-gemini-source-id-judge.md)
  now record the failed calibration, the sealed heldout and a prospective
  four-ID structured verdict: `useful_reading_page` plus
  `requested_relation_present` per issued page, with strict local 0–3
  selection and no answer text.
- [Current state](../../../docs/development/CURRENT-STATE.md) and
  [roadmap](../../../ROADMAP.md), plus the
  [decision index](../../../docs/decisions/ADR-000-INDEX.md), reflect that
  this is a hypothesis, not a passing public score, new runtime policy or
  Ask activation.
- Every existing availability, no-match, useful-hit, cardinality, 2/2
  overflow, at-least-90%-of-all-displayed, access and release gate remains.
  The 66 exposed cases are development data; the 60 independent heldout
  cases remain sealed until a separately frozen candidate passes calibration.

This change added no provider call, source code, migration, database write or
Ask admission. The four open Lane 6 checklist items remain open; Ask remains
disabled. The parent task owns the approved prototype and any future
separately authorized pilot.

## Verification

`python scripts/check_context.py` passed: 37 required files, 79 active guides
and 1,615 local links validated at the documentation update. `git diff --check`
exited 0; a targeted trailing-whitespace scan found none. The
diff checker emitted pre-existing Windows line-ending conversion warnings.
No backend/frontend/provider test was run for this documentation-only change.
