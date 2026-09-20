# Frontend map of content

Read [Start Here](../docs/00-START-HERE.md) and the
[project map](../PROJECT-MAP.md) first. This map describes the current React
client; the [system overview](../docs/architecture/SYSTEM-OVERVIEW.md) explains
its API, worker, and database boundaries.

## Purpose and ownership

The browser supports instructor subject/Knowledge management, PDF generation,
card/Knowledge publication, private Subject Ask AI, invitations, and student
study. FastAPI owns authorization, durable generation/index/answer execution,
evidence validity, answer correctness, and persistent progress. Browser guards
and form checks improve interaction but do not replace server enforcement.

The built Nginx edge emits only numeric status/duration access events and
suppresses request-bearing error text. It never logs URL paths, queries, IPs,
headers or bodies. See [observability](../docs/OBSERVABILITY.md); the operator's
TLS proxy and collector need the same redaction and their own expiry policy.

The stack is React 19, TypeScript, React Router 7, Redux Toolkit, Axios, Tailwind
CSS 4, Radix primitives, and Framer Motion, built by Vite 8. Supported Node/npm
versions are maintained in [Runtimes](../docs/RUNTIMES.md); exact dependencies
are in [package.json](package.json) and [package-lock.json](package-lock.json).

## Entry points and main areas

| Area | Entry or folder | Responsibility |
| --- | --- | --- |
| HTML/bootstrap | [index.html](index.html), [src/main.tsx](src/main.tsx) | Mount React, Redux, and user-preference motion handling. |
| Routing | [src/App.tsx](src/App.tsx) | Lazy pages, auth provider, error boundary, role-aware subject route, redirects, and not-found route. |
| Session | [src/context/AuthContext.tsx](src/context/AuthContext.tsx), [src/components/auth/RouteGuards.tsx](src/components/auth/RouteGuards.tsx) | Bootstrap/profile state and protected/role-specific UI. |
| API boundary | [src/services/](src/services/), especially [api.ts](src/services/api.ts), [types.ts](src/services/types.ts), [errors.ts](src/services/errors.ts) | Validated API base, bearer token/refresh coordination, typed contracts, and bounded error messages. |
| Instructor pages | [src/pages/instructor/](src/pages/instructor/) | Dashboard, subject upload/job management, and set/card review. |
| Student pages | [src/pages/student/](src/pages/student/) | Enrolled subjects, server-owned set progress, and study interaction. |
| Public account/join pages | [src/pages/](src/pages/) | Login, invited student registration, recovery/reset, joining, dashboard shell, and not-found handling. |
| Shared interactions | [src/components/](src/components/) | Generation telemetry, subject/invitation/set/preview dialogs, UI primitives, and failure views. |
| Brand | [BrandWordmark.tsx](src/components/BrandWordmark.tsx), [public/brand/](public/brand/), [index.html](index.html) | Shared accessible wordmark and supplied ICO; originals preserved under [separate terms](../BRANDING.md). |
| Job polling | [src/hooks/useGenerationJobs.ts](src/hooks/useGenerationJobs.ts) | Owner-scoped jobs/limits, active-job polling, cancellation/retry, and completion refresh. |
| Subject Knowledge | [KnowledgeArea.tsx](src/components/knowledge/KnowledgeArea.tsx), [knowledge.ts](src/services/knowledge.ts) | Instructor-only Knowledge upload/revision, capture/index/review/publication state, persisted-page retry, unpublish and removal. |
| Subject Ask AI | [AskAiPanel.tsx](src/components/rag/AskAiPanel.tsx), [rag.ts](src/services/rag.ts) | Principal-private threads/history, durable job recovery, stable logical retry identity, safe answer text and authorized evidence dialogs. |
| Study session state | [src/store/](src/store/), [studySlice.ts](src/store/slices/studySlice.ts) | Current cards/index, server-confirmed answer results, and session completion; no durable browser outbox. |
| Copy/style | [src/i18n/en.ts](src/i18n/en.ts), [src/index.css](src/index.css), [src/components/ui/](src/components/ui/) | English v1 catalog, Tailwind theme, focus/reduced-motion rules, and shared accessible controls. |

## Routes

