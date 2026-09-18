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

## Second hosted release attempt and scanner-cache repair

PR #16 merged as `50c4fdd653d5454ce27d82e8a0fe55c0921b5d2a`; exact-main
CI run `35253753500` passed. GitHub dependency graph and Dependabot alerts
were enabled after the public transition; the native dependency-review job
passed on its rerun. Release run `35254026625` passed protected-main preflight,
built and probed all three Linux/amd64 images, and passed each HIGH/CRITICAL
Trivy gate. It pushed three unique `v0.1.0-<source>-35254026625-1` GHCR tags,
then stopped before signing any image or checksum, creating a Git tag, or
drafting/publishing a GitHub Release. These partial tags must not be described
as a signed release or removed without separately reviewing their consumers.

The second `--remote` readiness gate failed because the job checkout was
dirty. The Trivy action's log puts its vulnerability database at
`$GITHUB_WORKSPACE/.cache/trivy`, which `.gitignore` does not exclude; its
temporary `trivy/` checkout and environment file were removed by the action.
The workflow did not print the exact `git status` paths, so the database is
the evidence-backed cause, not a captured path list. Relocate its cache to
`${{ runner.temp }}/cardchemy-trivy-cache` for both the action and direct
CLI calls, preserving the strict clean-tree gate. The workflow contract now
rejects an in-workspace cache, with mutation tests for both configuration
points. Pin Cosign to patched v3.1.3 as part of the release-tooling repair;
Sigstore advisory GHSA-fx35-mq7g-6g98 concerns legacy blob bundles, while
the default modern bundle format is unaffected. The signed draft, anonymous
image pulls and final publication still require a new reviewed source commit,
protected merge, exact-main CI and successful release workflow.

Local repair validation: 72 focused release-contract tests passed, including
both cache mutation cases. `scripts/check_ci.py`, local
`scripts/check_release.py --version 0.1.0`, `scripts/check_context.py` (37
required files, 59 active guides, 756 links), and `git diff --check` passed.
The next evidence boundary is hosted PR CI followed by exact-main CI and a
fresh release run; these local checks do not establish publication.

PR #17 automated review identified that `runner.temp` is unavailable in a
job-level `env` expression. The direct CLI cache variable was moved to that
Trivy step's `env`; the action input remains step-scoped. A workflow guard and
negative contract case now reject a future job-level placement. The first PR
CI pass predates this correction and must not be counted for the final head.
The corrected head passed 73 focused release tests, `scripts/check_ci.py`,
`scripts/check_context.py` and `git diff --check` locally.

The corrected PR head's PostgreSQL migration job failed twice before running
migrations: first with a connection reset, then with `CannotConnectNowError`
while the database system was starting. The harness's container-local
Unix-socket `pg_isready` can report success against the official PostgreSQL
image's temporary initialization server, which does not yet accept the
host-mapped TCP connection used by Alembic. The same wait existed in the
packaged journey. Both harnesses now wait up to 60 seconds for an authenticated
loopback TCP query of their exact generated test database, retrying only
startup/connection errors and keeping credential values out of logs. A
wrong-database response fails rather than quietly passing readiness. Focused
offline harness tests passed (4); the disposable local PostgreSQL suite passed
(34 passed, 3 skipped, 344 deselected), including head/drift and
downgrade/re-upgrade. The packaged Chromium journey passed (1) with its
database proof. Both harnesses reported cleanup of unique containers,
temporary data and generated credentials. These local passes do not replace
the next exact-head hosted CI gate.

The next PR head passed hosted PostgreSQL migrations but its three container
jobs failed before image probes: `check_images.py` imports `system_environment`
from `test_services.py` in a minimal host Python without backend packages, and
the new module-level `asyncpg` import made that import fail. Load `asyncpg`
only inside the PostgreSQL readiness function so the image checker retains its
stdlib-only import boundary. An isolated `python -S` image-checker import
regression now passes without site packages, alongside all five focused harness
tests, `scripts/check_ci.py` and `git diff --check`. A new hosted head is
required; the failed container run is not release evidence.

