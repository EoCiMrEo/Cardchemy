# Lane 6 prospective activation review

## Scope and present state

Read-only review of the current config, Compose consumers, profile/API/worker
fences, shutdown CLI, focused tests and operational guides. No source, root
configuration, credential, database or image was changed; no provider was
called. Only this log was added. Keep the pinned private12 and seed14 helper
and runtime bytes stable until both trials are terminal. The root owns any
activation and index update.

The retained-cutover record establishes head `20261002_0033`, matching healthy
services, preserved populated volume/PDF archives and disabled Ask. This
review did not independently probe that retained state. Full offline,
PostgreSQL, frontend, journeys and security have separate passing dated
evidence; do not repeat unrelated checks to prepare this runbook.

## Conditions before activation

Both complete private trials must be terminal and their actual issued/selected
source results must pass the independent metrics: private twelve-case hit and
per-group gates, at least 80% useful **all displayed cards**, seed hit at least
10/11, N12 and both restricted wrong-source controls. The seed controls do not
prove corpus-wide absence. Preserve all failed attempts and unknown charges.

The root must also reconcile actual selected-PDF browser/display integrity,
zero fabricated/stale/unauthorized references, disclosure and relevant release
gates. Spoken assistive-technology checks in ACCESSIBILITY scenarios 9–11 and
any changed shared dialog/Study flow remain real spoken checks; an AX tree is
not that evidence. Passing quality trials alone does not satisfy these gates.
Use a disposable deterministic candidate where a manual scenario would
otherwise issue an unapproved provider call.

## Exact activation controls

`backend/app/config.py` currently has:

```python
ASK_REQUIRED_RELEASE_POLICY_VERSION = "related_knowledge_navigation_v8"
ASK_RUNTIME_POLICY_VERSION = "two_request_local_support_v1"
```

Only after the conditions above are met, change the runtime constant to the
required v8 value. Preserve the v8/`visual_source_id_v5`/
`literal_subject_admission_v2` contracts and old readable-policy list. No
migration is needed for this constant change; retained head stays 0033.

The installation's non-secret root settings needed for admission are
`RAG_ENABLED=true`, `RAG_ASK_ENABLED=true`,
`RAG_EMBEDDING_PROVIDER_ENABLED=true`, and
`RAG_SOURCE_JUDGE_PROVIDER_ENABLED=true`. Change only missing activation flags;
retain existing embedding identity, quota labels, credentials, PDF key and all
other user settings. Template and validated default flags stay **false**, so
fresh installations remain inactive after the source fence opens. Keep retired
`RAG_AI_*` and local-support roles disabled. A key by itself grants no authority.

## Narrow verification for the activation delta

Several current tests intentionally depend on the old closed source constant:
`test_config.py`, `test_runtime.py`, `test_source_visual_runtime_profile.py`,
`test_visual_source_judgment_policy_migration.py`, and `test_rag_shutdown.py`.
When activating, preserve their meaningful negative scenarios by explicitly
injecting a retired runtime fence or false Ask/provider flags. Do not remove
inactive mutation/claim/history, wrong-space, credential, budget or historical
read assertions merely to obtain a pass. Add/retain the direct positive v8
availability case and explicit template/default-off case.

From `backend`, the focused delta command is:

```powershell
venv/Scripts/python.exe -m pytest -q tests/test_config.py tests/test_runtime.py tests/test_source_visual_runtime_profile.py tests/test_rag_shutdown.py tests/test_rag_source_only.py tests/test_rag_source_only_negative_gate.py tests/test_rag_answers.py tests/test_source_judgment_visual_v5.py tests/test_source_visual_v5_provider.py tests/test_rag_question_context_v2.py tests/test_visual_source_judgment_policy_migration.py
```

This covers activation/inactivity, isolation, history/access, old-policy/retry
fences, current admission, request/usage budget, issued IDs and no generated
answer. It is not a new full-offline or real-provider claim. Existing frozen
full-suite and PostgreSQL evidence remains separately identified; broaden only
for a concrete new defect or required gate. Update config/ADR/plan/current-state
release text when activation is real, then run `python scripts/check_context.py`.

## Safe installation sequence (root executes later)

1. Confirm both diagnostic processes have ended. Preserve their frozen stages,
   ledgers, images and all earlier failures. Preserve the restore-verified
   before-0033 backup. Record current image/aggregate identities and root-file
   checksum; never print resolved Compose settings or secret values.
