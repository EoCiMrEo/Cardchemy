# Current Development State

Snapshot: 2026-09-17. Phases 0–11 are complete. The public v0.1.0 release
contains independently verified keyless-signed image digests, checksums,
source/provenance, audits and SBOMs. The separate v1.0 gate remains in progress.

## Current phase

The [remediation plan](../../issues-required-remediation.md) records Phases 0–11
complete. The separate v1.0 operational readiness gate is in progress.
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

The [Phase 9 closure log](../../.agent/logs/2026-09-16/2026-09-16-phase-9-merge-closure.md)
supersedes earlier unmerged checkpoints in its remediation log. Detailed tasks
belong to the roadmap; implementation/check details belong to the
[dated log index](../../.agent/logs/README.md).
The [Phase 10 closure log](../../.agent/logs/2026-09-17/2026-09-17-phase-10-remediation.md)
records current verification and its limits. Alembic head is `20260917_0008`;
operators must apply the documented upgrade before starting this code.

## Current focus and known risks

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

Finish the clean-machine [production recovery rehearsal](../PRODUCTION_REHEARSAL.md)
and final hosted CI for the separate v1.0 gate. Actual authenticated local
[TLS SMTP delivery/recovery](../SMTP-VERIFICATION.md) passed both supported modes.
Completing readiness does not publish v1.0. Update this summary whenever a
phase/milestone completes, and retain task
detail in the roadmap. For ongoing work read [orientation](../00-START-HERE.md),
[project map](../../PROJECT-MAP.md), [ADR index](../decisions/ADR-000-INDEX.md)
and [agent maintenance rules](../../AGENTS.md).
