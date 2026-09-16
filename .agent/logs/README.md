# Agent Logs

Last Updated: 2026-09-16

This directory records agent-visible development history for Cardchemy: what changed, why the work was needed, what problems appeared, how they were solved, and how the result was verified.

Do not store secrets, environment values, passwords, or long-lived credentials in these logs. Disposable QA credentials may be described only by purpose and cleanup status.

## Log Index

| Date | Log | Summary |
|---|---|---|
| 2026-09-16 | `2026-09-16-phase-9-remediation.md` | Root configuration, cleanup, consolidated tests and real journey, secure locks, runtime/OCR probes, CI coverage/bundle gates and remote merge protection. |
| 2026-09-16 | `2026-09-16-ai-request-efficiency-remediation.md` | Evidence packing, direct-generation fast path, multi-card batches, worker-wide RPM/TPM safety governor, durable request/cache telemetry, JSONB migrations, and end-to-end verification. |
| 2026-09-15 | `2026-09-15-ai-provider-retry-and-error-remediation.md` | Gemini schema compatibility, precise provider/model errors, three fixed-delay retries, stage canaries, fail-fast cancellation, and worker-wide request concurrency. |
| 2026-09-15 | `2026-09-15-ai-provider-enablement-fix.md` | Non-secret AI enablement shared by API and worker, worker-only provider credentials, fail-fast validation, no-claim kill switch, and runtime verification. |
| 2026-09-15 | `2026-09-15-phase-8-remediation.md` | Production-shaped self-hosting, generated secrets, multi-stage images, secure SPA edge, readiness/draining, backup/restore rehearsal, and platform evidence. |
| 2026-09-15 | `2026-09-15-phase-7-remediation.md` | Transactional email outbox, bounded SMTP worker, Mailpit capture/fault tests, reset and invitation delivery, guarded recovery, and live browser verification. |
| 2026-09-15 | `2026-09-15-phase-6-remediation.md` | Durable study-answer idempotency, valid review-all sessions, keyboard/screen-reader semantics, reduced motion, responsive/touch-safe UI, axe coverage, and 44 browser checks. |
| 2026-09-15 | `2026-09-15-phase-5-remediation.md` | Typed frontend API architecture, race-safe authentication, guarded routing, resilient join/edit/progress flows, centralized English copy, and 31 browser checks. |
| 2026-09-14 | `2026-09-14-phase-4-remediation.md` | Strict source-grounded generation, provider portability, hierarchical summaries, deterministic quality/deduplication, token/cost telemetry, operator UI, and fixed-corpus verification. |
| 2026-09-14 | `2026-09-14-phase-3-remediation.md` | Durable PostgreSQL PDF-generation jobs, bounded worker/extraction, quotas, encrypted source retention, polling/cancel/retry UI, optional OCR, and verification evidence. |
| 2026-09-14 | `2026-09-14-phase-2-remediation.md` | Clean Alembic baseline, PostgreSQL constraints/cascades/transactions, server-authoritative study contracts, frontend alignment, and migration/restore verification. |
| 2026-09-14 | `2026-09-14-phase-0-phase-1-remediation.md` | Phase 0 reproducible baseline and Phase 1 authentication/authorization remediation, decisions, implementation map, and verification evidence. |
