# Privacy, retention, deletion and export

This describes implemented technical behavior and the deployment operator's
responsibilities. It is not a promise of legal compliance or a deployment's
completed privacy notice. Operators must supply their contact, audience,
purpose, lawful basis, location, subprocessors and retention choices before
accepting real users. See [diagnostics/redaction](OBSERVABILITY.md),
[data ownership](architecture/DATA-MODEL.md) and [database operations](DATABASE_OPERATIONS.md).

## Data flows and provider disclosure

Accounts store normalized email, name, password hash and role. PostgreSQL holds
subjects, cards, enrollment, progress/answer receipts, revocable auth/reset and
invitation state, encrypted temporary PDFs, generation metadata, private
Subject Knowledge and per-user Ask AI conversations, email outbox and
content-free diagnostics/audits. Access tokens remain in browser memory;
refresh tokens use protected cookies. There is no offline answer store.

When generation is enabled with `FLASHCARD_AI_PROVIDER=gemini`, extracted document text
and evidence, instructions, derived summaries and prior generation context are
sent from the generation worker to Google's Gemini Developer API. Google
returns summaries/cards for local validation. This flow sends document content
outside the deployment; encrypting the retained PDF does not prevent it.
The application does not intentionally include account email or student
progress in AI requests, but a lecture PDF can itself contain personal data.
OCR runs locally. The OpenAI-compatible profile sends equivalent evidence to
the operator-selected endpoint, which can be hosted or local.

The approved [Subject Knowledge boundary](architecture/SUBJECT-KNOWLEDGE-FLOW.md)
adds durable extracted pages, chunks and vectors independently from temporary
PDFs and flashcard publication. Phases 14–16 implement private capture,
document embedding and internal authorized retrieval. Before enabling these
writes for real users, the operator notice must disclose permanent text
retention and embedding transfer to the configured endpoint. Embedding requests
contain document chunks; answer-worker query embedding contains a question,
and answer requests contain the question, eligible evidence and
bounded private history. Transfers occur only in the responsible worker.
Provider enablement or
a key being present does not authorize evaluation spending.

The default embedding/answer profiles use Google's official Gemini endpoint,
`gemini-embedding-001` and `gemini-3.5-flash` under
[ADR-014](decisions/ADR-014-native-gemini-rag-profiles.md). The embedding
worker sends document chunks with `RETRIEVAL_DOCUMENT`; the answer worker sends
questions with `QUESTION_ANSWERING` and sends bounded evidence/history for the
structured answer/support calls. The authorized profile endpoint supplies the
provider/model disclosure shown before an enabled upload or question; it never
returns keys or private endpoint credentials.
Operators must review their current provider contract, retention and location
before enabling any transfer. This guide makes no zero-retention or training-use
claim about that provider. A disabled RAG flag suspends new RAG work and keeps
stored Knowledge; disabling a provider suspends only its model work.

