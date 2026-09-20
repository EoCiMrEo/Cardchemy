# Subject Knowledge RAG Phase 20/21 technical closure

Date: 2026-09-20

## Scope and starting context

This record covers Phase 20 integrated verification, the implemented Phase 21
privacy/operations/recovery controls, existing-data policy and the active
definition-of-done closure of the
[Subject-scoped RAG implementation plan](../../../Cardchemy-Subject-Scoped%20RAG%20Implementation%20Plan.md).
The work started on `main` at `479f56f` with a large user-owned dirty working
tree containing the approved Phases 12–19 implementation. That state and the
real root `.env` were preserved. Configuration was inspected only through
presence/provider-safe checks; no key or credential value was printed. The
operator explicitly authorized bounded live Gemini spending, root `.env`
updates and deletion of the current Compose volumes for empty-volume startup.

Before editing, the repository guide, canonical orientation/project/module
maps, current state, RAG plan, accepted ADRs, architecture/operations/testing
guides and the relevant 2026-09-17 through 2026-09-19 logs were read. Three
bounded subagent audits were requested for Phase 20, Phase 21 and final
checklist coverage. Their later runs were unavailable because the agent service
reported a usage-limit reset, so the primary agent re-audited those scopes.

## Implemented behavior

### Native Gemini RAG profiles

- The answer provider now supports native Gemini structured output for the
  RAG answer/support role without changing the existing flashcard contract.
  Billed output accounts for both candidate and thinking tokens.
- The embedding adapter uses Gemini `embedContent`, fixed 1,536-dimensional
  normalized cosine vectors, `RETRIEVAL_DOCUMENT` for stored chunks and
  `QUESTION_ANSWERING` for queries. It retains strict count/order/finite-
  value/dimension checks, the single bounded retry owner, governor admission,
  time/token/cost ceilings and OpenAI-compatible support.
- The embedding identity is now the canonical length-framed ten-field tuple:
  provider, endpoint, model, revision, format, dimensions, representation,
  metric and both task modes. No credential enters the identity.
- The default RAG profile, template, live-evaluation guards and cost floors now
  use the official Gemini endpoint, `gemini-embedding-001` and
  `gemini-3.5-flash`. The separately guarded live RAG harness allows at most
  one query embedding, one answer and one support call, zero retries, 12,000
  input tokens, 1,024 answer-output tokens, 60 seconds and USD 0.04.
- Gemini 3 text roles omit sampling parameters and pin a validated thinking
  level. Flashcard live evaluation uses `minimal`, and the bounded factual RAG
  answer/support role also uses `minimal`; reported thinking tokens remain part
  of output usage and cost.

### Phase 21 privacy and operations

- Added an authorized, credential-free Subject RAG profile response and browser
  disclosure before an enabled Knowledge upload or Ask AI question.
- Added request correlation/stage timings for index/answer jobs, fixed-field
  Knowledge publish/unpublish/removal audits, content-free RAG queue/throughput/
  latency/rejection/usage metrics and explicit healthy-disabled versus stalled
  worker semantics.
- Extended consistent-snapshot export to instructor-owned Knowledge and only
  the requester's private conversation/job/source rows. Vectors, credentials,
  tokens, internal hashes and other students' chats remain excluded.
- Account, Subject and document deletion acquire the ordered Knowledge writer
  boundary and refuse active generation/capture/index/answer work. Cascades
  fence stale claims and document removal detaches rather than deletes surviving
  flashcards.
- The existing 90-day default private-message/source retention is applied by
  bounded operator cleanup; database deletion cannot erase provider copies,
  backups, delivered mail or previously exported private files.
- Alembic head `20260920_0013` carries Gemini identity constraints, correlation/
  timing fields and audit constraints. Its downgrade explicitly removes data
  that the older schema cannot represent while retaining canonical pages for a
  future reindex; it is not a live-data rollback procedure.

### Integrated and recovery coverage

- The real browser journey now runs two isolated stacks. RAG-off proves normal
  flashcard generation/publication and temporary-source cleanup with no RAG
  credentials/workers/records. RAG-on proves independent Knowledge publication,
  enrolled-user grounded Ask AI, exact current citation evidence and a `404`
  for cross-Subject thread access.
- The clean-production recovery harness now seeds a provider-disabled synthetic
  page/chunk/1,536-vector/conversation/job/citation fixture through legal state
  transitions and verifies extension/index identity, active publication,
  authorized exact retrieval, private history and three-principal isolation
  before and after a separate-empty-volume restore.
- The smaller pgvector recovery probe also verifies vector and lexical indexes,
  active/published filters and enrolled/other-student isolation.
- Configuration, privacy, AI, database, deployment, testing, architecture,
  project/module maps, current state and changelog were aligned to implemented
  behavior. Release defaults retain `RAG_ENABLED=false`, and the documented
  reversal drains/disables RAG without deleting durable Knowledge.

## Problems found and resolved

- The first security attempt reached the scan stage without the three expected
  local image tags and therefore stopped before container scanning. The exact
  backend, OCR and frontend runtime targets were built and the complete gate
  was rerun.
