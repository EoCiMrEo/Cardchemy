# Lane 6 sparse PDF exact-choice control

## Scope and starting evidence

On 2026-09-28, added a keyless sparse-source control to the existing
extraction-to-choice test. The checkout was `main` at `6c02d6c` with a
substantial shared working tree. The plan still has four open Lane 6 quality
and release items. Earlier evidence already showed the retained enrolled
browser rendering the original Week 2, Week 3 and Week 4 PDFs after the
PDF.js worker MIME fix, so no duplicate browser or database restore was run.

## Change and verification

- Parameterized
  [`test_generation_card_choice.py`](../../../backend/tests/test_generation_card_choice.py)
  to retain its existing two-fact, target-three case and add the existing
  `impossible_sparse` fixture as an authored one-page, one-fact PDF with a
  target of **20** cards. The worker extracts the actual PDF, runs the real
  grounded graph/pipeline with a scripted underproducing provider, and
  finishes with one encrypted validated candidate. It keeps the requested
  count at 20, creates no partial set, and retains the temporary source until
  the owner confirms an exact target of one.
- The test verifies the selected card's exact source quote remains in the
  PDF page, its four options are distinct and include the answer, it is
  unapproved and carries page one provenance. Confirmation creates exactly
  one unpublished set/card, clears both the encrypted candidate stage and
  temporary source, and makes no further provider request.
- Focused two-case run: **2 passed, 11 deselected**. Whole candidate-choice
  test module: **13 passed**. No paid provider, new indexing, retained DB or
  volume write, root `.env` change or live Ask activation occurred.

## Evidence limits

The source and provider behavior are synthetic. This checks the whole
one-fact extraction/shortfall/choice contract under a large requested count;
it does not measure whether a real sparse published lecture yields a useful
card with Gemini, whether Week 3 will reliably produce 20 cards, or instructor
pedagogical ratings. The independent Ask source-usefulness and release gates
remain open. No Lane 6 checkbox was changed.