As checked on 2026-09-17, Google's paid/unpaid data terms differ: unpaid content
may improve products and undergo human review; paid prompts/responses are not
used for product improvement but may be logged for abuse monitoring. The
operator must verify current billing, region, age/audience restrictions and
contract eligibility rather than infer them from a configured key. Google's
current terms restrict API clients likely accessed by minors and require paid
services for EEA/Swiss/UK users. Review the [Gemini API terms](https://ai.google.dev/gemini-api/terms)
before enabling this provider for the intended audience. Provider-side logging
and sharing have separate settings; review [Google's logging policy](https://ai.google.dev/gemini-api/docs/logs-policy)
and [abuse monitoring](https://ai.google.dev/gemini-api/docs/usage-policies).
Do not claim zero provider retention or retroactive provider deletion.

Operators choose a suitable provider/contract, disclose this transfer before
upload, require authorized uploads, and prohibit confidential/personal content
where the provider terms disallow it. SMTP relays receive recipient addresses
and rendered invitation/reset/security messages, including sensitive links;
production SMTP is encrypted. Delivered mail is outside database deletion.
Mailpit captures complete messages only in local/test deployments. Optional
aggregate reporting is off by default; [its exact payload](OBSERVABILITY.md#optional-telemetry)
contains no document content.

## Lifecycle table

| Data | Retention/deletion | Export |
| --- | --- | --- |
| Account/profile | Until explicit operator deletion; owned dependents cascade. Sessions are revoked through logout/reset and expire. | Own profile; never password/token hashes. |
| Subjects, sets and generated/manual cards | Until instructor content deletion or owner-account deletion. Generated source quotations remain in cards after PDF cleanup. | Instructor's owned content/provenance; other students' PII excluded. |
| Enrollment, study progress and answer receipts | Until owning account or related subject/card deletion. Receipts have no age-based purge, preserving logical retry idempotency. | Only the account's own records and allowlisted receipt results. |
| Generation job history | Configurable terminal-history period; only terminal jobs without retained sources qualify. Content/result sets survive job-history deletion. Job reservation idempotency lasts while its history is retained. | Own safe job metadata/usage; no source bytes/hashes/claim tokens. |
| Temporary encrypted PDFs | Success, cancellation and permanent failures remove sources atomically; retryable failures retain them for the configured 1–168 hours (default 24). Unfilled upload reservations expire (default 15 minutes). | Excluded; source storage is transient, not a document archive. |
| Subject Knowledge | Extracted pages, chunks and vectors persist until explicit document/Subject/owner deletion. Private/staged/failed retained revisions count against permanent capacity. Reindexing uses retained pages; no permanent raw PDF is added. Cancellation deletes the revision/document created by that job; a flashcard failure can retain a valid private capture. Document deletion preserves detached flashcards. | Instructor-owned documents, pages, chunks and revision/job metadata are allowlisted. Vectors, claim/idempotency hashes, raw temporary PDFs and other students' data are excluded. |
| Ask AI conversations | Only their user can read them, including instructors. Each message and its sources expire 90 days after creation by default under bounded cleanup. Reads hide a stored answer/citations when any supporting content is unpublished, deleted or replaced, and recheck current Subject access. | Only the requester's own threads/messages/sources/job metadata are allowlisted. No instructor access to student chats. Provider prompts, claim tokens, session IDs and idempotency hashes are excluded. |
| Auth/reset/invitation metadata | Expired records may be pruned after the configured grace; linked outbox records prevent pruning. Consumed invitations remain consumed while retained. | Tokens/codes/hashes and email recipient bindings excluded. |
| Email outbox | Worker cleanup: sent 7 days, failures 30 days by default; configurable. Active delivery and ambiguous-send recovery retain their existing guards. | Bodies/links/recipient lists excluded. |
| Rate/quota metadata | Cleanup only after active rate/UTC quota windows and configured metadata grace. Quota operation receipts remain while linked job history exists, preserving manual-retry idempotency; detached charges survive subject/job deletion until their grace expires. | Excluded. |
| Request/worker diagnostics and privileged audits | Configurable request/audit retention; stale worker-heartbeat rows expire after 24 hours. Deleted audit actors become null, opaque target IDs remain until audit expiry. Stdout/edge/proxy logs require collector-level expiry. | Not a user content export; operator-only diagnostics. |
| Backups, delivered mail, provider copies, private exports | Operator/recipient/provider policies apply independently; an application delete cannot erase these copies. | Operator safeguards and secure fulfillment. |

## Operator controls

Settings live only in root `.env`. [Configuration](CONFIGURATION.md) defines
their bounds; [observability](OBSERVABILITY.md) explains diagnostics. Metadata
cleanup is operator-run, dry-run by default and bounded to one batch per
category. No scheduled deletion of accounts, learning content, progress or
study receipts is enabled. Review counts before applying; schedule the same
command through your deployment's approved scheduler if periodic pruning is
required. Repeat bounded batches while checking results.

```text
docker compose exec backend python -m app.cli cleanup-retention
docker compose exec backend python -m app.cli cleanup-retention --apply
```

The cleanup skips active work, sources, linked outbox state and current
rate/quota windows. It does not replace generation/email source/queue cleanup.
Set provider and backup retention separately. A DB row deletion is logical
deletion; PostgreSQL storage reclamation and backup expiry are separate.

For an authorized account request, an operator verifies the requester and
selects their UUID through trusted account administration. No public account
export/delete or role-change API is introduced. Export writes an exclusive new
JSON file, restricts access to the current OS user, and prints only a completion
ID. PostgreSQL exports use a consistent read-only snapshot. Save outside the
repository in a private location; securely transfer it and expire the copy.

```text
python -m app.cli export-account --id ACCOUNT_UUID --output PRIVATE_NEW_FILE.json
```

Run natively from `backend` with the validated operator environment, or inside
the backend container using a private destination and a controlled copy-out.
Exports intentionally contain authorized private content; never send them to
logs, telemetry, issue trackers or this repository. They omit other accounts,
credentials, invitation codes, rendered email and temporary PDFs.

The current exporter includes instructor-owned Knowledge documents, pages,
chunks and safe revision/index-job metadata from the same consistent snapshot;
embedding values and internal hashes/claims remain excluded. Account deletion
takes the global Knowledge writer lock and refuses running generation, capture,
index or answer claims. Subject and document deletion use the same ordered lock
and refuse active related work, so a stale worker cannot resurrect content.
Ask AI exports include only the requester's private conversation and
safe job fields; they never include another user's chat. Backups,
provider copies and private export files retain their separate deletion limits.

Before account deletion, verify authorization, the UUID and a usable backup;
stop admission and drain/stop generation, index, answer and email workers. Use an operator
container with the same validated settings to run:

```text
docker compose stop -t 45 backend worker index-worker answer-worker email-worker
docker compose run --rm --no-deps backend python -m app.cli delete-account --id ACCOUNT_UUID --apply --writers-stopped
docker compose up -d --wait backend worker index-worker answer-worker email-worker
```

The acknowledgement flags are mandatory; the service additionally locks the
account and related work and refuses running generation/sending email claims.
Recover stale claims through normal worker fencing before retrying deletion.
An instructor's deletion removes their owned subject/content tree and related
student progress in that tree. Recipient-bound invitation/outbox copies of a
deleted account are also removed/redacted; used invitations keep consumption
state, while unused addressed invites are removed. Audits retain opaque
resources and null deleted actors under their separate policy. No real account
or operator data is deleted by ordinary test commands.
