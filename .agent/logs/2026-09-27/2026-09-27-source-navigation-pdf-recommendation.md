# Source navigation and original-PDF recommendation

Date: 2026-09-27. Status: **operator approved architecture and implementation**
through the displayed approval question. Scope: the unfinished Ask branch of
product-quality Lane 6. The operator confirmed automatic unverified references
and original-PDF page viewing; paid indexing/query tests remain separately gated.
Preserve the current source-only product decision, root `.env`, retained data,
volumes, existing migrations and Ask's disabled admission gate. No provider call,
model inference, database write, service recreation or PDF upload was made for
this recommendation.

## Starting evidence and operator choices

- Frozen v7's independent challenge chose 4/8 useful sources and 3/8 false
  primaries. Even with the independently reviewed correct page supplied, its
  qualifier selected 1/12 sufficient lecture windows. This proves a
  conditional source-selection problem; it does **not** measure current
  real-query candidate recall or prove that every extracted page is complete.
- The one approved GTE INT8 audit met startup, RAM and latency bounds but
  selected 0/32 sufficient heldout windows at its frozen calibration threshold.
  Its aggregate does not preserve score-separability statistics, so model
  objective, calibration shift and corpus shift remain competing explanations.
  Another generic model or a lowered threshold is not a justified repair.
- The current `source_relation_units_v7` worker skips neighbor expansion as soon
  as initial qualification selects anything. Its follow-up lexical search can
  use a locally resolved question while the embedding still receives the
  original current question. These are concrete mechanisms to isolate in an
  end-to-end funnel, not proven causes of the private supplied-anchor failure.
- Knowledge currently retains extracted page text, chunks and vectors. It
  deletes the job's encrypted raw PDF after terminal success. `Review & Publish`
  approves a content revision, not question/page evidence pairs. The current
  extracted-page dialog cannot show original slide graphics or formulas.
- The operator chose **fully automatic** references that explicitly say
  “related published Knowledge, not verified evidence or an answer,” 2–3
  citations when useful sources exist, and opening the **original PDF page
  inside the app**. No instructor question/page curation and no Ask answer
  generator/verifier are requested. Treat “source” provisionally as a distinct
  PDF page reference; pages may come from the same lecture. Never add a weak
  page merely to reach two or three.

