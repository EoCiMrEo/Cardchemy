# Original PDF worker MIME and retained-browser repair

## Scope and starting context

On 2026-09-28 the operator opened an enrolled student's published-lecture
browser on the retained local installation. Week 2 page 1 displayed the safe
extracted-text fallback despite an exact original PDF attachment. The same
failure appeared at narrow and wide browser widths. Work began on `main` at
`6c02d6c` with a substantial pre-existing working tree. The repository guide,
orientation, maps, ADR-023, viewer/API contracts and relevant Lane 6 logs were
read; existing changes and the populated installation were preserved.

## Diagnosis and change

- All three retained encrypted original-PDF archives authenticated and matched
  their stored SHA-256 and page counts. The running backend returned authorized
  `HEAD 200` with exact length/page/range metadata and `GET 206` with exact
  `Content-Range`, content type and byte length. This ruled out missing or
  corrupt attachments and the backend range contract.
- The built PDF.js `.mjs` worker returned `application/octet-stream` from the
  Nginx edge. The browser viewer failed in `pdf_load` after its initial
  authorized range. Module workers require a JavaScript MIME type.
- [frontend/nginx.conf](../../../frontend/nginx.conf) now serves only
  fingerprinted `/assets/*.mjs` as `text/javascript`, with the same immutable
  caching, CSP, `nosniff`, static-file 404 and redacted access-log behavior as
  the other assets. Other asset MIME handling remains inherited.
- Because the old wrong-MIME response was already cached under an immutable
  worker asset URL, [OriginalPdfPage.tsx](../../../frontend/src/components/rag/OriginalPdfPage.tsx)
  requests a one-time versioned URL. The same component now emits only a
  whitelisted failure stage/status/code, never the URL, PDF text, raw exception
  or token. [check_images.py](../../../scripts/check_images.py) checks the
  built worker MIME, cache, CSP and `nosniff` headers. Chromium viewer cases
  also check the versioned URL and a PDF requiring multiple ranges.
- The lecture dialog now labels the extracted text as the **opened** page and
  the Ask source dialog as the **cited** page. PDF page navigation updates its
  own page status; the adjacent extracted text remains anchored to the opened
  citation. This prevents a student from mistaking page-1 extracted text for
  a later PDF page after using Next. The typed English catalog and browser
  checks cover both labels.

## Verification and evidence limits

- The corrected local worker returned `HEAD 200`, `text/javascript`, the
  expected length, immutable cache header and CSP. The rebuilt frontend
  container reached healthy state; backend, workers, database and PDF archives
  were not recreated.
- The actual retained enrolled browser rendered original PDF page 1 for Week
  2, Week 3 and Week 4, and page 2 for Week 2 and Week 4. Canvas, selectable
  text and page-navigation controls appeared. The reported fallback did not
  recur in these checks. A disposable Chromium probe also rendered the actual
  Week 2 PDF in memory through two ranges, without copying or logging it.
- `py -3 scripts/check_images.py frontend --image cardchemy-frontend:0.1.0`
  passed the no-network, no-credential image smoke.
- After the label clarification, only the frontend image/container was rebuilt
  and recreated. The image smoke passed again, and the retained enrolled
  browser showed `Opened from Week 4 · page 1`, `PDF page 2 of 32`, and
  `Extracted text for opened page 1` after keyboard navigation. It rendered
  the original PDF rather than the extracted-text fallback. The reported Week
  2 page 1 was reopened on that final build; its 33-page PDF canvas rendered
  and a browser screenshot was shown to the operator without saving private
  lecture pixels into the repository.
- A nonconcurrent `npm run check` passed typechecks, lint, six unit tests,
  59 component tests with coverage, build and **81 Chromium tests**; the
  separately opt-in live password-reset browser case was skipped. An earlier
  duplicate run stopped because another Playwright run owned port 4175; that
  concurrent run had one unrelated invitation-navigation timeout which passed
  alone. The final nonconcurrent full run exited zero.
- A second nonconcurrent `npm run check` after the label clarification also
  passed six unit, 59 component and 81 Chromium tests, with the opt-in live
  password-reset case skipped.
- After the final frontend cutover, `scripts/check_context.py` validated 37
  required files, 78 guides and 1,401 active links; `scripts/check_ci.py` and
  `scripts/check_release.py --version 0.1.0` passed. The later unrelated
  public-audit log added one active link, and context validation passed again
  with 1,402 links.

This proves the original-PDF viewer works for these retained pages in the
current local browser. It does not establish the separate source-usefulness
gate, every PDF/page, a spoken assistive-technology pass or Ask activation.
Ask remains disabled. No paid provider call, Knowledge indexing, database
write, volume deletion or root `.env` change occurred. Temporary PDF probes
were removed; the user-owned browser tab was left available.
