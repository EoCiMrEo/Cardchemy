# CI, security gates and dependency updates

The `CI` workflow runs on pull requests, pushes to `main`, `v*` tags, merge
queues and manual dispatch. Its stable required check is **`ci-required`**.
That check fails when any mandatory job fails, is cancelled or is skipped,
including any matrix member. CI jobs use read-only tokens, full action commit pins,
bounded timeouts and fresh dependency installations. Paid AI requests are excluded.

| Mandatory job | Contract |
| --- | --- |
| `backend-offline (3.11)` / `(3.13)` | Hashed development install; offline unit/API contracts; line and branch coverage; critical-file floors; workflow and repository-context/link validation |
| `postgres-migrations` | Disposable PostgreSQL; constraints, transactions and concurrency; Alembic head and drift checks; full downgrade to base and upgrade to head |
| `database-artifact` | Validate pinned PostgreSQL/pgvector recipe inputs, LF/hash/platform/data path; build/probe immutable Linux/amd64 bytes; prove vector and legacy-to-ICU logical recovery; fail on HIGH/CRITICAL Trivy findings and retain configuration/archive/recipe-bound CycloneDX and provenance |
| `mailpit` | Disposable PostgreSQL and Mailpit; SMTP outbox delivery, retry and invitation contracts; authenticated local STARTTLS/implicit-TLS, certificate rejection and failure recovery |
| `frontend` | `npm run check`: types, lint, unit tests, component coverage, production build and Chromium browser contracts; emitted bundle budgets |
| `journey` | `python scripts/test_journey.py`: real instructor creation, PDF generation with an offline provider, review/publication, invitation, student study and persisted progress |
| `dependency-audit` | Fresh `pip-audit --require-hashes --strict` against the complete development lock; `npm audit --audit-level=low` across all npm scopes, plus explicit shipped-dependency audit |
| `secret-scan` | Gitleaks scans full Git history with redacted findings; Trivy scans the current source worktree |
| `containers (backend)` / `(backend-ocr)` / `(frontend)` | Final Linux runtime builds; native-library/auth/PDF/OCR and edge smoke probes; Trivy fails on HIGH/CRITICAL OS and application vulnerabilities, including vulnerabilities without fixes; CycloneDX SBOM artifacts |

The database artifact inventory is [`runtime-artifacts.json`](../runtime-artifacts.json).
It records the reviewed local recipe and immutable base/source/input identities.
The shared helper verifies recipe label, supported platform and actual runtime
prerequisites, then returns immutable bytes for every disposable consumer.
The CI-equivalent archive harness exports that identity and binds the audit to
the archive's image-configuration digest. Docker's local identity can represent
an OCI index; a configuration digest is recorded separately rather than equated
with it. Reports retain inventory/recipe inputs, image/index/configuration and
archive hashes, fresh advisory metadata, scanner identity and report checksums.
Keep this evidence with deployment records. Database reports are retained for
30 days in CI. The three-image signed application release workflow does not
publish/sign this database image; upstream signature verification is not claimed.
Any changed recipe/input requires a new identity and passing scan/recovery proof.

The local equivalent is `python scripts/test_database_artifact.py` using the
backend development Python. It exports the immutable reviewed database image,
downloads a fresh public advisory database into a disposable 4 GiB cache, then
disconnects scanner networking before analysis. It fails on HIGH/CRITICAL
findings, including unfixed vulnerabilities. Audit, CycloneDX SBOM, image and
scanner identities, archive hash and report checksums remain under ignored
`artifacts/database-artifact/<run-id>`. Owned scanner containers and exports
are cleaned. Bounded public-image scanner diagnostics are retained there and
uploaded even when scanning fails before producing a JSON report. These logs
contain scanner output for the public runtime archive only, never operator
configuration or application/database container output. Scanner failures remain
gate failures. No operator environment, application content or database volume
is mounted. A local pass does not establish a hosted CI pass.
The capability-free scanner matches the POSIX runner's user/group and uses
private temporary filesystems owned by that identity. This allows reading the
runner-owned Docker archive and writing reports without widening host file
permissions or restoring Linux capabilities. Docker Desktop uses its Windows
bind-mount ACL mapping with an explicit `0:0` fallback.

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
The frontend Docker builder also installs the declared npm 11.19.1 before
`npm ci`; dependency updates must satisfy the same peer graph in host and image
builds. Keep coupled Vite/React-plugin/Tailwind, ESLint/js and Vitest/coverage
upgrades aligned per [dependency policy](DEPENDENCIES.md).
Run this offline command from `backend`:

