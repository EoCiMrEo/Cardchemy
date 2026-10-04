# High-thinking pilot: transport-only repair and proposed new envelope

Date: 2026-10-01 (America/Chicago), continuing work begun on 2026-09-30. **Offline diagnostic and disabled repair
prototype; not a new live authorization or accepted plan amendment.** Branch
`main`, starting HEAD `6c02d6c`, with extensive pre-existing work preserved.
This follows the [three-request terminal stop](../2026-09-30/2026-09-30-full-cue-high-thinking-public-stop.md).

## Diagnosis and limits of the evidence

The consumed pilot stopped while reading its third HTTP response, before
parsing the response JSON. Its 8,192-byte whole-response guard is distinct
from the strict 2,048-byte visible verdict JSON limit and the 2,048 combined
output/thinking token limit. Two valid journals are not a full quality
measurement. No heldout claim exists. Known conservative cost is USD
0.004043; actual third-request cost and earlier failed-request costs remain
unknown.

Google's [official thought-signature documentation](https://ai.google.dev/gemini-api/docs/generate-content/thought-signatures)
describes encrypted metadata attached to response content parts, including
the last part of Gemini 3 non-function responses. Such metadata can make the
HTTP envelope larger without making the final verdict JSON larger. The
discarded G003 response was not parsed or retained, so its actual field
sizes and contents are unknown. This is a protocol-compatible explanation,
not a proven diagnosis of the provider's particular response. There is no
documented guarantee that every response fits 64 KiB.

A synthetic response with the same four valid ID/label verdicts, valid
usage, and inert optional signature metadata is rejected by the old reader
above 8 KiB. A bounded 64 KiB reader accepts that response while retaining
the original verdict and token checks. No synthetic outcome counts as a
model-quality result.

## Concrete offline repair

- [v2 runner](../../../scripts/run_fresh_public_full_cue_high_thinking_v2.py),
  [launcher](../../../scripts/launch_fresh_public_full_cue_high_thinking_v2.py)
  and [approval preparer](../../../scripts/prepare_fresh_public_full_cue_high_thinking_v2_approval.py)
  preserve the consumed v1 source files and old receipt hashes.
- The only transport behavior change is whole-HTTP-body allowance from
  8,192 to **65,536 bytes**, checked during streaming and again before
  parsing. The reader stops at the bound; no unrestricted body loading,
  network retry or response retention is added.
- Reuse the exact v1 prompt, request builder, cue/page inputs, candidate
  order, strict parser and scorer. The same single text part must contain
  valid four-label JSON of at most 2,048 bytes. Extra parts, foreign IDs,
  answer fields, unfinished output and over-token usage still reject.
  Opaque metadata is discarded; only validated selected IDs and aggregate
  usage/latency enter the paired journals.
- v2 has distinct authorization, claim, ledger and launcher identities.
  Its live flag is **false**, authorization is `UNAPPROVED_*`, and both
  cost caps are zero. The consumed v1 receipt cannot authorize v2. A new
  approval would be applied before freezing the exact source hashes and
  issuing new receipts; no frozen executable is edited during a run.
- The semantic candidate and scorer version stay v1 because neither
  selection nor scoring changes. Transport execution version v2 is bound
  in the source hashes, authorization and physical attempt claims.

## Offline verification

[Transport regression tests](../../../backend/tests/test_high_thinking_http_envelope.py)
passed **21/21**. They cover exact 8 KiB and 64 KiB boundaries, one byte over,
inert 16 KiB metadata, strict visible output, extra parts, token overruns,
the real stream-reading loop through `httpx.MockTransport`, no retry,
unchanged request bytes, disabled execution, durable selected-ID-only
journals, no false no-match on failures, early quality stop, and a full
synthetic calibration-to-heldout admission with different latency. These
tests use no real credentials, provider, private source or database.

An independent read-only review compared the v1/v2 executables and reran
the 21 transport tests successfully. It found no concrete blocker in the
disabled candidate; this is not proof about the discarded real response.
Documentation validation passed 37 required files, 79 active guides and
1,674 local links; the tracked diff whitespace check passed.
The original calibration approval receipt SHA still matches, and all
11 executable/dependency hashes bound by that receipt are unchanged.
Only match booleans and the count were printed during the local check.

The actual keyless calibration preflight passes for all **66** frozen
requests: maximum 5,942 model-visible bytes plus the unchanged 512-token
protocol reserve, maximum REST body 6,346 bytes. The request-body manifest
is still `0ff18408612e54fbe58d60de1b921017352fc0c00525b37ed986098bbd4cf07c`,
identical to consumed v1. Public PDF files are read for integrity; real
heldout questions, labels and model outcomes remain sealed. No key is
read and no claim or provider request is consumed by this preflight.

The broader backend suite completed earlier in this turn at **2,823
passed, 151 skipped and 2 live deselected**. It predates the 21 additional
transport tests; do not call it a full-suite run including those tests.
The retained root configuration, populated database, PDFs and backups were
not changed. Ask remains disabled and Lane 6 remains **3/7**.

## Proposed single new public run, requiring owner approval

Recommend a fresh 66-case calibration, followed by the sealed 60-case
different-PDF heldout only if every frozen gate passes. Keep the previous
two successes as diagnostics rather than merging transport versions or
silently treating the oversize rejection as a scorable no-match. The new
run repeats those cases under its own approval; old claims stay consumed.
Compared with carrying two successes and one failure forward, this spends
at most three additional calls (USD 0.022733 under the conservative token
guard) and avoids changing the failure/scoring bridge.

The proposed envelope is:

- Endpoint `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`;
  model `gemini-3.5-flash-lite`, thinking `high`, `store=false`.
- Only the frozen current public question and four exact page/cue windows
  from two of the eight existing CC BY 4.0 PDFs; receive four issued
  IDs/labels and locally derive 0-3 selected IDs. No new downloads, private
  Knowledge, chat history, identity, gold labels or PDF bytes.
- At most 66 calibration POSTs and conditional 60 heldout POSTs: **126
  total**, no retries, at least 20 seconds between starts, at most 30
  seconds per attempt, 60 minutes per split, 120 minutes total.
- At most 8,192 input and 2,048 combined output/thinking tokens per call;
  1,032,192 input and 258,048 output/thinking total. Whole HTTP response
  bound 65,536 bytes; visible verdict JSON still 2,048 bytes.
- Current [official standard pricing](https://ai.google.dev/gemini-api/docs/pricing)
  was checked this turn: Free tier USD 0, with public content potentially
  used for product improvement; Paid guard USD 0.30 input and USD 2.50
  output/thinking per million. New ceiling **USD 1.00**, split USD 0.52
  calibration and USD 0.48 heldout. Prior unknown charges are additional.
- Keep all frozen usefulness, cardinality, no-match, availability and
  provenance gates; at most two transient failed cases per split, counted
  as misses rather than no-match. Stop on a permanent/invalid/oversize
  response, a third transient failure, a limit overrun, or a quality gate
  becoming mathematically unreachable. Never silently increase 64 KiB.
- If approved, update Lane 6/ADR-024 to record this transport correction
  and exact new run, freeze all files and receipts, perform the permitted
  host's keyless/key/write preflights, then launch once. No source content
  or output is logged. Public success does not authorize private transfer,
  change the app's immutable model policy, or enable Ask.

The next required decision is this combined plan-note and exact new-run
approval. Nothing here lowers the 90% displayed-card usefulness target,
opens heldout prematurely, or promises that the model will pass.
