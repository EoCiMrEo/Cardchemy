# Configuration

The supported file-based configuration is the repository-root .env, using the
repository-root .env.example as its only template. Backend and frontend
directories do not need their own .env files. The bootstrap command creates the
root file with independent random database, JWT, and source-encryption secrets
and refuses to overwrite an existing file:

    python scripts/bootstrap_env.py

Keep .env private and out of source control. For an existing installation, make
an access-controlled backup, edit the existing file in place, validate the
effective configuration, and recreate only the affected processes. Do not
rerun bootstrap over an installation, replace its secrets with template blanks,
or delete its database volume to apply a setting.

An explicitly set nonempty process environment value takes precedence over the
root .env; the file takes precedence over validated application defaults.
Backend settings ignore empty values: an empty process value does not override
a nonempty root value, and an empty root value uses the validated default. Compose interpolation also uses defaults for empty values where the
compose file specifies them, while required values cause configuration to fail.
Tests must inject their own settings with _env_file=None and use disposable
services; normal test runs must not consume the operator's real root .env.

## Connection and delivery modes

In the base Compose stack, PostgreSQL is named db on the internal network. The
API and workers receive a DATABASE_URL built from POSTGRES_DB, POSTGRES_USER,
and POSTGRES_PASSWORD with db:5432. This process value takes precedence over
the optional root DATABASE_URL. The base stack publishes neither PostgreSQL
nor the API; only the frontend and Mailpit UI bind to host loopback.

For native Python processes, leave DATABASE_URL empty to derive a localhost
connection from those same POSTGRES_* settings and POSTGRES_PORT. Start
PostgreSQL with the development Compose override, or use an existing local
PostgreSQL 16 server. Set DATABASE_URL explicitly only for a separately
managed database. The development override publishes PostgreSQL, API, and
Mailpit SMTP on host loopback for native tooling. Its command is in
[DEPLOYMENT.md](DEPLOYMENT.md).

Vite reads the root .env when its public settings are not fully injected.
Explicit API_PORT and VITE_API_URL values avoid reading that file, as used by
`npm run check` and the browser runner. With VITE_API_URL=/api, its development proxy sends
requests to the host API_PORT, strips /api, and rewrites the refresh-cookie
path. The built Compose frontend uses Nginx for the same-origin /api route;
VITE_API_URL is a public value embedded at build time. Only VITE_* settings
may be exposed to the browser. Provider keys are injected only into the
generation worker, SMTP credentials only into the email worker, and the API
receives the non-secret generation enablement setting.

The local email worker uses mailpit:1025 inside Compose, with both SMTP TLS
flags false. For native email-worker development, use localhost:1025 through
the development override. Production needs a real relay and sender, its
actual SMTP port, and exactly one encrypted mode. Mailpit is excluded from
the production profile; see [EMAIL_DELIVERY.md](EMAIL_DELIVERY.md).

## Applying changes

### Existing installations and Cardchemy defaults

The v0.1.0 template names new installations `cardchemy`. Preserve an existing
Compose project name and `POSTGRES_DB` (previous default: `flashcard_gen`);
changing either may select a different
volume/database. Keep the existing root `.env` and installation secrets.
Do not copy the new `COMPOSE_PROJECT_NAME` into an existing deployment unless
it matches the project already owning its volumes. Check the existing
container/volume Compose labels privately before changing that identity.

If previously omitted, explicitly retain `JWT_ISSUER=flashcard-generator-api`,
`JWT_AUDIENCE=flashcard-generator-web` and `REFRESH_COOKIE_NAME=flashcard_refresh` when
upgrading an older installation that used those defaults. New defaults are
`cardchemy-api`, `cardchemy-web` and `cardchemy_refresh`. A coordinated switch
requires users to sign in again and old refresh cookies to expire/be removed.
`APP_NAME=Cardchemy` changes display/API metadata without renaming stored data.

After editing root .env, run `python scripts/check_config_migration.py` and then
docker compose config --quiet (or the corresponding
development/production override command) before recreating containers. Compose
substitutes settings when containers are created; a plain process restart does
not refresh values already injected into an existing container. Use
docker compose up -d --force-recreate for affected services. Native Python
and Vite processes need a restart to reread the file.

