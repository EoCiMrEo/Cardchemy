# Source rollout, signed release and installation

A protected source merge, a published version and an operator deployment are
distinct events. This map describes the maintained release mechanism; dated
release evidence and GitHub's actual state establish which steps completed.
It does not claim that the illustrated checks ran for a particular version.

```mermaid
flowchart TD
  Work["Focused branch: code / docs / version / notices"] --> Local["Applicable local tests + fresh-clone Compose rehearsal"]
  Local --> PR["GitHub pull request"]
  PR --> Required["Current-base ci-required + resolved conversations"]
  Required --> Merge["Protected main merge"]
  Merge --> MainCI["Successful CI on exact new main SHA"]
  MainCI --> Review["Reviewed source SHA and release metadata"]
  Review --> Preflight["Prepare signed release: remote readiness checks"]
  Preflight --> Build["Build backend, OCR backend and frontend"]
  Build --> Audit["Image smoke + HIGH/CRITICAL audit + SBOM"]
  Audit --> Publish["Unique GHCR tags; record immutable registry digests"]
  Publish --> Sign["Cosign keyless image + checksum signatures"]
  Sign --> Draft["Annotated version tag + draft GitHub Release"]
  Draft --> Verify["Download, checksums, identity/source signatures, anonymous pulls"]
  Verify --> Release["Publish reviewed release"]
  Release --> Install["Operator installs signed digest or reviewed source"]
  Install --> Upgrade["Backup / drain / migrate / verify / restore traffic"]
```

`main` protection requires a PR, current-base `ci-required`, resolved
conversations and administrator enforcement; force push/deletion are forbidden.
The release workflow rejects a different repository/ref/SHA, missing required
protection/CI/readiness, or an already used tag/release identity. Its exact
source SHA is checked again before privileged publication.

The three release images are backend, optional-OCR backend and frontend.
Registry tags are mutable labels; consumers use signed `image@sha256:...`
identities. Cosign verifies GitHub Actions OIDC identity and the reviewed source
SHA. The Git tag is annotated; artifact/image trust comes from keyless
signatures and their source binding, not a claim of a GPG-signed Git tag.

## What each verification establishes

```mermaid
flowchart LR
  Offline["Offline units + contract tests"] --> Logic["Local behavior with deterministic providers"]
  Services["Disposable PostgreSQL / Mailpit"] --> Transactions["Schema, concurrency, recovery and local SMTP"]
  Frontend["Types, lint, components, Chromium and coverage"] --> UI["Client contracts and automated accessibility"]
  Journey["Real API/worker/database/browser journey"] --> Stack["Integrated application using offline providers"]
  Clone["Untouched fresh clone + bootstrap + base Compose"] --> Start["Build and start without source edits"]
  Security["Dependency / secret / image scans + signed inventory"] --> Artifacts["Recorded source and final artifact gates"]
  Human["Manual spoken assistive-technology review"] --> Accessibility["Packaged candidate spoken-output evidence"]
```

Ordinary tests spend no AI quota and send no production email. Fixture,
skipped and deselected tests do not prove live-provider or deployment success.
For 0.2.0, the operator reported successful functional application checks and
explicitly waived repeating the manual spoken-output check; the automated
and signed-release checks remain applicable. The manual node above describes
the normal release procedure, not a claim of a new 0.2.0 spoken-output test.
A future paid evaluation needs a separate exact model/endpoint/price/call/
token/time/cost approval. Operators retain their own TLS, SMTP, backup, privacy
and activation obligations for each installation. Version publication does not
change AI flags or validate every arbitrary lecture/query.

Sources: [release runbook](../ci-cd/RELEASING.md),
[versioning](../ci-cd/VERSIONING.md), [CI](../ci-cd/CI.md),
[release workflow](../../.github/workflows/release-sbom.yml),
[release validator](../../scripts/check_release.py),
[branch protection definition](../../.github/branch-protection.json),
[testing](../development/TESTING.md),
[accessibility](../ui/ACCESSIBILITY.md),
[deployment](../operations/DEPLOYMENT.md).
