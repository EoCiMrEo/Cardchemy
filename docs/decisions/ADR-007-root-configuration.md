# ADR-007: One root file for user-managed configuration

## Status

Accepted. Records the implemented Phase 9 configuration decision; verified
2026-09-16. [Decision index](ADR-000-INDEX.md).

## Context

Separate backend/frontend environment files and cwd-dependent loading allowed
settings to diverge and made local and container setup confusing. Sharing all
settings with every container would also expose credentials unnecessarily.

## Decision

Use repository-root `.env` as the sole user-managed file, with root
[.env.example](../../.env.example) as its only template. Resolve it from source
paths, not process cwd. Nonempty process values take precedence over file values,
then validated defaults. Disable Vite's component/mode env-file discovery.
Expose only intentional public browser settings. Compose injects provider keys
only into the generation worker and SMTP credentials only into the email worker.

## Rationale

One documented file reduces divergence. Explicit per-service injection retains
credential boundaries while process overrides support containers and safe tests.

## Consequences

Bootstrap refuses to overwrite an installation. Secret rotation requires a
coordinated data/session plan; changing root settings requires affected process
restart/container recreation, and browser public settings require a rebuild.
Tests inject their own settings and avoid operator `.env`. Native processes
reading the shared root file do not gain Compose's credential isolation.

## Related areas

[Settings](../../backend/app/config.py), [public loader](../../frontend/config/environment.mjs),
[Vite](../../frontend/vite.config.ts), [Compose](../../docker-compose.yml),
[bootstrap](../../scripts/bootstrap_env.py), [configuration guide](../CONFIGURATION.md),
[system overview](../architecture/SYSTEM-OVERVIEW.md).
