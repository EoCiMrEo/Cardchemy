# Independent original-PDF review of the frozen public holdout

## Scope and starting state

This is a source-label review for Lane 6, before inspecting any selector or
model result. Ask admission remains disabled. The frozen 12-case packet has
SHA-256 `e7ff8ea711ab22f6d4c68e3fc681da23c17b3f53da2b1441cdd91d6c5a2bbe4c`.
The reviewer used the packet's proposed gold pages and excerpts, but did not
inspect candidate ranks, displayed Ask cards, model scores, database content,
or provider results. No provider request, indexing, database write, or change
to the frozen packet occurred.

## Checks and results

- Both downloaded public source PDFs matched the hashes declared in the
  packet; their page counts and every physical page index were valid.
- All 12 proposed gold pages were freshly rendered from the original PDFs and
  visually reviewed. The proposed excerpt was visible on the correct page,
  and the page and excerpt were useful for the precise question in 12/12
  cases: direct 4/4, paraphrase 4/4, follow-up 4/4. All four follow-up
  referents were resolved by the paired prior question. There were no `No`
  or `Unsure` labels and no faulty gold case requiring a replacement packet.
- Every excerpt had character continuity in the same extracted page after
  removing PDF extraction whitespace. Raw `pypdf` substring matching was
  0/12 because extraction serializes spacing and bullet boundaries differently;
  that raw mismatch is not a visual source mismatch. Runtime quote-offset
  correctness remains a separate gate.
- Per-case labels, with no question or source text, were saved privately at
  `C:/Users/eocim/AppData/Local/Temp/cardchemy-lane6-new-public-holdout-20260928/independent-page-review.json`.
  Label SHA-256:
  `f11c0a4fd107909d2ee3456ff000f306c9124b0b7c01da8e158673da449a5c3e`.

This validates only the frozen proposed gold sources. It does not measure
retrieval, final displayed-card usefulness, authorized PDF HTTP opening,
or release readiness. The new PDFs are public and have not become published
Knowledge in the retained local Subject.
