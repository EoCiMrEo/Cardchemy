# ADR-005: Database deletion follows ownership

## Status

Accepted; existing behavior verified 2026-09-16.

## Context

Deleting accounts, subjects or temporary job history must remove owned
dependents without restoring consumed invitations or erasing retained learning content.

## Decision

Owned content, enrollment/progress/receipts, auth state, generation sources
and linked email state use foreign-key cascades. Invitation consumers use
`ON DELETE SET NULL`, retaining `used_at`. Deleting generation job history
nulls result-set/quota links; its learning content and quota charges survive.
Quota rows still cascade with the owning user.

## Rationale

Database rules apply consistently to direct deletion and application paths,
prevent orphaned private state and retain independent durable records.

## Consequences

Deletion can remove a whole content tree. Rate-limit buckets have no account
foreign key. A consumed invitation remains consumed after its student is
deleted. These rules describe persistence; no public account-deletion API is
implied. Publication guards still prevent removing a final approved card
from a surviving published set.

## Related Areas

[ADR-012](ADR-012-subject-knowledge-and-rag-boundaries.md) extends deletion
ownership for durable Subject Knowledge: document deletion removes its
pages/chunks/index jobs and detaches surviving generation/set links, preserving
flashcards; job-history deletion preserves Knowledge. Subject/account ownership
cascades Knowledge. This adds dependents without changing existing study/card
deletion rules.

[Data model and cascade table](../architecture/DATA-MODEL.md),
[model definitions](../../backend/app/models/),
[PostgreSQL integrity tests](../../backend/tests/postgres/test_database_integrity.py),
[ADR index](ADR-000-INDEX.md).
