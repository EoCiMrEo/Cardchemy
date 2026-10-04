# Maintained test commands

## Current local Lane 6 closure — 2026-10-04

The local source-only v8/visual-v5/admission-v2 installation on head `0033`
is enabled after its measured quality, PDF/display and release gates. Fresh
installations remain default-off. See the
[closure and activation evidence](../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md). Earlier installation
checkpoints below remain historical snapshots; the linked closure supersedes
their off/pending status, while default-off and upgrade safeguards still apply.

## Published sparse whole-source control

`python scripts/test_sparse_generation_control.py` uses the unchanged guarded
PostgreSQL service runner for one independently reviewed authored whole-PDF
control. It exercises actual capture/index/review/publication and generation
shortfall, encrypted staging, exact smaller-target confirmation, replay/access
denials and cleanup. Only its providers are scripted offline. The
[completed evidence](../.agent/logs/2026-10-03/2026-10-03-published-sparse-whole-pdf-control.md)
records one passing test and zero remote requests; it is not live sparse lecture
yield. Do not run it against the retained installation or supply operator keys.

## Current dormant v8 verification — 2026-10-03

Current source and retained schema head are `20261002_0033`. The retained
forward migration, restore rehearsal and heads/drift checks completed with Ask
and source judging disabled. The current pairing is
`related_knowledge_navigation_v8` / `visual_source_id_v5` /
`literal_subject_admission_v2`; historical v7 rows remain readable but cannot
execute or retry under v8. Routine tests inject synthetic settings, omit live
and service opt-ins, and do not authorize provider execution.

From `backend`, the focused current contracts are:

```powershell
venv/Scripts/python.exe -m pytest -q tests/test_source_judgment_visual_v5.py tests/test_rag_question_context_v2.py tests/test_source_visual_v5_provider.py tests/test_visual_clarity_policy_migration.py
venv/Scripts/python.exe -m pytest -q tests/test_private_navigation_v8_preparation.py tests/test_private_navigation_seed_v8_preparation.py tests/test_private_visual_dispatch_guard_v8.py tests/test_private_visual_trial_v8_preflight.py tests/test_private_source_display_v8_score.py tests/test_private_visual_trial_v8_caller.py tests/test_execute_private_visual_trial_v8.py tests/test_private_visual_trial_launch_v8.py
```

Then run the full offline command in the table below and the disposable
PostgreSQL, frontend, journey and affected image/release checks. The PostgreSQL
scope includes both `test_postgres_visual_clarity_policy.py` and the independent
`test_postgres_visual_clarity_v8.py`: v7/v8 coexistence, exact profile/context
pairing, NULL and mutation guards, predecessor lifetime, parent-policy checks,
one physical attempt and no answer/verifier stages. SQLite contracts alone do
not establish those database properties.

The recorded full offline snapshot run passed **5,298 tests**, with **270 skipped**
cases and **two live AI cases deselected**, in **451.92 seconds**. Skips include
separately gated service and optional local-artifact checks.
All 448 scoped backend Python/config input hashes were unchanged during that
run. Service, provider, browser and release outcomes remain separately scoped.

The complete public sixty-case source-selection gate passed with 94/99 useful
displayed cards. It does not establish private current-source selection,
successful browser opening of selected PDF pages, spoken assistive-technology
verification or release enablement. See the
[current backend reconciliation](../.agent/logs/2026-10-03/2026-10-03-v8-full-offline-reconciliation.md)
and [independent boundary review](../.agent/logs/2026-10-03/2026-10-03-v8-runtime-independent-boundary-review.md).
The dated sections below preserve their earlier installation and test snapshots.

### Separate seed14 diagnostic preparation

The fixed eleven positive seeds, N12 positive source control and two restricted
wrong-source slates use a separate 14-case/50-slot diagnostic. Its independent
source review and exact reuse witness are SHA pinned, **not signed**. It does not
replace the signed private12 holdout, prove corpus-wide absence, or authorize
provider transfer. The existing v8 helpers and stages remain independently bound.

```powershell
venv/Scripts/python.exe -m pytest -q tests/test_private_seed_visual_trial_v1.py
```

Run this from `backend` with injected synthetic settings. The new preparation,
1–4-source guards, controller/host, one-use custody and supplied-selection scorer
stay inert without separate external authority. Passing synthetic tests and
keyless fresh SQL/PDF guards do not establish actual selected-source usefulness
or browser PDF opening. The [dated preparation evidence](../.agent/logs/2026-10-03/2026-10-03-private-seed-visual-v1-preparation.md)
records exact frozen inputs and resource limits. These helpers were added after
the full offline snapshot above; their focused check is separately recorded.

