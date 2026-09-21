# Observability and operator diagnostics

Diagnostics contain operational metadata, never document text, prompts, model
responses, recipients or credentials. See [privacy and lifecycle controls](PRIVACY.md)
and [configuration](CONFIGURATION.md). Metrics and audits are operator-only CLI
commands; there is no public metrics or audit endpoint.

## Correlation and safe errors

The API generates a new UUID for each request and returns `X-Request-ID`.
Client-supplied IDs are not trusted. Error responses retain the supported
`detail` contract and add a safe error code and request ID. Validation errors
omit submitted input and exception context. Unexpected errors return a generic
500. HTTP statuses, authentication headers and typed study conflicts remain
authoritative. An ID is for support correlation, not authorization.

Generation, Knowledge-index and answer reservations store the originating
request ID; each worker restores that durable correlation context while it
processes the claim. Worker events also carry the job ID; email events carry
the outbox ID. UUID context is isolated between concurrent tasks. Job
diagnostics survive an API/worker restart while job history remains retained:

```text
docker compose exec backend python -m app.cli operations-status
docker compose exec backend python -m app.cli operations-status --job-id JOB_UUID
docker compose exec backend python -m app.cli audit-status --target-id RESOURCE_UUID --limit 20
docker compose logs worker
docker compose logs index-worker
docker compose logs answer-worker
```

Look up the job's stage, safe failure code, attempt count, timestamps, provider
request/retry/wait counters and token/cost usage. Use the safe code to follow
[provider recovery](AI_PROVIDERS.md) or [PDF recovery](PDF_GENERATION.md).
Do not collect the source PDF or request body merely to diagnose an ID.

## Metrics and limitations

`operations-status` returns retained request counts, 5xx rate, latency sum/mean,
recent p95, route-template/status counts, generation/email/Knowledge-index/answer
queue and status counts, recent worker heartbeats, and bounded content-free RAG
aggregates. Those aggregates include capture/index/answer failure and throughput
counts; capture/index/answer duration samples; retrieval duration; answer versus
abstention outcomes; support-rejection counts; and per-provider/model physical
requests, retries, rate-limit waits, tokens and estimated/actual cost for index
and answer lanes. Micro-USD values
are millionths of a US dollar. Zero configured prices mean estimates are
unavailable; these are not a complete billing ledger.

Request diagnostics are bounded best effort and must not fail business
transactions. Logs remain available if their database write fails; missed
records make request aggregates incomplete. The p95 and durations use bounded
recent samples, while request aggregates use the configured retention window.
Generation/model aggregates cover retained job history, with a bounded model
list. Cleanup removes historical metrics. Crashed/cancelled provider work can
be absent from durable counters; manual retry accumulates provider usage, while
timestamps describe the latest recorded attempt. Do not infer exactly one
remote execution from one committed set. CLI output is private operational
data and must not be published automatically.

## Health

`/api/health/live` checks API process liveness; `/api/health/ready` and the
compatible `/api/health` check a bounded database round trip. Database outage
returns a sanitized 503. These routes do not expose workers, users or queue
contents. Readiness does not promise provider/SMTP availability.

Each worker pulses a local heartbeat file and a best-effort database heartbeat
from its scheduling loop. Container probes use `app.healthcheck --worker-kind
generation`, `index`, `answer` or `email`: they check that specific container's loop freshness
and database readiness. Fresh idle and intentionally disabled lanes are healthy;
stale or draining loops fail the worker probe. A healthy worker does not prove
the configured external provider or SMTP endpoint is available. The
database heartbeat list helps operators find stale replicas; it does not
replace per-container health or job lease fencing. Multiple native processes
of the same kind share the default local heartbeat path; use containers for
independent replica health.

## Log redaction

API/workers emit JSON with timestamp, level, approved event name, UUID
correlation and approved numeric/enum fields. Arbitrary messages, arguments,
exception strings/tracebacks, stack dumps and extra fields are discarded.
Unknown third-party messages become `external_log`; unknown codes become
`internal_error`. No email, IP, raw URL/query/referrer, Authorization/Cookie,
API key, invitation/reset link, filename, document/card text, prompt, provider
response or SMTP body is permitted. SQL echo is disabled even with `DEBUG=true`
and database bind parameters are hidden. Uvicorn access logging is disabled.
Nginx logs only status and duration and suppresses raw request-bearing errors.
Apply the same rules to the operator's TLS proxy and log collector.

`LOG_LEVEL` changes verbosity without changing redaction. Application stdout
does not own disk retention: configure Docker/collector rotation and expiry
separately (for example Docker `local` driver with `max-size=10m`, `max-file=3`).
`REQUEST_RETENTION_DAYS` governs database request metadata. Access to both logs
and metadata remains restricted to operators.

## Audits

Invitations, approval/unapproval (including manual/bulk approval), set and
Knowledge publication/unpublication, Knowledge removal, instructor provisioning
and account deletion stage fixed-field audit rows in the domain transaction.
Rollbacks also roll back their audits. No-op state updates add no transition. A
PostgreSQL trigger records direct account-role updates; the application has no
role-change API. Database actors are recorded as `operator_database`, not an
asserted human identity.

Audits contain action, opaque actor/resource/subject IDs, time, request ID and
fixed boolean/count/role transitions. They contain no free-form metadata or
content. Deleted actors become null; opaque target IDs and events survive
content deletion until audit retention cleanup. This is a diagnostic audit
trail, not a tamper-proof ledger: database administrators can alter it. Protect
database access and backups accordingly.

## Optional telemetry

`TELEMETRY_ENABLED=false` and an empty destination are the defaults. No startup,
request or worker action reports externally. If an operator explicitly enables
it and sets an HTTPS `TELEMETRY_ENDPOINT`, this command sends one aggregate
numeric snapshot:

```text
docker compose exec backend python -m app.cli report-telemetry
```

The fixed payload contains only aggregate request/error/latency, queue/worker,
job/card, token/request/retry and cost counts. It excludes IDs, routes,
provider/model labels, timestamps, content and exceptions. The destination
cannot embed credentials, query or fragment; redirects and environment proxy
inheritance are disabled, timeout is bounded and reporting failure is isolated.
The collector still observes the sender's network address. Operators own the
collector, consent/disclosure, access control and collector retention; no
vendor destination or automatic reporting schedule is bundled.
