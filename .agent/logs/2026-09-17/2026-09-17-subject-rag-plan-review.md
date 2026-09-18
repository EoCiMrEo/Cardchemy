# Subject-Scoped RAG Plan Review and Approved Decisions

Date: 2026-09-17
Scope: documentation only; no application implementation, dependency changes, migrations, or deployment.

## Authorization and evidence

The user approved all twelve recommendations and all three proposed V1 decisions from the preceding project review, then requested an updated implementation plan. This entry records that approval, the resulting changes, and the verification boundary.

The supplied `Cardchemy-Subject-Scoped RAG Implementation Plan.md` is the editing source. The preceding review audited the project. In this follow-up, repository checks are limited to confirming the current baseline and the contracts needed for the documentation update; this is not a new whole-project audit.

Confirmed repository: `EoCiMrEo/Cardchemy`, `main` at `a9461b712e043def32228b3b111474b1fe1ec383`. The complete recursive tree contains no `AGENTS.md` and no existing Subject-scoped RAG plan. Existing log convention is defined by `.agent/logs/README.md`. The repository still has Alembic revisions through `20260916_0007`; current generation-worker persistence, page-aware chunking, Subject authorization, root configuration, remediation roadmap, and Phase 9 log were consulted. Phase 10 privacy/operations work remains a dependency rather than assumed completed work.

## Approved V1 decisions

1. Knowledge capture is a side effect of the existing `Generate Set -> Upload PDF` workflow. No separate Knowledge-only upload endpoint or UI in V1. Existing AI-provider admission still applies.
2. Historical answers and citation provenance survive reindexing and ordinary document removal. Removed sources are labelled `Source removed` and excluded from retrieval immediately. Explicit hard deletion, Subject deletion, and retention cleanup follow the privacy policy and may erase source excerpts.
3. Domain contracts remain provider-neutral. Before Phase 15 implementation, select and pin one deployment-wide embedding provider/model/version and dimension. No provider or dimension value was chosen by this approval.

## Problems and resulting plan changes

| Recommendation | Problem | Approved change |
|---|---|---|
| R1 / P0 | Extraction exists only in memory until flashcard finalization. | Independent, lease-fenced and idempotent knowledge-capture transaction after extraction/chunking; unique `generation_job_id`; preserve successful capture if card generation fails. |
| R2 / P0 | Persistent UUIDs could replace logical chunk IDs used by generation. | Separate persistent chunk UUID from unchanged logical `chunk_key`; preserve current page-aware generation behavior and 1200/120 defaults. |
| R3 / P0 | Rebuild/delete could invalidate old citation foreign keys. | Versioned immutable chunk generations, atomic active-version switch, citation metadata/excerpt snapshots and nullable source reference; explicit cleanup behavior. |
| R4 / P0 | Application-only Subject consistency checks leave corruption paths. | Composite database foreign keys for document/Subject and related entities; Subject predicate inside every vector/FTS SQL query. |
| R5 / P0 | Shared job capacity could starve flashcard generation. | Same backend image and PostgreSQL, separate generation, knowledge-index and RAG-answer queues/processes; explicit concurrency and provider budgets. |
| R6 / P0 | Hiding UI alone would still change privacy while disabled. | `RAG_ENABLED=false` performs no extracted-knowledge persistence or RAG job claims; current PDF-generation and source cleanup remain intact. |
| R7 / P0 | Runtime/test changes alone miss database security and restore readiness. | PostgreSQL 16 pgvector image pin, effective Compose overrides, disposable test/security harnesses, DB image scan/SBOM, extension privileges and runtime-before-migration order. |
| R8 / P0-P1 | A model change may invalidate `vector(n)` and its index. | Deployment-wide dimension contract, startup validation, metadata per index version, explicit migration for dimension changes. |
| R9 / P1 | Vector and lexical scores cannot be added directly. | Reciprocal Rank Fusion, deterministic deduplication/ties, evaluation-selected FTS configuration, exact cosine baseline and evidence-gated ANN. |
| R10 / P1 | Duplicate submissions and unbounded history can multiply cost. | Durable question idempotency and conflict handling, bounded context, backend-owned Subject boundary and honest provider retry semantics. |
| R11 / P1 | Late privacy decisions conflict with schema and citation retention. | Early privacy/deletion/export/backup design gate before Phase 13; operational enforcement remains in Phase 21. |
| R12 / P1 | Ask AI could be built on unevaluated retrieval. | Deterministic retrieval/security gate at Phase 16 before Phase 17; complete answer/journey/rollout evaluation remains Phase 19. |

## Deliverables

- Revised implementation plan at `docs/SUBJECT_SCOPED_RAG_IMPLEMENTATION_PLAN.md`, preserving Phases 12-21 and the original V1 architecture/scope.
- Updated supplied plan file with identical content.
- This decision log and a new index entry in `.agent/logs/README.md`.

## Verification boundary

The complete supplied plan was read before editing. Structural validation confirmed exactly Phases 12-21, all twelve recommendation mappings, all three V1 decisions, early privacy and retrieval gates, preserved generation chunk defaults, unchecked implementation tasks, balanced fenced blocks, and no trailing whitespace or merge markers. The existing twelve log-index entries are preserved and one new dated entry is added.

An independently delegated documentation review checked approved-recommendation coverage and lifecycle/security consistency. It identified one sequencing ambiguity: dimensioned vector DDL cannot precede the pinned model/dimension choice. The final plan explicitly defers embedding-column/vector-index DDL to a Phase 15 migration after that choice, while Phase 13 establishes text and identities. No other material gap was reported. Final document validation and byte comparison verify that the supplied-file replacement and repository plan have identical content.

No application, paid-provider, migration, browser, runtime-image or full-CI execution is claimed for this documentation-only update. Implementation acceptance checkboxes stay unchecked; approval of a design is not evidence that its implementation passed. Repository documentation is staged on a dedicated review branch; no merge or deployment is authorized by this update.
