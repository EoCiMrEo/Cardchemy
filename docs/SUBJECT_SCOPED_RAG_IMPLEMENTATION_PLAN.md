# Subject-scoped RAG plan — superseded

This path is retained for navigation from PR #12. Its 2026-09-17 proposal
was superseded by later operator-approved decisions and implementation through
the Phase 20/21 technical closure in the [current implementation plan](../Cardchemy-Subject-Scoped%20RAG%20Implementation%20Plan.md).

The original proposal remains in [commit 18bbb20](https://github.com/EoCiMrEo/Cardchemy/blob/18bbb20fd31d7c0af99cd5a0e6c297a05b6ef173/docs/SUBJECT_SCOPED_RAG_IMPLEMENTATION_PLAN.md).
Its [historical decision log](../.agent/logs/2026-09-17/2026-09-17-subject-rag-plan-review.md)
is preserved without edits. Use [ADR-012](decisions/ADR-012-subject-knowledge-and-rag-boundaries.md)
and [current state](development/CURRENT-STATE.md) for active contracts.

The former generation-upload-only, historical citation visibility and deferred
vector-dimension choices were superseded by the approved G1/G2/G4/G5/G6
decisions. They do not govern current implementation. Capture, indexing,
internal retrieval, private durable answer jobs and browser chat APIs include
the Phase 20 integrated hardening and Phase 21 privacy/observability/recovery
controls. Paid live evaluation, production enablement, the Linux-only release
rehearsal for the current source, and human assistive-technology evidence remain
separately gated.
