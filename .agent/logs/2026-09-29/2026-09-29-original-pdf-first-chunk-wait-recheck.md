# Original-PDF first-chunk browser recheck

Date: 2026-09-29 (America/Chicago). Scope: test reliability after the
[PDF.js cancellation fix](2026-09-29-original-pdf-stream-cancellation-fix.md).
The retained populated volume, three attached original PDFs, root `.env` and
Ask-disabled policy were preserved. This step made no provider request or
database write.

## Finding and change

The regression closes the viewer only after it observes a real PDF.js text
chunk, then checks cancellation and browser errors. In 20 parallel repeats
before this test-only change, 19 passed and one timed out while waiting for
the **first** chunk; no stream-controller error was observed on that attempt.
Ten repeats with one worker passed. The PDF worker and page decode compete
for resources under parallel browser tests. In
`frontend/e2e/original-pdf.spec.ts`, the first-chunk wait now permits 15
seconds; all later cancellation and error assertions are unchanged. This does
not alter runtime PDF behavior or weaken the stream-error verdict.

## Checks and limits

- The focused dense-text test passed 20/20 parallel repeats after the wait
  adjustment.
- Full `frontend npm run check` passed type/lint/unit/component/coverage/build
  and the browser suite: 82 passed, one separately opt-in live-reset case
  skipped.
- The authenticated current-image browser previously rendered and navigated
  pages 1 and 2 of all three attached Week 2/3/4 originals, with no observed
  errors. The repeated disposable test and those six actual pages cover the
  reported failure path but do not prove every possible PDF or schedule.

No Lane 6 quality/release checkbox was closed by this test stabilization.
