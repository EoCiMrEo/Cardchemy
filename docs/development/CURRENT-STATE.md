# Current development state

Updated 2026-10-05. The **0.2.0** release candidate includes Phases 0–21,
product-quality Lanes 0–6 and the verified repository cleanup. The operator
defined Lane 7 as that cleanup, current documents/diagrams and final GitHub
rollout; documentation is ready and protected publication is in progress.
The separate v1.0 operational-readiness gate passed; it did not publish v1.0.

## Current source-only Ask

New jobs use `related_knowledge_navigation_v8`, `hybrid_source_navigation_v9`,
`visual_source_id_v5` and immutable `literal_subject_admission_v2` at Alembic
head `20261002_0033`. Each durable attempt permits at most one unchanged
current-question embedding and one bounded text/PNG source-ID judgment,
zero answer/verifier calls and zero automatic retries. Results contain 0–3
exact unverified references to currently authorized published original PDF pages.
An eligible unresolved follow-up may transfer only its immutable unique literal
preceding subject, at most 160 characters/twelve words; no full history or
assistant response is sent. Historical rows retain their contracts and cannot
execute or retry under the new policy.

The retained local installation was enabled on 2026-10-04 after Lane 6's **7/7**
quality/display/release gates. Fresh installations remain default-off and
require explicit Ask/judge flags, matching active embedding space and current
prices. Embedding 001 remains default; Embedding 2 is a separate optional
staged space. See [ADR-023](../decisions/ADR-023-original-pdf-source-navigation.md),
[ADR-024](../decisions/ADR-024-gemini-source-id-judge.md) and
[actual closure](../../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md).

| Complete measurement | Result |
| --- | --- |
| Public heldout, 60 cases | 94/99 useful displayed cards; 48/48 positive hits; 58/60 valid outcomes; 10/12 clear no-match |
| Independent private holdout, 12 cases | 21/24 useful cards (87.5%); 12/12 hits; 4/4 per form |
| Exposed seed/control set | 25/25 useful cards; 11/11 seed hits; positive N12 and empty restricted U01/U02 |
| Actual original-PDF display | 49 captured references reconciled against 30 distinct authenticated original pages |

These sets remain separate. All historical failed physical attempts and unknown
charges remain in the closure ledger; partial pilots were never relabeled passes.
Controlled HTTP/auth/job browser replay is distinct from live persisted paid Ask.
Real SQL/PDF guards and disposable journeys supply separate access/persistence proof.

The final recorded release verification passed full offline backend, disposable
PostgreSQL migration/race/access, full frontend, deterministic RAG-on/off
journeys, current image smoke/security and retained health/profile checks.
The operator reported the six spoken scenarios passed without supplying exact
browser/screen-reader/version/viewport metadata. That local closure does not
claim hosted CI, a protected merge, a new public release or production deployment.

## Generation and product quality

New text generation uses the verified native Gemini catalog. Study Progress is
distinct currently approved cards answered correctly at least once; Accuracy,
Attempted and status-based Mastery remain separate. Same-Subject repeat Knowledge
upload requires an explicit owner reuse/separate-copy choice; unchanged explicit
revisions avoid new Knowledge/index work.

Adaptive generation stays within request/token/cost bounds and retains strict
four-option grounding, deduplication, cancellation/fencing and atomic exact-target
persistence. Fully validated candidates can wait in encrypted finite private
storage for an exact smaller-target choice without another provider call.
The published whole sparse-PDF control used deterministic providers and proves
target20 → pending1 → exact-one persistence, not live Gemini sparse-source yield.

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
  authorized bounded live Gemini flashcard/RAG evaluations. The operator
  confirmed the release is self-hosted through the production-shaped Docker
  stack, with no centralized production deployment, and reported the current
  release-specific Windows/browser/Narrator validation as passed. Protected-main
  hosted CI, production recovery rehearsal #7 and an exact fresh-clone
  `docker compose up -d` start all passed commit `8a5c0aa`.


## Important constraints

- Local development is the reference environment. Production guides and
  hardened images exist; Cardchemy is distributed for operator-owned self-hosted
  Docker deployments and no centralized live production deployment is asserted.
- Study-session payloads hide answers, but other authorized card-read responses
  contain correct answers. See [study flow](../architecture/STUDY-PROGRESS-FLOW.md).
- Account deletion/export is available to authorized operators with documented
  safeguards. Deployments still need their own privacy notice, provider contract,
  backup/collector expiry and requester verification. See [privacy](../security/PRIVACY.md).
- Provider rate admission is process-wide, not distributed across worker replicas.
  Failed/cancelled/crashed requests can limit completeness of durable usage
  telemetry. Paid provider availability/quality requires explicit live evaluation.
- The separate live password-reset case and paid AI tests stay opt-in. Earlier
  offline/hosted passes do not establish live provider or production relay behavior.
- Linux/amd64 is the supported container target; arm64 remains best effort.
  Manual spoken assistive-technology checks remain release evidence.
- Preserve real `.env`, secrets and populated volumes. Migration downgrade
  rehearsals run on disposable test databases, never operator data.


## Final Lane 7 and release status

The operator's 2026-10-05 final Lane 7 definition supersedes the archived
tracker's older incomplete summaries: clean stale/unused project files,
refresh release/current documentation with comprehensive architecture diagrams,
then publish all latest source and release 0.2.0 through the protected GitHub
flow while resolving the remaining pull requests. Cleanup and documentation
are complete; the external rollout remains in progress until its actual
merge, exact-main CI and verified release evidence are recorded.

The [visual guide](../diagrams/README.md) describes current system boundaries,
generation, Knowledge/indexing, source-only Ask, authentication, study, email
and self-hosted release operation. Ask may still use Gemini for embeddings and
source-ID judgment even though it returns original-PDF reading references
instead of a generated answer. Local lexical retrieval is a bounded response
to transient embedding unavailability, not an inference from UI appearance.
Candidates found through that fallback still use source-ID judgment; Published
Knowledge browsing/search is a separate local route without an Ask provider call.

No additional accepted implementation plan remains beyond this final release
item. The retired [product-quality tracker](../archive/PRODUCT-QUALITY-REMEDIATION-PLAN.md)
and [public roadmap](../../ROADMAP.md) retain history and current completion
status. Future source changes require current-source tests and each
deployment's own provider, edge, encrypted SMTP and backup/recovery checks.
No new paid evaluation is implied. Operational guides are in the
[guide index](../README.md); chronology is in the [dated logs](../../.agent/logs/README.md).

The inherited source was subsequently published through [PR 41](https://github.com/EoCiMrEo/Cardchemy/pull/41), merged as `61b34eb`; see [publication evidence](../../.agent/logs/2026-10-04/2026-10-04-github-publication.md). The dated local activation is historical evidence, not a current container-health claim.

The 2026-10-04 repository cleanup consolidated current runtime modules, retired
consumed experiments and organized domain guides. Its local candidate
passed both Python offline suites, disposable services/journeys, frontend,
image/security gates and base-Compose fresh-clone verification; see the
[cleanup record](../../.agent/logs/2026-10-04/2026-10-04-repository-cleanup.md).
Operator configuration and migrations were preserved. This local verification
is separate from the current protected source/release publication.