```sh
python -m pytest -q -m "not postgres and not mailpit and not ai_live" \
  --cov=app --cov-config=.coveragerc --cov-report=term-missing \
  --cov-report=json:coverage.json --cov-report=xml:coverage.xml
```

From the repository root run
`python scripts/check_context.py` for required context files and active local
documentation links (external URLs and historical bodies are excluded),
`python scripts/check_coverage.py backend/coverage.json`,
`python scripts/test_services.py postgres`,
`python scripts/test_services.py mailpit`,
`python scripts/test_smtp_tls.py`,
`python scripts/test_journey.py`, `python scripts/check_runtime_artifacts.py`
and `python scripts/check_ci.py`.
From `frontend`, `npm run check` is the authoritative frontend gate; run
`node ../scripts/check_bundle.mjs` after its production build. See
[AI evaluation](AI_EVALUATION.md) for explicit opt-in live-provider validation.

The manual read-only [production recovery rehearsal](PRODUCTION_REHEARSAL.md)
runs on a fresh Ubuntu runner from protected main. It separately verifies a
clean clone, strict production Compose, trusted HTTPS edge and a checksummed
backup restored into a second empty volume. It is release evidence rather than
part of the required per-PR aggregator. No operator secrets or external AI/mail
services are injected.

Backend coverage includes every application module, including operational
entry points; only `TYPE_CHECKING` guards are excluded. The Phase 9 measured
offline baseline was 203 tests, 78.20% statement/line coverage, 57.56% branch
coverage and 74.25% combined coverage. Floors are 77%, 55% and 73%, respectively. Combined
critical-file floors in `.github/coverage-budget.json` are 88% for authentication,
95% for password hash compatibility (measured at 100% lines and branches),
68% for study/flashcard operations, 78% for generation admission/persistence,
85% for the AI pipeline and grounding, and 83% for email-worker delivery.
PostgreSQL and real-journey gates independently exercise behavior beyond the
offline report. Frontend component floors live in `frontend/vitest.config.ts`.
Coverage reports expose remaining gaps; raising floors should follow new
behavioral coverage, rather than excluding production code.

After Phase 9 lazy route loading the production build measured **120,400 bytes initial
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

For isolated local secret/container evidence, build the default backend, OCR
backend and frontend with the tags `cardchemy-backend:phase9-ci`,
`cardchemy-backend-ocr:phase9-ci` and `cardchemy-frontend:phase9-ci`, then run
`python scripts/test_security.py` from the root. This exports only Git-visible
source/history/current changes and immutable image archives, excludes operator
`.env` and ignored data, downloads public advisory data before private mounts,
and disables scan networking. Reports, CycloneDX SBOMs, source/snapshot/image
identities and SHA256 checksums stay in ignored `artifacts/security`; private
scanner exports are cleaned. `source_has_local_changes` records the actual Git
state, and `snapshot_commit` identifies the exact exported tree. Run
`python scripts/check_images.py VARIANT --image IMAGE` for the separate final
runtime probe, with VARIANT equal to backend, backend-ocr or frontend.

GitHub's native `dependency-review` job checks new pull-request dependencies
at severity LOW or higher across runtime, development and unknown scopes.
For a private repository it requires GitHub Advanced Security; the optional job
also requires the repository variable `DEPENDENCY_REVIEW_ENABLED=true`. Enable the dependency
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

## Signed release workflow

`release-sbom.yml` is a separate manual **Prepare signed release** workflow,
restricted to the approved public repository's `main` and an exact reviewed
main SHA with successful mandatory CI. It does not run on release publication,
which avoids recursive preparation. Its preflight is read-only; only the
release job can write contents/packages and request an OIDC signing identity.
A short-lived `CARDCHEMY_RELEASE_READINESS_TOKEN` secret, scoped to this
repository with Administration read-only and mapped to the job's
`RELEASE_READINESS_TOKEN` environment variable, supplies the protection read
unavailable to the ordinary workflow token. See [the release procedure](RELEASING.md) for setup
and revocation; tokens do not belong in source, settings files or logs.

