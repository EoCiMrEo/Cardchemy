# Phase 9 remediation: repository hygiene and verification

Date: 2026-09-16

## Orientation and inventory

The active roadmap is `issues-required-remediation.md` Phase 9A, then 9B and
9C. The requested `.agent/AGENTS.md` does not exist. The prior remediation and
AI-change logs in this directory provide the architectural history; maintained
application behavior comes from current code and tests. At the start of this
work the checkout already had user-owned edits to `.env.example` and the roadmap
and a deletion of `frontend/.env.example`; these were preserved. The real root
`.env` exists and its values were not read or logged.

| Candidate | Decision and consumer evidence |
|---|---|
| `backend/app/agents/nodes.py`, `state.py` | Remove. Repository source search found no imports of these compatibility modules. The maintained pipeline imports `app.ai.chunking` and `app.ai.grounding` directly; the old typed state is not referenced. |
| `backend/app/agents/graph.py`, `__init__.py` | Keep until consumers migrate. `workers/generation.py`, the package export, and the opt-in live AI test use the facade. It passes the provider semaphore and worker-wide rate governor to `FlashcardGenerationPipeline`; removing it alone would break those contracts. |
| `frontend/src/components/ui/slot.tsx` | Remove. Source search found no import of the wrapper; `button.tsx` imports `@radix-ui/react-slot` directly. Keep the Radix dependency. |
| `frontend/src/assets/react.svg` | Remove. Source search found no reference to this Vite scaffold asset. |
| `frontend/public/vite.svg` | Replace. `frontend/index.html` referenced it as the live favicon. The document now references a simple card icon at `frontend/public/cards.svg`. |
| `frontend/tailwind.config.js`, `postcss.config.js` | Consolidate after generated-CSS review. The original Dockerfile copied both and both Vite and PostCSS Tailwind plugins were configured. The frontend build workstream removed the redundant Tailwind config and PostCSS Tailwind plugin, retained active CSS `@theme` tokens and the Vite plugin, and kept Autoprefixer. Baseline CSS was 44.40 KB versus 44.03 KB after; only unused utility/theme-token differences appeared in the initial comparison. Browser/accessibility checks remain the final equivalence gate. |
| `frontend/README.md` | Replace the Vite scaffold text with the actual frontend setup and validation entry point. |
| `idea.md` | Archive intact under `docs/archive/idea.md` with an explicit historical label. Its older Redis, storage, quiz, and reward proposals are not product documentation. |
| Migrations, dependency lockfiles, AI evaluation fixtures, and maintained tests | Keep. Revision IDs/data, hash locks, fixed evaluation data, and regression coverage are product and release contracts, even where names mention old phases. Test renaming and fixture consolidation belong to the test workstream. |

Maintained documentation had a stale backend environment-template path,
per-job AI concurrency wording, a ten-job quota inconsistent with the selected
twenty-job limit, obsolete Compose profile commands, and remediation-phase
language. These were corrected in the relevant docs. The new
`docs/CONFIGURATION.md` documents the single root file, native/Compose routing,
settings, secret injection, and safe update path. Historical remediation evidence
remains in `.agent/logs/`.

## Verification boundary

Before test renaming, Playwright listed 48 tests in nine files. Host-global
`python -m pytest --collect-only -q` could not collect because that Python lacks
`alembic.config`; backend verification must use the project's dependencies or
container. This log does not claim PostgreSQL, Mailpit, live-provider, or browser
gates until those suites run in isolated environments. No production data,
secrets, migration files, or lockfiles were touched by the hygiene slice.

## Root configuration and completed 9A verification

- Merged all 120 application/Compose keys into the sole root template and
  removed component examples. Backend resolves root `.env` absolutely; native
  PostgreSQL URLs derive from root POSTGRES_* with URL-escaped passwords, while
  Compose injects its internal `db` URL. Vite reads exactly root `.env` with
  process precedence and exports only its public API setting. No `.env.local`
  or mode-file fallback is supported. Its `/api` proxy strips the prefix and
  rewrites the refresh-cookie path.
- The user explicitly selected 20 generation jobs per user per UTC day. Root
  template, Settings default, Compose fallback, and docs now agree. Local
  template SMTP port is 1025 with both TLS flags false; encrypted production
  transport remains mandatory.
- Shared PostgreSQL fixtures require asyncpg, a loopback/controlled test host,
  a disposable `*_test` database name, actual database identity, and the
  dynamically derived Alembic head before writes. Test processes force safe
  core settings and never load the real root `.env` through get_settings().
