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
| [003: Completion and mastery](ADR-003-completion-and-mastery.md) | Display/success decision superseded by ADR-016; API meanings retained | Attempted completion and mastery |
| [004: Alembic schema ownership](ADR-004-alembic-schema-ownership.md) | Accepted | Schema migration/startup |
| [005: Deletion cascades](ADR-005-deletion-cascades.md) | Accepted | Persisted ownership and dependent data |
| [006: Grounded generation validation](ADR-006-grounded-generation-validation.md) | Accepted validation; pre-result candidate retention extended by ADR-020 | Untrusted AI output before persistence |
| [007: Root configuration](ADR-007-root-configuration.md) | Accepted | File configuration and secret injection |
| [008: PostgreSQL durable jobs](ADR-008-postgresql-durable-jobs.md) | Accepted; private staged choice and exact-count finalization extended by ADR-020 | Bounded asynchronous generation |
| [009: Session and role boundaries](ADR-009-session-and-role-boundaries.md) | Accepted | Tokens, sessions, signup and authorization |
| [010: Transactional email](ADR-010-transactional-email.md) | Accepted | Atomic intent and SMTP ambiguity |
| [011: Operational privacy controls](ADR-011-operational-privacy-controls.md) | Accepted | Content-free diagnostics/audits and operator-mediated lifecycle controls |
| [012: Subject Knowledge and RAG boundaries](ADR-012-subject-knowledge-and-rag-boundaries.md) | Accepted boundaries; provider and remote-support/retry choices superseded by ADR-014/015/019 | Installation/privacy/versioning/worker contracts for Subject Knowledge |
| [013: Password hash compatibility](ADR-013-password-hash-compatibility.md) | Accepted | Direct bcrypt with unchanged v2 records and historic password verification |
| [014: Native Gemini RAG profiles](ADR-014-native-gemini-rag-profiles.md) | Accepted 001 embedding contract; Ask retry/support choices superseded by ADR-019 and extended by ADR-018 | Native embedding and task-aware space migration |
| [015: Ask pause and Gemini catalog](ADR-015-ask-pause-and-gemini-catalog.md) | Accepted catalog and historical fence; replacement completed by ADR-019 | Separate Ask shutdown, closed text catalog and historical snapshot retention |
| [016: Study progress and option order](ADR-016-study-progress-and-option-order.md) | Accepted | Correct-card Progress, attempt accuracy, exact completion gate and presentation shuffle |
| [017: Repeat Knowledge upload choice](ADR-017-repeat-knowledge-upload-choice.md) | Accepted; supersedes ADR-012 for distinct exact-byte repeats and reuse ownership; reviewed/published capture cancellation narrowed by ADR-020 | Durable same-Subject choice, revision no-op and upload/Knowledge accounting |
| [018: Gemini Embedding 2 space](ADR-018-gemini-embedding-2-space.md) | Accepted optional staging profile; 001 remains default | Versioned model-2 formatting, isolation, staging and cutover |
| [019: Two-request Ask with local support](ADR-019-two-request-local-support-ask.md) | Historical implementation; new-job answer execution superseded by ADR-022 | Former one-embedding/one-answer contract and manual retry consent |
| [020: Validated-card choice](ADR-020-validated-card-choice.md) | Accepted; Lane 6 local release complete; exact smaller-count confirmation remains bounded/private | Bounded private candidate staging, exact-count confirmation and Knowledge cancellation ownership |
| [021: Related Knowledge excerpts](ADR-021-related-knowledge-excerpts.md) | Historical fallback; new-job default/two-excerpt cap superseded by ADR-022 | Former source-labeled browsing excerpt for failed/abstained Ask outcomes |
| [022: Source-first related Knowledge Ask](ADR-022-related-knowledge-primary-ask.md) | Accepted source-only and access boundaries; runtime sufficiency gate and extracted-page-only viewer superseded by ADR-023 | One-embedding source browsing, distinct terminal result and no new answer generation |
| [023: Original-PDF source navigation](ADR-023-original-pdf-source-navigation.md) | Accepted source-only/PDF contract; bounded source judging/literal context extended by ADR-024; local release complete | Automatic unverified related reading, original-PDF page viewer, local lexical fallback and durable encrypted archive |
| [024: Gemini source-ID judging](ADR-024-gemini-source-id-judge.md) | Accepted released v8/visual-v5/admission-v2; fresh installs default-off; historical failed pilots remain failed | At most one source-ID judgment after one raw-current-question embedding, immutable bounded literal subject for unresolved follow-ups, zero answer generation, locally derived exact references and public-first privacy/quality gates |

## Maintenance

Add an ADR for decisions affecting multiple modules, costly reversals, product
invariants, data contracts, or security boundaries. Use Status, Context,
Decision, Rationale, Consequences and Related Areas. Include current source and
architecture links. Do not turn task logs or speculative ideas into accepted ADRs.

When reversing a decision, add a new numbered record, mark the old one
superseded, link both directions and update this index plus affected architecture.
Do not erase the rationale that explains historical data or behavior. See
[agent maintenance rules](../../AGENTS.md) and [current state](../development/CURRENT-STATE.md).
