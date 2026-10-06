# Accessibility and responsive-release checks

The current product targets WCAG 2.2 AA-compatible interaction patterns for
its core browser flows. Automated checks reduce regressions but do not certify
conformance on their own.

## Automated gate

`npm run check` includes the Playwright suite. Its accessibility coverage must:

- run axe against authentication, dashboard, subject, set, dialog, preview,
  study-question, study-feedback, save-error, and completion states;
- fail on every serious or critical violation without broad exclusions;
- complete the student study flow using only the keyboard at a mobile viewport;
- verify focus visibility and movement, accessible names and progress values,
  absence of nested interactive controls, reduced-motion behavior, 44 by 44 CSS
  pixel core targets, and horizontal-overflow prevention;
- verify submission idempotency under rapid activation, retry, timeout, and
  timer/user-action races.

Run the gate from `frontend`:

```text
npm run check
```

## Manual assistive-technology pass

Before a release, test the production candidate using current Chrome with
NVDA or Windows Narrator (VoiceOver/Safari is an acceptable macOS equivalent).
Do not use a mouse during this pass.

1. Sign in and confirm Email, Password, Sign In, Forgot Password, account email,
   and Logout are announced in a useful order.
2. Open a student course and confirm each set name, progress value, and Study
   Now or Review Again action is announced.
3. Complete an untimed study session. Confirm the question receives focus,
   options are announced as buttons, feedback states the result in text, Next
   Question receives focus, and Session Complete is announced.
4. Repeat with a timer. Confirm remaining time has a name/value, timeout is
   announced, and no duplicate result appears at the timer boundary.
5. Simulate a failed progress save. Confirm the error is announced, focus moves
   to Retry answer, retry does not change the logical answer, and the session
   cannot advance before persistence succeeds.
6. Open and close Join Course, Invite Students, Edit Subject, Edit Set, and
   Preview dialogs. Confirm each has a name and description, focus stays inside,
   Escape closes it, and focus returns to its trigger.
7. In Preview, confirm the flip control announces whether the answer is shown
   and only the visible card face is exposed.
8. Upload a PDF that matches Knowledge in the same Subject. Confirm the pending
   choice is announced after upload and after reload. Open the matching Knowledge
   dialog with the keyboard; confirm its title, matching document, available
   reuse/separate-copy actions, expiration and whole-job cancellation are
   announced. Confirm Escape returns focus to the trigger and the dialog fits a
   mobile viewport. Repeat when reuse is unavailable: no reuse action appears.
9. On an insufficient flashcard run with validated candidates, reload the page
   and confirm the observed count and pending state are announced. Open the
   smaller-target dialog with the keyboard, choose an exact count within the
   displayed range, confirm it, and verify focus returns and the resulting
   draft set has that exact count. Repeat an uncertain submission with the same
   operation identity and confirm it does not create a second set. Open the
   separate Retry dialog; confirm its extra-cost and unknown-prior-cost text is
   spoken before any new AI attempt can start. At a mobile width, verify no
   horizontal overflow or clipped controls.
10. In source-only Ask AI, confirm the provider disclosure names the source
    judge and bounded published page-text transfer before a question can be
    submitted. Verify the screen reader distinguishes a related Knowledge
    result, `no_match`, a clarification request, withdrawn references and
    temporary provider failure. The related
    heading, warning that passages are **not a verified answer**, document/
    page/section label and exact quote must be announced in order. Open the
    original lecture PDF page by keyboard, confirm focus enters the dialog,
    loading/rendering/page number and previous/next controls are announced,
    selectable text and the expanded page-text alternative are available, and
    close restores focus. The extracted quote stays adjacent; it is not a
    visual PDF highlight. Missing originals and lexical fallback must be
    announced distinctly. Confirm
    cancelled, hidden/stale or access-revoked sources expose no passage or page.
    At mobile width, quotes and pages must wrap without horizontal overflow;
    a manual Retry still needs its separate additional-cost dialog. Historical
    answer/abstention state checks apply only while older conversations exist.
11. With Ask unavailable, search and browse published lectures in an enrolled
    Subject. Confirm the search label, results and document/page names are
    announced; open the original PDF and extracted-text alternative by
    keyboard. After publication or enrollment access is revoked during an open
    page, verify the dialog closes, stale results disappear and focus returns
    to the published-lectures section. Repeat at mobile width.

Record the browser, assistive technology/version, viewport, date, tester, and
any findings in the release evidence. Repeat spoken-output verification on the
packaged release candidate; automated checks and accessibility-tree inspection
alone do not establish how assistive technology announces the interface.

## Product boundary

The web client is responsive and online-first. It does not register a service
worker, install as an offline-capable application, queue answers in IndexedDB,
or advertise offline synchronization. Network failures remain visible and a
study answer cannot advance until the server confirms durable persistence.
