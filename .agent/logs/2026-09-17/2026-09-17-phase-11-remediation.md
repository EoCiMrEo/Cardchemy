# Phase 11: open-source product and release preparation

Date: 2026-09-17. Scope: Cardchemy governance, identity, browser assets,
no-quota demonstration and v0.1.0 release machinery. This is implementation
evidence; publication must be recorded only after remote verification.

## Starting context and owner decisions

Started from local `main` at `b30ecd580ce469acc36275fb64e8f6e312e4fdeb`,
one commit ahead of protected `origin/main`. The accepted Phase 10 working tree,
supplied brand files, historical logs and pre-existing deletion of the completed
context-plan file were preserved. Read root instructions, canonical orientation,
maps, relevant architecture/decisions, Phase 11 checklist, current state,
configuration/release/accessibility guides and dated Phase 10/11 logs.
`.agent/AGENTS.md` is absent. The real root `.env`, operator data and volumes
were not read or changed.

The owner chose Apache-2.0 for code and EoCiMrEo as copyright holder, approved
redistribution of supplied artwork under separate brand/trademark terms, chose
private GitHub vulnerability reporting, and permitted the complaint contact only
in `CODE_OF_CONDUCT.md`. The owner authorized v0.1.0, GitHub Releases, GHCR,
keyless artifact signing and repository publication after readiness. The
fine-grained branch-protection read secret was configured by the owner in GitHub;
its value was never requested or recorded. Paid AI/live SMTP was not authorized.

## Implementation and why it matters

- Added Apache-2.0 `LICENSE`, `NOTICE`, separate `BRANDING.md`, contribution,
  conduct/security policies, issue/PR templates and public roadmap. The root
  README now describes scope, screenshots, architecture, quick start,
  configuration, backup/upgrade, privacy, limits and troubleshooting. Historical
  ideas remain explicitly archived rather than advertised as shipped.
- Synchronized byte-exact code/brand terms into backend and frontend
  distributions with `scripts/prepare_release_notices.py`. Brand metadata names
  the separate terms; the browser can fetch `/legal/BRANDING.md` without
  interpreting the artwork as Apache-licensed code.
- Prepared lossless cropped/scaled wordmark and lockup exports while retaining
  all supplied originals. Both dashboard roles and account pages use the
  Cardchemy identity, the typed English catalog and a shared accessible
  wordmark. The ICO replaces the scaffold favicon. Nginx serves the assets as
  files, not SPA HTML; tests cover image loading and mobile/desktop headers.
- Aligned API/config, Compose, image identities, frontend package/lock and
  examples with Cardchemy 0.1.0. Existing operator `.env` is not rewritten;
  upgrade documentation names the exact previous defaults to review.
- Added a disposable deterministic provider demo to the real journey harness,
  including an optional packaged Nginx image path. It uses loopback only,
  owner-only temporary credentials, bounded lifetime and cleanup. The separate
  [demo log](2026-09-17-phase-11-demo.md) records its details.
- Added `docs/RELEASING.md` and `scripts/check_release.py`. The release workflow
  verifies exact protected public main and current CI, builds/scans/probes all
  three Linux/amd64 images, inventories SBOMs and image digests, signs images
  and the checksum manifest keylessly, and stages a draft release for independent
  download and anonymous GHCR checks. It deliberately fails closed if an
  existing version or required remote proof is missing. An annotated Git tag
  is used; the artifacts, not the tag, carry cryptographic signatures.
- Recorded bounded domain/package/social/trademark observations in
  `docs/NAME-REVIEW.md`. The `.com`, X and Instagram identities are occupied
  or registered by unverified others; no domain or social identity is claimed.
  LinkedIn's exact company URL showed a not-found page, not availability proof.

## Verification performed

- Frontend `npm run check`: typecheck, lint, units, component/coverage, build
  and Chromium passed (53 browser passes; one intentional environment-gated
  live reset skip). The separate bundle budget passed; web-sized wordmark and
  lockup payloads were measured apart from JavaScript. Refreshed instructor and
  student screenshots were visually reviewed.
- Backend offline suite: 322 passed, 38 intentionally deselected; measured
  line/branch/critical coverage floors passed. Disposable PostgreSQL suite:
  34 passed, 3 skipped, 310 deselected; migration head/drift and full
  downgrade/re-upgrade passed. Mailpit suite: 3 passed, 351 deselected.
- All three final local images (backend, OCR and frontend) passed image probes,
  including legal notices, native runtime/OCR and real PNG/ICO responses.
  The final source/history/image scan passed: Gitleaks found no leaks across
  29 commits, Trivy found no source secrets, and all three release-candidate
  images passed the HIGH/CRITICAL vulnerability gate. CycloneDX SBOMs,
  audits, image IDs and checksums are retained in ignored `artifacts/security/`.
- `npm audit --audit-level=low` found zero vulnerabilities; strict hashed
  Python dependency audit found none. Local release metadata, CI workflow
  contracts, canonical notice copies, context links (37 files/59 guides/755
  links) and `git diff --check` passed.