- Phase-labelled tests/helpers were renamed/split without removing coverage.
  Backend discovery retained 194 ordinary cases plus the opt-in live AI case,
  then gained root-loader/template checks. Playwright retained 48 cases across
  14 behavior-named specs. The PostgreSQL generation file uses
  `test_generation_job_persistence.py` to avoid a pytest module-name collision.
- Offline backend gate after cleanup: 171 passed, 24 environment-gated skips,
  one opt-in live AI case deselected. Latest focused config gate: 11 passed,
  including precedence, CWD independence, secret isolation, template coverage,
  valid generated bootstrap, and refusal to overwrite an existing file.
- Frontend `npm run check`: typechecks, lint, three Node unit tests, production
  build, and 47 Chromium cases passed; the separate live password-reset case
  remains explicitly gated. Accessibility/responsive and keyboard tests passed
  after CSS consolidation. Generated CSS dropped only unused utility/theme
  material; active focus and layout behavior remains covered.
- Generated QA root configuration built and started the isolated
  `flashcardphase9qa` development Compose stack: every persistent service
  became healthy and migrations completed first. That project's containers,
  network, and disposable volumes were then removed; the original
  `flashcardgenerator` containers were untouched.
- `backend/venv/Scripts/python scripts/test_services.py postgres`: 21 passed,
  three Mailpit-only cases skipped, 172 deselected. Alembic current/head,
  metadata drift, full downgrade to base, and re-upgrade to head passed.
- The same helper's `mailpit` suite: three passed, 193 deselected. Both helper
  runs removed their UUID-named containers and generated credential files.
- An initial automatic approval review failed at the account usage limit.
  After inspecting the helper's bounded container/temporary-file operations,
  a retry was accepted and both service suites completed successfully.
- Real root `.env`, application data, migration files/revision IDs, and authored
  evaluation fixtures were preserved. Lockfile changes so far only remove the
  unused PostCSS Tailwind dependency. No paid provider call was made.

The root configuration template lists 120 names, all present in the grouped
configuration reference; their documented defaults were compared against the
template. The favicon parses as SVG, maintained Markdown links checked locally,
no active source/documentation reference to the deleted scaffold or compatibility
files remains, and `git diff --check` reported no whitespace errors. This
bounded verification does not replace the full frontend build/browser and
backend gates after concurrent configuration and test changes settle.

## 9B final evidence

Backend discovery now contains 228 cases: 203 offline, 21 PostgreSQL, three
Mailpit and one opt-in paid AI case. Domain renames retained existing behavior;
new cases cover JWT required claims/algorithms, PDF page bounds, disposable
harness safeguards and live-budget admission. The live test now calls the
pipeline directly; the graph facade remains a shipped worker dependency.

| Final gate | Result |
|---|---|
| Offline backend, Python 3.13.7 | 203 passed; 25 service/live cases deselected |
| PostgreSQL | 21 passed, three Mailpit-only skips, 204 deselected; current head, no drift, all seven revisions downgrade/re-upgrade passed |
| Mailpit | Three passed, 225 deselected; generated services/credentials cleaned |
| `npm run check` | All typechecks, lint, four Node units, 26 component contracts/coverage and production build passed; 47 Chromium passed, one separately gated live reset skipped |
| Real instructor/student journey | One passed in 23.2 seconds; actual API/generation/email workers, PDF extraction/grounding, review/publication, invitation, signup/study and database progress proof |
| Live evaluation admission | 19 offline guards passed; paid case deselected, no provider call |

The real journey's final database proof checks two users, one set/job/enrollment,
two approved grounded cards, two correct progress rows/durable answer receipts,
one delivered invitation and no retained PDF. Its deterministic provider exists
only in the guarded test entry point. Containers, processes, generated accounts,
credentials, browser artifacts and caches are disposable and cleaned afterward.

Full frontend verification exposed timing races under concurrent image builds.
The timer boundary now holds the session response until the lazy page mounts,
uses double activation at virtual 850 ms, holds acknowledgement across 1,050 ms
and proves one write. Telemetry awaits authenticated job responses. Invitation
navigation awaits Login URL/heading before filling fields; its trace proved the
old registration email was filled during the lazy transition. Original behavior
assertions and timeouts were retained. Focused reruns passed six timer/telemetry
and four authentication cases before the successful authoritative full gate.

Paid evaluation reserves the full 8,192-input/2,048-output token price envelope
before creating a provider, permits one request/two cards with no retries or
refills, and caps reviewed estimated cost at USD 0.02. Prompt/schema bytes and
framing are conservatively counted. Only the official OpenAI endpoint and pinned
non-reasoning GPT-4o Mini snapshot with reviewed price floors are admitted.
Other models need their own complete billing bound. Gemini's shipped adapter
does not account for billable thought tokens; production accounting was outside
this test change and was preserved. Taxes/future prices need account controls.
Maintained commands and expected gating are in docs/TESTING.md and docs/CI.md.

