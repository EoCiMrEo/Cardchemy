# Independent retained-browser original-PDF recheck

Date: 2026-09-29 (America/Chicago). Scope: read-only UI check following the
earlier [PDF stream cancellation fix](2026-09-29-original-pdf-stream-cancellation-fix.md).
The retained local app was already running and an authenticated in-app browser
session was available. No credentials, private page text or PDF bytes were
recorded in this log.

An independent agent opened Published lectures in the existing local Subject.
The original PDF visibly rendered for Week 2, Week 3 and Week 4 on page 1,
and navigation rendered each page 2: **six of six observed pages**. The viewer
showed expected totals of 33, 42 and 32 pages. No extracted-text fallback
banner was visible in those six views. Ask controls remained disabled. The
temporary browser tab was closed; the populated database, source attachments,
root `.env` and local services were left intact.

This confirms the bounded visible UI path that previously failed for the
owner. The browser surface did not expose console/network logs for this
check; it does not establish that all pages or timing/race cases are clear.
No provider call, database mutation, plan/ADR change or Ask activation was
made. The independent source-usefulness and release gates remain open.
