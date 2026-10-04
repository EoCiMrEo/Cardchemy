# Flash-Lite public source-ID harness: keyless readiness

Date: 2026-09-29 (America/Chicago). Scope: complete the separate proposed
Gemini 3.5 Flash-Lite synchronous **public-only** evaluation harness. Starting
branch `main`, HEAD `6c02d6c`, with the broad existing Lane 6 working tree.
The owner chose to remain on Google AI Studio Free tier and to create a
separate source-judge API key. This work did not inspect or change that key or
the root `.env`.

## Changes and rationale

- The evaluator now admits heldout only when a complete calibration run has
  exactly 48 claimed physical attempts, ordered response-ID and usage receipts,
  a matching terminal result and one-shot score claim, and a recomputed
  **passing** calibration result. It compares the entire expected score
  receipt. A forged top-level `public_passed: true` over failing metrics no
  longer opens heldout.
- The caller validates the independently frozen label file and freeze receipt
  before either approval-aware admission or its separate credential-free
  preapproval check. The latter checks pinned public requests, writable Temp
  directories, unconsumed claims and serialized token admission without
  reading a provider key, approval receipt or making a request. It reports
  readiness for calibration only; heldout requires the later passing score.
  The exact
  approval-aware preflight remains a later distinct step.
- Offline tests now stage a complete synthetic 48-attempt run rather than
  treating an unclaimed score-looking JSON file as evidence. Negative cases
  remove a call claim, usage file or response file and forge a passing score
  flag; each is rejected before heldout or scoring can proceed. A keyless
  preapproval test verifies that no claim or credential is consumed.

## Verification and limits

- `backend/venv/Scripts/python.exe -m pytest` over the two Flash-Lite focused
  test files: **43 passed**.
- `git diff --check`: passed. Ruff was unavailable in the installed local
  backend venv (`No module named ruff`); no package was installed to change
  the environment.
- No exact frozen public packet was prepared or scored in this step. No
  provider HTTP request, private Knowledge transfer, database write, Ask
  activation, plan/ADR amendment or release-quality conclusion occurred.
  The harness still requires an exact fresh operator-approved endpoint,
  model, request, token, time and cost envelope before any live pilot. The
  dedicated judge key is currently being supplied by the owner; presence
  and actual Free-tier model availability remain unverified here.

Existing populated volumes, attached original PDFs, prior consumed pilot
ledgers, the root `.env` and the disabled source-only Ask policy remain intact.