## Prospective parser and learning-question correctness repairs

From `backend`, run the synthetic contracts without provider quota:

```powershell
venv/Scripts/python.exe -m pytest -q tests/test_source_judgment_visual_v4.py tests/test_source_navigation_context_v2.py tests/test_source_navigation_context_v2_independent_review.py
```

These prove conservative candidate exclusion, global validation and narrow
question routing. They do not integrate or activate a runtime policy, recover
old failed responses, or replace independent source/PDF quality measurement.
See the [repair evidence](../.agent/logs/2026-10-02/2026-10-02-candidate-local-and-question-clarity-repair.md).

## Historical retained v7 context integration — 2026-10-02

Source and retained head are `20261002_0032`, with healthy matching services
and Ask/source judging off.
New v7/visual-v3 contracts include immutable admission/strict predecessor,
post-quota access/context checking, literal-only transfer and typed disclosure.
Run the focused contracts below from `backend`, then the existing full offline,
PostgreSQL, frontend and journey gates. Current offline (4,289), disposable
PostgreSQL (187), full frontend/bundle and both RAG-on/off journeys passed;
retained heads/drift and image smoke also passed. See the
[cutover/recheck record](../.agent/logs/2026-10-02/2026-10-02-v7-retained-cutover-and-release-recheck.md)
and [browser/security verification](../.agent/logs/2026-10-02/2026-10-02-v7-pdf-browser-and-security-verification.md).
Independent displayed-source quality and spoken assistive-technology gates
remain separate and open.

```powershell
venv/Scripts/python.exe -m pytest -q tests/test_rag_question_context.py tests/test_literal_subject_context_models.py tests/test_literal_subject_context_migration.py tests/test_rag_context_admission.py tests/test_visual_v3_worker_context.py tests/test_source_visual_v3_provider.py tests/test_source_visual_preparation_v3.py
```

Routine tests use invented credentials/data and never execute an approved live
caller. Public/private provider trials require their separate exact envelope.
The dated v6 section below is the retained installation's earlier verification.

## Historical dormant visual Ask contract — 2026-10-01

Source and retained schema are `20261001_0031`; matching API/workers/frontend
are healthy with Ask disabled after a restore-verified forward cutover. The
prepared `related_knowledge_navigation_v6` / `hybrid_source_navigation_v9`
path authenticates the complete current PDF archive before isolated Poppler
rendering, binds exact text and up to four bounded page PNGs, and permits
at most one query embedding plus one ID/category-only source judgment.
It makes no answer/verifier call or automatic retry. The archive key is also
required by the answer worker; provider keys remain isolated to their roles.

The current dormant application contract `visual_source_id_v2` uses
Gemini 3.5 Flash-Lite, HIGH thinking, 32,768 input / 4,096 output tokens
including thinking and a 60-second provider deadline. Adaptive full-page
rendering only reduces scale after definitive PNG oversize. Complete public
calibration passed; independent heldout preparation authorizes no provider
calls. Historical v5/v1 snapshots remain fenced and unchanged. The user's
prospective release target is 80% displayed usefulness, at least 10/12
conclusive no-match controls and all existing hit/availability gates.
Fabricated, unauthorized, stale or wrong-page references still require zero.
Independent different-PDF and private/release gates remain open.

See the [current verification record](../.agent/logs/2026-10-01/2026-10-01-visual-v6-matching-contract-and-backup.md).
Earlier v4 details below describe retained historical policies where they differ.


Use the backend Python 3.13 development environment installed from
`backend/requirements-dev.txt` with `--require-hashes`, and the frontend Node
24/npm 11 environment installed with `npm ci`. Run commands below from the
repository root unless a working directory is specified.