- Gitleaks identified eight high-entropy-looking unit-test idempotency fixtures.
  They were not credentials; the fixtures were shortened to explicit low-
  entropy test labels instead of adding broad ignores. The rerun reported no
  leaks.
- One backend rerun used the system Python, which lacked the maintained
  development dependencies, and stopped while loading `conftest.py`. That run
  is non-evidence; the authoritative backend virtual environment then passed.
- Native Gemini space hashing initially disagreed with the earlier eight-field
  database trigger. Revision `0013` replaces it with the canonical ten-field
  guard and full downgrade/re-upgrade verification passes.
- The first authorized RAG live call returned a response truncated by the
  original 512-token answer ceiling; the bounded harness made no retry. Raising
  the answer ceiling to 1,024 exposed a second no-retry timeout caused by the
  provider's default thinking effort. The explicit `minimal` thinking setting
  brought the final current-code live run inside its limit.
- An empty-volume Compose start initially left the backend and AI workers
  unhealthy because Compose still substituted pre-decision OpenAI URL and
  8,192-dimension defaults when native Gemini base URLs were intentionally
  blank. The Compose defaults were aligned with the root template and protected
  by a configuration regression test. After the authorized project-volume
  removal, all application services became healthy and migration exited zero.
- The first exact CI coverage rerun failed its unchanged 73% overall, 77% line
  and 55% branch floors. Targeted answer-worker completion and lifecycle tests
  increased measured coverage without lowering any budget; the final gate
  passed all three floors.
- The release production rehearsal was attempted from a clean isolated commit
  of the Git-visible working tree. It refused immediately with
  `linux_host_required` on this Windows host, before credentials or containers
  were created. This is recorded as non-evidence rather than a pass.

## Verification evidence

- Complete backend offline suite: `744 passed, 96 skipped, 2 deselected` before
  the final coverage additions. The exact CI coverage selection then passed
  `747 passed, 98 deselected` with 73.32% overall, 77.09% line and 57.47%
  branch coverage against unchanged 73%/77%/55% floors.
- Native Gemini/affected RAG focused suites: `40 passed`, then `57 passed`;
  privacy lifecycle focused suite: `26 passed`; recovery guard/safety suite:
  `39 passed`.
- Disposable PostgreSQL/migration gate: `81 passed, 3 skipped, 758 deselected`;
  current head/drift, downgrade to base and re-upgrade to `20260920_0013`
  passed and generated resources were removed.
- Complete frontend `npm run check`: typechecks, lint, 4 Node units, 31
  component tests, 96.65% statements/85.16% branches/93.1% functions/97.84%
  lines, production build, and `56 passed, 1 skipped` Chromium cases. The skip
  is the separately configured live password-reset case.
- Two-stack deterministic full journey passed, including RAG-off, unpublished
  Knowledge, grounded RAG-on, cross-Subject denial, persisted database outcomes
  and final resource cleanup.
- Mailpit: `3 passed, 839 deselected`; encrypted SMTP/recovery: `12 passed`.
- Database artifact scan/SBOM, prior-installation logical-volume upgrade,
  populated Knowledge restore and pgvector restore all passed on owned
  disposable resources.
- Isolated security gate: no Git/worktree leaks and no HIGH/CRITICAL findings
  for backend, OCR backend or frontend; CycloneDX SBOMs/checksums retained under
  ignored `artifacts/security`. Exact runtime checks for all three images passed.
- Release metadata, four CI workflows/protection/budget contracts, configuration
  migration and reviewed database runtime identity passed.
- Context validation: 37 required files, 68 active guides and 966 local links.
  `git diff --check` passed with line-ending notices only.
- Authorized live flashcard generation passed on the pinned native
  `gemini-3.5-flash-lite` profile: `1 passed, 19 deselected` in 3.47 seconds.
  Authorized live Subject RAG passed on `gemini-3.5-flash` plus
  `gemini-embedding-001`: `1 passed, 10 deselected` in 27.25 seconds. Both used
  explicit quota/cost/time/request ceilings, zero retries and content-free
  reporting.
- The current root configuration started successfully after an empty project
  volume with database, backend, frontend, generation/index/answer/email
  workers and Mailpit healthy; migration exited zero and `/healthz` returned
  HTTP 200. The real-browser login surface had correct accessible names, native
  required-field focus/error behavior and no browser console warning/error.

## Limits and remaining gates

The live results establish only the tested provider profiles at that time; they
do not prove future availability, provider billing completeness or every
production Subject. No current-source Linux clean-production rehearsal is
claimed from the Windows refusal. A post-merge fresh-clone Compose run, hosted
required CI/rehearsal, actual production enablement and a release-specific
human spoken assistive-technology pass remain open at this checkpoint.

Product version remains 0.1.0. The user-authorized Cardchemy Compose volumes
were removed for the empty-volume proof; generated service/journey/recovery
resources were otherwise cleaned or retained only as ignored content-free
reports. No credential or private content was recorded in this log.
