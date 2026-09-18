# AI request-efficiency remediation

Date: 2026-09-16

## Scope and completed work

The user approved reducing provider-request pressure by packing provenance-safe
PDF chunks into larger requests, batching card generation, sharing provider
quotas across concurrent jobs, and making request telemetry durable and visible.
Phase 8 and unrelated application behavior were not reopened.

- [x] Preserve page/section-grounded logical chunks and exact quote validation.
- [x] Greedily pack evidence using the complete rendered prompt token estimate.
- [x] Skip summary calls for one-pack documents; summarize once per pack and
  hierarchically reduce only multi-pack documents.
- [x] Batch per-chunk card quotas into multi-card requests and reject unknown
  source IDs, quota overflow, ungrounded candidates, and global duplicates.
- [x] Refill only the missing global card count within existing bounded rounds.
- [x] Preserve complete one-pack context when there are more chunks than cards,
  track summary coverage server-side, and prevent whole-job timeout replay.
- [x] Recalculate conservative token/cost/request preflight estimates.
- [x] Share one RPM/input-TPM governor across every job in a worker process.
- [x] Admit every physical provider attempt, including retries, through that
  governor; retain uncertain reservations and reconcile successful input usage.
- [x] Preserve initial call plus at most three retries, at least three seconds
  between retries, and honor usable longer provider Retry-After hints.
- [x] Persist request/retry/wait/cache/stage telemetry on durable generation
  jobs and carry it through both success and handled failure paths.
- [x] Expose compact request, rate-wait, and cached-input metrics in the UI;
  keep the stage breakdown API-only.
- [x] Add migrations, configuration examples, Compose wiring, documentation,
  changelog entries, and automated regression coverage.
- [x] Rebuild affected services, verify migration reversal on a disposable
  database, run PostgreSQL regressions, and perform one bounded live provider
  compatibility check.

## Design and behavior

The previous pipeline mapped every logical chunk to a summary request and
generated cards per allocated chunk. A 32-chunk / 20-card document could require
57 first-round requests. Logical chunks remain small (default 1,200 tokens) and
server-owned; they are now transport-packed rather than enlarged.

Shipped defaults:

| Setting | Default | Purpose |
|---|---:|---|
| AI_REQUEST_INPUT_TARGET_TOKENS | 40,000 | Soft rendered-input target per evidence/card request |
| AI_CARDS_PER_REQUEST | 10 | Maximum requested cards in one generation batch |
| AI_MAX_OUTPUT_TOKENS | 8,192 | Room for a multi-card structured response |
| AI_REQUESTS_PER_MINUTE | 5 | Operator-supplied provider RPM tier |
| AI_INPUT_TOKENS_PER_MINUTE | 250,000 | Operator-supplied provider input TPM tier |
| AI_RATE_LIMIT_SAFETY_PERCENT | 80 | Effective capacities of 4 RPM and 200,000 input TPM |

A typical one-pack / 20-card document now has two initial generation calls and
no summary calls. With two configured refill rounds, its conservative planned
maximum is six logical calls; provider retries are separate physical attempts
and still consume the same shared quota. Multi-pack documents map summaries per
pack, not per logical chunk. The first required planning/card batch remains a
compatibility probe and sibling work remains fail-fast.

Independent final review found and corrected three edge cases: zero-quota
chunks must still reach direct-generation context; large summary packs must not
spend their output budget repeating hundreds of IDs; and governor waits must
not trigger an automatic whole-job timeout replay. Direct batches now carry the
complete evidence pack, summary provenance is combined server-side, and job
timeouts finalize with available telemetry and manual Retry only. A regression
with 600 logical chunks verifies complete planning without a 500-ID output cap.
Successful token reconciliation also wakes TPM-blocked waiters immediately
rather than making them sleep through an unnecessarily full quota window.

