# Lane 6 frontend PDF full-check stability

Date: 2026-09-28. Scope: investigate five failures in the full Chromium stage
of `npm run check` on `main` at `6c02d6c`, preserving all pre-existing work.
The source-only Ask switch stayed off; no provider, database, retained PDF or
root configuration was touched. The Browser plugin was unavailable in this
session, so the repository's existing Playwright workflow was used.

The flow under test was: authenticated student reference or instructor PDF
attachment → open/navigate the original PDF or recover safely → show the
authorized page/text, keyboard control and exact attachment state.

The initial complete check passed typechecks, lint, six Node units, 59
component tests/coverage and build, then failed five of 80 regular Chromium
cases while running eight workers (75 passed, one opt-in live reset skipped).
Failure snapshots for the four Ask-PDF cases showed the dialog still loading
before the lazy PDF.js worker completed; a separate attachment case was still
loading account state after reload. The same ten PDF/attachment cases passed
with two workers, without changing product code or assertion timeouts. This
supports a test-runner resource/concurrency cause for these observed failures;
it does not prove every future environment is free of scheduling issues.

Set `frontend/playwright.config.ts` to two Chromium workers while retaining
full parallel test scheduling and every existing assertion, coverage and bundle
threshold. Reran the complete `npm run check`: typecheck, E2E/component
typecheck, lint, six Node units, 59 component tests, coverage, production build
and **80/80 regular Chromium cases passed** in 1.9 minutes. One live
password-reset browser case remained intentionally skipped because its separate
opt-in was not provided. No browser screenshot is claimed as a manual
assistive-technology review; the full check remains distinct from retained
user-PDF source usefulness, spoken NVDA/Narrator and hosted release gates.
