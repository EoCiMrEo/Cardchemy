# Versioning and releases

The project uses [Semantic Versioning](https://semver.org/):

- MAJOR: incompatible API, data, configuration, or deployment changes.
- MINOR: backward-compatible capabilities.
- PATCH: backward-compatible fixes and security hardening.

Until 1.0, a minor release may contain breaking changes. Each release aligns
the root changelog, frontend package and lock root version, API default version,
root `.env.example` version and `vMAJOR.MINOR.PATCH` tag. The current product
version is **0.1.0**. A source version alone does not establish a published
release; inspect [GitHub Releases](https://github.com/EoCiMrEo/Cardchemy/releases)
and [release evidence](../.agent/logs/README.md). Changes for a later release
remain in Unreleased until that release is intentionally prepared.

Follow [RELEASING.md](RELEASING.md) for protected-main readiness, keyless signed
artifacts/images, an annotated version tag, verified draft and final publication
to GitHub Releases plus GHCR. The published platform is Linux/amd64; see
[runtime support](RUNTIMES.md). Tags and versioned images are never overwritten.
Corrections to published artifacts require a reviewed new version.

The tag is annotated and binds the signed checksum-manifest hash; release
artifacts and image digests are signed through GitHub Actions OIDC. This does
not claim GPG signatures on Git tags or developer commits. Verify the exact
workflow certificate identity, issuer and reviewed commit when consuming them.

For existing installations, preserve the original root `.env` and its database,
Compose project/volume identity, independent encryption/signing keys and explicit
JWT/cookie settings. New Cardchemy defaults are intended for new installations;
copying them over an existing installation can select another volume/database
or invalidate sessions. Apply deliberate configuration changes using
[configuration](CONFIGURATION.md), [deployment](DEPLOYMENT.md) and
[database operations](DATABASE_OPERATIONS.md). Never regenerate installation
secrets as part of a version upgrade.
