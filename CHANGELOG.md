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

### Changed

- Added hashed Python lockfiles and documented supported runtime versions.
- Removed unused PWA, query-client, vector, document, and migration dependencies.

## [0.1.0] - 2026-01-29

### Added

- Initial PDF-to-flashcard instructor workflow.
- Instructor review and publication, student invitations, study mode, timers, and progress tracking.

[Unreleased]: https://github.com/EoCiMrEo/FlashCardGenerator/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/EoCiMrEo/FlashCardGenerator/releases/tag/v0.1.0
