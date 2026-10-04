# Ask AI and flashcard quality investigation before Lane 6

Date: 2026-09-25. Scope: read-only investigation and recommendations only;
no runtime implementation or remediation-plan update. Starting branch `main`,
HEAD `6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`. The working tree already
contained the uncommitted Lanes 0–5 implementation and related documentation;
those changes were preserved. The sole installation examined is the operator's
self-hosted local Compose stack. It was initially stopped and the operator
started it for content-free diagnostics.

## Context and boundaries

Read root `AGENTS.md`, Start Here, project/backend maps, current state, roadmap,
the product-quality plan, the generation/Knowledge/system flows, relevant ADRs,
the evaluation, observability and testing guides, and the dated September 17,
21, 22 and 23 product-quality/RAG logs. Three bounded read-only subagents traced
Ask retrieval, Ask answer validation and flashcard generation independently.
Current source and tests were checked against historical logs. Official
PostgreSQL 16 text-search and Gemini response metadata documentation were
consulted for the recommended diagnostics. No private question, page, PDF,
model response, credential, environment value, vector or hash was returned by
the database diagnostics or added to this record. The operator confirmed both
questions and Knowledge are in English. Screenshots of previously successful
cited answers were identified by the operator as predating this remediation.

## Confirmed Ask observations

- The retained local database has three active, ready, published Knowledge
  revisions and 104 eligible chunks in one Subject. Its 12 September 23 Ask
  jobs all reached query embedding and retrieval, then made one answer request.
  Ten completed as abstentions with one local-support rejection each; two
  failed at the answer stage with `invalid_ai_output`. Each attempt made one
  embedding and one answer request with zero automatic retries.
- A current screenshot supplied during the investigation matched three newer
  September 25 jobs in the same conversation. All three failed at the answer
  stage on the configured Gemini answer model with `ai_provider_unavailable`,
  after successful embedding/retrieval and one answer attempt each. No local
  support stage ran; remote execution and answer-call cost are uncertain. The
  safe category groups network/protocol problems, HTTP 408/409/425/5xx and
  unclassified SDK exceptions, so the precise transport/provider cause cannot
  be determined from stored metadata. Two eligible chunks contain every
  user-supplied topic term from the screenshot question; this proves term
  presence in published Knowledge, not that the selected evidence supports an
  answer. Source: `backend/app/ai/providers/__init__.py`,
  `backend/app/workers/rag_answer.py`.
- A second current screenshot showed two separate subject questions that both
  completed as abstentions after local support returned false. Each made one
  embedding and one answer request, with zero retries. The same exact wording
  had this outcome in 2/2 and 3/3 retained attempts across two answer-model
  selections. Ten eligible chunks contain the operator-supplied technical term;
  five also contain the two associated source-domain terms. Both full-question
  `simple` and English lexical queries still matched zero chunks. This makes
  the cases useful false-abstention candidates but does not prove that the
  retrieved vector evidence or generated claims were correct.
- The shipped `plainto_tsquery('simple', full_question)` lexical path matched
  zero eligible chunks for all 12 questions. An English-configured full-question
  query also matched zero. A read-only three-term OR probe found 6–41 candidate
  chunks per question, which shows candidate generation but does not establish
  recall or answer support. The 12 jobs relied on nonempty vector candidates.
  Source: `backend/app/services/knowledge_retrieval.py`; eligibility:
  `backend/alembic/versions/20260918_0010_subject_knowledge.py`.
- The local verifier passed its 11 short authored cases in three repetitions
  on the installed bundle, yet rejected all ten retained real completed jobs.
  Its boolean decision does not persist which entailment, QA relevance,
  equivalence or contradiction check rejected a claim. The retained metadata
  cannot establish whether those were correct rejections of irrelevant
  retrieved/generated content or false rejections. Source:
  `backend/app/ai/local_support.py`, `backend/app/workers/rag_answer.py`.
- The two older `invalid_ai_output` failures cannot be split into empty provider
  text, incomplete JSON or strict schema/shape failure from retained metadata.
  The adapter parses text before reading usage and does not retain a safe finish
  reason; answer-call cost is unknown. The generic public
  `rag_answer_failed` message covers several stages. A stored
  `local_support_unavailable` category is currently normalized to
  `internal_error` in operator diagnostics. Source:
  `backend/app/ai/providers/__init__.py`, `backend/app/services/operations.py`,
  `backend/app/observability.py`.
