# Product quality remediation plan audit

Date: 2026-09-22

## Scope and starting state

Read-only review of `docs/development/PRODUCT-QUALITY-REMEDIATION-PLAN.md`
against current backend, frontend, migrations, tests, architecture, accepted
decisions and relevant dated logs. No plan, runtime code, root `.env`, database,
deployment or provider setting was changed. Branch `main` at `6c02d6c`.
The plan and 2026-09-21 investigation log were untracked; `ROADMAP.md` and the
log index were already modified. All starting work was preserved. Three bounded
agents independently audited backend, frontend and documentation/operations.

## Evidence and findings

- The plan's two physical requests per Ask attempt needs an attempt-level
  definition. The worker currently performs query embedding, answer generation
  and remote support (`backend/app/workers/rag_answer.py:449-524`). Both provider
  adapters can retry, while job request counters accumulate across manual
  retries (`backend/app/ai/providers/__init__.py:359-407`,
  `backend/app/services/rag_answers.py:514-537`). Preserve the pre-provider
  infrastructure recovery fence and account for uncertain remote execution.
  The plan correctly requires an independently local support gate and abstention
  when it cannot meet the existing semantic/citation thresholds. Its local
  method, dependency and rollout outcome remain decisions.
- Progress currently means distinct attempted approved cards. The backend's
  `correct_count` is total correct attempts, and the student UI uses completion
  for trophy styling and `Study Now` versus `Review Again`
  (`backend/app/services/flashcard.py:575-605`,
  `frontend/src/pages/student/StudentSubjectDetails.tsx:100-155`). A new
  distinct-ever-correct metric can use existing progress rows, but accuracy,
  response-field compatibility and the UI success rule need definitions.
- Upload SHA is known only after the full source upload, which currently stores
  encrypted temporary bytes, charges upload quota and queues work immediately
  (`backend/app/services/generation.py:505-595`). Duplicate choice therefore
  needs a durable pending state, expiry/reload/idempotency rules and a separate
  reuse path. The existing capture function creates a content/index revision
  even when given a document ID (`backend/app/services/knowledge_capture.py:177-325`).
  Reuse must preserve existing review/publication and never let job cancellation
  delete the reused document.
- The proposed verified text-model catalog may narrow documented
  `openai_compatible` custom URL/model support (`docs/AI_PROVIDERS.md`,
  `backend/app/config.py:604-625`). The catalog's provider/endpoint scope and
  transition policy for queued jobs need a decision. Model changes also require
  a refreshed before-send provider disclosure on long-open browser pages.
- `gemini-embedding-2` needs a distinct space, model-specific formatting and
  migration; current settings, adapter and database constraints are specific to
  model 001 (`backend/app/config.py:573-602`, `backend/app/ai/embeddings.py`,
  `backend/app/models/knowledge.py:91-97`). Existing staged reindex/cutover can
  be extended, but availability during a mixed-space rollout must be specified.
  If title becomes indexed search input, capture currently changes a document's
  mutable title (`backend/app/services/knowledge_capture.py:177-206`); the plan
  must snapshot it per index or invalidate/reindex it on a title change.
- Proposed Progress and support changes intentionally reverse accepted
  ADR-003/012/014 contracts. `docs/decisions/ADR-000-INDEX.md` requires new
  numbered ADRs with bidirectional supersession links, not in-place replacement
  of historical decisions. The plan should also name affected flow, evaluation,
  testing, configuration and accessibility guidance, plus the manual spoken
  assistive-technology release pass.
- Study, duplicate handling and the safe Gemini parameter preflight can proceed
  independently of the uncertain local-support design. The plan's current
  phase order makes those work items appear blocked by it. The model-2 live Ask
  gate does depend on the chosen answer path.
- Visible extra cost for explicit Ask retry needs a concrete UI contract;
  existing jobs expose call/cost metadata but the Retry button currently gives
  no cost disclosure (`frontend/src/components/rag/AskAiPanel.tsx:253-263`).
  Shuffled Study options also require deterministic tests rather than fixed
  positional assumptions in existing keyboard flows.

The 2026-09-21 investigation log records the operator's earlier first-correct
Progress definition, two-request Ask cap, verified-model catalog, default 001
plus selectable model 2, and same-Subject warning choice. It also records that
the reported repeated question reached retrieval; support rejection, rather
than an empty retrieval result, explains its first observed abstention. Those
historical diagnostics are not current live/provider proof.

Official Google documentation checked during this audit confirms that 3.7/3.8
do not accept `minimal` thinking and that model 2 uses `gemini-embedding-2`,
prompt task instructions instead of `task_type`, and separate `Content` objects
for separate embeddings. References:
<https://ai.google.dev/gemini-api/docs/thinking>,
<https://ai.google.dev/gemini-api/docs/embeddings>,
<https://ai.google.dev/gemini-api/docs/structured-output>.

## Verification and limits

`python scripts/check_context.py` passed: 37 required files, 68 active guides
and 981 local links. `git diff --check` passed. No runtime suite, disposable
database, browser journey, paid AI call, hosted CI or deployment was run for
this documentation audit. The existing plan has 2 checked and 25 unchecked
tasks. The audit is awaiting operator clarification before any plan update.
