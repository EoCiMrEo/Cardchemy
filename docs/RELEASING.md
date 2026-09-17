# Preparing and publishing a release

Cardchemy releases use the canonical repository
[`EoCiMrEo/Cardchemy`](https://github.com/EoCiMrEo/Cardchemy), GitHub Releases
and GHCR. The approved first version is **v0.1.0**. This runbook describes the
procedure; it does not assert that a release has been published. Check the
[release page](https://github.com/EoCiMrEo/Cardchemy/releases), immutable
digests and dated release evidence for the actual result.

## Candidate readiness

Prepare changes through a pull request without bypassing `main` protection.
Keep [versions](VERSIONING.md), the [changelog](../CHANGELOG.md), code license,
[brand terms](../BRANDING.md), documentation and root `.env.example` aligned.
Do not include operator `.env`, exports, credentials or private documents in
Git or release attachments. Scan the complete history and final source before
changing repository visibility.

Use [TESTING.md](TESTING.md) and [CI.md](CI.md) for the required offline,
PostgreSQL/migration, Mailpit, frontend, real no-quota journey, dependency,
secret and final-image checks. Verify all three Linux/amd64 runtimes, including
OCR. Record the manual spoken-output pass on the packaged candidate required
by [ACCESSIBILITY.md](ACCESSIBILITY.md); automated accessibility tests do not
replace that pass. Normal verification does not spend provider quota or send
production email. Paid-provider evaluation has its separate explicit opt-in.

Run `python scripts/check_release.py --version 0.1.0` from the root for local
metadata validation. Merge only after the PR's mandatory `ci-required` check
passes, then wait for a successful CI workflow and `ci-required` on the exact
new **main commit**, rather than reusing the PR merge-ref result. Record that
40-character lowercase commit SHA as the independently reviewed source.
The separate v1.0 checklist remains a gate for v1.0; v0.1.0 does not claim it.

## Repository and narrowly scoped credentials

After candidate readiness passes and the owner has authorized publication,
change the repository to public using its Settings page. Recheck `main`
protection against [.github/branch-protection.json](../.github/branch-protection.json)
and enable private vulnerability reporting in Settings → Security. Confirm
the confidential reporting entry point in [SECURITY.md](../SECURITY.md) is
usable. [GitHub documents enabling the reporting channel](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository).

Create a short-lived fine-grained personal access token limited to this one
repository, with **Administration: read-only** and the automatically included
Metadata permission. Store it directly in GitHub's repository Actions secrets
as **`CARDCHEMY_RELEASE_READINESS_TOKEN`**. Do not paste it into chat, source, root `.env`,
logs or command arguments. It is used only to read branch protection; the
ordinary workflow token reads CI and performs the explicitly scoped release
writes. GitHub's
[Get branch protection endpoint requires Administration (read)](https://docs.github.com/en/rest/branches/branch-protection#get-branch-protection),
which the ordinary `GITHUB_TOKEN` does not provide. Do not grant this token
repository administration or content write permission. Choose the shortest
practical expiration; revoke it and remove the secret after release verification.

## Prepare the signed draft

In Actions, select **Prepare signed release**, run on `main`, enter version
`0.1.0` without `v`, and enter the reviewed exact main SHA. An authenticated
maintainer with GitHub CLI can dispatch the same inputs:

```sh
gh workflow run release-sbom.yml --repo EoCiMrEo/Cardchemy --ref main \
  -f version=0.1.0 -f source_sha=REVIEWED_40_CHARACTER_MAIN_SHA
```

The workflow refuses a different repository/ref/SHA, private or archived
repository, disabled private vulnerability reporting, missing protection,
absent exact-commit mandatory CI, or an existing Git version tag/release. Its
checks repeat before privileged work and tagging. It builds and probes backend,
backend-ocr and frontend, rejects HIGH/CRITICAL vulnerabilities including
unfixed findings, and creates CycloneDX SBOMs. For each image it pushes one
unique GHCR tag of the form
`v0.1.0-<source SHA>-<workflow run ID>-<run attempt>`, records and checks the
registry manifest digest, then signs/verifies that digest with Cosign using
GitHub Actions OIDC. The run attempt distinguishes a rerun of the same workflow
run. GHCR tags are mutable references; the signed `image@sha256:<digest>` is
the supported pull identity. On the first release, GHCR creates private
packages by default. On later releases, new tags can be visible immediately
if those packages are already public. A visible tag before the signed draft
exists is only a staged image, not evidence of a completed release. The
workflow never pushes a short `:0.1.0` image tag.

It archives the exact Git commit, prepares notes and image/source provenance,
hashes the complete attachment inventory, then keylessly signs `SHA256SUMS`
with a Sigstore verification bundle. It verifies those signatures before
creating an annotated `v0.1.0` Git tag and a **draft** GitHub Release. Each
image's unique GHCR tag and digest are included in its signed release inventory,
and the workflow verifies that the remote tag resolves to the recorded manifest
bytes. The annotated Git tag records the signed checksum manifest's hash and
points to the reviewed source; it is **not a GPG-signed Git tag**.
Cryptographic release trust comes from the keyless artifact/image signatures
and their source binding.

The attachment inventory includes `source-provenance.json`, `release-notes.md`,
`cardchemy-0.1.0-source.tar.gz`, `SHA256SUMS`, `SHA256SUMS.sigstore.json` and,
for each of `backend`, `backend-ocr` and `frontend`, its `.build.json`,
`.manifest.json`, `.audit.json` and `.sbom.json` files. The 15 source/inventory
files are checksummed; the checksum manifest and its verification bundle make
17 required attachments. The registry manifest files preserve raw bytes:
their SHA256 hashes must equal the corresponding released image digests.

The expected certificate identity is exactly
`https://github.com/EoCiMrEo/Cardchemy/.github/workflows/release-sbom.yml@refs/heads/main`;
the OIDC issuer is exactly `https://token.actions.githubusercontent.com`.
Verification must also require the reviewed source SHA. Do not weaken these
checks to broad owner/identity patterns or disable transparency verification.

## Verify downloads and public image access

GHCR packages initially default to private, though linked packages can inherit
repository visibility. Check `cardchemy-backend`, `cardchemy-backend-ocr` and
`cardchemy-frontend` individually. After readiness passes, make any private
package public using its Settings.
Repository visibility alone does not establish image visibility. Verify using
an unauthenticated client with a new empty Docker configuration, then remove
that temporary configuration. [GitHub documents the initial visibility and anonymous public pulls](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

Download **all** draft attachments into a new empty directory; do not mix them
with a previous run. With independently installed, verified Cosign 3.1.3, run
the following from that directory in a POSIX shell, replacing the source value
with the independently reviewed SHA, not a value accepted solely from a download:

```sh
SOURCE_SHA=REVIEWED_40_CHARACTER_MAIN_SHA
IDENTITY='https://github.com/EoCiMrEo/Cardchemy/.github/workflows/release-sbom.yml@refs/heads/main'
ISSUER='https://token.actions.githubusercontent.com'
cosign verify-blob --bundle SHA256SUMS.sigstore.json \
  --certificate-identity "$IDENTITY" --certificate-oidc-issuer "$ISSUER" \
  --certificate-github-workflow-sha "$SOURCE_SHA" SHA256SUMS
sha256sum --check SHA256SUMS
```

Inspect the manifest paths before invoking a checksum tool. The release
validator permits only the exact documented filenames, with no directories,
duplicates or omitted attachments. From a trusted checkout of the reviewed
source, run:

```sh
python scripts/check_release.py --version 0.1.0 --source-sha "$SOURCE_SHA" \
  --verify-package /absolute/path/to/downloaded-attachments
```

The package validator checks all 17 required attachments, the complete safe
checksum inventory and the following bindings before deployment:

- Source provenance identifies the reviewed commit/version, approved workflow
  and run, successful CI identity, and Linux/amd64 platform.
- Each raw `.manifest.json` hashes to the released registry digest, and its
  config digest equals the image config ID in the matching `.build.json`.
  The build record also names the unique version/source/run/attempt GHCR tag;
  pull by the recorded digest, since the registry tag itself can later move.
- The vulnerability audit and CycloneDX SBOM both identify that same image
  config. The audit contains no HIGH/CRITICAL findings and identifies
  Linux/amd64 plus the approved repository URL, source revision and version
  in the image's OCI labels. The build records and source provenance agree.
- The source archive's Git PAX `comment` equals the reviewed source SHA. Every
  member stays under `cardchemy-0.1.0/`, contains no traversal/backslash path,
  and is a regular file or directory. Links, private `.env` variants and key
  material are rejected; the public root `.env.example` is permitted.

Do not extract the source archive before signature, checksum and package
validation pass. For **each** digest in the verified inventory, pull
anonymously and verify its signature:

```sh
docker --config /path/to/new-empty-docker-config pull \
  ghcr.io/eocimreo/cardchemy-backend@sha256:VERIFIED_64_CHARACTER_DIGEST
cosign verify --certificate-identity "$IDENTITY" --certificate-oidc-issuer "$ISSUER" \
  --certificate-github-workflow-sha "$SOURCE_SHA" \
  ghcr.io/eocimreo/cardchemy-backend@sha256:VERIFIED_64_CHARACTER_DIGEST
```

Repeat for `backend-ocr` and `frontend` using their own digests. Run Cosign
with no registry credentials when establishing public access to signatures.
Use the flags documented for the pinned
[Cosign blob verifier](https://github.com/sigstore/cosign/blob/v3.1.3/doc/cosign_verify-blob.md)
and [image verifier](https://github.com/sigstore/cosign/blob/v3.1.3/doc/cosign_verify.md).

Independently fetch the version tag and confirm its peeled commit equals
`SOURCE_SHA`; verify its annotation names the SHA256 hash of the downloaded,
verified `SHA256SUMS`. Confirm the draft has every manifest-listed attachment
plus `SHA256SUMS` and `SHA256SUMS.sigstore.json`. Stop if any download, source,
tag, image, signature, scan or public-access check disagrees.

## Publish and retain evidence

Once those checks pass, publish the existing verified draft through GitHub
Releases, or use `gh release edit v0.1.0 --repo EoCiMrEo/Cardchemy --draft=false`.
Verify the resulting public release and anonymous attachment downloads again,
and record the release URL, source/tag SHA, workflow/CI run URLs, three immutable
image digests, checksum hash, signing identity, public access, manual accessibility
result and remaining limits in `.agent/logs/`. Mark publication checklist items
done only after actual publication succeeds. Retain the complete release assets
with operator records; Actions artifacts expire after 90 days.

Deploy by verified digest using [DEPLOYMENT.md](DEPLOYMENT.md). A later rebuild
from the same source can differ because base-image tags are mutable. Keep the
inventory belonging to the exact deployed digest. Never overwrite a published
Git version tag or deliberately reuse a GHCR tag, force-push history, or delete
deployment data to repair a failed release. GitHub Releases and GHCR do not
provide one atomic cross-service transaction. A failure before the Git tag can
leave unique image tags. A failure between tag creation and draft creation can
leave the annotated source tag without a draft. A later failure may leave a signed
draft. Existing public GHCR packages expose new tags during a later release
run. **Do not newly make packages public or publish a draft after a failed
workflow.** Inspect the retained Actions evidence,
draft inventory, annotated tag target and message, image signatures, unique
tag targets and every recorded digest. The normal workflow deliberately refuses
reuse of an existing Git version tag/release, so it cannot repair a tag-only
failure by rerunning. A maintainer must document and independently review an
exact-source, exact-checksum completion of the existing draft or orphaned Git
tag, or choose a new version after accounting for the partial state. Do not
overwrite an existing tag or image to make a rerun appear successful.
