# Proposal: public Batch source-ID quality evaluation after repeated HTTP 503

Date: 2026-09-29 (America/Chicago). Scope: read-only investigation and a
proposed next Lane 6 experiment. Branch `main` at starting HEAD `6c02d6c`;
the shared worktree, retained database and PDFs, root `.env`, consumed pilot
ledgers and Ask-off state were preserved. This record is **not** an approved
plan or ADR change, paid-call envelope, runtime policy or quality result. No
provider call, download, private Knowledge read or database write was made.

## Evidence and diagnosis

The [latest checkpointed public pilot](2026-09-29-checkpointed-public-source-id-503-stop.md)
revalidated three accepted `gemini-3.6-flash` source-ID responses, then saw
HTTP 503 twice on the first unresolved calibration group, including its one
authorized evaluation-only retry after 20.017 seconds. It accepted no new
group. All associated one-shot claims are consumed. The three selected ID
sets have not been inspected or scored for tuning, and the frozen 48-group
calibration and distinct-PDF 48-group heldout have **no quality score**.
Google's [error guide](https://ai.google.dev/gemini-api/docs/api-errors) calls
503 temporary service unavailability; the exact cause of these calls is not
known. It cannot be used as evidence for or against source-selection quality.

The [source-selection review](../2026-09-28/2026-09-28-source-selection-root-cause-review.md)
found useful candidates in exposed retained-course top three for 11/11
questions but only 19/33 displayed pages useful. In the public Mixedbread
calibration, raw pair-score top three contained a useful cue and original
page in 36/36 positive groups, while three frozen display selectors failed
their no-match/precision/positive-hit calibration gates. The earlier GTE
threshold failed its quality gate. The [Qwen3-4B diagnostic](../2026-09-26/2026-09-26-local-relation-4b-experiment.md)
timed out at startup before any semantic case, and concerned the retired
answer-verifier path. These observations support measuring source selection
separately from candidate recall and provider availability; they do not
justify another query vector, relaxed page-usefulness gate or Ask activation.

## One concrete public-only path for consideration

