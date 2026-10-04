# Lane 6 v4 operations and context alignment

Date: 2026-09-29 (America/Chicago). Branch `main` at `6c02d6c`. The shared
working tree already contained the dormant `0029` migration, v4 worker and
browser slices, and the database guide's earlier changes through `0028`. This
task preserved those edits, the root `.env`, populated database and original
PDF archives. It made no schema migration, provider request, private Knowledge
transfer or runtime activation.

## Scope and decision

Updated `docs/DATABASE_OPERATIONS.md` from source revision `0028` to `0029` as
the checkout head. The guide now describes the v4-only immutable judge snapshot,
`source_judgment` stage and one-embedding/one-judge physical-request guards,
the requirement for a completed successful judgment before v4 references,
and source-free pre-remote clarification. It distinguishes the source head from
the retained installation, last verified at `0028` in the
[persistence evidence](2026-09-29-source-judge-persistence-slice.md) and
[calibration stop](2026-09-29-public-source-id-live-calibration-stop.md).

The documented cutover keeps Ask disabled, drains writers, preserves the
existing root configuration, populated volume and PDF key, requires a
restore-verified backup, applies Alembic with current-head/drift checks, and
recreates matching API, answer worker and frontend processes. It calls for
historical v3 readability and independent published-Knowledge browse/PDF
authorization checks before ordinary traffic. The `0029` downgrade refuses any
retained v4 job, including terminal jobs without references; the guide directs
operators to preserve history and use forward repair or a verified backup in a
separate target instead of deleting records to force a downgrade. These are
operating instructions, not a claim that a populated cutover occurred.

Aligned `AGENTS.md`, `PROJECT-MAP.md`, both module maps, and the Ask shutdown,
configuration, Subject Knowledge architecture, RAG evaluation and deployment
guides with the dormant v4 contract. They distinguish at most one query
embedding plus one bounded source-ID judgment from historical answer requests;
the judge's worker-only credential, current published-page text transfer,
price/attempt limits, source-free clarification and failure state are separate.
The code's runtime release fence remains closed, and the retained installation
was last verified at `0028`. Current-state and roadmap alignment awaits the
coordinated cutover result; this documentation pass makes no cutover claim.

## Release boundary

The public two-PDF labels and scoring rule were frozen, but the first approved
public calibration attempt stopped after one physical provider request failed
response admission. Its exact response status and cost are unknown. No
calibration score or heldout score exists, and that approval is consumed. A new
paid pilot requires a fresh explicit endpoint/model/price/call/token/time/cost
envelope that includes unknown prior cost. ADR-024 then requires a passing
public gate before separately approved and disclosed real published-Knowledge
transfer. The independent original-PDF release gate still requires at least
10/12 useful-page hits in the fresh holdout, at least 3/4 for each question
form, at least 10/11 exposed-regression hits, at least 90% useful original
pages across **all displayed cards**, explicit no-match and negative cases,
and zero fabricated, unauthorized, stale or wrong-page references. Current
access, publication/revision, PDF-open, accessibility and operational checks
remain separate. Ask stays disabled; Lane 6 remains 3/7.

## Checks and limits

`python scripts/check_context.py` passed: 37 required files, 79 active guides
and 1,471 local links. A scoped `git diff --check` passed with only line-ending
warnings. The migration's offline/disposable
PostgreSQL verification is recorded in the persistence and preflight logs;
this task did not rerun it or migrate the retained database. Hosted CI,
deployment, manual spoken assistive-technology validation and source-judge
quality were not established here. No temporary resource was created.

## Subsequent status correction, 2026-09-29

The earlier `0028` retained-installation statements above describe the state
at the time of this documentation pass. A later, separately evidenced
[retained cutover](2026-09-29-source-judge-retained-cutover.md) restored a
checksum-verified pre-upgrade backup into a rehearsal database, migrated the
original populated volume to `20260928_0029`, passed head and drift checks,
and recreated healthy matching services. Ask remained disabled. `AGENTS.md`,
`backend/MOC.md` and the Subject Knowledge architecture now reflect that
verified `0029` state. The architecture also specifies the answer worker's
separate source-judge profile and worker-only credential requirement for any
future enabled v4 execution. This correction performed no database operation,
provider request or configuration change.
`python scripts/check_context.py` passed again: 37 required files, 79 active
guides and 1,479 local links. Scoped `git diff --check` passed with only
line-ending warnings.

Final credential-boundary wording correction: `AGENTS.md` now names the
actual Compose split explicitly: Flashcard AI key on the generation worker,
embedding key on index/answer workers, source-judge key on the answer worker,
and SMTP key on the email worker. This was checked against `docker-compose.yml`;
no credential value, root `.env` byte, container environment or runtime
configuration was changed.
