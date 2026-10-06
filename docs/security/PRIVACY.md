# Privacy, retention, deletion and export

Current source-only Ask uses `related_knowledge_navigation_v8`, `visual_source_id_v5` and `literal_subject_admission_v2` at Alembic head `20261002_0033`. Fresh installations remain default-off. The retained local installation was enabled after its measured release gates on 2026-10-04; see the [closure evidence](../../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md). Historical policies and database rows remain immutable and readable; they cannot execute as new jobs.

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
OCR runs locally. New AI work sends equivalent evidence only to the native
Gemini endpoint selected by the closed catalog.

The approved [Subject Knowledge boundary](../architecture/SUBJECT-KNOWLEDGE-FLOW.md)
adds durable extracted pages, chunks and vectors independently from temporary
PDFs and flashcard publication. Phases 14–16 implement private capture,
document embedding and internal authorized retrieval. Before enabling these
writes for real users, the operator notice must disclose permanent text
retention and embedding transfer to the configured endpoint. Embedding requests
contain document chunks; the source-only Ask query embedding contains only the
current question. It sends no lecture excerpt or bounded chat history to an
answer model. Historical answer-policy jobs sent question, eligible evidence
and bounded private history to a separate answer request. Transfers occur only
in the responsible worker.
Provider enablement or
a key being present does not authorize evaluation spending.

