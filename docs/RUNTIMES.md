# Supported runtimes

This file is the source of truth for local, CI, and container runtime support.

| Component | Supported | Baseline verified for this remediation |
| --- | --- | --- |
| Node.js | 24.x | 24.7.0 |
| npm | 11.x | 11.19.1 |
| Python | 3.11 through 3.13 | 3.11 container target; 3.13.7 local |
| PostgreSQL | 16.x | Compose uses `postgres:16` |
| Docker Engine | 24 or newer | 29.8.0 |
| Docker Compose | 2.20 or newer | 5.5.1 |

## Container platform support

Published self-hosting support targets Linux/amd64 containers. Linux hosts run
them directly; supported Windows and macOS hosts run them through a current
Docker Desktop Linux-container VM. Linux/arm64 is best effort until the default
and OCR images, PostgreSQL integration suite, and browser acceptance flow are
verified on that architecture.

The reference frontend build pins Node 24.7.0 for compilation and runs on an
unprivileged Nginx 1.31.3 Alpine image. The backend runtime uses Python 3.11 on
Alpine 3.24, runs as a non-root application user, and omits the compiler/header
toolchain used in its dependency-builder stage. Exact reference sizes and release inspection
commands are in [Deployment and self-hosting](DEPLOYMENT.md).

The npm version is declared in `frontend/package.json`. Python runtime packages
are pinned with hashes in `backend/requirements*.txt`; update them only through
`backend/scripts/lock_dependencies.ps1` and verify both Python 3.11 and 3.13.
