# Lane 6 PDF and access keyless recheck

## Scope and starting state

This independent recheck covers original-PDF storage, authenticated range routes,
the source-only viewer, published-lecture browsing, and their keyless release
controls. The retained local installation was already migrated to schema head
`20260927_0028` with three exact originals attached. Ask admission remained
disabled. The existing populated volume, root `.env`, original PDFs and backup
were not modified. No provider call, Knowledge indexing or retained DB write was
made.

Read the repository operating guide, Start Here, project/module maps, ADR-023,
accessibility guidance, tests and the prior cutover evidence. Inspected current
route/service/viewer source rather than treating the prior passing log as a new
test result.

## Checks on this checkout

- `backend/venv/Scripts/python.exe -m pytest -q tests/test_knowledge_pdf.py tests/test_pdf_cors.py`
  from `backend`: **35 passed**. This covers encrypted block/range integrity,
  exact-revision attachment and rejection, route reauthorization and failure
  handling, range bounds and CORS preflight.
- `npm run test:e2e -- e2e/original-pdf.spec.ts --workers=2` from `frontend`:
  **8 Chromium passed**. Deterministic mock API and two-page test PDF verified
  three explicitly unverified references, authenticated byte ranges, rendered
  canvas/text layer, keyboard page change and focus return, missing/malformed
  original fallback, revocation, failed navigation and close-during-fetch.
- `npm run test:e2e -- e2e/published-knowledge.spec.ts e2e/knowledge-original-attachment.spec.ts --workers=2`:
  **4 Chromium passed**. The Ask-off published library, access-change cleanup,
  exact-original attach flow and oversized/unavailable controls passed with
  mocked API responses.
- `npx vitest run tests/components/pdfApi.test.tsx tests/components/pdfRangeTransport.test.tsx tests/components/boundedPdfText.test.tsx`:
  **3 files, 11 tests passed**. Client metadata/range validation, transport and
  bounded text behavior passed.
- Unauthenticated read-only requests against the current local edge returned
  **401/401/401** for published document list, original-PDF HEAD and original-
  PDF GET using synthetic UUIDs. This confirms the deployed routes reject a
  missing session; it does not test an authorized student's PDF read.
- `git diff --check` over the PDF route/service/viewer paths passed.

## Source review and limits

The current browse route uses a student principal and repeats enrollment,
reviewed/published active revision and embedding-space checks in SQL. The
original-PDF read binds the encrypted manifest to the selected current content
revision, then serves only a single bounded authenticated byte range. The
Ask-reference route reauthorizes the complete reference bundle before its PDF
read. Response headers include `no-store` and `nosniff`; the PDF stays behind
API authorization, not a public static path. These are source observations,
not a proof of a live authorized browser journey.

The Chromium cases use mock identities, a synthetic PDF and intercepted API
traffic. They do **not** establish that a real enrolled student can open the
three retained lecture PDFs, that a revoked live session closes an already
open page, or that the page shown is pedagogically useful. No authenticated
browser session was available, and no credential was minted or read from
secrets. Manual Chrome/NVDA or Narrator spoken-output review, including mobile
focus/announcement behavior on the packaged candidate, remains open under
`docs/ACCESSIBILITY.md`. The independent usefulness and release gates in
ADR-023 therefore remain open; this recheck does not authorize enabling Ask or
checking Lane 6 release boxes.
