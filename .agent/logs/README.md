# Agent Logs

Last Updated: 2026-09-17

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
| 2026-09-17 | [v1.0 release gate](2026-09-17/2026-09-17-v1-release-gate.md) | Exact-source CI, local encrypted SMTP, clean-machine production backup/restore rehearsals and readiness evidence. |
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
