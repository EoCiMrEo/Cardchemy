# Local Setup

Current setup, verified against scripts/Compose on 2026-09-16. Begin with
[orientation](../00-START-HERE.md). Supported versions are owned by
[RUNTIMES.md](../RUNTIMES.md); settings/ranges and rotation rules are owned by
[CONFIGURATION.md](../CONFIGURATION.md).

## Built reference stack

On a clean clone, from the repository root:

```text
python scripts/bootstrap_env.py
python scripts/check_config_migration.py
docker compose config --quiet
docker compose up -d --build --wait
docker compose exec backend python -m app.cli create-instructor --email instructor@example.com
```

If root `.env` already exists, preserve it and skip bootstrap. It creates
independent secrets once and refuses overwrites. The CLI prompts for a password;
public signup creates only invited students. Additional instructors need the
explicit CLI `--allow-additional` option. See [authentication operations](../AUTHENTICATION.md).

At template defaults the application is [127.0.0.1:8080](http://127.0.0.1:8080)
and local email capture is [127.0.0.1:8025](http://127.0.0.1:8025).
The migrate service runs before API/workers. Generation remains disabled until
provider settings/credential are configured and `FLASHCARD_AI_PROVIDER_ENABLED=true`.
Recreate the API/generation worker to apply the switch/settings; enabling can
spend provider quota. See [AI providers](../AI_PROVIDERS.md).

Stop with `docker compose down`, retaining volumes. This guide never requires
discarding an existing database. For upgrades/recovery follow
[database operations](../DATABASE_OPERATIONS.md).

## Editing the frontend with the development stack

Use one override at a time, from root:

```text
python scripts/check_config_migration.py
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile development up -d --build --wait
```

The override mounts backend source, enables API reload, and publishes DB/API
and Mailpit SMTP only on loopback. Workers need restart after Python edits.
From `frontend/`:

```text
npm ci
npx playwright install chromium
npm run dev
```

Vite normally serves port 5173 and sends `/api` to the configured host API_PORT,
stripping the prefix and rewriting cookie paths. Keep root public settings
consistent with that API; no component `.env` is needed. The development
override includes the template local Vite origins. Custom origins need explicit
CORS configuration. The built Compose frontend remains a separate serving path.

## Native backend alternative

Use supported Python, create a development virtual environment and install the
hashed lock. Windows commands from root:

```powershell
python -m venv backend/venv
backend/venv/Scripts/python.exe -m pip install --require-hashes -r backend/requirements-dev.txt
```

Reuse an existing supported environment instead of recreating it. POSIX uses
`backend/venv/bin/python`. For the native mode, start only infrastructure through
the development override (or use a separately managed PostgreSQL 16 instance):

```text
python scripts/check_config_migration.py
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile development up -d --build --wait db mailpit
```

This infrastructure-only command does not stop an already running API/worker.
Avoid running native and Compose APIs on the same port, or duplicate workers
unintentionally; choose one application-process mode.

For a native installation, root settings must describe native endpoints:
an empty DATABASE_URL derives localhost from POSTGRES_* and POSTGRES_PORT;
FRONTEND_BASE_URL/CORS_ORIGINS must match the Vite browser origin. Native email
uses `SMTP_HOST=127.0.0.1`, the published MAILPIT_SMTP_PORT and a local sender,
without either TLS flag. Base Compose's internal `mailpit` hostname is not a
native endpoint. Set endpoints deliberately for the chosen mode before running.

From `backend/`, using that environment's Python, run migration once, then each
long-running process in its own terminal:

```text
python -m alembic upgrade head
python -m alembic current --check-heads
python -m alembic check
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
python -m app.worker
python -m app.email_worker
```

The shown 8000 must agree with API_PORT. The native generation process requires
provider credentials when enabled; the email worker requires complete SMTP
settings. OCR needs the explicit setting and local executables; follow
[PDF operations](../PDF_GENERATION.md). Compose is the simplest supported full
stack; [deployment](../DEPLOYMENT.md) owns its exact variants/production setup.

## Verify and find code

[TESTING.md](../TESTING.md) owns suite commands, install requirements and gated
cases. `npm run check` is the complete frontend authority; guarded service
harnesses generate isolated databases/credentials and ignore operator settings.
`python scripts/check_context.py` from root validates context files and local
links. Do not interpret fixture tests as a paid-provider or production test.

Trace a change through the [project map](../../PROJECT-MAP.md),
[backend MOC](../../backend/MOC.md) or [frontend MOC](../../frontend/MOC.md).
Read [current state](CURRENT-STATE.md) before phase work and
[agent rules](../../AGENTS.md) for documentation obligations.
