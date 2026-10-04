# Proposal: public synchronous source-ID pilot on Free tier

Date: 2026-09-29 (America/Chicago). The operator confirmed the Gemini API
project is on Free tier and selected a public-only synchronous pilot after the
one approved Gemini 3.6 Batch creation returned HTTP 400. This is a **proposal
and keyless preparation**, not a new provider authorization, plan/ADR change,
runtime model selection or quality result. The consumed Batch and synchronous
claims, populated database, original PDF attachments and root `.env` remain
untouched. Ask remains disabled.

## Why this candidate

The [Google pricing table](https://ai.google.dev/gemini-api/docs/pricing)
lists `gemini-3.6-flash` synchronous Standard service as available on Free
tier, but its Batch row as unavailable. This strongly explains the Batch
HTTP 400, without proving the exact rejection reason because the response
body was not retained. Earlier 3.6 synchronous pilots accepted three public
groups and then returned HTTP 503 on the next group, including one bounded
evaluation retry; those availability stops have **no quality score**.

For a distinct candidate, Google lists `gemini-3.5-flash-lite` synchronous
Standard input/output as Free of charge on Free tier and documents a stable
model ID, thinking and structured output support in its
[model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite).
This model's source-ID quality and actual account availability are unknown.
The three accepted 3.6 ID sets cannot be mixed into its score. A separate
3.5 Flash-Lite score also cannot validate the currently pinned 3.8 Ask worker.

Only frozen public CC BY 4.0 PDF-derived questions and four candidate
page/cue snippets from exactly two of the eight independently reviewed public
PDFs per group would be submitted. The packet has 48 calibration groups and
48 heldout groups from different PDFs. The new harness must bind the public
packet, labels, issued IDs, prompt/schema, scorer and model version by hash,
using an exclusive one-use approval claim. It must accept only 0–3 unique
issued page IDs, with no answer text. The first normal calibration call also
checks transport and response shape. A provider, quota, network or malformed
result stops without replay or opening heldout. Only a passing full
calibration may open the frozen heldout. No private Knowledge, chat history,
identity, independent labels or raw PDF bytes are submitted; no DB state,
index or Ask runtime is changed.

## Exact proposed one-use envelope, pending separate approval

| Guard | Proposed limit |
| --- | --- |
| Endpoint/model | `POST https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`; `gemini-3.5-flash-lite`, low thinking, structured IDs, `store=false`, no tools or redirects. |
| Requests | At most 48 calibration calls and, only on a full calibration pass, 48 heldout calls: **96 physical calls total**. No automatic retry, model fallback or replay of a completed group. |
| Pace/time | At least 20 seconds between request starts; at most 30 seconds per call and 120 minutes for the whole pilot. One failure stops. |
| Tokens | At most 8,192 input and 1,024 combined output/thinking tokens per call; at most **786,432 input and 98,304 output** across all 96 calls. |
| Cost guard | Current Free-tier list price is USD 0; reserve the current Paid Standard equivalent of USD **0.30 input / 2.50 output per million tokens** in case billing state changes. The unrounded token calculation is USD 0.4816896; rounding each of 96 per-call reservations upward to whole microdollars gives **USD 0.481728**, below the **USD 0.50** new-cost ceiling. Earlier failed-call actual charges remain unknown and outside this ceiling. The guard is not a provider invoice. |

[Google's rate-limit guide](https://ai.google.dev/gemini-api/docs/rate-limits)
says quotas are per project/model and actual account limits appear in AI
Studio; the proposed pacing cannot guarantee admission. A 429, 503 or any
other failure consumes that physical attempt and stops this one-use run.
Free-tier submitted content may be used to improve Google's products and
human reviewers may see it under Google's
[API terms](https://ai.google.dev/gemini-api/terms); this pilot therefore
uses only public educational material and does **not** authorize a private
lecture transfer. The owner clarified that Cardchemy is intended only for
students aged 18 or older. Regional availability and any eventual private
course transfer still require separate release checks under those terms.

The existing public calibration/heldout, no-match and original-PDF release
gates remain unchanged: at least 10/12 useful-page hit@3 on the independent
lecture evaluation, at least 3/4 per question group, at least **90% useful
among every displayed original-PDF page card**, and no fabricated,
unauthorized or stale source. A public pilot can establish candidate source-ID
selection only; it cannot itself finish Lane 6 or enable Ask. A later real
published-Knowledge transfer needs an explicit privacy and endpoint/model/
price/call/token/time/cost decision, and the runtime model would need a
separate versioned policy change and release evidence.

The keyless harness and tests are being prepared independently. Before any
live call, their exact script and packet hashes, admission preflight and
scorer contract will be verified. A secret-safe local presence check found
the dedicated `RAG_SOURCE_JUDGE_API_KEY` unset, while a different existing
Gemini key is present. The source-ID pilot must use the dedicated setting;
the operator chose to create and enter a distinct key in the same Free-tier
project rather than copy the existing credential. No key value was displayed,
logged or changed by this check. Only then should the
operator be asked to
approve the exact envelope above and the corresponding Lane 6/ADR-024
evaluation note. Until then, no paid or free-quota Gemini request is made.
