# Fresh public source overlap review and packet guard

Date: 2026-09-30 (America/Chicago). Starting checkout: `main` at `6c02d6c`.
The approved eight-PDF public acquisition succeeded; this step read only its
downloaded public PDF pages, the verified earlier Spring 2020 v4 public PDFs
and the two reserved Illinois public PDFs. It did not open old question or
usefulness labels, use a provider, read private Knowledge, mutate a database
or enable Ask. The populated volume, root `.env` and original PDFs remain
unchanged.

The source-only five-token-shingle screen covered **278 new pages** against
**579 earlier public pages**. Exact PDF hashes were distinct. The scan found
eight exactly repeated normalized pages and 24 new pages with best prior-page
Jaccard similarity at least 0.5. Per-document exclusion counts were 7, 7,
8, 0 / 0, 2, 0, 0 for new lectures 04–07 / 08, 09, 11, 13. A separate
read-only containment check found no additional substantive page pair with
at least 0.8 five-gram containment and Jaccard below 0.5. A rendered sample
of an exact pair showed the same slide diagram and explanatory bullets, so
these are material reuse, not merely different file hashes or common titles.
The screen is a conservative source-overlap filter, not proof that remaining
pages are semantically unrelated.

The new diagnostic is pinned to source manifest SHA-256
`6572395ae7234abdb790226940d0a104db153103d30f14ebb9d0a4e3118df72e`
and has SHA-256
`c719bb62f310a837f9321840262d6adf9c8b6f00167a887aa045923bd0a4f409`.
The source-only review receipt in the same guarded OS Temp directory has
SHA-256 `0d6c2fb8cd4e56a6d4e0f8c64819a2fc0ef68260738972512a44eaa0a57be0ae`.
The reviewer approved question authoring **only with all 24 listed pages
excluded**. No question has yet been authored or labeled from this corpus.
The review used extracted text for all pages and a visual sample for exact
reuse; it did not visually compare all 278 slides.

`scripts/prepare_fresh_public_source_id_v2.py` now records sorted excluded
physical page numbers in the diagnostic and rejects any authored candidate
using one. It binds the source manifest, diagnostic, separate review receipt,
two independent page-plus-cue reviews and conflict adjudication before
writing split-separated frozen packets. `scripts/score_fresh_public_source_id_v2.py`
remains a keyless, failure-inclusive, calibration-first scorer. The added
negative test proves an excluded page cannot enter a slate. The focused
acquisition/freezer/scorer/prototype suite passed **50/50** synthetic tests
after this guard; the first run exposed an old synthetic comparison-hash
mismatch, corrected in the fixture before the passing rerun.

The 254 remaining pages are only eligible source material. They are not
gold-labeled pages, a new model score, a private release pass or an Ask
activation. Independent question and page/cue authoring, two reviews,
calibration, heldout and runtime release gates remain open.

Correction (same date): the later author/reviewer separation guard added one
synthetic case. The final combined acquisition/freezer/scorer/prototype run
passed **51/51** tests; the earlier 50/50 figure above describes the preceding
overlap-only run.
