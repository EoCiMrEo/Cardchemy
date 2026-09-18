# ADR-008: Run bounded generation jobs through PostgreSQL

## Status

Accepted. Current implementation verified on 2026-09-16.

## Context

PDF extraction and provider calls can exceed an HTTP request's lifetime.
Browser/API restarts, overlapping retries, worker crashes, and unbounded
resource use must not lose queued work or create partial/duplicate result sets.

## Decision

Use PostgreSQL job/source/quota records and a separate generation worker,
without a message broker. Reserve jobs and retry operations with hashed
idempotency keys; bound raw uploads and admission/quota charges. Encrypt
temporary PDF sources with a dedicated AES-256-GCM key and remove them under
the recorded retention policy.

Claim jobs using `FOR UPDATE SKIP LOCKED`, worker identity, random fencing
tokens, renewable leases, and final lease verification. Persist the draft set,
validated cards, terminal status, telemetry, and source deletion atomically.
Enforce queue, storage, extraction, time, token, cost, concurrency, and attempt
limits. Provider adapters own one bounded retry loop; handled pipeline/provider
failures and job timeouts require manual retry rather than automatic pipeline
replay. Infrastructure/dead-lease recovery can requeue within attempt bounds.

## Rationale

The application already depends on PostgreSQL. Keeping admission, encrypted
sources, job state, and results there allows transactional recovery without an
additional queue service. Fencing plus the unique job/result-set link protects
database outcomes from stale workers.

## Consequences

Queued work survives API/browser restarts. A job has at most one committed
result set; remote provider execution is not exactly once and may repeat after
crash recovery. Source-key rotation requires draining/cancelling retained jobs.
Request telemetry can omit work before a crash/finalization and is not a
billing ledger. The worker's RPM/input-TPM governor is process-local; multiple
replicas require divided limits or a distributed governor. Broker/distributed
admission changes require a new decision and measured operational need.

## Related areas

- [AI generation architecture](../architecture/AI-GENERATION-FLOW.md),
  [PDF operations](../PDF_GENERATION.md), [provider operations](../AI_PROVIDERS.md)
- [Job service](../../backend/app/services/generation.py),
  [worker](../../backend/app/workers/generation.py),
  [models](../../backend/app/models/generation.py),
  [source encryption](../../backend/app/services/source_storage.py),
  [provider retry owner](../../backend/app/ai/providers/__init__.py),
  [governor](../../backend/app/ai/rate_limit.py)
- [PostgreSQL result tests](../../backend/tests/postgres/test_generation_job_persistence.py),
  [ADR index](ADR-000-INDEX.md)
