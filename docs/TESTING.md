# Maintained test commands

Use the backend Python 3.13 development environment installed from
`backend/requirements-dev.txt` with `--require-hashes`, and the frontend Node
24/npm 11 environment installed with `npm ci`. Run commands below from the
repository root unless a working directory is specified.

| Suite | Authoritative command | Required setup and expected gating |
| --- | --- | --- |
| Backend offline | `python -m pytest -q` from `backend` | Core test configuration is injected; PostgreSQL and Mailpit cases skip without their dedicated process values; live AI is deselected. |
| PostgreSQL and migration chain | `python scripts/test_services.py postgres` | Docker running. Creates a randomly addressed loopback PostgreSQL container and a disposable `regression_test` database, waits for an authenticated TCP query on that database, migrates/checks heads and drift, tests constraints/transactions/races, then rehearses downgrade to base/re-upgrade. |
| Mailpit request/delivery | `python scripts/test_services.py mailpit` | Docker running. Creates disposable PostgreSQL and Mailpit containers; verifies request/outbox/SMTP capture, invitation/password semantics and delivery retry. No production relay. |
| Local encrypted SMTP/recovery | `python scripts/test_smtp_tls.py` | Backend development Python and Docker. Actual authenticated STARTTLS/implicit-TLS delivery, certificate/hostname rejection, durable retry and guarded operator recovery on disposable local capture. See [SMTP verification](SMTP-VERIFICATION.md). Required email CI. |
| Clean production installation/restore | `python scripts/test_production_rehearsal.py --evidence /private/path/result.json` | Clean committed checkout on Linux/amd64 with Docker Compose/OpenSSL. Fresh clone, generated settings, production profile, trusted loopback HTTPS, current-head backup and restore into a separate empty volume, upgrade and recovered application checks. Also manually dispatch [production rehearsal](PRODUCTION_REHEARSAL.md) on protected main. |
| Frontend offline browser/components and build | `npm run check` from `frontend` | Typecheck, test typecheck, lint, unit/component tests, production build and maintained browser regressions. The separately configured password-reset live case remains gated. |
| Full real application browser journey | `python scripts/test_journey.py` | Docker and installed Playwright Chromium. Starts a fresh migrated database, real API/generation/email workers and browser frontend; uses a private deterministic AI provider with no provider SDK/network request. |
| Release metadata/workflow contracts | `python scripts/check_release.py --version 0.1.0` and `python scripts/check_ci.py` | Maintained source/templates only. Remote preflight, signatures and publication require the separate [release procedure](RELEASING.md). |
| Explicit live AI evaluation | `RUN_LIVE_AI_TESTS=1 python -m pytest -q -m ai_live tests/integration/test_live_ai_pipeline.py` from `backend` | Explicitly inject enabled provider/model/key and reviewed prices as described below. One request, two cards, no retries/refills, 8,192 input/2,048 output tokens, USD 0.02 maximum estimated cost. Never runs in normal CI. |

Install the browser once from `frontend` using
`npx playwright install chromium` (Linux CI: `npx playwright install --with-deps chromium`).

The frontend check and browser runner inject API_PORT=8000 and VITE_API_URL=/api
for all stages; the public loader then avoids reading root .env. Individual
development/build commands retain the normal root configuration contract.

The service/journey harnesses ignore operator application environment values
and root `.env`, generate credentials in private temporary storage, bind
services to loopback with random ports, and remove their containers, data,
processes and credentials even on failure. Cleanup claims require successful
Docker inventories confirming generated services are absent. Service/browser
failures emit safe test identities or fixed diagnostics; raw traces may contain
generated credentials and are withheld. Host-run PostgreSQL fixtures require
`postgresql+asyncpg` on loopback and a database named `*_test`; controlled CI
service hosts are allowed explicitly. They verify the connected database
identity and the dynamically resolved Alembic head before any write/cleanup.

The full journey exercises operator instructor creation, browser subject
creation, real PDF upload/extraction, durable generation/grounding, instructor
review/approval/publication, emailed invitation capture, student registration
and sign-in, answers and displayed progress. A final PostgreSQL query proves
two users, one enrollment/set/job, two approved grounded cards, two correct
progress rows and durable answer receipts, one delivered invitation, and no
retained PDF source. Its provider exists only in `backend/tests/support/` and
is injected by the guarded test entry point. Screenshot/video/trace capture is
disabled for this generated-credential journey.

`PASSWORD_RESET_LIVE_*` values are only for the dedicated password-reset
browser case. Its seed helper refuses any database except
`password_reset_browser_test` and requires disposable
`password-reset-browser-*@example.com` accounts. The complete journey command
uses its own automatically generated accounts and needs no manual credentials.

The live smoke evaluation admits only `AI_PROVIDER=openai_compatible`,
`AI_BASE_URL=https://api.openai.com/v1`, and
`AI_MODEL=gpt-4o-mini-2024-07-18`. Supply `AI_PROVIDER_ENABLED=true`, `AI_API_KEY`,
and reviewed `AI_INPUT_COST_PER_MILLION_USD` / `AI_OUTPUT_COST_PER_MILLION_USD`
through the process environment, using shell-specific assignment syntax.
Prices must be at least USD 0.15 / 0.60 per million tokens, respectively,
reviewed against the [official model pricing](https://developers.openai.com/api/docs/models/gpt-4o-mini)
before each run. Admission reserves the entire input/output token envelope,
counts UTF-8 prompt and actual closed-schema bytes plus framing headroom, and
rejects unknown endpoints, moving aliases, reasoning models, underpriced
estimates, or a second call. Provider-reported usage is mandatory afterward;
missing usage or a reported overrun fails evaluation without admitting a
retry. The server output cap and completion usage cover this non-reasoning
model's output. Other models require
a separately reviewed bound that accounts for billable thought tokens. The
USD 0.02 limit is a token-price estimate; taxes and future provider pricing are
outside that estimate, so also apply provider account spending controls.

Paid-provider results are distinct from offline provider wire mocks and the
deterministic journey. Consult [AI evaluation](AI_EVALUATION.md) for the authored
corpus and release thresholds; no offline pass proves a current remote model's
behavior.

## Operational and privacy contracts

The offline suite includes structured-log/exception redaction, concurrent
correlation isolation, safe job metrics, fresh/stale/draining worker probes,
disabled/explicit numeric telemetry, private exclusive export permissions,
operator deletion flags and sanitized startup failures. PostgreSQL cases verify
transactional audit rollback/role triggers, provisioning races, snapshot exports,
account cascades, bounded retention and protection of retry receipts/sources.
These fixtures use only guarded disposable databases and synthetic content.

Built images use the probes in [runtime support](RUNTIMES.md). The frontend
probe also checks that successful requests and rejected static POSTs keep
private URL queries and body sentinels out of Nginx logs. This proves the shipped
edge's behavior, not an operator's separate proxy or log collector policy.

On hosts with limited browser capacity, `npm run check -- --workers=2` runs the
same complete frontend gate with bounded Chromium concurrency; it does not
change coverage, bundle, accessibility or test thresholds.
