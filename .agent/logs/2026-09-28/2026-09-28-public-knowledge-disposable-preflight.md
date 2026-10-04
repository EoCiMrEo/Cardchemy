# Public Knowledge holdout: provider-free disposable preflight

## Scope and starting state

Lane 6 still needs a fresh published, source-separated original-PDF holdout.
The retained local database was at `20260927_0028` with three original lecture
PDFs attached; Ask admission was disabled. The checkout was `main` at
`6c02d6c` with extensive pre-existing edits, all preserved. This work used the
two newly sourced public Illinois lecture PDFs and a corrected, independently
reviewed twelve-case roster. The initial roster's proposed windows failed
literal app-extraction matching (0/12) and was retired before any selector or
provider execution. The corrected v2 roster is described in the
[independent review](2026-09-28-public-original-pdf-holdout-v2-independent-review.md).
It did not index/publish either source, create a database, call an AI provider,
execute retrieval, or view selector results. The operator has **not** approved
the additional document-index and new-holdout query-embedding cost envelope.

## Preflight implementation and measured result

Added `backend/scripts/preflight_public_knowledge_holdout.py` and twelve targeted
tests. The script accepts only a SHA-frozen, exactly two-source manifest under
the OS Temp directory. Each entry binds a PDF basename, SHA-256, HTTPS source
and license URL, and attribution. The license metadata is a provenance
requirement; the script cannot itself establish third-party figure rights.
It refuses changed bytes/path traversal, malformed or oversized source, failed
bounded extraction/capture, oversized chunk, more than two document embedding
batches, more than 8,000 estimated document tokens, a changed code-default
profile, or a bad cost guard. It
uses the current `PDFProcessor`, `prepare_document`, `estimate_tokens` and
Knowledge capture bounds. It does not read root `.env`, instantiate an SDK or
touch a database. Its output has only counts and admission limits.

The private OS-Temp manifest SHA-256 was
`1dda8eae4ab998bae83daa142ddb0caab6699ddf02695c875ebaf694c53e0251`.
The accepted v2 holdout SHA-256 was
`d841ae6489995f884266abf212f7c63f14952a348419bfc7aa42e923c00d6b12`;
the preflight rejects the retired v1 schema and checks all twelve proposed
windows as exact substrings of current PDF extraction on the physical pages.
Independent source review found source, excerpt and page useful in 12/12 cases.
The exact public PDFs passed extraction as 29 pages/29 chunks/2,922 estimated
document tokens and 31 pages/31 chunks/3,344 estimated document tokens: 60
chunks, 6,266 estimated document tokens, one 32-item-or-smaller batch per
document. The separately frozen twelve current questions total 272 estimated
query tokens, with a largest single question of 43; the roster bytes and
questions remain in OS Temp. The preflight performed **zero provider requests
and zero database writes**. `backend/venv/Scripts/python.exe -m pytest
tests/test_public_knowledge_holdout_preflight.py -q` from `backend` passed
**12/12**. No runtime Ask policy, plan checkbox or retained data changed.

## Controlled next step after a separate paid-call approval

1. Validate the frozen PDF/manifest/roster hashes, attribution and extraction
   again. Refuse any drift or changed runtime profile. Create a unique
   no-volume PostgreSQL container on a dedicated Docker network, generated
   credential file in OS Temp, and loopback-only host port. Do **not** use the
   Compose project/retained volume or root `.env` as database configuration.
   Migrate that empty database to head and check heads/drift before seeding.
2. Seed one disposable instructor, Subject and enrolled student. Use the normal
   Knowledge-only job/capture path with the exact original PDF bytes and
   current prepared pages, preserving the encrypted revision-bound PDF archive.
   Run the actual index worker for each queued job **once**, sequentially, with
   only the required provider credential in its isolated process, native SDK
   retries and application retries both set to zero. Stop on uncertain/failure;
   do not replay a call. Review and publish using the owner service only after
   both indexes are ready in the exact `gemini-embedding-001` active space.
3. Embed exactly the twelve frozen **current questions**, never prior chat or
   lecture text in a query request, and write the bounded vectors only under
   private Temp with hash/one-shot receipt. Run the v3/v9 diagnostic against
   the disposable database in read-only repeatable-read transactions. Grade
   displayed pages against the independently reviewed original PDFs, then
   exercise authenticated enrolled-student original-PDF byte ranges and
   negative access controls. This is separate from the manual spoken viewer
   accessibility gate.
4. Stop and remove only the exact owned disposable containers/network after
   preserving aggregate evidence. Verify the retained Compose volume, root
   configuration and Ask-off state remain unchanged. No selector tuning on
   this heldout set is allowed before scoring.

The proposed one-shot provider envelope is Google Gemini v1beta
`gemini-embedding-001:batchEmbedContents` with `RETRIEVAL_DOCUMENT` for at most
two document requests and 8,000 estimated input tokens, plus
`gemini-embedding-001:embedContent` with `QUESTION_ANSWERING` for at most twelve
question requests and 1,024 estimated input tokens. Zero retries; at most 60
seconds per document batch, 30 seconds per question call, and ten minutes for
the provider segment. At a conservative USD 0.20 per million input tokens,
expected current input is 6,538 tokens or USD 0.0013076; the proposed hard
admission cap is USD 0.002. This rate is a local guard, not a provider invoice.
The exact endpoints/modes match the [official embedding API](https://ai.google.dev/api/embeddings)
and current adapter; model pricing and actual billed use must be reviewed at
execution. No answer-generation/model call is in scope.

## Remaining limits

This is extraction and cost preflight only. It does not prove the sources can
be published, retrieval usefulness, PDF HTTP/browser opening, permissions,
latency or release readiness. Figure rights may differ from the text on the
slides; the independent holdout uses only lecture text for labels. Keep Ask
disabled and the four open Lane 6 quality/release boxes open.