- Standalone headings remain section metadata but are absent from the current
  citable chunk text/Embedding 001 input/FTS input. Follow-up history is added
  to the answer prompt after retrieval of the current question. These are
  verified design limitations, not established causes of the retained jobs.
  Source: `backend/app/ai/chunking.py`, `backend/app/workers/knowledge_index.py`,
  `backend/app/workers/rag_answer.py`.

## Confirmed generation observations

- The operator-named 20-card failed job has `insufficient_grounded_cards`, 32
  candidate rejections accumulated across its first run and two manual retries,
  12 generation requests and zero provider retries. Its zero accepted-card
  field means no cards were persisted atomically; valid intermediate candidates
  in failed attempts are not counted there. Another completed 20-card job used
  different source content and is not evidence of this source's feasibility.
- The failed job's Knowledge capture is active, ready, reviewed, published and
  fully indexed. Its 42 extracted pages yielded 13,740 characters and 39
  chunks with 4,382 estimated tokens. Replaying the current token-weighted
  20-card allocation over those stored chunk sizes assigns one card each to
  20 chunks and zero to 19. Refill recomputes from the same weights, leaving
  those 19 without an assigned card. This is a confirmed opportunity loss; the
  number of distinct testable facts in the source remains unmeasured.
- Pipeline diagnostics already calculate per-round raw/grounded/distinct/
  accepted/missing counts and fixed rejection reasons, but the generation
  worker does not persist them on failure. The dominant reason among the 32
  rejections therefore cannot be reconstructed. Candidate batches from the
  same chunk can run before earlier candidates are validated and excluded.
  Source: `backend/app/ai/chunking.py`, `backend/app/ai/pipeline.py`,
  `backend/app/workers/generation.py`.

## Operator decisions and recommendations pending approval

The operator chose to retain an exact requested card count. If it cannot be
met, show the verified available count and offer an explicit smaller target.
They prefer temporarily retaining fully validated candidates until that
choice, without creating a partial set or making another provider call. The
temporary state needs bounded capacity, expiry, authorization, cancellation,
fencing and atomic final persistence. The observed validated count is a lower
bound from that attempt, not a mathematical maximum for the source.

Recommend a single new remediation lane before the current Lane 6, with
separate gates for: safe per-stage/per-reason Ask and per-attempt generation
diagnostics; a private labeled real-course question/evidence corpus; measured
retrieval ablations including lexical terms and section context; a versioned,
independent local support policy evaluated on the same corpus; structured
answer validity/finish-reason diagnosis; adaptive card allocation/refill and
validated-candidate choice; and offline, disposable PostgreSQL, browser,
accessibility and separately authorized bounded live quality checks. Preserve
Subject authorization, publication/revision/space SQL filters, strict quotes,
citations, zero unsupported claims, two remote Ask calls per attempt with no
automatic retry, exact-count card persistence, four-option validation, duplicate
rejection, source cleanup and existing cost ceilings. Do not switch embedding
space, loosen semantic thresholds or enable automatic paid retries merely from
these observations.

## Checks, limits and cleanup

- Focused backend offline selection: 87 passed, 2 skipped. Separate generation
  quality selection: 37 passed. Separate retrieval/answer selection: 19 passed.
  These overlap and must not be summed as unique tests.
- Installed local-support evaluator: 11/11 authored cases in three repetitions,
  with no provider calls; startup 4.87 seconds and p95 check 113 ms. These
  short synthetic cases do not establish real-course answer quality.
- Local Compose/database queries were read-only and content-free. Investigators
  made no paid AI call; the operator's current screenshots were matched to
  five newer user-initiated attempts. No production deployment, migration, root
  `.env` edit, service restart, database write or volume change was performed
  by the investigation. No
  runtime code or product-quality plan file was changed. No temporary test
  database or container was created; the operator started the existing stack.
- The exact false-rejection mechanism, right retrieved evidence, strict-output
  failure subtype, new transport/provider failure subtype and source fact
  sufficiency remain open until reviewed representative cases and safer
  attempt diagnostics are available. A new live provider evaluation requires
  a fresh explicit endpoint/model/price/call/token/time/cost envelope.
