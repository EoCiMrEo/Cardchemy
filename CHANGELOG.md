# Changelog

All notable changes are recorded here. This project follows Semantic Versioning
and the Keep a Changelog structure.

## [Unreleased]

### Security

- Added typed JWTs, rotating server-side refresh sessions, reuse detection, and logout revocation.
- Moved refresh tokens to Secure-capable HttpOnly SameSite cookies.
- Consolidated student invitations into a signed, database-backed, single-use flow.
- Added explicit role and study-resource authorization checks.
- Removed reusable instructor registration secrets and added an operator CLI.
- Added a single-use SMTP password-reset flow and shared rate limits.
- Added media/signature validation, hard PDF resource bounds, safe error
  categories, and AES-256-GCM temporary source encryption.

### Added

- Added role-aware frontend routing, recoverable page and mutation error states,
  a wildcard not-found page, and an application error boundary.
- Added a typed English UI catalog with a documented English-only v1
  localization policy.
- Added a Playwright Chromium acceptance suite for authentication races, role
  routing, invitation joins, error recovery, card editing, and progress display.
- Added PostgreSQL-backed generation jobs with leases, bounded workers,
  cancellation, retries with jitter, idempotency keys, quotas, and cleanup.
- Added reload-safe job polling, progress, cancellation, retry, and completed-set
  navigation to the instructor UI.
- Added optional Poppler/Tesseract OCR with explicit build and capacity controls.
- Added strict source-grounded AI contracts with page/section citations,
  hierarchical summaries, deterministic quality checks, near-duplicate
  rejection, exact global card targets, and a fixed offline evaluation corpus.
- Added Gemini and OpenAI-compatible provider adapters with validated model,
  retry, context, concurrency, token, and operator-supplied cost limits.
- Added persisted per-job provider/model, estimated and actual token/cost,
  accepted/rejected card counts, and visible limit reasons.

### Changed

- Replaced untyped frontend API payloads with backend-aligned request and
  response contracts and a validated `VITE_API_URL` client configuration.
- Made refresh, logout, and invitation acceptance safe under concurrent requests
  and React Strict Mode, including existing-student invite sign-in continuity.
- Expanded multiple-choice editing with complete validation, explicit approval,
  and per-card concurrent action state; progress now renders server-owned metrics.
- Added hashed Python lockfiles and documented supported runtime versions.
- Removed unused PWA, query-client, vector, document, and migration dependencies.
- Replaced synchronous request-bound PDF generation with a two-step upload and
  separately deployed generation worker.
- Replaced model confidence approval with deterministic server validation;
  generated cards always require explicit instructor review.
- Replaced character-window processing and the LangChain/LangGraph runtime with
  structure-aware token chunks and a small provider-neutral pipeline.

## [0.1.0] - 2026-01-29

### Added

- Initial PDF-to-flashcard instructor workflow.
- Instructor review and publication, student invitations, study mode, timers, and progress tracking.

[Unreleased]: https://github.com/EoCiMrEo/FlashCardGenerator/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/EoCiMrEo/FlashCardGenerator/releases/tag/v0.1.0
