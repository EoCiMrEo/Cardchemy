# Approved categorical public pilot: frozen preflight before any call

Date: 2026-09-30 (America/Chicago). This record precedes the live run; it
does **not** claim a quality result or Ask activation.

## Approval and scope

The operator approved exactly one public Gemini 3.5 Flash-Lite categorical
page-judge pilot after the [keyless prototype](2026-09-30-categorical-offline-prototype-and-regression.md).
The endpoint is
`https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`,
model `gemini-3.5-flash-lite`, low thinking, `store=false`. Each call contains
only one public current question and four page/cue excerpts from two of the
eight frozen CC BY 4.0 public PDFs. The response may contain only four issued
IDs with one of four categorical labels per ID. No private Knowledge, chat
history, identity, PDF bytes, review labels, DB write or Ask activation is in
scope. The Free tier lists zero charge but may use public content to improve
Google products; the conservative Paid guard uses
[$0.30 input/$2.50 output per million tokens](https://ai.google.dev/gemini-api/docs/pricing).
Prior failed-call charges are unknown.

The one-use envelope permits at most 66 calibration POSTs and 60 different-PDF
heldout POSTs only after a full calibration pass; 126 total. It permits zero
automatic retries, starts at least 20 seconds apart, at most 30 seconds per
call, 60 minutes per split and 120 minutes overall. Limits are 8,192 input
and 1,024 output tokens per call, 1,032,192/129,024 across the pilot, with
separate new-cost caps $0.34 calibration and $0.31 heldout ($0.65 total).
The existing 90%-all-displayed usefulness, zero false no-match, exact
cardinality, positive-hit and availability gates are unchanged. Any failed
calibration or excessive provider errors stops without opening heldout.

## Frozen implementation and preflight

The new caller, isolated launcher, approval preparer, categorical prototype,
scorer and tests are separate from consumed Boolean and stronger-model
ledgers. The exact calibration receipt in ignored verification storage has
SHA-256 `58d54e18bcad23dfb4d4988aa2ad299424b37172f78c9f4a6aa72b22bc6210eb`.
The 66-group body manifest SHA-256 is
`04d56555aa1bda5f46b11a235389725f211ce1a1f37d6832963d5e247781de5f`.
The preflight validated 66 distinct public groups, a maximum actual outgoing
REST body of 6,345 bytes, and model-visible system+question/pages+schema of
5,942 bytes plus a 512-byte reserve, under the 8,192 input guard. Separate
REST size cap is 12,288 bytes. The directly invoked caller stopped at the
expected missing-key guard after content/cost/code validation; the isolated
launcher then passed the same preflight with the local key without exposing
its value or sending a request. There is no attempt claim yet.

Focused new prototype, scorer and caller tests: **59 passed**. The caller's
10 tests include an all-66 synthetic score, malformed/foreign IDs, three
HTTP 503 availability stop, source/receipt binding and a distinct nonzero
quality-failure CLI exit. An independent static safety review found no
actionable envelope or privacy defect. A temporary byte-count concern was
resolved: an audit had used an ASCII-escaping wire serializer instead of the
actual UTF-8 REST serializer; the outgoing 6,345-byte measurement is the
authoritative POST body bound. The sealed heldout question/labels were not
opened and no provider call was made during this preparation.

## Remaining proof

The one-use live calibration may still fail due to availability or quality;
only its complete frozen score can open the heldout. A public pass would
still require a matching versioned application policy, a separate approved
private transfer, independently reviewed original-PDF display and full
authorization/accessibility/release checks. Ask remains disabled and Lane 6
remains 3/7 at this preflight point.
