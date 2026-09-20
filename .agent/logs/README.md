# Agent Logs

Last Updated: 2026-09-20

This directory records agent-visible development history for Cardchemy: what changed, why the work was needed, what problems appeared, how they were solved, and how the result was verified.

Start with [canonical orientation](../../docs/00-START-HERE.md),
[current state](../../docs/development/CURRENT-STATE.md), and the
[project map](../../PROJECT-MAP.md) for current truth. Dated logs are historical
snapshots: later source/closure evidence supersedes old paths, failures and
phase-status notes. Logs are stored under date folders; preserve those moves.
Follow [agent rules](../../AGENTS.md) when adding scope/decision/check evidence.

Do not store secrets, environment values, passwords, or long-lived credentials in these logs. Disposable QA credentials may be described only by purpose and cleanup status.

## Log Index

| Date | Log | Summary |
|---|---|---|
| 2026-09-20 | [RAG Phase 20/21 technical closure](2026-09-20/2026-09-20-rag-phase20-phase21-closure.md) | Native Gemini RAG profiles, integrated RAG-off/RAG-on regression and security gates, privacy/operations controls, populated recovery and bounded live evaluation; hosted/fresh-clone, production and human evidence remain explicit. |
| 2026-09-19 | [RAG frontend and evaluation closure](2026-09-19/2026-09-19-rag-frontend-and-evaluation.md) | Closes Phases 18–19 with typed Knowledge/Ask AI UX, reload/retry/citation/accessibility contracts, the reviewed v2 retrieval/support/security corpus, actual exact-vector/FTS measurements, a guarded live harness and deterministic cross-stack proof. |
| 2026-09-19 | [Subject Ask AI backend and durable answer jobs](2026-09-19/2026-09-19-rag-subject-ask-ai.md) | Closes Phase 17 with owner-private conversation APIs, race-safe admission, isolated query/answer work, strict citation/support validation, G2 redaction/retention and offline/PostgreSQL migration evidence. |
| 2026-09-19 | [RAG capture, indexing and retrieval closure](2026-09-19/2026-09-19-rag-capture-index-retrieval.md) | Closes Phases 14–16 with one-pass private Knowledge capture, durable fenced embedding/index work, exact authorized hybrid retrieval, migration/runtime/privacy documentation and offline/PostgreSQL/journey evidence. |
| 2026-09-18 | [Dependabot batch policy](2026-09-18/2026-09-18-dependabot-batch-policy.md) | Groups routine minor/patch updates, limits each ecosystem to one open version PR, and reserves major upgrades for planned work while retaining security updates. |
| 2026-09-18 | [Final runtime-image PR reconciliation](2026-09-18/2026-09-18-final-runtime-image-pr-reconciliation.md) | Records bot-closed PR #24 and reconciles replacement PR #25 while retaining Node 24 and ignoring unsupported major Docker updates. |
| 2026-09-18 | [Coupled frontend dependency PR remediation](2026-09-18/2026-09-18-coupled-frontend-dependency-merges.md) | PRs #4–8 preserved in normal merge history, aligned peers/npm resolver and loading/Subject/session fences with component, browser and image evidence. |
| 2026-09-18 | [bcrypt 5 password compatibility](2026-09-18/2026-09-18-bcrypt5-password-compatibility.md) | Direct bcrypt with preserved historic/current password records, regenerated Windows hashed locks, independent fixtures, passing auth/offline/coverage and both native backend image probes; current-head security/hosted gates remain required. |
| 2026-09-18 | [Historical plan PR reconciliation](2026-09-18/2026-09-18-rag-plan-pr-reconciliation.md) | Preserves PR #12 history and supersedes its obsolete parallel plan with active plan/ADR navigation. |
| 2026-09-17 | [Historical Subject-scoped RAG plan review](2026-09-17/2026-09-17-subject-rag-plan-review.md) | Original PR #12 proposal decisions, superseded by later operator-approved G1/G2/G4/G5/G6 and the implementation plan; historical body unchanged. |
| 2026-09-18 | [Pull request merge and compatibility remediation](2026-09-18/2026-09-18-pull-request-merge.md) | Protected-main merge work, hosted scan remediation, completed feature/frontend/password merges, and tested current-head dependency/runtime integration for PRs #3/#9/#11/#14. |
| 2026-09-18 | [RAG foundation and Knowledge schema closure](2026-09-18/2026-09-18-rag-foundation-and-knowledge-schema.md) | Phase 12 guarded PG16/pgvector runtime and Phase 13 private Knowledge schema, exact artifact and disposable migration/recovery/integrity evidence, plus authorized legacy-volume and private `.env` key migration. |
| 2026-09-17 | [RAG through Phase 13 implementation](2026-09-17/2026-09-17-rag-through-phase-13-implementation.md) | Preparation A/B implementation after G1/G2/G4/G6 approval and delegated G5 selection; accepted ADR/model boundaries, preserved working state and per-phase evidence. |
| 2026-09-17 | [Flashcard quality offline comparison](2026-09-17/2026-09-17-flashcard-quality-offline-comparison.md) | Authored baseline-generation-renderer/refill replay, measured local outcomes and concrete four-card instructor review sample; no remote-model quality or paid-call claim. |
| 2026-09-17 | [RAG through Phase 13 startup audit](2026-09-17/2026-09-17-rag-through-phase-13-startup-audit.md) | Three read-only audits, fresh backend/AI/config baselines and explicit G1/G2/G4/G5/G6 questions before implementation; plan and existing work preserved. |
| 2026-09-17 | [Approved RAG plan update](2026-09-17/2026-09-17-rag-implementation-plan-update.md) | Updates the approved plan with flashcard quality/config preparations, independent Knowledge publication, explicit design gates and complete RAG verification/privacy/recovery contracts; no implementation. |
| 2026-09-17 | [Flashcard prompts and RAG plan review](2026-09-17/2026-09-17-flashcard-prompts-and-rag-plan-review.md) | Read-only source review of prompt yield, definitive AI profile migration and subject-scoped RAG; records independent Knowledge publication and required plan contracts before approval. |
| 2026-09-17 | [v1.0 release gate](2026-09-17/2026-09-17-v1-release-gate.md) | All eleven readiness items verified: exact-source CI, actual local encrypted SMTP and passing clean-machine production backup/restore. |
| 2026-09-17 | [Phase 11 remediation](2026-09-17/2026-09-17-phase-11-remediation.md) | Governance, Cardchemy identity, signed public v0.1.0 publication and separate v1.0 readiness work. |
| 2026-09-17 | [Local encrypted SMTP verification](2026-09-17/2026-09-17-local-smtp-tls-verification.md) | Actual authenticated STARTTLS/implicit-TLS delivery, certificate rejection, durable retry and guarded recovery with disposable local capture. |
| 2026-09-17 | [Phase 11 demo](2026-09-17/2026-09-17-phase-11-demo.md) | Bounded disposable production-build/Nginx demonstration, private generated sign-in, no provider calls and verified cleanup. |
| 2026-09-17 | [Phase 11 readiness audit](2026-09-17/2026-09-17-phase-11-readiness-audit.md) | Read-only release/governance, branding and documentation/demo audits; verified remote identity and recorded required owner decisions before implementation. |
| 2026-09-17 | [Phase 10 remediation](2026-09-17/2026-09-17-phase-10-remediation.md) | Safe structured logging/correlation, operational metrics and worker health, transactional audit, provider disclosure and guarded retention/export/deletion; isolated verification and limits. |
| 2026-09-16 | [Agent guidelines merge](2026-09-16/2026-09-16-agents-guidelines-merge.md) | Merged root and supplied agent guides, reconciled bootstrap/ownership, retained engineering safeguards and verified links. |
| 2026-09-16 | [Agent context audit](2026-09-16/2026-09-16-agents-context-audit.md) | Supporting repository audit for the supplied detailed operating guide; historical implementation evidence. |
| 2026-09-16 | [Repository context system](2026-09-16/2026-09-16-repository-context-system.md) | Source audit, canonical navigation, architecture/ADRs, setup/state, historical classification, CI link check and completion evidence. |
| 2026-09-16 | [Phase 9 merge closure](2026-09-16/2026-09-16-phase-9-merge-closure.md) | Supersedes earlier unmerged checkpoints; records merge and post-merge hosted checks. |
| 2026-09-16 | [Phase 9 remediation](2026-09-16/2026-09-16-phase-9-remediation.md) | Root configuration, cleanup, consolidated tests and real journey, secure locks, runtime/OCR probes, CI coverage/bundle gates and remote merge protection. |
| 2026-09-16 | [AI request efficiency](2026-09-16/2026-09-16-ai-request-efficiency-remediation.md) | Evidence packing, direct-generation fast path, multi-card batches, worker-wide RPM/TPM safety governor, durable request/cache telemetry, JSONB migrations, and end-to-end verification. |
| 2026-09-15 | [Provider retries/errors](2026-09-15/2026-09-15-ai-provider-retry-and-error-remediation.md) | Gemini schema compatibility, precise provider/model errors, bounded retries, stage canaries, cancellation, and worker-wide concurrency. |
| 2026-09-15 | [Provider enablement](2026-09-15/2026-09-15-ai-provider-enablement-fix.md) | API/worker enablement, worker-only credentials, startup validation, kill switch and verification. |
| 2026-09-15 | [Phase 8](2026-09-15/2026-09-15-phase-8-remediation.md) | Self-hosting, generated secrets, images, secure edge, readiness/draining and restore rehearsal. |
| 2026-09-15 | [Phase 7](2026-09-15/2026-09-15-phase-7-remediation.md) | Durable outbox, SMTP/Mailpit delivery, guarded recovery and browser evidence. |
| 2026-09-15 | [Phase 6](2026-09-15/2026-09-15-phase-6-remediation.md) | Durable study idempotency, review-all, accessibility, responsive UX and browser checks. |
| 2026-09-15 | [Phase 5](2026-09-15/2026-09-15-phase-5-remediation.md) | Typed frontend API, auth/routing recovery, mutation/progress UX and English copy. |
| 2026-09-14 | [Phase 4](2026-09-14/2026-09-14-phase-4-remediation.md) | Grounded AI, providers, summaries, deterministic quality and telemetry. |
| 2026-09-14 | [Phase 3](2026-09-14/2026-09-14-phase-3-remediation.md) | Durable PDF jobs, worker/extraction bounds, quotas, encryption, polling/retry and OCR. |
| 2026-09-14 | [Phase 2](2026-09-14/2026-09-14-phase-2-remediation.md) | Alembic, PostgreSQL integrity/cascades, authoritative study contracts and restore evidence. |
| 2026-09-14 | [Phases 0–1](2026-09-14/2026-09-14-phase-0-phase-1-remediation.md) | Reproducible baseline, auth/authorization decisions, implementation and verification. |
