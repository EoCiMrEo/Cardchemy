# Activation running-image reconciliation

## Read-only result

At `2026-10-04 04:21:06 UTC` (still October 3 local CDT), normal approved
read-only Docker inspection found the installed application consumers already
matched to the verified v8 preparation images. No restart, deployment, build,
provider, database or configuration mutation was performed by this review.
The real root environment and credential values were not read or printed.

| Consumer | Exact immutable image | Current state |
| --- | --- | --- |
| Backend API, generation worker, index worker, answer worker, email worker | `sha256:7002fd38e80dbe3ac89e4ab64e305944848d4cdd594de2bf41d229237a30af41` | All running and healthy, each restart count zero |
| Frontend | `sha256:e672a910c14e69f68fcecd974fac4435c258c0d12fcdbefca2b46889767ef694` | Running and healthy, restart count zero |
| Completed migrate service | Same `7002fd38…30af41` backend image | Exited zero |

Docker labels confirm the current deployment uses both `docker-compose.yml`
and `docker-compose.dev.yml`. The earlier restarting `4a0ecfb…` observation is
historical and does not describe this snapshot. All application images carry
the installation's existing `0.1.0` tags; version/tag names are not immutable
code proof, so the table records actual image IDs.

## Development mount distinction

The development override and actual mounts agree:

- API, generation worker and email worker use the host `backend` directory at
  `/app`; the API uses reload. The completed migrate service has the same bind.
- Index and answer workers have **no** host backend mount. They execute the
  immutable backend image. Frontend also has no source bind.

Editing the runtime fence on the host therefore changes the API's visible
source without changing the answer worker's image. Host API reload or
`docker compose restart` cannot provide a matching source/flag cutover. Keep
Ask off while every private frozen process is active. After those processes
and all quality/display/release gates are terminal, the root must build a new
matching backend image and recreate affected consumers; source head remains
0033 and does not require another schema migration.

## Smallest complete root-owned sequence

Use the documented explicit development composition for each Compose command:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile development
```

1. Preserve the exact old `7002fd38…` image under a separate local off-rollback
   tag before replacing its mutable `0.1.0` tag. Keep the original populated
   volume, restore-verified backup, original PDFs/archive key and every provider
   stage/claim/result. Preview old queued/running Ask jobs while Ask is off;
   only if active rows exist, drain API/answer writers and use the guarded
   shutdown CLI. Never replay those rows or regenerate installation secrets.
2. Apply the independently reviewed seven-file activation delta and run its
   focused tests. Keep the two real installation flags false during tests/build.
   The default/template flags remain false. Quiet config and configuration
   migration checks precede the build. Build only the changed backend consumer
   with this composition; no frontend, database or Mailpit rebuild is needed.
3. Record the **new actual backend image ID**. Run credential-free/networkless
   `scripts/check_images.py backend --image <new-ID>` and the applicable
   documented image/security gate. Prior smoke/security records bind old
   `7002fd38…`, OCR `2dde663b…` and frontend `e672a910…` IDs; they must not be
   relabeled as proof for the new backend bytes. The current security helper
   `scripts/test_security.py --image-tag 0.1.0` scans all three local variant
   tags; use its documented interface if that is the selected gate and preserve
   previous reports before its output directory is reused. The unchanged OCR
   and frontend identities stay separately identifiable.
4. Change only `RAG_ASK_ENABLED` and `RAG_SOURCE_JUDGE_PROVIDER_ENABLED` in the
   existing root configuration after release preflight passes. Retain all other
   values, provider/Subject space, prices, quotas and credential boundaries.
   The proposed minimal recreation command is:

   ```powershell
   docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile development up -d --no-deps --no-build --pull never --force-recreate --wait backend worker index-worker answer-worker email-worker
   ```

   This replaces all five shared-image consumers (API and four workers) with
   consistent source/flags. Database and Mailpit are untouched; `--no-deps`
   avoids rerunning the completed migrate service. The frontend already runs
   matching `e672a910…` bytes and supports the current profile, so it remains in
   place. A browser profile refetch/reload consumes the new API disclosure.
5. Inspect every newly running consumer's immutable image ID and health.
   Verify read-only `alembic current --check-heads` and `alembic check` with the
   matching image/source and retained head 0033; do not upgrade, stamp or
   downgrade just to activate a constant. Verify API readiness and edge/frontend
   health, then the authorized Subject profile: v8, active-space match, Ask and
   source judge available, visual-v5/HIGH, published-text/image/literal-subject
   disclosure; generated-answer availability stays false with null model/provider.
   Existing negative contracts retain wrong-space/access/old-job/no-retry fences.
   Do not send a paid Ask question as a health check without a fresh exact
   provider envelope.
6. Update current activation text and dated release evidence, run context
   validation and only then close the checklist/goal/heartbeat. The maintained
   `docs/ASK_AI_SHUTDOWN.md` still describes historical v4/0029 as prospective;
   its current introduction, preparation/activation section and profile
   identity must be aligned to released v8/0033, explicitly preserving the
   historical procedure. The final documentation update belongs to the root.

For immediate off rollback, close only the two installation flags, drain and
recreate the API and answer worker with false values. Knowledge browsing/index
availability, encryption keys and data remain intact. No schema rollback or
database restore is necessary for this activation delta; the preserved old
image is a separate off-mode recovery path.

This is an image/cutover audit, not a live quality result, fresh head/drift
execution, activation, hosted CI or production-deployment claim. It supplements
the [unapplied delta](2026-10-03-lane6-unapplied-activation-candidate.md) and
[activation runbook](2026-10-03-lane6-activation-readonly-runbook.md).