Google documents `gemini-3.6-flash` as supporting the
[Batch API](https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash).
The [Batch guide](https://ai.google.dev/gemini-api/docs/batch-api) supports
keyed inline `GenerateContentRequest` jobs under 20 MB, asynchronous per-item
responses/errors, and a target turnaround of 24 hours; jobs can also fail or
expire. The [REST reference](https://ai.google.dev/api/batch-api) specifies
`models.batchGenerateContent` and per-request metadata keys. This is an
evaluation transport hypothesis, not proof that Batch will accept every
request or that synchronous Ask will become available.

1. Implement a **new, versioned, public-only Batch harness** without editing
   or replaying the consumed synchronous runners. Hash-bind the unchanged
   eight-PDF CC BY 4.0 packet, independent labels, prompt/schema, old scorer,
   old three accepted ID/usage receipts and both group-four 503 claims.
   Preserve the three accepted decisions; include exactly the **45 unresolved
   calibration groups** in one keyed inline Batch job. Each nested request
   must preserve the same model-facing question, four exact public page/cue
   candidates from two PDFs, low thinking, structured ID-only output and
   `store=false`. Neither labels nor PDF bytes leave the machine. Validate
   the wrapper and one-to-one opaque key mapping offline before submission.
2. Accept only a complete, correctly keyed set of 45 valid responses with
   issued, unique, at-most-three IDs and valid finish/usage accounting. Merge
   them with the three previously accepted results and invoke the unchanged
   frozen calibration scorer **once**. A per-item error, missing/duplicate
   key, malformed output, uncertain creation or incomplete job means no
   calibration quality claim; do not inspect partial selected IDs for tuning
   or resubmit any item under the same approval.
3. Only a passing full calibration receipt may admit a **second** inline Batch
   job for the 48 frozen heldout groups from four different PDFs. Score the
   heldout once, under the unchanged hit/no-match/cardinality and **at least
   90% useful among every displayed cue-plus-original-PDF page card** gates.
   Failed/unknown items count as a failed evaluation, not safe abstentions.
   Report physical job availability, per-item status, usage/uncertain cost,
   candidate recall and selected-page usefulness separately.

This is the same `gemini-3.6-flash` quality candidate with a different
evaluation service. A public pass can justify the next gated step but does
not prove interactive `generateContent` reliability, the application’s
up-to-twelve-page candidate pool, private-lecture performance or the current
v4 worker, which is still pinned to `gemini-3.8-flash`. The application must
remain source-only, at most one current-question embedding and at most one
source-ID call per Ask attempt, with zero automatic Ask retries. The prior
Gemini 3.8 and local audit failures cannot be recycled as a pass.

## Suggested **new** approval envelope, not authorization

The consumed synchronous approval does not cover Batch. Before any paid
request, update Lane 6/ADR-024 through the operator's plan-change approval,
build keyless tests, then obtain a **fresh explicit** endpoint/model/price/
request/token/time/cost/content-transfer authorization. A concrete proposed
envelope is:

| Guard | Proposed bound |
| --- | --- |
| Endpoint/model | `POST https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:batchGenerateContent`, `gemini-3.6-flash`; authenticated `GET /v1beta/batches/{id}` for status/results only. |
| Data | Frozen public current questions and four public candidate page/cue snippets from exactly two of the eight reviewed CC BY 4.0 PDFs per item; opaque keys and `store=false` per nested request. No private Knowledge, history, identity, labels, raw PDF bytes, tools or answer draft. |
| Batch creation | At most **two** keyed inline creation POSTs: one with 45 calibration items, one with 48 heldout items only after a passing calibration. No File API upload, duplicate create, item replay or provider fallback. Wrapper size capped at 2 MiB and checked offline against the 20 MB service limit. |
| Polling/time | At most **100 authenticated status GETs total**, no more often than every 30 minutes per known job after its first status read; at most **48 hours total** for both jobs. Bound each create/status HTTP request to 30 seconds. No additional create if the first job misses its deadline or is incomplete. |
| Tokens | At most 8,192 input and 1,024 combined output/thinking tokens per item; at most **761,856 input** and **95,232 output** tokens across 93 newly submitted items. The three earlier accepted calls and failed calls are outside this new cap. |
| Cost | Use conservative **Batch** guard prices USD **0.75 input / 3.75 output per million tokens**, matching Google's stated post-2026 rates. Full token reservation is USD **0.928512**; cap new reserved spend at **USD 1.00**. Actual charges for earlier failed calls remain unknown. A batch or item without usage reserves its full maximum. [Pricing](https://ai.google.dev/gemini-api/docs/pricing). |

The harness should place a durable, exclusive create claim **before** each
POST and persist the returned job name immediately. An ambiguous create
response, 503 or timeout consumes that creation allowance: do not send a
second create for the same split. Known-job status GET failures may be
reobserved only within the proposed polling count/time bounds; they must not
trigger another job. If a job reports a per-item error, expiration or
incomplete output, stop without scoring or automatic resubmission. Batch
acceptance can itself be unavailable. Batch stores submitted public requests
and results for asynchronous processing even when each request sets
`store=false`; the flag does not erase the job resource or override provider
retention terms. Keep result files/IDs in access-restricted OS Temp, log only
hashes and safe aggregate status, and include this distinct retention surface
in operator disclosure and approval.

## Release boundary and verification of this proposal

Even a full public Batch pass would require a separately approved, versioned
3.6 runtime/model change, an authorized real-published-Knowledge transfer
and live spending envelope, independent original-PDF usefulness and no-match
measurements, current authorization/revision/PDF-open checks, operational
availability and spoken accessibility evidence. A Batch score cannot close
the four open Lane 6 quality/release boxes or enable Ask by itself. If Batch
fails to return a complete calibration, preserve the valid prefix and report
availability separately; a different model (including 3.5 Flash-Lite) would
be a separately frozen candidate with its own approval and full public gate.

This record was produced from repository documents and official Google API
documentation only. No script, model, database, provider or retained app was
executed for this proposal. Its only repository changes are this dated record
and the log-index link; the current plan, ADR and runtime remain unchanged.
