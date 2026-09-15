# Dependency policy

Runtime packages must be directly imported by shipped code. Test and lock tools
belong in `requirements-dev.in`; optional live-AI tests are excluded from normal
test runs and require both `RUN_LIVE_AI_TESTS=1` and provider credentials.

Phase 0 removed these unused or premature dependencies at that time:

- Backend: `pgvector` (no vector schema or search exists) and `python-docx`
  (only PDF input exists).
- Frontend: `idb` (no offline outbox), `@tanstack/react-query` (no queries used
  it), and `jwt-decode` (the browser no longer trusts token claims).

`@reduxjs/toolkit` and `react-redux` remain because study-session state uses
them. Radix packages remain because the shared UI components import them.
`@playwright/test` is a development-only dependency for the Phase 5 browser
acceptance suite; install its pinned Chromium runtime with
`npx playwright install chromium` before running `npm run test:e2e`.

Phase 2 introduced Alembic as the required schema owner. Phase 3 directly pins
`cryptography` because temporary PDF sources use AES-256-GCM authenticated
encryption. Optional OCR is provided by the external `poppler-utils` and
`tesseract-ocr` packages in OCR-enabled worker images; they are deliberately not
installed in the default image. See `docs/PDF_GENERATION.md` for the dependency,
capacity, and retention policy.

Phase 4 uses the direct `google-genai` SDK for Gemini and `httpx` for the
portable OpenAI-compatible HTTP contract. Provider prompts and orchestration
are plain typed application code, so `langchain`, `langchain-google-genai`, and
`langgraph` are not runtime dependencies. No vector schema, embedding model,
retrieval pipeline, or `pgvector` dependency is shipped. See
`docs/AI_PROVIDERS.md`.
