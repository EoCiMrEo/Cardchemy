# ADR-004: Alembic owns deployed schema evolution

## Status

Accepted; existing behavior verified 2026-09-16.

## Context

Startup-created tables and one-off schema scripts cannot provide reproducible
constraints, version checks or reviewed upgrades.

## Decision

Alembic is the only deployed schema migration mechanism. The API verifies
the database is at all configured code heads before serving. Compose runs a
one-shot migration service before the API and workers.

## Rationale

Versioned migrations preserve constraints, publication triggers and a
reviewable upgrade/rollback history.

## Consequences

Model changes need migrations and disposable PostgreSQL head/drift and
upgrade/downgrade/re-upgrade verification. `Base.metadata.create_all` remains
only in disposable SQLite unit fixtures. The clean baseline is not an
adoption migration for old development databases; never reset live data.

## Related Areas

[Database lifecycle](../../backend/app/database.py),
[Alembic](../../backend/alembic/), [Compose](../../docker-compose.yml),
[database operations](../DATABASE_OPERATIONS.md), [ADR index](ADR-000-INDEX.md).
