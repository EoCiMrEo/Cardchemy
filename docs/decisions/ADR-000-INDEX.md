# Architecture Decision Index

These short records explain durable decisions already implemented or accepted
in remediation work. Recorded 2026-09-16 after source/log review; that is the
recording date, not a claim that each decision was first made today.
Read [orientation](../00-START-HERE.md) and the relevant architecture flow before
changing a decision. Code remains the implementation authority.

| ADR | Status | Boundary |
| --- | --- | --- |
| [001: Four-option cards](ADR-001-four-option-cards.md) | Accepted | Current card/product shape |
| [002: Server-derived correctness](ADR-002-server-derived-correctness.md) | Accepted | Answer trust and scheduling |
| [003: Completion and mastery](ADR-003-completion-and-mastery.md) | Accepted | Distinct progress metrics |
| [004: Alembic schema ownership](ADR-004-alembic-schema-ownership.md) | Accepted | Schema migration/startup |
| [005: Deletion cascades](ADR-005-deletion-cascades.md) | Accepted | Persisted ownership and dependent data |
| [006: Grounded generation validation](ADR-006-grounded-generation-validation.md) | Accepted | Untrusted AI output before persistence |
| [007: Root configuration](ADR-007-root-configuration.md) | Accepted | File configuration and secret injection |
| [008: PostgreSQL durable jobs](ADR-008-postgresql-durable-jobs.md) | Accepted | Bounded asynchronous generation |
| [009: Session and role boundaries](ADR-009-session-and-role-boundaries.md) | Accepted | Tokens, sessions, signup and authorization |
| [010: Transactional email](ADR-010-transactional-email.md) | Accepted | Atomic intent and SMTP ambiguity |
| [011: Operational privacy controls](ADR-011-operational-privacy-controls.md) | Accepted | Content-free diagnostics/audits and operator-mediated lifecycle controls |
| [012: Subject Knowledge and RAG boundaries](ADR-012-subject-knowledge-and-rag-boundaries.md) | Accepted design; implementation follows the RAG plan | Installation/privacy/versioning/model/worker contracts for Subject Knowledge |

## Maintenance

Add an ADR for decisions affecting multiple modules, costly reversals, product
invariants, data contracts, or security boundaries. Use Status, Context,
Decision, Rationale, Consequences and Related Areas. Include current source and
architecture links. Do not turn task logs or speculative ideas into accepted ADRs.

When reversing a decision, add a new numbered record, mark the old one
superseded, link both directions and update this index plus affected architecture.
Do not erase the rationale that explains historical data or behavior. See
[agent maintenance rules](../../AGENTS.md) and [current state](../development/CURRENT-STATE.md).