## 9C dependency, runtime and CI evidence

The fresh Python production audit initially reported 92 findings in six packages,
including ecdsa without a fix. PyJWT replaces python-jose/ecdsa while retaining
HS256, token purposes, required claims, issuer/audience, expiry and sessions.
Compatible FastAPI/Starlette, multipart, PDF, dotenv/settings and pytest security
updates are pinned. Both hash locks were regenerated through the canonical
backend/scripts/lock_dependencies.ps1, which now stamps its actual command.
Production and full-development Python audits report no known vulnerabilities;
both production and full npm audits report zero. No registry exceptions or
legacy-peer-dependency bypass was used. Browserslist data is current.

Measured lazy-route bundles are 120,400 bytes initial JS gzip, 360,202 bytes
largest raw JS and 222,704 bytes total JS gzip. Budgets are 130,000/400,000/240,000.
Static imports count toward initial; dynamic routes toward total. The original
Vite warning threshold remains. Backend coverage includes every application
module: 78.20% lines, 57.56% branches, 74.25% combined, above 77/55/73 floors.
Authentication, generation, study, AI/grounding and email have individual floors.
Focused four-file frontend coverage is 96.44% statements, 85.05% branches,
91.66% functions, 97.71% lines; this is not whole-frontend coverage. AuthContext
branches remain 66.66%, visible in reports. Focused floors are 90/80/90/90.

Workflows use read-only tokens, official full action SHA pins, timeouts and
mandatory backend 3.11/3.13, migrations, Mailpit, frontend, real journey, full
dependency audits, secrets and final runtime-image gates. ci-required fails for
failed/cancelled/skipped mandatory jobs or matrix members. Release SBOMs include
CycloneDX, source/image identity and checksums. Native dependency review needs
the private repository's GitHub feature entitlement; full locked audits across
all scopes run regardless. Dependabot groups tested compatible/security updates.
The official actionlint 1.7.12 archive checksum was verified and all three
workflows passed its syntax/expression checks plus scripts/check_ci.py contracts.

Initial images had 62 default/104 OCR Debian OS HIGH/CRITICAL findings, vulnerable
vendored Python build tools and two Alpine OpenSSL findings. A Debian 13 upgrade
still had 44 default findings without fixes. Final Python 3.11/Alpine 3.24 images
upgrade OS packages and omit runtime pip/setuptools/wheel and compiler tools.
OCR installs English data and Liberation fonts; the real probe first proved a
blank raster and missing Helvetica font, then recovered image-only PDF text
after adding the font. All three nonroot runtime probes pass actual native
extensions, API/workers, bcrypt, JWT purpose, AES-GCM/PDF/OCR and nginx behavior.
CI and release workflows execute those same probes on their built images.

Scanner execution received explicit user approval after automatic review
rejected whole-repository/private-source mounts. The helper exports Git-visible
source/history/current changes and immutable built-image archives, excludes real
.env/ignored data, downloads only public advisory data before private mounts,
disables scan networking and mounts no Docker socket. The public Trivy database
cache is retained separately. Windows read-only exported Git objects required
a path-bounded cleanup callback. Six historical false positives are synthetic
idempotency values: exact fingerprints and an AND-scoped test-path/exact-literal
rule keep default scanner rules active. Two config-test literal matches were
removed by generating its private temporary secret instead of another exception.

GitHub main protection is applied using the existing noninteractive Git login,
without printing credentials. Its checks-only payload binds ci-required to
GitHub Actions app 15368, requires current-base success, includes admins,
requires pull requests/resolved conversations and forbids force pushes/deletion.
The initial 422 rejected simultaneous legacy contexts/checks fields; the valid
checks-only payload succeeded and its returned values were recorded privately.
Hosted workflow success and a controlled failing-PR proof are the final closure
steps; the corresponding checklist item stays pending until verified.

Final approved local scanner run passed: 24 commits including the exported current changes, zero Gitleaks findings, zero worktree secret findings, and zero HIGH/CRITICAL OS/Python findings in all three final image archives, including unfixed advisories. Three CycloneDX SBOMs, immutable image identities, advisory database timestamps and SHA256 checksums are retained in ignored artifacts/security. Generated scanner source/history/archive directories are removed. No OS vulnerability exception or ignore-unfixed option was introduced.

