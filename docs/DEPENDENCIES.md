# Dependency policy

Runtime packages must be directly imported by shipped code. Test and lock tools
belong in `requirements-dev.in`; optional live-AI tests are excluded from normal
test runs and require both `RUN_LIVE_AI_TESTS=1` and provider credentials.

Phase 0 removed these unused or premature dependencies:

- Backend: `alembic` (migrations begin in Phase 2), `pgvector` (no vector schema
  or search exists), `python-docx` (only PDF input exists), the `langchain`
  meta-package, and runtime `httpx`.
- Frontend: `idb` (no offline outbox), `@tanstack/react-query` (no queries used
  it), and `jwt-decode` (the browser no longer trusts token claims).

`@reduxjs/toolkit` and `react-redux` remain because study-session state uses
them. Radix packages remain because the shared UI components import them.