2. With Ask still off, preview `docker compose exec -T backend python -m app.cli
   resolve-ask-shutdown`. It returns only queued/running/possible-execution
   counts. If old active rows exist, stop the API and answer writer first and
   use the CLI's explicit `--apply --writers-stopped` route before reopening;
   it preserves history and uncertain execution and sets nonretryable terminal
   state. Do not purge jobs/references, replay them, or reset volumes.
3. Apply only the reviewed source fence and required two installation flags.
   Verify dedicated credential **presence and worker validation** without
   emitting values. `require_rag_answer_worker_config()` needs independent
   embedding/judge keys, nonempty quota labels, positive prices and the retained
   original-PDF key. The API receives no provider key.
4. Run `python scripts/check_config_migration.py` and `docker compose config
   --quiet`. Build the matching backend image after the trials end. Preserve
   the old immutable image/tag for reversible recovery. Do not pull, downgrade,
   stamp, reindex or run an upgrade merely to activate an already matching head.
5. The essential new-setting/source consumers are **backend and answer-worker**.
   The same backend image is shared by worker, index-worker and email-worker;
   recreate them from that image as needed for a matched installation, retaining
   each role's credential boundaries. An image-only activation can use
   `docker compose up -d --no-deps --force-recreate --wait backend worker
   index-worker answer-worker email-worker` after matching preflight. Database
   and Mailpit stay in place. Current frontend bytes already support v8 and
   consume the API profile; no frontend rebuild is required solely for flags.
   Its nginx upstream resolves Docker DNS continuously. Reload/refetch profile.
6. Check the **new** backend image with `python scripts/check_images.py backend
   --image <new-local-image>`. It runs credential-free and networkless and
   asserts inactive defaults and no retired inference package/client. The prior
   security/SBOM proof binds the old image IDs; identify any newly built image
   separately and run the applicable image security gate rather than labeling
   the prior scan as a scan of new bytes. Preserve earlier artifacts.
7. Check current heads/drift from the matching image, using the DATABASE
   OPERATIONS `alembic current --check-heads` and `alembic check` commands; these
   are read-only. All process health must be healthy, backend ready 200 and
   frontend `/healthz` 200. Existing `/api/health/ready` through the edge should
   also return 200. Health alone does not establish Ask capability.
8. In an authenticated authorized Subject, GET its `/rag/profile`: v8 policy,
   active embedding-space match, Ask enabled/available and source-judge available
   true; judge Gemini Flash-Lite/HIGH, v5 contract, published-text/images and
   bounded literal-context disclosures true; answer available false and answer
   provider/model null. A wrong-space Subject remains unavailable. The new job
   path stays one current-question embedding plus at most one source-ID call,
   zero answer/verifier and zero automatic retry. Do not submit a paid question
   as a health check without a new explicit provider envelope.

Compose credentials remain: embedding key in index/answer workers only; judge
key only in answer worker; PDF key in API/generation/answer worker; generation
key only in generation worker and SMTP only in email worker. Do not bulk-inject
root `.env` into every service. Preserve original PDF attachments, Knowledge,
generated sets, pending choices and old authorized references.

## Budgets and off rollback

Retain 32,768 input/4,096 output including thinking, HIGH, 120-second judge and
zero retries; source windows/images and one-call caps are unchanged. Defaults
reserve roughly USD 0.020378 per Ask attempt for maximum query embedding plus
judge tokens, using the existing conservative guards (not a provider invoice).
Manual retry must disclose extra cost and uncertain prior cost. Keep quotas,
daily/admission limits, 300-second job deadline and process-local RPM/TPM
governor unchanged unless a separately measured change is approved.

Immediate rollback closes `RAG_ASK_ENABLED` and
`RAG_SOURCE_JUDGE_PROVIDER_ENABLED`, then stops/drains and recreates API/answer
worker with false flags. Preserve `RAG_ENABLED` and embedding availability so
published-lecture browsing/indexing remain independent. Profile must report
Ask unavailable while authorized history/PDF browsing still work. Preview and
resolve only pending Ask jobs with the guarded shutdown command; uncertain
provider attempts are never automatically replayed. Keep all original data,
credentials and source rows. No schema downgrade or database restore is needed
for flag rollback; if necessary the preserved old image is an additional
reversible off-mode recovery path.
