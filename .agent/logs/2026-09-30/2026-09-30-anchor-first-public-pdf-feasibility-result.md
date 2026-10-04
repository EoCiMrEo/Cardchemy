# Anchor-first public PDF feasibility: no-go before provider pilot

Date: 2026-09-30 (America/Chicago). Scope: the owner-approved, keyless,
public-only Lane 6/ADR-024 reading-anchor feasibility audit. This is a
representation and original-PDF review, **not** a model-quality or release
result. Ask stayed disabled. No Gemini request, private Knowledge, sealed
60-case heldout, reindex, database write or runtime policy change occurred.

## Starting context and authorization

The one-use categorical public calibration had 58 valid responses before its
process disappeared. Those exposed responses already missed the frozen
multi-page and overflow gates. Read-only diagnosis found 23 independently
reviewed useful pages omitted and 40 weak same-topic pages labeled
`TOPIC_ONLY`; promoting that label wholesale would compromise displayed-card
precision. The owner approved [one offline reading-anchor audit and the
prospective plan/ADR amendment](2026-09-30-anchor-first-source-selection-recommendation.md).
The consumed categorical ledger remains untouched.

## What was built and checked

- `scripts/prototype_anchor_first_page_judge_v1.py` deterministically issues
  one to three exact, contiguous reading slices of at most 180 characters and
  a separately identified exact whole-cue fallback for each of four public
  pages. IDs bind to page, immutable page-text hash and absolute offsets.
  The prototype has no provider, credential, database or application path.
- The local parser rejects foreign, duplicated, malformed and multiple IDs
  for one page; a transport failure is distinct from a valid empty selection.
  It never generates an answer or pads to three pages.
- The frozen 66 exposed calibration groups reference four public PDFs. All
  four PDF hashes matched the roster. Across 264 candidate pages, the
  prototype issued 573 short slices plus 264 whole-cue fallbacks. All 66
  proposed wires fit the 8,192-byte cap (maximum 7,910; p95 7,349);
  maximum REST body was 8,540/12,288 bytes and conservative input-byte
  proxy 6,134/8,192. The narrow 282-byte worst-case wire headroom means a
  later runtime cannot add context without a fresh budget design.
- The 63-case review packet was frozen at SHA-256
  `ecdfa681662a9232d6beeac71f58ac77df360b3f642bbe17fe79bd45e0a235f4`.
  It contained the 23 missed useful and 40 weak same-topic public pages in
  blinded order. One independent reviewer verified the four PDFs, visually
  inspected all 44 distinct original pages, and froze per-case judgments
  **before** opening the separate old-label mapping. Review SHA-256:
  `f466b1a336c650ccb0c8d9d536ffefe35c82b800d884fe67563ac0710f5ed9da`.
  Files remain ignored under `.agent/.verification/anchor-first-public-v1/`;
  no question or page text is copied into this log.

## Aggregate result

| Prior reviewed category | Count | Original PDF page independently helpful | One short anchor helpful alone | Full cue helpful |
| --- | ---: | ---: | ---: | ---: |
| Useful page previously missed | 23 | 21 | **14** | 19 |
| Weak same-topic page | 40 | 8 | 7 | 8 |

Among the 40 prior weak pages, 32 concise slices looked deceptively topical
while the original page remained unhelpful under the independent rubric. The
reviewer disagreed with frozen usefulness labels for two prior positives and
eight prior negatives; the frozen gold was **not** relabeled. Two positive
pages expressed the needed relation in geometry/figures omitted from the
extracted cue. Five full cues were useful although no individual short slice
carried the relation, often because the explanation crossed slice boundaries.
Concise coverage of the 23 old misses was 2/5 direct, 3/4 follow-up and
9/14 paraphrase; by useful-page count, 1/3 two-page, 8/14 three-page and
5/6 four-page candidates. A lexical proxy was also weak: all shared
question terms fit one short slice for only 11/23 misses versus 23/40 weak
pages. Exact source offsets establish provenance, not usefulness.

A separate read-only sensitivity check revalidated the same 58 public
response/usage receipts and frozen labels without opening heldout. Loosening
the old **exact-all-useful-IDs** gate to merely require at least two useful
pages whenever two or more are available would still cover only **13/16**
two-useful groups, **5/10** three-useful groups and **1/2** four-useful
groups. The no-useful 12/12 groups stayed empty. Thus the repeated
multi-page gap is not explained solely by an overly strict exact-set
scoring rule. This is a diagnostic counterfactual, not an approved gate
change or a completed 66-case score.

**Decision: no-go for a paid/provider pilot on this representation.** The
approved pre-pilot condition required concise anchors to represent the missed
useful relations and distinguish weak same-topic pages. Fourteen of 23
coverage and 32 deceptively plausible weak pages do not support that. The
whole-cue fallback is the prior cue by construction and cannot count as an
improvement. No provider or heldout request was made, and no Lane 6 checkbox
closes from this audit.

## Verification and limits

`venv\\Scripts\\python.exe -m pytest
tests\\test_anchor_first_page_judge_public_prototype.py -q` from `backend`
passed **25/25**. `python scripts/check_context.py` passed **37 required
files, 79 guides and 1,644 links** before this log addition;
`git -c core.safecrlf=false diff --check` passed. An initial test invocation
from the repository root failed module discovery (`app` unavailable); rerun
from the documented backend working directory passed. One independent PDF
reviewer is diagnostic evidence, not an independently adjudicated
replacement for the existing frozen gold. This audit cannot predict how a
new model would behave, and it does not validate the current dormant v4
application policy. The retained database, encrypted originals, populated
volume and root `.env` were preserved.

The next architecture or provider attempt requires a new evidence-backed
proposal and owner approval. A live request additionally needs its own exact
endpoint/model/price/call/token/time/cost envelope. Lane 6 remains **3/7**;
Ask remains disabled.