VITE_API_URL changes require rebuilding the frontend image and recreating its
container. PDF_OCR_ENABLED changes the backend build and require rebuilding
the backend/worker image before recreation. Other backend and worker settings
usually require container recreation without an image rebuild. Updating
POSTGRES_PASSWORD on an existing database requires a coordinated PostgreSQL
credential change; editing .env alone does not rotate the database role
password. Rotating SECRET_KEY revokes JWT validity, and rotating
GENERATION_SOURCE_ENCRYPTION_KEY makes queued or retained encrypted PDFs
unreadable until they are drained or removed by the normal workflow.

## Basic settings

The values below are the template defaults. A range is shown where the
application validates it; otherwise the type or required format is stated.
The consumer column identifies where a value goes. All port settings are TCP
ports from 1 to 65535. Do not publish database, API, or Mailpit ports beyond
trusted loopback without a separate network-security design.

| Setting and template default | Purpose, bounds, and required condition | Consumer |
| --- | --- | --- |
| COMPOSE_PROJECT_NAME=cardchemy | Installation namespace for Compose networks/volumes. Keep an existing installation's namespace during upgrades; changing it selects different resources. | Compose |
| APP_PORT=8080 | Host loopback port for the built frontend. | Compose |
| API_PORT=8000 | Host API port in the development override; Vite's /api proxy target. | Compose, Vite |
| POSTGRES_PORT=5432 | Host database port in the development override; native derived URL. | Compose, backend |
| MAILPIT_UI_PORT=8025; MAILPIT_SMTP_PORT=1025 | Host loopback UI and optional development SMTP ports. SMTP remains internal in the base stack. | Compose |
| POSTGRES_DB=cardchemy; POSTGRES_USER=admin | Database and login identifiers, letters/digits/underscore and leading letter or underscore. | Compose, native backend |
| POSTGRES_PASSWORD=empty | Required generated database password. Empty is invalid for Compose startup and for a native derived URL. Keep secret. | Compose, native backend |
| DATABASE_URL=empty | Native backend derives localhost URL when empty; explicit value selects a separately managed database. Compose injects its internal db URL regardless. This URL can contain a password and must stay private. | Native backend; Compose injection |
| APP_NAME=Cardchemy; APP_VERSION=0.1.0 | Display identity and image/version metadata. Name is 1–128 characters. | API, Compose |
| ENVIRONMENT=development | development, test, or production. Production enforces stronger cookie, origin, SMTP, and secret checks. | API, workers, Compose |
| DEBUG=false; API_DOCS_ENABLED=empty | Debug is disabled by default. Empty docs flag uses validated environment-specific behavior; limit public API docs intentionally. | API |
| API_ROOT_PATH=empty | Native API path prefix, empty by default; Compose injects /api for its edge proxy. | API, Compose |
| FRONTEND_BASE_URL=empty; CORS_ORIGINS=empty | Empty uses localhost development defaults natively and Compose's local frontend origin in containers. Set HTTPS values in production. CORS entries must be exact origins without paths or wildcards; FRONTEND_BASE_URL cannot contain credentials, query, or fragment and supplies email-link origin. | API, email worker, Compose |
| VITE_API_URL=/api | Public browser API base; same-origin /api is the supported Compose route. Must be an absolute HTTP(S) URL or root-relative path. Rebuild frontend image after changing it. | Vite build, browser |
| FORWARDED_ALLOW_IPS=empty | Compose's private API uses a proxy-trust fallback; narrow to exact trusted proxy addresses if changing the network exposure. | Compose/Uvicorn |
| WORKER_SHUTDOWN_GRACE_SECONDS=30 | Drain time in seconds, 0–7200; coordinate with Compose stop grace period. | Workers |

## Diagnostics, telemetry and metadata retention

These settings reach the API and both workers through the core Compose
environment. They contain no provider/SMTP credentials. See
[observability](OBSERVABILITY.md) for fields, metric limits and health
semantics, and [privacy](PRIVACY.md) for lifecycle/commands. Changes require
process restart/container recreation. Cleanup is operator-run, dry-run by
default; stdout/proxy/backup/provider expiry is separately configured.

