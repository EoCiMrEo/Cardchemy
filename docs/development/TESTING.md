# Maintained test commands

Use the backend development environment installed from
`backend/requirements-dev.txt` with `--require-hashes`, and the supported
Node/npm environment installed with `npm ci`. Runtime versions are maintained
in [Runtimes](RUNTIMES.md). Run commands from repository root unless noted.
Normal tests inject settings, suppress root `.env`, use synthetic material and
spend no provider quota. Keep coverage/bundle/security/accessibility thresholds.

## Routine and explicitly gated suites

| Suite | Authoritative command | Required setup and expected gating |
| --- | --- | --- |
| Backend offline | `python -m pytest -q` from `backend` | Core test configuration is injected; PostgreSQL and Mailpit cases skip without their dedicated process values; live AI is deselected. |
| PostgreSQL and migration chain | `python scripts/test_services.py postgres` | Docker running. Creates a randomly addressed loopback PostgreSQL container and a disposable `regression_test` database, waits for an authenticated TCP query, migrates/checks heads and drift, rehearses downgrade to base/re-upgrade on the empty schema, then tests constraints/transactions/races including Knowledge choice and source-only Ask results. Prints only allowlisted numeric Lane 4 ablation results. |
| Database artifact and legacy recovery | `python scripts/test_database_artifact.py`, `python scripts/test_database_volume_upgrade.py`, `python scripts/test_pgvector_restore.py` | Docker running. Build/verify the reviewed PG16/pgvector recipe; scan exact immutable bytes and SBOM; refuse a legacy volume unchanged; logically restore synthetic prior-head records into a separate ICU target; verify vector infrastructure. Reports are ignored artifacts; no operator data. |
| Mailpit request/delivery | `python scripts/test_services.py mailpit` | Docker running. Creates disposable PostgreSQL and Mailpit containers; verifies request/outbox/SMTP capture, invitation/password semantics and delivery retry. No production relay. |
| Local encrypted SMTP/recovery | `python scripts/test_smtp_tls.py` | Backend development Python and Docker. Actual authenticated STARTTLS/implicit-TLS delivery, certificate/hostname rejection, durable retry and guarded operator recovery on disposable local capture. See [SMTP verification](../mail-server/SMTP-VERIFICATION.md). Required email CI. |
| Clean production installation/restore | `python scripts/test_production_rehearsal.py --evidence /private/path/result.json` | Clean committed checkout on Linux/amd64 with Docker Compose/OpenSSL. Fresh clone, generated settings, production profile, trusted loopback HTTPS, current-head backup and restore into a separate empty volume, upgrade and recovered application checks. Also manually dispatch [production rehearsal](../operations/PRODUCTION_REHEARSAL.md) on protected main. |
| Frontend offline browser/components and build | `npm run check` from `frontend` | Typecheck, test typecheck, lint, unit/component tests, production build and maintained browser regressions, including reload-safe duplicate-choice dialog behavior. The separately configured password-reset live case remains gated. |
| Full real application browser journey | `python scripts/test_journey.py` | Docker and installed Playwright Chromium. Starts a fresh migrated database, real API plus generation/index/source-only Ask/email workers and browser frontend; uses deterministic generation/embedding providers with no provider SDK/network request. Proves exact Knowledge references/page opening and no-match without assistant answers. |
| Release metadata/workflow contracts | `python scripts/check_release.py --version 0.2.0` and `python scripts/check_ci.py` | Maintained source/templates only. Remote preflight, signatures and publication require the separate [release procedure](../ci-cd/RELEASING.md). |
| Explicit live AI evaluation | `RUN_LIVE_AI_TESTS=1 python -m pytest -q -m ai_live tests/integration/test_live_ai_pipeline.py` from `backend` | Explicitly inject enabled provider/model/key and reviewed prices as described below. One native Gemini request, two cards, no retries/refills, 8,192 input/2,048 output tokens, USD 0.02 maximum estimated cost. Never runs in normal CI. |
| Explicit live source-only RAG smoke | `RUN_LIVE_RAG_TESTS=1 RAG_LIVE_EVAL_AUTHORIZED=I_ACCEPT_EMBEDDING_CHARGES_SOURCE_ONLY python -m pytest -q -m ai_live tests/integration/test_live_rag_evaluation.py::test_live_rag_embedding_and_source_selection_with_hard_bounds` from `backend` (shell-specific assignments) | Separate endpoint/model/price/call/token/time/cost approval required. One Embedding 001 current-question request, zero retries, at most 512 input tokens, 30 seconds/call, 45 seconds total and USD 0.001 conservative admission using a USD 0.20/million price floor. Zero answer/verifier calls. Authored source-selector smoke is not a private retrieval-quality gate. |
| Private 20-card source evaluation | `venv/Scripts/python.exe scripts/evaluate_private_generation.py` from `backend`, or inside the configured generation worker | Separately approved, one-shot read-only current published-source selection. Every approved endpoint/model/price/call/token/time/cost field must be supplied as a process-only value; up to 16 physical calls, 120,000 input/48,000 output tokens, 30 seconds/call, 8 minutes total and USD 0.18 estimated admission. No set/cards are written. See [AI evaluation](../ai/AI_EVALUATION.md#prompt-and-replay-measurement). |

For the published sparse whole-source control, run
`backend/venv/Scripts/python.exe scripts/test_sparse_generation_control.py`
from root with Docker running. It uses an authored whole one-fact PDF,
deterministic providers and guarded disposable PostgreSQL/browser resources to
prove target20 â†’ pending1 â†’ exact-one persistence/publication without another
provider call. It is not live Gemini sparse-source yield.

Context changes use `python scripts/check_context.py`; CI/workflow changes also
use `python scripts/check_ci.py`. Runtime/image/security changes use
`python scripts/check_runtime_artifacts.py`, `python scripts/check_images.py`
and `python scripts/test_security.py` with their documented Docker prerequisites.

Install Chromium once from `frontend` using `npx playwright install chromium`
(Linux CI: `npx playwright install --with-deps chromium`). On a constrained
host `npm run check -- --workers=2` runs the same full frontend gate with
bounded browser concurrency; it changes no required threshold.

Current source-only Ask tests cover issued-ID/schema and PNG bounds, immutable
literal-subject admission, canonical-page offsets, current SQL access/revision/
space, provider-stage limits, unknown cost, no answer/verifier/retry, whole-bundle
redaction and default-off installation flags. Generation tests cover strict
grounding/four-option/provenance rules, adaptive bounded allocation, encrypted
candidate storage, exact smaller-target choice, expiry/cancel/idempotency and
stale-worker fencing. The full PostgreSQL harness verifies current heads/drift,
base-to-head and disposable downgrade/re-upgrade, transaction/race constraints
and deletion semantics. Never downgrade operator data for verification.

The browser regressions cover operation-race cleanup, reload-safe duplicate
and smaller-card choices, durable answer save, cost-aware manual Retry, typed
source/no-match/clarification/provider-failure outcomes, PDF ranges/fallback,
mobile keyboard/focus/dialog/live-region behavior. Spoken assistive-technology
release checks follow [accessibility](../ui/ACCESSIBILITY.md) and remain human
evidence separate from automated tests.

## Harness isolation and live evaluation

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
including independent Knowledge capture/index/review/publication. An invited
student enrolled in two Subjects submits one related question, opens its exact
source and original PDF page, and submits an unrelated question that completes as `no_match`.
Cross-Subject history access returns 404. Final PostgreSQL queries prove exactly
two user messages, two completed source-only jobs with one embedding each,
zero assistant messages or answer identities, one exact source reference, four
embedding/retrieval stage records, study receipts/progress, delivered invitation
and no retained temporary job source. RAG-on capture retains one independently
encrypted Knowledge PDF archive/block; its synthetic key is isolated from the
temporary generation-source key. The source-only policy override exists only in the
guarded test API/worker entry points and requires a loopback `journey_test`
database, test environment, disabled answer lane and deterministic credential.
The deterministic providers exist only
in `backend/tests/support/` and are injected by the guarded
test entry point. Screenshot/video/trace capture is disabled for this generated-
credential journey.

`PASSWORD_RESET_LIVE_*` values are only for the dedicated password-reset
browser case. Its seed helper refuses any database except
`password_reset_browser_test` and requires disposable
`password-reset-browser-*@example.com` accounts. The complete journey command
uses its own automatically generated accounts and needs no manual credentials.

The live flashcard smoke evaluation admits only `FLASHCARD_AI_PROVIDER=gemini`,
uses Google's official endpoint with no base-URL setting, and requires
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
deterministic journey. Consult [AI evaluation](../ai/AI_EVALUATION.md) for the authored
corpus and release thresholds; no offline pass proves a current remote model's
behavior.

The former live answer harness is retired. Its earlier two-request/local-support
sample on 2026-09-23 remains historical evidence only;
[RAG evaluation](../ai/RAG_EVALUATION.md#live-deployment-model-boundary) records its
limits. The maintained live RAG smoke uses fresh source-only authorization,
one current-question embedding and authored source selection, with zero
answer/verifier calls. It does not measure private retrieval or displayed-window
usefulness and does not enable the installation. An incomplete or failed
provider attempt has unknown prior cost and must never be silently replayed.

## Operational and privacy contracts

The offline suite retains historical Ask output/quote/support tests and now
needs strict source-only result, page-read, prompt-injection and every private
thread/job/source HTTP contract, plus structured-log/exception redaction, concurrent
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
