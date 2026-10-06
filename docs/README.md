# Documentation index

Start with [00-START-HERE.md](00-START-HERE.md), then the
[project map](../PROJECT-MAP.md) and [backend](../backend/MOC.md)/
[frontend](../frontend/MOC.md) module maps. Source remains the implementation
authority; guides own supported contracts and operating procedures.

For a visual tour, open the [architecture diagrams](diagrams/README.md).
They show each workflow, model role, local fallback, data/access boundary and
the signed release flow, with links to the maintained contracts and source.

## Guides by domain

| Domain | Guides and responsibility |
| --- | --- |
| [Development](development/README.md) | [Local setup](development/LOCAL-SETUP.md), [current state](development/CURRENT-STATE.md), [testing](development/TESTING.md), [runtimes](development/RUNTIMES.md), [demo](development/DEMO.md) and dated [name review](development/NAME-REVIEW.md) |
| [AI, PDFs and Knowledge](ai/README.md) | [Generation](ai/AI_GENERATION.md), [PDFs](ai/PDF_GENERATION.md), [providers](ai/AI_PROVIDERS.md), [profile migration](ai/AI_PROFILE_MIGRATION.md), [generation evaluation](ai/AI_EVALUATION.md), [RAG evaluation](ai/RAG_EVALUATION.md) and [Ask maintenance](ai/ASK_AI_SHUTDOWN.md) |
| [Operations](operations/README.md) | [Configuration](operations/CONFIGURATION.md), [deployment](operations/DEPLOYMENT.md), [observability](operations/OBSERVABILITY.md) and [production rehearsal](operations/PRODUCTION_REHEARSAL.md) |
| [Database](database/README.md) | [Migrations, backup/restore and rollback](database/DATABASE_OPERATIONS.md) |
| [Mail server](mail-server/README.md) | [Email delivery](mail-server/EMAIL_DELIVERY.md) and [SMTP verification](mail-server/SMTP-VERIFICATION.md) |
| [Security and privacy](security/README.md) | [Authentication](security/AUTHENTICATION.md) and [privacy/lifecycle controls](security/PRIVACY.md) |
| [CI/CD and releases](ci-cd/README.md) | [CI](ci-cd/CI.md), [dependencies](ci-cd/DEPENDENCIES.md), [versioning](ci-cd/VERSIONING.md) and [releasing](ci-cd/RELEASING.md) |
| [UI](ui/README.md) | [Accessibility](ui/ACCESSIBILITY.md) and [localization](ui/LOCALIZATION.md) |

## Architecture and durable decisions

[System overview](architecture/SYSTEM-OVERVIEW.md),
[data model](architecture/DATA-MODEL.md), [auth flow](architecture/AUTH-FLOW.md),
[generation flow](architecture/AI-GENERATION-FLOW.md),
[Knowledge flow](architecture/SUBJECT-KNOWLEDGE-FLOW.md),
[study/progress](architecture/STUDY-PROGRESS-FLOW.md) and
[accepted ADRs](decisions/ADR-000-INDEX.md).

[Current state](development/CURRENT-STATE.md) owns milestone evidence;
the [public roadmap](../ROADMAP.md) owns pending work/proposals.
[Contribution](../CONTRIBUTING.md), [security](../SECURITY.md),
[conduct](../CODE_OF_CONDUCT.md), [brand terms](../BRANDING.md) and
[changelog](../CHANGELOG.md) govern participation and release history.
Update affected guides with source changes per [AGENTS.md](../AGENTS.md).
Run `python scripts/check_context.py` from root for maintained local paths;
it does not prove remote URLs, provider quality or current installation health.

## Historical evidence

[Archived trackers and ideas](archive/README.md) preserve completed/superseded
plans; retirement does not mark unresolved work complete.
[Dated agent logs](../.agent/logs/README.md) preserve implementation/results,
failed baselines, consumed provider attempts and earlier paths without changing
their historical bodies. Supporting-artifact rules are in
[.agent/README.md](../.agent/README.md) and [.agent/MOC.md](../.agent/MOC.md).
