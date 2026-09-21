# Cardchemy public roadmap

This page describes implemented capabilities and proposals. It is not a
delivery-date commitment. [Current state](docs/development/CURRENT-STATE.md)
summarizes completed milestones; this page owns current proposals. Completed
engineering trackers are in the [documentation archive](docs/archive/README.md).
[Accepted ADRs](docs/decisions/ADR-000-INDEX.md) explain decisions already made.

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
- Instructor-owned, revisioned Subject Knowledge with PostgreSQL/pgvector and
  full-text retrieval, isolated Gemini embedding/answer workers, private durable
  Ask AI conversations, grounded citations, lifecycle controls and deterministic
  RAG-off/RAG-on evaluation and recovery gates.

## Release work and verification

Phases 0–11 cover the secure self-hosted foundation, branding, governance,
no-quota demo, documentation/screenshots and verifiable release packaging.
Subject Knowledge/RAG Phases 12–21 cover the implemented retrieval, private
Ask AI, privacy, observability and release closure. Their completed task detail
is preserved in the [archived remediation tracker](docs/archive/issues-required-remediation.md)
and [archived RAG implementation plan](<docs/archive/Cardchemy-Subject-Scoped RAG Implementation Plan.md>).
Published artifacts belong to [releases](https://github.com/EoCiMrEo/Cardchemy/releases).

The separate v1.0 readiness gate passed clean-machine production-profile
deployment/recovery, actual local encrypted SMTP delivery/recovery, complete
release evidence and a reported human spoken assistive-technology check. See
[gate evidence](.agent/logs/2026-09-17/2026-09-17-v1-release-gate.md).
The published version remains 0.1.0. Each operator still verifies provider
quality, external SMTP/DNS/mailbox delivery and their own hosting/recovery goals.

## Proposals requiring a decision

Native mobile clients, another UI language, offline study/PWA/conflict handling,
quiz/rewards features, a broker/Redis/Celery layer and broader
multi-tenant/distributed governance have **no accepted implementation or
delivery commitment**. Evaluate a concrete user need, privacy/data design,
operating costs and compatibility before accepting any proposal.

The [documentation archive](docs/archive/README.md) contains the completed phase
trackers and early brainstorming, including superseded tooling and affiliation
claims. Cardchemy is a standalone project. Discuss new work in a feature issue;
do not treat archived prose as current instructions or a new architecture change.
