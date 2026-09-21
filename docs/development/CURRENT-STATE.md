# Current Development State

Snapshot: 2026-09-21. Phases 0–11, Subject Knowledge RAG Phases 12–19 and the
Phase 20/21 implementation, offline integration and bounded live-AI scope are complete. The public v0.1.0 release
contains independently verified keyless-signed image digests, checksums,
source/provenance, audits and SBOMs. The separate v1.0 operational readiness gate
passed, including an actual clean-machine production-profile recovery rehearsal.

## Current phase

The [remediation plan](../../issues-required-remediation.md) records Phases 0–11
complete. All eleven separate v1.0 operational readiness items passed; see
[exact-source evidence](../../.agent/logs/2026-09-17/2026-09-17-v1-release-gate.md).
Current product version is 0.1.0. The repository context system is implemented;
its [completion log](../../.agent/logs/2026-09-16/2026-09-16-repository-context-system.md) records its
separate documentation scope.

## Completed major work

- Phases 0–2: reproducible dependencies, purpose-scoped authentication and
  authorization, Alembic baseline and transactional/database integrity.
- Phases 3–4: durable bounded PDF workers, source-grounded structured AI,
  validation and token/cost telemetry.
- Phases 5–6: typed API/session recovery, durable study answer receipts,
  accessible responsive online-first study.
- Phases 7–8: transactional SMTP outbox/worker, local Mailpit, production-shaped
  Compose, migration/backup/restore and graceful shutdown procedures.
- Phase 9: root-only configuration, source/test cleanup, runtime/dependency
  security, coverage/bundle budgets, isolated journey and mandatory CI gates.
- Phase 10: allowlisted structured logs and safe correlated errors, private
  request/job metrics and worker health, transactional privileged audits,
  provider disclosure, bounded retention and guarded account export/deletion.
  External numeric telemetry remains disabled by default and explicitly run.
- Subsequent context work: canonical orientation, navigation/module maps, five
  architecture flows, accepted ADRs, local setup, historical separation and
  automatic context-file/link validation.
- Subject Knowledge Phases 12–19: pinned PostgreSQL 16/pgvector foundation,
  private revisioned storage, one-pass capture and Knowledge-only admission,
  durable isolated embedding/index execution, explicit reindex/cutover, and
  worker-only authorized exact cosine plus PostgreSQL FTS retrieval; private
  Subject Ask AI threads, durable answer jobs, grounded citations, semantic
  support validation, bounded quotas and G2 history invalidation; instructor
  Knowledge and private Subject Ask AI browser workflows; and a reviewed v2
  retrieval/support/security corpus with measured exact-search gates.
- Phase 20/21 technical closure: native Gemini RAG answer/embedding profiles,
  full deterministic RAG-off/RAG-on integration, request/job diagnostics,
  Knowledge lifecycle audits, private export/deletion/retention controls and
  populated page/vector/conversation/citation recovery, and explicitly
  authorized bounded live Gemini flashcard/RAG evaluations. Production
  enablement and release-specific human assistive-technology evidence remain
  separate rollout gates rather than being inferred from test success.

The [Phase 9 closure log](../../.agent/logs/2026-09-16/2026-09-16-phase-9-merge-closure.md)
supersedes earlier unmerged checkpoints in its remediation log. Detailed tasks
belong to the roadmap; implementation/check details belong to the
[dated log index](../../.agent/logs/README.md).
The [Phase 10 closure log](../../.agent/logs/2026-09-17/2026-09-17-phase-10-remediation.md)
records its verification and limits at Alembic `20260917_0008`. The current
working branch advances the mandatory pgvector and private Subject Knowledge
chain through `20260920_0013`; operators must apply the documented
configuration and database upgrade before starting this code.

## Current focus and known risks

