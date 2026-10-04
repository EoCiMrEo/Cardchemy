# Lane 6 source evidence selection implementation

Date: 2026-09-26. Status: implementation and validation in progress; Ask remains disabled.

## Scope and starting context

- The operator approved the evidence-sufficiency extension to Lane 6 and ADR-022, preserving source-only Ask: one current-question embedding at most, no generated answer, no answer verifier, and no automatic paid retry. No live-provider request or remote reindex was approved for this implementation turn.
- Started on `main` at `6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57` with a large existing modified/untracked Lane 0–6 working tree. Existing files, root `.env`, retained Knowledge, volumes and historical migrations were preserved.
- The retained self-hosted development stack is at schema head `20260926_0023`, runs the earlier source-only image, and has Ask disabled. Current v2 code has not been built into that image. No real-database writes were made here.

## Implementation

- Added a local question descriptor and exact-unit source selector in `backend/app/ai/source_sufficiency.py`. It retains the requested relation, entity, qualifiers and an unambiguous bounded follow-up referent. It treats relation cues as candidates for lecture navigation, not semantic entailment or verified answers. It returns source-contiguous offsets no longer than 480 characters and at most three distinct pages.
- Versioned first-stage retrieval as `hybrid_source_sufficiency_v2` and local selection as `source_relation_units_v2`. Existing vector/FTS Subject, owner/enrollment, publication, revision and embedding-space predicates remain in SQL; queued jobs with an old retrieval policy fail profile matching before provider work.
- Added bounded same-page/nearby-page reads with the same current authorization and immutable source identity. Neighbor chunks do not inherit vector/lexical scores. Worker completion reauthorizes exact offsets and commits the whole reference bundle atomically under the current claim and Knowledge write lock.
- Updated the guarded read-only private display evaluator to use the same runtime policy/selector; its outputs remain owner-private and aggregate-only on stdout. No private Knowledge text was added to tracked fixtures or logs.
- Updated the plan, ADR-022, project/backend maps, evaluation guide, current state, Subject Knowledge flow and English no-match copy to describe the approved source-only evidence path and its still-open release gate.

## Verification and findings so far

