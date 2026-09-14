# Supported runtimes

This file is the source of truth for local, CI, and container runtime support.

| Component | Supported | Baseline verified for this remediation |
| --- | --- | --- |
| Node.js | 24.x | 24.7.0 |
| npm | 11.x | 11.5.1 |
| Python | 3.11 through 3.13 | 3.11 container target; 3.13.7 local |
| PostgreSQL | 16.x | Compose uses `postgres:16` |
| Docker Engine | 24 or newer | 29.2.1 |
| Docker Compose | 2.20 or newer | 5.1.0 |

The npm version is declared in `frontend/package.json`. Python runtime packages
are pinned with hashes in `backend/requirements*.txt`; update them only through
`backend/scripts/lock_dependencies.ps1` and verify both Python 3.11 and 3.13.
