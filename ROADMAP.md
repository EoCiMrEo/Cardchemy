# Cardchemy public roadmap

This page records completed delivery, the published release and uncommitted ideas.
[Current state](docs/development/CURRENT-STATE.md) owns milestone evidence;
[accepted ADRs](docs/decisions/ADR-000-INDEX.md) own durable decisions.
Completed trackers are preserved in the [archive](docs/archive/README.md).

## Implemented

- Instructor-owned subjects, invitation-backed student enrollment and revocable
  rotating sessions; instructor provisioning is operator CLI only.
- Bounded PDF upload, optional local OCR, encrypted temporary sources and
  PostgreSQL generation workers with leases, cancellation and manual retry.
- Native Gemini generation through a versioned five-model catalog, strict
  source-grounded four-option cards, quality checks and instructor
  approval/publication. Historical provider identities remain readable.
- Online student study with durable answer receipts, server-derived grading,
  stable per-card displayed-option shuffling and spaced repetition. Progress is
  correct-card coverage; Accuracy, Attempted and Mastery are separate views.
- Transactional password-recovery/invitation email, conservative delivery
  recovery, local Mailpit and encrypted production SMTP configuration.
- Root-only configuration, production-shaped Compose, Alembic schema ownership,
  guarded service/journey tests and mandatory CI/security/accessibility budgets.
- Content-free diagnostics/correlation, worker health, transactional audits,
  authorized operator exports/deletion and bounded metadata retention. Optional
  aggregate reporting remains disabled by default.
- Instructor-owned, revisioned Subject Knowledge with PostgreSQL/pgvector and
  full-text retrieval, isolated Gemini embedding and Ask workers, private
  durable Ask AI history, lifecycle controls and deterministic evaluation/
  recovery gates. Current Ask is source-only: at most one current-question
  embedding, one bounded Gemini source-ID judgment and three exact original-PDF
  references, with no answer model or verifier. Fresh installations remain
  default-off until explicitly configured. Embedding 001 remains default;
  Embedding 2 is an incompatible,
  explicitly staged/cut-over option. New-document repeats within one Subject offer
  an explicit reuse or separate-copy choice; unchanged explicit revisions avoid
  a second Knowledge capture/index.

## Release work and verification

Phases 0–11 cover the secure self-hosted foundation, branding, governance,
no-quota demo, documentation/screenshots and verifiable release packaging.
Subject Knowledge/RAG Phases 12–21 cover the implemented retrieval, private
Ask AI, privacy, observability and release closure. Their completed task detail
is preserved in the [archived remediation tracker](docs/archive/issues-required-remediation.md)
and [archived RAG implementation plan](<docs/archive/Cardchemy-Subject-Scoped RAG Implementation Plan.md>).
Published artifacts belong to [releases](https://github.com/EoCiMrEo/Cardchemy/releases).

The separate v1.0 readiness gate passed clean-machine production-profile
deployment/recovery, actual local encrypted SMTP delivery/recovery, complete
release evidence and a reported human spoken assistive-technology check. See
[gate evidence](.agent/logs/2026-09-17/2026-09-17-v1-release-gate.md).
Release [0.2.0](https://github.com/EoCiMrEo/Cardchemy/releases/tag/v0.2.0) was
published on 2026-10-05 through the protected publication flow. Each operator
still verifies provider quality, external SMTP/DNS/mailbox delivery and their
own hosting/recovery goals.


## Product quality and final Lane 7

Product-quality Lanes 0–6 are complete in their recorded scope. Lane 6 is 7/7
with retained local source-only v8/visual-v5/admission-v2 activation on 0033.
Public usefulness is 94/99; independently reviewed private usefulness is
21/24 (87.5%), with 12/12 hits. See the
[local closure](.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md).
Fresh installations remain default-off. Historical failure/cost records stay
unchanged; a complete local gate does not claim hosted CI, protected release
flow, public version publication or a production deployment.

On 2026-10-05 the operator defined the final Lane 7 scope, superseding the
historical tracker summaries:

- [x] Clean stale/unused implementations and consumed experiments, organize
  domain guides and archive completed plans. Both Python suites, disposable
  integration/journeys, frontend, image/security checks and an untouched
  base-Compose fresh clone passed; see the [cleanup record](.agent/logs/2026-10-04/2026-10-04-repository-cleanup.md).
- [x] Refresh the README and current documents and provide a comprehensive
  [Mermaid architecture guide](docs/diagrams/README.md), including current
  generation models, source-only Ask and its bounded lexical fallback.
- [x] Publish the latest source through protected GitHub checks, resolve the
  remaining pull requests and publish the verified 0.2.0 release. [PR 44](https://github.com/EoCiMrEo/Cardchemy/pull/44)
  merged as `7f326e833c586d7008b18daf85d3a425623d3e72`; the
  [exact-main CI](https://github.com/EoCiMrEo/Cardchemy/actions/runs/37395995321)
  and [signed release workflow](https://github.com/EoCiMrEo/Cardchemy/actions/runs/37396275822)
  passed. Existing PRs 38, 42 and 43 were closed.

The [archived product-quality tracker](docs/archive/PRODUCT-QUALITY-REMEDIATION-PLAN.md)
preserves the original chronology. **Lane 7 is 3/3 complete. All approved
delivery plans are complete; no active implementation plan remains.** The
[Lane 7 release record](.agent/logs/2026-10-05/2026-10-05-lane7-release.md)
contains actual publication, signed-artifact/image verification, fresh-clone
startup and preservation evidence. This is a self-hosted project release;
operators own their deployments.

## Uncommitted future ideas

Native mobile clients, another UI language, offline study/PWA/conflict handling,
quiz/rewards, a broker/Redis/Celery layer and broader multi-tenant/distributed
governance have no accepted implementation or delivery commitment. Evaluate
a concrete user need, privacy/data design, operating costs and compatibility
before accepting a proposal. Discuss new work in a feature issue; archived
toolkit affiliation and early brainstorming do not define current architecture.

The inherited source was published through [PR 41](https://github.com/EoCiMrEo/Cardchemy/pull/41), merged as `61b34eb`; see [publication evidence](.agent/logs/2026-10-04/2026-10-04-github-publication.md). Lane 7's protected publication and 0.2.0 release are recorded separately. Dated local activation is historical evidence, not a current container-health claim.
