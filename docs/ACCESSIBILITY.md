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

Record the browser, assistive technology/version, viewport, date, tester, and
any findings in the release evidence. Repeat spoken-output verification on the
packaged release candidate; automated checks and accessibility-tree inspection
alone do not establish how assistive technology announces the interface.

## Product boundary

The web client is responsive and online-first. It does not register a service
worker, install as an offline-capable application, queue answers in IndexedDB,
or advertise offline synchronization. Network failures remain visible and a
study answer cannot advance until the server confirms durable persistence.
