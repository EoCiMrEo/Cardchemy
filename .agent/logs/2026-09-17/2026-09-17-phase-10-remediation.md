# Phase 10: observability, privacy and operational controls

Date: 2026-09-17. Scope: all eleven Phase 10 tasks in
[the remediation roadmap](../../../issues-required-remediation.md).
Phase 11 release/branding work remains open.

## Starting context and preservation

Started on `main`, HEAD `b30ecd580ce469acc36275fb64e8f6e312e4fdeb`.
Inspected status/diffs before implementation. Preserved existing user changes:
expanded root `AGENTS.md`, Phase 11 brand-asset roadmap additions, dated log
index/context-audit/guidelines-merge records, four supplied frontend brand
assets and deletion of `repository-context-system-plan.md`. Repaired active
navigation to the deleted completed plan by linking its existing completion log;
did not restore or rewrite the deleted artifact or historical log bodies.

Read root instructions (no `.agent/AGENTS.md` present), Start Here/project map,
current state/roadmap, relevant architecture/accepted ADRs, backend/frontend
maps, agent governance/log index, relevant dated logs, configuration/testing,
deployment/database/email/AI guides and affected source/tests. Historical memory
was only orientation; current code and command results established behavior.
Independent subagents owned observability, privacy and privileged-audit audits
and implementation. Final privacy review was read-only and found no blockers.

Real root `.env` was not inspected, modified or regenerated. No application
database, populated volume, account or provider/SMTP credential was used.
No branch, commit, push, merge, live deployment or paid AI call occurred.

## Decisions and implementation evidence

[ADR-011](../../../docs/decisions/ADR-011-operational-privacy-controls.md)
records decisions within the authorized phase: use existing PostgreSQL/operator
boundaries, closed diagnostic fields, transactional audits and guarded privacy
CLI workflows. No new service, dependency or public privacy/metrics API.

| Completed task | Changes and evidence |
| --- | --- |
| Structured logs/levels | `backend/app/observability.py` installs allowlisted JSON formatting and redaction before settings/imports, including API/workers/CLI and isolated PDF extraction. Third-party text, arguments, traces, stack dumps and arbitrary extras are discarded. API/worker print diagnostics were replaced. SQL echo stays off and bind parameters are hidden. |
| Correlation/safe codes | Middleware generates request UUIDs, returns `X-Request-ID` and additive error codes/IDs, ignores untrusted inbound correlation, records only trusted route templates and persists generation origin IDs. Worker events carry job/outbox UUIDs with task-isolated context. |
| Central exceptions | HTTP/validation/unexpected handlers retain supported statuses/auth headers and typed conflicts, omit input/context/private field names and return bounded safe messages. Startup/CLI failures suppress raw configuration/URL exceptions. |
| Metrics | New request records and private `operations-status` commands provide retained request/error/latency, queue depths, bounded recent job durations, generated-card counts and retained provider/model token/request/cost aggregates. Job lookup selects explicit operational columns without documents, filenames or user details. |
| Health | DB-independent API liveness, bounded DB readiness, local loop heartbeats and best-effort DB heartbeats. Worker container probes check their own fresh loop plus DB; disabled generation is healthy, draining/stale loops fail. |
| Redaction policy | [Observability](../../../docs/OBSERVABILITY.md) defines closed fields and forbidden tokens, emails, URLs, document/prompt/model content and secrets. Nginx logs numeric status/duration only and suppresses raw request-bearing errors; Uvicorn access logs are disabled. |
| Provider disclosure | [Privacy](../../../docs/PRIVACY.md) describes selected extracted evidence sent to Gemini/configured OpenAI-compatible providers, encryption boundaries, operator/provider roles and current linked official Google terms/logging/abuse policies. No legal-compliance or zero-retention claim. |
| Lifecycle/export/delete | Privacy guide covers account/content/progress/receipts/jobs/PDF/auth/email/quota/audit/backups. `services/privacy.py` exports allowlisted own records under a PostgreSQL consistent read-only snapshot; CLI creates an exclusive owner-only file (Windows ACL restricted before writing). Explicit account deletion requires apply/quiesced-writer acknowledgements, locks/refuses active claims, cascades dependents and removes recipient copies without resurrecting used invitations. |
| Configurable retention | Validated root settings/template/Compose control request, terminal job, expired DB metadata and audit grace/batch. Operator cleanup previews by default and bounds each category; protects active windows, sources, outbox-linked auth history, lifetime study receipts and linked manual-retry quota receipts. Stale heartbeat history expires after 24h. Existing worker source/email expiry remains authoritative. |
| Privileged audit | Fixed-field audit rows share invitation, approval/unapproval/manual/bulk, publication, provisioning and account-deletion transactions. A PostgreSQL trigger records direct role transitions atomically. Opaque resource targets survive deletion; actor FK becomes null. Parent-set locks prevent duplicate transition audits; CLI advisory lock protects concurrent first-instructor provisioning. |
| Optional telemetry | Disabled/no endpoint by default. Only explicit CLI sends a fixed numeric aggregate snapshot to a validated HTTPS operator destination, without IDs, routes, provider/model labels, content or exceptions. No redirects/environment proxies/retries; bounded timeout and isolated failure. No external reporting was performed. |

