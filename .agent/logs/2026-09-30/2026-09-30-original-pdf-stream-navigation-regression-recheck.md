# Original-PDF stream navigation regression recheck

Date: 2026-09-30 (America/Chicago). Scope: the timing-sensitive PDF.js text
stream during Next, close and reopen. Starting checkout: `main` at `6c02d6c`,
with a large in-progress working tree. The retained installation, original
PDFs, database, volumes and root `.env` were preserved.

The current untracked `frontend/e2e/original-pdf.spec.ts` already contained a
focused regression for this exact sequence before this recheck. It uses an
authored two-page PDF through mocked authenticated byte ranges and the real
PDF.js worker. The test waits for page 1 to render, selects Next, holds the
first page-2 text chunk inside the real stream reader, closes and reopens the
dialog, then releases the old read. It asserts an `Error` cancellation reason,
page-1 canvas/text in the new viewer, no stale page-2 text or safe-fallback
message, and no browser page or stream-controller errors. No duplicate test or
runtime change was needed.

## Checks

- Focused Next/close/reopen case: 1/1 passed; five further serial repeats:
  5/5 passed.
- The first full `frontend npm run check` passed typechecks, lint, six Node
  units, 65 components with coverage, build and 82 Chromium cases; one
  separately opt-in live-reset case skipped. An older `page failure during
  navigation` case timed out before its source button appeared. That case
  passed 5/5 isolated repeats.
- A second full `frontend npm run check` exited zero: typechecks, lint, six
  Node units, 65 components, coverage, build and 83 Chromium cases passed;
  the separately opt-in live-reset case skipped. The new stream regression
  passed while running alongside the complete Chromium suite.

The first suite timeout was transient in these observations; its exact cause
was not established. The deterministic fixture verifies the exercised browser
schedule, not every retained PDF, scheduling interleaving or spoken assistive
technology. This recheck made no provider request, database write, deployment,
PDF archive change or Ask enablement decision. Lane 6 quality and release gates
remain independent.