Final-head review further identified an overly broad readiness retry:
`asyncpg.PostgresError` also catches invalid credentials and missing database.
The wait now retries only OS/timeouts, PostgreSQL connection/startup errors
and asyncpg interface failures. A negative test proves invalid credentials
fail on the first attempt; all six harness safety tests passed. The first
local rerun used system Python, which lacks the development Alembic CLI; it
stopped before migrations and cleaned its disposable service. The corrected
run with `backend/venv/Scripts/python.exe` passed PostgreSQL integrations
(34 passed, 3 skipped, 346 deselected), head/drift and full downgrade/re-upgrade,
and reported complete disposable cleanup. The final hosted head remains
pending after this review-driven change.


## Successful public v0.1.0 publication and separate readiness work

PR #17 merged as `8ced5229407de660c2f8035b61459bf4c3470de6` after final-head
CI run `35258223986` passed. Exact-main CI run `35258496025` passed every
required gate. Release run [35258820641](https://github.com/EoCiMrEo/Cardchemy/actions/runs/35258820641)
succeeded for that exact source: protected-main preflight, all three builds/
runtime probes and HIGH/CRITICAL scans, unique image pushes, keyless image
signing/verification, complete packaging and checksum signing/verification,
final registry/source/CI guard, annotated `v0.1.0` tag and a 17-asset draft.

Independently downloaded every draft attachment into a new ignored directory.
The trusted source's package validator passed complete filename/checksum/
source/config/manifest/audit/SBOM/provenance bindings. Official Cosign v3.1.3
Windows binary SHA256 `9fe59be0eca1271873ce019061335eb1ac419b7059202e797828467ddabe33be`
verified the modern v0.3 checksum bundle with exact workflow identity, GitHub
OIDC issuer and reviewed source SHA. All three images pulled anonymously
using a new empty Docker configuration, and independent Cosign image
verification passed certificate, claims and transparency checks with those
same exact constraints. No registry credential was used for these pulls.

Verified release digests:

| Image | Signed pull digest |
| --- | --- |
| backend | `sha256:020db87b7b244512b39cdcdef429ea6cc865a7742de805df8760487f4f7a7582` |
| backend-ocr | `sha256:8f2f7b5d413f7d93165a9e084fa6c0758080510093ae81e7047ea5fe9a533348` |
| frontend | `sha256:7a4c4aecc24cf1c78c02c0452b0113fbcf210b109c5e7395ddbcfe6bcd5272ed` |

Each unique image tag is
`v0.1.0-8ced5229407de660c2f8035b61459bf4c3470de6-35258820641-1`;
the signed digest remains the supported pull identity. The annotated Git tag
peels to the reviewed source and its message binds the independently hashed
SHA256SUMS (`27654e9f84ca40d6081f8a6614518ced929ab1871a733335c4e94ae6340c59a1`).
Published the user-authorized [v0.1.0 release](https://github.com/EoCiMrEo/Cardchemy/releases/tag/v0.1.0)
at 2026-09-17 18:41:23 UTC after every publication prerequisite passed.
The unsigned unique tags from failed run `35254026625` remain partial
historical state and are not supported signed release identities.

The subsequent user request separately authorizes completing the v1.0
readiness checklist; it does not authorize a v1.0 version/tag/publication.
Read-only audit found remaining current-head backup/restore and clean-machine
production-profile gaps, plus actual encrypted SMTP delivery/recovery absent
from prior fake-TLS unit coverage. The operator clarified the product is
self-hosted and SMTP is local. An online relay is unnecessary: actual local
certificate-validating STARTTLS and implicit-TLS capture/recovery verifies
the application's supported production transport with no external messages.
See the [12-test SMTP evidence](2026-09-17-local-smtp-tls-verification.md).
The new clean Ubuntu production rehearsal builds an exact fresh clone with
production Compose/private services/trusted HTTPS, then drains writers,
checksums a custom-format current-head backup and restores it into a distinct
empty volume before upgrade/head/drift and instructor/student receipt/progress
checks. Its SMTP setup is validated but sends no mail; delivery is covered by
the separate actual TLS harness. Hosted rehearsal and final-source CI remain
pending, so the v1.0 gate is not yet marked complete. Operator configuration,
database and populated volumes are preserved; all rehearsal cleanup checks
ownership before removing its own generated resources.


Post-publication verification fetched all 17 assets anonymously into another
new empty directory; complete package/checksum bindings passed again, as did
independent exact-identity/issuer/source Cosign verification of its checksum
bundle. Public downloads therefore match the verified draft, rather than
merely relying on authenticated draft access. The temporary empty Docker
configuration used for anonymous pulls contained no login credentials.

Readiness integration adds actual TLS SMTP verification to the required
`mailpit` CI job and prevents its opt-in tests from being mistaken for the
separate PostgreSQL/Mailpit suite. The manual production workflow has pinned
read-only actions, a fixed main/repository guard, a bounded timeout and no
repository-secret injection. Maintained testing/email/deployment navigation
and context maps now distinguish local transport evidence, clean deployment
recovery and site-specific operator responsibilities.

Independent source review caught that the single-set API defaults computed
`approved_count` to zero; only the set collection populates those counts.
The rehearsal must use that implemented collection contract. It also noted
Python 3.13 strict certificate extensions, now required in generated rehearsal
certificates rather than relaxing trust. These source checks do not replace
actual hosted execution. Initial targeted invocations from the wrong working
directory and with guessed filenames ran no tests; corrected invocation from
`backend` using the actual filenames passed 88 release/harness/ownership tests.
CI/context/release metadata validators and whitespace checks passed locally.


Final pre-PR harness corrections passed 89 focused release/readiness/ownership
contracts. The production verifier now selects the exact fixture set from the
computed collection response, protected by a regression with an unrelated
first entry. Its generated HTTPS trust uses a separate CA and server leaf with
CA/leaf constraints, KeyUsage, SKI/AKI, leaf EKU and DNS SAN. An actual Python
3.13.7 strict certificate-validating HTTPS handshake passed without disabling
any validation flags. Compose rendering confirms seven intended services,
private API/database and loopback frontend/TLS only. The CI, context (37
required files/61 active guides/780 links), release metadata and whitespace
validators passed. An unrelated untracked subject-scoped RAG planning document
appeared during this task and is preserved/excluded from the release PR.


PR #18 initial source `dfc16f29730be0cbc2bc1022587e9836606b1f90`
passed complete CI run `35261059703`, including actual local TLS SMTP on
Ubuntu/Python 3.11. Before merge, independent review identified two verifier
contracts needing correction: any failed Docker inspection was incorrectly
accepted as service absence, and pytest default tracebacks could print
credential-bearing fixture/function arguments. No failing output from the
successful hosted run contains those tracebacks. Shared cleanup now requires
a successful Docker daemon inventory and exact generated-name absence.
Service/TLS pytest output is captured privately in memory and only whitelisted
counts/static test identities are emitted, preserving the exit status. Browser
journey diagnostics are similarly withheld; its fixed failure summary remains.
Journey cleanup also verifies owned network absence through a successful
inventory. Focused regressions cover daemon/query failure, surviving owned
containers and a credential-bearing failure-output sentinel. The corrected
PR head must pass CI again before protected merge.

Final correction validation: 101 focused release, service/readiness cleanup,
credential-redaction and demo contracts passed; CI/context/whitespace checks
passed. Remote main protection was revalidated: strict current-base
ci-required bound to GitHub Actions app15368, administrator enforcement,
resolved conversations, no force pushes and no branch deletion.

## Superseding operational readiness closure

The later [v1.0 readiness closure](2026-09-17-v1-release-gate.md) now completes
the separate gate; it supersedes the pending rehearsal/CI status above while
preserving those historical checkpoints. Exact-main CI `35266166793` and
actual clean-machine strict-production/TLS/current-head backup/separate-volume
restore/upgrade rehearsal `35266166852` passed at protected source
`79e3212cfa682ee0d9f643a03d45aeea66502162`. Its twelve checks, restored
counts/answer receipt/progress and owned cleanup were independently verified.
Actual local authenticated TLS SMTP delivery/recovery also passed as recorded
in its twelve-case evidence. All nineteen Phase 11 and eleven separate
readiness checkboxes are complete. The published release remains v0.1.0;
readiness completion does not publish/tag v1.0 or claim paid AI/external
mailbox delivery or an operator's live production installation.
