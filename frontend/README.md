# Frontend development

This React and TypeScript client supports instructor review and publication of
AI-generated flashcards, invitations, and student study. The FastAPI backend owns
authentication, generation jobs, card data, and progress; the browser consumes
its API through `src/services/`.

Begin with the canonical [Start Here](../docs/00-START-HERE.md), then the
[project map](../PROJECT-MAP.md) and [frontend MOC](MOC.md) for routes, source
ownership, API traces, and common change paths.

## Run locally

Use the supported Node.js and npm versions in
[docs/RUNTIMES.md](../docs/RUNTIMES.md). Configure the application from the one
repository-root `.env` using [docs/CONFIGURATION.md](../docs/CONFIGURATION.md). The
public `VITE_API_URL` setting controls the browser API base. `/api` is the
same-origin path used by the Compose frontend; the local development route is
configured in `vite.config.ts`.

From `frontend/`:

```text
npm ci
npm run dev
```

The backend must be running for real application flows. The Compose deployment
builds and serves the frontend separately; see the deployment guide for the
complete stack and its development override.

## Validate changes

```text
npm run check
```

This checks application, browser-test, and component-test types, lint, Node unit
tests, Vitest component contracts with focused coverage, the production build,
and Playwright Chromium acceptance tests. Component coverage applies to the
four critical files configured in `vitest.config.ts`, not the whole frontend.
Install the pinned Chromium
runtime with `npx playwright install chromium` if needed. Browser tests start
their own local Vite server on port 4175 and use controlled API fixtures; the
live Mailpit password-reset test is gated separately by disposable credentials.
See [docs/ACCESSIBILITY.md](../docs/ACCESSIBILITY.md) for manual accessibility
checks and [docs/AI_EVALUATION.md](../docs/AI_EVALUATION.md) for AI quality gates.
The ordinary browser suite uses controlled API fixtures; run the separate real
application journey with `python scripts/test_journey.py` from the repository
root. Maintained commands and gates are in [docs/TESTING.md](../docs/TESTING.md).
