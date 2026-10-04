# Corrected public PDF holdout: independent source review — 2026-09-28

## Scope and starting context

Lane 6 needs an independently labeled, document-separated source-navigation
holdout. The first public two-PDF packet was retired after its proposed windows
failed exact app-extraction substring checks (0/12). This review used the
corrected frozen packet in private OS Temp, SHA-256
`d841ae6489995f884266abf212f7c63f14952a348419bfc7aa42e923c00d6b12`.
The original PDFs were [Illinois lecture 17](https://courses.grainger.illinois.edu/ece448/sp2020/slides/lec17.pdf)
and [Illinois lecture 37](https://courses.grainger.illinois.edu/ece448/sp2020/slides/lec37.pdf).
I inspected the packet's proposed sources only, without seeing selector output,
candidate rankings, displayed Ask cards, model scores or database content.
The existing worktree, retained volume, root configuration and Ask-off policy
were preserved.

## Method and results

- Recomputed both PDF digests and physical page counts against the frozen
  packet. All twelve proposed page numbers were in range and distinct.
- Re-rendered all twelve selected physical pages from the original PDFs with
  Poppler at 1,500-pixel scale and visually checked source identity, owning
  relation, requested conditions and whether the specific question can be
  studied from the displayed excerpt and page. All four follow-up questions
  resolved to the topic in their preceding question; no fact was borrowed
  from another slide.
- Re-extracted the original PDFs with `pypdf 6.19.0`, as the application PDF
  processor does. All twelve corrected windows appeared **exactly once** in
  the appropriate extracted physical page; each window was at most 480
  characters. Some bullet/formula glyphs in extracted text remain imperfect,
  but the relation reviewed on each page and in its window remains legible.
- Independent labels: proposed source/excerpt/page **12/12 Yes**, split
  direct **4/4**, paraphrase **4/4**, follow-up **4/4**. **No: 0; Unsure: 0.**

Per-case labels, source/page/window/render digests and no source text are in
private Temp at
`C:/Users/eocim/AppData/Local/Temp/cardchemy-lane6-new-public-holdout-20260928/holdout-v2-independent-labels.json`,
SHA-256 `13bf7aa9518b5d125948aa4a98045ffd4f3bcdba9761d010c8750fcb8b259877`.
Provider requests: **0**. Database reads/writes: **0**.

## Limits and next gate

These are independent labels for proposed gold sources, not retrieval results.
The two public PDFs are not published Knowledge in the retained Subject. This
review does not establish actual hybrid SQL recall, usefulness of every
displayed card, authenticated original-PDF opening, access controls or release
readiness. Keep Ask disabled and the Lane 6 quality/release checkboxes open
until those separate measurements pass.
