# Database migrations, backup, restore, and rollback

## Current local Lane 6 closure — 2026-10-04

The local source-only v8/visual-v5/admission-v2 installation on head `0033`
is enabled after its measured quality, PDF/display and release gates. Fresh
installations remain default-off. See the
[closure and activation evidence](../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md). Earlier installation
checkpoints below remain historical snapshots; the linked closure supersedes
their off/pending status, while default-off and upgrade safeguards still apply.

## Current retained v8 forward upgrade — 2026-10-03

Source and retained head are **`20261002_0033`**. A fresh backup was restored and
verified separately before the forward migration; retained heads and model
drift passed. Populated volumes, root `.env`, original PDF archives and earlier
backups remain preserved. Matching-service checks are a separate cutover step;
Ask/source judging remain off and private transfer/release gates remain open.

The additive migration pairs v8 with `visual_source_id_v5` and
`literal_subject_admission_v2`, retaining exact historical v7 checks. It extends
immutable context, source-only profile/result/reference/stage and one-remote-
attempt guards without rewriting old jobs. Historical jobs cannot execute or
retry as v8. Downgrade refuses any retained v8 job before changing schema; use
forward repair or restore a verified backup into a separate target. Never
downgrade retained data to test. See
[migration](../backend/alembic/versions/20261002_0033_visual_clarity_policy.py),
[independent disposable checks](../.agent/logs/2026-10-03/2026-10-03-v8-runtime-independent-boundary-review.md)
and [ADR-024](decisions/ADR-024-gemini-source-id-judge.md).
Earlier dated sections preserve their original installation snapshots.

## Historical completed retained v7 forward upgrade — 2026-10-02

Source and retained head are `20261002_0032`. Writers were drained and a fresh
backup restored to a separate disposable target before the forward migration.
Retained heads/drift, matching-service health and preserved aggregate counts
passed; root `.env`, populated volumes, three original PDFs and earlier backups
remain intact. Ask and source judging remain off. See
[cutover evidence](../.agent/logs/2026-10-02/2026-10-02-v7-retained-cutover-and-release-recheck.md)
and [disposable PostgreSQL evidence](../.agent/logs/2026-10-02/2026-10-02-v7-postgresql-uuid-repair.md).
For future retained upgrades repeat drain, restore-verified backup, forward
migration, heads/drift and matching-service checks. Never downgrade retained
data as a test. Earlier dated sections are history.

## Historical dormant visual Ask contract — 2026-10-01

Source and retained schema are `20261001_0031`; matching application services
are healthy after a restore-verified forward cutover, with data, original PDFs
and root `.env` preserved. Ask and source judging remain disabled. The
`related_knowledge_navigation_v6` / `hybrid_source_navigation_v9` path uses
`visual_source_id_v2`, Gemini 3.5 Flash-Lite HIGH, 32,768 input / 4,096 output
including thinking and a 60-second provider deadline. It allows at most one
current-question embedding and one issued-ID/category-only judgment, zero
answer/verifier calls and zero automatic provider retries. Full-page PNGs are
bounded to 1 MiB/2 MP/1,600 pixels; definitive oversize alone permits bounded
1,400/1,200/1,000 scale reduction within one 30-second page deadline.

Complete public calibration passed with 89.32% useful displayed cards.
Independent different-PDF/private usefulness and release gates remain open:
the prospective target is 80% displayed usefulness, at least 10/12 ordinary
no-match controls and the existing hit/availability gates. Fabricated,
unauthorized, stale or wrong-page references still require zero. Installed
0030 and historical v5/visual-v1 2,048-token snapshots remain immutable and
readable; they cannot execute or manually retry as v6.

See the [current verification record](../.agent/logs/2026-10-01/2026-10-01-visual-v6-matching-contract-and-backup.md).
Earlier dated v4/v5 details below describe retained history where they differ.