| Setting and default | Bounds and behavior |
| --- | --- |
| `LOG_LEVEL=INFO` | DEBUG, INFO, WARNING, ERROR or CRITICAL; redaction applies at every level. SQL echo stays disabled. |
| `REQUEST_RETENTION_DAYS=7` | 1–365 days; database request metadata eligibility/window. |
| `GENERATION_JOB_RETENTION_DAYS=30` | 1–3650 days; terminal source-free job history; result sets survive. |
| `DATABASE_METADATA_RETENTION_DAYS=30` | 1–3650 days; grace for expired auth/reset/invite, stale rate buckets and past quota windows. Does not expire accounts, content, progress or study receipts. |
| `AUDIT_RETENTION_DAYS=90` | 1–3650 days; fixed-field privileged audit history. |
| `RETENTION_BATCH_SIZE=500` | 1–10000 rows per metadata category per cleanup command; apply skips locked candidates. |
| `WORKER_HEALTH_STALE_SECONDS=60` | 10–3600 seconds; must cover at least twice the greater worker poll interval (and at least 10 seconds). |
| `TELEMETRY_ENABLED=false` | Optional aggregate reporting enablement; enabling alone sends nothing. |
| `TELEMETRY_ENDPOINT=empty` | Operator-owned HTTPS collector, no embedded credentials/query/fragment; required when enabled. Never exposed to the browser. |
| `TELEMETRY_TIMEOUT_SECONDS=5` | 1–30 seconds; one explicit `report-telemetry` call, no automatic retry or redirect. |

## Authentication and session settings

These settings are consumed by the API and relevant workers. Keep secrets out
of logs, image layers, and browser variables. Production requires secure
cookies, trusted origins, and strong generated secret material.

| Setting and template default | Purpose, bounds, and required condition |
| --- | --- |
| SECRET_KEY=empty | Required generated JWT signing secret, at least 32 characters; rotation invalidates active sessions. |
| GENERATION_SOURCE_ENCRYPTION_KEY=empty | Required independent 32-byte URL-safe base64 key for temporary PDF ciphertext; rotation requires draining retained sources. |
| ALGORITHM=HS256 | The only supported JWT signing algorithm. |
| JWT_ISSUER=cardchemy-api; JWT_AUDIENCE=cardchemy-web | Exact token issuer and audience. Change only with a coordinated client/session rollout. |
| JWT_CLOCK_SKEW_SECONDS=30 | Token clock tolerance, 0–300 seconds. |
| ACCESS_TOKEN_EXPIRE_MINUTES=15 | Access-token lifetime, 1–60 minutes. |
| REFRESH_TOKEN_EXPIRE_DAYS=7; REFRESH_SESSION_EXPIRE_DAYS=30 | Refresh-token and server-session lifetimes, 1–30 and 1–90 days. |
| REFRESH_COOKIE_NAME=cardchemy_refresh; REFRESH_COOKIE_DOMAIN=empty | Cookie name and optional domain; empty domain makes a host-only cookie. |
| REFRESH_COOKIE_SECURE=false; REFRESH_COOKIE_SAMESITE=lax | Cookie transport and SameSite mode (lax or strict). Production requires secure transport. |
| INVITATION_MIN_HOURS=1; INVITATION_MAX_HOURS=720 | Allowed invitation TTL bounds, each 1–720 hours and minimum no greater than maximum. |
| PASSWORD_RESET_EXPIRE_MINUTES=30 | Password-reset token lifetime, 5–120 minutes. |

## PDF and generation limits

The API enforces upload/admission bounds; the generation worker enforces
extraction, AI, job, and retention bounds. Byte values are raw bytes. Raising
these limits can increase database growth, worker memory, or paid model usage.
The selected default daily per-user job limit is 20.

