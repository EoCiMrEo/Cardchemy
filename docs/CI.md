# CI, security gates and dependency updates

The `CI` workflow runs on pull requests, pushes to `main`, `v*` tags, merge
queues and manual dispatch. Its stable required check is **`ci-required`**.
That check fails when any mandatory job fails, is cancelled or is skipped,
including any matrix member. Jobs use read-only tokens, full action commit pins,
bounded timeouts and fresh dependency installations. Paid AI requests are excluded.

| Mandatory job | Contract |
| --- | --- |
| `backend-offline (3.11)` / `(3.13)` | Hashed development install; offline unit/API contracts; line and branch coverage; critical-file floors; workflow contract validation |
| `postgres-migrations` | Disposable PostgreSQL; constraints, transactions and concurrency; Alembic head and drift checks; full downgrade to base and upgrade to head |
| `mailpit` | Disposable PostgreSQL and Mailpit; SMTP outbox delivery, retry and invitation contracts |
| `frontend` | `npm run check`: types, lint, unit tests, component coverage, production build and Chromium browser contracts; emitted bundle budgets |
| `journey` | `python scripts/test_journey.py`: real instructor creation, PDF generation with an offline provider, review/publication, invitation, student study and persisted progress |
| `dependency-audit` | Fresh `pip-audit --require-hashes --strict` against the complete development lock; `npm audit --audit-level=low` across all npm scopes, plus explicit shipped-dependency audit |
| `secret-scan` | Gitleaks scans full Git history with redacted findings; Trivy scans the current source worktree |
| `containers (backend)` / `(backend-ocr)` / `(frontend)` | Final Linux runtime builds; native-library/auth/PDF/OCR and edge smoke probes; Trivy fails on HIGH/CRITICAL OS and application vulnerabilities, including vulnerabilities without fixes; CycloneDX SBOM artifacts |

Service runners generate isolated credentials, bind random ports to loopback,
use no persistent volumes and remove containers in cleanup. They do not use the
operator's `.env`. The real journey disables trace/report artifacts because its
browser and SMTP traffic contains generated credentials. Mock-browser and
coverage reports are retained for 14 days; CI container reports and SBOMs for 30 days.

## Local commands and measured budgets

Use the backend development environment's Python (on Windows,
`backend/venv/Scripts/python.exe`) and Node 24.7.0/npm 11.19.1. Install with
`python -m pip install --require-hashes -r backend/requirements-dev.txt` and
`npm ci` from `frontend`; install Chromium with
`npx playwright install --with-deps chromium` where the platform requires it.
Run this offline command from `backend`:

```sh
python -m pytest -q -m "not postgres and not mailpit and not ai_live" \
  --cov=app --cov-config=.coveragerc --cov-report=term-missing \
  --cov-report=json:coverage.json --cov-report=xml:coverage.xml
```

From the repository root run
`python scripts/check_coverage.py backend/coverage.json`,
`python scripts/test_services.py postgres`,
`python scripts/test_services.py mailpit`,
`python scripts/test_journey.py` and `python scripts/check_ci.py`.
From `frontend`, `npm run check` is the authoritative frontend gate; run
`node ../scripts/check_bundle.mjs` after its production build. See
[AI evaluation](AI_EVALUATION.md) for explicit opt-in live-provider validation.

Backend coverage includes every application module, including operational
entry points; only `TYPE_CHECKING` guards are excluded. The successful measured
offline baseline was 203 tests, 78.20% statement/line coverage, 57.56% branch
coverage and 74.25% combined coverage. Floors are 77%, 55% and 73%, respectively. Combined
critical-file floors in `.github/coverage-budget.json` are 88% for authentication,
68% for study/flashcard operations, 78% for generation admission/persistence,
85% for the AI pipeline and grounding, and 83% for email-worker delivery.
PostgreSQL and real-journey gates independently exercise behavior beyond the
offline report. Frontend component floors live in `frontend/vitest.config.ts`.
Coverage reports expose remaining gaps; raising floors should follow new
behavioral coverage, rather than excluding production code.

After lazy route loading the production build measured **120,400 bytes initial
JavaScript gzip**, **360,202 bytes largest JavaScript asset uncompressed**, and
**222,704 bytes total JavaScript gzip**. `.github/bundle-budget.json` limits
these to 130,000, 400,000 and 240,000 bytes. `check_bundle.mjs` measures emitted
assets and follows static imports/module-preload links; dynamic route assets
count toward total bytes. The Vite warning threshold remains unchanged. Budget
changes require an explanation and a measured before/after build.

## Security and dependency maintenance

Registry audits fail on any reported vulnerability; there are no accepted audit
exceptions. Runtime container scans fail on HIGH/CRITICAL findings and retain
the JSON result. A new advisory or unavailable advisory service makes the gate
fail; investigate and regenerate the relevant lock rather than weakening it.
Gitleaks reports redact values. Worktree scanning excludes operator `.env`,
Git internals, installed dependencies and generated reports; `.env.example`
and application/test source remain scanned. Run local scans with those same
exclusions to avoid reading the operator's secrets.

