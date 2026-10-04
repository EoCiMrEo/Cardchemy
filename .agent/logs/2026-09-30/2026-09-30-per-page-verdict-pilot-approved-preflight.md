# Per-page verdict public pilot: approval and preflight

Date: 2026-09-30 (America/Chicago). Checkout `main` at `6c02d6c` with the
existing Lane 6 changes preserved. The populated volume, retained original
PDFs and root `.env` were not modified. Ask remains disabled at Lane 6 **3/7**.

## Exact new authorization

After the keyless v3 prototype, the operator separately approved **one**
public-only `gemini-3.5-flash-lite:generateContent` pilot: at most 66
calibration calls, and at most 60 different-PDF heldout calls only after every
calibration gate passes. Each request contains the current public question and
four page/cue snippets from the eight frozen CC BY 4.0 PDFs, and requests only
four source-ID/Boolean verdicts. No private Knowledge, history, identity,
labels or PDF bytes may be sent. Model `gemini-3.5-flash-lite`, thinking `low`,
`store=false`; no automatic retry. Limits are 126 POST total, at least 20
seconds between starts, 30 seconds per call, 60 minutes per split and 120
minutes total, at most 8,192 input/1,024 output tokens per call and
1,032,192/129,024 tokens overall. The conservative price guard is USD 0.30
input/USD 2.50 output per million tokens, with new-spend ceilings USD 0.34
calibration and USD 0.31 heldout. Prior failed attempts have uncertain actual
cost. Google's [pricing page](https://ai.google.dev/gemini-api/docs/pricing)
currently lists Free-tier token price USD 0 but allows public content to be
used for product improvement. The approval is for this public evaluation only:
no application DB write, private transfer, runtime policy switch or Ask
activation.

## Pre-request correction and checks

An independent read-only audit found the inherited augmented calibration
scorer reported one/two/three-useful exact-cardinality counts but did not gate
them. That could open the independent heldout after a high hit rate with too
few useful pages displayed. The approved Lane 6/ADR-024 gate requires these
strata. The v3 scorer now applies the existing 5/6 per-stratum ratio before
heldout; the historical v2 scorer and consumed result remain unchanged. A
synthetic seven-case under-selection control has 54/54 positive hit and 100%
displayed usefulness but now correctly fails calibration and leaves heldout
unopened.

The approved endpoint, model, two split caps, 20-second spacing and one-use
authorization ID are pinned in `scripts/run_fresh_public_per_page_verdict_v3.py`.
`scripts/prepare_fresh_public_per_page_verdict_v3_approval.py` created a
canonical, SHA-bound **calibration-only** receipt in the ignored verification
area. Its SHA is `31be7ab692e6376344920a19230b035b2c9aa8d61430b92beee0ebae0fc4e6bb`.
The separate v3 attempt ledger has not claimed a split or physical request.
The isolated launcher ran a two-stage approval preflight with the root source
judge credential without displaying its value or making an HTTP request;
status was `approval_preflight_passed`. The frozen 66-group request manifest
SHA is `fd4421940eb613523d126138e6453e4e4e731bf14af1ae03b908b783fb75e6ed`;
largest REST request is 6,340 bytes. The 60-group heldout packet and labels
remain unopened.

The completed focused tests after pinning the envelope passed **69/69**.
The first run after pinning found an obsolete test expectation that the
global live envelope must still be false; the test was corrected to exercise
the disabled-fence branch explicitly, and the full focused run passed.
`python scripts/check_context.py` passed after this log/index update with 37
required files, 79 active guides and 1,618 local links. Git whitespace check
also passed. These are documentation/format checks, not model-quality proof.

No result from this preflight establishes model quality, private-page
usefulness or a release gate. If calibration fails, the pilot stops without
opening heldout; Ask stays disabled.