| Setting and template default | Purpose, bounds, and required condition |
| --- | --- |
| PDF_MAX_UPLOAD_BYTES=10485760 | Raw upload cap, 1024–104857600 bytes. |
| PDF_MAX_PAGES=100; PDF_MAX_EXTRACTED_CHARS=500000 | Page cap 1–2000; extracted-character cap 1000–10000000. |
| PDF_EXTRACTION_TIMEOUT_SECONDS=60; PDF_EXTRACTION_MEMORY_LIMIT_MB=512 | Extraction subprocess limit 5–600 seconds and 128–4096 MiB. |
| PDF_OCR_ENABLED=false | Optional OCR switch; requires rebuilding OCR-enabled worker image and installed Poppler/Tesseract. |
| PDF_OCR_LANGUAGE=eng; PDF_OCR_DPI=200; PDF_OCR_PAGE_TIMEOUT_SECONDS=30 | Tesseract language token (1–64 permitted characters); raster DPI 72–400; page timeout 5–300 seconds. |
| GENERATION_MIN_CARD_COUNT=1; GENERATION_MAX_CARD_COUNT=100 | Requested-card range, configured minimum 1–100 and maximum 1–500; minimum must not exceed maximum. |
| GENERATION_MAX_ACTIVE_JOBS_PER_USER=2; GENERATION_MAX_ACTIVE_JOBS_DEPLOYMENT=20 | Active job caps, 1–100 and 1–10000. |
| GENERATION_MAX_QUEUED_JOBS_DEPLOYMENT=100 | Queue cap, 1–100000. |
| GENERATION_DAILY_JOBS_PER_USER=20; GENERATION_DAILY_JOBS_DEPLOYMENT=1000 | UTC daily job quotas, 1–10000 and 1–1000000. |
| GENERATION_DAILY_CARDS_PER_USER=500; GENERATION_DAILY_CARDS_DEPLOYMENT=50000 | UTC daily requested-card quotas, 1–1000000 and 1–10000000. |
| GENERATION_DAILY_UPLOAD_BYTES_PER_USER=104857600; GENERATION_DAILY_UPLOAD_BYTES_DEPLOYMENT=10737418240 | UTC daily accepted-upload quotas, from 1024 bytes up to 100 GiB/user and 10 TiB/deployment. |
| GENERATION_MAX_RETAINED_SOURCE_BYTES_PER_USER=52428800; GENERATION_MAX_RETAINED_SOURCE_BYTES_DEPLOYMENT=1073741824 | Encrypted retained-source caps, from 1024 bytes up to 100 GiB/user and 10 TiB/deployment. |
| GENERATION_WORKER_CONCURRENCY=2 | Concurrent jobs per worker, 1–64. Model request concurrency is separately worker-wide. |
| GENERATION_JOB_TIMEOUT_SECONDS=600; GENERATION_LEASE_SECONDS=60 | Whole-job limit 30–7200 seconds; lease 15–600 seconds. |
| GENERATION_WORKER_POLL_SECONDS=1; GENERATION_HEARTBEAT_SECONDS=10 | Empty-queue poll 0.1–30 seconds; lease heartbeat 1–120 seconds and shorter than the lease. |
| GENERATION_MAX_ATTEMPTS=3; GENERATION_MAX_MANUAL_RETRIES=2 | Infrastructure attempt cap 1–10 and manual retry cap 0–10. Provider failures do not trigger automatic whole-job replay. |
| GENERATION_RETRY_BASE_SECONDS=2; GENERATION_RETRY_MAX_SECONDS=60 | Infrastructure backoff bounds, 0.1–300 and 1–3600 seconds. |
| GENERATION_SOURCE_RETRY_RETENTION_HOURS=24; GENERATION_UPLOAD_RESERVATION_MINUTES=15 | Retained-source window 1–168 hours; unfilled reservation window 1–120 minutes. |
| GENERATION_CLEANUP_INTERVAL_SECONDS=60 | Expiration cleanup cadence, 5–3600 seconds. |

Generation retry base cannot exceed its maximum, worker concurrency cannot
exceed the deployment active-job cap, and lease heartbeat must be shorter than
the lease. These relationships are checked at startup.

## AI provider and budget settings

The API receives `FLASHCARD_AI_PROVIDER_ENABLED` and non-secret availability
settings. Only the generation worker receives `FLASHCARD_AI_API_KEY`. Enabling a
provider can spend money; set current provider quotas and prices before doing
so. Zero cost-rate fields mean that monetary estimates are unavailable, not
that calls are free. Paid live tests stay explicitly opted in.