PDF extraction can omit or reorder information visible on a slide; pypdf
documents that PDFs store layout rather than semantic structure and that
pypdf is not OCR. The original page is therefore an essential learner-facing
source, not just a cosmetic preview. See
[pypdf text-extraction guidance](https://pypdf.readthedocs.io/en/4.2.0/user/extract-text.html).

## Recommended complete product contract

The full fix is **reliable, honest source navigation**. Ask must never produce
an answer, a “gold/verified/sufficient” badge or a claim that a passage proves
one. It should find likely useful lecture pages, present up to three exact
extracted snippets as *unverified reading cues*, and open each physical page of
the original published PDF. If it has only one credible page, show one. If it
cannot identify a useful page, show a distinct no-useful-match state and a
subject-scoped browse/search path; never fabricate a citation or fill the quota
with merely same-topic transitions.

This contract fully removes unsupported answer claims and makes source access
faithful. **No fully automatic system can guarantee that every arbitrary
question has 2–3 answer-sufficient pages in every PDF.** The separately
requested evidence-sufficiency ideas remain valuable *ranking features and
offline diagnostics*, but they cannot certify citations at runtime under the
chosen automatic/unverified contract. A stronger verified-evidence promise
would require a different decision, such as review of question/page pairs.

### 1. Preserve and serve the original lecture

- Add a durable, revision-bound, AES-GCM-encrypted PDF archive distinct from
  temporary `GenerationJobSource` and its job-fingerprint AAD. Keep an immutable
  source SHA, versioned encryption key identity, page count, length and bounded
  storage accounting. Use composite ownership/revision FKs. Capture the archive
  with the same fenced Knowledge transaction that commits canonical pages;
  a new PDF-viewer-ready revision never points to a partial archive. Older
  published revisions without recoverable PDF remain explicitly marked for
  hash-verified attachment or extracted-text fallback.
- Handle the configured maximum PDF size (up to 100 MiB) without whole-file
  decryption on the API event loop: bounded encrypted blocks plus a manifest
  can serve authenticated HTTP Range requests by decrypting only needed blocks.
  Recheck student enrollment or instructor ownership, publication, active
  content/index/space/corpus revision and the entire Ask reference bundle on
  **every** metadata/range request. Use `Cache-Control: no-store`, safe content
  headers, range validation/rate limits and revocation on unpublish, delete,
  replacement or expiry. Keep PDF bytes out of logs, exports and public paths.
- The current frontend CSP forbids iframe/embed and objects. Use a lazy in-app
  PDF.js canvas/text-layer viewer with authenticated, token-aware range fetch,
  page `N` from the canonical 1-based PDF page number, keyboard navigation and
  a nearby exact extracted quote. Do not claim visual text highlighting from
  character offsets, which do not map to PDF coordinates. Preserve CSP rather
  than weakening it to allow arbitrary embedded PDFs.
- Existing published Knowledge has no recoverable original in the DB. Offer an
  instructor-only **attach original** action that verifies the uploaded PDF's
  exact SHA-256 equals the active content revision's `source_sha256` and checks
  page count before encrypting it. It must not change revision/publication,
  reindex, call a provider or silently attach a different file. Missing PDFs
  remain explicitly unavailable; the current extracted-page view can be a
  temporary fallback. The seven local lecture PDFs total about 3.7 MB in a
  metadata-only check, but per-user/Subject/deployment archive quotas and
  backup/key-rotation guidance must still cover configured limits.

### 2. Replace source-sufficiency admission with navigation ranking

- Keep one current-question embedding at most, zero answer/verifier calls and
  no automatic provider retry. Use authorized exact-vector plus PostgreSQL
  full-text candidate search. If embedding is unavailable, run a bounded
  **local lexical-only fallback** so a provider outage does not recreate the
  old “answer generation failed” experience. Do not conceal total search
  failure as “no relevant Knowledge.” PostgreSQL supports positional lexical
  queries and proximity ranking; see its
  [full-text search documentation](https://www.postgresql.org/docs/16/textsearch-intro.html).
- Rank at the page/window level using query entity, requested relation,
  qualifiers, title/section/bullet context, exact lexical match, vector rank
  and section diversity. Inspect nearby pages for every promising candidate,
  not only after the first-stage selector returns no result. Resolve bounded
  follow-ups locally for both lexical and semantic intent, or request a clearer
  question when a referent is ambiguous. Do not make a second remote embedding
  request for a rewritten follow-up.
- Select at most three distinct current published PDF pages; prefer diverse
  useful sections or documents, with only exact canonical snippets (up to the
  existing 480-character cap) that actually belong to the displayed page.
  When extraction is incomplete, present the PDF page without a fictitious
  quote. Label every card as a reading suggestion, never as sufficient proof.
  A misleading wrong-owner/wrong-condition page is a navigation error to be
  measured, even though it is no longer a “verified citation.”
- Version the new job/result/ref contract and migration. Keep atomic references,
  current authorization/revision checks, expiry, source cleanup, historical
  policy fencing, typed API/UI and accessible no-match/failure states. Do not
  run the v7 rule selector or the rejected GTE score as an admission gate.

### 3. Measure each failure stage before tuning

Freeze a content-free funnel for each independently labelled question:
original-PDF page fidelity -> canonical extraction coverage -> eligible gold
page in index -> SQL candidate recall -> neighboring-page pool -> final displayed
page/snippet -> original-PDF open. Run the oracle-gold-page condition separately
from real-query retrieval, to distinguish missing extraction, candidate search,
ranking and display. Use current owner-reviewed positives as exposed regression,
plus a **new source/document-separated** independent holdout; the 107 current
published pages and the prior 96 synthetic GTE cases are already exposed.
Review actual physical PDF pages, not only stored extracted text.

Proposed non-relaxed release gates for the navigation contract: at least 10/11
useful-page hit@3 on the exposed seed and 10/12 on a fresh holdout, at least
3/4 in each direct/paraphrase/follow-up group; report top-1 and the usefulness
of every one of the 2–3 displayed cards. Reject any source outside the current
authorized published revision, incorrect PDF page/hash, fabricated quote,
answer-like assertion, extra provider request, or inaccessible/expired source
at read time. Exercise wrong-owner/condition and no-source controls, including
local lexical fallback and provider failure, before enabling Ask. Keep the
maintained RAG corpus gates and the existing full backend/PostgreSQL/frontend/
journey/accessibility/security/release checks. The navigation gate replaces
the unachievable runtime “verified sufficiency” claim **only if the operator
explicitly approves this product-contract change**; never mark existing Lane 6
checks passed from this proposal.

## Approval and execution boundary

If approved, update Lane 6 and ADR-022 first, with a new ADR for permanent
encrypted PDF retention if needed. Then implement schema/archive/reattachment,
authorized PDF.js viewer, navigation ranking and lexical fallback, and run
stagewise offline/disposable evaluation. Keep Ask disabled until the new gates
pass. No volume reset is necessary: existing PDFs can be hash-reattached.
Any paid indexing or live Ask query evaluation requires a **new** explicit
endpoint/model/price/call/token/time/cost envelope; this proposal authorizes
none. No new model download, training or answer generation is proposed.
