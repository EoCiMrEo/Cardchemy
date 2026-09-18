# ADR-012: Subject Knowledge, private history and independent RAG profiles

## Status

Accepted design, 2026-09-17. The operator approved G1/G2/G4/G6 and delegated
G5 selection during implementation of the beginning of the
[RAG plan](<../../Cardchemy-Subject-Scoped RAG Implementation Plan.md>) through
Phase 13. This record is a design contract; it does not claim that capture,
indexing, retrieval, conversations or Ask AI are implemented. Implementation
and verification follow the plan's preparation/phase order.

## Context

Generation sources are encrypted temporary PDFs, removed under the existing
lifecycle. Card snippets cannot reconstruct old lecture pages. Persistent
Knowledge therefore requires independent records, publication, storage limits,
provider disclosure and revision ownership. Subject enrollment alone must not
expose private source material. Profiles/processes do not create more provider
quota and must not expose credentials to the API or browser.

## Decision

PostgreSQL 16 with reviewed pgvector support is required for every installation,
including when `RAG_ENABLED=false`. One unconditional Alembic chain owns schema
installation; the flag suspends new RAG admission/capture/retrieval without
purging stored data. Artifact, extension-version, installation-privilege and
restore/downgrade checks must pass before declaring runtime support implemented.
No Redis, Celery or separate vector database is introduced.

The Phase 12 [runtime inventory](../../runtime-artifacts.json) selects pgvector
server extension 0.8.6 on PostgreSQL 16.15, a reviewed Linux/amd64 build recipe
and Python `pgvector==0.5.0`. The recipe pins the official Alpine base by digest,
pgvector source by checksum and package versions, uses portable compiler flags,
and replaces the embedded Go user-switch binary with native `su-exec`. Its
flattened final filesystem omits discarded binary/compiler layers. Consumers
verify the recipe and run its immutable local image identity; the exact image
is separately scanned and inventoried with its SBOM and archive/configuration
identity. This is a local build contract, not a published signed database image.
Fresh clusters use UTF-8 with ICU `en-US`. Moving prior libc-based Debian data
to this musl-based runtime requires logical restore into a separate fresh ICU
target and rebuilt indexes, preserving the original volume until recovery is
verified. The named data-directory path remains unchanged; that does not
authorize an in-place distribution switch. Native operators retain their
platform's compatible locale or rehearse a separate logical target under the
[database operations](../DATABASE_OPERATIONS.md) contract.
Alembic checks exact extension version/schema and installation permissions;
downgrading the foundation leaves the possibly shared extension installed.
This extends [ADR-004](ADR-004-alembic-schema-ownership.md), retaining one
unconditional migration chain without a feature-flag-dependent schema.

Knowledge is Subject-owned. Captured documents default to private. Readiness,
instructor review/publication and flashcard-set publication are separate.
Publication belongs to a specific reviewed content revision; changed content
requires fresh review. Reindexing never publishes or transfers approval to
changed content. Knowledge-only uploads are supported by the design, without
requiring card generation. Identical-upload replay is confined to the same
Subject and current authorized operation; changed payload reuse conflicts.
No cross-Subject content-hash lookup or deduplication may reveal existence.

Deleting a document removes its Knowledge dependents and detaches optional
generation-job/set links, preserving surviving flashcards. Deleting generation
job history preserves Knowledge. Subject/account ownership cascades its
Knowledge. One job-to-document association is authoritative; no reverse
ownership cycle is added. Historical job/set links remain nullable, with no
invented page/text backfill.

Content revisions and index revisions are separate. Canonical pages and
instructor review/publication belong to immutable content revisions; chunks,
vectors, chunker and full embedding-space identity belong to an index revision.
Old and staged replacement revisions both count against storage. Conservative
foundation limits are: content revision 100 pages/500,000 characters/2 MiB UTF-8
page text; index revision 512 chunks/16 MiB charged chunk/vector bytes; document
four content revisions/eight index revisions/64 MiB reserved text/vector bytes;
Subject 50 documents/256 MiB; uploader 100 documents/512 MiB; deployment 500
documents/2 GiB. Reservations use measured planned payload, and row writes may
not exceed them. Database triggers enforce aggregate admission and release on
deletion under deterministic transaction locking; later capture/index services
must use this contract rather than bypassing it. Charged bytes bound payload,
not physical PostgreSQL indexes, tuple overhead, WAL or backups; operators need
additional disk headroom and recovery measurements. Raising these hard schema
limits requires a new migration and measured rationale.

The initial admission contract uses one PostgreSQL transaction advisory lock
before Knowledge or related parent row locks, then global, Subject and uploader
usage counters. This deliberately serializes Knowledge writes at the initial
deployment cap; ordinary authentication, study and generation status updates
do not acquire it. Retention/account deletion acquires the same lock before
its explicit parent locks. Future capture/index code must follow that order;
changing concurrency needs measured contention evidence and equivalent quota,
delete and fencing tests.

This adds Knowledge ownership rules to [ADR-005](ADR-005-deletion-cascades.md)
and persistent-content/export prerequisites to
[ADR-011](ADR-011-operational-privacy-controls.md). It does not change card
approval, study progress or temporary PDF cleanup.

Conversations are private to their user and actual Subject, including instructors.
Subject ownership does not grant access to student chats. Each message and its
sources expire 90 days after creation; bounded operator cleanup removes empty
threads afterward. Chat writes and cleanup implement this clock in Phase 17.
All Ask AI uses ready, published eligible Knowledge. If any supporting content
is unpublished, deleted or replaced, derived stored answers/citations are hidden
on history/source reads; a citation-row cascade alone is insufficient. Current
principal access must also pass. Unpublication is not authority to read stale
snippets; no narrowly authorized historical-source exception is selected.
Chat storage/cleanup and history enforcement arrive in their later phases.

