# Per-page source verdict: approved offline prototype

Date: 2026-09-30 (America/Chicago). Checkout `main` at `6c02d6c` with the
existing Lane 6 working tree preserved. The retained populated volume, three
encrypted original PDFs and root `.env` were not changed. Ask stays disabled
and Lane 6 stays **3/7**.

## Approval and scope

The operator approved the [per-page verdict recommendation](2026-09-30-per-page-source-verdict-recommendation.md)
for plan/ADR changes and a **keyless offline prototype only** after the prior
66-response calibration failed its no-match and multiple-page gates. That
approval did not authorize a new Gemini request, private Knowledge transfer,
runtime policy switch, indexing, DB write or Ask activation. The 60-group
different-PDF heldout remained unopened in this work.

## What changed

- `scripts/prototype_per_page_source_verdict_v3.py` builds a four-page,
  cue-first public request. It preserves the current question and issued
  exact page/cue data, asks for `useful_reading_page` and
  `requested_relation_present` booleans independently for every ID, and
  prohibits answer text. The parser requires exactly four distinct issued IDs,
  exact boolean types and no extra fields, then selects at most three IDs
  meeting both conditions in issued order. Malformed output fails rather than
  becoming a valid no-match.
- `scripts/score_fresh_public_per_page_verdict_v3.py` reuses the frozen 66/60
  public packets and inherited augmented quality ratios. A read-only
  independent audit found that the inherited calibration scorer reported
  exact one/two/three-page cardinality but did not gate it. The v3 scorer now
  enforces the already-approved 5/6 ratio in each of those calibration
  strata before the heldout can open, without rewriting the consumed v2
  scorer. It binds the new
  wire/parser/scorer hashes, counts errors as misses, and does not open heldout
  receipts unless the whole calibration gate passes. The consumed v2 caller,
  scorer and ledger were left intact.
- `backend/tests/test_per_page_source_verdict_public_prototype.py` and
  `backend/tests/test_score_fresh_public_per_page_verdict_v3.py` cover positive,
  empty, four-qualified, malformed, foreign, duplicate, partial-relation,
  availability, no-match, cardinality and sealed-heldout behavior.
- `scripts/run_fresh_public_per_page_verdict_v3.py` and
  `scripts/launch_fresh_public_per_page_verdict_v3.py` provide a dormant,
  one-use public-pilot scaffold. Both stop before reading a key or making a
  request while `LIVE_ENVELOPE_APPROVED` is false. The caller binds the exact
  frozen packet, public PDF manifest, code hashes and a separate attempt
  ledger; each physical attempt requires an exclusive claim. A response with
  invalid verdict fields fails rather than becoming a no-match. Validated
  provider token usage from a malformed HTTP 200 candidate or finish is
  counted in the terminal cost record. No earlier pilot ledger is reused.
- `backend/tests/test_run_fresh_public_per_page_verdict_v3.py` covers the
  keyless guard, receipt/source binding, exclusive claims, bounded responses,
  failure accounting, and the isolated launcher. The launcher source is among
  the SHA-bound files, so changing how the credential enters the child
  invalidates the prepared receipt.
- `PROJECT-MAP.md` points to the new inert prototype and corrects the prior
  pilot's stale pending-score description. The separate
  [documentation decision](2026-09-30-per-page-verdict-doc-decision.md)
  records the approved Lane 6/ADR-024 change.

## Verification and limits

- 69 focused provider-free tests passed on the completed prototype/caller,
  including inherited baseline gates. The first test invocation in this
  session used a repository-relative interpreter path from the `backend`
  working directory and failed before collecting tests; the corrected
  `venv/Scripts/python.exe` invocation passed. This was a command-path
  mistake, not a product/test failure.
- A synthetic calibration with seven two-useful questions reduced to one
  useful page still had 54/54 positive hit and 100% displayed usefulness;
  the new v3 cardinality gate correctly rejected it and did not open the
  heldout. This closes a pre-request gate defect found during independent
  review. No frozen result or threshold was retroactively changed.
- The frozen **calibration-only** public packet produced 66/66 bounded v3
  wires, largest 8,007 bytes against the 8,192-byte wire cap. All 66 inert
  REST bodies passed the existing 12,288-byte guard; largest was 6,340 bytes.
  This made **zero** provider calls and did not read heldout labels/results.
- The current Google [structured-output reference](https://ai.google.dev/api/generate-content)
  lists boolean, enum, required, `additionalProperties`, `minItems` and
  `maxItems` among supported schema fields. This documents schema
  compatibility only; no model response to the new wire has been measured.
- `python scripts/check_context.py` passed with 37 required files, 79 active
  guides and 1,617 local links. `git -c core.safecrlf=false diff --check`
  also passed. No live provider, PostgreSQL, frontend or
  release gate is claimed from these checks. `ruff` is not installed in the
  local backend venv, so no Ruff result is claimed.
- A fresh authenticated in-app browser read showed the original PDF rendered
  for Week 2 pages 1–2, Week 3 page 1 and Week 4 page 1. The Ask panel showed
  its disabled status. Escape closed the PDF dialog and returned focus to its
  Week 4 trigger; Enter reopened the PDF page. At the 319-pixel browser width,
  document scroll width was also 319 pixels and the dialog width was about
  287 pixels, with no measured horizontal overflow. This is a narrow visual and
  keyboard smoke check, not the required
  spoken assistive-technology, private usefulness or authorization release
  evidence. Browser navigation was read-only.

The next possible public pilot requires a **new exact** endpoint/model/price/
call/token/time/cost approval and a separately frozen one-use harness. A public
pass would still leave private-source, runtime-wire and final release gates.
