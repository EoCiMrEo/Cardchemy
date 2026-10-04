# Dormant v4 Ask AI browser contract

Date: 2026-09-29 (America/Chicago). Branch `main` at `6c02d6c`. This focused frontend slice follows accepted [ADR-024](../../../docs/decisions/ADR-024-gemini-source-id-judge.md) and the original-PDF rules retained from [ADR-023](../../../docs/decisions/ADR-023-original-pdf-source-navigation.md). The broad pre-existing working tree, root `.env`, populated database, original PDFs and provider ledgers were preserved. Ask remained disabled; no paid request, private Knowledge transfer, database change or deployment occurred.

## Change and contract

- Matched the typed v4 profile/job response to `backend/app/schemas/rag.py`: source-judge capability/provider/model/content-transfer disclosure, `clarification_needed`, safe failure kinds, and nullable historical job policy. Historical answer/abstention is a message outcome, while the historical job `result_kind` is null. Current v3 source-only jobs remain readable without admitting new v3 work.
- The browser now checks the independent Ask release switch along with advertised availability before creating a conversation, submitting a question or retrying. A long-open page refreshes the profile before enqueue so a changed embedding model or source judge must be displayed first. Retry keeps its separate additional-cost and unknown-prior-cost dialog.
- A completed related job with a withdrawn reference bundle is labelled unavailable instead of claiming related material is still present. Revalidation closes an open page when the job, visible question or exact reference has changed. The original-PDF viewer and its extracted-text fallback stay behind current authorized page reads.
- Updated the shared browser fixture to the v4 profile, repaired a v3 original-PDF test fixture, and added focused component cases for the closed release switch and withdrawn references. The frontend map and accessibility guide now include source-judge disclosure and distinct clarification/withdrawal states.

## Verification and limits

- `npm run test:e2e -- e2e/rag-knowledge.spec.ts`: **7 passed**.
- `npx vitest run tests/components/askAiFailureCopy.test.tsx`: **18 passed**.
- Final `npm run check`: types, lint, six Node units, **65 component tests**, production build and **81 Chromium tests passed**; the separately opted-in live reset browser case was skipped. The first complete run had one unrelated set-editing alert assertion fail under load; its targeted suite then passed **3/3**, and the entire check passed on rerun. No threshold was reduced.
- `python scripts/check_context.py`: validated **37 required files, 79 active guides and 1,460 local links**. Scoped `git diff --check` passed.
- These tests prove deterministic client behavior against local API fixtures. They do not prove spoken screen-reader output, real Gemini selection usefulness, current private lecture quality or the separate Lane 6 release gate. Manual assistive-technology and original-PDF release checks remain open; Ask must stay disabled.
