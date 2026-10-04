# Independent public original-PDF holdout freeze — 2026-09-28

## Scope and starting context

Lane 6 needs a new document-separated source-navigation holdout. The existing private lecture questions and earlier unpublished-PDF proxy have been exposed to development. This task used only two newly downloaded public lecture PDFs in a private local Temp directory. It did not inspect selector outputs, run retrieval, publish Knowledge, alter the database, call an AI provider, or change the release gate. The retained Ask switch remains off.

The selector implementation and diagnostic hashes were captured in the prelabel receipt before authoring. Its SHA-256 is `cf28e6c4939c16b962cdcec91b6e2d5f0e6e917025f91b2f9e9fd1a5b0bf8156`; that receipt records `question_labels_frozen=false` and `selector_results_seen=false` at the start. The current branch was `main`, HEAD `6c02d6c`, with pre-existing work preserved.

## Source and independent labels

| Public source | Physical pages | PDF SHA-256 |
| --- | ---: | --- |
| [Illinois lecture 17](https://courses.grainger.illinois.edu/ece448/sp2020/slides/lec17.pdf) | 29 | `f8d3ef7b5284c827286183d9b14e00fef51acaf49742f2d9ee3b85631abf3e49` |
| [Illinois lecture 37](https://courses.grainger.illinois.edu/ece448/sp2020/slides/lec37.pdf) | 31 | `5b8c326ccff98c51b114ae45acd95f985c75464858a2da68e3cd06b2c4e66fe6` |

Both physical first pages were visually rendered and inspected. Each names Mark Hasegawa-Johnson and states CC-BY 4.0. The selected gold windows use only the lecture's text, not third-party figures or their credits. All twelve gold pages were also visually rendered and inspected; three additional plausible alternative pages were reviewed. The PDF text extractor emits some nonstandard bullet/formula glyphs, so each gold window is recorded as an **exact extracted-text substring** and the physical page remains the independent usefulness authority.

The private, untracked Temp packet contains exactly twelve cases: four direct, four paraphrase and four follow-up. Each source contributes two cases per group; all twelve primary gold physical pages are distinct. Each follow-up has a prior question and an elliptical current question. For each case, the packet records source digest, one primary page, a short exact source-text window, and visually reviewed useful-page labels. The longest window is 312 characters. Unlisted returned pages require independent original-PDF review before being counted unhelpful.

Packet: `C:\Users\eocim\AppData\Local\Temp\cardchemy-lane6-new-public-holdout-20260928\holdout.json`, SHA-256 `e7ff8ea711ab22f6d4c68e3fc681da23c17b3f53da2b1441cdd91d6c5a2bbe4c`. Its separate freeze receipt SHA-256 is `9c4b7fea7f553e309a26c44d7f63d11a53106c24bd8680830ba5d3260298a502`. The packet and its question/source text remain outside the repository.

## Checks and limits

- Recomputed both PDF digests and physical page counts; checked the selected source windows occur literally in extracted text.
- Asserted twelve cases, a 4/4/4 group split, two cases per source per group, twelve distinct primary pages, and complete prior-question fields for follow-ups.
- Verified source/license and selected pages visually before label freeze; no selector result was viewed. Provider requests: **0**. Database writes: **0**.
- This is a **public unpublished-PDF offline holdout**. Its result cannot substitute for current published-Subject SQL retrieval, authenticated original-PDF opening, owner/enrollment controls, or the release gate. Those require separate measurement, and the Ask switch stays off while they are open.