| Setting and template default | Purpose, bounds, and required condition |
| --- | --- |
| FLASHCARD_AI_PROVIDER_ENABLED=false; FLASHCARD_AI_PROVIDER=gemini | Generation admission switch and gemini/openai_compatible profile. Disabled allows startup without a key. |
| FLASHCARD_AI_MODEL=gemini-3.8-flash | Model identifier, 1–128 characters; verify availability with the provider. |
| FLASHCARD_AI_API_KEY=empty; FLASHCARD_AI_QUOTA_BUCKET=empty | Worker-only credential and explicit account/project quota label. An enabled worker requires both; no legacy key fallback. |
| FLASHCARD_AI_BASE_URL=empty | Required for openai_compatible; must be an HTTP(S) origin/endpoint without embedded credentials, query, or fragment. Empty is correct for native Gemini. |
| FLASHCARD_AI_ALLOW_UNSTABLE_MODEL=false | Explicit production opt-in for model names indicating preview/latest/experimental status. |
| FLASHCARD_AI_TEMPERATURE=0.2; FLASHCARD_AI_MAX_OUTPUT_TOKENS=8192; FLASHCARD_AI_CONTEXT_WINDOW_TOKENS=1048576 | Sampling 0–2; per-call output 64–131072 tokens; model context 2048–4194304 tokens. |
| FLASHCARD_AI_PROVIDER_TIMEOUT_SECONDS=90; FLASHCARD_AI_PROVIDER_MAX_RETRIES=3 | Per-call timeout 1–600 seconds; 0–3 retries after the first attempt. |
| FLASHCARD_AI_RETRY_BASE_SECONDS=3; FLASHCARD_AI_RETRY_MAX_SECONDS=30 | Provider retry delay bounds, 3–60 and 3–600 seconds; respect usable longer Retry-After hints. |
| FLASHCARD_AI_CONCURRENCY=3 | Provider calls shared across one worker process, 1–32. Multiple worker replicas need divided quotas or a distributed governor. |
| FLASHCARD_AI_REQUESTS_PER_MINUTE=5; FLASHCARD_AI_INPUT_TOKENS_PER_MINUTE=250000 | Configured provider rate tier, 1–100000 requests/minute and 1–100000000 input tokens/minute. |
| FLASHCARD_AI_RATE_LIMIT_SAFETY_PERCENT=80 | Allowed fraction of configured RPM/TPM, 1–100 percent. |
| FLASHCARD_AI_CHUNK_INPUT_TOKENS=1200; FLASHCARD_AI_CHUNK_OVERLAP_TOKENS=120 | Grounded logical chunk target 128–131072 tokens; overlap 0–32768 tokens. |
| FLASHCARD_AI_REQUEST_INPUT_TARGET_TOKENS=40000; FLASHCARD_AI_CARDS_PER_REQUEST=10 | Packed request target 2048–4000000 input tokens; 1–100 cards per call. |
| FLASHCARD_AI_SUMMARY_OUTPUT_TOKENS=1024; FLASHCARD_AI_REFILL_ROUNDS=2 | Per-summary budget 64–32768 tokens; 0–5 bounded refill rounds. |
| FLASHCARD_AI_MAX_JOB_INPUT_TOKENS=200000; FLASHCARD_AI_MAX_JOB_OUTPUT_TOKENS=262144 | Whole-job ceilings, 1024–20000000 input and 64–5000000 output tokens. |
| FLASHCARD_AI_DUPLICATE_SIMILARITY_THRESHOLD=0.88 | Near-duplicate rejection threshold, 0.5–1. |
| FLASHCARD_AI_INPUT_COST_PER_MILLION_USD=0; FLASHCARD_AI_OUTPUT_COST_PER_MILLION_USD=0 | Operator-entered USD per million tokens, 0–10000; zero disables monetary estimate. |
| FLASHCARD_AI_MAX_ESTIMATED_COST_USD=5 | Preflight per-job cost ceiling, greater than 0 and at most 100000 USD. |

Flashcard AI budget settings also have cross-field checks: chunk overlap is smaller than
the chunk, summary output fits the per-call output budget, input plus output
fits model context, a packed request fits the safety-adjusted input TPM, and
whole-job budgets cover individual calls. Input and output price rates must
both be zero or both be configured.

The [hard-rename migration guide](AI_PROFILE_MIGRATION.md) maps all former
`AI_*` settings and the removed `GEMINI_API_KEY` fallback. Run the key-name-only
`python scripts/check_config_migration.py` preflight before Compose or native
startup. Base Compose also rejects nonempty removed keys during direct config/up
interpolation. Preserve
the existing `.env`, installed secrets and generation-job provider/model
snapshots; do not regenerate them to apply the rename.

