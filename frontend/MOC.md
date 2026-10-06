# Frontend map of content

## Current local Lane 6 closure â€” 2026-10-04

The local source-only v8/visual-v5/admission-v2 installation on head `0033`
is enabled after its measured quality, PDF/display and release gates. Fresh
installations remain default-off. See the
[closure and activation evidence](../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md). This is dated activation evidence; fresh-install default-off and upgrade
safeguards still apply. It does not assert current container health.

The current source-only panel fences new admission/retry to v8/visual-v5,
while retaining earlier published-reference history including v7. Its transfer
disclosure and source-only PDF behavior are unchanged. Full current frontend
checks passed; retained installation and independent private quality remain
separate from frontend source verification. See
[completion work](../.agent/logs/2026-10-03/2026-10-03-v8-completion-work.md).

Read [Start Here](../docs/00-START-HERE.md) and the
[project map](../PROJECT-MAP.md) first. This map describes the current React
client; the [system overview](../docs/architecture/SYSTEM-OVERVIEW.md) explains
its API, worker, and database boundaries.

## Purpose and ownership

The browser supports instructor subject/Knowledge management, PDF generation,
card/Knowledge publication, private Subject Ask AI, invitations, and student
study. FastAPI owns authorization, durable generation/index/source-only Ask
execution, evidence validity, card answer correctness, and persistent progress. Browser guards
and form checks improve interaction but do not replace server enforcement.

The built Nginx edge emits only numeric status/duration access events and
suppresses request-bearing error text. It never logs URL paths, queries, IPs,
headers or bodies. See [observability](../docs/operations/OBSERVABILITY.md); the operator's
TLS proxy and collector need the same redaction and their own expiry policy.

The stack is React 19, TypeScript, React Router 7, Redux Toolkit, Axios, Tailwind
CSS 4, Radix primitives, and Framer Motion, built by Vite 8. Supported Node/npm
versions are maintained in [Runtimes](../docs/development/RUNTIMES.md); exact dependencies
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
| Job polling | [src/hooks/useGenerationJobs.ts](src/hooks/useGenerationJobs.ts) | Owner-scoped jobs/limits, active and both pending-choice statuses, cancellation/cost-aware retry, idempotent Knowledge and card-count choice, and completion refresh. |
| Subject Knowledge | [KnowledgeArea.tsx](src/components/knowledge/KnowledgeArea.tsx), [knowledge.ts](src/services/knowledge.ts) | Instructor-only Knowledge upload/revision, capture/index/review/publication state, persisted-page retry, unpublish and removal. |
| Subject Ask AI | [AskAiPanel.tsx](src/components/rag/AskAiPanel.tsx), [rag.ts](src/services/rag.ts) | Principal-private threads/history, durable job recovery, released v8 visual source-judge and bounded literal-subject disclosure, distinct related/no-match/clarification/provider-failure states, unverified source-labeled cues, authenticated lazy original-PDF viewer and stable logical retry identity. Fresh installations remain default-off; the retained local installation passed its release gates. |
| Student published lectures | [PublishedKnowledgeBrowser.tsx](src/components/knowledge/PublishedKnowledgeBrowser.tsx), [publishedKnowledge.ts](src/services/publishedKnowledge.ts), [OriginalPdfPage.tsx](src/components/rag/OriginalPdfPage.tsx) | Independent enrolled-student catalog and page search, current-access PDF page view and extracted-text fallback while Ask is paused or finds no match. |
| Study session state | [src/store/](src/store/), [studySlice.ts](src/store/slices/studySlice.ts) | Current cards/index, server-confirmed answer results, and session completion; no durable browser outbox. |
| Copy/style | [src/i18n/en.ts](src/i18n/en.ts), [src/index.css](src/index.css), [src/components/ui/](src/components/ui/) | English v1 catalog, Tailwind theme, focus/reduced-motion rules, and shared accessible controls. |

## Routes

| Browser route | Page/control boundary |
| --- | --- |
| `/login`, `/register`, `/forgot-password`, `/reset-password` | Public account pages; registration requires an invitation. |
| `/join?token=â€¦` | JoinCourse preserves the invitation through sign-in/registration and accepts it for a student. |
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
`useGenerationJobs` lists jobs, polls active and pending-choice statuses, backs off status failures,
and refreshes sets on completion. After upload, a same-Subject PDF match can
return a durable `awaiting_choice` job. GenerationJobCard opens an accessible
dialog to reuse a compatible ready Knowledge revision, create a separate private
copy, or cancel the whole job. The choice is idempotent and recoverable after
reload; Knowledge-only uploads use the same job list. An unchanged explicit
revision reports `No changes detected`. The card also renders server telemetry
and the server's `can_cancel`/`can_retry` controls. Provider calls happen in the
generation worker. Follow [AI generation](../docs/architecture/AI-GENERATION-FLOW.md)
and the backend [generation router](../backend/app/routers/generation.py).

If a bounded run verifies fewer cards than requested, a separate
`awaiting_card_choice` state survives reload with an observed validated count.
The owner can confirm an exact smaller count within that range; the API commits
one unpublished draft set without another provider call. Retry toward the
original target is a distinct action: the dialog states additional estimated
cost or unavailable cost and unknown prior cost, and the browser sends the
server-required acknowledgement. The card labels latest-attempt validation,
cumulative rejection and persisted result counts separately.

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
and [email delivery](../docs/mail-server/EMAIL_DELIVERY.md).

