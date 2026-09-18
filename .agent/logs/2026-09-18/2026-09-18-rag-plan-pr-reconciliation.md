# Historical plan PR reconciliation

The operator requested merging all PRs, including draft #12. Its original
commit `18bbb20` predates the approved G1/G2/G4/G5/G6 decisions and completed
RAG foundation through Phase 13. Merging its full duplicate plan unchanged
would introduce contradictory upload, citation-history and embedding policies.

The feature history was merged normally, preserving the original PR commit.
The obsolete docs plan now explicitly points to the current root plan,
ADR-012 and current state. Its original content remains available at the
original GitHub commit. The historical decision log was moved into the dated
2026-09-17 folder without changing its bytes; original SHA256 is
`5108ea2b35f3baff0298eab74474177300c601e40348f9348fc03d127fa1025d`.
The current complete log index is preserved and both historical and
reconciliation records are indexed. This supersedes the old proposal as active
guidance without rewriting historical evidence.

No runtime, configuration, schema or provider calls are changed by this
reconciliation. Context validation and current-base protected CI are required
before merge; their results will be recorded after execution.
