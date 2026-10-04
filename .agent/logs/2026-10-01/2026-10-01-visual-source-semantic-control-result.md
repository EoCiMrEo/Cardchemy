# Completed offline visual-source semantic/control reconciliation

Date: 2026-10-01 (America/Chicago). Executes only the
[approved narrow scope](2026-10-01-visual-source-semantic-control-approved.md).
Starting branch/HEAD: dirty `main`, `6c02d6c`. Root guidance and affected
helpers/contracts were checked; unrelated working-tree changes preserved.
No provider, model inference, download, rerender, private Knowledge, root
environment/key, database, heldout or runtime was accessed or changed.

## Changes and independent review

- Added `prototype_visual_page_source_judge_v2.py`, an inert clarity-aligned
  wire: discovery questions need not contain their answer; missing source
  evidence is separate from task ambiguity. Closed IDs/cues/clarification,
  0–3 cards, no weak padding and source-only parsing remain. V1 freezes stand.
- Added `prepare_visual_semantic_control_v2.py`: only three approved pairs
  and four existing draft-control pages, shuffled neutral IDs, one cases
  array and neutral image names. Six existing PNGs were copied byte-identically
  for image-tool access; no rendering/cropping. Old U/N control-role exposure
  is historical development evidence, not repeated in this packet.
- Added `summarize_visual_semantic_control_v2.py`: complete sealed reviews,
  readable/clear/control guards, parent SHA binding, conservative overlay
  and inert request assembly. The old feasibility predicate omitted cue/
  clarity conditions; this new bound is separate and does not regrade it.
- Fixed the old review projection's post-validation freeze read to check the
  external SHA again. A coordinated synthetic freeze/manifest replacement
  is rejected before projection. Completed old artifacts remain unchanged.

One fresh vote-free adjudicator inspected all three exact full-page inputs:

| Pair | Input / cue | Clarity | Reason |
| --- | --- | --- | --- |
| P009 | Yes / Yes | Yes | Direct on-page relation |
| P119 | Yes / Yes | Yes | Direct on-page relation |
| P146 | No / No | Yes | Requires unstated outside inference |

Both fresh control contexts separately inspected all four pages at actual
resolution. They agreed on readable/clear Yes and input/cue No throughout.
The existing draft therefore admits exactly **one** additional no-match
group; no replacement question was needed. This concerns the supplied slate,
not source absence across the corpus.

All 66 original groups/264 pairs and historical labels remain. P146 stays
an unrepresented historical positive obligation and a miss. Fresh positives
P009/P119 conflict with old weak judgments and receive **Unsure**, not useful
credit; the original three uncertain pairs remain too. Qualification is
**108 Yes / 151 No / 5 Unsure**. Unknowns never earn no-match/useful-card credit.

## Conservative input bound and keyless assembly

These are available-input ceilings, **not model accuracy, a predicted pass,
release evidence or provider authorization**. Complete input repair is not
required.

| Historical useful-page stratum | Exact-set ceiling | Existing minimum |
| --- | --- | --- |
| One | 16/17 | 15/17 |
| Two | 19/21 | 18/21 |
| Three | 14/14 | 12/14 |
| Four, capped at three | 2/2 | 2/2 |

A useful candidate is available for all 54 positive questions, 18/18 each
direct/paraphrase/follow-up. Three exact-set misses remain: Q003/Q030/Q037.
The control brings conclusive no-match groups to 12. The original unresolved
group earns no binary no-match/exact-set credit. All **67 requests** remain
in availability, allowing at most two errors (minimum 65 valid), with all
≥90% displayed-card/hit/per-form/cardinality/no-match gates unchanged.

The conservative representation bound can support those gates. A separate
enforced Windows job (4 CPU / 2 GiB process-tree memory / 600 seconds)
assembled **67 inert v2 requests**, maximum full wire **3,395,977 bytes**
under 6 MiB. Each revalidates original text/cue/page/image bindings and PNG
bytes. No HTTP/token-count/model call occurred. Bytes are not exact tokens.

## Artifact bindings

Public review root:
`C:\Users\eocim\AppData\Local\Temp\cardchemy-visual-semantic-v2-zn3h5eqb`.

| Artifact | SHA-256 |
| --- | --- |
| Review freeze | `caee7777a313813a3b46917d6245cc693422eb4f418e9cf6d1cef49e697c7097` |
| Semantic packet | `1789834de2c5a734efcfffabf68e21a0973ecaf8cec07c2377f7bee0dc9710b9` |
| Four-page packet | `3e7450e8a517e3e76b28becd261867cce7ac25bbfee7c8996031eaec03172879` |
| Semantic review | `a303aead84e35b5839a44d2f8f8dcf661b9ffc8aa26b9c03d1544e81e042aeb2` |
| Control A | `5592c944cb374783f03b2ed304da2802f1eb5e28302ba804afdbe8199519f795` |
| Control B | `95892ecabd9b063a161dfcf8a820f01db8a98b5b8d5aabb21685f65a4c46e703` |

Bound/wire root:
`C:\Users\eocim\AppData\Local\Temp\cardchemy-visual-semantic-summary-v2-5v5jc3li`.
Summary SHA: `09b1f1abd79c6a79a3d5a50f4d5ae4d3c08dc377f9c757caeb7b552ca5c0d3b3`.
It binds all 67 request SHAs, overlay/bounds and the prototype SHA
`f6541e0fc854bdb5f4279a385d6f2c116916a03ccf2d4b5f20ad328c61e44415`.
Parent visual freeze remains
`1079eab34382f62467757209040e40113ee4bae76082ea98c4e644bd378e5bac`;
original tri-state mapping remains
`1a25153b1ac6163671b1f18e69c836e3007faf44a2ba24875990e83e0938847d`.

## Checks, preservation and limits

Final cross-check against the maintained public calibration scorer found
its per-form minimum is `ceil(5*positive_form/6)` (15/18), stronger than the
private release floor of 3/4. The new bound now uses that same public rule,
with a regression rejecting 14/18. No input, review, label or historical
result was changed. A separate enforced 4 CPU/2 GiB/600-second verification
rechecked the existing overlay and every one of the 67 request hashes:
`cardchemy-visual-bound-verification-v2-hkkqbnpb` in Windows Temp,
receipt SHA `6dc1b51d66101072c8695777d7b448518508dd902c76e23257c947c69fe1a813`.
It confirms 18 available hits against 15 required per form and unchanged
threshold feasibility, without rebuilding inputs or invoking a provider.

- **251** relevant synthetic tests passed from `backend`: original annotation,
  PNG/resource/source/wire/parser and new projection, external-freeze race,
  tri-state/complete-review/conservative-bound contracts.
- Independent code review cleared the binding/blinding/resource/parser and
  bound logic; its independent **18** summary tests passed. It opened no
  actual corpus, votes or model outputs.
- Final context/whitespace results follow the documentation update. No
  frontend/service/journey/hosted-CI/live-release result is claimed here.
- Preserved all freezes/results and six byte-identical public scratch PNGs
  still needed to validate the new review, under ignored `tmp/pdfs`. No
  model process remains. Real `.env`, populated volumes, ignored backups and
  private original PDFs remain untouched; health was not rechecked.

The 60 different-PDF heldout questions/labels stay sealed; compatible
independent visual review requires separate approval. Public quality needs
a fresh exact endpoint/model/image/token/call/time/cost envelope. Ask stays
disabled and Lane 6 **3/7**; no checklist closes from this offline result.
