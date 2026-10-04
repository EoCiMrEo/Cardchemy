# Visual source worker integration and disposable verification

Date: 2026-10-01 (America/Chicago). The populated volume, root `.env`, original
PDFs and ignored backups are preserved. No provider request or private transfer
was made for these checks.

## Implementation

The dormant v5 worker authorizes the current principal/session/question and
eligible retrieval scope before authenticating complete original-PDF archives.
Bounded isolated Poppler rendering produces faithful page PNGs. Current PDF,
page, revision and access bindings are rechecked before the single source-ID
dispatch and atomic reference commit. Its visual adapter has zero automatic
retries and safe closed errors, preserves image/thinking usage and locally
derives zero to three issued IDs. It creates no assistant answer message.

Repeated cancellation now waits for renderer child termination/cleanup before
allowing the worker to abandon preparation. Synthetic tests cover revoked access,
changed questions/scope, invalid/unissued IDs, unfinished/over-budget output,
timeout uncertainty, exact physical-attempt accounting and distinct clarification.

## Verification

- Targeted application contract/archive/renderer/worker/service tests: **221
  passed**. The new focused dispatch/preparation/adapter set: **39 passed**.
- First disposable PostgreSQL run: migration head/drift and empty-schema
  downgrade/re-upgrade passed; 137 tests passed and nine failed because existing
  synthetic fixtures still admitted the historical v4 profile.
- Fixtures now exercise current v5 with a real encrypted synthetic PDF archive,
  real authorized PostgreSQL retrieval and the categorical ID-only fake judge.
  Windows database tests substitute only the rasterizer; native resource/image
  rendering has separate Linux container evidence. Historical v4 guard tests
  retain their immutable old snapshots.
- Corrected full disposable run: **146 passed, 3 skipped, 3,458 deselected**,
  106.86 seconds. This includes the fifteen new v5 PostgreSQL guards. Head/drift
  and empty-schema downgrade/re-upgrade passed. The harness reported removal of
  its separate test container and generated credential file.
- Broad backend/frontend checks and matching image builds were started; their
  final outcomes and any retained cutover belong in subsequent dated evidence.

## Limits

No retained migration has been performed by this record: source head is `0030`,
retained installation remains `0029`. The old development API/generation worker
were observed unhealthy after the source/profile change. A coordinated verified
backup/migration/recreate is needed to restore matching runtime services.
Public model calibration remains failed, heldout/private/release gates remain
open, Ask remains disabled and Lane 6 is **3/7**.
