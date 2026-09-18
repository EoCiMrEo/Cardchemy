# Phase 4 remediation - grounded, bounded, portable AI generation

Date: 2026-09-14

## Scope and repository context

- Completed every item under Phase 4 in `issues-required-remediation.md`.
- Phase 3 changes were already present and uncommitted at the start of this
  work. They and all unrelated work were preserved; no reset or checkout was
  used.
- `/.agent/AGENTS.md` was not present. Existing `.agent/logs/` entries and the
  Phase 2/3 migration, queue, retention, and UI contracts were read before
  implementation.
- Three subagents audited the AI pipeline, provider/cost portability, and
  evaluation strategy. Their findings converged on direct provider adapters,
  strict typed output, server-owned provenance, deterministic validation,
  exact global allocation, and an offline release corpus. Root integrated and
  verified their scoped work.

## Provider and configuration contract

- Added a provider-neutral `AIProvider` protocol with adapters for Gemini and
  OpenAI-compatible Chat Completions endpoints.
- Both adapters keep system instructions separate from untrusted document
  data, request native strict JSON Schema output, validate again with strict
  Pydantic models, normalize usage, bound response size, and return safe public
  errors.
- Centralized and validated provider, versioned model, temperature, output and
  context windows, request timeout, retry jitter, concurrency, chunk/summary
  limits, per-job token ceilings, refill rounds, duplicate threshold, current
  operator-supplied prices, and cost ceiling.
- Production rejects preview/latest/experimental model identifiers unless the
  operator explicitly enables them. The default stable Gemini identifier and
  required provider capabilities are documented with official lifecycle,
  structured-output, and token-usage references.
- Each job snapshots its provider and model. Estimated and actual input/output
  tokens, micro-US-dollar cost, estimated-usage flag, accepted/rejected counts,
  and paired limit reason code/message are persisted and returned by the API.
- Applied the generation-persistence guidance by making each durable job the
  addressable accounting record for model identity, usage, cost, quality, and
  failure reason.

## Grounded quality pipeline

- PDF extraction now returns ordered page objects, including empty page
  placeholders, so native extraction and optional OCR preserve page numbers.
- Replaced raw character windows with page-, heading-, paragraph-, and
  token-aware chunks. Each chunk receives a server-issued ID plus page/section
  provenance.
- Replaced first-30,000-character summarization with map summaries over every
  chunk and bounded hierarchical reduction. Missing or unverified summary
  coverage fails visibly as `summary_generation_failed` and retains retry
  behavior.
- Uses largest-remainder allocation so all chunk quotas sum to the requested
  total. Refill rounds are bounded; success requires exactly the requested
  number of cards, otherwise the transaction fails without a partial set.
- Provider candidates have a strict four-option contract and no confidence
  field. The server verifies the named chunk, exact normalized source quote,
  answer containment, canonical options, clarity, and meaningful distractors.
  Page and section are derived from trusted server state, not model output.
- A deterministic second pass calculates a quality score and rejects near
  duplicates using normalized token, character, and answer similarity.
  Generated cards always start unapproved and require an instructor action.
- Per-call context checks and conservative whole-job preflight estimates reject
  work before an over-limit request. Runtime token/cost counters enforce the
  configured cumulative ceilings and are retained on failures.

## Database, API, and frontend

- Added reversible Alembic revision `20260914_0003` for generation telemetry,
  constraints, `quality_score`, `source_snippet`, `source_page`, and
  `source_section`.
- Aligned agent state, API schemas, ORM fields, services, worker persistence,
  and frontend types around the same canonical multiple-choice card shape.
- The limits response now reports provider/model, pricing availability,
  generation availability, and exact unavailability reasons. Job cards show
  provider/model, estimated/used tokens, estimated/recorded cost, validated and
  rejected counts, and limit/failure messages.
- Instructor review renders verified quote plus page/section. Model quality no
  longer auto-approves a card.
- The React quality checklist led to functional state updates, complete effect
  dependencies, explicit form labels/live regions, typed data, and retry-safe
  limit polling.

## Dependency and documentation cleanup

- Replaced LangChain, LangChain Google, and LangGraph runtime dependencies with
  direct `google-genai` and `httpx` dependencies; regenerated both hashed lock
  files. `pip check` reports no broken requirements.
- No pgvector, embedding, vector database, or RAG implementation/claim remains.
  `idea.md` now describes the shipped source-grounded provider-neutral design.
- Added `docs/AI_GENERATION.md`, `docs/AI_PROVIDERS.md`, and
  `docs/AI_EVALUATION.md`; aligned dependency, PDF-generation, database, env,
  Compose, and changelog documentation.

## Runtime findings resolved

- Browser verification found FastAPI's dynamic `/flashcards/{flashcard_id}`
  route shadowing `/flashcards/generation-limits` and
  `/flashcards/generation-jobs`, producing 422 responses. Static generation
  routes now register first, with a regression test protecting the order.
- The same run showed that a failed initial limits request was not retried after
  the jobs endpoint recovered. Polling now continues requesting limits until
  it succeeds, so submission cannot remain incorrectly enabled or omit the
  provider reason after a transient startup failure.

## Verification evidence

- Offline AI/PDF quality suite: `29 passed`, including exact 1/5/8-card corpus
  targets, strict schema failures, grounding, near-duplicate rejection,
  injection boundaries, long-document beginning/middle/final coverage,
  provider parity, context/preflight refusal, usage, cost, and structured pages.
- Full local backend suite: `81 passed, 12 skipped, 1 deselected`.
- Isolated PostgreSQL suite: `12 passed, 81 deselected`. A new database migrated
  from empty through revisions 0001/0002/0003; `alembic current --check-heads`
  reported 0003 and `alembic check` reported no drift.
- Phase 4 downgrade to 0002 and re-upgrade to 0003 succeeded with test data.
  The disposable database was then dropped.
- The existing local application database was upgraded from 0002 to 0003 and
  passed both head and schema-drift checks.
- Phase 4 frontend ESLint scope passed with zero warnings/errors. Production
  TypeScript/Vite build passed with 2,296 modules; only the existing
  Browserslist-age and bundle-size advisory warnings remain.
- `docker compose config --quiet`, Python compilation, `pip check`, regenerated
  dependency-lock scans, and `git diff --check` passed.
- Supervised browser checks rendered the generation form, stable provider/model
  and pricing status, then an intentionally unconfigured-provider state with a
  disabled submit button and the exact remediation message. Browser console
  warning/error logs were empty.
- The disposable browser-QA instructor, subject, and auth sessions were removed
  by database cascade after testing; they are not recoverable or retained.

## Operational notes

- No live AI request was made, so verification incurred no provider charge.
  Remote model output and pricing can drift; a release owner must deliberately
  run the opt-in live corpus for each configured production model after setting
  current prices.
- Normal Compose startup still requires a root `.env` with strong
  `POSTGRES_PASSWORD`, `SECRET_KEY`, and an independent
  `GENERATION_SOURCE_ENCRYPTION_KEY`. Validation and browser checks used only
  disposable process-scoped values; no secret was written to project files or
  this log.