Controlled hosted merge-blocking rehearsal: the first review-branch commit intentionally sets authentication coverage to an impossible 101% floor. This is confined to the review branch, is expected to fail ci-required, and must be restored to the measured 88% floor before final closure. Branch protection prevents merging this rehearsal.

## Hosted enforcement and final isolation review

The Phase 9 branch is published as codex/phase-9-remediation and review PR
https://github.com/EoCiMrEo/Cardchemy/pull/1 is open without merging main.
The initial hosted run is
https://github.com/EoCiMrEo/Cardchemy/actions/runs/35129005199 at
731bc7d6942710774e42be91e751cb8d67f58ffb. Both Python 3.11/3.13 suites
passed 203 tests and failed only the deliberately impossible authentication
coverage floor (89.40% actual versus 101%). Migrations, Mailpit, the real
journey, dependency audits, secret scans and all three final-image gates passed.
GitHub returns a non-draft, conflict-free PR with mergeable_state=blocked; the
required aggregate result is still pending the frontend at this checkpoint.
The returned main policy retains strict ci-required bound to Actions app 15368,
admin enforcement, zero required reviewers and disabled force pushes/deletion.

A final subagent audit found that Vite had eagerly parsed root .env before
applying public process overrides; earlier browser checks could therefore
consult the operator file for API_PORT. Its contents were not printed, copied
or modified. The loader now skips the file when both public values are supplied.
The complete frontend check, browser runner and direct Playwright server inject
safe API_PORT/VITE_API_URL values; standalone dev/build keep the root contract.
A new Node regression uses a directory as an unreadable root file to prove no
read with complete injection, partial fallback behavior and port validation.
Node discovery increases from three to four cases. The existing pre-browser
check stages/order remain unchanged and propagate failures before the browser.

All four named early QA/scanner temporary artifacts were removed after exact
path checks. The source exports were owned by the sandbox account, so cleanup
ran under that same account with a path-bounded read-only-file callback.
Final audits/SBOMs and filtered remote evidence remain in ignored artifacts.

The controlled negative run completed: frontend and all other mandatory gates
passed, both backend matrix members failed only Coverage budgets, and
ci-required failed with backend-offline as its sole failed dependency. GitHub
reports the PR blocked with a completed failing ci-required from app 15368;
main protection includes administrators, so the authenticated maintainer also
cannot bypass this requirement. No merge was attempted. The authentication
floor is restored to 88% and the branch-protection task is now verified/done.
The repaired branch must still receive a successful final hosted CI run.

The repaired isolation orchestrator passed all three typecheck stages, full
lint, four Node units, all 26 component contracts/coverage, production build
and four focused authentication browser cases. Its 48 ordinary browser cases
are unchanged; hosted CI will run the entire browser suite on the repaired head.
Workflow contracts and restored backend coverage budgets pass locally.

## Phase 9 closure

Repaired hosted run
https://github.com/EoCiMrEo/Cardchemy/actions/runs/35129468986 at
bd6580bd54874a3c4edbec5cd607cf0c44fc2281 completed successfully: all 12
mandatory jobs including every matrix member and ci-required passed. Frontend
logs prove four Node units, 26 components and 47 Chromium passes/one intentionally
gated reset case, with the same measured bundle budgets; no browser retries or
flaky cases were reported. The real journey passed separately. GitHub reports
PR #1 clean, non-draft, unmerged and conflict-free, with successful ci-required
from app 15368 and unchanged enforced main protection. The initial negative
run and this repaired run establish actual protected-merge behavior.

All 40 Phase 9 tasks are marked done: 24 in 9A, eight in 9B, eight in 9C. The
duplicate v1.0 Phase 9A cleanup/root-configuration criterion is also done; other
release criteria and Phases 10-11 retain their scope/status. The roadmap baseline
now reflects current tests, audits, image probes, bundle measurements and hosted
enforcement instead of the older cleanup-review numbers.

Local scan provenance now records the actual Git dirty state and exported
snapshot commit instead of a constant flag. Its complete final scan is recorded
below once finished. This final evidence/documentation commit will receive a
new full hosted CI run before handoff. Changes remain on the review branch;
main has not been merged and original application services/data/root .env are
preserved. Optional paid AI and the separately gated live reset are not claimed
as executed.

Final approved isolated scan after the provenance correction returned exit 0:
zero history/current-source secret findings and zero HIGH/CRITICAL findings
in every final image, including unfixed advisories. All three CycloneDX SBOMs
parse and every retained SHA256 checksum verifies. Source head is bd6580bd and
exported snapshot 05968b0e804d212ece600a8303dde6465839a051 identifies the scanned
Git-visible tree; dirty state is true for the pending closure changes. The
private scanner workspace is confirmed removed.