Use separate flashcard, indexing and answer worker processes, with independent
role enablement, credentials and reserved local capacity. API/email/frontend
containers receive no model credentials. The answer worker needs only its
answer and query-embedding credentials; the index worker needs embedding
credentials; flashcard generation retains its own credentials. A process-local
governor and bounded retry owner remain. Operators explicitly divide shared
provider-account/project limits across enabled profiles, roles and replicas;
different keys/prefixes do not establish independent quota. No distributed
governor is selected.

Initial G5 selections, verified against official documentation:

| Capability | Initial profile |
| --- | --- |
| Embeddings | `openai_compatible`, official `https://api.openai.com/v1`, `text-embedding-3-small`, 1,536 dimensions, float32 `vector`, cosine metric, explicit `encoding_format=float` |
| Document/query formatting | `raw_text_v1` for both; no task-type/prefix distinction, one ordered embedding per input, explicit dimension parameter |
| Ask AI | `openai_compatible`, official `https://api.openai.com/v1`, dated `gpt-4.1-mini-2025-04-14`, strict structured output, bounded stateless evidence/history requests |
| Flashcards | Preserve the configured and queued provider/model snapshots; this decision does not switch existing generation models |
| Retrieval | Authorized exact cosine search baseline plus bounded PostgreSQL lexical search; no ANN/reranker until measured corpus evidence justifies it |

Embedding-space identity includes provider/endpoint identity, model/version,
document/query format version, dimensions, numeric representation and metric.
The embedding model has no separately dated snapshot documented; record an
explicit operator-controlled space revision and require a staged rebuild/cutover
when the provider/model/format changes. Matching dimensions alone never permits
mixing spaces. Missing, non-finite, zero/malformed, reordered/count-mismatched or
wrong-dimensional results fail validation. Old active vectors remain usable
only within their complete compatible eligible revision while a replacement
is staged. Query vectors execute inside an authorized worker, not the API.

The deterministic RAG corpus must precede tuning: zero cross-Subject/private
exposure, complete rejection of known-invalid citations/support, abstention for
authored unsupported queries, and complete expected-evidence recall within the
reviewed top-K for authored feasible exact-search cases. Semantic answer support
and pedagogical judgment remain separate measurements. Record latency and cost
with the corpus/hardware; choose relevance/ANN tuning only from measured results.
Offline embeddings do not prove a remote model's retrieval quality.

## Rationale

The initial embedding profile is text-only, inexpensive and supports ordinary
per-input batching. Its native 1,536 dimensions fit pgvector's ordinary vector
index dimension limits without truncation or half-precision conversion.
The dated answer snapshot supports structured output and low latency without
a reasoning step, matching the existing bounded OpenAI-compatible adapter.
These are engineering fit judgments, not a corpus-based claim of superior
retrieval or answer quality. No implicit credential/model fallback is allowed.

Official prices checked during selection are USD 0.02 per million embedding
input tokens and USD 0.40/1.60 per million answer input/output tokens. Prices,
availability and account-specific quotas must be refreshed before any live
evaluation. Cached-input discounts are not assumed in admission budgets.
The provider key being present does not authorize spending or disclosure.

Google's stable alternatives were reviewed: `gemini-embedding-2` supports
768/1536/3072 dimensions but has a different task-prefix/per-input aggregation
contract, and `gemini-3.5-flash-lite` includes billable thinking. They remain
possible explicitly configured profiles after compatible implementation and
evaluation; they are not fallbacks. Keeping the current Gemini flashcard
profile does not imply sharing its key with RAG.

## Consequences

Root-only configuration and explicit per-container secret injection remain.
Before persistent writes, document extracted-text/vector capacity, deletion/
export ownership and external embedding transfers; before chat writes disclose
question/history transfers and implement the selected retention/history policy.
Backups/provider copies/private exports have separate deletion limits. Content,
prompts, embedding payloads and model output never enter logs or diagnostics.

Fresh backend, disposable PostgreSQL constraints/head/drift/migration/recovery,
affected runtime/service/image/security and context checks are required for
each implemented phase. Instructor quality review and paid evaluation are
reported separately; live calls need explicit endpoint/model/price/call/token/
time/cost authorization. G3 capture-cancellation outcomes remain a Phase 14
decision, outside the currently requested endpoint.

## Related Areas

[Grounding](ADR-006-grounded-generation-validation.md),
[root configuration](ADR-007-root-configuration.md),
[durable work](ADR-008-postgresql-durable-jobs.md),
[privacy](ADR-011-operational-privacy-controls.md),
[data model](../architecture/DATA-MODEL.md),
[AI flow](../architecture/AI-GENERATION-FLOW.md),
[runtime support](../RUNTIMES.md), [evaluation](../AI_EVALUATION.md).

Primary selection sources: [OpenAI embeddings](https://developers.openai.com/api/docs/guides/embeddings),
[embedding model/pricing](https://developers.openai.com/api/docs/models/text-embedding-3-small),
[answer model/snapshot/pricing](https://developers.openai.com/api/docs/models/gpt-4.1-mini),
[deprecations](https://developers.openai.com/api/docs/deprecations),
[pgvector](https://github.com/pgvector/pgvector),
[Google embeddings](https://ai.google.dev/gemini-api/docs/embeddings),
[Google pricing](https://ai.google.dev/gemini-api/docs/pricing).