New migration `backend/alembic/versions/20260917_0008_phase10_operations.py`
adds request/audit/heartbeat tables, generation request correlation, retention
indexes and role trigger. Existing migration history was preserved. Documentation
maps, architecture, guides, current state, changelog and roadmap were updated
together. Operator upgrade guidance records the new head and downgrade data-loss
limits; this task migrated only disposable test databases.

## Verification actually executed

Commands used `backend/venv/Scripts/python.exe` and installed Node 24/npm 11.
Docker checks ran with scoped permission for isolated resources. Test harnesses
inject synthetic settings and never load the operator root `.env`.

| Gate | Result |
| --- | --- |
| Backend `python -m pytest -q` from backend | **259 passed, 37 skipped, 1 deselected**. Skips are gated service fixtures; live AI is deselected. |
| `python scripts/test_services.py postgres` | **34 passed, 3 skipped, 260 deselected**. Current head `20260917_0008`, no schema drift, full downgrade to base/re-upgrade passed. Includes audit rollback/role trigger, provisioning race, privacy cascade/snapshot/retention and operational schema contracts. |
| `python scripts/test_services.py mailpit` | **3 passed, 258 deselected** at that checkpoint. Disposable DB/head/drift and real local SMTP capture passed; no production relay. Later added offline/provisioning fixtures do not change delivery behavior. |
| Frontend `npm run check -- --workers=2` | Types/test-types/lint, **4 Node units**, **26 component contracts**, coverage/build and **47 Chromium passed, 1 skipped**. Coverage: statements 96.44%, branches 85.05%, functions 91.66%, lines 97.71%; thresholds unchanged. |
| `python scripts/test_journey.py` | **1 passed**: real instructor/student browser → API → durable PDF/generation/email workers → PostgreSQL journey and final data proof; deterministic offline provider, no paid calls. |
| Three freshly built verification images | Backend, optional OCR backend and frontend builds passed. Native/auth/encryption/PDF probes passed for backend; image-only OCR/English language data passed for OCR image. Frontend UID/config/health/index/assets/security/cache and 200/405 private-query/body log-redaction probes passed. |
| Compose base/development/production | Generated temporary settings: all configurations passed, new defaults/worker probes verified, provider/SMTP credential isolation preserved and development access logging disabled. No real `.env` read. |
| CI/context/diff checks | `scripts/check_ci.py`, `scripts/check_context.py` and `git diff --check` passed; final closure checked all eleven Phase 10 boxes and left Phase 11 open. |

Final context validation covered 29 required files, 51 active guides and 647
local links. Both backend images matched normalized hashes of every current
application Python source file. No verification-container leftovers remained;
new untracked text artifacts also passed trailing-space/tab inspection.

New targeted contracts also verify malicious messages/codes/validation data,
correlation concurrency, metrics safe-column selection, worker stale/draining
behavior, telemetry disabled without DB/network calls, exclusive export/ACLs,
deletion acknowledgement flags and malformed-settings startup redaction.

## Failures resolved and verification limits

- Initial system Python lacked `alembic.script`; used the documented backend
  development virtual environment rather than changing dependencies.
- Early redaction assertions used an ambiguous short sentinel, and a timed-out
  in-memory SQLite diagnostic dropped its schema; corrected test sentinel and
  disposable file-backed fixture. Central-error helper/message handling and
  closed code allowlisting were corrected before passing final suites.
- An existing email log test expected UUIDs in plaintext; configured its capture
  sink with the shipped JSON formatter while preserving no-private-data/code/
  correlation assertions. Final full offline suite passed.
- Provisioning-race schema cloning required a private copy of the PostgreSQL
  role enum, not a missing local enum or a domain with incompatible operators;
  fixed the isolated fixture and passed the complete PostgreSQL gate.
- Initial eight-worker frontend run had one fixture stuck at account loading;
  complete two-worker rerun passed every browser case without lowering budgets
  or removing tests.
- The first expanded edge probe expected a 404 access event from an asset
  location whose logging is intentionally disabled; changed the probe to a
  rejected static POST (405). Both success/error redaction checks then passed.
- Initial synthetic production Compose settings omitted its mandatory sender;
  included an explicit test-only sender and all three configurations passed.
- Retired-plan context links were repaired to the existing completion log.
- A diff-check invocation overriding Git's Windows newline conversion reported
  CRLF as whitespace; reran with repository-native Git configuration and passed.
  No files or repository settings were rewritten to suppress that artifact.

No paid-provider, separate opt-in live reset, production SMTP, real production
deployment, remote protection/hosted CI, new full dependency/history-secret/
image-CVE audit or manual spoken assistive-technology result is claimed here.
Dependencies/base-image policy and thresholds were not changed. Those release
checks remain in their established gates; prior Phase 9 evidence is historical.

Request persistence is bounded best effort, historical metrics shrink on
cleanup and token costs are not a complete billing ledger. Audits are diagnostic,
not tamper-proof or an asserted human identity for direct database changes.
Operators still own requester verification, deployment notice/contracts,
proxy/collector rotation, external mail/provider copies, backups and export expiry.

## Cleanup and completion

Disposable PostgreSQL/Mailpit/journey/image-probe containers, generated temporary
credentials/settings and harness processes were cleaned up by their guarded
owners. Three newly tagged local `cardchemy-*:phase10-verification` images remain
as verification artifacts; existing operator containers/images/volumes were
preserved. No export, deletion, retention apply or external telemetry command
was run against operator data. Phase 10's eleven tasks are marked complete with
the evidence above; Phase 11 is unchanged except preserved pre-existing edits.
