# Ask AI query-embedding budget assessment

Date: 2026-09-28 (America/Chicago). Branch `main`, HEAD
`6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`. The checkout already had
extensive modified and untracked work; it was preserved. This was an
investigation, not Ask activation, policy implementation, live evaluation, or
an update to the product-quality plan.

## Scope and current decision

The operator asked whether allowing one to three embedding requests per Ask
would resolve the remaining quality problem, while keeping the Ask experience
bounded. In this review the operator clarified that the target is the current
ADR-023 original-PDF source-navigation experience, with **zero answer-model
requests**, not a return to generated answers. Read root `AGENTS.md`, Start
Here, the project and backend maps, the Knowledge architecture, ADR index and
ADR-023, current state, Lane 6 plan, testing guide, relevant dated logs, and
the active retrieval/worker/selector code. Three independent bounded,
read-only audits covered runtime contracts, experimental evidence and design.

## Evidence and diagnosis

- The active new-job contract is `related_knowledge_navigation_v3` with
  `hybrid_source_navigation_v9` and `source_navigation_v9`. The worker sends
  only the current question through `embed_query` once, with automatic
  provider retries disabled. It uses authorized hybrid SQL, or a bounded local
  lexical fallback on specified transient embedding errors. It makes no
  answer-model or local answer-verifier call. Worker, model and PostgreSQL
  stage guards enforce one query-embedding stage and at most one physical
  request per durable attempt. `RAG_ASK_ENABLED` remains effectively off.
  See `backend/app/workers/rag_answer.py`, `backend/app/models/rag.py`,
  `backend/app/services/knowledge_retrieval.py`, `backend/app/ai/source_navigation.py`,
  `backend/app/config.py` and ADR-023.
- The separately authorized, consumed 2026-09-28 run made eleven real
  `gemini-embedding-001` calls, one per current question and zero retries.
  On this exposed published-source regression set, all eleven designated
  pages reached the actual hybrid SQL candidate pool; useful original-PDF
  page hit@3 was 11/11 and useful top-one was 9/11. Independent page review
  found only **19/33 displayed cards useful**. Fourteen weak cards were shown
  despite a useful page being reachable. This is development evidence, not a
  fresh holdout or live billing receipt. See the live-query hybrid diagnostic
  and independent original-PDF grading logs dated 2026-09-28.
- A fresh unpublished-PDF lexical proxy reached useful-page hit@3 9/12 and
  follow-up hit@3 1/4. The three failed follow-ups separated into unresolved
  referent, lexical candidate miss, and wrong-page selection when the useful
  candidate was already present. This was not real indexed hybrid retrieval
  or a published-source release test. See the stagewise diagnostic log.
- The latest approved public-only selective navigation scorer stopped at
  `calibration_rejected_no_heldout`. Its raw ranking contained a useful cue
  in the top three for all 36 positive calibration groups, but the frozen
  question-level no-match and per-card thresholds could not jointly satisfy
  zero displays on twelve no-useful groups, at least 90% useful displayed
  cards, and the positive hit floor. No heldout score or runtime component
  follows. See the selective-navigation frozen-audit log.
- No recorded experiment compares one versus two or three query embeddings
  for the **same** Ask question. A historical embedding batch contained six
  different questions, not six query variants for one question. The current
  code's single-vector assumption cannot be relaxed by configuration alone.

## Recommendation and falsifiable next step

Keep the current one-query-embedding cap and zero answer calls. First measure
the complete original-PDF-to-displayed-card funnel and address page
qualification and selective display: show zero to three useful pages, never
fill the count with merely same-topic pages, and distinguish no useful match
from embedding unavailability or an unresolved follow-up. The current
selector gives positive term overlap plus search rank a score and selects up
to three pages; it does not prove that a page addresses the requested relation
or condition. Prior structural and local-scorer attempts did not pass their
frozen gates, so another heuristic or model is a candidate to test, not a
release claim.

Only if a pre-frozen independent, eligible published-source evaluation shows
material candidate-stage misses should a separately approved experiment
compare one, two and three same-space query vectors on the same questions,
same selector and same access controls. Record candidate recall, useful
first page, hit@3, every displayed card's usefulness, no-match correctness,
latency, physical requests, total tokens and cost uncertainty. Current-question
variants could potentially be sent in one synchronous
`models.batchEmbedContents` HTTP call, which Google's API documents as
returning multiple vectors; this is not implemented here, does not make
multiple embeddings free, and needs capability and quota verification. Sending
resolved conversation history to the provider would change the current
privacy disclosure and require a separate decision. Do not mix Embedding 001
and Embedding 2 vectors. A runtime increase requires a new immutable policy,
compatible migration/guard, aggregate attempt budget, failure and uncertain
cost handling, disclosure, and offline/disposable tests before any activation.

ADR-023's independent source-separated 12-case release gate remains open:
useful-page hit@3 at least 10/12 overall and 3/4 per direct, paraphrase and
follow-up form, at least 90% useful original-PDF pages among **all displayed
cards**, plus no-match, access, exact page/PDF, browser, spoken accessibility
and operational checks. More embeddings cannot by themselves establish the
displayed-card gate. Ask remains disabled if it is not met. The already
implemented independent published-Knowledge browse/search path remains
available while Ask is off.

## Checks and limits

- Re-ran the provider-free targeted tests from `backend`:
  `test_rag_source_only.py`, `test_source_navigation.py`,
  `test_navigation_query_candidate.py`, and `test_knowledge_retrieval.py`:
  **58 passed**. An initial command used the wrong relative Python path and
  exited before test collection; the corrected command passed.
- `python scripts/check_context.py` passed: 37 required files, 78 active
  guides and 1,412 local links validated. `git diff --check` on the touched
  log index reported no whitespace errors.
- Checked Google's current primary documentation for task-mode/space
  compatibility and the synchronous `models.batchEmbedContents` endpoint:
  <https://ai.google.dev/gemini-api/docs/embeddings> and
  <https://ai.google.dev/api/embeddings>. This establishes API capability,
  not Cardchemy integration or actual account quota/billing.
- No provider request, private PDF text inspection, retained database write,
  root `.env` read/change, reindex, Ask activation, plan/ADR edit or runtime
  source edit occurred. Existing live and public scorer approvals were
  consumed by earlier work and were not reused. This investigation adds only
  this dated record and its log-index entry.
