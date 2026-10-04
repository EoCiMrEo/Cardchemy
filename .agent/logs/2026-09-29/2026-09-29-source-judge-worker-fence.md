# Dormant v4 source-ID worker fence

Date: 2026-09-29 (America/Chicago). Branch `main` at `6c02d6c`. This is a focused worker and keyless-test slice under accepted [ADR-024](../../../docs/decisions/ADR-024-gemini-source-id-judge.md). The pre-existing broad working tree was preserved. Ask remained disabled; no provider request, private Knowledge transfer, retained-database migration or data change occurred.

## Change

- In `backend/app/workers/rag_answer.py`, an unresolved v4 follow-up now completes with source-free `clarification_needed` before either remote stage. Missing or over-budget canonical pages fail the candidate read rather than appearing as a genuine no-useful-source result.
- The aggregate selection diagnostic now reports all inspected canonical pages/chunks/tokens separately from the at-most-four pages sent to the judge; it records no source text or page identifiers.
- The judge stage uses its admitted snapshot for input/output token and maximum-cost checks. Runtime usage uses the matching configured prices, including the admission service's upward micro-price rounding. An unchanged source snapshot is required immediately before source text egress, including physical page, section, revision, space, exact page text and cue offsets.
- Stage completion now rechecks the live lease, worker ID and claim token before committing usage. The provider adapters remain one query embedding and at most one source-ID request, with SDK retries disabled and no answer-generation or answer-verification path.
- `backend/tests/test_source_judgment_worker.py` adds fake-only checks for missing canonical pages, clarification without a provider boundary, a bounded multi-page slate, exact price snapshot, configured token/cost limits and stale-claim usage fencing.

## Verification and limits

- Focused backend tests covering the worker, source-ID parser, navigation and retrieval: **52 passed**.
- `git diff --check` on the worker and focused tests passed. Ruff was unavailable in the backend virtual environment (`No module named ruff`); no lint pass is claimed.
- A separate combined run including the older `test_rag_source_only.py` had **13 failures** from its v3 policy monkeypatch against the current v4 release fence; the admission/test owner is handling that stale suite. This slice does not claim a full offline-suite pass.
- The worker may inspect up to twelve current canonical pages but sends **at most four** to the judge. That cap preserves the prepared public pilot shape and bounded request. Actual multi-PDF runtime candidate recall and every displayed-card usefulness gate remain unmeasured release risks. The public pilot and any paid request need their separate gate and authorization. Ask stays disabled.
