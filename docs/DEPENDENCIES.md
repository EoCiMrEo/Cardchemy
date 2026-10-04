# Dependency policy

Keep a package when it supports shipped runtime behavior, a CLI command, a
build step, or a maintained test. Python runtime dependencies are pinned with
hashes in `backend/requirements.txt`; test and lock tools are in
`backend/requirements-dev.txt`. Update direct pins in the corresponding `.in`
file and regenerate locks with `backend/scripts/lock_dependencies.ps1`, then
verify the supported Python versions in [RUNTIMES.md](RUNTIMES.md).

Source-only Ask reuses the canonical backend runtime and production lock.
Its former dedicated ONNX image and dependency superset have been removed
from active builds, audits and release inventory. The backend image probe
checks that NumPy, ONNX Runtime, tokenizers and local model artifacts are
absent. Historical local-model research scripts are outside the shipped
Ask path; they do not require or enable an answer verifier in the application.

The frontend original-page viewer pins `pdfjs-dist`
6.3.289 (Apache-2.0), lazy-loads its display code and worker on source open,
and retains the existing no-iframe/object CSP. Its upstream Apache-2.0 text
is redistributed with the frontend legal files. The 2026-09-27 measured
budget approval keeps initial JS gzip at 130,000 bytes and sets total JS gzip
at 780,000 and largest raw JS at 1,350,000; the checker includes both `.js`
and `.mjs` worker assets. Review final emitted bytes, dependency audit and
browser compatibility together before release.

The backend uses FastAPI, SQLAlchemy, PostgreSQL through `asyncpg`, and Alembic
for schema migrations. PyJWT handles purpose-scoped HS256 tokens; token
claims, issuer/audience, clock skew, and session verification remain enforced.
The direct `bcrypt` backend replaces Passlib while preserving the existing
password record formats and full-password v2 prehash. Historic v1 and raw
bcrypt verification is covered by independent known vectors and fixtures from
the prior runtime; see [password compatibility](decisions/ADR-013-password-hash-compatibility.md).
The production lock excludes python-jose and its unfixable ECDSA dependency. `cryptography` protects temporary PDF source data with
AES-256-GCM. New AI work uses the direct `google-genai` SDK. `httpx` remains a
general HTTP dependency and the historical adapter is unavailable from new-job
factories. AI orchestration and grounding are typed application
code, without an AI framework. Subject Knowledge uses the hash-locked Python
`pgvector` integration and PostgreSQL 16's pgvector 0.8.6 server extension;
[`runtime-artifacts.json`](../runtime-artifacts.json) pins the reviewed local
database recipe and its external base/source/package inputs independently of
the Python lock.
The database build's flattened final runtime uses pinned native privilege
switching and a separately retained exact-image audit/SBOM. OCR uses external
Poppler and Tesseract executables only in the explicitly enabled worker image.

The direct `google-genai==2.23.0` upgrade retains SDK HTTP retries at one physical
attempt; the application remains the sole bounded retry owner. Offline tests
exercise the installed SDK configuration, structured schema, token usage and
transient/permanent error behavior. See the
[official SDK release](https://github.com/googleapis/python-genai/releases/tag/v2.23.0)
and [SDK configuration reference](https://googleapis.github.io/python-genai/).
The direct server/auth extras remain declared in the `.in` inputs. Windows lock
generation evaluates their platform markers, omits Linux-only `uvloop` and keeps
the portable standard-server dependencies. Locks strip extras while retaining
explicit resolved packages and hashes.

Local-support model files are runtime artifacts, not Python packages or source
assets. `scripts/install_local_support_models.py` pins immutable upstream
revisions, exact sizes and SHA-256 digests for the Apache-2.0
`cross-encoder/nli-deberta-v3-xsmall` NLI graph/tokenizer and the CC-BY-4.0
`onnx-community/tinyroberta-squad2-ONNX` QA graph/tokenizer. The installer
refuses an unknown existing bundle; the worker verifies all digests again,
rejects symlinks and runs offline. Review both model licenses and the deployment
audience before redistribution. The approximately 181.7 MB verified bundle is
ignored by Git and mounted read-only at runtime.

The frontend uses React and Redux Toolkit for study-session state. Radix
packages support the shared UI controls. Build dependencies include Vite,
Tailwind, TypeScript, and ESLint. Playwright and axe run the maintained browser
and accessibility checks; install the pinned Chromium runtime with
`npx playwright install chromium` before `npm run check` on a new host.

Upgrade coupled frontend peers together: ESLint and `@eslint/js` use major 10;
Vite 8 pairs with React plugin 6 and a Tailwind Vite plugin that supports Vite 8.
Vitest and `@vitest/coverage-v8` must share the exact version (currently 5.0.0).
Regenerate the lock with the declared npm 11.19.1, which the Docker builder also
installs, and verify a clean `npm ci`, the complete frontend gate and the image
runtime smoke. Resolve incompatible peers instead of using forced installs or
disabling lint rules, coverage or browser checks.

Dependabot checks monthly and opens at most one routine version-update pull
request per ecosystem. Routine npm, Python and Docker minor/patch updates are
grouped into ecosystem batches; GitHub Actions updates are grouped together.
Automatic npm/pip/Docker major-version PRs are ignored, and Docker's Python
image stays on the reviewed 3.11 line. Runtime/toolchain line changes need an
explicit planned upgrade with compatibility research, lock regeneration and
the full applicable gate. Security updates remain eligible and are grouped
separately for npm, Python and Actions. Operators may open a focused major-
upgrade PR when the project chooses to expand support; closing a generated PR
does not establish support. Pip updates must still be regenerated with the
repository's Windows lock script before merge.

Normal tests use injected providers and fixtures. The live AI evaluation is
separately opted in with `RUN_LIVE_AI_TESTS=1` and configured provider
credentials, and may consume quota. See [AI_EVALUATION.md](AI_EVALUATION.md).
