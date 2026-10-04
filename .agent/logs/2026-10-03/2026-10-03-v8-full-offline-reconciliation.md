# v8 full backend offline reconciliation

## Scope and authority

Bounded continuation of the operator-approved Lane 6 source-only work.
Starting shared checkout is dirty `main`, HEAD
`6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`. Existing changes are preserved.
Root instructions, orientation, maps, architecture/decision index, testing
guidance and relevant dated v8 records were read. This task owns only this new
record and `docs/TESTING.md`; it does not change runtime, migrations, tests,
credentials, retained data or provider callers.

## Why a fresh full run is required

The previous exec handle `25228` is absent: an actual wait returned
`Unknown process id 25228`. No terminal success or matching complete durable
aggregate for that handle was found. The preceding dated record retains a
different complete run with **1 failed, 5,295 passed, 216 skipped and 2
deselected**; it is not counted as a pass. Its concurrent fixture correction
and a passing narrow test are insufficient to claim a complete passing suite.

After the root confirmed app/test/helper sources frozen, one fresh full offline
run was launched from `backend` with the maintained command:

```powershell
venv/Scripts/python.exe -m pytest -q
```

A parent wrapper allowlists host runtime environment values, explicitly sets
the test environment and excludes operator, service and live-provider opt-ins.
The existing pytest configuration deselects `ai_live`; missing disposable
service process values cause their tests to skip. The wrapper captures output
without printing arbitrary failure details, imposes a 1,200-second outer
deadline, and writes only exit status, safe test identities, numeric summary
and input-integrity evidence to the ignored aggregate
`.agent/.verification/v8-full-backend-offline-reconciled-20261003.json`.
All Python files in `backend/app`, `tests`, `scripts` and `alembic`, plus pytest
configuration, are hashed before and after to detect concurrent input changes.

## Actual terminal result

The fresh exec handle `57840` returned terminal **exit code 0**. Its final
aggregate was then read from disk:

- **5,298 passed, 270 skipped and 2 deselected in 451.92 seconds**.
- Wrapper elapsed time: **459.733 seconds**.
- No failed or error test identities were reported.
- All **448** scoped backend Python/config inputs matched their starting
  hashes. Their canonical map SHA-256 is
  `163609b8084136b7b81ec19e5b5089bd88cac6149d5f5aeb983ca84859d9ddbc`.
- The full run used no live or disposable-service opt-ins. Live AI tests were
  deselected; skipped service tests require their separate service harness,
  and optional real local-artifact tests remain separately opted in.
  This offline pass is not proof of PostgreSQL execution, a real provider call,
  private source usefulness, a browser journey or release enablement.

Only the numeric/safe aggregate is retained. Arbitrary pytest failure output,
prompts, credentials and model responses were not printed or logged. No
operator environment or retained database was used. The scoped input hash
covers backend directories named above, not every transitive repository file;
the root also coordinated the test/helper freeze before this run.

The durable aggregate SHA-256 is
`0ab74fc820a74613b25a9302c4bd5a024736e111a0f87ca6b73a0e03149b4060`.
Repository context validation after the documentation change passed:
**37 required files, 79 active guides and 2,107 local links**. Scoped
`git diff --check` passed, with an existing LF/CRLF notice only.

## Documentation and evidence boundaries

`docs/TESTING.md` now names current source/retained `20261002_0033` and the
v8/visual-v5/admission-v2 pairing, with focused current commands and both v8
PostgreSQL modules. Earlier v7 command/evidence sections remain historical.
The root owns retained cutover, combined PostgreSQL, frontend/journey/image
evidence, private source transfer/display measurement and final enablement.

No provider call, private source/credential read, Docker operation, retained
mutation, Ask activation or hosted CI was performed by this scoped work.
The public sixty-case selection result is separate from private usefulness and
browser/spoken-accessibility release evidence. Root `.env`, populated volumes,
original PDFs, backups and all historical failed attempts remain untouched.
