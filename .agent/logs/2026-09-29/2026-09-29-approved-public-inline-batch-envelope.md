# Approved public inline Batch source-ID pilot

Date: 2026-09-29 (America/Chicago). The operator explicitly approved the
exact public-only Batch question after reviewing the keyless harness and
proposal. The approval includes updating Lane 6 and ADR-024 and one bounded
Gemini 3.6 Batch quality pilot. It does not authorize private-source transfer,
an Ask runtime policy change or Ask activation. Earlier synchronous and
checkpointed approvals were consumed and are not reused. The retained
database, root `.env`, original PDFs and prior pilot ledgers remain unchanged.

## Exact authorization

| Guard | Approved limit |
| --- | --- |
| Model/endpoint | `gemini-3.6-flash`, low thinking, nested `store=false`; `POST https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:batchGenerateContent`, then authenticated `GET https://generativelanguage.googleapis.com/v1beta/batches/{id}` only. |
| New inputs | 45 unresolved calibration questions from the frozen eight-PDF CC BY 4.0 public packet. Each has the current public question and four public page/cue candidates from exactly two PDFs. Keep the three accepted older calls. Submit a second 48-item public heldout from different PDFs only after all 48 calibration cases pass the unchanged scorer. |
| Output/privacy | Only issued page IDs; no private Knowledge, history, identity, labels, raw PDF bytes, answer draft or database write. Batch request/result resources may be retained by Google for up to six weeks despite nested `store=false`. |
| Requests/time | At most two non-replayed creation POSTs and 100 total status GETs; each known job polled no more often than every 30 minutes, each HTTP call at most 30 seconds, both jobs within 48 hours. No File API, create retry, item replay or model fallback. |
| Tokens/cost | At most 8,192 input/1,024 combined output and thinking tokens per new item; 761,856 input/95,232 output tokens total. Conservative post-2026 Batch guard USD 0.75 input/USD 3.75 output per million tokens, full reservation USD 0.928512, **new cap USD 1.00**. Actual costs of earlier HTTP 503 attempts remain unknown and separate. |

The freeze identity is
`lane6-public-36-inline-batch-20260929-4d56d49e618a40fb9ab3848b2683e83f`.
The new runner is the only tool admitted by this approval; its exact SHA and
canonical approval receipt are checked immediately before a paid create. A
durable claim is written before a non-idempotent POST. An uncertain creation,
incomplete/error item, missing/duplicate key, expired job or failed complete
calibration stops the pilot without a quality pass or heldout submission.

The plan, ADR-024, index, roadmap and current-state note were updated after
this approval. The existing source-only 0–3 page navigation, one current-
question embedding, one source-ID call and no automatic Ask retry remain. The
four open Lane 6 items and Ask-off fence remain until independent private PDF
usefulness, no-match, access, accessibility and release gates pass. This log
records authorization, **not** provider execution or a quality result.