**Subject Knowledge and Ask AI:** Instructor SubjectDetails keeps normal
flashcard generation separate from Knowledge upload/revision and explicit
review/publication. Both instructor and student Subject pages lazy-load one
private Ask AI panel. It reloads server-owned threads/history/jobs, polls one
 active job at a time with abort cleanup, and reuses the same idempotency key
 only for one logical failed submission. The source-only result shows up to
 three currently authorized exact related passages with page labels, clearly
 states they are not verified answers, and opens the original lecture PDF page
 in an accessible dialog. The released v8 disclosure names the query embedding
 and source judge, including bounded published page text and rendered full-page
 PNG transfer, before Ask can enqueue. Only an unresolved follow-up may add
 a unique literal subject of at most 160 characters/twelve words from the
 strictly preceding user question, under the immutable visual-v5/admission-v2 capability.
 Original PDF bytes, the full prior question/history and assistant text are
 excluded. Clarification, no match, provider
 failure and withdrawn references
 have separate safe text. No new answer-model output is rendered. Read the
[Knowledge flow](../docs/architecture/SUBJECT-KNOWLEDGE-FLOW.md).

The lazy [OriginalPdfPage](src/components/rag/OriginalPdfPage.tsx) loads PDF.js
only on source open, uses authenticated bounded ranges and rechecks current
page access before navigation. The quote remains adjacent to the rendered page;
text offsets do not imply a visual PDF highlight. A lexical fallback label
separates reduced search from normal hybrid results.
The built edge serves its `.mjs` worker with a JavaScript MIME type and the
viewer versions the worker URL once to recover browsers that cached an older
wrong-MIME response under immutable asset caching.
The student [PublishedKnowledgeBrowser](src/components/knowledge/PublishedKnowledgeBrowser.tsx)
uses a separate enrolled-student API for catalog, local page search and PDF
navigation even while Ask admission is disabled. It clears stale search links
and restores safe focus when publication or enrollment access changes.

**Study/progress:** StudentSubjectDetails loads visible sets and server progress.
StudyMode gets answer-free cards from `GET /study/sets/{set_id}/session`.
StudyCardView creates one key/payload per logical answer and sends
`POST /study/progress`; click, timeout, and retry share that submission. Feedback
and Next remain blocked until success. The response supplies correctness and
the correct option; Redux records that acknowledged result. The card view
shuffles a display-only copy of options once and sends canonical option text.
Progress, Accuracy, Attempted and Mastery use separate server fields; Review Again requests
`review_all` instead of due-only cards. Read
[Study/progress](../docs/architecture/STUDY-PROGRESS-FLOW.md),
[data model](../docs/architecture/DATA-MODEL.md), and the
[study router](../backend/app/routers/study.py).

## Common files changed together

| Change | Read/change together |
| --- | --- |
| API/session contract | `src/services/api.ts`, `auth.ts`, `types.ts`, `src/context/AuthContext.tsx`, route guards, backend auth schemas/router/service; `tests/components/auth.test.tsx` and auth browser specs. |
| Upload/job state or telemetry | Instructor SubjectDetails, KnowledgeArea, `src/hooks/useGenerationJobs.ts`, GenerationJobCard, `src/services/flashcards.ts`/`types.ts`, generation router/schemas/service/worker; `e2e/generation-telemetry.spec.ts` and `e2e/knowledge-duplicate.spec.ts`. |
| Knowledge/Ask AI state | SubjectDetails/StudentSubjectDetails, `src/components/knowledge/`, `src/components/rag/`, `src/services/knowledge.ts`/`rag.ts`/`types.ts`, backend Knowledge/RAG routers and workers; `e2e/rag-knowledge.spec.ts` and the deterministic real journey. |
| Card review/publication | Instructor SetView, EditSetDialog/PreviewDialog, subject/flashcard services and types, backend card/set contracts; editing component and browser specs. |
| Study correctness/retry/progress | StudyMode, StudentSubjectDetails, studySlice, `src/services/study.ts`/`types.ts`, backend study router/schemas and progress persistence; study component, reliability/recovery/progress browser specs. |
| Invitations | JoinCourse, StudentDashboard, InviteStudentDialog, `src/services/subjects.ts`, auth/subject types and backend invitation/email contracts; join/auth-recovery/invitation browser specs. |
| Shared UX or wording | `src/components/ui/`, `src/index.css`, `src/i18n/en.ts`, affected pages, accessibility/responsive browser specs; [accessibility](../docs/ui/ACCESSIBILITY.md) and [localization](../docs/ui/LOCALIZATION.md). |

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
[Configuration](../docs/operations/CONFIGURATION.md) and [Deployment](../docs/operations/DEPLOYMENT.md).

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
environment gating. Read [Testing](../docs/development/TESTING.md) and [CI](../docs/ci-cd/CI.md).

The client is responsive and online-first. Answers require durable server
acknowledgement before advancing; there is no service worker or IndexedDB
outbox. Preserve keyboard/focus behavior, text feedback, reduced motion, touch
targets, and overflow protection. Manual spoken assistive-technology checks
remain release evidence under [Accessibility](../docs/ui/ACCESSIBILITY.md).
