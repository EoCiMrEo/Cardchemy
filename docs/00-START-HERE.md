# Cardchemy: Start Here

Current truth, checked against this checkout on 2026-09-20. This is the
canonical orientation; [source navigation](../PROJECT-MAP.md) leads to the
implementation, which remains the final authority.

## Product summary

Instructors upload lecture PDFs to generate source-grounded flashcards,
review them, and publish them for enrolled students. Students study approved
cards and see completion, accuracy, and mastery. This is a responsive browser
application with an online-first study flow.

## Users and roles

- Instructors own subjects, sets, generation jobs, review and invitations.
  Instructor accounts are created by an operator CLI, not public signup.
- Students register through a single-use invitation or join an invited subject
  with an existing account. Enrollment and publication constrain their access.
- Operators manage installation, credentials, migrations, recovery and queues;
  this is an operational responsibility, not a third application role.

## Core workflows

1. Instructor creation/sign-in → subject → reserved job/raw PDF upload → durable
   extraction and grounded generation → instructor approval → publication.
2. Invitation link/email → validation → student registration or existing-user
   join → atomic invitation consumption and enrollment.
3. Published approved cards → due/review-all study → selected option/timeout →
   server-derived result and durable receipt → refreshed progress.
4. Forgot password → transactional email outbox → SMTP worker → single-use
   reset → session revocation and password-change notification.
5. Instructor PDF → private extracted Knowledge → isolated embedding/index
   worker → explicit Knowledge review/publication → an enrolled user's private
   Subject Ask AI thread → isolated answer worker → supported answer/citations.

## Current development state

Version 0.1.0; [the roadmap](../issues-required-remediation.md) and dated
[closure evidence](../.agent/logs/2026-09-17/2026-09-17-phase-11-remediation.md)
record Phases 0–11 complete and independently verified public v0.1.0
publication. The separate v1.0 operational readiness gate passed; see
[gate evidence](../.agent/logs/2026-09-17/2026-09-17-v1-release-gate.md).
The published version remains 0.1.0; readiness completion did not publish v1.0.
See [release procedures](RELEASING.md).
Local development is the reference environment;
production-shaped Compose and production operating guides do not establish a
live production deployment. Read [current state](development/CURRENT-STATE.md).

## Technology stack

FastAPI/Pydantic, SQLAlchemy async/asyncpg, PostgreSQL 16 and Alembic; typed
application AI orchestration with direct Gemini SDK or OpenAI-compatible HTTP.
PDF extraction uses pypdf, with optional Poppler/Tesseract OCR. React 19,
TypeScript, Vite, React Router, Axios, Redux Toolkit, Tailwind, Radix and Framer
Motion make up the client. Docker Compose runs separate generation, index,
answer and email workers plus a built Nginx frontend; local SMTP is Mailpit. See
[runtime support](RUNTIMES.md) and [dependency policy](DEPENDENCIES.md).

## Important product / technical invariants

- Cards currently have exactly four distinct options and one correct answer.
- The server derives correctness and scheduling from the selected answer;
  completion and mastery measure different things.
- Instructor ownership, student role/enrollment, publication and approval are
  server checks. The study-session payload hides the answer, but authorized
  card-read APIs currently include it; see [study limits](architecture/STUDY-PROGRESS-FLOW.md).
- Access tokens live in browser memory. Refresh tokens use an HttpOnly cookie,
  rotation and server sessions; token purposes are distinct.
- Alembic alone evolves the schema; processes verify every head before work.
- AI content passes structural, grounding and duplicate checks before atomic
  persistence. Generated cards still require instructor approval.
- Generation, Knowledge indexing, Subject Ask AI and email are durable PostgreSQL workflows with leases/fencing; no
  Redis/broker is required. Provider retries are bounded under one owner.
- Root `.env` is the only user-managed file configuration. Secrets remain
  outside the browser and repository; Compose limits provider/SMTP credentials
  to their workers. Normal tests use injected settings/disposable services.
- Completion requires durable answer persistence. There is no offline answer
  queue or service worker. English is the supported UI language.
- Diagnostics use safe codes and opaque correlation IDs. Operator-only
  [metrics/audits](OBSERVABILITY.md) and [privacy controls](PRIVACY.md) exclude
  document content from logs; external aggregate reporting is off by default.

Rationale lives in the [accepted ADRs](decisions/ADR-000-INDEX.md).

## Repository boundaries

`backend/` owns HTTP authorization/contracts, persistence and workers.
`frontend/` consumes those contracts and manages transient UI state.
`scripts/` owns guarded validation/bootstrap harnesses; `.github/` owns CI and
budget/protection definitions. Cardchemy is the approved standalone identity;
code uses Apache-2.0 and supplied artwork has [separate terms](../BRANDING.md).
New installations use Cardchemy runtime names; existing installation settings
remain supported. [The public roadmap](../ROADMAP.md) separates proposals from
implemented behavior.

## Read in this order

[Agent rules](../AGENTS.md) → this file → [project map](../PROJECT-MAP.md) →
relevant architecture and ADRs → [backend MOC](../backend/MOC.md) or
[frontend MOC](../frontend/MOC.md) → task-relevant source/tests.
For first installation use [local setup](development/LOCAL-SETUP.md); for
operations use the [guide index](README.md).

## Current truth vs historical material

Maps, architecture docs and operational guides describe current behavior.
The remediation plan owns task status; current state owns the phase summary.
Dated [agent logs](../.agent/logs/README.md), [archived early ideas](archive/README.md)
and the completed [context implementation log](../.agent/logs/2026-09-16/2026-09-16-repository-context-system.md)
are evidence/reference. They may contain superseded paths, baseline failures or
future ideas. Do not treat them as current instructions or shipped features.
