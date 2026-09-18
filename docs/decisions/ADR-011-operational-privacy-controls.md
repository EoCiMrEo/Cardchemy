# ADR-011: Content-free diagnostics and operator-mediated privacy

## Status

Accepted within authorized Phase 10 remediation, 2026-09-17.

## Context

Raw tracebacks, validation inputs and SQL/access logs can disclose user data.
Operators need durable correlation/metrics, privileged audits and predictable
privacy controls without introducing another queue or public account workflow.

## Decision

Use server-issued request UUIDs and persisted generation origin correlation,
closed structured log fields/safe error contracts, PostgreSQL request metadata
and loop heartbeats, and transactional fixed-field privileged audits. Operator
CLI owns aggregate/job diagnostics, authorized private exports, explicit
quiesced account deletion and bounded metadata-retention preview/application.
Accounts/content/progress/study receipts have no automatic age-based deletion.
Optional numeric aggregate reporting has no default destination, is disabled
by default and requires an explicit operator command.

## Rationale

Existing PostgreSQL and operator boundaries support diagnosability without
uploading content, adding a persistence layer or weakening lifetime study
idempotency. Business/audit commit ownership remains atomic.

## Consequences

Request metadata is bounded best effort, not a billing/security ledger. Direct
role updates are audited by a PostgreSQL trigger, without a new role API.
Retained UUIDs are operational pseudonyms, not anonymization guarantees.
Operators own log/backup/provider/collector expiry and deployment disclosures.
Metadata cleanup shortens job-history idempotency and historical metric windows.
Deletion is explicit and requires draining/backup checks. Exports contain
private content and need secure fulfillment. No live production or legal
compliance claim follows from these controls.

## Related Areas

[Observability](../OBSERVABILITY.md), [privacy](../PRIVACY.md),
[settings](../../backend/app/config.py), [operations](../../backend/app/services/operations.py),
[privacy service](../../backend/app/services/privacy.py),
[audit service](../../backend/app/services/audit.py), [data model](../architecture/DATA-MODEL.md),
[ADR index](ADR-000-INDEX.md).
