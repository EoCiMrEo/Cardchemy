# Durable PDF generation

PDF generation is a PostgreSQL-backed job workflow. The API reserves a job,
accepts a bounded raw PDF body, and returns `202 Accepted`; a separate worker
extracts text, optionally captures private Subject Knowledge, calls the model,
and atomically creates the set and cards. Leaving the page or restarting the API
does not discard queued work.

## Request flow

1. `POST /flashcards/generation-jobs` accepts metadata and a required
   `Idempotency-Key`. It returns a job in `awaiting_upload` and a `Location`
   header.
2. `PUT /flashcards/generation-jobs/{job_id}/source` accepts a raw
   `application/pdf` body. Both declared and streamed bytes are bounded.
3. `GET /flashcards/generation-jobs?subject_id=...` and
   `GET /flashcards/generation-jobs/{job_id}` expose owner-scoped progress.
4. `POST .../{job_id}/cancel` requests cancellation. `POST .../{job_id}/retry`
   uses a new required `Idempotency-Key` and is available only while an encrypted
   failed source is retained.

When `RAG_ENABLED=true`, normal generation uses the same extraction and one
shared page-aware preparation to capture private Knowledge and enqueue indexing
before card generation. It does not wait for embeddings. Supported Knowledge
capture failure is reported independently and does not discard a successful
flashcard result. A cancelled combined job removes the capture created by that
job; a non-cancelled flashcard failure may retain a valid private capture.

`POST /flashcards/knowledge-jobs` plus the same raw source-upload route creates
an explicit `knowledge_only` job. It uses separate queue/daily/source quotas.
Omitting `document_id` creates a new document; supplying an owned same-Subject
ID creates a new private revision. Replaying one idempotent operation returns
the same job, while changed metadata or bytes conflict. Source PDFs remain
transient in every mode.

Job states are `awaiting_upload`, `queued`, `running`, `completed`, `failed`, and
`cancelled`. The UI polls without overlapping requests, recovers jobs after a
reload, and exposes cancellation, retry, and the completed set link.

## Bounds, backpressure, and cost controls

Defaults are intentionally conservative and are configurable through the
variables in the repository-root `.env.example`:

- Upload: 10 MiB; page count: 100; extracted text: 500,000 characters.
- Requested cards: 1-100; active jobs per user: 2.
- Deployment: 20 active jobs and 100 pending upload/queued jobs.
- Daily per user: 20 accepted jobs, 500 requested cards, and 100 MiB uploaded.
- Daily deployment: 1,000 jobs, 50,000 cards, and 10 GiB uploaded.
- Retained encrypted source: 50 MiB per user and 1 GiB per deployment.
- Worker concurrency: 2; provider-call concurrency shared across the worker: 3.
- Overall job timeout: 600 seconds; provider timeout: 90 seconds; extraction
  timeout: 60 seconds and 512 MiB on production Linux workers.

Admission and quota decisions use a PostgreSQL transaction-level advisory lock,
so concurrent requests cannot race past a limit. Quota events are append-only
for the lifetime of the user and are charged only after the source is accepted.
The limits endpoint reports the current per-user remainder and UTC reset time.

Workers claim rows with `FOR UPDATE SKIP LOCKED`, a unique claim token, and a
renewed lease. A stale worker cannot persist results. Retryable infrastructure
failures use bounded exponential backoff with full jitter; provider failures
stop without automatic whole-job replay and retain the source for a manual retry.
Permanent PDF/output failures do not retry. Every persistence step—set, cards,
source deletion, and terminal job state—commits in one transaction, so no empty
set is left behind.

## PDF validation and public errors

The server requires a supported media type and a `%PDF-` signature; filenames
are display metadata only. Parsing happens in a killable child process, never on
the API event loop. Encrypted, malformed, zero-page, over-page, over-text,
image-only, OCR dependency, OCR timeout, and extraction resource failures use
stable public error codes and bounded messages. Raw exceptions and model output
are logged server-side only and are not returned to clients.

## Source storage and retention policy

Source PDFs are temporary and inaccessible through the public API. They are
stored in a separate `generation_job_sources` table as AES-256-GCM ciphertext
with a random nonce and request-bound authenticated data. The required
`GENERATION_SOURCE_ENCRYPTION_KEY` is independent from the authentication
`SECRET_KEY`.

- Success, cancellation, and permanent failure delete the source in the same
  transaction as the terminal state.
- A final retryable failure retains ciphertext for 24 hours by default. Cleanup
  deletes expired ciphertext and disables retry.
- An abandoned upload reservation expires after 15 minutes.
- Subject deletion cascades active jobs and their source. Job metadata contains
  no PDF payload; completed set deletion does not recreate or retain a source.
- Knowledge capture persists only extracted pages/chunks and later vectors, not
  the raw PDF. Reindexing rebuilds chunks from canonical stored pages.
- Database dumps and WAL archives can contain ciphertext and must remain
  encrypted and access-controlled. Keep the source encryption key in a secret
  manager and include it in protected disaster-recovery material.

Do not rotate the source encryption key while queued or retryable jobs remain.
Drain, complete, or cancel those jobs first; otherwise their source becomes
undecryptable. Never log the key, PDF text, ciphertext, or model prompt content.

## Optional OCR

OCR is disabled by default. To build the worker with Poppler and Tesseract and
enable it in Compose, set `PDF_OCR_ENABLED=true` before building:

```powershell
docker compose build backend worker
docker compose up -d migrate backend worker
```

The Docker build installs `poppler-utils` and `tesseract-ocr` only when OCR is
enabled. Configure an installed Tesseract language through `PDF_OCR_LANGUAGE`.
OCR renders each page at `PDF_OCR_DPI` and applies a per-page timeout; it is
substantially slower and more CPU/memory intensive than native extraction. Size
worker capacity and generation quotas from measured documents before enabling
it in a shared deployment.

## Operations

Generate required keys independently, preserve them in a secret manager, run
`alembic upgrade head`, and start both the API and worker. Useful checks are:

```powershell
docker compose run --rm migrate
docker compose run --rm backend alembic current --check-heads
docker compose run --rm backend alembic check
docker compose up -d backend worker
docker compose logs -f worker
```

The API and worker both refuse to start when configuration is invalid or the
database is not at the current Alembic head.

The worker's provider-neutral generation, grounding, token/cost budgeting, and
failure contracts are documented in `AI_GENERATION.md`; provider profiles and
model lifecycle guidance are documented in `AI_PROVIDERS.md`.

See [privacy](PRIVACY.md) for the provider transfer, temporary source lifetime,
persisted card quotations and export/deletion limits. Diagnose jobs through
[safe operational IDs and metrics](OBSERVABILITY.md), never raw PDFs or prompts
in logs.
