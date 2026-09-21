# Subject-scoped RAG capture, indexing and retrieval closure

Date: 2026-09-19

Scope: implement and close Phases 14, 15 and 16 of the approved
`Cardchemy-Subject-Scoped RAG Implementation Plan.md`. Phase 17 answer jobs,
chat/API/UI, Phase 19 corpus-scale quality tuning, live provider evaluation and
production enablement remain outside this scope.

## Starting context and preservation

Work started from `main` at `479f56f597ff5a13410d01cad433ef075da260bd`
with a clean worktree. Root `AGENTS.md`, canonical orientation/maps, current
state, RAG ADRs, backend maps, AI/PDF/database/privacy/deployment/testing guides
and relevant dated logs were read before implementation. The existing Phase
12–13 pgvector/Knowledge foundation and accepted ADR-012 boundaries were treated
as authoritative.

The real root `.env`, installation secrets, user data and operator volumes were
not read, rewritten or removed. All provider behavior used deterministic local
fakes; no paid embedding or generation request was authorized or made. Three
bounded Phase 14/15/16 subagent audits were dispatched as requested. Their
remote authentication/usage failures were not treated as evidence; any partial
work was reviewed against source, tests and the approved contracts before it was
retained.

## Approved decisions applied

- A combined generation cancellation after capture removes the captured private
  Knowledge revision/document when newly created and cancels indexing. A normal
  flashcard failure may retain valid private Knowledge. A Knowledge-only
  cancellation removes its captured revision.
- `knowledge_only` is an explicit durable job kind using the existing encrypted
  source queue, separate admission limits and no flashcard-provider dependency.
- Idempotent replay applies only to the same operation. A changed PDF creates a
  revision only with an explicitly authorized existing document ID; otherwise it
  creates a new document.
- Supported capture bound/capacity failures are independent of successful
  flashcards. Cancellation, ownership, lease and ambiguous integrity failures
  fail closed.
- Reindex cutover is explicit and requires a ready compatible target for every
  active ready content revision. A failed stage/cutover preserves the old corpus.
- Retrieval uses exact authorized cosine search plus PostgreSQL FTS and
  deterministic reciprocal-rank fusion. ANN remains disabled until measured
  Phase 19 evidence supports it. Query embedding stays in a credential-bearing
  worker; Phase 17 owns public answer-job/API work.

## Phase 14 implementation

- Added immutable `PreparedDocument` preparation so extraction/chunking happens
  once and the existing graph/pipeline consumes the same validated chunks used
  by Knowledge capture. Existing PDF/OCR subprocess, packing, allocation and
  grounding behavior remains intact.
- Added a short fenced capture transaction that rechecks claim, lease,
  cancellation and Subject ownership; writes canonical pages, stable local-to-
  persistent chunk provenance, content/index revisions and one durable index job
  atomically.
- Added stable capture replay, bounded private capture outcomes, explicit
  `knowledge_only` admission/route/schema, independent quotas, existing-document
  revision targeting and transient encrypted-source cleanup.
- Integrated capture before the flashcard pipeline, so exact-count generation
  failure cannot roll back valid private Knowledge and successful flashcards do
  not wait for embeddings. Cancellation and recovery remove or retain capture
  according to the approved semantics.

Primary paths: `backend/app/ai/chunking.py`,
`backend/app/services/knowledge_capture.py`,
`backend/app/workers/generation.py`, `backend/app/services/generation.py`,
`backend/app/routers/generation.py` and `backend/app/schemas/generation.py`.

## Phase 15 implementation

- Added a separate strict OpenAI-compatible embedding adapter. It validates
  response size, index/order, dimensions, finite float32 values and non-zero
  cosine vectors, while retaining one application retry owner and bounded
  timeout/rate/token/cost telemetry without content logging.
- Added the dedicated durable index worker and entry point with fixed worker kind,
  health pulses, `SKIP LOCKED` claims, leases, heartbeats, cancellation, fenced
  batch persistence, terminal post-provider failures and pre-provider dead-lease
  recovery.
- Added staged index construction and all-or-nothing embedding-space cutover.
  Reindexing reconstructs bounded chunks from canonical stored pages, so it does
  not need the deleted raw PDF. Failed cutover keeps the old active index.
- Added migration `20260919_0011`, task-mode/identity constraints, telemetry and
  exact index-job execution state. Compose now runs `index-worker` with only the
  embedding credential; generation, API, email and browser roles do not receive
  it. The guarded production rehearsal now inventories, builds, validates,
  health-checks and drains this service.