- Backend offline suite before the final neighbor-budget adjustment: **1,421 passed, 120 skipped, 2 deselected**. The skipped/deselected cases do not establish live-provider or service behavior.
- Frontend full `npm run check -- --workers=2`: typechecks, lint, Node and component tests, build, and Chromium **68 passed, 1 intentionally skipped**. Two browser tests were corrected to assert the current source-only copy and wait for the actual successful retry request.
- `python scripts/check_context.py`: **37 required files, 77 guides, 1,266 local links**. `python scripts/check_ci.py` passed workflow/protection contract validation.
- Disposable PostgreSQL migration upgrade, head/drift, downgrade-to-base and re-upgrade reached head `20260926_0023`. The first full service run found two later quota-test failures caused by committed synthetic owners from the newly added neighbor test. After that fixture cleaned only its owned records, the repeat suite passed: **100 passed, 3 skipped, 1,444 deselected**, with owned container and credential cleanup confirmed. These are disposable service checks, not operator DB or live-provider proof.
- A code review found that passing all top-20 anchors into neighbor expansion could consume the 12-page/8,192-token examination budget before any neighbor was examined. The first partial-anchor correction passed focused tests; a second review found that its cheap preselection still read content across too many pages and counted initial/neighbor budgets separately. A strict cumulative-budget correction and regression test are in progress. No claim of improved private retrieval or displayed-window quality is made from public synthetic tests.
- The subsequent shared selector/neighbor correction passed 57 focused offline tests. A later full offline run reached 1,440 passes with one failing **new packet-builder test** (`UUID` object passed through `UUID(...)`), 120 skips and two deselections. The packet builder is still being edited; rerun the full suite after its contract stabilizes.
- The first deterministic `rag-on` disposable journey failed before query embedding: one source-only job returned `rag_answer_failed` with zero provider requests and content-free `answer_internal_error`. A disposable PostgreSQL reproduction isolated the cause to `ck_rag_answer_jobs_retrieval_timing`: the ambiguous-question `no_match` path stamped `retrieval_completed_at` without a provider boundary. `_complete_source` now leaves that timestamp null before a provider call and rejects references without the boundary. Its public `process_claim` regression passes with zero provider/stage/reference/assistant rows. The journey fixture now asks an explicit definition found in its synthetic lecture and a recognized but absent measurement question. Both `rag-on` and `rag-off` disposable browser journeys passed, with owned processes, containers, data and credentials cleaned. No paid provider was involved.
- The later full disposable PostgreSQL suite passed **101 passed, 3 skipped, 1,470 deselected**, including head/drift and downgrade-to-base/re-upgrade at `20260926_0023`; owned resources were cleaned. The count reflects the new no-provider regression and does not establish real provider or retained-data behavior.
- A source-only question-intent audit found that optional adverbs could contaminate measurement entities (for example an acronym followed by `primarily`) and that an entity-free comparison question could qualify a different metric from generic overlapping words. Narrow parser fixes preserve the entity; entity-free measurement now requires all discriminators in the same unit. A second audit reproduced same-unit other-entity predicates and dropped numeric ranges. The selector now bounds entity-to-predicate bridges, rejects a reason cue after a separate clause and requires numeric requirements in the exact selected unit. Synthetic regressions cover these failures. Limitation/application questions remain outside the six declared relation classes; do not count them as supported or infer general semantic accuracy from these rules.
- A provider-free, read-only discovery pass initially yielded six unreviewed positive candidates and two insufficient-pair candidates. One bounded authored-template expansion examined 104 eligible pages/chunks, excluding 21 distinct pages already exposed in earlier reviews or seed cases. It yielded ten unreviewed positives on ten distinct pages across three documents (3 direct, 4 paraphrase, 3 follow-up) and five unreviewed insufficient pairs. This remains below the approved 12/12 gate; the owner-private Temp packet was opened and human review requested. No quality labels, corpus-wide absence or displayed-window pass are inferred.
- The full backend offline suite after the selector/packet corrections passed **1,459 passed, 121 skipped, 2 deselected**. Subsequent logging and retry admission corrections require final targeted/full verification.
- A release audit identified the deliberate five-pair durable retrieval-rank cap alongside v2's twenty candidates. Documentation now explicitly distinguishes top-five persisted ranks from the full candidate set. It also found that `knowledge_source_selection` was missing from the structured log allowlist; the formatter now retains only its fixed policy/status and numeric inspection/selection counts while dropping questions, quotes and source identities. No migration or diagnostic rank-array expansion was made.
- Service retry admission and `can_retry` now require the current immutable retrieval policy before capacity/quota/state mutation. Historical questions remain readable. The first PostgreSQL regression setup attempted to rewrite an immutable snapshot and was correctly rejected; the fixture now creates a legacy snapshot at enqueue. Targeted service units and the isolated PostgreSQL regression passed.
- Final runtime backend validation passed **1,461 passed, 122 skipped, 2 deselected**; the full disposable PostgreSQL suite passed **102 passed, 3 skipped, 1,480 deselected**, with upgrade/head/drift/downgrade/base/re-upgrade clean at `0023`. Both deterministic journey modes passed again against the final selector/logging/retry code, with owned processes, containers, data and credentials cleaned. The private packet builder is undergoing further scoped corrections after these runs.
- The owner reviewed the new packet: three positive excerpt/page Yes, six No, one omitted; five insufficient-pair No. Source-fidelity labels were omitted and remain unreviewed. Only the supplied decisions were saved in the existing owner-private Temp packet; no roster was promoted. Local original-PDF comparison found one matching source page for each of the six rejected positive excerpts. Visual review confirmed recap/transition pages, another entity's metric definition or material lacking the requested relation. This does not establish corpus-wide absence or an extraction defect.
- The independent builder audit found entity/clue self-matches, cross-entity nearby clues, first-page bias and non-structural character windows. Its invented exactly-two-positive-per-relation requirement is being removed: the approved positive gate is category-balanced 4/4/4, while insufficient pairs require two per declared relation with sufficient controls. This corrects the harness without changing thresholds.
- The existing seed questions include limitation/information-loss and application/example intents outside the six initial relation families. The owner approved the separate [coverage amendment](2026-09-26-source-relation-coverage-recommendation.md) adding those explicit families and sixteen reviewed insufficient pairs. Lane 6 and ADR-022 now record this scope; the v3 descriptor/unit implementation, independent discovery corrections and provider-free reviewed-pair scorer are in progress. Retrieval snapshots use `hybrid_source_sufficiency_v3` with local `source_relation_units_v3` so older snapshots cannot execute/retry. No model, provider spending, remote reindex or runtime activation was introduced; earlier six-family suite results do not prove the new extension.