`RAG_ENABLED=false` keeps Knowledge capture/retrieval/Ask AI inactive, without
purging any stored data. `RAG_AI_PROVIDER_ENABLED` and
`RAG_EMBEDDING_PROVIDER_ENABLED` independently suspend their future worker
roles. Enabling a profile is not authorization for paid requests. The complete
profile defaults are in the one root [.env.example](../.env.example):

| Profile | Initial model and controls | Secret consumer |
| --- | --- | --- |
| `FLASHCARD_AI_*` | Existing selected text provider/model, card/summary/refill budgets, independent quota bucket/RPM/input TPM and cost ceiling | Generation worker |
| `RAG_AI_*` | `openai_compatible`, `gpt-4.1-mini-2025-04-14`, answer-only temperature/output/context/timeout/retry/rate/token/cost limits, explicit quota bucket | Future answer worker |
| `RAG_EMBEDDING_*` | `openai_compatible`, `text-embedding-3-small`, 1536 float32 cosine, `raw_text_v1`, `v1` space revision, batch/input/rate/cost limits, explicit quota bucket | Future indexing and answer workers for document/query vectors |

Each enabled role must receive only its own credentials. Sharing a provider
account requires deliberately matching quota-bucket labels and dividing actual
account/project limits across every profile and replica. Separate keys do not
multiply a provider's quota. The API/email/frontend receive no profile key.
Answer/index execution and durable space/corpus snapshots are implemented only
in their specified later phases; these configuration fields alone do not run
those processes. Initial prices in the template are planning inputs to verify
against current provider prices before any live calls.

## SMTP and email worker settings

The email worker alone receives SMTP credentials. For the base local stack an
empty SMTP_HOST selects Mailpit, and both TLS flags remain false. Production
requires a non-Mailpit host, sender address, and exactly one TLS mode; entering
SMTP credentials without transport encryption is rejected.

| Setting and template default | Purpose, bounds, and required condition |
| --- | --- |
| SMTP_HOST=empty; SMTP_PORT=1025 | Empty host selects mailpit in base Compose; native delivery needs a host. Port 1–65535; production must set the relay's actual encrypted port. |
| SMTP_USERNAME=empty; SMTP_PASSWORD=empty | Optional authentication pair, both required together and secret when used. |
| SMTP_FROM_EMAIL=empty; SMTP_FROM_NAME=empty; SMTP_REPLY_TO=empty | Base Compose supplies a local example sender when empty; production requires a real sender. Optional display name is at most 128 characters, and empty uses application name; reply-to address is optional. |
| SMTP_STARTTLS=false; SMTP_IMPLICIT_TLS=false | Local Mailpit uses neither. Production requires exactly one true flag. |
| SMTP_TIMEOUT_SECONDS=15 | Network operation timeout, 1–120 seconds. |
| EMAIL_WORKER_CONCURRENCY=4; EMAIL_WORKER_POLL_SECONDS=1 | Parallel deliveries 1–32; empty-queue poll 0.1–30 seconds. |
| EMAIL_LEASE_SECONDS=240; EMAIL_MAX_ATTEMPTS=5 | Delivery lease 5–3600 seconds; automatic attempt cap 1–10. |
| EMAIL_RETRY_BASE_SECONDS=5; EMAIL_RETRY_MAX_SECONDS=300 | Retry backoff bounds, 0.1–3600 and 1–86400 seconds. Ambiguous delivery requires operator review. |
| EMAIL_CLEANUP_INTERVAL_SECONDS=3600 | Retention cleanup cadence, 60–86400 seconds. |
| EMAIL_SENT_RETENTION_DAYS=7; EMAIL_FAILED_RETENTION_DAYS=30 | Sent and terminal-failure record retention, 1–365 and 1–3650 days. |
| EMAIL_SECURITY_NOTIFICATION_EXPIRE_HOURS=24 | Stale security-notification limit, 1–168 hours. |

EMAIL_LEASE_SECONDS must be at least twelve times SMTP_TIMEOUT_SECONDS, and
EMAIL_RETRY_BASE_SECONDS cannot exceed EMAIL_RETRY_MAX_SECONDS. The worker
validates these relationships before delivery.
