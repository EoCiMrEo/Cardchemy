# Completed self-hosted project: GitHub source update

## Scope and starting state

The owner confirmed that the completed full local stack works and authorized
updating the project on GitHub. This task publishes source through the existing
protected pull-request flow. It does not create a managed production deployment,
change repository visibility, publish a version tag, or dispatch the signed
release workflow.

Starting branch was `main`, HEAD
`6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`. A normal `git fetch origin --prune`
confirmed matching remote `main`. Independent live repository reads confirmed
the public canonical repository `EoCiMrEo/Cardchemy`, owner push/admin access,
protected `main` with required GitHub Actions `ci-required`, and no open PR.
The connector could not read the complete classic protection policy, so that
check remains required before merge through an authorized read-only alternative.

The existing accumulated product-quality changes are preserved: 145 modified
and 840 individual untracked candidate paths, 985 total, approximately 12.25 MB.
The independent publication-scope audit found only source/text files, no PDFs,
model weights, database dumps, caches or generated binary outputs. Root `.env`,
backups, verification receipts, build/security artifacts and local model data
are ignored and untracked. All 536 changed/new Python files parse; twelve JSON
files parse. The limited high-confidence credential-pattern scan found nothing;
it does not replace complete history/source secret scanning.

## Readiness and preservation

The previously completed Lane 6 remains seven of seven; Lane 7 remains outside
this source-publication task. Its dated closure contains the actual local
activation, source-only behavior, independent public/private usefulness,
original-PDF, migration, access, browser, accessibility and release evidence:
[Lane 6 closure](../2026-10-03/2026-10-03-lane6-final-closure-and-activation.md).

Fresh required hosted checks must validate the exact PR candidate and merged
main commit. The current local backend run has 5,362 passing tests, 271 skipped
and two opted-out live tests, without coverage instrumentation. The old coverage
report is historical; it is not current-tree coverage proof. Existing local
frontend, disposable PostgreSQL, deterministic journeys and exact runtime
security results remain separate from hosted CI.

Independent CI review found one maintained documentation mismatch: `docs/CI.md`
still listed the pre-PDF.js asset limits. Only that guide was corrected to the
previously approved current budgets, retaining the historical Phase 9 baseline.
Current emitted build passed: 123,457 initial gzip bytes, 1,265,413 largest raw
JavaScript bytes and 756,476 total gzip bytes, including `.mjs` worker assets.
The actual budgets remain 130,000 / 1,350,000 / 780,000. Workflow/context/release
identity/notice checks passed; no workflow, runtime, budget or test behavior was
changed during this publication preparation.

The populated volumes, original PDFs, independent encryption/signing secrets,
root configuration and healthy running self-hosted stack remain untouched.
Normal Git branch/push/PR operations will preserve shared history and enforce
current-base checks. No paid AI request is part of publication.

## Publication evidence

The normal owner Git credential provided the read-only administration check
that the connector could not perform. Credential material stayed in process
memory and was neither printed nor persisted. Actual `main` protection matches
the complete repository definition: strict/current-base `ci-required` from
GitHub Actions app 15368, administrator enforcement, required PR flow, resolved
conversations, no force push and no branch deletion. No policy was changed.

The prospective history/source scan passed with cached pinned scanners and
network disabled: Gitleaks full history plus prospective snapshot returned zero
findings; Trivy Git-visible source returned zero secrets. All 1,299 exported
paths and HEAD were unchanged during the scan. Isolated snapshot commit was
`95d9b9a1a42064c2419d4ac1d6e517044dd9791f`; the source manifest SHA was
`cb90b223831d0441cb8c09f65baea3b7542c76cc7c59c718c7db947d11257f9b`.
Owned scanner containers and exports were cleaned. The later additions to this
log are authored content-free operational evidence, not runtime/source changes.

The new publication branch is `codex/product-quality-remediation`. The first
staging attempt was blocked by a pre-existing empty `.git/index.lock` dated
2026-10-02. After checking that no Git process was running, the exact old lock
was moved into ignored verification storage; it was not discarded. No source,
index, commit or user configuration was replaced to repair the lock.

Commit, PR, required hosted checks, merge and exact-main confirmation remain
pending. Their actual results will be recorded after they exist.

The exact Git-visible staging manifest excludes all operator/ignored artifacts.
Checking the now-staged previously untracked files additionally exposed thirteen
existing whitespace findings: eight trailing spaces inside the used migration
0027 and five extra final blank lines in dated logs, a historical ADR and a test.
These files are preserved as reviewed; this optional check returned two, not a
pass. No migration history, source semantics, security/coverage/bundle threshold
or required CI gate was rewritten to silence formatting warnings. Earlier plain
worktree diff checks covered tracked modifications and remain their own scope.