GitHub's native `dependency-review` job checks new pull-request dependencies
at severity LOW or higher across runtime, development and unknown scopes.
For this private repository it requires GitHub Advanced Security and the
repository variable `DEPENDENCY_REVIEW_ENABLED=true`. Enable the dependency
graph/dependency-review feature first, then enable that variable and verify an
actual pull-request run. The conditional native job is not the required
aggregator: full locked registry audits across all scopes run regardless.
Those mandatory audits provide dependency security review for additions and
updates by checking the entire resulting graph, including existing dependencies,
at LOW severity and above. They fail on any advisory or audit-service error and
use no accepted exceptions. This is stronger than reviewing only new vulnerable
dependencies for the configured vulnerability policy; it does not supply
GitHub's native change summary or a license policy. The conditional native job
adds GitHub's pull-request-specific review when available. Its condition is an
external feature limitation, not evidence that native review is enabled.
[GitHub's dependency-review action documents the availability requirement](https://github.com/actions/dependency-review-action).

Dependabot opens weekly grouped npm, pip, Docker and GitHub Actions updates.
Compatible minor/patch and security updates are grouped separately; major
updates receive independent review. Its edits are proposals. Python updates
must change the reviewed `.in` inputs and regenerate both hashed `.txt` locks
with the supported Python/pip-tools environment; verify that the development
lock incorporates the final production lock. npm updates must keep the
manifest and npm-11 lock aligned. Require the complete CI gate before merging.
[Dependabot's option reference defines grouping and security-update behavior](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference).

The release workflow builds all three final images when a release is published
or on manual dispatch, audits them and generates CycloneDX SBOMs. Each 90-day
artifact contains the SBOM, vulnerability report, source commit/ref, image ID,
platform, run URL and SHA256 checksums. These describe the exact images built
by that run; mutable base tags mean a later rebuild may differ. Download and
archive artifacts with release records before expiration. A deployment
pipeline should retain the SBOM from its exact deployed image digest. This
workflow does not push images or attach files to a release automatically.
[Trivy documents final-image scanning and CycloneDX output](https://github.com/aquasecurity/trivy-action).

## Remote enforcement runbook

The actual GitHub repository is `EoCiMrEo/Cardchemy`, private. On 2026-09-16,
the Phase 9 protection payload was applied to `main` using the existing
authenticated account. The controlled first run on review PR #1 passed all
mandatory suites but deliberately failed its authentication coverage threshold;
`ci-required` failed and GitHub reported the non-draft PR blocked. The final
threshold is restored to 88%; the repaired head must pass every mandatory gate.
Local workflow files and the payload alone cannot prevent merges. Main
protection is active for this private repository; native dependency review
requires its separate Advanced Security entitlement, with full locked registry
audits across all scopes enforced regardless.
[GitHub documents protected-branch availability and required checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

Publish the reviewed changes
through a pull request and obtain a successful `ci-required` run. Inspect the
repository and branch before applying `.github/branch-protection.json`:

```sh
gh api repos/EoCiMrEo/Cardchemy --jq '{full_name,private,default_branch}'
gh api repos/EoCiMrEo/Cardchemy/branches/main/protection
gh api --method PUT repos/EoCiMrEo/Cardchemy/branches/main/protection \
  --input .github/branch-protection.json
gh api repos/EoCiMrEo/Cardchemy/branches/main/protection
```

The payload requires current-base `ci-required`, includes administrators,
requires pull requests and resolved conversations, and disables force pushes
and branch deletion. It sets zero approving reviewers to support the current
solo-maintainer workflow; a team should select its reviewer count and code-owner
policy explicitly. Verify that the returned protection matches the payload.
The payload binds `ci-required` to GitHub Actions app ID 15368, verified from
[the official checkout repository's check runs](https://api.github.com/repos/actions/checkout/commits/main/check-runs)
on 2026-09-16. Confirm that the actual `ci-required` run reports that same app
and the returned protection retains this binding. Avoid other
workflows producing the same job name.

Finally open a controlled failing pull request and confirm GitHub blocks its
merge, then confirm a repaired pull request passes every gate. Record the
remote workflow run, protection response and failed-merge evidence in
`.agent/logs/`. Until those checks succeed, leave branch protection and the
phase's merge-blocking completion criterion unchecked.

## Action pin provenance

Pins were checked against the maintainers' release commit links:
[checkout v4.3.1](https://github.com/actions/checkout/commit/34e114876b0b11c390a56381ad16ebd13914f8d5),
[setup-python v5.6.0](https://github.com/actions/setup-python/commit/a26af69be951a213d495a4c3e4e4022e16d87065),
[setup-node v4.4.0](https://github.com/actions/setup-node/commit/49933ea5288caeca8642d1e84afbd3f7d6820020),
[upload-artifact v4.6.2](https://github.com/actions/upload-artifact/commit/ea165f8d65b6e75b540449e92b4886f43607fa02),
[dependency-review v4.8.2](https://github.com/actions/dependency-review-action/commit/3c4e3dcb1aa7874d2c16be7d79418e9b7efd6261)
and [Trivy action v0.36.0](https://github.com/aquasecurity/trivy-action/commit/ed142fd0673e97e23eac54620cfb913e5ce36c25).
Trivy's scanner version is explicitly v0.70.0 and
[Gitleaks is v8.24.2 with the official GHCR manifest digest](https://github.com/gitleaks/gitleaks/pkgs/container/gitleaks).
When updating pins verify the official release/commit and review upstream
changes; a version comment does not replace commit verification.
