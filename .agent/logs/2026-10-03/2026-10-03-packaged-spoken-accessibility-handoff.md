# Lane 6 packaged spoken accessibility handoff

## Scope and preservation

The operator authorized finishing Lane 6 and required an actual spoken assistive
technology release check. The root agent authorized a bounded loopback synthetic
fixture for that check. This record covers UI handoff preparation, not a spoken
pass, source usefulness, provider reliability, authorization, or release enablement.
No provider request, operator configuration read, private lecture read, retained
database/service/flag mutation, package rebuild, or threshold change occurred.

Read the repository instructions, relevant orientation and accessibility guidance,
current frontend services/components, and existing original-PDF, published Knowledge,
generation-choice, accessibility and journey fixtures. Applied
`frontend-testing-debugging`; the host browser inventory was empty and `iab` was
unavailable, so the approved local fixture was verified with installed Playwright.

## Exact candidate and bounded fixture

- Frontend image: `sha256:e672a910c14e69f68fcecd974fac4435c258c0d12fcdbefca2b46889767ef694`.
- Existing `frontend/dist` differs from that image. It was preserved and was not
  used as the fixture package. A networkless read-only disposable Docker run copied
  the image's fifty public static assets into a new private Temp directory.
- Image `index.html` SHA: `a36f322fa045f028b4d91bf549bbab2b3e330c2b8d2069a6685cf18ebcd2260c`.
- Asset manifest SHA: `76e0c6c6efa99649ae9396ff58afcb4240dbb79eeb02b96bd2cb71d0c9dc82a2`.
- Owner-private output:
  `C:\Users\eocim\AppData\Local\Temp\cardchemy-spoken-release-jca_bzxc`.
- Fixture URL: <http://127.0.0.1:8898/__lane6-review__>.
- Python process PID `30060`; launcher PID `53196`. Start
  `2026-10-03T22:45:23Z`; shutdown timer is sixty minutes (deadline
  `2026-10-03T23:45:23Z`, 18:45:23 America/Chicago).
- Ignored helpers: `.agent/.verification/lane6_spoken_fixture.py` and
  `.agent/.verification/lane6_spoken_smoke.mjs`. The server serves copied assets
  unchanged, a separate test-only landing page and fixed synthetic API responses.
  It binds only `127.0.0.1:8898`, never forwards requests, uses no real credentials,
  does not read `.env`, and has no provider client. The synthetic bearer string is
  explicitly nonsecret and has no authority outside this fixture.
- `asset-manifest.json` and `running.json` bind candidate identity and lifecycle;
  `smoke-complete.json` records rendered checks; `stopped.json` records automatic
  shutdown. All artifacts and screenshots remain in the private Temp directory.

## Verified synthetic interaction checks

Current Chromium, desktop 1280×900 and mobile 360×780:

- Ten distinct scenario routes render meaningful Cardchemy content: related,
  no-match, clarification, failure, withdrawn, lexical fallback, absent original,
  published browse while Ask is disabled, revoked access, and pending card choice.
- Original two-page PDF renders using the packaged PDF.js module/worker; page
  1→2→1 navigation, readable text disclosure and Escape return focus to the exact
  triggering reference. Mobile PDF/dialog has no body overflow.
- Absent original preserves current extracted text; revoked source access closes
  the dialog and removes the publication entry. Synthetic status is not evidence
  of actual backend authorization enforcement.
- Search retry disclosure shows unknown prior cost before the user can confirm;
  Cancel starts no retry.
- Generation remains pending across reload. A separate additional-cost dialog
  opens and cancels. Selecting exactly ten of twelve valid cards first receives a
  synthetic HTTP 503, locks the selected count, then succeeds only with the same
  logical retry identity. UI shows `Review 10 cards`; no generation retry occurs.
- No runtime exceptions, external requests or unhandled synthetic API routes.
  Console 404/503 and content-free PDF warnings are the intended missing/revoked/
  uncertain-response controls, not unexplained errors.

An initial smoke assertion used an obsolete empty-state string; it timed out and
was corrected to the actual catalog copy. An initial no-match screenshot captured
loading; the final smoke explicitly waits for the no-match state. These were
fixture assertion repairs, not product changes. Final screenshots were visually
checked, including the original-PDF desktop dialog and smaller-count mobile dialog.
This evidence does not establish NVDA/Narrator speech or replace retained live
browser, provider, migration, security, or independent usefulness gates.

## Concrete human spoken review (pending)

Open the fixture landing URL in current Chrome. Use **NVDA or Narrator**, then use
the keyboard only. Do not log in or enter real data. Record date, browser version,
screen reader/version, viewport and any observed issue. The landing page links
perform full reloads so each test scenario selects the intended synthetic role.

1. **related**: read the `Related published Knowledge` warning and both reference
   titles, pages and quotes. Open `Read lecture page 1`; hear the dialog name,
   current PDF page and controls. Use Next/Previous, expand `Readable text from
   this PDF page` and the cited-page text. Press Escape; focus returns to the
   reference. Repeat at a narrow/mobile viewport or 200% browser zoom.
2. **no-match**, **clarification**, **withdrawn**, **fallback**: hear each distinct
   outcome, the suggestion to clarify/browse, and the fallback warning. No-match,
   unclear and withdrawn states must not pretend to contain an answer or a source.
3. **failure**: open `Retry search`; hear the new-attempt disclosure, additional
   cost and unknown previous cost before any confirmation. Cancel and verify focus
   returns to the retry trigger.
4. **published-only**: open the synthetic lecture with Ask disabled, navigate PDF
   pages, expand current text, Escape. **missing-pdf**: hear the absent-original
   status and read available extracted text. **revoked**: the source disappears;
   dialog closes and focus stays in a useful page location with no stale content.
5. **gen-choice**: first open `Retry`, hear `Start another AI generation attempt?`,
   estimated additional cost and unknown prior cost; Cancel. Reload and hear
   twelve verified versus twenty requested, with no set yet. Open `Choose a
   smaller set`, type **10**, submit. Hear the synthetic error, unchanged locked
   count, then submit the same choice once more. Hear success and
   `Review 10 cards`. Check keyboard reachability, dialog focus and mobile wrapping.
6. Report `spoken pass` or the failing scenario/control with browser and AT
   versions. Missing speech, unclear names/state changes, lost focus, traps or
   inaccessible text are failures. Automated checks cannot mark this pass.

Use the landing page's `Reset synthetic scenarios` button before repeating the
revoked/generation cases. It only resets fixture memory. The root agent may stop
the owned fixture after the check or let the sixty-minute timer stop it. Never
stop retained services to clean up this fixture.

**Status: synthetic UI handoff ready; actual spoken release check pending.**
