# Retained original-PDF rendering and cancellation check

## Scope and starting state

The user had reported a safe extracted-text fallback after attaching exact lecture PDFs. The earlier MIME repair was already in the running local stack. This independent check started on `main` at `6c02d6c`, with a large pre-existing working tree and the populated installation preserved. The repository guide, orientation, frontend map, ADR-023, and the previous PDF repair evidence were read. No paid AI call, database mutation, volume reset, or root `.env` edit was part of this check.

## Browser observation before the focused change

In the retained authenticated local subject browser, the original PDF canvas rendered Week 2 page 1/33 and page 2/33, Week 3 page 1/42, and Week 4 page 1/32 and page 2/32. The reported extracted-text fallback did not occur on these pages. Ask was visibly paused. Each initial lecture open nevertheless produced one PDF.js `RenderingCancelledException` and two `ReadableStreamDefaultController` console errors; page navigation succeeded. No lecture text or screenshot was saved in this log.

## Focused change

`OriginalPdfPage.tsx` now waits for the measured viewer width before rendering, and observes the canvas render promise immediately while text is streamed. Both source dialogs reserve a stable scrollbar gutter, reducing the chance that their first canvas changes measured width. The Chromium viewer test also checks for stream-controller console errors and page errors. This addresses a plausible first-render/resize cancellation race; it does not change authentication, PDF range access, source content, or the safe fallback.

## Verification and limit

- `npm run test:e2e -- e2e/original-pdf.spec.ts --project=chromium --grep "three unverified" --workers=1` exited zero, one test passed.
- After adding the page-error assertion, the focused nine-case `original-pdf.spec.ts` run exited zero, nine tests passed.
- `npm run check -- --workers=2` exited zero: six unit tests, 65 component tests, 81 Chromium tests passed; one separately opt-in live reset browser case skipped. The build, types, lint, and coverage stage passed.
- Rebuilt and recreated **only** the local frontend service with the documented development Compose override. The frontend reached healthy state, `/healthz` returned HTTP 200, and the read-only built-image smoke passed, including the PDF module worker MIME/security headers.
- The original in-app browser session disappeared after the frontend cutover. A fresh in-app tab was available, but it redirected to `/login` because the retained browser authentication session was gone. No credentials or account state were inspected or changed to regain access. Therefore the retained Week 2/3/4 PDFs and console were **not** rechecked on the new image. The synthetic Chromium result proves the regression path tested there, not the absence of the previously observed real-PDF console errors. The original canvas rendered on the prior image, and the new image still needs an authenticated retained-browser check.
- A disposable Chromium replay used the exact local Week 2, 3, and 4 PDF bytes in memory through the existing mocked authenticated range route; no private bytes, page text, or screenshot was saved to the repository. One early run rendered all three PDFs but captured six PDF.js stream-controller `pageerror`s. With navigation synchronized on the viewer's enabled Next control, a subsequent run and three repeat runs rendered page 1 and 2 of each PDF with zero observed stream errors. The temporary test file was removed. This mixed result shows the console race is timing-sensitive and **does not prove it is completely fixed**. A future regression test should exercise the early navigation/teardown schedule and require zero page errors before closing this issue.
- `python scripts/check_context.py` passed with 37 required files, 79 active guides, and 1,481 local links.

Ask remains disabled under the separate Lane 6 usefulness and release gates. Backend, workers, database, encrypted PDFs, populated volumes, backup, and root `.env` were left intact.
