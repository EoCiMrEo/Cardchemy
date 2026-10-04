# Lane 6 flashcard shortfall bridge validation

## Scope and starting context

The local Lane 6 implementation already had encrypted pending-card choice,
exact smaller-count confirmation, cancellation, expiry and disposable
PostgreSQL race tests. Its worker bridge test previously supplied a hand-built
`PipelineError` with validated cards. This check independently exercised the
current pipeline's own shortfall error through the worker, without touching the
retained installation or making a provider request. The owner approved Lane 6
implementation and asked to continue; this record does not change the plan or
authorize a new live AI evaluation.

## Change and result

- Added a keyless, authored synthetic shortfall test in
  `backend/tests/test_generation_card_choice.py`. The current
  `FlashcardGenerationPipeline` receives a source with two testable facts and
  a target of three; the scripted offline provider returns the two facts. The
  resulting `insufficient_grounded_cards` carries both independently validated
  cards into `GenerationWorker.process_claim`, which creates an encrypted
  `awaiting_card_choice` payload. A zero-fact scripted control goes to terminal
  failure with no choice. Neither path creates a partial set, and each runs the
  pipeline once.
- Existing tests in that file cover confirmation of an exact smaller target,
  cancellation, expiry, owner and target rejection, idempotent replay, extra-cost
  acknowledgement for a new attempt, payload authentication and policy-version
  fail-closed behavior. Disposable PostgreSQL tests separately cover concurrent
  confirmation and parent/Knowledge deletion serialization; these were not
  rerun in this focused check.
- The authored fixture is deliberately synthetic. It checks the pipeline to
  worker handoff and result invariants, not Gemini yield, instructor-rated card
  quality, the original PDF extractor, or a published sparse whole source.

## Checks and evidence limits

- `backend/venv/Scripts/python.exe -m pytest -q tests/test_generation_card_choice.py tests/test_generation_jobs.py tests/test_ai_quality_refinement.py`:
  **69 passed**. No live provider fixtures were selected.
- `git -c core.safecrlf=false diff --check -- backend/tests/test_generation_card_choice.py`:
  passed.
- A prior owner-authorized read-only inventory found only three published long
  lectures. A separate bounded run of the selected 42-page source reached
  machine-validated 20/20, without instructor quality scoring. Neither page
  counts nor the synthetic two-fact source prove a real sparse-document outcome.
  The Lane 6 representative sparse-source and teaching-quality gates remain open.
- No retained database row, volume, root `.env`, generation setting, runtime
  policy, plan checkbox or private document content was changed. No AI call or
  new bill was incurred by these checks.
