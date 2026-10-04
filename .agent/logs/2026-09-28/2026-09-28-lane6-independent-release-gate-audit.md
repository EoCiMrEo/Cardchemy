# Lane 6 independent keyless release-gate audit

## Scope and starting context

On 2026-09-28, audited the current source-only Ask v3/v9 worker, encrypted
original-PDF routes, published-lecture browser, and their release tests on
`main` at `6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`. The checkout already
contained extensive operator work. Read the repository guide, Start Here,
project/module maps, Knowledge architecture, ADR-023, Lane 6 plan, testing and
accessibility guides, source, and relevant prior evidence. This audit changed
no runtime source, plan, root `.env`, retained database, or retained volume.
The approved work was keyless offline/disposable verification; no Gemini call,
Knowledge reindex, or Ask activation was authorized or attempted.

## Fresh checks

- `backend/venv/Scripts/python.exe -m pytest -q tests/test_rag_source_only.py tests/test_source_navigation.py tests/test_knowledge_pdf.py tests/test_pdf_cors.py`
  from `backend`: **64 passed**. Source-only admission/worker request bounds,
  lexical fallback, old-policy fencing, navigation selection, encrypted PDF
  blocks, exact-original attachment and route/range failures were covered.
- `npx vitest run tests/components/pdfApi.test.tsx tests/components/pdfRangeTransport.test.tsx tests/components/boundedPdfText.test.tsx`
  from `frontend`: **3 files, 11 tests passed**.
- `npm run test:e2e -- e2e/original-pdf.spec.ts e2e/published-knowledge.spec.ts e2e/knowledge-original-attachment.spec.ts --workers=2`
  from `frontend`: **12 Chromium tests passed** with mocked API identities and
  synthetic PDFs. They cover page rendering/ranges, keyboard navigation,
  fallback, access loss, cleanup/focus, Ask-off browse, and exact attachment UI.
- `backend/venv/Scripts/python.exe scripts/test_journey.py` from the root:
  **RAG-off and RAG-on browser plus database proof passed** using separately
  generated disposable credentials, PostgreSQL/Mailpit, and deterministic
  providers. The RAG-on browser opened the authenticated Ask original-PDF GET
  as a `206` range and displayed physical page 1 with adjacent exact text.
  Database proof checked two completed source-only outcomes (`related_knowledge`
  and `no_match`), one query embedding per job, zero assistant messages or
  answer identities, one exact reference, and archived PDF blocks. Both
  scenarios cleaned up their processes, containers, data, and credentials.
- `backend/venv/Scripts/python.exe scripts/test_services.py postgres` from the
  root: **127 passed, 3 skipped, 2141 deselected** in the guarded disposable
  selection. Migration head/drift and selected downgrade/re-upgrade checks
  passed. Generated service and credential cleanup was confirmed. Skipped and
  deselected cases are not counted as passing release evidence.

The first journey invocation under filesystem sandboxing could not access the
Docker pipe and returned only the harness's safe failure line. The successful
run above used the approved sandbox escalation; it did not relax the harness's
disposable guards.

## Source observations and evidence limits

Inspected [`rag.py`](../../../backend/app/routers/rag.py),
[`published_knowledge.py`](../../../backend/app/routers/published_knowledge.py),
[`knowledge_pdf.py`](../../../backend/app/services/knowledge_pdf.py),
[`rag_answers.py`](../../../backend/app/services/rag_answers.py),
[`rag_answer.py`](../../../backend/app/workers/rag_answer.py), and
[`OriginalPdfPage.tsx`](../../../frontend/src/components/rag/OriginalPdfPage.tsx).

The Ask original-PDF HEAD/GET path requires an authenticated user, rechecks the
whole job-owned exact-reference bundle via `related_page` on every call, binds
the encrypted archive to the selected content revision, source SHA-256 and page
count, then probes or reads a bounded authenticated byte range. The separate
published-lecture path requires a student and repeats enrollment, active
reviewed/published revision, ready index and current embedding-space conditions
inside its document SQL. The worker sends only the current question for at most
one embedding attempt; source-only execution has no answer-provider or local
answer-verifier object. PostgreSQL stage guards reject an answer stage or a
second embedding. These are source plus deterministic-test findings, not a
live-provider billing measurement.

The real disposable browser journey exercises the Ask reference PDF route with
one synthetic page and a generated enrolled student. The published-lecture
browser and attachment Chromium cases use mocked API responses; this audit did
not open the three retained original PDFs through an actual enrolled browser,
or verify retained-session revocation against an already open live page. The
prior local unauthenticated `401` route probe remains historical evidence, not
a new result here. No private PDF text or account identifier was recorded.

Source-only safety controls have deterministic coverage for stale/foreign
references, wrong keys/hashes, incomplete/tampered archive blocks, out-of-range
reads, revoked enrollment before embedding, old-policy replay, and duplicate
remote-stage rejection. The full release gate still requires independent
original-PDF usefulness and negative/access controls on reviewed published
sources, including unrelated, ambiguous follow-up, unpublished/cross-Subject,
N12/U01, outage and malformed-embedding cases. A one-page deterministic journey
cannot establish useful displayed windows or page-open correctness on the
owner's course PDFs. The independent direct/paraphrase/follow-up holdout and
all-card usefulness requirement remain open; prior exposed development results
must not be used as fresh holdout proof.

The targeted browser cases exercise keyboard page controls and focus return,
but no manual spoken NVDA/Narrator or mobile assistive-technology review of the
packaged candidate occurred. Full `npm run check`, context, hosted CI, and
self-hosted release/backup/rollback proof were not rerun in this independent
audit. The Lane 6 plan's four open quality/release boxes stay unchecked; no
Ask enablement or deployment claim follows from these keyless passes.