| Browser route | Page/control boundary |
| --- | --- |
| `/login`, `/register`, `/forgot-password`, `/reset-password` | Public account pages; registration requires an invitation. |
| `/join?token=…` | JoinCourse preserves the invitation through sign-in/registration and accepts it for a student. |
| `/dashboard` | Protected Dashboard renders InstructorDashboard or StudentDashboard. |
| `/subjects/:id` | Protected subject route renders SubjectDetails for instructors or StudentSubjectDetails for students. |
| `/sets/:id` | Instructor-only SetView. |
| `/study/:id`, optionally `?mode=review_all` | Student-only StudyMode; `id` is a set ID. |

`/` redirects to `/dashboard`; unmatched paths render NotFound. The backend
still independently verifies roles, ownership/enrollment, publication, and
approval. Read [Authentication](../docs/architecture/AUTH-FLOW.md).

## Important control flows

**Loading and navigation:** Initial loading is declared in state; route loading
is derived from the completed Subject/set/session key. Event retries explicitly
enter loading. Loaders pass abort signals and ignore late canceled responses.
Subject/set instructor forms remount when their route ID changes; study cards
remount for a changed set/mode/card. Generation jobs and limits remain scoped to
the current Subject, including failed polls and delayed cancel/retry responses.

**Session:** Login calls `authService.login`, then AuthContext stores the access
token in memory and reads `/auth/me`. On reload, bootstrap uses the HttpOnly
refresh cookie through `/auth/refresh`. Protected requests share one in-flight
refresh after a 401 and retry once. Operation revisions prevent stale refresh
or profile responses from replacing a newer login/logout. Server logout must
succeed before the client clears the active session.

**Generation:** SubjectDetails reads limits, reserves a job with
`POST /flashcards/generation-jobs` and one logical `Idempotency-Key`, then uploads
raw PDF bytes with `PUT /flashcards/generation-jobs/{job_id}/source`.
`useGenerationJobs` lists jobs, polls active statuses, backs off status failures,
and refreshes sets on completion. GenerationJobCard renders server telemetry
and the server's `can_cancel`/`can_retry` controls. Provider calls happen in the
generation worker. Follow [AI generation](../docs/architecture/AI-GENERATION-FLOW.md)
and the backend [generation router](../backend/app/routers/generation.py).

**Review and publication:** SetView loads set metadata through subjectService
and cards through flashcardService. Editing validates the four options and
correct answer locally; approval is a separate explicit card action.
EditSetDialog updates publication and the optional per-card timer through
subjectService. Student access remains server-filtered. Follow the backend
[subjects router](../backend/app/routers/subjects.py) and
[flashcards router](../backend/app/routers/flashcards.py).

**Invitations:** InviteStudentDialog calls subjectService to create an invite;
an optional recipient queues server email. JoinCourse and StudentDashboard
use the shared abortable join request for `POST /subjects/invitations/accept`.
The backend owns idempotent enrollment. See [Auth flow](../docs/architecture/AUTH-FLOW.md)
and [email delivery](../docs/EMAIL_DELIVERY.md).

**Subject Knowledge and Ask AI:** Instructor SubjectDetails keeps normal
flashcard generation separate from Knowledge upload/revision and explicit
review/publication. Both instructor and student Subject pages lazy-load one
private Ask AI panel. It reloads server-owned threads/history/jobs, polls one
active job at a time with abort cleanup, reuses the same idempotency key only
for one logical failed submission, renders model output as text, and opens
current server-derived page/section evidence in an accessible dialog. Read the
[Knowledge flow](../docs/architecture/SUBJECT-KNOWLEDGE-FLOW.md).

**Study/progress:** StudentSubjectDetails loads visible sets and server progress.
StudyMode gets answer-free cards from `GET /study/sets/{set_id}/session`.
StudyCardView creates one key/payload per logical answer and sends
`POST /study/progress`; click, timeout, and retry share that submission. Feedback
and Next remain blocked until success. The response supplies correctness and
the correct option; Redux records that acknowledged result. Progress uses the
server's separate completion/mastery percentages. Review Again requests
`review_all` instead of due-only cards. Read
[Study/progress](../docs/architecture/STUDY-PROGRESS-FLOW.md),
[data model](../docs/architecture/DATA-MODEL.md), and the
[study router](../backend/app/routers/study.py).