- The packaged-image demo ran the real Chromium instructor/student journey
  (1 passed) and its database proof with no paid provider calls. The owner
  then reported that all seven manual spoken-output checks in
  `docs/ACCESSIBILITY.md` worked in Chrome with Windows Narrator at
  approximately 1920 × 1080, and that the favicon looked clear in a fresh tab.
  Browser and Narrator version numbers were unknown; the owner identified
  themself as the manual tester and reported no findings. This is user-reported
  human evidence, not an automated assertion about spoken output.
- Interrupting the hosted demo terminal ended the harness before its normal
  cleanup finished. Removed only its three uniquely named disposable
  containers, network and verified temporary workspace; confirmed no matching
  containers/network remained, the workspace was absent and its loopback URL
  stopped responding. No operator installation or volume was removed.

## Remote state and remaining gates

The canonical remote is `https://github.com/EoCiMrEo/Cardchemy.git`; the local
first release branch was `codex/phase-11-release`. PR #13 passed every required
job and merged as `b839469bfddd20686e194e7aa4a3252ae387a614`; the exact
post-merge `main` CI and `ci-required` passed too. Protected `main` was verified with
strict current-base CI, PR/conversation/admin enforcement and no force/delete.
An automated review completed after the first merge and identified a genuine
ordering risk: stable GHCR version tags were pushed before image/checksum
signing and creation of the draft release. The follow-up
`codex/phase-11-release-hardening` branch stages and signs private candidate
digests first, signs the checksum package, creates the draft, then pushes the
stable tags only if each resolves to the exact signed candidate manifest. The
workflow contract rejects moving stable tag pushes earlier, and the release
guide describes partial-state recovery without pretending that GHCR and GitHub
Releases form one atomic transaction. Focused release tests passed (59), as did
CI-workflow, local metadata and context validators. This follow-up requires its
own protected merge and exact-main CI before publication.

The repository was private at preparation time. Do not mark private reporting,
publication or signed release complete until the PR is merged, exact main CI
passes, the repository/reporting channel is public and enabled, the draft assets
and images verify anonymously, and the release is published. The user-reported
manual Chrome/Narrator pass is recorded above. This log should be updated with those
final results instead of treating a prepared workflow as a published release.

## Follow-up release identity correction

The stable GHCR tag plan described in the preceding remote-state paragraph is
superseded. Review of PR #15 identified that checking for `:0.1.0` absence
before pushing it does not prevent another writer from creating the tag in
between; the earlier workflow contract also recognized only one literal push
spelling. The review additionally found that a GHCR package already made
public exposes future candidate tags immediately, a rerun needs a distinct
attempt identifier, and a failure after annotated Git tag creation can leave
that tag without a draft release. The first PR #15 CI pass predates these
findings and is not evidence for the corrected workflow.

The owner approved unique GHCR tags of the form
`v0.1.0-<source SHA>-<workflow run ID>-<run attempt>` and signed image digests
as supported pull identities; the Git tag and GitHub Release remain `v0.1.0`.
No short `:0.1.0` GHCR tag is to be pushed. The unique tag names reduce
accidental reuse, but GHCR tags remain mutable, so the verified signed digest
and signed release inventory bind the actual image. `docs/RELEASING.md`,
`docs/CI.md` and `docs/VERSIONING.md` now describe visibility and tag-only
failure states. Source changes, new CI results, protected merge and publication
must be recorded separately when completed.

The follow-up now publishes one `v<version>-<source>-<run>-<attempt>` tag per
image and stores its exact tag, run identity and manifest digest in each build
record and signed provenance. It verifies the remote tag's manifest bytes both
after the push and just before creating the draft. No short version tag is
pushed; the supported pull reference is the signed digest. The CI validator
permits only the reviewed `docker push "$release_tag"` command in the release
job and rejects an additional stable-tag push spelling. Focused release
contracts passed (69 tests), as did `scripts/check_ci.py`, local
`scripts/check_release.py --version 0.1.0`, `scripts/check_context.py` and
`git diff --check`. Hosted PR and exact-main CI remain pending for this patch.

## First hosted release preflight and correction

PR #15 merged through the protected flow as
`46025690dd8ffa2ee53d9ab8d74877a64cb7bc53`; exact-main CI run
`35252195174` passed, including `ci-required`. The repository was made
public only after those checks, and anonymous reads of the repository and root
`.env.example` succeeded. GitHub private vulnerability reporting was enabled
and its authenticated status returned `enabled: true`. Branch protection and
the presence (not value) of `CARDCHEMY_RELEASE_READINESS_TOKEN` were rechecked.

Release run `35252710598` failed in read-only preflight, before any image push,
source tag, draft or release publication. The validator's root repository GET
used a trailing slash; GitHub returned HTTP 404 for that URL and HTTP 200 for
the canonical URL without it. A focused fix removes the slash for the root
endpoint and adds a regression test. Using the existing maintainer credential
only for a read-only rehearsal, all remote preflight endpoints then passed for
the exact CI-passed main SHA. The focused release suite passed (70 tests), as
did the CI, local release and context validators. A new protected PR and its
exact-main CI are required before another release dispatch. This rehearsal
does not validate the Actions secret value or substitute for the hosted gate.
