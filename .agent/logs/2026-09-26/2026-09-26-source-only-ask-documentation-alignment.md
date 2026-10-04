# Lane 6 source-only Ask documentation alignment

Date: 2026-09-26. Scope: current orientation, module maps, architecture,
configuration, operations, evaluation, privacy, accessibility and decision
navigation for the owner-approved source-only Ask change. Starting branch was
`main` at `6c02d6c`; the working tree already contained ongoing Lane 6 and
earlier product-quality work. Those edits were preserved.

## Approved direction and source state

The owner changed the Ask AI product goal: new work should guide students to
**Related published Knowledge** and the corresponding extracted lecture page,
without an answer-generation model or answer verifier. The owner approved
Lane 6 implementation and a clean reset of the development Docker volumes
after current evidence is preserved. Live provider spending remains separately
approval-gated. [ADR-022](../../../docs/decisions/ADR-022-related-knowledge-primary-ask.md)
owns the durable design. Historical ADR-019/021 answer/fallback decisions remain
readable as data and migration context, not as paths to enable new answers.

At this alignment checkpoint, source changes in progress use a default-off
`related_knowledge_v1` Ask path, one current-question embedding at most,
authorized retrieval, up to three exact page-labeled excerpts and an extracted-
page read. Source migration `20260926_0022` and typed API/UI contracts are
under verification. Old local containers were intentionally Ask-disabled;
the source-only runtime has **not** passed its measured corpus, full regression,
accessibility or rollout gate. Lane 6 therefore stays **3/7** checked. No
private document text, credentials, question text or raw model response is in
this log.

## Changes made in this documentation pass

- Updated root `AGENTS.md`, `docs/00-START-HERE.md`, `PROJECT-MAP.md`,
  `backend/MOC.md`, `frontend/MOC.md`, `ROADMAP.md`, `CURRENT-STATE.md`, the
  ADR index and narrow supersession notes in ADR-019/021. They distinguish
  historical answer execution from the only approved new Ask result.
- Updated `SYSTEM-OVERVIEW.md`, `SUBJECT-KNOWLEDGE-FLOW.md` and `DATA-MODEL.md`
  for a job-level related/no-match result with no assistant message, fenced
  query embedding, exact offsets, whole-bundle read redaction and the extracted
  page. The old answer-policy flow remains visibly labeled historical.
- Updated `.env.example`, `CONFIGURATION.md`, `AI_PROVIDERS.md`,
  `ASK_AI_SHUTDOWN.md`, `DEPLOYMENT.md` and `RUNTIMES.md` so the new path does
  not require an answer key, local verifier or ONNX model mount. `RAG_AI_*` and
  `RAG_LOCAL_SUPPORT_*` template entries remain labeled historical/inert while
  settings and migration consumers are still being reviewed. The source-only
  image/security inventory remains a release check, not a claimed pass.
- Updated `PRIVACY.md`, `ACCESSIBILITY.md`, `OBSERVABILITY.md`,
  `AI_EVALUATION.md`, `RAG_EVALUATION.md`, `TESTING.md` and the old profile
  migration guide. The source-only gate scores the **displayed windows** and
  page-open action, not just retrieval page rank. The candidate gate fixture is
  unobserved; no new live call was authorized by these doc edits.
- Corrected Lane 6 plan status language while leaving all unchecked items
  unchecked. The approved architecture does not itself prove quality.

## Verification and limits

`python scripts/check_context.py` passed after the edits: 37 required files,
77 active guides and 1,241 local links. Scoped `git diff --check` passed; Git
reported only existing working-copy LF/CRLF normalization warnings. No provider
request, database write, migration, volume operation or `.env` secret read was
made during this documentation pass. Source-only runtime tests, retained-stack
cutover, private displayed-window review and manual spoken accessibility are
still outstanding and must be recorded by their own evidence before any Lane 6
closure.

Historical logs were not rewritten. This entry supersedes current-state claims
about new Ask answer generation in older implementation records without
changing their observed results.