The governor uses a FIFO rolling 60-second window. Quota waiting is outside each
provider-call timeout but inside the whole-job timeout and lease heartbeat.
The existing shared concurrency semaphore remains conservative during waits.
Google SDK retries remain explicitly disabled (one SDK attempt). A provider
Retry-After above the configured bounded wait stops automatic retries rather
than retrying earlier than requested.

Native provider adapters maintain per-instance attempt telemetry while sharing
the worker quota governor. This prevents concurrent jobs from attributing one
another's requests to themselves. Reused graph invocations subtract their own
provider baseline. GenerationJob counters are cumulative across manual retries;
estimated requests are the maximum plan for one run, while actual attempts,
retries, waits, cache tokens, and stage counts are additive.

The AI-generation persistence skill influenced the implementation by keeping
these metrics on the existing durable, owner-scoped generation job rather than
ephemeral client or worker state. No prompts, source text, credentials, or raw
provider errors are persisted in request telemetry.

## Migration findings and resolution

Revision 20260916_0006 adds the new fields and nonnegative/retry-count constraint.
The initial PostgreSQL drift rehearsal found that comparing a JSON server
default fails because PostgreSQL JSON has no equality operator. A follow-up
20260916_0007 migration converts only the stage map to JSONB, preserving rows.
The ORM uses the project's existing portable JSON-with-PostgreSQL-JSONB pattern.
No live downgrade or telemetry deletion was performed.

The disposable database was upgraded to head, downgraded through both new
revisions to 20260915_0005, checked for removal of the new columns, then upgraded
again to 20260916_0007. Alembic current --check-heads and alembic check passed.
The live database also reports 20260916_0007 / JSONB with no new upgrade
operations detected. A first disposable connection attempt lacked a host-exported
password; the retry reused the container's existing credential privately.

## Verification

- Initial focused backend suite: 82 passed; final review corrections were then
  covered by the final full backend gate.
- Final full backend suite: 169 passed, 24 environment-gated skips, one deliberately
  opt-in live-provider evaluation deselected.
- Frontend npm run check: type checks, lint, two unit tests, production build,
  and 47 Chromium acceptance tests passed; one live password-reset test remained
  intentionally gated.
- Added coverage for deterministic packing/no provenance loss, one-pack fast
  path, multi-source batches, 20 cards in two initial calls, quota/retry
  admission, Retry-After bounds, cached usage, API telemetry, failed-job
  telemetry, UI rendering, complete zero-quota context, 600-chunk summary
  coverage, no-timeout replay, early TPM wake-up, cumulative telemetry and
  stage-map persistence across retries, and migration
  columns/constraints/JSONB type.
- PostgreSQL suite in a removed one-off test container: 21 passed against the
  disposable migration-test database. The specifically named test database was
  dropped after verification; live data was not removed.
- Base, development, and production-shaped Compose config validation passed.
  Production validation used non-secret placeholder public/SMTP requirements.
- Backend, generation worker, and frontend were rebuilt/recreated and reported
  healthy; effective non-secret settings confirmed 40,000 / 10 / 5 / 250,000 /
  80 / 8,192 for the new defaults.
- One live packed request with retries/refills disabled returned two strict,
  grounded cards citing pages 1 and 2: one physical request, zero retries,
  278 input tokens and 207 output tokens. No database rows were written by that
  check. A full paid PDF job was not run unnecessarily.
- A final live summary-only-schema check also passed with one request, zero
  retries, 166 input tokens and 28 output tokens. It wrote no database rows.

The build retained non-blocking pre-existing Browserslist age and large-bundle
warnings. No API key or secret value was printed or changed.

## Operational boundaries

The quota governor is worker-process-local, matching the current single-worker
Compose topology. Multiple worker replicas require divided per-replica limits
or a distributed governor. Operators should configure RPM/TPM for their actual
provider tier. Telemetry is finalized with success/handled failure; a process
crash or cancellation before finalization can omit attempts from that run.
Longer jobs can still reach the existing token, cost, or whole-job-time limits.
Provider Batch API, alternate-model planning, and explicit prompt caching remain
separate future scope.