The job builds/probes/scans all three final Linux/amd64 runtimes, rejects
HIGH/CRITICAL findings, and creates CycloneDX SBOMs. It pushes one unique
`v<version>-<source SHA>-<run ID>-<attempt>` GHCR tag per image, records each
manifest digest, and keylessly signs/verifies those digests. The tags may be
immediately visible on later releases once the GHCR packages are public; the
signed digests are the supported pull identities. The workflow packages
exact-commit source, notes and provenance, signs the complete checksum manifest
with a Sigstore bundle, verifies the remote tags against its digest inventory,
then creates an annotated Git version tag and attaches verified files to a
**draft** GitHub Release. It never pushes a short `:<version>` GHCR tag. The
maintainer verifies downloaded artifacts, source/tag bindings and anonymous
access to all three GHCR packages/signatures before publishing the draft.

Release evidence artifacts expire after 90 days; preflight artifacts after 14
days. Preserve the published attachments and verified digest inventory with
release/operator records. Mutable base tags mean a later rebuild can differ;
retain the SBOM/audit belonging to the exact deployed digest. A prepared draft,
an expiring Actions artifact and a public verified release are different states.
[Trivy documents image scanning and CycloneDX output](https://github.com/aquasecurity/trivy-action).

## Remote enforcement runbook

The canonical GitHub repository is `EoCiMrEo/Cardchemy`. On 2026-09-16, while
the repository was private,
the Phase 9 protection payload was applied to `main` using the existing
authenticated account. The controlled first run on review PR #1 passed all
mandatory suites but deliberately failed its authentication coverage threshold;
`ci-required` failed and GitHub reported the non-draft PR blocked. The final
threshold is restored to 88%; repaired hosted run
[35129468986](https://github.com/EoCiMrEo/Cardchemy/actions/runs/35129468986)
passed every mandatory gate and GitHub reported the PR clean.
Local workflow files and the payload alone cannot prevent merges. Main
protection was verified during that private-repository review. Recheck live
visibility/protection before release or operational claims. Native dependency
review requires the appropriate repository feature/entitlement, with full
locked registry audits across all scopes enforced regardless.
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
[checkout v7.0.1](https://github.com/actions/checkout/commit/3d3c42e5aac5ba805825da76410c181273ba90b1),
[setup-python v7.0.0](https://github.com/actions/setup-python/commit/5fda3b95a4ea91299a34e894583c3862153e4b97),
[setup-node v7.0.0](https://github.com/actions/setup-node/commit/820762786026740c76f36085b0efc47a31fe5020),
[upload-artifact v7.0.1](https://github.com/actions/upload-artifact/commit/043fb46d1a93c77aae656e7c1c64a875d1fc6a0a),
[dependency-review v5.0.0](https://github.com/actions/dependency-review-action/commit/a1d282b36b6f3519aa1f3fc636f609c47dddb294)
and [Trivy action v0.36.0](https://github.com/aquasecurity/trivy-action/commit/ed142fd0673e97e23eac54620cfb913e5ce36c25).
Release preparation additionally uses
[download-artifact v8.0.1](https://github.com/actions/download-artifact/commit/3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c)
and [Cosign installer v4.1.2](https://github.com/sigstore/cosign-installer/commit/6f9f17788090df1f26f669e9d70d6ae9567deba6),
with Cosign explicitly pinned to v3.1.3. The release-only action owner and
permissions are checked by `scripts/check_ci.py`.
Trivy's scanner version is explicitly v0.70.0 and
[its release cache is held in the runner's temporary directory](https://github.com/aquasecurity/trivy-action#inputs)
so later release readiness checks see the same clean source checkout.
The patched Cosign pin addresses the legacy-bundle verification advisory
[GHSA-fx35-mq7g-6g98](https://github.com/sigstore/cosign/security/advisories/GHSA-fx35-mq7g-6g98).
[Gitleaks is v8.24.2 with the official GHCR manifest digest](https://github.com/gitleaks/gitleaks/pkgs/container/gitleaks).
When updating pins verify the official release/commit and review upstream
changes; a version comment does not replace commit verification.