The released [ADR-024](../decisions/ADR-024-gemini-source-id-judge.md)
source-only path permits, after at most one current-question embedding,
the same current raw question plus bounded exact
text/cues and bounded rendered PNG images from currently authorized,
reviewed and published original Knowledge pages to Gemini for **source-ID selection only**. It must not send
raw PDF bytes, full prior chat, other Subjects, unpublished pages or an answer
draft. Only an eligible unresolved follow-up may additionally transfer its
immutable unique literal subject from the strictly preceding user question,
at most 160 characters/twelve words, rechecked before dispatch; the full prior
question and assistant text are excluded. The reply contains only closed
issued-ID/category/cue judgments; the server derives and reauthorizes all
shown source references. The worker sends this bounded request
with `store=false`, one HTTP attempt and no redirect; that setting does not
prevent provider abuse-monitoring retention. This is materially more content
transfer than the historical v3 query-embedding-only path, even though no answer
is generated.
Public-first calibration and independent private quality/display/release gates
passed for the recorded local activation. New installation transfer still needs
the provider/content disclosure and applicable quality/release evidence;
new live evaluations need a fresh exact endpoint/model/price/call/token/time/cost
approval.
Neither the architecture approval nor the current key establishes an active
billing tier, eligible audience or release. Operators must check the current
[Gemini API terms](https://ai.google.dev/gemini-api/terms),
[abuse-monitoring policy](https://ai.google.dev/gemini-api/docs/usage-policies)
and [optional project logging settings](https://ai.google.dev/gemini-api/docs/logs-policy)
before that step. Paid prompts/responses are described by Google as excluded
from product improvement, but the abuse policy permits retention of prompt,
context and output for monitoring; do not promise zero provider retention.

The default embedding profile uses Google's official Gemini endpoint and
`gemini-embedding-001` under
[ADR-014](../decisions/ADR-014-native-gemini-rag-profiles.md). The embedding
worker sends document chunks with `RETRIEVAL_DOCUMENT`; the Ask worker sends
only current questions with `QUESTION_ANSWERING`. The historical
`gemini-3.5-flash` structured answer call is retired from new Ask work.
Optional `gemini-embedding-2` sends separately framed
document/query text under its distinct staged space and never mixes with 001.
The authorized profile endpoint supplies configured and active provider/model
disclosure shown before an enabled upload or question; it never returns keys or
private endpoint credentials.

The old pinned local NLI/extractive-QA verifier is historical and has no role
in [source-only Ask](../decisions/ADR-023-original-pdf-source-navigation.md).
Existing private history retains its ownership, expiry and source-redaction
controls. New Ask admission remains default-off and requires an exact active
embedding-space match, current embedding price and a passed source-window/
access and page-open gate. Knowledge document embedding remains independently
available. The Ask worker selects at most three related PDF pages from retrieved
published Knowledge after at most one current-question query embedding; a
bounded local lexical fallback is available if that embedding call fails. It
stores job-owned source/revision
references, explicit page/chunk source kind and offsets, not a second quote
copy or an answer citation. Own-account reference exports include that source
kind so the offsets remain interpretable. Every
authorized job/page read rechecks current publication, revisions and access;
one invalid source hides the whole bundle. Validated originals are retained in
a separate encrypted, revision-bound archive with an independent key. Students
open the physical PDF page through authenticated bounded byte ranges in the
app, with the extracted-text cue beside it. Historical revisions without an
exact original use an explicit extracted-text fallback until an instructor
attaches a PDF whose SHA-256 and page count both match the revision. The page
reference is labeled related and unverified, not a verified answer.
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
aggregate reporting is off by default; [its exact payload](../operations/OBSERVABILITY.md#optional-telemetry)
contains no document content.

## Lifecycle table

| Data | Retention/deletion | Export |
| --- | --- | --- |
| Account/profile | Until explicit operator deletion; owned dependents cascade. Sessions are revoked through logout/reset and expire. | Own profile; never password/token hashes. |
| Subjects, sets and generated/manual cards | Until instructor content deletion or owner-account deletion. Generated source quotations remain in cards after PDF cleanup. | Instructor's owned content/provenance; other students' PII excluded. |
| Enrollment, study progress and answer receipts | Until owning account or related subject/card deletion. Receipts have no age-based purge, preserving logical retry idempotency. | Only the account's own records and allowlisted receipt results. |
| Generation job history | Configurable terminal-history period; only terminal jobs without retained sources qualify. Content/result sets survive job-history deletion. Job reservation idempotency lasts while its history is retained. | Own safe job metadata/usage; no source bytes/hashes/claim tokens. |
| Temporary encrypted PDFs | Success, cancellation and permanent failures remove sources atomically; retryable failures retain them for the configured 1–168 hours (default 24). Unfilled upload reservations expire (default 15 minutes). | Excluded; source storage is transient, not a document archive. |
| Pending validated-card choices | Only fully validated distinct cards may be encrypted in a job-bound, owner-private payload after an insufficient bounded run. A finite 1–168-hour expiry and per-job/user/deployment byte caps apply. Exact smaller-target confirmation, explicit retry, cancellation and expiry remove the payload; no partial set or candidate text is returned before confirmation. | Staged payload and key/operation hashes are excluded; own safe status, observed count, expiry and bounded quality diagnostics are available. |
| Subject Knowledge | Extracted pages, chunks, vectors and separately encrypted original PDFs persist until explicit document/Subject/owner deletion. Private/staged/failed revisions count against permanent capacity. Reindexing uses retained pages. Original-PDF archives are revision/SHA bound; existing revisions need exact-original attachment. Cancellation may remove an unreviewed private capture created solely by that job; independently reviewed/published Knowledge survives card-choice cancellation/expiry. A flashcard failure can retain a valid private capture. Document deletion preserves detached flashcards. | Instructor-owned documents, pages, chunks and safe revision/job metadata are allowlisted. Vectors, encrypted archives, original-file bytes, decryption material, claim/idempotency hashes, raw temporary PDFs and other students' data are excluded from JSON account export. Authorized original-PDF page reads are a separate access-controlled capability. |
| Ask AI conversations | Only their user can read them, including instructors. Each question expires after 90 days by default under bounded cleanup. Historical answer messages/citations remain under their old policy until the approved development reset. Reads recheck current Subject access. | Only the requester's own threads/messages/job metadata are allowlisted. No instructor access to student chats. Provider prompts, claim tokens, session IDs and idempotency hashes are excluded. |
| Related Ask source references | At most three job-owned exact source offsets, each expiring no later than its question message. Current-access reads reconstruct a whole bundle or nothing; unpublish, replacement, deletion, expiry or access loss hides all excerpts, extracted pages and original-PDF range reads. Related references are explicitly unverified. A source-only result has no assistant answer message; question/job deletion cascades refs without deleting independent Knowledge archives. | Own reference metadata and offsets only, without duplicate quote text, cross-user chats or raw provider output. |
| Auth/reset/invitation metadata | Expired records may be pruned after the configured grace; linked outbox records prevent pruning. Consumed invitations remain consumed while retained. | Tokens/codes/hashes and email recipient bindings excluded. |
| Email outbox | Worker cleanup: sent 7 days, failures 30 days by default; configurable. Active delivery and ambiguous-send recovery retain their existing guards. | Bodies/links/recipient lists excluded. |
| Rate/quota metadata | Cleanup only after active rate/UTC quota windows and configured metadata grace. Quota operation receipts remain while linked job history exists, preserving manual-retry idempotency; detached charges survive subject/job deletion until their grace expires. | Excluded. |
| Request/worker diagnostics and privileged audits | Configurable request/audit retention; stale worker-heartbeat rows expire after 24 hours. Deleted audit actors become null, opaque target IDs remain until audit expiry. Stdout/edge/proxy logs require collector-level expiry. | Not a user content export; operator-only diagnostics. |
| Backups, delivered mail, provider copies, private exports | Operator/recipient/provider policies apply independently; an application delete cannot erase these copies. | Operator safeguards and secure fulfillment. |

## Operator controls

Settings live only in root `.env`. [Configuration](../operations/CONFIGURATION.md) defines
their bounds; [observability](../operations/OBSERVABILITY.md) explains diagnostics. Metadata
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
also cascades original-PDF archives and encrypted blocks through their content
revision. Archives have fixed caps of 100 MiB per PDF, 256 MiB per Subject,
512 MiB per uploader and 2 GiB per deployment; the ordinary configured upload
limit may be lower. Their independent encryption key must be recoverable with
backups. Logical deletion does not erase backups or browser copies already
delivered. PDF responses are authenticated, bounded and `no-store`.
Account deletion
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
