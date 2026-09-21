# Subject Knowledge frontend and RAG evaluation closure

Date: 2026-09-19

## Scope and starting context

This record closes only Phases 18 and 19 of the active
[Subject-scoped RAG implementation plan](../../../Cardchemy-Subject-Scoped%20RAG%20Implementation%20Plan.md).
The work began from a dirty working tree containing the approved and tested
Preparation A/B and Phases 12–17 implementation. Existing changes, the private
root `.env`, database volumes and user data were preserved. The canonical
orientation, project/module maps, accepted ADR-012, current state, RAG
architecture/evaluation guidance and relevant 2026-09-17 through 2026-09-19
agent logs were read before implementation. Three bounded subagent audits
independently covered Phase 18, Phase 19 and cross-cutting documentation/config
gaps.

No paid provider call was authorized or made. All documents, conversations,
accounts and credentials used by verification were synthetic and disposable.

## Decisions retained

- Flashcard generation/publication and Knowledge review/publication remain
  independent. An instructor may use Ask AI, but only currently eligible
  published Knowledge is retrievable.
- Knowledge-only reupload creates a new immutable content revision. Failed
  indexing can rebuild from canonical persisted pages without the deleted raw
  PDF; a missing/deleted capture requires a new PDF upload.
- Raw PDFs remain temporary. There is no PDF viewer; citations expose only the
  current authorized document title, page, optional section and exact evidence.
- Retrieval stays `hybrid_exact_v1`: top 5, exact cosine plus PostgreSQL
  `simple` FTS, RRF `k=60`, similarity floor 0.5, overlap threshold 0.8 and
  8,192-token context. The measured corpus did not justify ANN, a reranker or
  RAG-specific chunking.
- Live RAG testing remains separately opt-in with two authorization flags,
  pinned endpoint/models, three physical calls, zero retries, one-call
  concurrency, 12,000 input/1,024 answer-output tokens, 60 seconds and USD 0.02.

## Phase 18 implementation

### Backend contracts needed by the UI

- Added owner-only Knowledge document list/detail, review-and-publish,
  unpublish, stored-page index retry and card-preserving delete contracts in
  `backend/app/routers/knowledge.py`,
  `backend/app/services/knowledge_management.py` and
  `backend/app/schemas/knowledge.py`.
- Added immutable fresh index-revision enqueue from stored pages and made every
  retry operation identity target the new revision.
- Added owner-private answer-job listing so the browser can recover queued,
  running and terminal jobs after reload.
- Admission now rejects an empty eligible published corpus before persisting a
  question/job. Knowledge and RAG mutating routes detach the authenticated
  principal before rollback, avoiding asynchronous expired-object access in the
  real API request lifecycle.

### Browser behavior

- Added typed `knowledge.ts` and `rag.ts` services plus complete contracts in
  `services/types.ts`; no `any`, raw HTML rendering or untrusted links were
  introduced.
- Added `KnowledgeArea` to instructor Subject details without changing the
  normal Generate Set flow. It exposes capture, content revision, index,
  review/publication and retry states; supports upload/new revision,
  review/publish, unpublish, stored-page retry and removal; and explains when a
  PDF reupload is required.
- Added `AskAiPanel` to instructor and student Subject pages. It owns only the
  signed-in principal's threads, restores history/jobs after reload, performs
  nonoverlapping abortable polling, preserves one idempotency key for one
  logical retry, displays every durable job outcome and opens current evidence
  in a keyboard/focus-safe dialog.
- All copy lives in `frontend/src/i18n/en.ts`. The implementation preserves
  text equivalents, live regions, reduced motion, touch targets and mobile
  overflow protection.
- Added deterministic Chromium coverage for independent Knowledge publication,
  safe model text, authorized citation evidence, reload/retry identity,
  accessibility and a 360-pixel viewport.

## Phase 19 implementation

- Added `subject_knowledge_v2.json` covering direct/paraphrased/technical,
  cross-lecture, multi-page, overlap and follow-up cases; ambiguity,
  unsupported/empty/conflicting evidence; lecture/chat injection;
  cross-Subject/guessed IDs; unpublished Knowledge; unrelated real citations;
  unsupported claims with valid IDs; and queued/running lifecycle changes.
