# Current Development State

Snapshot: 2026-09-16. Source and roadmap reviewed in this context-system task.
Phase completion and prior verification below are recorded repository evidence,
not a fresh execution of every application/hosted/security gate.

## Current phase

The [remediation plan](../../issues-required-remediation.md) records Phases 0–9
complete. Its next development phase is 10; 11 follows for release/rebranding.
Current product version is 0.1.0. The repository context system is implemented;
its [completion checklist](../../repository-context-system-plan.md) records its
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
- Subsequent context work: canonical orientation, navigation/module maps, five
  architecture flows, accepted ADRs, local setup, historical separation and
  automatic context-file/link validation.

The [Phase 9 closure log](../../.agent/logs/2026-09-16/2026-09-16-phase-9-merge-closure.md)
supersedes earlier unmerged checkpoints in its remediation log. Detailed tasks
belong to the roadmap; implementation/check details belong to the
[dated log index](../../.agent/logs/README.md).

## Current focus and known risks

Phase 10 tracks structured logging, correlation/errors, broader metrics,
privacy disclosure/retention/export and privileged audit/operational controls.
Readiness/liveness and some queue/usage telemetry already exist in code while
the broader roadmap gate remains open; this document does not silently complete
overlapping roadmap items.

Phase 11 still tracks license choice, contribution/security policy, consistent
standalone branding, demo/release packaging and final release documentation.
This task adds a root README and orientation but does not complete Phase 11's
broader README/release requirements or select a license. Cardchemy is the
working name; application configuration/package names retain legacy values.

## Important constraints

- Local development is the reference environment. Production guides and
  hardened images exist; no live production deployment is asserted here.
- Study-session payloads hide answers, but other authorized card-read responses
  contain correct answers. See [study flow](../architecture/STUDY-PROGRESS-FLOW.md).
- Database cascade rules exist; public account deletion/export and a complete
  privacy policy are not established flows. See [data model](../architecture/DATA-MODEL.md).
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

Implement Phase 10 only when authorized; then Phase 11 and the v1.0 release
gate. Update this summary whenever a phase/milestone completes, and retain task
detail in the roadmap. For ongoing work read [orientation](../00-START-HERE.md),
[project map](../../PROJECT-MAP.md), [ADR index](../decisions/ADR-000-INDEX.md)
and [agent maintenance rules](../../AGENTS.md).
