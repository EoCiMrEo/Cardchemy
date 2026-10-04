# Original-PDF early-close browser test stabilization

Date: 2026-09-29 (America/Chicago). Scope: the timing-sensitive PDF.js
text-stream cancellation regression test after the original-PDF viewer fix.
The populated local stack, original PDFs, root `.env`, backups and Ask release
fence were preserved. No provider call, database write or PDF-byte change was
made for this check.

## Observation and narrow test change

The existing synthetic dense-text Chromium test closes the viewer only after
the first nonempty PDF.js text chunk and asserts that cancellation passes the
content-free `pdf_viewer_closed` `Error`. Before the test adjustment, 20
parallel repeats produced 19 passes and one failure: the five-second default
poll expired **before the first text chunk**. The failure screenshot still
showed the original-PDF loading state. That iteration did not reach the
cancellation or final console-error assertion, so it is not evidence of a
PDF stream error or a successful cancellation. Ten serial repeats then passed.

`frontend/e2e/original-pdf.spec.ts` now allows 15 seconds for this initial
text-chunk observation, matching the existing PDF readiness waits elsewhere
in the file. The cancellation reason and no-stream-error assertions remain
unchanged. No viewer runtime code was altered for this stabilization.

## Verification and limit

- The adjusted early-close test passed **20/20 parallel repeats**.
- Full `frontend npm run check` passed its type, lint, unit, component,
  coverage and build gates; Chromium was **82 passed, one separately opt-in
  case skipped**. These post-adjustment results were supplied by the root
  Lane 6 run; this log does not claim a second independent execution.
- The exercised successful cancellations did not reproduce the
  `ReadableStreamDefaultController` browser error. The original-PDF release
  race is bounded by these synthetic schedules and the separately recorded
  authenticated Week 2–4 browser observations; neither is proof that every
  possible timing schedule is error-free.

Ask remains disabled pending the independent source-usefulness and release
gates. No Lane 6 checklist status changes solely from this test adjustment.
