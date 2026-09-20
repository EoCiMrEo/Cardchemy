# Maintained test commands

Use the backend Python 3.13 development environment installed from
`backend/requirements-dev.txt` with `--require-hashes`, and the frontend Node
24/npm 11 environment installed with `npm ci`. Run commands below from the
repository root unless a working directory is specified.

| Suite | Authoritative command | Required setup and expected gating |
| --- | --- | --- |
| Backend offline | `python -m pytest -q` from `backend` | Core test configuration is injected; PostgreSQL and Mailpit cases skip without their dedicated process values; live AI is deselected. |
| PostgreSQL and migration chain | `python scripts/test_services.py postgres` | Docker running. Creates a randomly addressed loopback PostgreSQL container and a disposable `regression_test` database, waits for an authenticated TCP query on that database, migrates/checks heads and drift, tests constraints/transactions/races, then rehearses downgrade to base/re-upgrade. |
| Database artifact and legacy recovery | `python scripts/test_database_artifact.py`, `python scripts/test_database_volume_upgrade.py`, `python scripts/test_pgvector_restore.py` | Docker running. Build/verify the reviewed PG16/pgvector recipe; scan exact immutable bytes and SBOM; refuse a legacy volume unchanged; logically restore synthetic prior-head records into a separate ICU target; verify vector infrastructure. Reports are ignored artifacts; no operator data. |
| Mailpit request/delivery | `python scripts/test_services.py mailpit` | Docker running. Creates disposable PostgreSQL and Mailpit containers; verifies request/outbox/SMTP capture, invitation/password semantics and delivery retry. No production relay. |
| Local encrypted SMTP/recovery | `python scripts/test_smtp_tls.py` | Backend development Python and Docker. Actual authenticated STARTTLS/implicit-TLS delivery, certificate/hostname rejection, durable retry and guarded operator recovery on disposable local capture. See [SMTP verification](SMTP-VERIFICATION.md). Required email CI. |
| Clean production installation/restore | `python scripts/test_production_rehearsal.py --evidence /private/path/result.json` | Clean committed checkout on Linux/amd64 with Docker Compose/OpenSSL. Fresh clone, generated settings, production profile, trusted loopback HTTPS, current-head backup and restore into a separate empty volume, upgrade and recovered application checks. Also manually dispatch [production rehearsal](PRODUCTION_REHEARSAL.md) on protected main. |
| Frontend offline browser/components and build | `npm run check` from `frontend` | Typecheck, test typecheck, lint, unit/component tests, production build and maintained browser regressions. The separately configured password-reset live case remains gated. |
| Full real application browser journey | `python scripts/test_journey.py` | Docker and installed Playwright Chromium. Starts a fresh migrated database, real API plus generation/index/answer/email workers and browser frontend; uses private deterministic generation/embedding/answer providers with no provider SDK/network request. Proves independent Knowledge review/publication before Ask AI. |
| Release metadata/workflow contracts | `python scripts/check_release.py --version 0.1.0` and `python scripts/check_ci.py` | Maintained source/templates only. Remote preflight, signatures and publication require the separate [release procedure](RELEASING.md). |
| Explicit live AI evaluation | `RUN_LIVE_AI_TESTS=1 python -m pytest -q -m ai_live tests/integration/test_live_ai_pipeline.py` from `backend` | Explicitly inject enabled provider/model/key and reviewed prices as described below. One native Gemini request, two cards, no retries/refills, 8,192 input/2,048 output tokens, USD 0.02 maximum estimated cost. Never runs in normal CI. |
| Explicit live RAG evaluation | `RUN_LIVE_RAG_TESTS=1 RAG_LIVE_EVAL_AUTHORIZED=I_ACCEPT_PROVIDER_CHARGES python -m pytest -q -m ai_live tests/integration/test_live_rag_evaluation.py` from `backend` | Requires native Gemini, the official endpoint identity, pinned `gemini-3.5-flash`/`gemini-embedding-001` snapshots, role-specific keys/quota buckets and refreshed price floors. At most one query embedding, one answer and one support call; zero retries, one-call concurrency, 12,000 total input/2,048 answer-output tokens, 60 seconds and USD 0.04. Never runs in normal CI. |

Install the browser once from `frontend` using
`npx playwright install chromium` (Linux CI: `npx playwright install --with-deps chromium`).

