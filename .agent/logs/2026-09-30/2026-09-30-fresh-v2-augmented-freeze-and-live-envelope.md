# Fresh v2 augmented public freeze and proposed live envelope

Date: 2026-09-30 (America/Chicago). Checkout: `main` at `6c02d6c`, existing
working tree preserved. This is public-only, keyless evidence. Ask remains
disabled and Lane 6 remains **3/7**.

## Decisions and inputs

The operator approved retaining all 96 original public questions, adding
up to 30 independently reviewed public questions, and then approved a
specific max-three-display rule for two independently judged four-useful
calibration questions. The unchanged original 96 were labeled twice with
third-party resolution of 24 disagreements. The 30 reserve questions had
two separate 120-candidate reviews and five third-party resolutions. The
reserve author, reviewers and adjudicator were separate. The blind packet
omitted forms, author mapping and target counts. No label or question was
removed or changed after review.

Combined reviewed distribution, including all cases:

| Split | One useful | Two useful | Three useful | Four useful | No useful | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Calibration | 19 | 17 | 16 | 2 | 12 | 66 |
| Different-PDF heldout | 12 | 16 | 20 | 0 | 12 | 60 |

The first augmented freeze rejected the two four-useful groups under its
earlier max-three-gold rule. The separately approved overflow rule keeps both
groups and requires exactly three useful issued IDs from each; all other
one/two/three exact useful-ID-set gates and every no-useful group remain.
The third review file used ordinary noncanonical JSON formatting; the
freezer accepts human review JSON only after duplicate-key rejection and
binds its **raw SHA-256**, while machine-authored source/mapping inputs must
be canonical. No decision value was normalized or altered.

## Implementation and local proof

- `scripts/review_fresh_public_source_id_v2.py` now supports a separately
  marked `reserve_v1` blind profile with exact 30-group/120-candidate roster.
- `scripts/prepare_fresh_public_source_id_v2.py` retains its original 96-group
  behavior and has an explicit 96+30 path. It preserves original G001–G048
  IDs, assigns reserve G049 onward, rechecks source offsets/split/overlap,
  distinct reviewers/adjudicators and all labels, and requires exactly two
  calibration overflow cases plus the approved minimum twelve per 1/2/3
  stratum in each split.
- `scripts/prepare_fresh_public_source_id_v2_augmented.py` rebinds blinded
  reserve rows to authored offsets and the eight hash-verified original public
  PDFs, then writes a new versioned packet/label/freeze contract. It refuses
  changed, duplicated, extra, or omitted cases.
- `scripts/score_fresh_public_source_id_v2_augmented.py` counts every group,
  every displayed card and all actual zero-useful groups; applies the
  proportional gates, `N-2` valid-response availability, and 2/2 overflow
  rule. Heldout model outcomes remain closed until full calibration passes.
- `scripts/run_fresh_public_source_id_v2_augmented.py` is keyless by default;
  its authorization/model constants are intentionally pending. A later
  approval must bind exact freeze, request manifest, source hashes, costs,
  and one physical claim per group, with zero automatic retries.

The actual augmented freeze passed without a provider key or network call:
`C:\Users\eocim\AppData\Local\Temp\cardchemy-fresh-public-source-id-v2-augmented-934ur3zj`.
Its `freeze.json` SHA-256 is
`c8b97e3851f081c40108d6f6a40b9bb675dc3b824329d4fc7f047480425017b1`.
The calibration packet SHA-256 is
`cd7c6aefdda0b6f33e75a5e499c7eef42b9cc1797c414e17c742d5bde5ac8965`;
different-PDF heldout packet SHA-256 is
`a56a5f44ac3d782310d0be9adbcb9bf9b4a19b4ef2d807cb18620548c51db3e1`.
The caller's **default keyless calibration preflight** revalidated all eight
public PDF hashes, the excluded overlap pages, 66 exact question/four-page
request wires and all source offsets. It returned `preapproval_preflight_passed`
with max REST body **6,103 bytes** and no key, provider request or model score.
Heldout request execution still requires a passing real calibration receipt.

Focused original-plus-augmented freezer/reviewer/scorer/caller tests passed
**88/88**. The private snapshot/bridge/display contracts separately passed
**59/59** keyless tests. Python compilation and `git diff --check` passed;
`python scripts/check_context.py` passed 37 required files, 79 active guides
and 1,597 local links at this point. These are offline and synthetic checks,
not model, private PDF, browser accessibility, or release proof. One earlier
mistyped private test filename yielded no tests and was corrected before
the 59-test run.

## Proposed separate public-only provider envelope

**Not yet authorized:** one staged calibration/heldout pilot using
`https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`,
model `gemini-3.5-flash-lite`, thinking low and `store=false`. Send only each
current public question and four extracted public PDF page/cue windows from
two of the eight hash-verified CC BY 4.0 PDFs. Receive only 0–3 issued source
IDs. Send no PDF bytes, private Knowledge, history, identity, gold labels or
author mapping. Max **66 calibration POSTs**; only if full calibration passes,
max **60 different-PDF heldout POSTs**, total **126**. No retry; starts at
least 20 seconds apart. At most 30 seconds per call, 60 minutes per split
and 120 minutes overall. At most 8,192 input and 1,024 output tokens per call,
1,032,192 input and 129,024 output tokens over all 126. The prior failed
provider attempts have uncertain actual cost and are separate.

Google's [official Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing)
lists Free-tier standard use without a charge and Paid-equivalent
`gemini-3.5-flash-lite` standard text input/output at USD **0.30/2.50 per
million tokens** (output includes thinking). The conservative per-call guard
is 5,018 micro-USD; all 126 total 632,268 micro-USD. Proposed approval caps:
USD **0.34** calibration plus **0.31** conditional heldout, **0.65** new total.
The public Free-tier text may be used by Google to improve products under
its posted terms. This proposal has not read a key or sent any request.

If approved later, pin the exact runner/prototype/parser/scorer/freezer code
and the above freeze/request hashes in a one-use receipt before key access.
If a split fails availability/quality, do not open the next split or retry
claimed groups. A public pass alone does not transfer private Knowledge,
change the retained `gemini-3.8-flash` runtime or enable Ask. Private PDF
usefulness, access, release and spoken accessibility gates remain open.