The separate [Subject-scoped RAG implementation plan](<../../Cardchemy-Subject-Scoped RAG Implementation Plan.md>)
is implemented through Preparation A/B and Phases 12–21 technical closure. Preparation A prompt,
diagnostic and offline-comparison implementation passed its offline and
deterministic journey checks; on 2026-09-18 the operator accepted the authored
card sample as "very good". Preparation B's definitive AI profile migration
passed full offline backend/frontend, Compose, configuration and deterministic
cross-stack checks. Phases 12–13 established the PostgreSQL/pgvector foundation
and private Subject Knowledge schema. Phases 14–16 implement one-pass private
capture and separately admitted Knowledge-only uploads, durable isolated
embedding/index execution, explicit reindex/cutover, and reusable worker-only
authorized hybrid retrieval. Phase 17 adds owner-private per-user conversations,
API enqueue/poll/history/retry/cancel/delete/source contracts, a separate
answer/query-embedding worker, strict claim/quote/source validation and immediate
redaction when current access or evidence eligibility is lost. Phase 18 adds
typed instructor Knowledge management and private Ask AI interfaces with safe
state recovery, evidence dialogs, reload/retry polling, accessibility and mobile
contracts. Phase 19 adds the deterministic v2 corpus and actual PostgreSQL
exact-vector/FTS recall, ranking, exposure, overlap, latency and indexing-
throughput gates. Exact search remains the baseline; ANN and reranking remain
absent because the measured corpus did not justify them. Installation, privacy,
upload/versioning, initial
models and separate-worker quota decisions are accepted
in [ADR-012](../decisions/ADR-012-subject-knowledge-and-rag-boundaries.md).
The integrated offline/service/frontend/journey/recovery gates and Phase 21
privacy/observability controls are implemented. Bounded live Gemini flashcard
and Subject RAG evaluations passed after explicit operator authorization. The
exact self-hosted startup command passed from a pushed fresh clone with generated
secrets, no source edits, migration exit zero, all services healthy and routed
health HTTP 200. The remaining rollout items require external evidence: hosted
Linux closure, production enablement and release-specific spoken assistive-
technology validation.
The reviewed database build uses PostgreSQL 16.15/pgvector 0.8.6, ICU `en-US`
and a fail-closed legacy-volume guard. A prior Debian/libc installation needs a
logical restore into a separate fresh target; the existing volume path alone
is not compatibility evidence. Live calls were bounded by explicit model,
request, token, time and cost guards and made no automatic retries.
Actual checks and limits belong to the
[Phase 14–16 implementation record](../../.agent/logs/2026-09-19/2026-09-19-rag-capture-index-retrieval.md)
and [Phase 17 record](../../.agent/logs/2026-09-19/2026-09-19-rag-subject-ask-ai.md).
Phase 18–19 implementation and exact verification are recorded in the
[frontend/evaluation record](../../.agent/logs/2026-09-19/2026-09-19-rag-frontend-and-evaluation.md).

Phase 10 diagnostics are content-free, bounded and best effort. Metrics are
not a complete provider billing ledger and audits are not tamper-proof. Account
export/deletion and retention cleanup are operator CLI workflows; no public
self-service privacy API or automatic external reporting is introduced. See
[observability](../OBSERVABILITY.md) and [privacy](../PRIVACY.md).

Phase 11 adds the approved standalone Cardchemy name/tagline and artwork,
Apache-2.0 code licensing with separate brand terms, contribution/security/
conduct policies, templates, operating README/screenshots and public roadmap.
New configuration/package/image defaults use Cardchemy. Existing operators
retain database/project identities and explicit authentication settings per
[configuration](../CONFIGURATION.md#existing-installations-and-cardchemy-defaults).
The [demo](../DEMO.md) uses authored data and an offline provider; the
[release guide](../RELEASING.md) defines exact-source keyless signing and
verified draft publication. Name screening and its limits are recorded in
[name review](../NAME-REVIEW.md). The [published v0.1.0 release](https://github.com/EoCiMrEo/Cardchemy/releases/tag/v0.1.0),
public repository/image pulls and private vulnerability reporting are verified.
The user reported a successful Chrome/Narrator manual pass at 1920×1080;
browser/assistive-technology versions were unknown and are recorded as such.

## Important constraints

- Local development is the reference environment. Production guides and
  hardened images exist; no live production deployment is asserted here.
- Study-session payloads hide answers, but other authorized card-read responses
  contain correct answers. See [study flow](../architecture/STUDY-PROGRESS-FLOW.md).
- Account deletion/export is available to authorized operators with documented
  safeguards. Deployments still need their own privacy notice, provider contract,
  backup/collector expiry and requester verification. See [privacy](../PRIVACY.md).
- Provider rate admission is process-wide, not distributed across worker replicas.
  Failed/cancelled/crashed requests can limit completeness of durable usage
  telemetry. Paid provider availability/quality requires explicit live evaluation.
- The separate live password-reset case and paid AI tests stay opt-in. Earlier
  offline/hosted passes do not establish live provider or production relay behavior.
- Linux/amd64 is the supported container target; arm64 remains best effort.
  Manual spoken assistive-technology checks remain release evidence.
- Preserve real `.env`, secrets and populated volumes. Migration downgrade
  rehearsals run on disposable test databases, never operator data.

## Next and maintenance

The clean-machine [production recovery rehearsal](../PRODUCTION_REHEARSAL.md)
and exact-source hosted CI passed. Actual authenticated local
[TLS SMTP delivery/recovery](../SMTP-VERIFICATION.md) passed both supported modes.
The v1.0 readiness gate is complete; current version remains 0.1.0 and no v1.0
publication is performed. Repeat required release checks for future source
changes and verify each deployment's own edge, relay and recovery goals.
Update this summary whenever a phase/milestone completes, and retain task
detail in the roadmap. For ongoing work read [orientation](../00-START-HERE.md),
[project map](../../PROJECT-MAP.md), [ADR index](../decisions/ADR-000-INDEX.md)
and [agent maintenance rules](../../AGENTS.md).
