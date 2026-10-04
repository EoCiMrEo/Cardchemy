# Public and private source holdouts are separate

Date: 2026-09-30 (America/Chicago). During a read-only Lane 6 gate audit,
the plan and ADR-024 were found to call an older two-PDF Illinois holdout a
"release" or "published" holdout. Those Illinois PDFs are public audit
material and are not published in the retained Subject. A later frozen
12-case private holdout spans the three attached, published lecture PDFs.

I corrected ADR-023/024, the RAG evaluation guide, the remediation plan and
current-state wording to keep
these two samples distinct. The Illinois sample is an unpublished
supplemental generalization check. The private three-PDF sample is the
retained installation's release measurement, still subject to separate
private-transfer approval and original-page/authorization checks. Both are
unscored. This changes no threshold, public packet, provider call, runtime
policy, database, PDF archive, root `.env` or Ask enablement state.

The correction follows the previously frozen public holdout review and the
later private original-PDF gold freeze. It prevents a public score from being
mistaken for an authenticated published-Knowledge release pass. Lane 6 stays
3/7.
