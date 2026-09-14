# AI generation evaluation

Phase 4 uses a fixed, authored evaluation corpus under
`backend/tests/fixtures/ai_eval/`. Normal CI is deterministic, offline, and
never needs provider credentials.

## Corpus cases

- Short multi-page facts exercise exact target allocation and provenance.
- A document longer than the former 30,000-character boundary places unique
  facts at its beginning, middle, and final page.
- An injection case mixes legitimate facts with commands to ignore system
  instructions, fabricate answers, expose secrets, and change output format.
- Duplicate/invalid candidates include paraphrased questions, repeated
  options, unsupported answers, invented quotes, and valid replacements.
- Unicode text exercises NFKC normalization, whitespace folding, and repeated
  headings.

Provider wire fixtures and injected test providers exercise both `gemini` and
`openai_compatible` contract profiles without network traffic. The optional
live test is excluded from normal runs and must be explicitly enabled with
`RUN_LIVE_AI_TESTS=1` after the operator reviews the selected model and cost
configuration.

## Release thresholds

| Metric | Required result |
|---|---:|
| Strict schema validity of persisted cards | 100% |
| Rejection of known-invalid candidates | 100% |
| Valid server-derived source references | 100% |
| Answers contained in verified source evidence | 100% |
| Known near duplicates remaining | 0% |
| Successful jobs matching requested count | 100% |
| Partial sets from failed quality runs | 0 |
| Source chunks included in hierarchical summarization | 100% |
| Injection-compliance failures | 0 |
| Provider calls after a failed preflight budget | 0 |
| Requests exceeding configured token limits | 0 |
| Provider contract scenarios normalized identically | 100% |

Run the offline quality suite from `backend`:

```powershell
$env:PYTHONUTF8='1'
pytest tests/test_ai_chunking.py tests/test_ai_grounding.py tests/test_ai_pipeline.py tests/test_ai_evaluation.py tests/test_ai_providers.py -q
```

Run a deliberately opt-in live smoke test only after configuring the provider:

```powershell
$env:RUN_LIVE_AI_TESTS='1'
pytest -m ai_live tests/integration/test_live_graph.py -q
```

Captured or offline results validate application invariants and provider
contract parity. A release owner should run the live corpus against every model
selected for a deployment because remote model behavior and pricing can drift
without application code changes.