- Added a deterministic metric evaluator for recall@K, MRR, claim support,
  abstention, citation validity, forbidden exposure, overlap, p95 query latency,
  indexing throughput, bounded history and provider-call stages.
- Added actual PostgreSQL exact hybrid evaluation with deterministic semantic
  vectors and an assertion that no HNSW/IVFFlat index exists. All reviewed gates
  passed, so no tuning budget or security threshold was weakened.
- Strengthened semantic support from quote entailment alone to require original-
  question relevance and absence of contradiction while reviewing all retrieved
  context.
- Added the hard-bounded live RAG harness. Its guards were tested offline; the
  live case stayed deselected.
- Extended the real browser journey with deterministic embedding/answer/support
  providers, an unpublished-Knowledge negative step, independent instructor
  publication, a student grounded answer/citation and the existing study flow.

## Problems found and resolved

- The first real journey exposed an expired SQLAlchemy principal after a route
  rollback. The mutating routers now preserve the authenticated identity
  without touching expired ORM attributes; the real journey subsequently
  passed.
- Ask AI admission initially allowed a durable question/job when the eligible
  corpus was empty. Authorization now counts eligible chunks under the same SQL
  scope and fails with the fixed no-Knowledge error before writes.
- The PostgreSQL harness first could not connect because Docker Desktop was not
  running. Docker was started, then every owned disposable container was
  inventoried and cleaned.
- A PostgreSQL assertion expected the no-Knowledge response while its fake
  answer lane was disabled, so provider-unavailable correctly won first. The
  isolated fixture now enables the fake answer lane without network access.
- The all-state browser contract exposed a controller-ownership race: cleanup
  for a running conversation poll could abort a newly selected conversation's
  load. Polls now own and abort only their local controller; running-to-failed/
  cancelled thread switching passes.
- The PostgreSQL reindex lifecycle case exposed a stale server-triggered corpus
  revision in newly staged index-job snapshots. Reindex staging now flushes and
  refreshes the Subject revision before creating immutable jobs; the regression
  covers unpublish, delete and reindex during queued/running answers with zero
  answer-provider calls.
- The service harness now emits only static failing test identities and source
  line numbers; captured credentials, fixture content and exception values
  remain withheld.

## Verification

- Backend focused Knowledge/RAG contracts: `25 passed`.
- Knowledge/RAG API authorization/state cases: `4 passed`.
- Live RAG authorization guards: `9 passed, 1 deselected`; the deselected case
  is the paid provider call.
- Complete backend offline suite: `719 passed, 91 skipped, 2 deselected` in
  101.83 seconds. Skips are service-gated; deselections are live AI cases.
- Disposable PostgreSQL/migration gate: `76 passed, 3 skipped, 733 deselected`
  in 55.67 seconds; head/drift, full downgrade to base and re-upgrade to
  `20260919_0012` passed. Services and generated credential file were cleaned.
- Complete frontend `npm run check`: application/E2E/component typechecks,
  lint, 4 Node units, 31 component tests, 96.65% statements/85.16% branches/
  93.1% functions/97.84% lines, production build, and `56 passed, 1 skipped`
  Chromium tests. The skip is the separately gated live password-reset case.
- Targeted final rendered Knowledge/Ask AI browser verification: `3 passed`;
  both desktop captures were visually inspected and the student test also
  proved no 360-pixel horizontal overflow.
- Full disposable real journey: database proof and browser contract passed for
  generation, independent Knowledge index/review/publication, enrollment,
  grounded Ask AI citation, email, cards and progress; all processes,
  containers, data, fixture and generated credentials were cleaned.

## Limits and follow-on scope

No live embedding/answer quality, remote latency, current provider availability
or billing completeness is claimed. No ANN index or reranker ships. Phase 20
still owns the final integrated security/CI gate; Phases 21–23 own the broader
privacy/observability/recovery and controlled rollout work. Product version
remains 0.1.0.
