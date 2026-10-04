# Authenticated original-PDF browser recheck

Date: 2026-09-29. Scope: read-only verification of the retained local
development stack after the rebuilt frontend was installed. The owner signed in
directly in the in-app browser; no credential was supplied to the agent. The
populated database, encrypted original PDFs, root `.env`, volumes and backups
were not changed. Ask remained disabled and no paid AI request was made.

## Observed result

- Opened the Published lectures dialog for Week 2, Week 3 and Week 4 on the
  current frontend image. Each displayed the **original PDF canvas**, not the
  extracted-text failure fallback: page 1 of 33, 42 and 32 respectively.
- Navigated each document to its PDF page 2. The canvas and page counter
  advanced to 2 of 33, 42 and 32. A visual screenshot check confirmed that
  the Week 2 page-1 canvas contained rendered lecture content.
- Closed the viewer and rapidly opened/closed Week 2 three times. The in-app
  browser error log returned no errors during these observed operations.
- The earlier timing-sensitive PDF.js cancellation error was not reproduced in
  this authenticated sequence. A previous disposable replay did reproduce it
  under an early interaction schedule, so this check does **not** establish
  that every PDF.js stream race is fixed. Keep the focused regression issue open
  until the early schedule passes deterministically.

No private lecture text, screenshot, authentication material or PDF bytes were
written to this record. The independent source-usefulness and release gates
for Lane 6 remain open; Ask remains off.
