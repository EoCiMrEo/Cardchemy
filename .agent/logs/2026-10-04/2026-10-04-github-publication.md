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

## First published candidate and fresh-CI diagnosis

Commit `2d96b68bbe1d13e82942b8374e592f23f0986313` contains 987 changed paths,
including the new publication evidence and previously unchanged CI guide fix.
It was pushed normally, without force, and opened as
[PR 41](https://github.com/EoCiMrEo/Cardchemy/pull/41). The PR is attached to this
task. Remote base remains the original main commit; GitHub reports no conflicts.

The first hosted CI run, `37221870078`, completed seven mandatory jobs
successfully and six unsuccessfully, including the required aggregator.
Frontend, real deterministic journey, database artifact, full-history/source
secret scanning and all three runtime image checks passed. Separate dependency
review `37221870079` passed. No merge occurred under a failed required check.

Both Python versions and PostgreSQL/Mailpit test collection stopped because
the development lock omitted NumPy, which the local environment already had.
Maintained historical guard/calibration tests also directly import ONNX Runtime
and tokenizers. These packages are being explicitly pinned in development only,
with official Python 3.11/3.13 compatible wheels; no tests are skipped or removed,
and runtime images still exclude them. The existing lock-generation script
reuses unaffected pins without a blanket dependency upgrade.

The exact dependency-audit artifact identified PyJWT 2.14.0 with
`PYSEC-2026-4141` / `CVE-2026-101918`, fixed in 2.15.0. The
[official upstream advisory](https://github.com/advisories/GHSA-42vr-xj54-vc7v)
and published release were verified. The direct runtime pin is being updated;
the existing HS256 signature/claim/session contract is unchanged. Cardchemy does
not add JWKS or signature-disabled reads. This dependency finding is recorded
without claiming that the affected pre-verification path exists in Cardchemy.

Fresh collection and current coverage did not run in the failed jobs. Earlier
local passes are preserved with their environment scope; the collection failure
is not relabeled as a pass. All fixes will face the same unchanged hosted gates.

## Reproducible dependency repair

The required `backend/scripts/lock_dependencies.ps1` completed successfully.
The runtime graph changes only PyJWT from 2.14.0 to 2.15.0. Development adds
NumPy 2.4.1, ONNX Runtime 1.30.0 and tokenizers 0.22.1 plus their required
dependencies; unaffected pins are preserved. Official wheel metadata supports
both Python versions. These local research guard dependencies remain absent
from production requirements and the runtime image install path.

A fresh Windows Python 3.13 environment installed the complete development
graph with `--require-hashes`; a separate fresh runtime install also passed.
Fresh strict pip-audit returned zero vulnerabilities. Targeted authentication
and historical local-model guard contracts passed: 185 passed and one existing
Windows symlink skip. Full collection found 5,633 of 5,635 tests, with only the
two opt-in live tests deselected and no import errors. No model weights,
inference, provider calls or database changes were used. Python 3.11 execution
and complete current coverage remain the hosted matrix's responsibility.

Workflow/protection validation and context validation passed again, including
37 required files, 79 active guides and 2,191 local links. The independent
repair review confirmed unchanged fixed-HS256 authorization and runtime
dependency isolation. The repair is published through the same PR and the
same required gates; no failing test, audit or threshold is waived.

PR 41 and its Actions runs are the authoritative evolving publication record.
This dated snapshot records preparation and the first repair; final merge and
exact-main outcomes will be checked against their actual remote commit, rather
than predicted here. No local runtime deployment is part of this GitHub update.

## Linux fixture portability repair

The dependency repair commit `dd25710c429661538296351e41ddcdecec1080d8`
passed nine mandatory jobs in hosted run `37223081912`: frontend, PostgreSQL,
database artifact, journey, dependency audit, secret scanning and all three
container checks. Both backend jobs and SMTP remained unsuccessful, so the
required aggregator failed and the PR was not merged.

Python 3.13 reached 5,355 passing tests, eight skips and 268 marker exclusions,
with four concrete fixture failures. Python 3.11 stopped during failure
reporting after a shared `os.name` monkeypatch made pathlib select WindowsPath
on Linux. The test repair uses a caller-local OS simulation, leaving the host
platform, pytest and pathlib unchanged. A mock query-replay test now creates its
new private directory with mode 0700, so Linux reaches the intended consumed-
approval guard. The Windows-only locked-source tests now explicitly simulate
their required resource mode; unsupported POSIX/Windows isolation is still
rejected before source copy, including POSIX with a claimed Windows job.

SMTP's production fixture selected a retired model even with AI disabled.
Removing this unrelated model override makes both exact fixture modes validate
against the supported default. The four-outcome fixture probe and seventeen
offline configuration tests passed, without connecting to SMTP or a database.
Application settings/catalog and SMTP transport are unchanged.

The query SDK's mock-only contracts passed 34/34 on Windows in newly owned
private scratch. The default pytest scratch was inaccessible and produced nine
setup errors in the first local attempt; it was neither deleted nor repaired
by changing permissions. The successful scratch was validated and removed.
The targeted caller portability contracts passed on cached Python 3.11 Linux:
90 passed and one existing native-Windows redirector skip, with Docker network
disabled, source read-only and four CPU/two GiB limits. This used copied local
test tooling; the fresh hosted matrix remains the pinned-tooling gate.

Only fixtures are changed in this repair, retaining every assertion and the
strict runtime/privacy/resource guards. Coverage from the failed Python 3.13
run was 79.65% line-plus-branch, but its formal budget step did not execute after
pytest failed; this number is not labeled as a passing coverage gate.

A later read-only inventory observed the retained Cardchemy containers stopped
four hours earlier. Publication did not start, recreate or remove them. The
earlier completed local activation remains historical; no current runtime
health or new local deployment is claimed by this source-publication task.

The final targeted Linux portability check also ran the updated SDK and visual
fixtures: 139 passed with no skips. Together with the caller check this is
229 passed, one existing platform skip and zero failures. Two isolated overlay
bootstrap attempts stopped before any test execution; their evidence is kept,
and the passing run is distinct. Windows visual contracts passed 105/105 after
using fresh owned Temp for the same pre-existing cache-access problem. All
owned synthetic Temp/tooling copies were removed; receipts remain ignored.
Current-change diff checking and context validation passed. No application,
workflow, migration or threshold changed in this second repair.
