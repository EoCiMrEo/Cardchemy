# Lane 6 local-query feasibility before source-ID judging

Date: 2026-09-29 (America/Chicago). Branch `main` at `6c02d6c`; all pre-existing work, retained `0028` database, root `.env`, three original PDFs and failed public model ledgers were preserved. Ask remained disabled. No provider request, private Knowledge transfer, indexing or heldout score occurred.

## Starting observation

The first keyless projection of 48 already reviewed public calibration groups used the immutable navigation-v3 resolver. It classified 13 groups as requiring clarification; eleven of those contained a useful exact cue and original page. Therefore even a perfect remote selector could hit at most 25/36 positive groups, below the frozen 30/36 calibration gate. This was recorded in the [preflight stop](../2026-09-28/2026-09-28-source-id-public-preflight-stop.md). The 192-group fixture still contains four pages from only one PDF per question and is not the ADR-024 deployment-shaped multi-PDF pilot.

## Local-only change

Added a distinct `navigation_query_v4` helper in `backend/app/ai/source_navigation.py` without changing the v3 resolver. It accepts a question whose topic is explicit before a later possessive referent, or combines one specific prior user turn with the current question **only for local retrieval**. It rejects absent/vague or explicitly multi-topic prior context. Neither the prior turn nor the locally expanded query is added to `backend/app/ai/source_judgment.py`'s remote request; its wire allowlist remains current raw question plus exact candidate page/cue and ephemeral IDs. The public harness pins this local resolver version in its packet fingerprint.

An exclusive new keyless calibration preflight under OS Temp prepared 48 public requests: **44 callable and four clarification**. Of 36 independently labeled positive groups, three remain behind clarification; the best possible useful-source hit@3 is now **33/36** (direct 12/12, paraphrase 9/12, follow-up 12/12). This makes the unchanged 30/36 calibration gate mathematically attainable, but does not show that a model will select the useful pages. The largest serialized wire was 6,738 UTF-8 bytes under the 8,192-byte bound. The preparation was run before a subsequent strict-parser hardening edit, so its contract hash must be refreshed before any use as a frozen live packet.

The source-ID parser now rejects duplicate JSON keys as well as duplicate, foreign, excessive or explanatory outputs. The source-ID-only request cannot carry prior chat or arbitrary candidate metadata. The focused provider-free tests `backend/tests/test_source_navigation.py` and `backend/tests/test_source_judgment.py` passed **26/26**. `git diff --check` passed during this work. The first test invocation from the repository root failed to import `app`; running from the documented backend directory passed. One test initially used an issued ID in its supposed foreign-ID case; it was corrected before the passing run.

## Limits and next gate

This is a feasibility repair to local query handling, not a Gemini quality result or runtime v4 activation. Do not score the existing same-PDF heldout or the separate fresh two-PDF release holdout as a substitute for ADR-024's new multi-PDF public candidate evaluation. Prepare independently reviewed other-PDF candidate pages and a new frozen packet, then document an exact endpoint/model/price/call/token/time/cost envelope for owner authorization before any paid call. Keep all 90% displayed-page and question-hit/no-match/access/release gates intact; Lane 6 remains 3/7.
