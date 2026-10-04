# Original-PDF text stream cancellation fix

Date: 2026-09-29 (America/Chicago). Scope: the owner's intermittent
"original PDF could not be displayed" complaint and a prior exact-byte
disposable replay that sometimes produced PDF.js stream-controller page errors.
Starting branch/HEAD: `main` / `6c02d6c`; the populated local stack, root
configuration, attached Week 2–4 PDFs and large in-progress working tree were
preserved. Ask remained disabled throughout.

## Root cause and change

The installed PDF.js `MessageHandler.sendWithStream` requires its stream
`cancel` reason to be an `Error` before it marks the worker-backed controller
closed. Both `OriginalPdfPage` teardown and bounded text truncation called
`reader.cancel()` without a reason and swallowed the resulting rejection.
In that state, a later worker enqueue can target an already closed browser
stream. This gives a concrete explanation for the observed timing-sensitive
`ReadableStreamDefaultController` error; it does not prove that every earlier
fallback had that cause.

Both cancellation sites now supply a content-free `Error` reason. The
published-lecture dialog also passes a stable access-change callback to the
PDF component. Previously an unrelated parent render changed that callback
identity, restarted the load effect, canceled an active PDF, and could leave
navigation disabled after its controller was aborted. No PDF bytes, credentials
or source text are logged by these changes.

The new synthetic Chromium regression closes the dialog only after a nonempty
PDF.js text-content chunk is actually returned to the page's reader. It
observes that the reader is canceled with the expected `Error` reason and
checks for browser page errors and stream-controller console errors after
teardown. The bounded-text unit case also asserts its cancellation reason.
This improves on the first transient-DOM-label test, which could close before
streaming began and was therefore not adequate evidence.

## Verification

- Focused dense-text early-close browser test: 1 passed.
- Original-PDF browser file: 10 passed, including authenticated ranges,
  navigation, revoked access, malformed/missing originals and in-flight close.
- Bounded-text component tests: 3 passed.
- Full `frontend npm run check`: six unit, 65 component, 82 Chromium passed;
  one separately opt-in live reset browser case skipped. Type, lint, coverage,
  build and bundle checks passed.
- Rebuilt and recreated **frontend only** on the retained development stack.
  Frontend `/healthz` returned HTTP 200; all eight long-running services were
  healthy and validated backend settings still reported Ask disabled.
- In a signed-in in-app browser on the new image, Week 2, Week 3 and Week 4
  original PDF pages 1 and 2 rendered and navigated. The three page-open,
  next-page and close sequences produced no observed browser errors. This
  live check covers those six pages and sequences; it is not a claim of zero
  possible races across every page or schedule.

No provider call, database migration/write, volume reset, PDF reattachment or
root `.env` edit occurred for this fix. The separate public source-ID
diagnostic is recorded in its own log.