## Remaining gate

The new independent, owner-reviewed twelve-positive and sixteen-insufficient source-pair gate is not yet established. Earlier reviewed exact source pairs are development cases; they do not prove corpus-wide absence or general accuracy. Current source-only v3 is not deployed or enabled. A new live embedding comparison requires its own reviewed endpoint/model/price/call/token/time/cost envelope. Keep the Ask switch off until the exact displayed excerpts, current page opening, access negatives, maintained retrieval thresholds, disposable integration, journey and manual accessibility checks pass.

## Later v3 verification and structure diagnostic

- After the v3 selector, private-packet builder and exact-window audit harness
  stabilized, the full backend offline suite passed **1,554 tests**, with 122
  skipped and two deselected. An earlier full invocation during a coordinated
  harness schema change had 26 test-fixture failures because collected tests
  still called the old `parse_controls` signature; the final focused suite
  passed **181 tests** and the subsequent full suite had no failure. The
  default packet and evaluator CLIs each confirmed zero DB/provider work.
- Disposable PostgreSQL passed **102 tests**, three skipped and 1,573
  deselected; head/drift and downgrade-to-base/re-upgrade remained clean at
  `20260926_0023`. Both deterministic `rag-on` and `rag-off` browser journeys
  passed with owned disposable resources cleaned. The full frontend check
  passed typecheck, lint, unit/component/build and Chromium **68 passed, one
  intentional skip**. Context and CI checks passed; `git diff --check` was
  clean. None of these is a live-provider or private displayed-window pass.
- The v3 review audit found four concrete synthetic false primary references:
  a definition omitting a second requested relation, an explicitly incorrect
  parenthetic expansion, one entity dropped from a compound question, and an
  application bullet owned by another topic. Narrow fail-closed fixes and
  positive/negative controls passed **118 focused tests**. A subsequent
  original-PDF inspection found a bare negative limitation bullet under its
  owning title; a bounded same-chunk property correction passed **81
  selector tests**. This last correction postdates the full/backend/PG/journey
  runs above and needs final scope verification if it is retained.
- An owner-authorized read-only snapshot counted 104 current published pages.
  After excluding 31 exposed review/seed pages, fixed authored filters found
  strict candidate pages in only two definition and one property page;
  weaker title-owned evidence flags appeared in two additional definition and
  two mechanism pages. These are filter-capacity diagnostics, not independent
  labels, corpus-wide absence, retrieval quality or proof that a displayed
  excerpt is sufficient. See the separate
  [structure recommendation](2026-09-26-source-structure-coverage-recommendation.md).
  No private source text or identifiers were logged. The temporary PDF renders
  were deleted after resolved-path verification; a temporary read-only probe
  copy in the retained backend container was also removed. One read-only
  ephemeral container failed to mount the host scripts directory before any
  source read and left no container. The retained Ask setting was verified
  disabled and its old running image still advertises the retired policy, so
  no current-image live Ask result is claimed.
