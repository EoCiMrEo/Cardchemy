# Approved Subject-scoped RAG implementation plan update

Date: 2026-09-17

## Scope and starting context

The operator approved all recommendations from the
[source-grounded review](2026-09-17-flashcard-prompts-and-rag-plan-review.md)
and explicitly requested updating
[Cardchemy-Subject-Scoped RAG Implementation Plan.md](<../../../Cardchemy-Subject-Scoped RAG Implementation Plan.md>).
This task changes the plan and dated evidence only; it does not implement RAG,
change configuration/source/schema, deploy, or make paid provider calls.

- Branch: `main`; HEAD: `e10f5839735379e4277d35600067835f53272a89`.
- Starting tracked change: `.agent/logs/README.md` contained the prior review entry.
- Starting untracked files: the original plan and prior review log. They were
  preserved; the plan was updated in place under the operator's authorization.
- Root guidance, canonical orientation/maps, relevant source/contracts and
  historical evidence were read during the preceding comprehensive review.
  This update rechecked guidance, current tree, original plan, review findings,
  template key names and documentation validator behavior.
- `.agent/AGENTS.md` is absent. No component environment files were introduced.

## Approved decisions and resulting plan

The existing Phase 12–21 numbering is retained. Two preparations precede RAG:

1. Measure/refine flashcard prompts and bounded refill context. Version prompts,
   use realistic feasible/insufficient fixtures and content-free rejection/yield
   diagnostics, account for exclusions in packing/budgets, and compare quality,
   coverage, success rate, usage and latency. Preserve intentional
   `insufficient_grounded_cards`, strict validation and atomic complete results.
2. Hard-rename all 29 current `AI_*` template names to `FLASHCARD_AI_*`, remove
   `GEMINI_API_KEY` fallback, add independent `RAG_AI_*` and `RAG_EMBEDDING_*`
   profiles, and require safe old-key detection/migration without aliases.
   Preserve installation secrets, queued snapshot contracts, worker-only
   credentials, independent enablement and actual shared account/project quotas.

The revised RAG phases specify:

- Independent instructor Knowledge review/publication. Ready/private documents
  cannot enter student retrieval; flashcard publication does not publish Knowledge.
- Mandatory-extension versus optional-installation support decision before
  runtime/schema changes, complete PostgreSQL consumer inventory, reviewed pinned
  artifacts, native privileges, portable offline fixtures and recovery coverage.
- Persistent canonical pages and revision-aware chunks, subject-consistent
  associations/FKs/deletion rules and permanent storage caps.
- Short fenced atomic private capture/index enqueue before temporary-source
  cleanup, independent of flashcard success and embedding execution.
- Complete durable indexing schema in Phase 13, capture enqueue in Phase 14,
  execution/recovery in Phase 15; compatible embedding spaces, staged cutover,
  bounded retry owners and independent worker lanes.
- Principal/Subject/publication/revision predicates inside both retrieval queries,
  worker query embeddings and separately authorized sources/history/endpoints.
- Durable own-conversation answer jobs, bounded admission/idempotency/fencing,
  explicit abstention and evidence relationships. Citation IDs and quote
  containment are not presented as proof of arbitrary prose's semantic truth.
- Early evaluation corpus, phase-specific tests, independent Knowledge publication
  in the deterministic journey, safe frontend rendering/typed English copy,
  privacy/export/delete draining and populated vector/text/chat recovery.

All 208 implementation checklist items remain unchecked. No current-state,
roadmap, ADR or changelog was changed to claim implementation.

## Decisions deliberately left open

Approval of recommendations does not choose undocumented product/model defaults.
Six blocking gates now make dependencies explicit:

- G1: Installation/extension support, artifact identity, privileges and ownership.
- G2: Conversation retention, history/citation behavior after content changes,
  and instructor own-chat scope; subject ownership does not expose student chats.
- G3: After-capture cancellation and independent capture-failure/recovery outcomes.
- G4: Knowledge-only upload versus regeneration and within-Subject version handling.
- G5: Provider/model/task/dimensions/representation, embedding space and retrieval
  thresholds, including decisions required before vector schema creation.
- G6: Worker/credential topology, fairness, actual quota buckets and replica limits.

Resolve and record each gate before its dependent implementation. Live spending,
deployment and destructive schema/data operations retain their separate gates.

## Independent review and corrections

A read-only subagent compared the rewritten plan with the complete approved
review and original phase contracts/exclusions. It found two actionable wording/
ordering issues, both corrected:

1. Capture needs a durable indexing enqueue target before Phase 14. The indexing
   schema/claim-field requirement is now in Phase 13; Phase 15 implements execution.
2. G2 permits a reviewed narrowly authorized historical-version policy. History
   and source-read wording now follows that resolved policy with current access
   checks; new retrieval/answers require eligible active published revisions.

The review found no additional missing approved recommendation or invented
provider/model/dimension/retention/cancellation choice. A follow-up read confirmed
both corrections and the earlier G5 schema dependency; no actionable findings remain.

## Verification and limits

- Direct standard-library plan validation passed: 859 lines, Phases 12–21 exactly
  once/in order, two preparations, six explicit gates, all 29 template AI key names
  mapped exactly, 17 local links/anchors resolved, 208 unchecked tasks, balanced
  code fences, no trailing whitespace and a final newline.
- The root plan is outside `scripts/check_context.py`'s active-guide inventory;
  therefore its links were checked explicitly using the same validator helpers.
- Original-plan temporary backup SHA256 matched
  `AF530620C81712B2B626BE736E208EC3DAFE8B193F13DCCB9C57C3152EF3FD61`.
- Original-versus-updated no-index diff was reviewed. Git's return code 1 denotes
  changed files in this comparison; its whitespace check reported no defects.
- `python scripts/check_context.py` passed: 37 required files, 61 active guides,
  789 local links. The new evidence log's two local links and whitespace passed
  direct validation; `git diff --check` passed for tracked changes.
- HEAD remained unchanged. The prior review log's SHA256 remained
  `2C9DC0DFC6952AC45C4675CB6D5B244ECD04D0556459E5DA1BFE9896C9C855B1`.
  The index retains its existing review entry and adds only this update entry.
- The prior review's 376 backend passes/42 focused AI passes are cited as baseline
  evidence, not rerun or relabeled as RAG validation. No application tests or live
  provider/service/frontend/deployment checks are needed to claim this plan edit.

An initial oversized PowerShell write failed before process creation with Windows
error 206 (command too long), without modifying files. The plan was then written
successfully with the file patch tool; no dependency or runtime changes were made.

## Preservation and cleanup

Real `.env` values were not read, printed or changed. Signing/encryption/database
secrets, source, migration history, data/volumes and unrelated files were preserved.
The historical review body remains unchanged. Only the approved plan, this new
dated evidence record and the nearest log index are modified by this update.

The task-specific original-plan backup was removed after comparison and validation.
Its resolved path/filename were checked against the intended temporary directory;
absence was verified afterward. No recursive or unrelated cleanup was performed.
