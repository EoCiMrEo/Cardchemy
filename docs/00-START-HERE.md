# Cardchemy: Start Here

Current truth, checked against this checkout on 2026-10-04. This is the
canonical orientation; [source navigation](../PROJECT-MAP.md) leads to the
implementation, which remains the final authority.

## Product summary

Instructors upload lecture PDFs to generate source-grounded flashcards,
review them, and publish them for enrolled students. Students study approved
cards and see correct-card Progress, attempt Accuracy, Attempted and Mastery.
This is a responsive browser
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
   When bounded generation finds fewer valid cards than requested, a pending
   owner choice can commit an exact smaller count without another AI call;
   retrying toward the original count requires a separate cost confirmation.
2. Invitation link/email → validation → student registration or existing-user
   join → atomic invitation consumption and enrollment.
3. Published approved cards → due/review-all study → selected option/timeout →
   server-derived result and durable receipt → refreshed correct-card Progress,
   Accuracy, Attempted and Mastery.
4. Forgot password → transactional email outbox → SMTP worker → single-use
   reset → session revocation and password-change notification.
5. Instructor PDF → private extracted Knowledge → isolated embedding/index
   worker → explicit Knowledge review/publication. Existing private Subject
   Ask AI history remains readable. The released v8 path is default-off for
   fresh installations: at most one current-question embedding and one bounded
   text/PNG source-ID judgment, then zero to three exact published PDF page
   references, clearly marked unverified, and an authenticated original-PDF
   viewer. Transient embedding failure may use bounded local lexical search.
   It creates no generated or verified answer; see
   [ADR-023](decisions/ADR-023-original-pdf-source-navigation.md).
   A same-Subject repeated new upload pauses for an owner choice before capture;
   an unchanged explicit revision creates no new Knowledge revision or index.

## Current development state

Ask AI is enabled in the retained local installation (verified 2026-10-04). Product-quality Lane 6 is **7/7 complete** on
retained head `20261002_0033`; Lane 7's three tasks remain unchecked. See the
[actual local closure](../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md), including independent usefulness,
source/display, release checks and the limits of controlled browser replay.

Version 0.1.0; [current state](development/CURRENT-STATE.md) and dated
[closure evidence](../.agent/logs/2026-09-21/2026-09-21-rag-release-closure.md)
record Phases 0–21 complete, including independently verified public v0.1.0
publication and Subject Knowledge/RAG closure. The separate v1.0 operational
readiness gate passed; see
[gate evidence](../.agent/logs/2026-09-17/2026-09-17-v1-release-gate.md).
The published version remains 0.1.0; readiness completion did not publish v1.0.
See [release procedures](RELEASING.md).
Local development is the reference environment;
production-shaped Compose and production operating guides do not establish a
live production deployment. Read [current state](development/CURRENT-STATE.md).

## Technology stack

FastAPI/Pydantic, SQLAlchemy async/asyncpg, PostgreSQL 16 and Alembic; typed
application AI orchestration with the native Gemini SDK. The Ask worker's new
source-only path uses query embeddings, local retrieval and at most one
bounded Gemini text/PNG source-ID judgment; its former ONNX answer-verifier
runtime is historical. Historical
OpenAI-compatible job and vector identities remain readable for migration.
PDF extraction uses pypdf, with optional Poppler/Tesseract OCR. React 19,
TypeScript, Vite, React Router, Axios, Redux Toolkit, Tailwind, Radix and Framer
Motion make up the client. Docker Compose runs separate generation, index,
answer and email workers plus a built Nginx frontend; local SMTP is Mailpit. See
[runtime support](RUNTIMES.md) and [dependency policy](DEPENDENCIES.md).

## Important product / technical invariants

- Cards currently have exactly four distinct options and one correct answer.
- The server derives correctness and scheduling from the selected answer;
  Progress counts approved cards ever answered correctly, Attempted counts
  distinct attempted approved cards, Accuracy counts successful attempts, and
  Mastery follows spaced-repetition status. Study shuffles displayed options
  without changing stored order.
- Instructor ownership, student role/enrollment, publication and approval are
  server checks. The study-session payload hides the answer, but authorized
  card-read APIs currently include it; see [study limits](architecture/STUDY-PROGRESS-FLOW.md).
- Access tokens live in browser memory. Refresh tokens use an HttpOnly cookie,
  rotation and server sessions; token purposes are distinct.
- Alembic alone evolves the schema; processes verify every head before work.
- AI content passes structural, grounding and duplicate checks before atomic
  persistence. Generated cards still require instructor approval.
- Generation, Knowledge indexing, Subject Ask AI history and email are durable
  PostgreSQL workflows with leases/fencing; no Redis/broker is required.
  Ask defaults off and requires explicit Ask/judge flags, matching active
  embeddings, current embedding/judge prices and source-only release evidence. Its durable attempt has zero automatic provider
  retries; generation and indexing retain their separate bounded retry policy.
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
Current state owns completed milestone status; the public roadmap owns proposals.
Dated [agent logs](../.agent/logs/README.md) and [archived plans/ideas](archive/README.md)
and the completed [context implementation log](../.agent/logs/2026-09-16/2026-09-16-repository-context-system.md)
are evidence/reference. They may contain superseded paths, baseline failures or
future ideas. Do not treat them as current instructions or shipped features.