| Suite | Authoritative command | Required setup and expected gating |
| --- | --- | --- |
| Current private v8 preparation and signed-review bridge | `venv/Scripts/python.exe -m pytest tests/test_private_navigation_v8_preparation.py tests/test_private_navigation_seed_v8_preparation.py tests/test_private_source_display_v8_score.py -q` from `backend` | Keyless raw-current-question/literal-subject resolution under v8/visual-v5/admission-v2, simulated evaluation admission and unchanged read-only/vector/source guards. Matching real packet/runtime pins, independent exact-source labels and fresh provider-transfer authorization are separate; candidate recall does not establish selected-card usefulness or activation. |
| Historical private v7 preparation and signed-review bridge | `venv/Scripts/python.exe -m pytest tests/test_private_navigation_v7_preparation.py tests/test_source_visual_preparation_v3.py tests/test_private_source_display_v7_score.py -q` from `backend` | Keyless historical raw-question/literal-subject resolution, simulated evaluation admission, preserved read-only/vector/source guards and unchanged independently signed v6 labels. New runtime/request/admission hashes are separate; changed source/cue/page/PNG/current or preceding question requires fresh review. Candidate recall does not establish selected-card usefulness or activation. |
| Dormant private v6 query execution caller | `venv/Scripts/python.exe -m pytest tests/test_private_query_vectors_v6_caller.py tests/test_private_query_vectors_v6.py tests/test_private_query_vector_builder.py -q` from `backend` | Synthetic authorization/code/input/profile/no-replay and process-role isolation, durable aggregate evidence, local venv wrapper PID handling and mocked native singleton transport. Default caller is inert; exact fresh provider approval remains mandatory. No real profile/source/key/network or release result. |
| Current private v6 hybrid-input preparation | `venv/Scripts/python.exe -m pytest tests/test_private_navigation_v6_preparation.py tests/test_private_query_vectors_v6.py tests/test_private_source_gold_v4_snapshot.py -q` from `backend` | Synthetic input/vector/source pins, current SQL authorization, exact production hybrid/visual inputs, read-only rollback and private artifact bounds. Explicit execution requires isolated finite <=4 CPU/2 GiB cgroups and a hard 300-second outer process deadline. No real source, provider, credential, DB write or display-quality claim. |
| Public heldout transport successor preparation | `venv/Scripts/python.exe -m pytest tests/test_visual_public_heldout_v2_caller.py -q` from `backend` | Synthetic bindings for three same-heldout successes, preserved six historical attempts and costs, all sixty-case gates, 57 fresh-call roster, 120-second deadline, 30-second spacing and cooldown before a different question after HTTP503. Live authorization is false; a fresh exact envelope is required. No installed-runtime change. |
| Current private v6 question-vector preparation | `venv/Scripts/python.exe -m pytest tests/test_private_query_vectors_v6.py tests/test_private_query_vector_builder.py tests/test_private_source_gold_v4_snapshot.py -q` from `backend` | Keyless current-question/source-hash bindings, exact native singleton batch endpoint, compatible space, independent fresh authorization and durable no-replay claim, checkpoint/failure/privacy contracts. CLI is preparation-only; no real vector or hybrid/display quality is established. Provider execution needs its own exact approved envelope and resource-fenced caller. |
| Current private v6 display metric | `venv/Scripts/python.exe -m pytest tests/test_private_source_display_v6_score.py tests/test_source_judgment_display_v4_score.py tests/test_private_source_gold_v4_bridge.py tests/test_private_source_gold_v4_snapshot.py -q` from `backend` | Synthetic 80% all-card/full-case boundaries, independent signed review ordering/key/hash bindings, issued-source/PDF hashes, 10/12 and 3/4 hit gates, N12/U01, one embedding/judgment and zero answer/verifier/retry budgets. Historical v4 contracts remain unchanged. No provider/private input/DB or real display quality is established; runtime release stays false. |
| Independent visual public heldout preparation | `venv/Scripts/python.exe -m pytest tests/test_visual_public_heldout_v1_caller.py tests/test_visual_public_heldout_v1_score.py tests/test_visual_public_heldout_review_v1.py tests/test_visual_public_heldout_input_v2.py -q` from `backend` | Synthetic complete 60-group scoring, blind tri-state qualification, full-page adaptive bindings, calibration admission, fresh authorization before key access, resource/usage/cost/spacing/no-replay guards. Preparation and preflight are keyless; separate precise authorization is mandatory before any heldout provider call. |
| Visual continuation preparation | `venv/Scripts/python.exe -m pytest tests/test_visual_public_calibration_v5_caller.py tests/test_visual_public_calibration_v5_launch.py tests/test_visual_public_calibration_v5_score.py -q` from `backend` | Keyless 20-valid-receipt reuse, preserved six historical failures/costs, prospective 47-call/4,096-output guards, 80% usefulness and 10/12 no-match. Fresh precise provider approval required; old pilots stay failed. |
| Public visual 60-second trial preparation | `venv/Scripts/python.exe -m pytest tests/test_visual_public_calibration_v4_caller.py tests/test_visual_public_calibration_v4_launch.py -q` from `backend` | Synthetic five-success/three-prior-failure bindings, 62-call cap, no replay, separate costs, 60-second transport and four-CPU/two-GiB supervisor; a fresh exact envelope is required before live calls. |
| Pure visual source-ID contract and worker archive read | `venv/Scripts/python.exe -m pytest tests/test_source_judgment_visual.py tests/test_knowledge_pdf_worker_read.py tests/test_knowledge_pdf.py -q` from `backend` | Synthetic cue/source/PNG bindings, closed IDs/status, thinking/request limits and complete archive authentication. Helpers are connected to dormant v5; these checks do not establish model quality or enable Ask. |
| Backend offline | `python -m pytest -q` from `backend` | Core test configuration is injected; PostgreSQL and Mailpit cases skip without their dedicated process values; live AI is deselected. |
| Public source-usefulness annotation contract | `venv/Scripts/python.exe -m pytest tests/test_source_usefulness_contract_audit.py tests/test_source_contract_summary.py -q` from `backend` | Synthetic blind-packet preservation, complete tri-state admission, wire-before-PDF sealing, blind disputes and complete-denominator finalization; no corpus, provider, private data or quality inference. |
| Public visual-page input and source verdict contracts | `venv/Scripts/python.exe -m pytest tests/test_visual_page_source_input.py tests/test_visual_page_source_judge.py tests/test_visual_source_feasibility_review.py -q` from `backend` | Synthetic PNG/bytes/source binding, immutable freeze, resource admission, exact four-page wire, closed ID/status parsing and clarification without weak padding; deterministic agreed-weak sampling preserves uncertain judgments. Tests use no real PDF, provider, credential, heldout or private Knowledge. The separately approved offline preparation is limited to four cached public PDFs / 80 cited pages; it is not model-quality evidence or permission to invoke Gemini. |
| Public visual semantic/control reconciliation | `venv/Scripts/python.exe -m pytest tests/test_visual_semantic_control_v2.py tests/test_visual_semantic_summary_v2.py -q` from `backend` | Synthetic discovery/clarification, opaque image projection, external-freeze replacement regression, complete tri-state reviews and conservative complete-denominator bounds. Missing relations remain misses; conflicting/unknown sources receive no usefulness or no-match credit. One independently reviewed additional control may bring the request denominator to 67 without removing any of the original 66 cases. No provider, real environment, private Knowledge, heldout, database or runtime is used; input bounds do not establish Ask accuracy. |
| Public visual calibration caller/scorer/supervisor | `venv/Scripts/python.exe -m pytest tests/test_visual_public_calibration_v2_score.py tests/test_visual_public_calibration_v2_caller.py tests/test_visual_public_calibration_v2_launch.py -q` from `backend` | Invented 67-group rosters, shuffled source/review bindings, complete-denominator stop math, ID/usage/HTTP/token/cost guards, no replay, spacing and credential isolation. On Windows a synthetic child verifies its named four-CPU/two-GiB resource ancestor before work. No provider call, real credential, source PDF, heldout or private Knowledge is used. Actual calibration remains separately one-use approved and SHA-bound. |
| Checkpoint-bound public visual calibration v3 | `venv/Scripts/python.exe -m pytest tests/test_visual_public_calibration_v3_score.py tests/test_visual_public_calibration_v3_caller.py tests/test_visual_public_calibration_v3_launch.py -q` from `backend` | Synthetic exact-80% and below-80% boundaries, full 67-case hit/availability/no-match gates, immutable prior-receipt admission, no duplicate provider attempts, old/new cost separation and resource/authorization-before-key fences. Default preparation is keyless; a full model score needs a separate precise live envelope. The four exposed receipts are calibration data only and partial 4/5 is not a pass. |
| Public source-navigation selective audit contracts | `venv/Scripts/python.exe -m pytest -q tests/test_reading_usefulness_selective_audit.py` from `backend` | Keyless synthetic tests for split/label boundaries, two separate classifiers, calibration-before-heldout, fixed ledger and fail-closed resource/protocol handling. The single approved networkless model run stopped at calibration; its fixed ledger is consumed. Never run `--execute-approved` as part of tests or CI. See the [frozen audit record](../.agent/logs/2026-09-28/2026-09-28-selective-navigation-frozen-audit.md). |
| Public source-navigation groupwise audit contracts | `venv/Scripts/python.exe -m pytest -q tests/test_reading_usefulness_groupwise_audit.py` from `backend` | Keyless synthetic tests for the fixed count-cap/per-card rule, split/label boundaries, calibration-before-heldout and one-shot resource/ledger guards. The one approved networkless model run stopped at calibration after 20 calls; the heldout was not scored and its ledger is consumed. Never run `--execute-approved` as part of tests or CI. This public experiment does not select an Ask runtime policy. |
| Failure-inclusive public source-ID continuation contracts | `venv/Scripts/python.exe -m pytest -q tests/test_public_source_id_multipdf_35_lite_continuation.py tests/test_public_source_id_multipdf_35_lite_continuation_caller.py tests/test_public_source_id_multipdf_35_lite_caller.py tests/test_public_source_id_multipdf_35_lite_score.py` from `backend` | Keyless fake-transport checks for pinned prior receipts, no replay of group 11, 46/48 availability, all-displayed source usefulness, exact approval/caller hashes, no retries and conditional heldout. The separate preapproval CLI is zero-call; never run its `--execute` mode as a routine test or without a fresh exact live envelope. |
| Exhaustive public source-ID prototype | `venv/Scripts/python.exe -m pytest -q tests/test_exhaustive_source_id_public_prototype.py` from `backend` | Keyless admission and parser bounds for an inactive four-page ID-only request. This checks no source usefulness; the previous public calibration failed and a new independently reviewed corpus/live envelope is still needed. |
| Public full-cue high-thinking candidate | `venv/Scripts/python.exe -m pytest -q tests/test_full_cue_high_thinking_public.py` from `backend` | Keyless synthetic tests for disabled live authorization, unchanged public cue/prompt binding, selected-ID receipts, known usage/latency, optimistic all-gate early stop and calibration-before-heldout. The detached fake child uses no provider or credential. Real public preflight reads all eight PDF files for integrity but leaves heldout questions/labels/outcomes gated. No model quality or Ask activation is established. |
| High-thinking HTTP transport regression | `venv/Scripts/python.exe -m pytest -q tests/test_high_thinking_http_envelope.py` from `backend` | Keyless synthetic 8/64 KiB envelope boundaries, strict 2 KiB verdict JSON, token/ID guards, mock HTTP stream without retry, unchanged request bytes, no raw metadata retention and calibration-before-heldout. A distinct exact public-only v2 pilot is approved under its own one-use ledger; this routine test is not a live invocation or quality result. See the [approved scope](../.agent/logs/2026-10-01/2026-10-01-high-thinking-transport-pilot-approved-scope.md). |
| Fresh public source-ID PDF acquisition contract | `venv/Scripts/python.exe -m pytest -q tests/test_acquire_fresh_public_source_id_corpus_v2.py` from `backend` | Fake-transport and one-use approval tests only; routine tests make no HTTP request. The bounded downloader's offline `--preflight` checks actual public comparison manifests and an unused Temp output, but does not authorize `--execute` or establish source usefulness. |
| Fresh public source-ID packet and score contracts | `venv/Scripts/python.exe -m pytest -q tests/test_prepare_fresh_public_source_id_v2.py tests/test_score_fresh_public_source_id_v2.py` from `backend` | Keyless synthetic checks for exact public PDF source bytes, source-overlap page exclusions, two independent page/cue reviews, frozen split-separated packets, failure-inclusive scoring, exact useful-ID cardinality and calibration-before-heldout. A passing contract suite is not a real source-quality score or permission to call Gemini. |
| Private source gold-to-slate bridge | `venv/Scripts/python.exe -m pytest -q tests/test_private_source_gold_v4_bridge.py tests/test_private_source_gold_v4.py tests/test_source_judgment_display_v4_score.py` from `backend` | Synthetic-only exact stage-1/roster/revision/cue-label binding. The caller-supplied current-source snapshot is not a real authorization read or private holdout score; the independent release gate remains open. |
| PostgreSQL and migration chain | `python scripts/test_services.py postgres` | Docker running. Creates a randomly addressed loopback PostgreSQL container and a disposable `regression_test` database, waits for an authenticated TCP query, migrates/checks heads and drift, rehearses downgrade to base/re-upgrade on the empty schema, then tests constraints/transactions/races including Knowledge choice and source-only Ask results. Prints only allowlisted numeric Lane 4 ablation results. |
| Database artifact and legacy recovery | `python scripts/test_database_artifact.py`, `python scripts/test_database_volume_upgrade.py`, `python scripts/test_pgvector_restore.py` | Docker running. Build/verify the reviewed PG16/pgvector recipe; scan exact immutable bytes and SBOM; refuse a legacy volume unchanged; logically restore synthetic prior-head records into a separate ICU target; verify vector infrastructure. Reports are ignored artifacts; no operator data. |
| Mailpit request/delivery | `python scripts/test_services.py mailpit` | Docker running. Creates disposable PostgreSQL and Mailpit containers; verifies request/outbox/SMTP capture, invitation/password semantics and delivery retry. No production relay. |
| Local encrypted SMTP/recovery | `python scripts/test_smtp_tls.py` | Backend development Python and Docker. Actual authenticated STARTTLS/implicit-TLS delivery, certificate/hostname rejection, durable retry and guarded operator recovery on disposable local capture. See [SMTP verification](SMTP-VERIFICATION.md). Required email CI. |
| Clean production installation/restore | `python scripts/test_production_rehearsal.py --evidence /private/path/result.json` | Clean committed checkout on Linux/amd64 with Docker Compose/OpenSSL. Fresh clone, generated settings, production profile, trusted loopback HTTPS, current-head backup and restore into a separate empty volume, upgrade and recovered application checks. Also manually dispatch [production rehearsal](PRODUCTION_REHEARSAL.md) on protected main. |
| Frontend offline browser/components and build | `npm run check` from `frontend` | Typecheck, test typecheck, lint, unit/component tests, production build and maintained browser regressions, including reload-safe duplicate-choice dialog behavior. The separately configured password-reset live case remains gated. |
| Full real application browser journey | `python scripts/test_journey.py` | Docker and installed Playwright Chromium. Starts a fresh migrated database, real API plus generation/index/source-only Ask/email workers and browser frontend; uses deterministic generation/embedding providers with no provider SDK/network request. Proves exact Knowledge references/page opening and no-match without assistant answers. |
| Release metadata/workflow contracts | `python scripts/check_release.py --version 0.1.0` and `python scripts/check_ci.py` | Maintained source/templates only. Remote preflight, signatures and publication require the separate [release procedure](RELEASING.md). |
| Explicit live AI evaluation | `RUN_LIVE_AI_TESTS=1 python -m pytest -q -m ai_live tests/integration/test_live_ai_pipeline.py` from `backend` | Explicitly inject enabled provider/model/key and reviewed prices as described below. One native Gemini request, two cards, no retries/refills, 8,192 input/2,048 output tokens, USD 0.02 maximum estimated cost. Never runs in normal CI. |
| Explicit live source-only RAG smoke | `RUN_LIVE_RAG_TESTS=1 RAG_LIVE_EVAL_AUTHORIZED=I_ACCEPT_EMBEDDING_CHARGES_SOURCE_ONLY python -m pytest -q -m ai_live tests/integration/test_live_rag_evaluation.py::test_live_rag_embedding_and_source_selection_with_hard_bounds` from `backend` (shell-specific assignments) | Separate endpoint/model/price/call/token/time/cost approval required. One Embedding 001 current-question request, zero retries, at most 512 input tokens, 30 seconds/call, 45 seconds total and USD 0.001 conservative admission using a USD 0.20/million price floor. Zero answer/verifier calls. Authored source-selector smoke is not a private retrieval-quality gate. |
| Retired private answer comparison | `scripts/compare_private_ask_once.py` | Paid entry point refuses `answer_generation_retired`, even with historical opt-ins. Pure keyless historical diagnostic tests remain; do not use it for source-only release evidence. |
| Private real-query retrieval | `scripts/evaluate_private_query_retrieval.py` inside the local answer-worker; default preflight is provider-free | Separately approved `--execute` plus exact process/argument authorization required for one native Embedding 001 batch of six authored questions; unchanged `QUESTION_ANSWERING` space, zero retries, 512 input tokens, 30-second call/45-second total and USD 0.001 conservative admission. No lecture/history or answer call; read-only current-authorized retrieval and aggregate-only output. Keyless contracts: `python -m pytest tests/test_private_query_retrieval.py` from `backend`. |
| Public local relation calibration | `scripts/calibrate_local_relation.py --artifacts <public-local-bundle> --fixture <reviewed-public-fixture>` in the isolated CPU worker | Provider-free, owner-approved one-candidate audit; pinned fixture/artifacts, complete-input guard, frozen public-only rule selection and closed heldout on calibration failure. Does not activate runtime support or read private cases. Keyless contracts: `python -m pytest tests/test_local_relation_calibration.py` from `backend`. |
| Approved 4B public relation calibration | `scripts/calibrate_local_relation_4b.py --artifacts <pinned-public-4b-bundle> --fixture <same-reviewed-public-fixture>` in an isolated Linux CPU container | Separate explicit owner approval; immutable eight-file CPU export, 3 GiB artifacts, 4 GiB additional RSS, 5 GiB container and four CPUs. Hard 30-second startup/600-second total supervisor, ten-second complete checks, same frozen 96-case procedure. Unknown interrupted heldout state is reported honestly. No private reads, provider calls, dependency changes or activation. Keyless contracts: `python -m pytest tests/test_local_relation_4b_candidate.py tests/test_local_relation_4b_calibration.py tests/test_local_relation_4b_download.py` from `backend`. Public transport uses separately approved, one-shot modes. Transport time excludes the unchanged 600-second audit. See the [dated evidence](../.agent/logs/2026-09-26/2026-09-26-local-relation-4b-experiment.md). |
| Private 20-card source evaluation | `venv/Scripts/python.exe scripts/evaluate_private_generation.py` from `backend`, or inside the configured generation worker | Separately approved, one-shot read-only current published-source selection. Every approved endpoint/model/price/call/token/time/cost field must be supplied as a process-only value; up to 16 physical calls, 120,000 input/48,000 output tokens, 30 seconds/call, 8 minutes total and USD 0.18 estimated admission. No set/cards are written. See [AI evaluation](AI_EVALUATION.md#prompt-and-replay-measurement). |

The two approved single-stream Range continuations and one approved segmented continuation each used distinct exclusive markers and no automatic network retry. The segmented run made four HTTP 206 requests and downloaded the remaining data shard bytes, then returned `failure_stage=finalize`. A separate local SHA-256 check confirmed the full 2,885,434,880-byte shard matched its literal pin, and a local move finalized it without another HTTP call. The exact cause of the earlier Python finalization failure was not captured; the stage covers the target-exists check and rename operation. The subsequent small-file completion left only `README.md` missing.

The separately approved six-small-file completion made six request attempts. Five files were finalized and verified; the sixth, `README.md` (519 bytes), failed at `failure_stage=transport_open` before a valid response was recorded. A subsequent primary-source repository-tree check established a downloader URL mapping error: `README.md` is at the pinned repository root, whereas the previous request targeted the export subdirectory. The exact HTTP status and whether any other transport condition contributed were not retained. The downloader now resolves only this pinned file at the repository root; the other seven pinned files remain under the export directory, and unexpected names are rejected.

The first separately approved README-only attempt used one request, received zero body bytes and ended at `failure_stage=transport_open` while still using the incorrect export-subdirectory URL. Its `.readme-only-used` marker remains consumed. The owner then approved one corrected-root GET using the separate `--corrected-readme-approved` mode. That call also stopped at `transport_open` with zero received body bytes; its `.corrected-readme-used` marker remains consumed. The exact HTTP/transport cause is unknown. A further public request requires a new operator decision.

The consumed corrected-root envelope allowed **one HTTP GET** to `https://huggingface.co/onnx-community/Qwen3-4B-ONNX/resolve/98ddba15d05dede4435afb63f13280abcdbc2a48/README.md`, requiring status 200, identity encoding, exact `Content-Length: 519` and exactly **519 body bytes**. The only destination was the missing public `README.md`; the complete eight-file bundle would be **2,897,393,599 bytes (<3 GiB)**. Incremental SHA-256 and full on-disk SHA-256 had to match its literal pin before finalization, followed by a complete rehash of all eight files. Limits were 60-second socket inactivity, 120-second hard request time and 10-minute hard total process time. The failed call made no Gemini call, `.env` or course Knowledge read, database write or model inference.

The owner separately approved **one runtime-only diagnostic** as `scripts/calibrate_local_relation_4b.py --artifacts /experiment --fixture /app/local_relation_calibration_v1.json --runtime-only-diagnostic` inside the isolated CPU container. It requires `README.md` to be absent and verifies the hashes, graph, and model contracts of the seven pinned runtime files before loading ONNX Runtime. The default command still requires all eight pinned files. The diagnostic retains the same frozen 96 public cases, resource caps, and supervisor; its report explicitly says `incomplete_bundle_diagnostic=seven_runtime_files_verified_readme_missing`, and `candidate_passed` is always false even if all 96 results are correct. That one run returned `supervisor_startup_timeout` after 30,026.9 ms, before a validated case result; it made no provider call or database write and did not change the runtime policy. The diagnostic neither establishes full artifact provenance nor measures semantic model quality. A further model run needs a new operator decision.

Install the browser once from `frontend` using
`npx playwright install chromium` (Linux CI: `npx playwright install --with-deps chromium`).

The frontend check and browser runner inject API_PORT=8000 and VITE_API_URL=/api
for all stages; the public loader then avoids reading root .env. Individual
development/build commands retain the normal root configuration contract.
Component regressions include aborted and delayed Subject/session responses,
immediate loading on navigation, and generation jobs staying in their Subject
scope after poll failures or late mutation responses.
`backend/tests/test_knowledge_duplicate_choice.py` is the focused offline
contract for exact-revision no-op, compatible reuse, separate copy, stale or
incompatible candidates, owner/Subject isolation, expiry, cancellation, source
cleanup and raw quota accounting. The maintained browser case
`frontend/e2e/knowledge-duplicate.spec.ts` covers reload recovery, idempotent
choice retry, unavailable reuse, cancellation and no-change presentation. The
disposable PostgreSQL command runs
`backend/tests/postgres/test_postgres_knowledge_duplicate_choice.py` for the
scoped candidate constraint and concurrent first-choice result, plus migration
and downgrade coverage; SQLite success alone does not establish those
properties.

Lane 6 targeted offline suites exercise source-only results, exact displayed
excerpts and current-page reads, safe stage/reason/finish/usage diagnostics,
historical NLI/QA contracts, bounded retrieval variants, adaptive
generation allocation and per-attempt quality counts, and encrypted validated
candidate storage. The PostgreSQL harness must also pass migrations
`20260925_0018` through current source head `20261002_0033` with head/drift and disposable downgrade/re-upgrade,
concurrent exact card-choice/idempotency, expiry, cancellation, source cleanup,
authorization, Knowledge publication races and provider-call caps, including
the `0023` parent-policy/attempt trigger against disguised source-only stages,
and the later original-PDF and dormant source-judgment constraints. The browser
spec `frontend/e2e/generation-card-choice.spec.ts` covers reload, exact smaller
count, retry identity, mobile accessibility and explicit extra-cost Retry;
`rag-knowledge.spec.ts` covers the safe Ask outcome classes. A passing
deterministic suite establishes these invariants, not real lecture usefulness or
20-card provider yield.
The staged related-Knowledge tests additionally check exact excerpt bounds,
source-offset and attempt guards, whole-bundle hiding after source drift,
terminal-only response copy, escaped text and historical failed-job display.

The [independent source-page review builder](../scripts/build_private_source_holdout.py)
and [displayed-window probe](../scripts/evaluate_private_source_display.py) default
to preflight without provider work. Creating the private page-review packet
requires explicit scoped corpus access; it assigns no quality labels and
measures no runtime selection. A displayed-window run needs frozen independently
reviewed gold pages, a frozen selector and a separately approved embedding
envelope. A matching canonical span is not proof that the browser opened the
current authorized page or that the owner found the displayed window useful.

The separately approved local relation-checker experiment has keyless unit
contracts in `backend/tests/test_local_relation_candidate.py` and a public
24-case adversarial fixture checked by
`backend/tests/test_local_relation_adversarial_fixture.py`. Normal tests load no
model and make no network calls. The isolated
[`evaluate_local_relation.py`](../scripts/evaluate_local_relation.py) harness
requires separately downloaded, digest-pinned public artifacts and read-only
fixture/script mounts; it is not part of routine CI or the running Ask factory.
An unknown, unavailable or inconsistent model decision safely rejects but does
not count as a successful semantic negative. A failed development configuration
is reported after one repetition; only a configuration passing every gate
continues to the required three repetitions. See
[experimental boundaries](RAG_EVALUATION.md#live-deployment-model-boundary).

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
deterministic journey. Consult [AI evaluation](AI_EVALUATION.md) for the authored
corpus and release thresholds; no offline pass proves a current remote model's
behavior.

The former live answer harness is retired. Its earlier two-request/local-support
sample on 2026-09-23 remains historical evidence only;
[RAG evaluation](RAG_EVALUATION.md#live-deployment-model-boundary) records its
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
