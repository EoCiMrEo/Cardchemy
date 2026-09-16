# Documentation Index

Start at [00-START-HERE.md](00-START-HERE.md), then use the
[project map](../PROJECT-MAP.md) and [backend](../backend/MOC.md)/
[frontend](../frontend/MOC.md) module maps. These are current navigation;
implementation remains the final source of truth.

## Current architecture and decisions

[System overview](architecture/SYSTEM-OVERVIEW.md),
[data model](architecture/DATA-MODEL.md), [auth](architecture/AUTH-FLOW.md),
[AI generation](architecture/AI-GENERATION-FLOW.md),
[study/progress](architecture/STUDY-PROGRESS-FLOW.md) and
[accepted ADRs](decisions/ADR-000-INDEX.md).

## Current operational and development guides

These existing guides retain their domain ownership; architecture docs link to
them for operational detail rather than copying their setting tables/commands.

| Guide | Owns |
| --- | --- |
| [Local setup](development/LOCAL-SETUP.md) | First installation and editing modes |
| [Current state](development/CURRENT-STATE.md) | Phase/milestone summary and limits |
| [Configuration](CONFIGURATION.md) | Root settings, ranges, precedence, service consumers and applying changes |
| [Runtimes](RUNTIMES.md) | Supported runtime/platform versions |
| [Deployment](DEPLOYMENT.md) | Compose variants, TLS/edge, draining, volumes, image/recovery procedures |
| [Database operations](DATABASE_OPERATIONS.md) | Migration chain, backup/restore and safe rollback |
| [Authentication](AUTHENTICATION.md) | Secrets, instructor bootstrap, browser session and recovery operations |
| [PDF generation](PDF_GENERATION.md) | Upload contract, bounds, encrypted-source retention, OCR and operations |
| [AI generation](AI_GENERATION.md) | Grounding, packing, budgets, validation, quality and telemetry contracts |
| [AI providers](AI_PROVIDERS.md) | Provider configuration, retry/error and request governance |
| [AI evaluation](AI_EVALUATION.md) | Fixed corpus, thresholds and explicitly opted-in paid evaluation |
| [Email delivery](EMAIL_DELIVERY.md) | SMTP, Mailpit, outbox retry/ambiguity and operator recovery |
| [Testing](TESTING.md) | Maintained suites, safe harnesses and live/gated boundaries |
| [CI](CI.md) | Mandatory jobs, budget/scanning/protection contracts and recorded baselines |
| [Dependencies](DEPENDENCIES.md) | Dependency/hashed-lock policy and tooling |
| [Versioning](VERSIONING.md) | SemVer and intentional release synchronization |
| [Accessibility](ACCESSIBILITY.md) | Automated interaction checks and manual release AT pass |
| [Localization](LOCALIZATION.md) | English catalog and requirements for another language |

[Remediation plan](../issues-required-remediation.md) owns detailed phase tasks;
[changelog](../CHANGELOG.md) owns release history. Update guides with affected
code per [AGENTS.md](../AGENTS.md). Run `python scripts/check_context.py` from root
for active local documentation paths; it does not prove external URLs or claims.

## Historical reference

[Archive](archive/README.md) contains superseded product ideas.
[Dated agent logs](../.agent/logs/README.md) preserve implementation and verification
snapshots, including earlier paths/failed baselines; newer evidence supersedes
them. The completed [context-system plan](../repository-context-system-plan.md)
is a reusable implementation reference, not a second project orientation.
Supporting-artifact governance/navigation are in
[.agent/README.md](../.agent/README.md) and [.agent/MOC.md](../.agent/MOC.md).
