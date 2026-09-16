# Cardchemy

Cardchemy helps instructors turn lecture PDFs into reviewed multiple-choice
flashcards and lets enrolled students study them with spaced repetition.
Instructors manage subjects, approve cards, publish sets, and invite students;
the server records answers and calculates progress.

The current version is **0.1.0**. The reference environment is local Docker
Compose; production deployment instructions exist, with operational hardening
and open-source release work still tracked in the
[remediation plan](issues-required-remediation.md).

Start with [project orientation](docs/00-START-HERE.md) and the
[project map](PROJECT-MAP.md). See the [system overview](docs/architecture/SYSTEM-OVERVIEW.md)
for how the browser, API, PostgreSQL, and workers fit together.

## Quick local setup

Install the [supported runtimes](docs/RUNTIMES.md). From the repository root on
a clean clone:

```text
python scripts/bootstrap_env.py
docker compose config --quiet
docker compose up -d --build --wait
docker compose exec backend python -m app.cli create-instructor --email instructor@example.com
```

The instructor command prompts for a password. Open
[the application](http://127.0.0.1:8080) and
[local Mailpit](http://127.0.0.1:8025). Ports above are template defaults.
Root `.env` is the sole user-managed configuration file; the bootstrap refuses
to overwrite an existing file. Generation starts disabled: configure the
worker's provider credential/model and enable `AI_PROVIDER_ENABLED` before
uploading a PDF for AI generation. Provider calls can consume paid quota.
Follow [configuration](docs/CONFIGURATION.md) to apply changes.

Use `docker compose down` to stop the stack. Preserve volumes for application
data. For native editing and the development override, follow
[local setup](docs/development/LOCAL-SETUP.md). Production TLS, SMTP, backups and
upgrade procedures are in [deployment](docs/DEPLOYMENT.md).

## Basic checks

| Working directory | Command | Purpose |
| --- | --- | --- |
| Root | `python scripts/check_context.py` | Required context files and active local documentation links |
| `backend` | `python -m pytest -q -m "not postgres and not mailpit and not ai_live"` | Offline backend contracts using the development Python environment |
| `frontend` | `npm run check` | Types, lint, units, components/coverage, build and Chromium regressions |
| Root | `python scripts/test_services.py postgres` | Disposable PostgreSQL and migration checks |
| Root | `python scripts/test_services.py mailpit` | Disposable email integration checks |
| Root | `python scripts/test_journey.py` | Real instructor/student journey with a deterministic offline provider |

Install test dependencies and Chromium as described in [testing](docs/TESTING.md).
Paid AI and the dedicated live reset browser test are separately gated.
[All guides](docs/README.md), [current state](docs/development/CURRENT-STATE.md),
and the [changelog](CHANGELOG.md) provide further context.
