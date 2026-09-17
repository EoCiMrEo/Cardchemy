# v1.0 release-gate verification

Date: 2026-09-17. Scope: complete the readiness checklist, preserving published
v0.1.0 identities and operator data. This work does not publish/tag v1.0.

## Context and decisions

Read root governance, canonical orientation/maps, phase roadmap/current state,
release/deployment/database/email/testing/accessibility guidance and relevant
source/tests. Phase 11 now has complete public publication evidence in its
[closure log](2026-09-17-phase-11-remediation.md): all 17 public assets and three
signed public image digests were independently verified. Code is Apache-2.0;
brand terms are separate. Private vulnerability reporting is enabled; the
maintainer address is published only in Code of Conduct as authorized.

The gate audit found that current-head backup/restore and a fresh production
installation on a clean machine needed actual execution, and encrypted SMTP
needed actual transport evidence beyond fake-TLS units. The user clarified
that SMTP is self-hosted/local; no online relay is necessary. Supported local
production TLS delivery/recovery is verified with authenticated disposable
capture servers, without external messages or paid AI. See
[actual SMTP evidence](2026-09-17-local-smtp-tls-verification.md).

An unrelated untracked subject-scoped RAG plan appeared during this work. It
is preserved and excluded from commits; no proposal/architecture work is added.
Real root configuration, secrets, populated databases and volumes are untouched.

## Verified source checkpoint

Protected PR #18 final head `6032f7355e33af432fe7946f5bf975eabf582ac7`
passed [CI 35261881870](https://github.com/EoCiMrEo/Cardchemy/actions/runs/35261881870),
then merged as `87fec6f4474c138fa6ceb5655ba75274a5825585`.
[Exact-main CI 35262195128](https://github.com/EoCiMrEo/Cardchemy/actions/runs/35262195128)
passed every required job: Python 3.11/3.13 offline/coverage, PostgreSQL
migrations/heads/drift/reversal, Mailpit and actual TLS SMTP, full frontend
checks/Chromium, real deterministic instructor/student journey, complete
locked dependency audits, secret scans and three container probes/scans/SBOMs.
There are no accepted vulnerability exceptions or lowered thresholds.

Local pre-merge checks passed 101 focused release, harness cleanup/privacy,
production ownership/API contract and demo regressions; CI/context/release
metadata/whitespace validation passed. Independent review corrected the
collection-only computed card-count contract and generated strict CA/server
certificate extensions. Actual Python 3.13.7 HTTPS trust/hostname validation
passed. Cleanup now requires a successful daemon inventory proving generated
container/network absence; raw credential-bearing service/browser failures
are privately captured rather than printed. Negative cleanup and redaction
sentinels verify failure status remains meaningful.

## First clean-machine rehearsal: failed, not completion evidence

Manually dispatched [production run 35262192225](https://github.com/EoCiMrEo/Cardchemy/actions/runs/35262192225)
on a fresh Ubuntu runner at the exact checkpoint. It cloned/bootstrapped the
committed source, then failed at fixed stage `compose_up`, before fixture/API,
backup or restore verification. Captured build/service output was withheld
and no credential values were exposed. The failure is not passing deployment
or recovery evidence; the v1.0 gate remains open. A bounded source/reproduction
investigation is underway before a reviewed correction and new hosted run.


## Rehearsal startup correction

The original command output was not retained, so its exact low-level cause
cannot be asserted from the fixed `compose_up` stage alone. Source review
identified pull-before-build ambiguity for the TLS edge sharing a generated
frontend image tag without a build definition. [Docker documents the default
pull-before-build behavior](https://docs.docker.com/reference/compose-file/build/).
Make the harness explicitly `compose build` before `up --no-build`; the restore
project continues to reuse the built images. This changes rehearsal ordering,
not application Dockerfiles, production settings or readiness thresholds.

Privately captured command failures now map to fixed allowlisted categories
(pull/build/health/port/daemon/generic failure) and bounded timeout/unavailable
categories. No raw service/build output is printed. Four sentinel cases prove
credentials never appear in classified errors, and a shared-image ordering
contract verifies the separate build precedes startup. All 24 production,
service cleanup/privacy and harness safety contracts passed locally. A new
protected source/CI checkpoint and a successful fresh-machine rerun remain
required; this correction alone is not deployment/recovery evidence.