The frontend check and browser runner inject API_PORT=8000 and VITE_API_URL=/api
for all stages; the public loader then avoids reading root .env. Individual
development/build commands retain the normal root configuration contract.
Component regressions include aborted and delayed Subject/session responses,
immediate loading on navigation, and generation jobs staying in their Subject
scope after poll failures or late mutation responses.

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
The PostgreSQL suite additionally restores a populated synthetic 1,536-vector
Subject Knowledge document into a separate guarded child database, then checks
publication eligibility, page numbering, indexes, capacity counters, linked
cards and deletion effects. It also runs the capture/index/cutover/exact-hybrid
pipeline with deterministic local vectors, including authorization, corpus/
space fences, partial batches and dead leases. Phase 17 cases also exercise
owner-private API/service access, concurrent idempotency/quota admission, query
embedding, strict grounded answers, semantic support, atomic exact citations,
G2 unpublish redaction, access revocation, dead leases and stale claim fencing.
Phase 19 adds the v2 authored corpus, actual exact pgvector plus `simple` FTS
recall/ranking/latency/throughput gates, empty retrieval, overlap diversity,
forbidden-source exposure, unsupported/irrelevant citation rejection and an
explicit assertion that no ANN index ships.
This is local recovery proof,
not an operator database restore or live embedding-quality evaluation.

The full journey runs two isolated disposable application scenarios. With RAG
disabled, an ordinary real-PDF flashcard generation/review/publication proves
normal source cleanup while Knowledge, embedding, thread and answer records and
their provider workers remain absent. The RAG-enabled scenario exercises
operator instructor creation, browser subject creation, real PDF upload/
extraction, durable flashcard generation/grounding and card/set publication,
including the negative proof that flashcard publication alone leaves Ask AI
unavailable. The same instructor reviews and publishes Knowledge independently,
after which an invited student enrolled in two real Subjects receives one
deterministic grounded answer with a current page citation, completes study and
gets a 404 when attempting to read that thread through the other Subject. Final
PostgreSQL queries prove the scenario-specific users/enrollments/sets/cards,
Knowledge content/index publication, private conversation/job/message/source,
answer receipts/progress, delivered invitation and no retained PDF source. The
providers exist only in `backend/tests/support/` and are injected by the guarded
test entry point. Screenshot/video/trace capture is disabled for this generated-
credential journey.

`PASSWORD_RESET_LIVE_*` values are only for the dedicated password-reset
browser case. Its seed helper refuses any database except
`password_reset_browser_test` and requires disposable
`password-reset-browser-*@example.com` accounts. The complete journey command
uses its own automatically generated accounts and needs no manual credentials.

The live smoke evaluation admits only `FLASHCARD_AI_PROVIDER=gemini`, an empty
`FLASHCARD_AI_BASE_URL` (the native adapter uses Google's official endpoint), and
`FLASHCARD_AI_MODEL=gemini-3.5-flash-lite` with
`FLASHCARD_AI_THINKING_LEVEL=minimal`. Supply `FLASHCARD_AI_PROVIDER_ENABLED=true`, `FLASHCARD_AI_API_KEY`,
an explicit `FLASHCARD_AI_QUOTA_BUCKET` with a separately divided worker/replica quota,
and reviewed `FLASHCARD_AI_INPUT_COST_PER_MILLION_USD` / `FLASHCARD_AI_OUTPUT_COST_PER_MILLION_USD`
through the process environment, using shell-specific assignment syntax.
Prices must be at least USD 0.30 / 2.50 per million tokens, respectively,
reviewed against the [official Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing)
before each run. Admission reserves the entire input/output token envelope,
counts UTF-8 prompt and actual closed-schema bytes plus framing headroom, and
rejects custom endpoints, moving aliases, other models/providers, underpriced
estimates, or a second call. Provider-reported usage is mandatory afterward;
missing usage or a reported overrun fails evaluation without admitting a
retry. The provider-reported output usage includes billable generated tokens;
other models require a separately reviewed bound for their token semantics. The
USD 0.02 limit is a token-price estimate; taxes and future provider pricing are
outside that estimate, so also apply provider account spending controls.

Paid-provider results are distinct from offline provider wire mocks and the
deterministic journey. Consult [AI evaluation](AI_EVALUATION.md) for the authored
corpus and release thresholds; no offline pass proves a current remote model's
behavior.

The live RAG harness is a separate authorization. In addition to both opt-in
flags in the table, inject `RAG_ENABLED=true`,
`RAG_AI_PROVIDER_ENABLED=true`, `RAG_EMBEDDING_PROVIDER_ENABLED=true`, native
`gemini` providers, role-specific API keys and explicit answer/embedding quota
buckets. Both base URLs remain empty; the adapters use the canonical Google
endpoint identity. The guard accepts only `gemini-3.5-flash` and
`gemini-embedding-001` at 1,536 dimensions with the fixed retrieval task modes.
The answer profile must pin `RAG_AI_THINKING_LEVEL=minimal`.
Before every authorized run, refresh the configured USD 1.50 input / USD 9.00
output / USD 0.15 embedding per-million-token price floors against official
pricing and retain provider-account spending controls. Reported Gemini thinking
tokens count as output; embedding tokens are a conservative local estimate.
The harness forces provider retries to zero and concurrency to one. Neither
setting both provider switches nor passing the offline v2 corpus authorizes
this paid test.

## Operational and privacy contracts

The offline suite includes strict Ask AI output/quote/support/prompt-injection
contracts and every private thread/job/source HTTP endpoint, plus structured-log/exception redaction, concurrent
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