Primary paths: `backend/app/ai/embeddings.py`,
`backend/app/services/knowledge_indexing.py`,
`backend/app/workers/knowledge_index.py`, `backend/app/index_worker.py`,
`backend/alembic/versions/20260919_0011_rag_capture_indexing.py`,
`docker-compose.yml` and `scripts/test_production_rehearsal.py`.

## Phase 16 implementation

- Added a reusable internal `KnowledgeRetriever` that authorizes the trusted
  principal and actual Subject before retrieval. Instructor ownership and student
  enrollment are rechecked; student rows require reviewed/published Knowledge.
- Both exact-vector and `english` PostgreSQL FTS candidate CTEs contain Subject,
  document, publication, ready, active revision and embedding-space predicates.
  Retrieval never performs a global search followed by application filtering.
- Candidate sets, top-K, context tokens and overlap are bounded. Deterministic
  RRF fusion/deduplication returns server-derived document/chunk/title/page/
  section/revision metadata with rank semantics, not a fabricated confidence.
- Source reads reauthorize current access and corpus revision. Guessed document
  or chunk IDs, cross-Subject access, unpublication, inactive/not-ready revisions
  and incompatible embedding spaces fail closed.

Primary path: `backend/app/services/knowledge_retrieval.py`. There is deliberately
no public retrieval/answer route in this phase.

## Verification evidence

Passing evidence on the final source:

- Focused AI/capture/index/retrieval/runtime/config/rehearsal guards: 103 passed.
- Complete backend offline suite: 692 passed, 84 service-gated skips and one
  explicitly deselected live-AI case in 83.89 seconds.
- Disposable PostgreSQL/pgvector suite: 69 passed, three gated skips and 705
  deselected. Fresh migration reached `20260919_0011`; head and Alembic drift
  checks passed; full downgrade to base, re-upgrade to head and repeated head/
  drift checks passed. Owned container/data/credential cleanup was confirmed.
- Real PostgreSQL RAG contracts cover capture, batches, vector writes, exact
  cosine plus FTS retrieval, instructor/student authorization, publication and
  corpus fences, guessed document/source rejection, mixed-space rejection,
  partial batch failure, stale claim fencing and dead-lease policy.
- Full deterministic browser/API/worker journey passed with one extraction
  producing completed flashcards plus private pending Knowledge/index work, then
  review/publication/enrollment/study proof and source cleanup. Embedding/provider
  network calls remained disabled; all owned resources were removed.
- Frontend `npm run check` passed: typecheck, lint, four unit tests, 31 component
  tests, coverage thresholds, production build and 53 Chromium cases with one
  gated skip.
- AI configuration migration preflight, base Compose configuration and
  production-profile Compose configuration with process-only non-secret SMTP
  placeholders passed. The private root `.env` was unchanged.
- `scripts/check_ci.py`, `scripts/check_runtime_artifacts.py`,
  `scripts/check_release.py --version 0.1.0`, and 18 script tests passed. The
  published version remains 0.1.0; phase closure is not a release.

Final context validation passed with 37 required files, 67 active guides and
910 local links. `git diff --check` reported no whitespace errors (only the
repository's existing Windows line-ending notices), and an explicit plan scan
reported 40 checked and zero unchecked items between Phase 14 and Phase 17.

## Failed attempts and non-evidence

- One sandboxed Docker run could not access the engine pipe. An approved retry
  reached Docker but used the system Python, which lacks the backend Alembic
  runtime; it cleaned up and is not test evidence. The documented backend virtual
  environment then ran the passing disposable suite above.
- The first production Compose configuration check correctly rejected missing
  required production SMTP values. A second non-secret process-only fixture
  supplied the required shape and passed; no operational SMTP claim is made.
- A new page-rebuild unit initially referenced an ORM chunk field on the prepared
  contract. The field mapping was corrected and both focused and complete suites
  were rerun; the failed run is not evidence.

## Limits and deferred work

- RAG remains disabled by default. No public Ask AI endpoint, conversation,
  answer worker or UI was added; those begin in Phase 17.
- Exact cosine is the approved Phase 16 baseline. Approximate-versus-exact recall
  and iterative-scan settings are not applicable while ANN is absent; the full
  authored corpus, relevance thresholds and any ANN/reranker decision remain
  Phase 19 work.
- No live model quality, current provider pricing, production deployment,
  external SMTP, hosted CI or clean committed Linux production-rehearsal result
  is claimed. The production rehearsal requires that separate supported host/
  checkout gate.
- No temporary raw PDF is retained. Reindex is possible only while canonical
  stored pages remain; deleted uncaptured source requires an authorized reupload.
