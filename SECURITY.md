# Security policy

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/EoCiMrEo/Cardchemy/security/advisories/new)
for Cardchemy. Do not open a public issue or disclose an unfixed exploit in a
pull request. If that private form is unavailable, open only a nonsensitive
issue about reporting-channel availability, without exploit details. Ordinary
bug reports belong in the issue tracker.

Include the affected release/commit, deployment mode, a synthetic reproduction,
impact, prerequisite roles and any proposed mitigation. Never submit real
documents, account information, secrets, cookies, reset/invitation links,
provider prompts/responses or database backups. Redact logs according to
[observability guidance](docs/OBSERVABILITY.md).

Maintainers review reports on a best-effort basis, confirm scope, coordinate
mitigation and agree disclosure timing with the reporter. No guaranteed
response time or service-level commitment is offered. Keep exploit details
private until a fix/advisory is coordinated; reports made in good faith should
avoid accessing other users' data or disrupting a deployment.

## Supported versions

| Version | Security support |
| --- | --- |
| 0.1.0, once published | First supported release; best-effort fixes through the latest patched release |
| Latest published release | Active best-effort support; install the latest patch |
| Superseded releases | No backport commitment; upgrade |
| Development `main` | Report reproducible issues; not a stable release guarantee |

[Versioning](docs/VERSIONING.md) and the [changelog](CHANGELOG.md) identify the
current version and compatibility policy. Release artifacts are distinct from
unreleased working-tree changes. A deployment operator must decide whether a
version and its dependencies are suitable for their audience and data.
Update this table when the supported release changes; there is no long-term
support or historical-release backport promise. Verify release checksums and
keyless signatures using [RELEASING.md](docs/RELEASING.md).

## Deployment responsibilities and boundaries

Follow [deployment](docs/DEPLOYMENT.md), [configuration](docs/CONFIGURATION.md)
and [privacy](docs/PRIVACY.md). Use HTTPS/secure cookies, private API/database
ports, encrypted production SMTP, strong independent keys, least-privilege
process credentials and tested encrypted off-host backups. Preserve worker
fencing, bounded retries, and conservative ambiguous-email recovery. Keep
the host, proxy and dependencies patched; protect diagnostics and exports.

The general authorized card-read API exposes answers; only study-session
payloads hide them. Cardchemy provides study tooling, not exam secrecy.
Documents and AI outputs are untrusted and locally validated. Content sent to
an external provider is subject to that provider's contract, independently of
database deletion. Optional aggregate telemetry is disabled by default.

The audit trail is diagnostic, not tamper-proof. No legal-compliance,
production-availability or paid-provider guarantee is implied by a passing
offline test. Manual assistive-technology and deployment release gates remain
documented in [accessibility](docs/ACCESSIBILITY.md) and the
[remediation plan](issues-required-remediation.md).