The database schema is owned by Alembic. The API never creates or alters tables
at startup; it refuses to start when the database revision is not at the current
head. The initial revision, `20260914_0001`, is a clean baseline and is not an
adoption migration for older development databases. This checkout's head is
`20261002_0033`, described above. The earlier `20260928_0029` admitted a
separately bounded v4 source-ID judge snapshot, stage and reference guard
without reinterpreting historical Ask jobs. The
`20260927_0028` revision admitted the corrected source-navigation v3/v9
job/reference pair without rewriting historical v2/v8 or earlier jobs.
`20260927_0027`
admits source-navigation v2 and its v8 canonical references.
`20260927_0026` adds immutable original-PDF archives and authenticated
encrypted blocks. Original archives are included
in database backups; separately preserve `KNOWLEDGE_PDF_ENCRYPTION_KEY`.
Current key version 1 has no online key-rotation tool. `20260927_0025` fences
historical canonical-page reference inserts to the structural
v7 retrieval policy while retaining historical v6 rows. Revision
`20260927_0024` adds an explicit reference source kind and canonical-page
offsets, retaining historical chunk offsets. Its insertion guard checks the
current authorized page and eligible discovery anchor. Revision `20260926_0023`
binds source-only stage policy and current manual/worker attempt identity to
the parent job. Revision `20260926_0022` adds source-only terminal
kinds, separate embedding identity and at most three source references without
assistant answer messages. These revisions do not enable Ask: the source-only
release gate remains separate. Revision `20260925_0021` introduced the historical
two-excerpt fallback. Revision `20260925_0020` extends
the same one-request-per-remote-stage, zero-retry database guard to that dormant
v2 policy. Revision `20260925_0019` adds bounded
encrypted validated-card choices and generation quality history, while
`20260925_0018` adds content-free Ask diagnostics. Revision `20260922_0017`
snapshots the two-request answer/support policies and attempt cost provenance,
admits the local-support stage, and constrains each remote stage to one physical
request with zero retries. Revision `20260922_0016`
admits the exact `gemini-embedding-2` format/task identity while preserving 001
and historical spaces. Revision `20260922_0015` adds durable, owner-scoped Knowledge duplicate choices,
exact-revision no-change/reuse outcomes and their constraints. Revision
`20260922_0014` adds Gemini catalog/schema-policy snapshots and content-free Ask
failure-stage, physical-attempt, timing and uncertainty diagnostics.
`20260920_0013` admits canonical native Gemini embedding-space/task-mode
identities, adds RAG request correlation and stage timings, and adds fixed-field
Knowledge publish/unpublish/removal audits.
`20260919_0012` adds private Subject Ask AI threads/messages/exact sources,
separate quota receipts and durable fenced answer jobs. Revision
`20260919_0011` adds durable capture outcomes, Knowledge-only admission,
embedding task-mode identity, local chunk mapping and index execution telemetry
to the private Subject Knowledge schema created by `20260918_0010`. Revision
`20260918_0009` requires
PostgreSQL 16 and pgvector 0.8.6 in `public`, even with RAG disabled.
The [runtime inventory](../runtime-artifacts.json) pins the supported container
image/platform; [native prerequisites](RUNTIMES.md#database-runtime-and-native-installation)
apply before migration or restore. Revision `20260917_0008` adds content-free operational tables, generation request
correlation, retention indexes and the transactional role-change audit trigger.
The preceding `20260916_0007` stores the per-stage request map as PostgreSQL JSONB so schema
drift checks remain comparable. Revision `20260916_0006` adds durable AI
provider request, retry, quota-wait, cache, and per-stage telemetry. Revision
`20260915_0005` adds the transactional email
outbox and optional recipient binding for emailed invitations. Revision
`20260915_0004` adds durable
study-answer idempotency receipts. Revision `20260914_0003` adds AI
provider/model snapshots, bounded usage/cost telemetry, and verified flashcard
page/section provenance; `20260914_0002` adds durable generation jobs,
encrypted temporary sources, quotas, and the exactly-once job/result link.

Before using Compose, define strong `POSTGRES_PASSWORD`, `SECRET_KEY`, and
`GENERATION_SOURCE_ENCRYPTION_KEY` values in the root `.env`. Generate the two
application keys independently. Compose intentionally refuses to start when a
required value is missing; do not place real values in source-controlled
examples.

For a clean clone, `python scripts/bootstrap_env.py` creates those three values
independently, without displaying them, and refuses to overwrite an existing
`.env`.

## Fresh installation

On a new installation, create the root `.env` with the non-overwriting bootstrap
script, then start the stack. The migration service applies the complete Alembic
chain before the API and workers start:

```powershell
python scripts/bootstrap_env.py
docker compose up -d --build --wait
```

Never remove a populated Compose volume as part of an upgrade; follow the backup
and migration steps below instead.

## Upgrade and verify

Create a backup before every upgrade. Preserve the existing database name,
Compose project and data-volume path. Drain all writers before changing the
PostgreSQL 16 image. A patch-level image replacement does not authorize a major
version upgrade or volume recreation. Validate a restore into a separately
named empty target first; the tested source/target must have the reviewed
pgvector binaries installed. Then run:

```powershell
docker compose run --rm migrate
docker compose run --rm backend alembic current --check-heads
docker compose run --rm backend alembic check
```

`current --check-heads` proves the database reached every configured head.
`alembic check` detects model changes that do not yet have a migration.

The `0015` upgrade adds nullable choice/outcome history to existing generation
jobs and extends the active-job status/index with `awaiting_choice`; it adds no
root `.env` setting and does not rewrite existing Knowledge. Drain writers as
above, migrate, then recreate the API, generation worker and frontend together
so every process understands the new status and typed response fields. Existing
queued/captured jobs retain their prior lifecycle and links.

The `0016` upgrade changes only embedding-space and index-identity constraints.
It does not create or relabel vectors. Existing 001 and historical rows remain
valid; model-2 vectors require a newly staged space built from canonical pages.
The `0017` upgrade adds nullable policy snapshots to retained answer jobs,
attempt-cost fields and a partial unique index for each new-policy attempt's
query-embedding/answer stages. Existing jobs remain historical and cannot be
executed under a different policy. Its answer/local-support execution is now
retired for new Ask jobs under [ADR-022](decisions/ADR-022-related-knowledge-primary-ask.md).
Source-only rollout needs embedding configuration, not an answer-model key or
local verifier bundle. Drain the worker and keep Ask off while migrating.

The `0018` upgrade adds nullable content-free Ask failure, finish, retrieval-rank
and local-support verdict fields, plus a safe abstention kind on new assistant
messages. Existing private history remains readable with null kinds. The `0019`
upgrade adds the encrypted validated-candidate table, generation attempt-quality
history and `awaiting_card_choice` state/indexes. Drain API admission and all
generation/answer workers, take and restore-verify a backup, migrate, then
recreate API, generation worker, answer worker and frontend together. Keep the
same source-storage key while any pending choice exists. New candidate storage
limits and retention come from the root `.env` template/validated defaults; do
not regenerate the operator's root `.env` or installation secrets.

The `0020` upgrade only expands the Ask stage constraint and partial unique
index to cover the staged v2 answer contract. It does not change the release
policy constant, local support factory, or existing v1 jobs. Drain the answer
worker and take a restore-verified backup before applying it on a populated
installation. Recreate the API and answer worker from matching source and
confirm their migration head checks. The v2 contract remains historical and
permanently fenced for new Ask work; it is not a future answer mode.

The `0021` upgrade adds job-owned source references and offsets for at most two
related Knowledge excerpts. It adds no duplicated quote text or provider work.
Drain the answer worker, take and restore-verify a backup, then migrate and
recreate the API, answer worker and frontend from the same checkout. Existing
jobs have no excerpt references and continue to return an empty list. API reads
reauthorize current Knowledge before reconstructing a quote. Downgrade refuses
to remove the new table while it holds rows; retain the pre-upgrade backup and
make any rollback decision explicitly instead of deleting those rows.

The `0022` upgrade conditionally separates source-only embedding identity and
`related_knowledge`/`no_match` completion from historical answer snapshots. It
requires no assistant message for those new result kinds, allows at most three
references and limits source-only stages to one query embedding and local
retrieval with zero retries. The `0023` trigger prevents a stage with a null or
different policy, or different current attempt numbers, from disguising its
source-only parent and bypassing those limits. Upgrade preflight refuses
inconsistent retained source-policy rows rather than relabelling them.
Drain writers/workers, preserve and restore-verify a populated installation's
backup, migrate and check heads/drift, then recreate API, workers and frontend
from matching source-only images. Keep Ask disabled until its displayed-window,
access and release gates pass. Source-only workers must not execute old-policy
jobs; use the documented drain/fence process, not reinterpretation or replay.

The `0028` upgrade admits only the immutable
`related_knowledge_navigation_v3`/`hybrid_source_navigation_v9` pair in the
existing source-only job, reference and stage guards. It changes no source
pages, vectors, original-PDF archives or historical job snapshots. Keep Ask
off and drain writers before migrating; verify current heads and model drift,
then recreate the API, answer worker and frontend from matching code before
restoring ordinary traffic. The separate enrolled-student published-Knowledge
browse/search and original-PDF page routes can operate while Ask admission is
off, but require the same current authorization, publication and revision
checks and a readable original-PDF archive for PDF display. The `0028`
schema migration itself is not evidence that the Ask usefulness/release gate
has passed.

The historical `0029` upgrade admits only the prospective
`related_knowledge_navigation_v4`/`hybrid_source_navigation_v9` pair. Eight
nullable job fields snapshot the Gemini source judge endpoint, model, contract,
prices and token limits; earlier jobs must keep them null. The v4-only
`source_judgment` stage is bound to the parent job and current attempt. Database
guards permit at most one physical query-embedding request and one physical
source-judgment request per attempt, with zero automatic retries. V4 canonical
page references require a completed successful judgment stage for that attempt;
`clarification_needed` has no references and is allowed only before either
remote stage. Older v3 jobs and source reads retain their policy. This migration
does not alter pages, vectors, original-PDF archives or embedding spaces, and
it makes no provider request.

For a populated installation, keep Ask admission disabled, drain the API and
answer worker, and confirm no pending job will be executed under a different
policy. Preserve the root `.env`, populated volume and original-PDF encryption
key. Take and restore-verify a backup before applying `0029`; then check heads
and model drift using the commands above. Recreate the API, answer worker and
frontend from matching source before restoring ordinary traffic. Verify old
v3 history remains readable and the independent published-Knowledge browse,
search and current-authorized original-PDF page/range paths still work. Keep
Ask disabled until the public pilot, private original-PDF usefulness,
authorization, browser/accessibility and operational release gates in
[ADR-024](decisions/ADR-024-gemini-source-id-judge.md) pass. A configured
provider key or successful migration does not authorize paid calls, transfer
private Knowledge or activate Ask; each live pilot needs its separate approved
request and cost envelope.

The historical `0030` upgrade added immutable v5 visual source judgment while
preserving v4 rows and constraints. Judge snapshots include thinking level
and timeout; v5 binds `visual_source_id_v1`, Flash-Lite/HIGH, 32,768 input,
2,048 output including thinking, 60 seconds and one physical judgment per
attempt. Original-PDF bindings and current access/revision checks remain
required. The populated installation reached `0030` after a checksum-verified
backup and separate-database restore; heads, model drift and aggregate counts
matched before ordinary services restarted. Do not rewrite installed `0030`
to adopt the prospective 4,096-token public candidate: a matching successor
requires a new policy/contract and additive migration after measurement.
Never downgrade retained data for testing. Disposable downgrade/re-upgrade
checks are separate from this forward cutover; downgrade refuses v5 rows.
The earlier additive `0031` installs the measured-budget v6/visual-v2
successor while retaining that history, and refuses downgrade with v6 rows.
Its restore-verified retained cutover and exact preserved counts are recorded
in the [v6 verification](../.agent/logs/2026-10-01/2026-10-01-visual-v6-matching-contract-and-backup.md).
The earlier additive `0032` binds v7/visual-v3 immutable admission context
without rewriting those historical rows; its retained forward upgrade and
disposable downgrade/re-upgrade evidence are linked in the dated v7 section.
The current `0033` successor adds the exact v8/visual-v5/admission-v2 pair;
both historical and current rows retain their original policy semantics.
Ask remains disabled; source migration does not satisfy independent quality
or release gates.

The Lane 6 validated-candidate payload policy now authenticates the duplicate
threshold used when candidates were generated. This is an application-policy
update within schema `0019`, not another Alembic migration. Before recreating
the generation worker/API with this policy, let any pending v1 card choices be
confirmed or expire, or explicitly resolve them with their owner. A v1 staged
payload cannot reconstruct that threshold and its later confirmation fails
closed; a new paid attempt still requires the owner's cost acknowledgement.
Do not delete pending rows or rotate the source key as a migration shortcut.

The vector foundation migration checks the installed/available extension version
and schema. A compatible preinstalled extension does not require the application
role to create it. Otherwise a database administrator must preinstall
`CREATE EXTENSION vector WITH SCHEMA public VERSION '0.8.6'` or authorize an
appropriately privileged migration role. The application does not automatically
upgrade an incompatible existing extension. Fixed migration errors omit SQL
exception details; do not stamp past them. Verify `extversion` and its namespace
from `pg_extension` after migration and restore.

Downgrading revision `20260918_0009` deliberately leaves the extension installed:
it can have other consumers, and Alembic cannot infer ownership from its presence.
Application-schema downgrades must remove dependent application objects first.
Never use `DROP EXTENSION ... CASCADE` or downgrade a populated operator database
as a test. The disposable [vector recovery harness](../scripts/test_pgvector_restore.py)
checks infrastructure dump/restore with synthetic vectors and indexes; actual
Knowledge-table recovery is verified separately by the guarded
[PostgreSQL Knowledge restore test](../backend/tests/postgres/test_postgres_knowledge_recovery.py)
with a populated 1,536-dimensional vector and two disposable child databases.
Downgrading `20260918_0010` removes all Subject Knowledge documents, pages,
chunks, vectors, indexing jobs and counters, and detaches its job/set links.
Use it only in disposable verification or after an explicitly authorized,
verified backup and product rollback decision; a real recovery normally
restores the pre-upgrade archive into a separate target.

Downgrading `20260919_0011` removes Knowledge-only queue receipts, capture/index
execution fields and local chunk mappings before restoring the Phase 13 model.
The durable documents/revisions themselves remain until an `0010` downgrade,
but this is still a lossy operational rollback. Stop generation/index workers,
take and verify a backup, and prefer restoring the pre-upgrade archive into a
separate target. Normal verification exercises the downgrade only on a generated
disposable database.

Downgrading `20260920_0013` is deliberately lossy. The Phase 12 schema cannot
represent native Gemini spaces, so the downgrade deletes Gemini-indexed
conversation/index revisions and clears affected active cutovers while
preserving canonical extracted pages for a future reindex. It also removes the
new request/timing fields and Phase 21 Knowledge lifecycle audit rows. Stop all
RAG admission/workers, export required private history and verify a backup
before an authorized rollback; ordinary downgrade testing uses only a generated
disposable database.

## Subject Knowledge reindex and cutover

Changing any embedding-space setting does not mix vectors or silently activate
a partial corpus. After configuring the index worker, stage a new index for
every active ready content revision, wait for all jobs to become ready, then
perform the explicit all-or-nothing cutover:

```powershell
docker compose run --rm backend python -m app.cli rag-stage-reindex --subject-id SUBJECT_UUID --owner-id OWNER_UUID --apply
docker compose exec backend python -m app.cli operations-status
docker compose run --rm backend python -m app.cli rag-cutover --subject-id SUBJECT_UUID --owner-id OWNER_UUID --space-hash LOWERCASE_64_HEX_HASH --apply
```

Staging is idempotent for an existing pending/indexing/ready target. Cutover is
refused unless every active ready content revision has a ready index in the
target space; a failure leaves the prior active space usable. Unpublication or
deletion changes the corpus fence, and stale retrieval/index claims fail closed.
The CLI prints no document text, vectors, provider payloads or credentials.

## Moving the prior Debian installation to the reviewed Alpine build

This runtime change requires a logical restore into a **separate empty volume**.
Do not start the Alpine database container on the old Debian/libc data volume:
its data-directory path and PostgreSQL major version alone do not establish
locale or text-index compatibility. Fresh reviewed clusters use UTF-8 and ICU
`en-US`; restore recreates text indexes under the target's collation.

Drain all application writers/workers using the existing source runtime, take
and checksum its custom-format backup, and preserve the original volume and
source encryption key. Build/verify the reviewed database recipe, initialize
a separately named empty target, restore the archive, then apply the new
Alembic heads. Verify extension schema/version, heads/drift, expected rows,
valid indexes, representative Unicode uniqueness/order and application behavior
before pointing traffic at that target. Keep the old volume available for an
explicit rollback decision; never fix a failed restore by stamping a head or
deleting that volume. A real cutover remains an operator deployment action.

Native installations retaining compatible libc/ICU binaries and locale may
follow their supported platform's normal extension installation procedure;
a platform/locale change needs the same separate logical-target rehearsal.
After a collation library upgrade, identify and rebuild affected indexes before
refreshing recorded collation versions. See the PostgreSQL 16
[locale contract](https://www.postgresql.org/docs/16/locale.html) and
[collation-version guidance](https://www.postgresql.org/docs/16/sql-altercollation.html).
The disposable [prior-installation harness](../scripts/test_database_volume_upgrade.py)
exercises this source/target contract with generated data; it is not an
operational migration command.

## Backup

Create the destination directory yourself and keep it outside source control.
The custom archive format supports selective inspection and restore:

```powershell
New-Item -ItemType Directory -Force backups
docker compose exec -T db pg_dump -U admin -d cardchemy --format=custom --no-owner --file=/tmp/cardchemy.dump
docker compose cp db:/tmp/cardchemy.dump backups/cardchemy.dump
```

Record the application version, Alembic revision, UTC timestamp, and archive
checksum next to the backup. Store production archives encrypted with access
restricted to database operators. Preserve the source encryption key separately
in protected disaster-recovery material if queued/retryable jobs must survive a
restore. Never commit either artifact.

## Restore rehearsal

Test every important backup in a separately named database; do not overwrite the
active database during a rehearsal:

```powershell
docker compose cp backups/cardchemy.dump db:/tmp/cardchemy.dump
docker compose exec -T db createdb -U admin cardchemy_restore_test
docker compose exec -T db pg_restore -U admin -d cardchemy_restore_test --no-owner --no-privileges /tmp/cardchemy.dump
docker compose exec -T db psql -U admin -d cardchemy_restore_test -c "SELECT version_num FROM alembic_version;"
```

Verify expected table counts and a representative instructor/student journey
against the restored database before declaring the backup usable. After that
verification, explicitly remove only the rehearsal database:

```powershell
docker compose exec -T db dropdb -U admin cardchemy_restore_test
```

For an actual restore, stop application writers, create a fresh empty target
database, restore the archive, run `alembic upgrade head`, verify the revision
and counts, and only then point the application at the restored database.

Repeat this rehearsal with release-specific data and record the result in the
release evidence. Prior development rehearsals are recorded in `.agent/logs/`.

## Downgrade and rollback

Inspect the history and downgrade exactly one revision only after confirming the
target revision's downgrade is safe for the data in use:

```powershell
docker compose run --rm backend alembic history
docker compose run --rm backend alembic downgrade -1
docker compose run --rm backend alembic current
```

Downgrading `20260928_0029` refuses any retained v4 source-judgment job,
including terminal `no_match` or `clarification_needed` jobs without references.
When no v4 job exists, it restores the exact v3/v9 guards and removes the v4
snapshot fields and stage constraints. Do not delete private job history to
force a rollback. On a populated installation, keep Ask disabled and prefer a
forward repair or a restore-verified pre-upgrade backup into a separate target.

Downgrading `20260927_0028` refuses any retained navigation-v3 job, including
a terminal or no-match result. It restores the exact v2/v8 guards only when
no v3 job snapshot exists; it does not relabel or remove historical rows. On
a populated installation, keep Ask disabled and prefer a forward repair or a
restore-verified backup into a separate target over deleting jobs to force a
rollback.

Downgrading `20260927_0027` refuses any retained navigation-v2 job, even a
terminal/no-match result. It restores exact old policy guards without rewriting
history. Downgrading `20260927_0026` refuses while original-PDF archives remain;
never delete them to force rollback. Prefer disabling Ask, a forward repair or
an authorized restore to a separate target. Before upgrade, drain writers,
verify a database backup and the independently stored PDF key. After upgrade,
check heads/drift, exact archive identity and current-access range reads before
restoring traffic. Exact old-PDF attachment does not trigger indexing or change
content revision; paid reindexing remains a separate decision.

Downgrading `20260927_0025` refuses while any v7 job snapshot remains, including
terminal/no-match jobs with no references. It restores the exact v6 insertion
guard only after that check; it never relabels or deletes historical jobs.
Preserve history and prefer feature disable plus a forward repair.

Downgrading `20260927_0024` refuses while any canonical-page reference exists:
its offsets cannot safely be interpreted as chunk offsets. Preserve references
and prefer Ask shutdown plus a forward repair, or an explicitly approved
restore into a separate target. Do not delete references to force a downgrade.

Downgrading `20260926_0023` removes the stage-parent trigger and function, which
would remove an enforcement layer while `0022` constraints remain. This is not
a rollback to an answer policy. Downgrading `20260926_0022` refuses while any
source-only Ask job exists. Do not remove jobs or references to force either
rollback; prefer disabling Ask and repairing source-only behavior, or restoring
an explicitly approved pre-upgrade archive into a separate target. The empty
upgrade/head/drift, downgrade to base and re-upgrade checks passed on a
disposable PostgreSQL database, not the retained operator database.

Downgrading `20260925_0021` refuses while any related-evidence reference row
exists. Preserve those private references and use the verified pre-upgrade
archive in a separate target for a rollback decision; do not remove rows just
to force a downgrade. Its empty-table downgrade and re-upgrade passed on a
disposable PostgreSQL database. Downgrading `20260925_0020` refuses while any
v2 answer job or stage row exists;
older schema would not enforce the v2 physical-request cap. Its disposable
downgrade and re-upgrade passed without such rows. Downgrading `20260925_0019`
refuses while any encrypted candidate stage,
pending/selected smaller-target choice or generation attempt-quality history
exists. Downgrading `20260925_0018` refuses while retained Ask diagnostics or
typed abstention history exists. Do not delete these private/user-visible rows
to force a rollback. Restore a verified pre-upgrade archive into a separate
target, or keep the new schema and disable new Ask/generation admission while
repairing the application. On disposable databases, verify upgrade, downgrade
and re-upgrade before release. Backup and source-key rotation must account for
pending encrypted card choices and their temporary PDF sources.

Downgrading `20260922_0017` is refused while any two-request/local-support job
or local-support stage row exists. The older worker cannot represent or safely
execute those snapshots; restore a verified pre-upgrade backup or remain on
0017. Downgrading `20260922_0016` is refused while any
`gemini2_qa_section_v1` space exists. Restore every Subject/process to 001 and
remove a model-2 space only through an explicit data-retention decision; never
relabel it to satisfy the old check.
Downgrading `20260922_0015` is refused if any job is awaiting a duplicate choice,
has a `reused` or `unchanged` capture status, or retains any typed Knowledge
upload outcome. The prior schema cannot represent those decisions. Before the
feature is used, a disposable downgrade can remove the nullable fields and old
active-status extension. After outcomes exist, prefer restoring a verified
pre-upgrade backup into a separate target or remain on `0015`; do not delete
retained job history merely to force a rollback.
Downgrading `20260922_0014` next removes Gemini catalog snapshots and the
content-free per-stage Ask diagnostics. The old constraint cannot represent
jobs terminally marked `rag_ask_shutdown`; restoring a verified pre-upgrade
backup is safer than rewriting their private history. Practice this downgrade
on a disposable database whose retained rows satisfy the old constraint.
Downgrading `20260920_0013` then applies the native-Gemini and audit loss
described above. Downgrading `20260919_0012` permanently drops all stored Ask AI conversations,
citations, answer-job history and answer quota receipts and removes the answer
worker heartbeat kind. Stop API/answer admission, drain or cancel answer jobs,
and export any required private history first. Downgrading `20260917_0008` drops request/heartbeat/audit history, origin request
correlation and the role audit trigger. Stop writers/workers and preserve
required audit evidence before an explicitly authorized operational rollback;
ordinary rehearsal uses only disposable databases. [Privacy controls](PRIVACY.md)
define account/export/metadata cleanup separately from schema rollback.
Downgrading `20260916_0007` changes the per-stage request map back to JSON.
Downgrading `20260916_0006` removes AI request-efficiency telemetry but leaves
generation jobs and their earlier token/cost telemetry intact. Downgrading
`20260915_0005` removes every email outbox row and emailed-invitation
recipient binding. Stop the email worker and drain, inspect, or intentionally
discard all pending and failed email before that downgrade. Downgrading
`20260915_0004` removes study-answer idempotency receipts. Downgrading
`20260914_0003` removes AI telemetry/provenance fields and restores
the legacy confidence/source column names. Downgrading `20260914_0002` removes generation jobs, temporary sources, quota
history, and job/result links. Stop the API and worker and drain or cancel jobs
before doing so. Downgrading the `20260914_0001` baseline to `base` drops the
entire schema and all application data, so it is only appropriate for an empty
test database or after a verified backup. Production recovery should normally
restore the pre-upgrade archive into a fresh database instead.

## Failed migration recovery

PostgreSQL runs these migrations in a transaction. If an upgrade fails, preserve the
error output, confirm `alembic current`, correct the migration or environment,
and retry. Do not use `alembic stamp` to bypass a failed migration. If a change
was non-transactional in a future revision, follow that revision's explicit
recovery notes or restore the pre-upgrade backup.

The [production recovery rehearsal](PRODUCTION_REHEARSAL.md) automates the
current-head custom backup/checksum, separate empty-volume restore, upgrade,
head/drift and representative instructor/student receipt/progress checks on a
fresh runner. It uses generated fixtures and removes only resources whose
rehearsal ownership is verified.
