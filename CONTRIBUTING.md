# Contributing to Cardchemy

Use [Start Here](docs/00-START-HERE.md), the [project map](PROJECT-MAP.md), and
the relevant module map before changing behavior. Read [AGENTS.md](AGENTS.md)
for repository engineering requirements and follow the
[Code of Conduct](CODE_OF_CONDUCT.md). Discuss substantial architecture or
product changes in an issue first; the [public roadmap](ROADMAP.md) separates
implemented work from proposals.

## Setup and safe development

Follow [local setup](docs/development/LOCAL-SETUP.md) and
[runtime support](docs/RUNTIMES.md). Configure only repository-root `.env`
from [.env.example](.env.example). Bootstrap refuses overwrites; preserve an
existing file, secrets, data and volumes. Never commit credentials, private
documents, invitation/reset links, database dumps or real user information.
Tests use authored fixtures and disposable services, not an operator's data.

Create a focused branch, such as `codex/describe-change`, and keep code, tests
and affected guides together. Use a new Alembic revision for deployed schema
changes. Preserve ownership, authorization, transaction/idempotency and
accessibility contracts. Do not add Redis, Celery, RAG, offline storage or a
new locale without an accepted product/architecture decision.

## Verification

[TESTING.md](docs/TESTING.md) owns installation, commands and gated suites.
Run checks appropriate to the change:

| Scope | Verification |
| --- | --- |
| Backend behavior | Targeted tests and `python -m pytest -q -m "not postgres and not mailpit and not ai_live"` from `backend` |
| Database model/transaction | `python scripts/test_services.py postgres` from root |
| Email delivery | `python scripts/test_services.py mailpit` from root |
| Frontend behavior | `npm run check` from `frontend` |
| Critical cross-stack flow | `python scripts/test_journey.py` from root; deterministic, no provider quota |
| Documentation/navigation | `python scripts/check_context.py` from root |
| Workflow changes | `python scripts/check_ci.py` from root |
| Release metadata | `python scripts/check_release.py --version 0.1.0` from root; use the candidate's aligned version for later releases |

Install hashed Python locks and use `npm ci` for clean frontend installs.
Dependency changes follow [dependency policy](docs/DEPENDENCIES.md). Never
lower security, coverage, accessibility or bundle budgets merely to pass.
Paid AI and the separate live password-reset browser case require their
documented opt-ins; configured credentials are not spending authorization.

## Pull requests and reports

Describe the concrete problem, resulting behavior and checks actually run.
Explain migration/configuration effects and known limits; distinguish skipped
gates from passed checks. For substantial work, add concise evidence under
`.agent/logs/` following [its governance](.agent/README.md). Keep each PR
reviewable, preserve unrelated work, and resolve review conversations.
The required `ci-required` check and current-base branch protection apply to
maintainers too. Publication follows [the release procedure](docs/RELEASING.md)
after the applicable manual and automated readiness gates pass.

Use bug/feature templates for nonsensitive reports. Report vulnerabilities
privately through [SECURITY.md](SECURITY.md), with synthetic reproductions and
safe IDs instead of secrets or user content.

By intentionally submitting code or documentation for inclusion, you offer
your contribution under Apache-2.0 as described in [LICENSE](LICENSE), unless
separately agreed otherwise. Confirm that you have the necessary rights.
Supplied brand assets have [separate terms](BRANDING.md); asset contributions
and identity changes need explicit owner approval.
