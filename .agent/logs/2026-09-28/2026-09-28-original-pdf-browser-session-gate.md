# Original-PDF enrolled-browser session gate

## Scope and starting context

On 2026-09-28, independently checked whether the retained local Cardchemy
installation could be reviewed through an existing enrolled-student browser
session. The checkout was `main` at
`6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57` with extensive pre-existing
work. Read the repository guide, orientation and maps, ADR-023, accessibility
guidance, the published Knowledge browser and original-PDF viewer, current
Chromium cases, and the relevant prior keyless audit logs. This check made no
runtime, database, PDF archive or configuration change.

## Browser result and focused check

- The connected browser had no pre-existing tabs. A temporary local tab at
  `http://127.0.0.1:8080` reached Cardchemy's sign-in page. There was no
  authenticated enrolled-student session to reuse. The tab was closed; no
  credential was read, entered or created.
- From `frontend`, `npm run test:e2e -- e2e/original-pdf.spec.ts
  e2e/published-knowledge.spec.ts --workers=2` passed **10/10 Chromium cases**.
  These use a mocked student identity/API and synthetic PDF. They cover
  authenticated range-request wiring, visual page and text-layer rendering,
  keyboard page navigation and focus return, extracted-text fallback,
  revocation cleanup, Ask-off lecture browse/search, and mobile overflow.
- Earlier independent evidence records a disposable enrolled-student journey
  that opened a synthetic original PDF through a `206` range with adjacent
  source text; it does not substitute for the retained three-PDF session.

## Evidence limit and cleanup

The retained original PDFs were not opened in an actual enrolled-student
browser. Their physical page number, exact adjacent extracted cue, and live
fallback could not be observed here. No manual spoken NVDA/Narrator pass or
packaged-release mobile assistive-technology check occurred. The independent
usefulness, access and release gates remain open, and Ask remains disabled.
No provider call, Knowledge indexing, destructive action or credential lookup
was performed. The temporary browser tab and focused test process exited.
