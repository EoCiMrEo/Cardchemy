# Lane 6 extracted-PDF shortfall-to-choice rehearsal

Date: 2026-09-28 (America/Chicago). Scope: strengthen the existing keyless
flashcard smaller-target bridge without touching the retained database,
published Knowledge, root `.env` or any live provider. Branch `main` at
`6c02d6c`; preserve the shared working tree and prior dated evidence.

Earlier provider-free tests exercised pipeline-to-worker staging with a fake
PDF signature and tested extraction separately. The new
[`test_generation_card_choice.py`](../../../backend/tests/test_generation_card_choice.py)
case creates an authored one-page PDF, reserves/uploads it to disposable
in-memory SQLite, lets the real worker extract and prepare it, and injects a
scripted underproducing provider into the real graph/pipeline. For target
three, it verifies exactly two validated candidates in encrypted pending
storage, no premature set, original requested count unchanged, retained
temporary source and no candidate plaintext in storage. Exact-two owner
confirmation then creates one unpublished set with two unapproved page-one
cards, clears stage/source, and makes **zero additional provider calls**.

The focused extraction/choice/generation/PDF tests passed **80/80** in 16.71
seconds. The post-edit complete backend offline suite passed **2,266** tests
with 147 skipped and two live tests deselected in 210.19 seconds.
This is a meaningful extraction-to-choice integration proof with a
scripted provider. It does not establish that a truly sparse published whole
source yields two useful cards with Gemini, that the original Week-3 failure
will never recur, or that an instructor rates the cards pedagogically useful.
The existing 42-page private-source 20-card read-only live diagnostic remains
the sole feasible live sample and created no set. Those separate quality and
sparse-source gates remain open.
