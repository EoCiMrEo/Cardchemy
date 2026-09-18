# Root AGENTS.md repository-context audit

Date: 2026-09-16

## Scope

Performed a repository-wide context audit to author a root `AGENTS.md` for Cardchemy.

The goal was to give future AI coding agents and developers a stable operating guide that preserves the project's implemented security, data-integrity, AI, frontend, testing, deployment, and documentation contracts without requiring every new session to rediscover the repository from scratch.

No application behavior, source code, database schema, dependency, configuration, or GitHub repository state was changed.

## Repository state reviewed

Repository: `EoCiMrEo/Cardchemy`

Default branch reviewed: `main`

Tree/commit inspected: `a9461b712e043def32228b3b111474b1fe1ec383`

The requested `.agent/AGENTS.md` was not present in the reviewed tree, so there was no nested agent instruction file to apply.

The real root `.env` was not read or exposed. Configuration understanding came from `.env.example`, validated settings, Compose, and maintained documentation.

No subagent-execution capability was available in this session, so the audit was performed directly against the repository.

## Areas inspected

The audit covered the repository structure and current implementation boundaries, including:

- root configuration, Compose variants, operational scripts, GitHub workflows, security configuration, and remediation roadmap;
- `.agent/logs/` index and remediation history through Phases 0-9 plus AI-provider enablement, retry/error classification, and request-efficiency follow-up work;
- FastAPI startup, database lifecycle, validated settings, health endpoints, and route ordering;
- authentication/session/invitation/password-reset models, routes, services, and security contracts;
- subject, set, card, enrollment, study-progress, and answer-idempotency models/contracts;
- durable generation reservation/upload/cancel/retry flow, quotas, encrypted source storage, worker leases/fencing, and atomic result persistence;
- provider-neutral AI chunking/pipeline/grounding/provider/rate-governor boundaries and request/cost telemetry;
- transactional email outbox architecture and operational policy;
- Alembic schema ownership, current migration chain, and database operations;
- React routing, authentication context, Axios refresh behavior, typed API contracts, generation polling, study persistence/retry behavior, accessibility, and localization;
- maintained test commands, CI required checks, coverage/bundle/security gates, deployment topology, and supported runtimes.

## Key invariants captured in the generated guide

The root `AGENTS.md` records, among other things:

- instructor/student role and subject ownership/enrollment boundaries;
- no public instructor registration;
- rotating server-backed refresh sessions and memory-only browser access tokens;
- exactly-four-option multiple-choice card invariants;
- explicit instructor approval for AI-generated cards;
- server-derived study correctness and quality;
- durable study-answer idempotency receipts;
- separate completion and mastery semantics;
- Alembic-only production schema ownership and timezone-aware UTC;
- durable PostgreSQL generation jobs with encrypted temporary source storage;
- worker lease/fencing and all-or-nothing generated-set persistence;
- strict source grounding and untrusted-document/model-output boundaries;
- bounded provider retries, worker-wide RPM/TPM governance, and no unapproved paid live-AI testing;
- transactional email outbox behavior and secret isolation;
- root `.env` as the only supported user-managed file configuration source;
- English-only and online-first v1 frontend policy;
- authoritative verification commands and the `ci-required` merge gate.

## Current project status observed

`issues-required-remediation.md` records Phases 0-9 complete as of 2026-09-16.

Phase 10 remains open for observability, privacy, retention/export controls, auditability, and related operational hardening.

Phase 11 remains open for license, root README, contributor/security documentation, final open-source packaging, demo/release work, and consistent Cardchemy branding.

The generated `AGENTS.md` tells future agents to re-read the roadmap rather than treating that phase snapshot as permanently current.

## Design decisions for AGENTS.md

The file is an operational guide rather than a second architecture specification.

It:

- separates implementation truth, maintained documentation, historical agent evidence, and archived material;
- defines a mandatory startup protocol;
- gives a high-level repository map without indexing every source file;
- captures cross-cutting invariants that can be violated when reading only one feature file;
- ties verification requirements to change scope;
- requires substantial future work to leave durable `.agent/` evidence without storing secrets/private content;
- avoids dependence on chat memory;
- avoids claiming planned Phase 10/11 capabilities already exist.

## Verification

Referenced paths and commands in the generated `AGENTS.md` were checked against the reviewed repository tree and maintained documentation.

No application test suite was run because this task produced documentation artifacts only and did not modify application behavior.

When this log is added to the repository, update the nearest `.agent/logs/` MOC/index according to the workspace navigation rules in use at that time.