## Common files changed together

| Change | Read/change together |
| --- | --- |
| API/session contract | `src/services/api.ts`, `auth.ts`, `types.ts`, `src/context/AuthContext.tsx`, route guards, backend auth schemas/router/service; `tests/components/auth.test.tsx` and auth browser specs. |
| Upload/job state or telemetry | Instructor SubjectDetails, `src/hooks/useGenerationJobs.ts`, GenerationJobCard, `src/services/flashcards.ts`/`types.ts`, generation router/schemas/service/worker; `e2e/generation-telemetry.spec.ts`. |
| Knowledge/Ask AI state | SubjectDetails/StudentSubjectDetails, `src/components/knowledge/`, `src/components/rag/`, `src/services/knowledge.ts`/`rag.ts`/`types.ts`, backend Knowledge/RAG routers and workers; `e2e/rag-knowledge.spec.ts` and the deterministic real journey. |
| Card review/publication | Instructor SetView, EditSetDialog/PreviewDialog, subject/flashcard services and types, backend card/set contracts; editing component and browser specs. |
| Study correctness/retry/progress | StudyMode, StudentSubjectDetails, studySlice, `src/services/study.ts`/`types.ts`, backend study router/schemas and progress persistence; study component, reliability/recovery/progress browser specs. |
| Invitations | JoinCourse, StudentDashboard, InviteStudentDialog, `src/services/subjects.ts`, auth/subject types and backend invitation/email contracts; join/auth-recovery/invitation browser specs. |
| Shared UX or wording | `src/components/ui/`, `src/index.css`, `src/i18n/en.ts`, affected pages, accessibility/responsive browser specs; [accessibility](../docs/ACCESSIBILITY.md) and [localization](../docs/LOCALIZATION.md). |

Use the architecture documents and [ADR index](../docs/decisions/ADR-000-INDEX.md)
before changing a recorded contract. Persistent model or API changes also need
backend review; frontend types are hand-maintained, not generated OpenAPI code.

## Configuration and serving

[vite.config.ts](vite.config.ts) and [config/environment.mjs](config/environment.mjs)
read only repository-root `.env`, with process values taking precedence.
Normal Vite env-file discovery is disabled. Only the public `VITE_API_URL`
reaches browser code; `API_PORT` configures the local proxy. With `/api`, Vite
strips that prefix and rewrites the refresh-cookie path to `/api/auth`.

[Dockerfile](Dockerfile) builds the SPA and serves it through unprivileged Nginx.
[nginx.conf](nginx.conf) supplies SPA fallback, fingerprinted asset caching,
same-origin `/api` proxying, cookie-path rewriting, and edge health checks.
Changing the built public URL requires rebuilding the frontend. See
[Configuration](../docs/CONFIGURATION.md) and [Deployment](../docs/DEPLOYMENT.md).

## Validation and product boundaries

From `frontend/`, `npm run check` is the maintained frontend gate.
[e2e/support/run.mjs](e2e/support/run.mjs) runs application, browser, and component
typechecks; lint; Node units; Vitest components with coverage; production build;
then Playwright Chromium. The fixtures inject safe public settings without
consulting operator `.env`. Component coverage in [vitest.config.ts](vitest.config.ts)
is focused on four critical files, not whole-frontend coverage. CI also runs
`node ../scripts/check_bundle.mjs` after the build.

Tests live in [tests/](tests/), [e2e/](e2e/), and [journey/](journey/). Ordinary
browser regressions use controlled API fixtures; they do not prove a live
backend or paid AI provider. The separate real API/worker/database journey runs
from the root with `python scripts/test_journey.py` and a deterministic test
provider. The live Mailpit password-reset case has dedicated disposable
environment gating. Read [Testing](../docs/TESTING.md) and [CI](../docs/CI.md).

The client is responsive and online-first. Answers require durable server
acknowledgement before advancing; there is no service worker or IndexedDB
outbox. Preserve keyboard/focus behavior, text feedback, reduced motion, touch
targets, and overflow protection. Manual spoken assistive-technology checks
remain release evidence under [Accessibility](../docs/ACCESSIBILITY.md).
