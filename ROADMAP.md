# Cardchemy public roadmap

This page describes implemented capabilities and proposals. It is not a
delivery-date commitment. [Current state](docs/development/CURRENT-STATE.md)
summarizes milestones; the [remediation tracker](issues-required-remediation.md)
owns engineering tasks and release gates. [Accepted ADRs](docs/decisions/ADR-000-INDEX.md)
explain decisions already made.

## Implemented

- Instructor-owned subjects, invitation-backed student enrollment and revocable
  rotating sessions; instructor provisioning is operator CLI only.
- Bounded PDF upload, optional local OCR, encrypted temporary sources and
  PostgreSQL generation workers with leases, cancellation and manual retry.
- Gemini and OpenAI-compatible generation, strict source-grounded four-option
  cards, quality checks and instructor approval/publication.
- Online student study with durable answer receipts, server-derived grading
  and spaced repetition, completion/accuracy/mastery views.
- Transactional password-recovery/invitation email, conservative delivery
  recovery, local Mailpit and encrypted production SMTP configuration.
- Root-only configuration, production-shaped Compose, Alembic schema ownership,
  guarded service/journey tests and mandatory CI/security/accessibility budgets.
- Content-free diagnostics/correlation, worker health, transactional audits,
  authorized operator exports/deletion and bounded metadata retention. Optional
  aggregate reporting remains disabled by default.

## Release work and verification

Phase 11 covers consistent Cardchemy branding, governance, a no-quota demo,
documentation/screenshots and verifiable release packaging. Its individual
completion and publishing status belongs to the remediation tracker and
[releases](https://github.com/EoCiMrEo/Cardchemy/releases).

The separate v1.0 gate includes clean-machine deployment, complete release
evidence and manual spoken assistive-technology checks. Automated tests and
documentation alone do not establish live provider quality, production SMTP
delivery or a production deployment.

## Proposals requiring a decision

Native mobile clients, another UI language, offline study/PWA/conflict handling,
quiz/rewards features, RAG/vector search, a broker/Redis/Celery layer and broader
multi-tenant/distributed governance have **no accepted implementation or
delivery commitment**. Evaluate a concrete user need, privacy/data design,
operating costs and compatibility before accepting any proposal.

The [archived early idea](docs/archive/idea.md) is historical brainstorming,
including superseded tooling and affiliation claims. Cardchemy is a standalone
project. Discuss new work in a feature issue; do not treat archived prose as a
shipped feature or an approved architecture change.
